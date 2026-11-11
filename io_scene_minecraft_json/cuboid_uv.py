"""Minecraft face corners and rectangular UV conversion shared by import/export."""
from mathutils import Vector
from .transforms import BASIS

CORNERS = {
    'down': [(0,0,1),(0,0,0),(1,0,0),(1,0,1)],
    'up': [(0,1,0),(0,1,1),(1,1,1),(1,1,0)],
    'north': [(1,1,0),(1,0,0),(0,0,0),(0,1,0)],
    'south': [(0,1,1),(0,0,1),(1,0,1),(1,1,1)],
    'west': [(0,1,0),(0,0,0),(0,0,1),(0,1,1)],
    'east': [(1,1,1),(1,0,1),(1,0,0),(1,1,0)],
}
NORMALS = {'west':(-1,0,0),'east':(1,0,0),'down':(0,-1,0),'up':(0,1,0),'north':(0,0,-1),'south':(0,0,1)}

def direction(normal):
    face = max(NORMALS, key=lambda key: Vector(NORMALS[key]).dot(normal))
    if Vector(NORMALS[face]).dot(normal) < .999:
        raise ValueError('Mesh faces must be axis-aligned cuboids; rotate objects in Object Mode')
    return face


def default_uv(lo, hi, face):
    x,y,z=lo; X,Y,Z=hi
    return {'down':[x,16-Z,X,16-z],'up':[x,z,X,Z],
            'north':[16-X,16-Y,16-x,16-y],'south':[x,16-Y,X,16-y],
            'west':[z,16-Y,Z,16-y],'east':[16-Z,16-Y,16-z,16-y]}[face]


def polygon_corners(mesh, poly, points, lo, hi, face):
    result = [None] * 4
    for loop_index in poly.loop_indices:
        point = points[mesh.loops[loop_index].vertex_index]
        selector = tuple(0 if abs(point[i]-lo[i]) <= abs(point[i]-hi[i]) else 1 for i in range(3))
        try:
            index = CORNERS[face].index(selector)
        except ValueError as exc:
            raise ValueError('Only rectangular cuboid faces can be exported') from exc
        if result[index] is not None:
            raise ValueError('Duplicate cuboid corner')
        result[index] = loop_index
    if any(i is None for i in result):
        raise ValueError('Each cuboid face must have four corners')
    return result


def encode_uv(mesh, poly, points, lo, hi, face, preferred=0):
    if not mesh.uv_layers.active:
        return {'uv':default_uv(lo,hi,face)}
    indices=polygon_corners(mesh,poly,points,lo,hi,face)
    actual=[(mesh.uv_layers.active.data[i].uv.x*16, (1-mesh.uv_layers.active.data[i].uv.y)*16) for i in indices]
    for angle in dict.fromkeys([preferred,0,90,180,270]):
        values=[None]*4
        for i,uv in enumerate(actual):
            values[(i+angle//90)%4]=uv
        u,v=values[0];U,V=values[2]
        expected=[(u,v),(u,V),(U,V),(U,v)]
        if all(abs(a-b)<1e-4 for xy,XY in zip(values,expected) for a,b in zip(xy,XY)):
            result={'uv':[u,v,U,V]}
            if angle:result['rotation']=angle
            return result
    raise ValueError('Minecraft requires rectangular UVs (including 90-degree rotations and mirroring); unwrap this face to a rectangle')


def apply_face_data(obj, element, textures, import_uvs=True):
    """Map UVs by Minecraft corner identity, rather than Blender polygon order."""
    mesh = obj.data
    points = [BASIS.transposed() @ vertex.co for vertex in mesh.vertices]
    lo = [min(v[i] for v in points) for i in range(3)]
    hi = [max(v[i] for v in points) for i in range(3)]
    materials = {}
    for polygon in mesh.polygons:
        face = direction(BASIS.transposed() @ polygon.normal)
        data = element['faces'][face]
        if import_uvs:
            rectangle = data.get('uv', default_uv(element['from'], element['to'], face))
            rotation = data.get('rotation', 0)
            if rotation not in (0,90,180,270):
                raise ValueError('Face UV rotation must be 0, 90, 180 or 270 degrees')
            for i,index in enumerate(polygon_corners(mesh, polygon, points, lo, hi, face)):
                j = (i + rotation // 90) % 4
                mesh.uv_layers.active.data[index].uv = (
                    rectangle[0 if j < 2 else 2] / 16,
                    1 - rectangle[1 if j in (0,3) else 3] / 16,
                )
        name = data.get('texture', '')
        if name.startswith('#'):
            name = name[1:]
        if name in textures:
            if name not in materials:
                materials[name] = len(mesh.materials)
                mesh.materials.append(textures[name])
            polygon.material_index = materials[name]

