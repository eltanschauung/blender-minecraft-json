"""Verify renderer corner orientation, sparse faces and edited UV round trips."""
import copy
import json
import math
import os
import tempfile
from pathlib import Path
exec((Path(__file__).parent/'reproduce_import.py').read_text().split("path=os.environ")[0])
from mathutils import Vector
from minecraft_json_fork.io_scene_minecraft_json.transforms import BASIS
from minecraft_json_fork.io_scene_minecraft_json.cuboid_uv import direction


def objects():
    return sorted((o for o in bpy.context.scene.objects if o.type=='MESH'), key=lambda o:o['minecraft_index'])


def snapshot(items):
    return [[tuple(loop.uv) for loop in obj.data.uv_layers.active.data] for obj in items]


def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


with tempfile.TemporaryDirectory(prefix='minecraft-json-uv-') as directory:
    directory = Path(directory)
    model = directory/'assets/test/models/item/cube.json'
    model.parent.mkdir(parents=True)
    image = directory/'assets/test/textures/item/cube.png'
    image.parent.mkdir(parents=True)
    texture = bpy.data.images.new('test', width=16, height=16)
    texture.filepath_raw = str(image)
    texture.file_format = 'PNG'
    texture.save()
    faces = {name:{'texture':'#0','uv':[1,2,11,13]}
             for name in ('north','south','west','east','down','up')}
    # Where the top-left UV corner must lie on each Minecraft face.
    top_left = {'north':(2,3,0),'south':(0,3,4),'west':(0,3,0),
                'east':(2,3,4),'down':(0,0,4),'up':(0,3,0)}
    document = {'textures':{'0':'test:item/cube'},
                'elements':[{'from':[0,0,0],'to':[2,3,4],'faces':faces}]}
    model.write_text(json.dumps(document))
    bpy.ops.minecraft.import_json(filepath=str(model), recenter_to_origin=False)
    obj = objects()[0]
    for polygon in obj.data.polygons:
        face = direction(BASIS.transposed() @ polygon.normal)
        matching = [index for index in polygon.loop_indices
                    if (BASIS.transposed() @ (obj.matrix_world @ obj.data.vertices[obj.data.loops[index].vertex_index].co)
                        - Vector(top_left[face])).length < 1e-5]
        assert len(matching)==1, (face,matching)
        uv = obj.data.uv_layers.active.data[matching[0]].uv
        assert (uv-Vector((1/16,1-2/16))).length < 1e-6, (face,uv)

    # Import rotated and mirrored rectangles, then edit them with a UV quarter-turn.
    clear()
    for index,value in enumerate(faces.values()):
        value['rotation'] = (index%4)*90
        if index%2:value['uv'] = [11,2,1,13]
    model.write_text(json.dumps(document))
    bpy.ops.minecraft.import_json(filepath=str(model))
    obj = objects()[0]
    for loop in obj.data.uv_layers.active.data:
        u,v = loop.uv
        loop.uv = (1-v+1/16, u-2/16)
    expected = snapshot(objects())
    output = model.with_name('edited.json')
    bpy.ops.minecraft.export_json(filepath=str(output))
    clear()
    bpy.ops.minecraft.import_json(filepath=str(output))
    for before,after in zip(expected,snapshot(objects())):
        assert max(abs(x-y) for a,b in zip(before,after) for x,y in zip(a,b)) < 1e-6

    # Unsupported UV shear must report failure and preserve an existing export.
    previous = output.read_bytes()
    objects()[0].data.uv_layers.active.data[0].uv.x += .01
    try:
        result = bpy.ops.minecraft.export_json(filepath=str(output))
        assert result == {'CANCELLED'}
    except RuntimeError as error:
        assert 'rectangular UVs' in str(error)
    assert output.read_bytes()==previous

    path = os.environ.get('MC_JSON_MODEL')
    if path:
        clear()
        bpy.ops.minecraft.import_json(filepath=path)
        original = json.loads(Path(path).read_text())
        imported = objects()
        assert sum(len(o.data.polygons) for o in imported)==sum(len(e['faces']) for e in original['elements'])
        for obj in imported:
            for loop in obj.data.uv_layers.active.data:
                loop.uv += Vector((1/16,-2/16))
        expected = snapshot(imported)
        # Export into a temporary pack; use the real source texture read-only.
        real_image = Path(path).parents[2]/'textures/item/ibuki_gourd_3d.png'
        target = directory/'assets/lunatic/textures/item/ibuki_gourd_3d.png'
        target.parent.mkdir(parents=True)
        target.symlink_to(real_image)
        output = directory/'assets/lunatic/models/item/gourd.json'
        bpy.ops.minecraft.export_json(filepath=str(output))
        clear()
        bpy.ops.minecraft.import_json(filepath=str(output))
        actual = snapshot(objects())
        assert len(expected)==len(actual)
        assert max(abs(x-y) for before,after in zip(expected,actual)
                   for a,b in zip(before,after) for x,y in zip(a,b)) < 1e-6
        assert sum(len(o.data.polygons) for o in objects())==5288

print('PASS: all six face orientations, rotated/mirrored UV edits, sparse faces, safe failure, real-model UV round trip')
