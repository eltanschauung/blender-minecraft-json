exec(open(__file__.replace('test_resources.py','reproduce_import.py')).read().split("path=os.environ")[0])
from minecraft_json_fork.io_scene_minecraft_json.resources import resolve_resource
import tempfile
with tempfile.TemporaryDirectory()as temp:
    assets=Path(temp)/'assets';model=assets/'lunatic/models/item/gourd.json';model.parent.mkdir(parents=True);model.write_text('{}')
    image=assets/'lunatic/textures/item/gourd.png';image.parent.mkdir(parents=True);image.touch()
    vanilla=assets/'minecraft/textures/item/apple.png';vanilla.parent.mkdir(parents=True);vanilla.touch()
    assert resolve_resource(model,'lunatic:item/gourd')==('lunatic:item/gourd',image)
    assert resolve_resource(model,'gourd')==('lunatic:item/gourd',image)
    assert resolve_resource(model,'minecraft:item/apple')==('minecraft:item/apple',vanilla)
    assert resolve_resource(model,'minecraft:item/gourd')[0]=='minecraft:item/gourd'
    for bad in ['../secret','evil:../../secret','/secret']:
        try:resolve_resource(model,bad)
        except ValueError:pass
        else:raise AssertionError(bad)
print('PASS namespace resolution, recoverable unqualified exports, cross-namespace paths and traversal rejection')
