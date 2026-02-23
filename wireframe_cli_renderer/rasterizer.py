#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/rasterizer.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 5.4
# LOG_REF: 2026-02-19
#

from .canvas import Canvas

def fill_triangle_depth(canvas: Canvas, p1, p2, p3):
    """
    Rasterizes a triangle ONLY to the Z-buffer (for occlusion).
    p1, p2, p3 are (x, y, z) tuples in screen space (z is camera Z).
    """
    # Sort vertices by Y
    if p1[1] > p2[1]: p1, p2 = p2, p1
    if p1[1] > p3[1]: p1, p3 = p3, p1
    if p2[1] > p3[1]: p2, p3 = p3, p2

    # Convert to integer coordinates for rasterization
    # Z is scaled by 1000 for integer buffering
    x1, y1, z1 = int(p1[0]), int(p1[1]), int(p1[2] * 1000)
    x2, y2, z2 = int(p2[0]), int(p2[1]), int(p2[2] * 1000)
    x3, y3, z3 = int(p3[0]), int(p3[1]), int(p3[2] * 1000)

    # Polygon Offset to prevent Z-fighting with wireframe
    # Wireframe lines sit "on top" of the solid depth mask
    z1 += 50; z2 += 50; z3 += 50

    w, h = canvas.w, canvas.h
    z_buf = canvas.z_buffer

    def draw_scanlines(y_start, y_end, xa, za, xb, zb, x_step_a, z_step_a, x_step_b, z_step_b):
        for y in range(y_start, y_end):
            if y < 0 or y >= h:
                xa += x_step_a; za += z_step_a
                xb += x_step_b; zb += z_step_b
                continue
            
            sx, ex = int(xa), int(xb)
            sz, ez = za, zb
            if sx > ex: sx, ex = ex, sx; sz, ez = ez, sz
            
            denom = (ex - sx)
            z_slope = (ez - sz) / denom if denom != 0 else 0
            curr_z = sz
            
            start_x = max(0, sx)
            end_x = min(w, ex)
            
            # Sub-pixel correction for start Z
            if start_x > sx:
                 curr_z += z_slope * (start_x - sx)

            row = z_buf[y]
            # Unrolled loop or slice assignment might be faster, but per-pixel test needed
            # Python loop is the bottleneck here.
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
    
    # Top half
    if y2 > y1:
        x_step_1 = (x2 - x1) * inv_dy1
        z_step_1 = (z2 - z1) * inv_dy1
        xa, za = float(x1), float(z1)
        xb, zb = float(x1), float(z1)
        draw_scanlines(y1, y2, xa, za, xb, zb, x_step_long, z_step_long, x_step_1, z_step_1)

    # Bottom half
    if y3 > y2:
        y_diff = y2 - y1
        xa = x1 + x_step_long * y_diff
        za = z1 + z_step_long * y_diff
        xb, zb = float(x2), float(z2)
        x_step_2 = (x3 - x2) * inv_dy2
        z_step_2 = (z3 - z2) * inv_dy2
        draw_scanlines(y2, y3, xa, za, xb, zb, x_step_long, z_step_long, x_step_2, z_step_2)


def draw_line_dda(canvas: Canvas, p1, p2, fog_model=None):
    """
    Draws a line using DDA algorithm with per-pixel Z-buffering and fog.
    Requires a pre-configured FogModel instance for color calculations.
    """
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

    if fog_model:
        # Use the provided FogModel for consistent color/depth calculations
        for _ in range(int(step) + 1):
            c_idx = fog_model.get_color_index(cz)
            canvas.set_pixel(int(cx), int(cy), int(cz), c_idx)
            cx += x_inc; cy += y_inc; cz += z_inc
    else:
        # No fog model: always use index 0 (object color) for valid pixels
        for _ in range(int(step) + 1):
            canvas.set_pixel(int(cx), int(cy), int(cz), 0)
            cx += x_inc; cy += y_inc; cz += z_inc
