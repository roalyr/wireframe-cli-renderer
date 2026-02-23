#
# PROJECT: wireframe-cli-renderer
# MODULE: wireframe_cli_renderer/config.py
# STATUS: Level 2 - Implementation
# TRUTH_LINK: TRUTH_SPEC.md Section 8.1
# LOG_REF: 2026-02-19
#

import os
from dataclasses import dataclass, field
from typing import Optional
from .fog import FogModel

@dataclass
class RenderConfig:
    """Configuration for the rendering pipeline."""
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
    
    # Instance of the FogModel computed from these settings
    fog_model: Optional[FogModel] = field(init=False, repr=False, default=None)

    def __post_init__(self):
        self.init_fog()

    def init_fog(self):
        """Update the internal fog model based on current settings."""
        self.fog_model = FogModel(
            gradient_steps=self.gradient_steps,
            fog_start=self.fog_start,
            fog_end=self.fog_end,
            far_plane=self.far_plane,
            fog_exp=self.fog_exp
        )

    @classmethod
    def detect_terminal(cls) -> 'RenderConfig':
        """
        Autodetect terminal capabilities and return a default config.
        Checks TERM and LANG environment variables.
        """
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
            # Linux console font often lacks braille, so default off there
            use_braille=supports_utf8 and not is_linux_console,
            use_zbuffer=True,
            use_culling=True
        )
