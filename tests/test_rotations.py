"""Run with blender --background --factory-startup --python-exit-code 1 --python tests/test_rotations.py."""
exec(open(__file__.replace('test_rotations.py','reproduce_import.py')).read().split("path=os.environ")[0])
from minecraft_json_fork.io_scene_minecraft_json.transforms import rotation_matrix, BASIS
from mathutils import Vector, Euler
import math
for rotation in [{'axis':'y','angle':180}, {'x':0,'y':180,'z':0}, {'x':12,'y':31,'z':-23}]:
    actual=rotation_matrix(rotation)
    angles=[rotation.get(a,0) for a in 'xyz'] if 'axis' not in rotation else [0,180,0]
    expected=Euler([math.radians(a)for a in angles],'XYZ').to_matrix()
    assert max(abs(actual[r][c]-expected[r][c])for r in range(3)for c in range(3))<1e-6
    p=Vector((2,3,5)); assert ((BASIS@actual@BASIS.transposed())@(BASIS@p)-BASIS@(actual@p)).length<1e-5
print('PASS legacy single-axis, 180-degree and compound XYZ rotations')
