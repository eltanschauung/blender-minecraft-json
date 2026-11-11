"""Coordinate and rotation conversion shared by the modern JSON path."""
import math
from mathutils import Matrix, Euler, Vector

# (Minecraft X,Y,Z) -> (Blender Z,X,Y), a right-handed basis change.
BASIS = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))

def rotation_matrix(rotation):
    if not rotation:
        return Matrix.Identity(3)
    if 'axis' in rotation or 'angle' in rotation:
        angles = [0.0, 0.0, 0.0]
        angles['xyz'.index(rotation['axis'].lower())] = math.radians(rotation['angle'])
    else:
        angles = [math.radians(rotation.get(axis, 0.0)) for axis in 'xyz']
    matrix = Euler(angles, 'XYZ').to_matrix()
    if rotation.get('rescale', False):
        scales = [1.0 / max(abs(matrix[row][col]) for row in range(3)) for col in range(3)]
        matrix = matrix @ Matrix.Diagonal(Vector(scales))
    return matrix
