#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/__init__.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 8.3
# LOG_REF: 2026-02-19
#

from .math_utils import Vec3, Mat4
from .config import RenderConfig
from .color import parse_hex_color, init_colors
from .canvas import Canvas
from .mesh import Mesh
from .camera import Camera
from .scene import Scene
from .renderer import Renderer
from .fog import FogModel
