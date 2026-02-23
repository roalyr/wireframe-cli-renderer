#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/demo.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 3.3
# LOG_REF: 2026-02-19
#

import curses
import time
import random

from .config import RenderConfig
from .renderer import Renderer
from .scene import Scene
from .camera import Camera
from .mesh import Mesh
from .color import parse_hex_color


class DemoApp:
    """
    Interactive demo harness that replicates the original monolithic script's
    main() loop exactly: input handling, orbital camera, rendering, HUD overlay.
    """

    def __init__(self, stdscr, args):
        self.stdscr = stdscr
        self.running = True

        # ── Curses setup ────────────────────────────────────────────────
        curses.curs_set(0)
        stdscr.nodelay(True)

        # ── RenderConfig from terminal detection + CLI overrides ────────
        config = RenderConfig.detect_terminal()
        if args.no_color:
            config.use_color = False
        if args.ascii:
            config.use_braille = False
        if args.no_zbuffer:
            config.use_zbuffer = False
        if args.no_cull:
            config.use_culling = False
        if args.mono:
            config.use_color = False  # Mono implies no color
        if args.no_fog:
            config.use_fog = False
        config.fog_start = args.fog_start
        config.fog_end = args.fog_end
        config.fog_exp = args.fog_exp
        config.far_plane = args.far_plane
        config.gradient_steps = max(6, min(30, args.gradient_steps))
        # Re-initialise fog model after parameter changes
        config.init_fog()
        self.config = config

        # ── Parse user-specified hex colors ─────────────────────────────
        obj_rgb = parse_hex_color(args.obj_color)
        bg_rgb = parse_hex_color(args.bg_color)
        fog_rgb = parse_hex_color(args.fog_color)

        # ── Renderer + curses color init ────────────────────────────────
        renderer = Renderer()
        renderer.init_colors(config, obj_rgb, bg_rgb, fog_rgb)
        self.renderer = renderer

        # ── Mesh ────────────────────────────────────────────────────────
        mesh = Mesh(args.model if args.model else "")
        self.mesh = mesh

        # ── Scene with one initial instance at origin ───────────────────
        scene = Scene()
        scene.add(mesh, (0.0, 0.0, 0.0))
        self.scene = scene

        # ── Camera (matches original defaults) ──────────────────────────
        camera = Camera(fov=60.0, distance=6.0,
                        near=config.near_clip, far=config.far_plane)
        self.camera = camera

        # ── Frame counter ───────────────────────────────────────────────
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()

    # ────────────────────────────────────────────────────────────────────
    # Input — matches original key bindings exactly
    # ────────────────────────────────────────────────────────────────────
    def handle_input(self):
        try:
            key = self.stdscr.getch()
        except Exception:
            key = -1

        if key == -1:
            return

        camera = self.camera
        config = self.config

        if key == ord('q'):
            self.running = False
        elif key == curses.KEY_UP:
            camera.pitch += 0.1
        elif key == curses.KEY_DOWN:
            camera.pitch -= 0.1
        elif key == curses.KEY_RIGHT:
            camera.yaw += 0.1
        elif key == curses.KEY_LEFT:
            camera.yaw -= 0.1
        elif key in (ord('='), ord('+')):
            camera.zoom(-0.5)
        elif key == ord('-'):
            camera.zoom(0.5)
        elif key == ord('['):
            camera.adjust_fov(-5)
        elif key == ord(']'):
            camera.adjust_fov(5)
        elif key == ord('f'):
            camera.flip = not camera.flip
        elif key == ord(' '):
            self.scene.add(self.mesh,
                           (random.uniform(-25, 25),
                            random.uniform(-25, 25),
                            random.uniform(-25, 25)))
        # Runtime toggles
        elif key == ord('c'):
            config.use_color = not config.use_color
        elif key == ord('b'):
            config.use_braille = not config.use_braille
        elif key == ord('z'):
            config.use_zbuffer = not config.use_zbuffer
        elif key == ord('g'):
            config.use_fog = not config.use_fog

    # ────────────────────────────────────────────────────────────────────
    # Main loop
    # ────────────────────────────────────────────────────────────────────
    def run(self):
        while self.running:
            start_time = time.time()

            self.handle_input()

            # Render frame (fills canvas → outputs to stdscr, does NOT refresh)
            self.renderer.render(self.stdscr, self.scene, self.camera, self.config)

            # ── HUD overlay (line 0) ────────────────────────────────────
            th, tw = self.stdscr.getmaxyx()

            self.frame_count += 1
            now = time.time()
            if now - self.last_fps_time >= 1.0:
                self.fps = self.frame_count
                self.frame_count = 0
                self.last_fps_time = now

            ms = (now - start_time) * 1000
            fogstr = (f"FOG:{self.config.fog_exp}"
                      if self.config.use_fog else "---")
            modestr = (f"{'COL' if self.config.use_color else 'MON'} "
                       f"{'BRA' if self.config.use_braille else 'ASC'} "
                       f"{'Z+' if self.config.use_zbuffer else 'Z-'} "
                       f"{fogstr}")
            hdr = (f" OBJ:{len(self.scene.objects)}"
                   f" | V:{len(self.mesh.vertices)}"
                   f" F:{len(self.mesh.faces)}"
                   f" | FPS:{self.fps}"
                   f" | {ms:.1f}ms"
                   f" | [{modestr}] ")
            try:
                self.stdscr.addstr(
                    0, 0,
                    hdr.center(tw - 1, '='),
                    curses.color_pair(0) | curses.A_BOLD)
            except Exception:
                pass

            self.stdscr.refresh()


def main(stdscr, args):
    """Entry point called from curses.wrapper."""
    app = DemoApp(stdscr, args)
    app.run()
