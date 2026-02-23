#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/fog.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 5.3
# LOG_REF: 2026-02-19
#

class FogModel:
    """
    Manages the depth fog model:
    - Calculates zone splits (how many colors per zone)
    - Maps coordinate Z-depth to palette indices
    """
    __slots__ = ('gradient_steps', 'fog_start', 'fog_end', 'far_plane', 'fog_exp',
                 'z1_count', 'z2_count', 'z3_count',
                 'z1_max_idx', 'z2_base', 'z2_max_idx', 'last_idx',
                 'fog_start_i', 'fog_end_i', 'far_plane_i',
                 'zone1_range', 'zone2_range')

    def __init__(self, gradient_steps: int, fog_start: float, fog_end: float, 
                 far_plane: float, fog_exp: float):
        self.gradient_steps = gradient_steps
        self.fog_start = fog_start
        self.fog_end = fog_end
        self.far_plane = far_plane
        self.fog_exp = fog_exp
        
        # Precompute zone splits
        self._compute_zones()
        
        # Precompute integer thresholds for rasterization
        self.fog_start_i = self.fog_start * 1000
        self.fog_end_i = self.fog_end * 1000
        self.far_plane_i = self.far_plane * 1000
        self.zone1_range = self.fog_end_i - self.fog_start_i
        self.zone2_range = self.far_plane_i - self.fog_end_i
        
        if self.zone1_range <= 0: self.zone1_range = 1
        if self.zone2_range <= 0: self.zone2_range = 1

    def _compute_zones(self):
        """
        Determines how many gradient steps are allocated to each fog zone.
        Zone 1: Object -> Fog
        Zone 2: Fog -> Background
        Zone 3: Background (deep far field)
        """
        total = self.gradient_steps
        self.z1_count = total // 3
        self.z2_count = total // 3
        self.z3_count = total - self.z1_count - self.z2_count
        
        # Ensure minimums
        if self.z1_count < 2: self.z1_count = 2
        if self.z2_count < 2: self.z2_count = 2
        # z3_min is less critical but good for stability
        if self.z3_count < 2: self.z3_count = 2
        
        # Precompute Index Mapping Constants
        self.z1_max_idx = self.z1_count - 1 # Last index of Zone 1
        self.z2_base = self.z1_count        # First index of Zone 2
        self.z2_max_idx = self.z2_count - 1 # Offset range of Zone 2
        self.last_idx = self.gradient_steps - 1

    def get_zone_counts(self):
        """Returns tuple (z1_count, z2_count, z3_count) for gradient generation."""
        return (self.z1_count, self.z2_count, self.z3_count)

    def get_color_index(self, z_depth_int: float) -> int:
        """
        Calculates the color index for a given Z depth (in 1000x integer units).
        """
        if z_depth_int <= self.fog_start_i:
            return 0  # Pure Object Color
        
        elif z_depth_int <= self.fog_end_i:
            # Zone 1: Object -> Fog
            rel = (z_depth_int - self.fog_start_i) / self.zone1_range
            try:
                rel = rel ** self.fog_exp
            except:
                rel = 0
            idx = int(rel * self.z1_max_idx)
            if idx > self.z1_max_idx: return self.z1_max_idx
            return idx
            
        elif z_depth_int <= self.far_plane_i:
            # Zone 2: Fog -> Background
            rel = (z_depth_int - self.fog_end_i) / self.zone2_range
            try:
                rel = rel ** self.fog_exp
            except:
                rel = 0
            idx = self.z2_base + int(rel * self.z2_max_idx)
            if idx > self.z2_base + self.z2_max_idx: return self.z2_base + self.z2_max_idx
            return idx
            
        else:
            # Zone 3: Deep Far Plane (Background color)
            return self.last_idx
