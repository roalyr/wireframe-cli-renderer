#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/math_utils.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 3.1
# LOG_REF: 2026-02-19
#

import math

class Vec3:
    """Immutable 3-component vector."""
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x: float, y: float, z: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __repr__(self):
        return f"Vec3({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __getitem__(self, index):
        if index == 0: return self.x
        if index == 1: return self.y
        if index == 2: return self.z
        raise IndexError("Vec3 index out of range")

    def __add__(self, other):
        if isinstance(other, Vec3):
            return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
        if hasattr(other, 'x') and hasattr(other, 'y') and hasattr(other, 'z'):
             return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
        # Assuming scalar or iterable? sticking to simple for now.
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Vec3):
            return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
        return NotImplemented

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __truediv__(self, scalar):
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def dot(self, other) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other) -> 'Vec3':
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )

    def magnitude(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalize(self) -> 'Vec3':
        m = self.magnitude()
        if m == 0:
            return Vec3(0, 0, 0)
        return self / m


class Mat4:
    """4x4 Matrix for transforms (row-major internally for storage, logic depends on convention).
    Here utilizing [row][col] storage.
    """
    __slots__ = ('m',)

    def __init__(self, data=None):
        if data:
            self.m = data
        else:
            self.m = [[0.0]*4 for _ in range(4)]
            # Identity by default? No, explicit identity() factory is better.

    @classmethod
    def identity(cls) -> 'Mat4':
        res = cls()
        for i in range(4):
            res.m[i][i] = 1.0
        return res

    @classmethod
    def translation(cls, x, y, z) -> 'Mat4':
        mat = cls.identity()
        mat.m[0][3] = x
        mat.m[1][3] = y
        mat.m[2][3] = z
        return mat

    @classmethod
    def scale(cls, sx, sy, sz) -> 'Mat4':
        mat = cls.identity()
        mat.m[0][0] = sx
        mat.m[1][1] = sy
        mat.m[2][2] = sz
        return mat

    @classmethod
    def rotation_x(cls, rad: float) -> 'Mat4':
        mat = cls.identity()
        c = math.cos(rad)
        s = math.sin(rad)
        mat.m[1][1] = c
        mat.m[1][2] = -s
        mat.m[2][1] = s
        mat.m[2][2] = c
        return mat

    @classmethod
    def rotation_y(cls, rad: float) -> 'Mat4':
        mat = cls.identity()
        c = math.cos(rad)
        s = math.sin(rad)
        mat.m[0][0] = c
        mat.m[0][2] = s
        mat.m[2][0] = -s
        mat.m[2][2] = c
        return mat

    @classmethod
    def rotation_z(cls, rad: float) -> 'Mat4':
        mat = cls.identity()
        c = math.cos(rad)
        s = math.sin(rad)
        mat.m[0][0] = c
        mat.m[0][1] = -s
        mat.m[1][0] = s
        mat.m[1][1] = c
        return mat

    def __matmul__(self, other):
        # Matrix multiplication
        if isinstance(other, Mat4):
            res = Mat4()
            for r in range(4):
                for c in range(4):
                    val = 0.0
                    for k in range(4):
                        val += self.m[r][k] * other.m[k][c]
                    res.m[r][c] = val
            return res
        return NotImplemented

    def mul_vec3(self, v: Vec3) -> Vec3:
        """Multiply with Vec3 as if w=1, return Vec3 (ignoring w result)."""
        x = self.m[0][0]*v.x + self.m[0][1]*v.y + self.m[0][2]*v.z + self.m[0][3]
        y = self.m[1][0]*v.x + self.m[1][1]*v.y + self.m[1][2]*v.z + self.m[1][3]
        z = self.m[2][0]*v.x + self.m[2][1]*v.y + self.m[2][2]*v.z + self.m[2][3]
        return Vec3(x, y, z)

    def mul_vec3_project(self, v: Vec3) -> Vec3:
        """Multiplying handling w division if needed, though for standard
        affine transforms w=1 stays 1. PROJECTION matrices will change w."""
        x = self.m[0][0]*v.x + self.m[0][1]*v.y + self.m[0][2]*v.z + self.m[0][3]
        y = self.m[1][0]*v.x + self.m[1][1]*v.y + self.m[1][2]*v.z + self.m[1][3]
        z = self.m[2][0]*v.x + self.m[2][1]*v.y + self.m[2][2]*v.z + self.m[2][3]
        w = self.m[3][0]*v.x + self.m[3][1]*v.y + self.m[3][2]*v.z + self.m[3][3]
        if w != 1.0 and w != 0.0:
            return Vec3(x/w, y/w, z/w)
        return Vec3(x, y, z)

