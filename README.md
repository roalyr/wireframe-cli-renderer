# Wireframe CLI Renderer

A modular Python library for rendering 3D wireframe graphics directly in the terminal using ASCII/Braille characters and ANSI colors.

## Features

- **3D Rendering**: Perspective projection, backface culling, and Cohen-Sutherland clipping (future).
- **Output Modes**:
  - Braille (High resolution dots)
  - ASCII (Fallback characters)
  - Color (Gradient Fog/Lighting via ncurses)
  - Monochrome (Fallback)
- **Fog**: Distance-based exponential fog.
- **Z-Buffering**: Per-pixel depth testing for correct occlusions.
- **Performance**: Optimized algorithms (DDA, fixed-point math).

## Installation

This is a standalone Python package. No external dependencies required (uses standard library `curses`).

```bash
# Clone the repository
git clone https://github.com/roalyr/wireframe-cli-renderer.git
cd wireframe-cli-renderer
```

## Usage

Run the included demo client:

```bash
python3 client_demo.py [model.obj]
```

### Controls

- **Arrows**: Orbit Camera (Pitch/Yaw)
- **+/-**: Zoom In/Out
- **[ / ]**: Adjust FOV
- **Space**: Add random object instance
- **C**: Toggle Color
- **B**: Toggle Braille/ASCII
- **Z**: Toggle Z-Buffer
- **G**: Toggle Fog
- **Q**: Quit

## Developer Guide

The project is structured as a Python package `wireframe_cli_renderer`.

```python
from wireframe_cli_renderer import Renderer, Scene, Camera, Mesh, RenderConfig, Vec3, RenderObject

# Setup
cfg = RenderConfig.detect_terminal()
renderer = Renderer(width=80, height=24, config=cfg)
scene = Scene()
camera = Camera()

# Load Mesh
mesh = Mesh("model.obj")
scene.add_object(RenderObject(mesh, Vec3(0, 0, -5)))

# Render Loop
renderer.render(scene, camera)
# (See demo.py for curses integration)
```

## License

GPL License (See LICENSE.md)
