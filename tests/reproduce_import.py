import sys,os,importlib.util,time
from pathlib import Path
import bpy
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('minecraft_json_fork',root/'__init__.py',submodule_search_locations=[str(root)]);addon=importlib.util.module_from_spec(spec);sys.modules[spec.name]=addon;spec.loader.exec_module(addon);addon.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
path=os.environ['MC_JSON_MODEL'];start=time.monotonic();print('IMPORT',path,flush=True)
bpy.ops.minecraft.import_json(filepath=path)
print('PASS',len([o for o in bpy.context.scene.objects if o.type=='MESH']),time.monotonic()-start,flush=True)
