#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/canvas.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 5.1
# LOG_REF: 2026-02-19
#

class Canvas:
    __slots__ = ['w', 'h', 'grid', 'z_buffer', 'c_grid', 'cell_z']
    
    # Braille dot mapping for 2x4 grid
    #  1 4
    #  2 5
    #  3 6
    #  7 8
    # 0x01, 0x02, 0x04, 0x40, 0x08, 0x10, 0x20, 0x80
    BRAILLE_REMAP = [0x01, 0x02, 0x04, 0x40, 0x08, 0x10, 0x20, 0x80]

    def __init__(self, w, h):
        self.w, self.h = w, h
        # Grid stores 8-bit masks for 2x4 cells
        self.grid = [[0] * (w // 2 + 1) for _ in range(h // 4 + 1)]
        # Z-buffer stores depth per-pixel (resolution w x h)
        self.z_buffer = [[999999] * w for _ in range(h)]
        # Color grid stores color index per-cell (resolution w/2 x h/4)
        self.c_grid = [[0] * (w // 2 + 1) for _ in range(h // 4 + 1)]
        # Cell-Z stores min depth per-cell for deciding color priority
        self.cell_z = [[999999] * (w // 2 + 1) for _ in range(h // 4 + 1)]

    def set_pixel(self, x, y, z_int, color_idx):
        if x < 0 or x >= self.w or y < 0 or y >= self.h: return
        
        if z_int < self.z_buffer[y][x]:
            self.z_buffer[y][x] = z_int
            cx, cy = x >> 1, y >> 2
            # Set the specific bit for this pixel in the 2x4 block
            # (y & 3) gives row 0-3 in block
            # (x & 1) gives col 0-1 in block
            # Bit index 0-7: 0,1,2,3 for left col; 4,5,6,7 for right col
            self.grid[cy][cx] |= (1 << ((y & 3) + (x & 1) * 4))
            
            # Update cell color if this pixel is closer than previous cell winner
            if z_int < self.cell_z[cy][cx]:
                self.cell_z[cy][cx] = z_int
                self.c_grid[cy][cx] = color_idx

def render_cell_ascii(mask: int) -> str:
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

def render_cell_braille(mask: int) -> str:
    """Renders a 2x4 cell mask as a Unicode Braille character."""
    if not mask:
        return ' ' 
    b = sum(Canvas.BRAILLE_REMAP[i] for i in range(8) if mask & (1 << i))
    return chr(0x2800 + b)
