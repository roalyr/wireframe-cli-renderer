#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/mesh.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 6.1
# LOG_REF: 2026-02-19
#

import sys

class Mesh:
    def __init__(self, filename=None):
        self.vertices = []
        self.faces = []
        if filename:
            self.load_from_obj(filename)
        else:
            # None or empty string: generate demo cube (matches original behavior)
            self._make_demo_cube()

    def load_from_obj(self, filename):
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('v '):
                        self.vertices.append([float(x) for x in line.split()[1:4]])
                    elif line.startswith('f '):
                        # Handle v/vt/vn format by splitting by '/'
                        face = [int(x.split('/')[0]) - 1 for x in line.split()[1:]]
                        self.faces.append(face)
        except Exception as e:
            print(f"Warning: Could not load '{filename}': {e}", file=sys.stderr)
            # If load fails, we don't fall back to cube automatically in the library, 
            # but the CLI might want that. 
            # The original code acted as if the file was empty if it failed, then checked `if not self.vertices`.
            self.vertices, self.faces = [], []

        if not self.vertices or not self.faces:
             # Original behavior fallback
             self._make_demo_cube()

    def _make_demo_cube(self):
        """Generate a unit cube centered at origin as fallback geometry."""
        self.vertices = [
            [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],
            [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1],
        ]
        self.faces = [
            [0, 1, 2, 3],  # front
            [5, 4, 7, 6],  # back
            [4, 0, 3, 7],  # left
            [1, 5, 6, 2],  # right
            [3, 2, 6, 7],  # top
            [4, 5, 1, 0],  # bottom
        ]

    @classmethod
    def cube(cls):
        """Factory method to create a mesh with a demo cube."""
        return cls()  # No filename → _make_demo_cube()

    @classmethod
    def from_obj(cls, filename):
        """Factory method to create a mesh from an OBJ file."""
        return cls(filename)
