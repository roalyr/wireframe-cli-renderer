#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/renderer.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 4
# LOG_REF: 2026-02-19
#

import math
import curses

from .config import RenderConfig
from .canvas import Canvas, render_cell_ascii, render_cell_braille
from .camera import Camera
from .scene import Scene
from .rasterizer import draw_line_dda, fill_triangle_depth


class Renderer:
    """
    Stateless wireframe renderer.

    render(stdscr, scene, camera, config) draws one frame to the curses screen.

    Internally uses the same inline rotation matrix and perspective projection
    math as the original monolithic script to guarantee identical output.
    """

    def __init__(self):
        self.valid_pairs = None
        self.bg_pair = 0

    def init_colors(self, config, obj_rgb=None, bg_rgb=None, fog_rgb=None):
        """Initialize curses color pairs.  Call once after curses.wrapper init."""
        from .color import init_colors
        self.valid_pairs, self.bg_pair = init_colors(config, obj_rgb, bg_rgb, fog_rgb)

    def render(self, stdscr, scene: Scene, camera: Camera, config: RenderConfig):
        """
        Render one frame and output to curses screen.

        Pipeline (matches TRUTH_SPEC Section 4):
          1. Build canvas from terminal size
          2. Compute rotation matrix from camera angles
          3. Sort objects front-to-back by center Z
          4. Per object: vertex transform → frustum cull → backface cull →
             Z-prepass → wireframe draw
          5. Output canvas cells to curses (erase + background + draw)

        Does NOT call stdscr.refresh() — the caller should do that after
        optional HUD / overlay drawing.
        """
        if self.valid_pairs is None:
            self.valid_pairs = [0] * config.gradient_steps

        th, tw = stdscr.getmaxyx()
        W = (tw - 1) * 2
        H = (th - 2) * 4
        if W <= 0 or H <= 0:
            return

        canv = Canvas(W, H)
        aspect = W / H

        # ── Camera rotation matrix (identical to original) ──────────────
        f_tan = 1.0 / math.tan(math.radians(camera.fov) / 2.0)
        cx_r = math.cos(camera.pitch)
        sx_r = math.sin(camera.pitch)
        cy_r = math.cos(camera.yaw)
        sy_r = math.sin(camera.yaw)

        m0, m1, m2 = cy_r, sx_r * sy_r, cx_r * sy_r
        m3, m4, m5 = 0,    cx_r,        -sx_r
        m6, m7, m8 = -sy_r, sx_r * cy_r, cx_r * cy_r

        half_w = W * 0.5
        half_h = H * 0.5
        near_clip = config.near_clip
        far_clip = config.far_plane
        cam_z = camera.distance

        # ── PASS 1: Sort objects by center Z ────────────────────────────
        render_queue = []
        for mesh, (ox, oy, oz) in scene.objects:
            cen_z = ox * m6 + oy * m7 + oz * m8 + cam_z
            if cen_z < near_clip or cen_z > far_clip:
                continue
            render_queue.append((cen_z, mesh, ox, oy, oz))

        render_queue.sort(key=lambda x: x[0])

        # Fog model — None when disabled so rasterizer skips fog math
        fog_model = config.fog_model if config.use_fog else None

        # ── PASS 2: Transform & Render ──────────────────────────────────
        for entry in render_queue:
            _cen_z, mesh, ox, oy, oz = entry

            proj_v = [None] * len(mesh.vertices)
            obj_z_min = 99999.0
            obj_z_max = -99999.0

            for i, v in enumerate(mesh.vertices):
                vx = v[0] + ox
                vy = v[1] + oy
                vz = v[2] + oz

                # Camera-space Z
                rz = vx * m6 + vy * m7 + vz * m8 + cam_z

                if rz > near_clip:
                    # Camera-space X, Y
                    rx = vx * m0 + vy * m1 + vz * m2
                    ry = vx * m3 + vy * m4 + vz * m5

                    # Perspective projection
                    px = (rx * f_tan / aspect / rz) * half_w + half_w
                    py = (1.0 - (ry * f_tan / rz)) * half_h

                    proj_v[i] = (px, py, rz)

                    if rz < obj_z_min:
                        obj_z_min = rz
                    if rz > obj_z_max:
                        obj_z_max = rz

            # Per-object Z range
            z_min = obj_z_min
            z_max = obj_z_max
            if z_min >= z_max:
                z_max = z_min + 1.0

            # Render faces
            for f in mesh.faces:
                pts = []
                valid = True
                for idx in f:
                    if proj_v[idx] is None:
                        valid = False
                        break
                    pts.append(proj_v[idx])

                if not valid or len(pts) < 3:
                    continue

                # ── Frustum side culling ────────────────────────────────
                all_left = True
                all_right = True
                all_top = True
                all_bottom = True
                for pt in pts:
                    px_t, py_t = pt[0], pt[1]
                    if px_t >= 0:
                        all_left = False
                    if px_t <= W:
                        all_right = False
                    if py_t >= 0:
                        all_top = False
                    if py_t <= H:
                        all_bottom = False
                if all_left or all_right or all_top or all_bottom:
                    continue

                # ── Backface culling (screen-space cross product) ───────
                p0, p1_f, p2_f = pts[0], pts[1], pts[2]
                cross = ((p1_f[0] - p0[0]) * (p2_f[1] - p0[1]) -
                         (p1_f[1] - p0[1]) * (p2_f[0] - p0[0]))

                should_render = True
                if config.use_culling:
                    if not ((cross < 0) ^ camera.flip):
                        should_render = False

                if should_render:
                    # 1. Z-Prepass (solid triangle depth fill)
                    if config.use_zbuffer:
                        fill_triangle_depth(canv, pts[0], pts[1], pts[2])
                        if len(pts) > 3:
                            fill_triangle_depth(canv, pts[0], pts[2], pts[3])

                    # 2. Wireframe draw (DDA with per-pixel Z-test + fog)
                    for i in range(len(pts)):
                        draw_line_dda(canv,
                                      pts[i], pts[(i + 1) % len(pts)],
                                      fog_model=fog_model)

        # ── Output to curses ────────────────────────────────────────────
        stdscr.erase()

        # Apply background color to entire screen
        if config.use_color and self.bg_pair:
            try:
                stdscr.bkgd(' ', curses.color_pair(self.bg_pair))
            except Exception:
                pass

        # Draw canvas cells
        valid_pairs = self.valid_pairs
        grid = canv.grid
        c_grid = canv.c_grid
        use_color = config.use_color
        use_braille = config.use_braille

        for y in range(min(th - 2, len(grid))):
            row_grid = grid[y]
            row_color = c_grid[y]
            for x in range(min(tw - 1, len(row_grid))):
                mask = row_grid[x]
                if mask:
                    try:
                        if use_braille:
                            char = render_cell_braille(mask)
                        else:
                            char = render_cell_ascii(mask)

                        attr = curses.color_pair(0)
                        if use_color and valid_pairs:
                            c_idx = row_color[x]
                            if c_idx < len(valid_pairs):
                                attr = curses.color_pair(valid_pairs[c_idx])

                        stdscr.addstr(y + 1, x, char, attr)
                    except Exception:
                        pass
