"""Modern cuboid export: preserve imported data and export actual Blender transforms.

No rotation snapping, automatic resizing, or silent dropping of unsupported meshes.
The older generated-colour/bone exporter remains available as an explicit legacy mode.
"""
import copy
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from .transforms import BASIS
from .resources import asset_layout

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


def remember_element(obj, element, index):
    obj['minecraft_element'] = json.dumps(element)
    obj['minecraft_index'] = index
    obj['minecraft_import_name'] = obj.name
    # The unedited UV layout can be carried through verbatim, including mirrored bounds.
    obj['minecraft_uv_baseline'] = json.dumps([list(v.uv) for v in obj.data.uv_layers.active.data])


def remember_model(context, data, filepath, objects, offset):
    header = copy.deepcopy(data)
    header.pop('elements', None)
    text = bpy.data.texts.new('Minecraft JSON: ' + Path(filepath).name)
    text['minecraft_model'] = True
    text.write(json.dumps({'header':header, 'offset':list(offset), 'source':str(Path(filepath).resolve())}))
    for obj in objects:
        obj['minecraft_model'] = text.name


def source_model(objects):
    keys = {o.get('minecraft_model') for o in objects if o.get('minecraft_model')}
    if len(keys) > 1:
        raise ValueError('Multiple imported models selected; export one model at a time')
    if not keys:
        return {'header':{},'offset':[8,8,8]}
    key = keys.pop()
    text = bpy.data.texts.get(key)
    if text is None:
        raise ValueError('Missing imported Minecraft metadata text: ' + key)
    return json.loads(text.as_string())


def image_identifier(material, output):
    if material is None:
        raise ValueError('Every newly added face needs an image-textured material')
    if material.get('minecraft_texture'):
        return material['minecraft_texture']
    if material.node_tree:
        for node in material.node_tree.nodes:
            if node.type != 'TEX_IMAGE' or not node.image:
                continue
            path = Path(bpy.path.abspath(node.image.filepath)).resolve()
            root, namespace = asset_layout(path)
            if root:
                relative = path.relative_to(root / namespace / 'textures')
                return namespace + ':' + relative.with_suffix('').as_posix()
            _, namespace = asset_layout(output)
            if namespace:
                return namespace + ':item/' + path.stem
    raise ValueError('Material needs a resource texture identifier or an image inside assets/<namespace>/textures')


def texture_slot(material, textures, output):
    identifier = image_identifier(material, output)
    for slot, value in textures.items():
        if value == identifier:
            return '#' + slot
    index = 0
    while str(index) in textures:
        index += 1
    textures[str(index)] = identifier
    return '#' + str(index)


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


def export_element(obj, offset, textures, filepath):
    mesh = obj.data
    if obj.modifiers:
        raise ValueError(obj.name + ': apply modifiers before cuboid export')
    if len(mesh.vertices) != 8 or any(len(p.vertices)!=4 for p in mesh.polygons):
        raise ValueError(obj.name + ': Minecraft JSON supports eight-vertex cuboids, not arbitrary meshes')
    points=[BASIS.transposed() @ v.co for v in mesh.vertices]
    lo=Vector([min(v[i]for v in points)for i in range(3)])
    hi=Vector([max(v[i]for v in points)for i in range(3)])
    if any(hi[i]-lo[i]<1e-7 for i in range(3)):
        raise ValueError(obj.name + ': zero-volume or flattened cuboid')
    corners={tuple(round(v[i],5)for i in range(3))for v in points}
    expected={tuple(round(v,5) for v in (x,y,z))for x in (lo.x,hi.x)for y in (lo.y,hi.y)for z in (lo.z,hi.z)}
    if corners != expected:
        raise ValueError(obj.name + ': mesh is not an axis-aligned cuboid; use Object Mode rotation')
    basis=BASIS.to_4x4()
    transform=Matrix.Translation(Vector(offset)) @ basis.inverted() @ obj.matrix_world @ basis
    location, quaternion, scale=transform.decompose()
    rotation=quaternion.to_matrix()
    reconstructed=Matrix.LocRotScale(location,quaternion,scale)
    if max(abs(transform[r][c]-reconstructed[r][c])for r in range(4)for c in range(4))>1e-4:
        raise ValueError(obj.name + ': sheared transforms cannot be represented as a Minecraft cuboid')
    if any(v<=0 for v in scale):
        raise ValueError(obj.name + ': apply negative scale and recalculate normals before export')
    data=json.loads(obj.get('minecraft_element','{}'))
    result=copy.deepcopy(data)
    if obj.name != obj.get('minecraft_import_name'):
        result['name']=obj.name
    result['from']=[location[i]+lo[i]*scale[i] for i in range(3)]
    result['to']=[location[i]+hi[i]*scale[i] for i in range(3)]
    angles=rotation.to_euler('XYZ')
    if max(abs(v)for v in angles)>1e-7:
        result['rotation']={'origin':list(location),**{a:math.degrees(angles[i])for i,a in enumerate('xyz')}}
    else:
        result.pop('rotation',None)
    original_faces=data.get('faces',{})
    baseline=json.loads(obj.get('minecraft_uv_baseline','[]'))
    faces={}
    for poly in mesh.polygons:
        face=direction(BASIS.transposed() @ poly.normal)
        if data and face not in original_faces:
            continue
        original=original_faces.get(face,{})
        value=copy.deepcopy(original)
        unchanged=bool(baseline) and all(i<len(baseline)and all(abs(float(mesh.uv_layers.active.data[i].uv[j])-baseline[i][j])<1e-7 for j in range(2))for i in poly.loop_indices)
        if not unchanged:
            value.pop('rotation',None)
            value.update(encode_uv(mesh,poly,points,lo,hi,face,original.get('rotation',0)))
        material=mesh.materials[poly.material_index] if poly.material_index<len(mesh.materials)else None
        if material is not None:
            value['texture']=texture_slot(material,textures,filepath)
        elif 'texture' not in value:
            raise ValueError(obj.name+': untextured face '+face)
        faces[face]=value
    result['faces']=faces
    return result


def remap_groups(groups, indices):
    result=[]
    for group in groups:
        if not isinstance(group,dict):continue
        copy_group=copy.deepcopy(group)
        children=[]
        for child in group.get('children',[]):
            if isinstance(child,int) and child in indices:children.append(indices[child])
            elif isinstance(child,dict):children.extend(remap_groups([child],indices))
        copy_group['children']=children
        result.append(copy_group)
    return result


def save(context, filepath, selection_only=False, decimal_precision=6, minify=False, **kwargs):
    if context.object and context.object.mode=='EDIT':
        context.object.update_from_editmode()
    objects=[o for o in (context.selected_objects if selection_only else context.scene.objects)if o.type=='MESH']
    if not objects:raise ValueError('No cuboid mesh objects to export')
    objects.sort(key=lambda o:(o.get('minecraft_model',''),o.get('minecraft_index',2**31),o.name))
    metadata=source_model(objects);document=copy.deepcopy(metadata['header'])
    document['format_version']='26.3'
    textures=document.setdefault('textures',{})
    elements=[export_element(obj,metadata['offset'],textures,filepath)for obj in objects]
    document['elements']=elements
    indices={o['minecraft_index']:i for i,o in enumerate(objects)if 'minecraft_index'in o}
    if 'groups'in document:document['groups']=remap_groups(document['groups'],indices)
    def clean(value):
        if isinstance(value,float):return round(value,decimal_precision) if decimal_precision>=0 else value
        if isinstance(value,list):return [clean(v)for v in value]
        if isinstance(value,dict):return {k:clean(v)for k,v in value.items()}
        return value
    path=Path(filepath);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(clean(document),indent=None if minify else 2,allow_nan=False)+'\n')
    temporary.replace(path)
    print('SAVED modern Minecraft JSON:',filepath,'elements:',len(elements))
    return {'FINISHED'}
