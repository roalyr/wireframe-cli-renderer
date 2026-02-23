#!/usr/bin/env python3
#
# PROJECT: wireframe-cli-renderer
# MODULE: client_demo.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 3.3
# LOG_REF: 2026-02-19
#

import curses
import argparse
import sys
import os

# Ensure local package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wireframe_cli_renderer.demo import DemoApp


def parse_args():
    """CLI argument parser — matches the original script's flags exactly."""
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
    parser.add_argument("--no-color", action="store_true",
                        help="Disable color output")
    parser.add_argument("--mono", action="store_true",
                        help="Force monochrome output")
    parser.add_argument("--ascii", action="store_true",
                        help="Use ASCII characters instead of Braille")
    parser.add_argument("--no-zbuffer", action="store_true",
                        help="Disable Z-buffering")
    parser.add_argument("--no-cull", action="store_true",
                        help="Disable backface culling")
    parser.add_argument("--obj-color", default="#D0DD14",
                        help="Wireframe color in hex #RRGGBB (default: #D0DD14)")
    parser.add_argument("--bg-color", default="#0E0E2C",
                        help="Background color in hex #RRGGBB (default: #0E0E2C)")
    parser.add_argument("--fog-color", default="#8D0582",
                        help="Fog color in hex #RRGGBB (default: #8D0582)")
    parser.add_argument("--fog-start", type=float, default=3.0,
                        help="Camera-space Z where fog begins (default: 3.0)")
    parser.add_argument("--fog-end", type=float, default=50.0,
                        help="Camera-space Z where fog is fully opaque (default: 50.0)")
    parser.add_argument("--fog-exp", type=float, default=0.6,
                        help="Fog curve exponent (default: 0.6)")
    parser.add_argument("--far-plane", type=float, default=150.0,
                        help="Far clipping plane distance (default: 150.0)")
    parser.add_argument("--gradient-steps", type=int, default=15,
                        help="Number of fog gradient color steps, 6-30 (default: 15)")
    parser.add_argument("--no-fog", action="store_true",
                        help="Disable depth fog")
    return parser.parse_args()


def main(stdscr, args):
    app = DemoApp(stdscr, args)
    app.run()


if __name__ == "__main__":
    args = parse_args()
    try:
        curses.wrapper(lambda s: main(s, args))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        curses.endwin()
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
