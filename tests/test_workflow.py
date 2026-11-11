"""Import into a normal nonempty scene; export must exclude unrelated meshes."""
import json
import tempfile
from pathlib import Path
exec((Path(__file__).parent/'reproduce_import.py').read_text().split("path=os.environ")[0])
bpy.ops.mesh.primitive_cube_add()
unrelated = bpy.context.object
source = Path(__file__).parent/'fixtures/rotations.json'
bpy.ops.minecraft.import_json(filepath=str(source))
assert unrelated not in bpy.context.selected_objects
assert bpy.context.view_layer.objects.active in bpy.context.selected_objects
assert bpy.context.view_layer.objects.active.get('minecraft_index')==0
with tempfile.TemporaryDirectory(prefix='minecraft-json-selection-') as directory:
    target = Path(directory)/'exported.json'
    assert bpy.ops.minecraft.export_json(filepath=str(target))=={'FINISHED'}
    assert len(json.loads(target.read_text())['elements'])==2
print('PASS: imported objects active/selected, default export excludes unrelated startup cube')
