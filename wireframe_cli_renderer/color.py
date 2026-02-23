#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/color.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 5.2
# LOG_REF: 2026-02-19
#

import curses

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

def _build_three_zone_gradient(obj_rgb, fog_rgb, bg_rgb, z1_count, z2_count, z3_count):
    """Build an N-step gradient across three depth zones using precomputed counts."""
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
    
    # Get zone distribution from the fog model
    if config.fog_model:
        z1_n, z2_n, z3_n = config.fog_model.get_zone_counts()
    else:
        # Fallback if uninitialized (should not happen in normal flow)
        z1_n, z2_n = GRADIENT_STEPS // 3, GRADIENT_STEPS // 3
        z3_n = GRADIENT_STEPS - z1_n - z2_n
        if z1_n < 2: z1_n = 2
        if z2_n < 2: z2_n = 2
        
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
            obj_rgb, fog_rgb, bg_rgb, z1_n, z2_n, z3_n)

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
            # Only append fg_slots up to GRADIENT_STEPS if using fallback
            # (Though logic here is correct: one slot per gradient step)
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
            
            # Use precomputed zone counts
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
