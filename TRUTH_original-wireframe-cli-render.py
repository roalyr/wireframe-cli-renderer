#
# PROJECT: wireframe-cli-render
# MODULE: wireframe-cli-render.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 5
# LOG_REF: 2026-02-11
#

import curses
import math
import time
import sys
import random
import os
import argparse
from dataclasses import dataclass

@dataclass
class RenderConfig:
    use_color: bool = True
    use_braille: bool = True
    use_zbuffer: bool = True
    use_culling: bool = True
    use_fog: bool = True
    fog_start: float = 3.0
    fog_end: float = 80.0
    fog_exp: float = 0.6
    near_clip: float = 0.1
    far_plane: float = 150.0
    gradient_steps: int = 12

    @classmethod
    def detect_terminal(cls):
        term = os.environ.get('TERM', '').lower()
        lang = os.environ.get('LANG', '').lower()
        
        # Detect capabilities based on environment
        # Note: accurate color detection requires curses initialization,
        # so this is a pre-init guess.
        
        is_dumb = term in ('dumb', 'unknown')
        is_linux_console = term == 'linux'
        supports_utf8 = 'utf-8' in lang or 'utf8' in lang
        
        return cls(
            use_color=not is_dumb,
            use_braille=supports_utf8 and not is_linux_console, # Linux console font often lacks braille
            use_zbuffer=True,
            use_culling=True
        )

def parse_hex_color(hex_str):
    """
    Parse a hex color string to an (r, g, b) tuple.
    Accepts: '#RRGGBB' or 'RRGGBB' (case-insensitive).
    Returns: (r, g, b) tuple with values 0-255, or None on failure.
    """
    if hex_str is None:
        return None
    val = str(hex_str).strip().lstrip('#')
    if len(val) != 6:
        return None
    try:
        r = int(val[0:2], 16)
        g = int(val[2:4], 16)
        b = int(val[4:6], 16)
        return (r, g, b)
    except ValueError:
        return None

# --- xterm-256 RGB lookup for smooth gradient interpolation ---

# The 6x6x6 color cube occupies indices 16-231.
# Each axis has values: 0, 95, 135, 175, 215, 255
_CUBE_VALUES = [0, 95, 135, 175, 215, 255]

# Grayscale ramp occupies indices 232-255 (24 shades).
# Values: 8, 18, 28, ..., 238

# The first 16 are standard ANSI colors with fixed approximate RGB.
_ANSI_RGB = [
    (0, 0, 0),       # 0  black
    (128, 0, 0),     # 1  red
    (0, 128, 0),     # 2  green
    (128, 128, 0),   # 3  yellow
    (0, 0, 128),     # 4  blue
    (128, 0, 128),   # 5  magenta
    (0, 128, 128),   # 6  cyan
    (192, 192, 192), # 7  white
    (128, 128, 128), # 8  bright black
    (255, 0, 0),     # 9  bright red
    (0, 255, 0),     # 10 bright green
    (255, 255, 0),   # 11 bright yellow
    (0, 0, 255),     # 12 bright blue
    (255, 0, 255),   # 13 bright magenta
    (0, 255, 255),   # 14 bright cyan
    (255, 255, 255), # 15 bright white
]

def _xterm_to_rgb(idx):
    """Convert an xterm-256 color index to (r, g, b) tuple."""
    if idx < 0:
        return (0, 0, 0)
    if idx < 16:
        return _ANSI_RGB[idx]
    if idx < 232:
        # 6x6x6 color cube
        idx -= 16
        b = _CUBE_VALUES[idx % 6]
        g = _CUBE_VALUES[(idx // 6) % 6]
        r = _CUBE_VALUES[(idx // 36) % 6]
        return (r, g, b)
    if idx < 256:
        # Grayscale ramp
        v = 8 + (idx - 232) * 10
        return (v, v, v)
    return (255, 255, 255)

def _rgb_to_nearest_xterm(r, g, b):
    """Find the nearest xterm-256 index for an (r, g, b) color.
    Searches the 6x6x6 cube and the grayscale ramp for best match."""

    def _nearest_cube_val(v):
        """Find nearest index in the 6-level cube axis."""
        best_i = 0
        best_d = abs(v - _CUBE_VALUES[0])
        for i in range(1, 6):
            d = abs(v - _CUBE_VALUES[i])
            if d < best_d:
                best_d = d
                best_i = i
        return best_i

    # Find best cube match
    ri = _nearest_cube_val(r)
    gi = _nearest_cube_val(g)
    bi = _nearest_cube_val(b)
    cube_idx = 16 + ri * 36 + gi * 6 + bi
    cr, cg, cb = _CUBE_VALUES[ri], _CUBE_VALUES[gi], _CUBE_VALUES[bi]
    cube_dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2

    # Find best grayscale match
    gray_avg = (r + g + b) // 3
    gray_step = max(0, min(23, (gray_avg - 8 + 5) // 10))
    gray_idx = 232 + gray_step
    gv = 8 + gray_step * 10
    gray_dist = (r - gv) ** 2 + (g - gv) ** 2 + (b - gv) ** 2

    return gray_idx if gray_dist < cube_dist else cube_idx

def _rgb_to_nearest_ansi8(r, g, b):
    """Find the nearest basic ANSI color index (0-7) for an (r, g, b) color.
    Used on terminals that only support 8 colors."""
    # ANSI 0-7 approximate RGB values
    _ANSI8 = [
        (0, 0, 0),       # 0  black
        (128, 0, 0),     # 1  red
        (0, 128, 0),     # 2  green
        (128, 128, 0),   # 3  yellow
        (0, 0, 128),     # 4  blue
        (128, 0, 128),   # 5  magenta
        (0, 128, 128),   # 6  cyan
        (192, 192, 192), # 7  white
    ]
    best_idx = 0
    best_dist = (r - _ANSI8[0][0]) ** 2 + (g - _ANSI8[0][1]) ** 2 + (b - _ANSI8[0][2]) ** 2
    for i in range(1, 8):
        ar, ag, ab = _ANSI8[i]
        d = (r - ar) ** 2 + (g - ag) ** 2 + (b - ab) ** 2
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx

def _build_rgb_gradient(color_a, color_b, steps):
    """Build a smooth gradient by interpolating in RGB space.
    color_a and color_b are (r, g, b) tuples with values 0-255.
    Returns a list of (r, g, b) tuples."""
    r1, g1, b1 = color_a
    r2, g2, b2 = color_b

    palette = []
    for i in range(steps):
        t = i / float(steps - 1) if steps > 1 else 0.0
        r = int(round(r1 + (r2 - r1) * t))
        g = int(round(g1 + (g2 - g1) * t))
        b = int(round(b1 + (b2 - b1) * t))
        palette.append((r, g, b))
    return palette

def _build_three_zone_gradient(obj_rgb, fog_rgb, bg_rgb, total_steps=10):
    """Build an N-step gradient across three depth zones:
      Zone 1: obj_color → fog_color  (near field to mid field)  ~1/3 of steps
      Zone 2: fog_color → bg_color   (mid field to far field)   ~1/3 of steps
      Zone 3: bg_color               (beyond fog, about to cull) remainder
    Returns a list of total_steps (r, g, b) tuples."""
    z1_count = total_steps // 3
    z2_count = total_steps // 3
    z3_count = total_steps - z1_count - z2_count
    if z1_count < 2: z1_count = 2
    if z2_count < 2: z2_count = 2
    if z3_count < 2: z3_count = 2
    zone1 = _build_rgb_gradient(obj_rgb, fog_rgb, z1_count)
    zone2 = _build_rgb_gradient(fog_rgb, bg_rgb, z2_count)
    zone3 = [bg_rgb] * z3_count
    return zone1 + zone2 + zone3

def init_colors(config, obj_rgb=None, bg_rgb=None, fog_rgb=None):
    """
    Safely initialize curses colors based on terminal capabilities.
    Color mode cascade:
      1. True color  – can_change_color(): init_color() with exact RGB
      2. xterm-256   – 256+ colors: nearest xterm-256 index
      3. 8-color     – basic ANSI palette approximation
      4. Mono        – no color
    Builds an N-step three-zone gradient from (r,g,b) tuples.
    Returns a list of N color pair indices and the bg pair ID.
    """
    GRADIENT_STEPS = config.gradient_steps

    if not config.use_color:
        return [0] * GRADIENT_STEPS, 0

    try:
        if not curses.has_colors():
            return [0] * GRADIENT_STEPS, 0

        curses.start_color()

        # Try to use default background transparency
        default_bg_idx = curses.COLOR_BLACK
        try:
            curses.use_default_colors()
            default_bg_idx = -1
        except Exception:
            pass

        # Apply defaults for missing colors
        if obj_rgb is None:
            obj_rgb = (0, 255, 0)  # default green
        if bg_rgb is None:
            bg_rgb = (0, 0, 0)    # default black
        if fog_rgb is None:
            fog_rgb = bg_rgb       # fade toward background

        # Determine available palette depth
        num_colors = 8
        try:
            num_colors = curses.COLORS
        except Exception:
            pass

        # Detect true-color support (can redefine color slots with exact RGB)
        can_redefine = False
        try:
            can_redefine = curses.can_change_color()
        except Exception:
            pass

        # Build the RGB gradient (list of (r,g,b) tuples)
        gradient_rgb = _build_three_zone_gradient(
            obj_rgb, fog_rgb, bg_rgb, GRADIENT_STEPS)

        # --- Resolve foreground color slots for each gradient step ---
        # We need GRADIENT_STEPS fg slots + 1 bg slot + 1 bg-pair fg slot.
        # Use color slots starting at 16 to avoid clobbering ANSI 0-15.
        fg_slots = []  # curses color index per gradient step
        bg_slot = -1   # curses color index for background

        if can_redefine and num_colors >= 256:
            # ── True color path: define exact RGB on color slots ──
            # Slot layout: 16 .. 16+GRADIENT_STEPS-1 for fg, 16+GRADIENT_STEPS for bg
            base_slot = 16
            for i, (r, g, b) in enumerate(gradient_rgb):
                slot = base_slot + i
                try:
                    curses.init_color(slot,
                                      r * 1000 // 255,
                                      g * 1000 // 255,
                                      b * 1000 // 255)
                    fg_slots.append(slot)
                except Exception:
                    # Fall back to nearest xterm-256 for this slot
                    fg_slots.append(_rgb_to_nearest_xterm(r, g, b))

            # Background slot
            bg_slot_num = base_slot + GRADIENT_STEPS
            if bg_rgb == (0, 0, 0) and default_bg_idx == -1:
                bg_slot = -1  # use terminal default
            else:
                try:
                    curses.init_color(bg_slot_num,
                                      bg_rgb[0] * 1000 // 255,
                                      bg_rgb[1] * 1000 // 255,
                                      bg_rgb[2] * 1000 // 255)
                    bg_slot = bg_slot_num
                except Exception:
                    bg_slot = _rgb_to_nearest_xterm(bg_rgb[0], bg_rgb[1], bg_rgb[2])
                    if bg_rgb == (0, 0, 0) and default_bg_idx == -1:
                        bg_slot = -1

        elif num_colors >= 256:
            # ── xterm-256 fallback: nearest index match ──
            for r, g, b in gradient_rgb:
                fg_slots.append(_rgb_to_nearest_xterm(r, g, b))
            bg_slot = _rgb_to_nearest_xterm(bg_rgb[0], bg_rgb[1], bg_rgb[2])
            if bg_rgb == (0, 0, 0) and default_bg_idx == -1:
                bg_slot = -1

        elif num_colors >= 8:
            # ── 8-color fallback: match to ANSI 0-7 palette ──
            obj_idx = _rgb_to_nearest_ansi8(obj_rgb[0], obj_rgb[1], obj_rgb[2])
            fog_idx = _rgb_to_nearest_ansi8(fog_rgb[0], fog_rgb[1], fog_rgb[2])
            bg_c_idx = _rgb_to_nearest_ansi8(bg_rgb[0], bg_rgb[1], bg_rgb[2])
            z1_n = GRADIENT_STEPS // 3
            z2_n = GRADIENT_STEPS // 3
            z3_n = GRADIENT_STEPS - z1_n - z2_n
            if z1_n < 2: z1_n = 2
            if z2_n < 2: z2_n = 2
            if z3_n < 2: z3_n = 2
            fg_slots = ([obj_idx] * z1_n + [fog_idx] * z2_n +
                        [bg_c_idx] * z3_n)
            bg_slot = _rgb_to_nearest_ansi8(bg_rgb[0], bg_rgb[1], bg_rgb[2])
            if bg_rgb == (0, 0, 0) and default_bg_idx == -1:
                bg_slot = -1
        else:
            return [0] * GRADIENT_STEPS, 0

        # --- Initialize color pairs ---
        valid_pairs = []
        for i in range(GRADIENT_STEPS):
            if i >= len(fg_slots):
                break
            pair_id = i + 1
            try:
                curses.init_pair(pair_id, fg_slots[i], bg_slot)
                valid_pairs.append(pair_id)
            except Exception:
                valid_pairs.append(0)

        while len(valid_pairs) < GRADIENT_STEPS:
            valid_pairs.append(valid_pairs[-1] if valid_pairs else 0)

        # Background pair for screen fill
        bg_pair = 0
        try:
            fg_for_bg = 7 if bg_slot != 7 else 0  # contrast text on bg
            curses.init_pair(GRADIENT_STEPS + 1, fg_for_bg, bg_slot)
            bg_pair = GRADIENT_STEPS + 1
        except Exception:
            pass

        return valid_pairs, bg_pair

    except Exception:
        return [0] * GRADIENT_STEPS, 0

def render_cell_ascii(mask: int, depth: int = 0) -> str:
    """
    Renders a 2x4 cell mask as an ASCII character based on pixel density.
    Used when Braille is unavailable.
    """
    if not mask:
        return ' '
        
    # Count set bits
    density = bin(mask).count('1')
    
    # Map density 1-8 to ASCII gradient
    # CHARS: " .:-=+*#%@"
    chars = " .:-=+*#%@"
    return chars[density] if density < len(chars) else '@'

class Mesh:
    def __init__(self, filename):
        self.vertices, self.faces = [], []
        if not filename:
            self._make_demo_cube()
            return
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('v '):
                        self.vertices.append([float(x) for x in line.split()[1:4]])
                    elif line.startswith('f '):
                        face = [int(x.split('/')[0]) - 1 for x in line.split()[1:]]
                        self.faces.append(face)
        except Exception as e:
            print(f"Warning: Could not load '{filename}': {e}", file=sys.stderr)
            self.vertices, self.faces = [], []
        if not self.vertices or not self.faces:
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

class Canvas:
    __slots__ = ['w', 'h', 'grid', 'z_buffer', 'c_grid', 'cell_z']
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.grid = [[0] * (w // 2 + 1) for _ in range(h // 4 + 1)]
        self.z_buffer = [[999999] * w for _ in range(h)]
        self.c_grid = [[0] * (w // 2 + 1) for _ in range(h // 4 + 1)]
        self.cell_z = [[999999] * (w // 2 + 1) for _ in range(h // 4 + 1)]

    def set_pixel(self, x, y, z_int, color_idx):
        if x < 0 or x >= self.w or y < 0 or y >= self.h: return
        
        if z_int < self.z_buffer[y][x]:
            self.z_buffer[y][x] = z_int
            cx, cy = x >> 1, y >> 2
            self.grid[cy][cx] |= (1 << ((y & 3) + (x & 1) * 4))
            
            if z_int < self.cell_z[cy][cx]:
                self.cell_z[cy][cx] = z_int
                self.c_grid[cy][cx] = color_idx

    # Rasterizes a triangle ONLY to the Z-buffer
    def fill_triangle_depth(self, p1, p2, p3):
        # Sort vertices by Y
        if p1[1] > p2[1]: p1, p2 = p2, p1
        if p1[1] > p3[1]: p1, p3 = p3, p1
        if p2[1] > p3[1]: p2, p3 = p3, p2

        x1, y1, z1 = int(p1[0]), int(p1[1]), int(p1[2] * 1000)
        x2, y2, z2 = int(p2[0]), int(p2[1]), int(p2[2] * 1000)
        x3, y3, z3 = int(p3[0]), int(p3[1]), int(p3[2] * 1000)

        # Polygon Offset
        z1 += 50; z2 += 50; z3 += 50

        def draw_scanlines(y_start, y_end, xa, za, xb, zb, x_step_a, z_step_a, x_step_b, z_step_b):
            for y in range(y_start, y_end):
                if y < 0 or y >= self.h:
                    xa += x_step_a; za += z_step_a
                    xb += x_step_b; zb += z_step_b
                    continue
                
                sx, ex = int(xa), int(xb)
                sz, ez = za, zb
                if sx > ex: sx, ex = ex, sx; sz, ez = ez, sz
                
                z_slope = (ez - sz) / (ex - sx) if ex > sx else 0
                curr_z = sz
                
                start_x = max(0, sx)
                end_x = min(self.w, ex)
                
                if start_x > sx:
                     curr_z += z_slope * (start_x - sx)

                row = self.z_buffer[y]
                for x in range(start_x, end_x):
                    if curr_z < row[x]:
                        row[x] = int(curr_z)
                    curr_z += z_slope
                
                xa += x_step_a; za += z_step_a
                xb += x_step_b; zb += z_step_b

        inv_dy1 = 1.0 / (y2 - y1) if y2 != y1 else 0
        inv_dy2 = 1.0 / (y3 - y2) if y3 != y2 else 0
        inv_dy_long = 1.0 / (y3 - y1) if y3 != y1 else 0

        x_step_long = (x3 - x1) * inv_dy_long
        z_step_long = (z3 - z1) * inv_dy_long
        
        if y2 > y1:
            x_step_1 = (x2 - x1) * inv_dy1
            z_step_1 = (z2 - z1) * inv_dy1
            xa, za = float(x1), float(z1)
            xb, zb = float(x1), float(z1)
            draw_scanlines(y1, y2, xa, za, xb, zb, x_step_long, z_step_long, x_step_1, z_step_1)

        if y3 > y2:
            y_diff = y2 - y1
            xa = x1 + x_step_long * y_diff
            za = z1 + z_step_long * y_diff
            xb, zb = float(x2), float(z2)
            x_step_2 = (x3 - x2) * inv_dy2
            z_step_2 = (z3 - z2) * inv_dy2
            draw_scanlines(y2, y3, xa, za, xb, zb, x_step_long, z_step_long, x_step_2, z_step_2)

def draw_line_dda(canvas, p1, p2, z_min, z_max,
                  fog_start=5.0, fog_end=120.0, far_plane=200.0,
                  use_fog=True, fog_exp=0.5, gradient_steps=10):
    x1, y1, z1 = int(p1[0]), int(p1[1]), int(p1[2] * 1000)
    x2, y2, z2 = int(p2[0]), int(p2[1]), int(p2[2] * 1000)
    
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0: return

    step = abs(dx) if abs(dx) > abs(dy) else abs(dy)
    
    x_inc = dx / step
    y_inc = dy / step
    z_inc = (z2 - z1) / step
    
    cx, cy, cz = float(x1), float(y1), float(z1)

    if use_fog:
        # Compute zone sizes from total gradient_steps (same split as _build_three_zone_gradient)
        z1_count = gradient_steps // 3
        z2_count = gradient_steps // 3
        z3_count = gradient_steps - z1_count - z2_count
        if z1_count < 2: z1_count = 2
        if z2_count < 2: z2_count = 2
        if z3_count < 2: z3_count = 2
        z1_max_idx = z1_count - 1   # last index in zone 1
        z2_base = z1_count           # first index in zone 2
        z2_max_idx = z2_count - 1    # offset within zone 2
        last_idx = gradient_steps - 1  # very last gradient index

        # Three-zone fog:
        #   Zone 1: fog_start → fog_end   => gradient indices 0 .. z1_max_idx
        #   Zone 2: fog_end  → far_plane  => gradient indices z2_base .. z2_base+z2_max_idx
        #   Zone 3: > far_plane           => gradient index last_idx (pure bg)
        #   < fog_start                   => gradient index 0 (pure obj)
        fog_start_i = fog_start * 1000
        fog_end_i = fog_end * 1000
        far_plane_i = far_plane * 1000
        zone1_range = fog_end_i - fog_start_i
        zone2_range = far_plane_i - fog_end_i
        if zone1_range <= 0: zone1_range = 1
        if zone2_range <= 0: zone2_range = 1

        for _ in range(int(step) + 1):
            if cz <= fog_start_i:
                c_idx = 0
            elif cz <= fog_end_i:
                rel = (cz - fog_start_i) / zone1_range
                rel = rel ** fog_exp
                c_idx = int(rel * z1_max_idx)
                if c_idx > z1_max_idx: c_idx = z1_max_idx
            elif cz <= far_plane_i:
                rel = (cz - fog_end_i) / zone2_range
                rel = rel ** fog_exp
                c_idx = z2_base + int(rel * z2_max_idx)
                if c_idx > z2_base + z2_max_idx: c_idx = z2_base + z2_max_idx
            else:
                c_idx = last_idx
            canvas.set_pixel(int(cx), int(cy), int(cz), c_idx)
            cx += x_inc; cy += y_inc; cz += z_inc
    else:
        # No fog: flat object color (index 0) for all pixels
        for _ in range(int(step) + 1):
            canvas.set_pixel(int(cx), int(cy), int(cz), 0)
            cx += x_inc; cy += y_inc; cz += z_inc

def parse_args():
    epilog = """\
examples:
  %(prog)s                                             Demo cube (no model needed)
  %(prog)s cobra.obj                                   Load OBJ model
  %(prog)s cobra.obj --obj-color #FF8800 --bg-color #1A1A2E   Orange on dark blue
  %(prog)s cobra.obj --fog-exp 0.3 --fog-end 200       Gentle fog, long range
  %(prog)s cobra.obj --gradient-steps 24               Smoother fog gradient
  %(prog)s cobra.obj --no-fog --ascii --mono            No fog, ASCII, monochrome
  %(prog)s --obj-color #00FFFF --fog-color #FF0044     Cyan cube fading to red
"""
    parser = argparse.ArgumentParser(
        description="CLI Wireframe Renderer",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("model", nargs='?', help="Path to .obj file")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    parser.add_argument("--mono", action="store_true", help="Force monochrome output")
    parser.add_argument("--ascii", action="store_true", help="Use ASCII characters instead of Braille")
    parser.add_argument("--no-zbuffer", action="store_true", help="Disable Z-buffering")
    parser.add_argument("--no-cull", action="store_true", help="Disable backface culling")
    parser.add_argument("--obj-color", default="#D0DD14",
                        help="Wireframe color in hex #RRGGBB (default: #D0DD14)")
    parser.add_argument("--bg-color", default="#0E0E2C",
                        help="Background color in hex #RRGGBB (default: #0E0E2C)")
    parser.add_argument("--fog-color", default="#8D0582",
                        help="Fog color edges fade toward in hex #RRGGBB (default: #8D0582)")
    parser.add_argument("--fog-start", type=float, default=3.0,
                        help="Camera-space Z where fog begins (default: 3.0)")
    parser.add_argument("--fog-end", type=float, default=50.0,
                        help="Camera-space Z where fog is fully opaque (default: 50.0)")
    parser.add_argument("--fog-exp", type=float, default=0.6,
                        help="Fog curve exponent: <1 = slow start, 1 = linear, >1 = fast start (default: 0.6)")
    parser.add_argument("--far-plane", type=float, default=150.0,
                        help="Far clipping plane distance; objects beyond are culled (default: 150.0)")
    parser.add_argument("--gradient-steps", type=int, default=15,
                        help="Number of fog gradient color steps, 6-30 (default: 15)")
    parser.add_argument("--no-fog", action="store_true", help="Disable depth fog")
    return parser.parse_args()

def main(stdscr, args):
    curses.curs_set(0)
    stdscr.nodelay(True)
    
    # Initialize Config
    config = RenderConfig.detect_terminal()
    if args.no_color: config.use_color = False
    if args.ascii: config.use_braille = False
    if args.no_zbuffer: config.use_zbuffer = False
    if args.no_cull: config.use_culling = False
    if args.mono: 
        config.use_color = False # Mono implies no color
    if args.no_fog:
        config.use_fog = False
    config.fog_start = args.fog_start
    config.fog_end = args.fog_end
    config.fog_exp = args.fog_exp
    config.far_plane = args.far_plane
    config.gradient_steps = max(6, min(30, args.gradient_steps))

    # Initialize Colors
    # Parse user-specified hex colors to (r, g, b) tuples
    obj_rgb = parse_hex_color(args.obj_color)
    bg_rgb = parse_hex_color(args.bg_color)
    fog_rgb = parse_hex_color(args.fog_color)
    # valid_pairs maps depth index (0-5) to curses color pair ID
    # bg_pair is the pair for full-screen background fill
    valid_pairs, bg_pair = init_colors(config, obj_rgb, bg_rgb, fog_rgb)
    
    mesh = Mesh(args.model if args.model else "")
    
    ax, ay = 0.0, 0.0
    cam_z, fov, flip = 6.0, 60.0, False
    instances = [(0.0, 0.0, 0.0)]
    BRAILLE_REMAP = [0x01, 0x02, 0x04, 0x40, 0x08, 0x10, 0x20, 0x80]
    
    frame_count = 0
    last_fps_time = time.time()
    fps = 0

    while True:
        start_time = time.time()
        try: key = stdscr.getch()
        except: key = -1
        
        if key != -1:
            if key == ord('q'): break
            elif key == curses.KEY_UP: ax += 0.1
            elif key == curses.KEY_DOWN: ax -= 0.1
            elif key == curses.KEY_RIGHT: ay += 0.1
            elif key == curses.KEY_LEFT: ay -= 0.1
            elif key in (ord('='), ord('+')): cam_z = max(0.5, cam_z - 0.5)
            elif key == ord('-'): cam_z += 0.5
            elif key == ord('['): fov = max(10, fov - 5)
            elif key == ord(']'): fov = min(170, fov + 5)
            elif key == ord('f'): flip = not flip
            elif key == ord(' '):
                instances.append((random.uniform(-25, 25), random.uniform(-25, 25), random.uniform(-25, 25)))
            # Runtime Toggles
            elif key == ord('c'): config.use_color = not config.use_color
            elif key == ord('b'): config.use_braille = not config.use_braille
            elif key == ord('z'): config.use_zbuffer = not config.use_zbuffer
            elif key == ord('g'): config.use_fog = not config.use_fog

        th, tw = stdscr.getmaxyx()
        W, H = (tw-1)*2, (th-2)*4
        canv = Canvas(W, H)
        aspect = W / H
        
        f_tan = 1.0 / math.tan(math.radians(fov) / 2.0)
        cx, sx = math.cos(ax), math.sin(ax)
        cy, sy = math.cos(ay), math.sin(ay)
        
        m0, m1, m2 = cy, sx*sy, cx*sy
        m3, m4, m5 = 0, cx, -sx
        m6, m7, m8 = -sy, sx*cy, cx*cy

        half_w, half_h = W * 0.5, H * 0.5
        render_queue = []
        
        # --- PASS 1: Sort Objects ---
        far_clip = config.far_plane
        near_clip = config.near_clip
        for ox, oy, oz in instances:
            cen_z = ox*m6 + oy*m7 + oz*m8 + cam_z
            if cen_z < near_clip or cen_z > far_clip: continue
            
            # Note: We only need Center Z for sorting.
            # Perspective projection happens per-vertex in Pass 2.
            render_queue.append((cen_z, ox, oy, oz))

        # Sort Front-to-Back
        render_queue.sort(key=lambda x: x[0])
        
        # --- PASS 2: Transform & Render ---
        for entry in render_queue:
            cen_z_sort, ox, oy, oz = entry
            
            proj_v = [None] * len(mesh.vertices)
            
            # Local stats for this object to determine color range
            obj_z_min = 99999.0
            obj_z_max = -99999.0
            
            for i, v in enumerate(mesh.vertices):
                vx, vy, vz = v[0] + ox, v[1] + oy, v[2] + oz
                
                # Camera Space Z
                rz = vx*m6 + vy*m7 + vz*m8 + cam_z
                
                if rz > near_clip:
                    # Camera Space X, Y
                    rx = vx*m0 + vy*m1 + vz*m2
                    ry = vx*m3 + vy*m4 + vz*m5
                    
                    # True Perspective Projection
                    # x_screen = (rx * f_tan / aspect) / rz * half_w + half_w
                    px = (rx * f_tan / aspect / rz) * half_w + half_w
                    py = (1.0 - (ry * f_tan / rz)) * half_h
                    
                    proj_v[i] = (px, py, rz)
                    
                    if rz < obj_z_min: obj_z_min = rz
                    if rz > obj_z_max: obj_z_max = rz

            # Render Faces
            # Use object-level min/max for gradient consistency
            z_min, z_max = obj_z_min, obj_z_max
            if z_min >= z_max: z_max = z_min + 1.0

            for f in mesh.faces:
                pts = []
                valid = True
                for idx in f:
                    if proj_v[idx] is None: valid = False; break
                    pts.append(proj_v[idx])
                
                if not valid or len(pts) < 3: continue

                # --- Frustum side culling ---
                # Skip face if ALL vertices are beyond the same screen edge
                all_left = True
                all_right = True
                all_top = True
                all_bottom = True
                for pt in pts:
                    px_t, py_t = pt[0], pt[1]
                    if px_t >= 0: all_left = False
                    if px_t <= W: all_right = False
                    if py_t >= 0: all_top = False
                    if py_t <= H: all_bottom = False
                if all_left or all_right or all_top or all_bottom:
                    continue
                
                p0, p1, p2 = pts[0], pts[1], pts[2]
                cross = (p1[0]-p0[0])*(p2[1]-p0[1]) - (p1[1]-p0[1])*(p2[0]-p0[0])
                
                should_render = True
                if config.use_culling:
                    if not ((cross < 0) ^ flip): should_render = False

                if should_render:
                    # 1. Z-Prepass (Solid Fill)
                    if config.use_zbuffer:
                        canv.fill_triangle_depth(pts[0], pts[1], pts[2])
                        if len(pts) > 3:
                             canv.fill_triangle_depth(pts[0], pts[2], pts[3])

                    # 2. Wireframe Draw
                    for i in range(len(pts)):
                        draw_line_dda(canv, pts[i], pts[(i+1)%len(pts)], z_min, z_max,
                                      config.fog_start, config.fog_end, config.far_plane,
                                      config.use_fog, config.fog_exp,
                                      config.gradient_steps)

        stdscr.erase()
        # Apply background color to entire screen
        if config.use_color and bg_pair:
            try:
                stdscr.bkgd(' ', curses.color_pair(bg_pair))
            except Exception:
                pass
        frame_count += 1
        if time.time() - last_fps_time >= 1.0:
            fps = frame_count; frame_count = 0; last_fps_time = time.time()

        ms = (time.time() - start_time) * 1000
        fogstr = f"FOG:{config.fog_exp}" if config.use_fog else "---"
        modestr = f"{'COL' if config.use_color else 'MON'} {'BRA' if config.use_braille else 'ASC'} {'Z+' if config.use_zbuffer else 'Z-'} {fogstr}"
        hdr = f" OBJ:{len(instances)} | V:{len(mesh.vertices)} F:{len(mesh.faces)} | FPS:{fps} | {ms:.1f}ms | [{modestr}] "
        try: stdscr.addstr(0, 0, hdr.center(tw-1, '='), curses.color_pair(0) | curses.A_BOLD)
        except: pass

        for y in range(min(th - 2, len(canv.grid))):
            for x in range(min(tw - 1, len(canv.grid[0]))):
                mask = canv.grid[y][x]
                if mask:
                    try:
                        char = ' '
                        if config.use_braille:
                            b = sum(BRAILLE_REMAP[i] for i in range(8) if mask & (1 << i))
                            char = chr(0x2800 + b)
                        else:
                            char = render_cell_ascii(mask)
                            
                        # Use color if enabled and pair is valid
                        attr = curses.color_pair(0)
                        if config.use_color:
                            c_idx = canv.c_grid[y][x]
                            # valid_pairs length check just in case
                            if c_idx < len(valid_pairs):
                                attr = curses.color_pair(valid_pairs[c_idx])
                        
                        stdscr.addstr(y + 1, x, char, attr)
                    except: pass
        stdscr.refresh()

if __name__ == "__main__":
    args = parse_args()
    curses.wrapper(lambda s: main(s, args))

