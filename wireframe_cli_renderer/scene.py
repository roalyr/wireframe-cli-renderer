#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/scene.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 3.1
# LOG_REF: 2026-02-19
#

from .mesh import Mesh


class Scene:
    """
    Container for renderable objects.

    Each entry is a (Mesh, (ox, oy, oz)) pair representing a mesh instance
    placed at a world-space offset.  Multiple instances may share the same
    Mesh object.
    """

    def __init__(self):
        self.objects = []  # list of (Mesh, (float, float, float))

    def add(self, mesh: Mesh, translation=(0.0, 0.0, 0.0)):
        """Add a mesh instance at the given world position.

        Args:
            mesh: Mesh to render.
            translation: (x, y, z) world offset tuple.
        """
        if isinstance(translation, (list, tuple)) and len(translation) >= 3:
            pos = (float(translation[0]), float(translation[1]), float(translation[2]))
        else:
            pos = (0.0, 0.0, 0.0)
        self.objects.append((mesh, pos))

    def clear(self):
        """Remove all objects from the scene."""
        self.objects.clear()
