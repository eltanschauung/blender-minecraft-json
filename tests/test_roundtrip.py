"""Run with Blender --background --factory-startup --python-exit-code 1 --python ...

MC_JSON_MODEL may point at a local model; no external assets are committed here.
"""
import itertools
import json
import math
import os
import tempfile
from pathlib import Path

exec((Path(__file__).parent / 'reproduce_import.py').read_text().split("path=os.environ")[0])
from mathutils import Matrix, Vector
from minecraft_json_fork.io_scene_minecraft_json.transforms import BASIS, rotation_matrix


def world_corners(element):
    rotation = element.get('rotation', {})
    pivot = Vector(rotation.get('origin', [0, 0, 0]))
    matrix = rotation_matrix(rotation)
    return [pivot + matrix @ (Vector(point) - pivot)
            for point in itertools.product(*zip(element['from'], element['to']))]


def compare_geometry(source, exported, transform=lambda p: p):
    assert len(source['elements']) == len(exported['elements'])
    error = 0
    for before, after in zip(source['elements'], exported['elements']):
        actual = world_corners(after)
        for expected in map(transform, world_corners(before)):
            error = max(error, min((expected - p).length for p in actual))
    assert error < 0.0001, error


source_path = Path(os.environ.get('MC_JSON_MODEL', Path(__file__).parent/'fixtures/rotations.json'))
source = json.loads(source_path.read_text())
assert bpy.ops.minecraft.import_json(filepath=str(source_path)) == {'FINISHED'}
objects = sorted((o for o in bpy.context.scene.objects if o.type == 'MESH'),
                 key=lambda o:o['minecraft_index'])
metadata = json.loads(bpy.data.texts[objects[0]['minecraft_model']].as_string())
offset = Vector(metadata['offset'])
vertices = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
center = Vector([(min(v[i] for v in vertices)+max(v[i] for v in vertices))/2 for i in range(3)])
assert center.length < 1e-5, ('Import was not centered', center)

with tempfile.TemporaryDirectory(prefix='minecraft-json-roundtrip-') as directory:
    output = str(Path(directory)/'exported.json')
    def export():
        assert bpy.ops.minecraft.export_json(filepath=output) == {'FINISHED'}
        return json.loads(Path(output).read_text())

    exported = export()
    compare_geometry(source, exported)
    assert sum(len(e['faces']) for e in source['elements']) == sum(len(e['faces']) for e in exported['elements'])
    assert exported.get('display') == source.get('display')
    assert exported.get('groups') == source.get('groups')
    for a,b in zip(source['elements'], exported['elements']):
        assert a['faces'] == b['faces'], 'Untouched face metadata or UVs changed'
    if source_path.name == 'ibuki_gourd_3d.json':
        assert exported['textures']['0'] == 'lunatic:item/ibuki_gourd_3d'
        assert len(objects) == 2764

    # Real Object Mode half-turn, without applying transforms or snapping angles.
    original = [o.matrix_world.copy() for o in objects]
    turn = Matrix.Rotation(math.pi, 4, 'Z')
    bpy.ops.transform.rotate(value=math.pi, orient_axis='Z', center_override=(0,0,0))
    bpy.context.view_layer.update()
    exported = export()
    compare_geometry(source, exported,
                     lambda p: offset + BASIS.transposed() @ turn.to_3x3() @ BASIS @ (p-offset))

    # Compound rotations must also survive; old exporter rounded to 90/45 degrees.
    turn = Matrix.Rotation(math.radians(23),4,'X') @ Matrix.Rotation(math.radians(31),4,'Y')
    for obj,matrix in zip(objects,original):
        obj.matrix_world = turn @ matrix
    bpy.context.view_layer.update()
    compare_geometry(source, export(),
                     lambda p: offset + BASIS.transposed() @ turn.to_3x3() @ BASIS @ (p-offset))

    # Metadata and original resource identifiers must persist in a saved .blend.
    blend = str(Path(directory)/'roundtrip.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    bpy.ops.wm.open_mainfile(filepath=blend)
    compare_geometry(source, export(),
                     lambda p: offset + BASIS.transposed() @ turn.to_3x3() @ BASIS @ (p-offset))

print('PASS: no-op, 180-degree and compound rotation, metadata, .blend persistence;', len(objects), 'cuboids')
