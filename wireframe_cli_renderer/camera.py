#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/camera.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 7
# LOG_REF: 2026-02-19
#

class Camera:
    """
    Camera state for the wireframe renderer.

    Stores orbital rotation angles (pitch/yaw), distance from origin,
    field-of-view, near/far clip planes, and face-winding flip flag.

    The renderer reads these values directly and computes the inline
    rotation matrix + perspective projection per frame (matching the
    original monolithic script's math exactly).
    """
    __slots__ = ('pitch', 'yaw', 'distance', 'fov', 'near', 'far', 'flip')

    def __init__(self, fov: float = 60.0, distance: float = 6.0,
                 near: float = 0.1, far: float = 150.0):
        self.pitch = 0.0         # Rotation around X axis (radians) — 'ax' in original
        self.yaw = 0.0           # Rotation around Y axis (radians) — 'ay' in original
        self.distance = distance # Camera Z offset — 'cam_z' in original
        self.fov = fov           # Field of view (degrees)
        self.near = near         # Near clip plane
        self.far = far           # Far clip plane
        self.flip = False        # Winding-order flip toggle

    def orbit(self, dyaw: float, dpitch: float):
        """Adjust orbital angles by delta (radians)."""
        self.yaw += dyaw
        self.pitch += dpitch

    def zoom(self, delta: float):
        """Adjust camera distance. Positive = further, negative = closer."""
        self.distance = max(0.5, self.distance + delta)

    def adjust_fov(self, delta: float):
        """Adjust field of view by delta degrees, clamped to [10, 170]."""
        self.fov = max(10, min(170, self.fov + delta))
