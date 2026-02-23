# TRUTH_SPEC — Wireframe CLI Renderer — Technical Specification

> **Status:** READ-ONLY TRUTH | **Version:** 1.0 | **Date:** 2026-02-19

---

## 1. Project Identity

| Field           | Value                                      |
| :-------------- | :----------------------------------------- |
| **Name**        | wireframe-cli-renderer                     |
| **Type**        | Standalone 3D wireframe rendering library + demo |
| **Stack**       | Python 3.10+, curses (ncurses)             |
| **License**     | See LICENSE.md                             |
| **Deliverable** | Importable Python package + runnable demo  |

---

## 2. Architecture Overview

The project is structured as a **library with a demo harness**. The engine is
importable (`import wireframe_cli_renderer`) and the demo is a thin script that
constructs a scene and runs the render loop.

### 2.1 Module Map

```
wireframe_cli_renderer/         # Package root
├── __init__.py                 # Public API re-exports
├── math_utils.py               # Vec3, Mat4, transforms, projection
├── mesh.py                     # Mesh class, OBJ loader, procedural generators
├── canvas.py                   # Braille/ASCII canvas, Z-buffer
├── rasterizer.py               # Line drawing (DDA), triangle depth fill
├── color.py                    # Color parsing, gradient builder, curses palette init
├── camera.py                   # Camera state, orbit controller, automated flyby
├── scene.py                    # Scene graph: list of (Mesh, Transform) entries
├── renderer.py                 # Main render loop: transform → cull → project → draw
├── config.py                   # RenderConfig dataclass, terminal capability detection
└── fog.py                      # Fog model (three-zone exponential)

demo.py                         # Entry point: builds scene, runs automated camera demo
```

### 2.2 Dependency Rules

- **No external dependencies.** Only Python stdlib + curses.
- **No global mutable state.** All state lives in explicit objects passed through function arguments.
- Modules depend **downward** only (renderer → scene → mesh → math_utils).
  No circular imports.

---

## 3. Public API Surface

The library exposes a minimal, composable API. All public symbols are
re-exported from `wireframe_cli_renderer/__init__.py`.

### 3.1 Core Types

```python
class Vec3:
    """Immutable 3-component vector. Supports +, -, *, dot, cross, normalize, length."""

class Mat4:
    """4×4 matrix for transforms. Class methods: identity, rotation_x/y/z, translation, perspective."""

class Mesh:
    """Vertex + face data. Constructors: from_obj(path), cube(), grid(), sphere(), axes()."""

class Camera:
    """Position, target, FOV, near/far. Methods: view_matrix(), orbit(yaw, pitch, radius)."""

class Scene:
    """Collection of (Mesh, Mat4) pairs representing the world."""

class RenderConfig:
    """Rendering options: color, braille, zbuffer, culling, fog params."""

class Renderer:
    """Stateless renderer. render(stdscr, scene, camera, config) → draws one frame."""
```

### 3.2 Minimal Usage (Library Mode)

```python
from wireframe_cli_renderer import Mesh, Camera, Scene, Renderer, RenderConfig
import curses

def run(stdscr):
    scene = Scene()
    scene.add(Mesh.cube(), translation=(0, 0, 0))
    camera = Camera(fov=60, position=(0, 0, -6))
    config = RenderConfig.detect_terminal()
    renderer = Renderer()

    while True:
        renderer.render(stdscr, scene, camera, config)

curses.wrapper(run)
```

### 3.3 Demo Mode (Standalone)

```bash
python demo.py                          # Random scene, automated camera orbit
python demo.py --model ship.obj         # Load OBJ, automated camera
python demo.py --interactive            # Manual camera controls (arrow keys, +/-, q)
```

---

## 4. Rendering Pipeline

Each frame follows this fixed-function pipeline:

```
1. Scene Traversal
   └─ For each (mesh, transform) in scene:
       ├─ Compute model_matrix = transform
       └─ Compute center_z for depth sort

2. Depth Sort
   └─ Sort objects front-to-back by center_z

3. Per-Object Processing (for each sorted object):
   ├─ 3a. Vertex Transform
   │       vertex_world = model_matrix × vertex_local
   │       vertex_cam   = view_matrix  × vertex_world
   │
   ├─ 3b. Frustum Cull (near/far + screen-space sides)
   │
   ├─ 3c. Perspective Projection
   │       vertex_screen = perspective_matrix × vertex_cam
   │
   ├─ 3d. Backface Cull (screen-space cross product, optional)
   │
   ├─ 3e. Z-Prepass (solid triangle rasterization to Z-buffer only)
   │
   └─ 3f. Wireframe Draw (DDA lines with per-pixel Z-test + fog color)

4. Canvas → Terminal
   ├─ Braille path: 2×4 pixel blocks → Unicode Braille (U+2800–U+28FF)
   └─ ASCII path: density-mapped characters (" .:-=+*#%@")

5. Curses Output
   └─ stdscr.addstr() with color_pair attributes, then refresh
```

---

## 5. Rendering Features

### 5.1 Display Modes

| Mode     | Resolution    | Character Set                | Requirement      |
| :------- | :------------ | :--------------------------- | :--------------- |
| Braille  | 2×4 per cell  | U+2800–U+28FF               | UTF-8 terminal   |
| ASCII    | 1×1 per cell  | ` .:-=+*#%@` (density map) | Any terminal     |

### 5.2 Color Cascade

Terminal color support is detected at init and falls through:

1. **True color** — `can_change_color()` → define exact RGB via `init_color()`
2. **xterm-256** — `COLORS >= 256` → nearest xterm-256 index
3. **8-color** — `COLORS >= 8` → nearest ANSI 0–7
4. **Monochrome** — no color pairs, attributes only

### 5.3 Fog Model

Three-zone exponential fog blending object color → fog color → background color:

| Zone | Depth Range              | Gradient Segment      |
| :--- | :----------------------- | :-------------------- |
| 1    | `fog_start` → `fog_end` | Object → Fog color    |
| 2    | `fog_end` → `far_plane` | Fog → Background      |
| 3    | `> far_plane`           | Pure background (cull) |

Controlled by exponent `fog_exp`: <1 = slow onset, 1 = linear, >1 = aggressive.

### 5.4 Z-Buffering

- Per-pixel integer Z-buffer (`z * 1000` fixed-point).
- Solid triangle depth prepass with polygon offset (+50) to ensure wireframe
  edges always render on top of filled faces.
- Configurable: can be disabled for faster rendering of simple scenes.

### 5.5 Backface Culling

- Screen-space winding-order test via cross product.
- Toggleable at runtime.

---

## 6. Mesh Format Support

### 6.1 OBJ Loader

- Supports `v` (vertex) and `f` (face) records.
- Face indices are 1-based, converted to 0-based internally.
- Handles `v/vt/vn` slash notation (only position index used).
- Quads and n-gons supported (fan triangulation for Z-prepass).

### 6.2 Procedural Generators

Built-in mesh generators for demo and testing:

| Generator       | Description                              |
| :-------------- | :--------------------------------------- |
| `Mesh.cube()`   | Unit cube centered at origin             |
| `Mesh.grid()`   | Flat grid on XZ plane                    |
| `Mesh.sphere()` | UV sphere with configurable segments     |
| `Mesh.axes()`   | XYZ axis indicator lines                 |

---

## 7. Camera System

### 7.1 Orbit Camera

- Controlled by `yaw`, `pitch`, `radius` around a focus point.
- Smooth interpolation for automated flyby.

### 7.2 Automated Demo Camera

- Sinusoidal orbit path with slowly varying radius and pitch.
- Random scene spawn: N random meshes placed in a volume.
- Cycle duration configurable (default ~30s full orbit).

### 7.3 Interactive Controls

| Key         | Action                          |
| :---------- | :------------------------------ |
| Arrow keys  | Rotate camera (yaw/pitch)       |
| `+` / `-`   | Zoom in / out                   |
| `[` / `]`   | Decrease / increase FOV         |
| `f`         | Flip face winding               |
| `Space`     | Spawn random object instance    |
| `c`         | Toggle color                    |
| `b`         | Toggle braille / ASCII          |
| `z`         | Toggle Z-buffer                 |
| `g`         | Toggle fog                      |
| `q`         | Quit                            |

---

## 8. Configuration

### 8.1 RenderConfig Fields

| Field            | Type   | Default | Description                          |
| :--------------- | :----- | :------ | :----------------------------------- |
| `use_color`      | bool   | True    | Enable color output                  |
| `use_braille`    | bool   | True    | Use Braille characters (vs ASCII)    |
| `use_zbuffer`    | bool   | True    | Enable Z-buffer depth testing        |
| `use_culling`    | bool   | True    | Enable backface culling              |
| `use_fog`        | bool   | True    | Enable depth fog                     |
| `fog_start`      | float  | 3.0     | Fog start distance                   |
| `fog_end`        | float  | 80.0    | Fog full opacity distance            |
| `fog_exp`        | float  | 0.6     | Fog curve exponent                   |
| `near_clip`      | float  | 0.1     | Near clipping plane                  |
| `far_plane`      | float  | 150.0   | Far clipping / cull distance         |
| `gradient_steps` | int    | 12      | Number of fog color gradient steps   |

### 8.2 CLI Arguments (Demo Mode)

See Section 3.3. All `RenderConfig` fields are exposed as `--flag` arguments.
Color arguments accept `#RRGGBB` hex strings.

---

## 9. Performance Constraints

| Constraint                    | Target                                     |
| :---------------------------- | :----------------------------------------- |
| Frame budget                  | ≤ 50ms per frame (20+ FPS) for ~1k faces   |
| Memory                        | O(W×H) for canvas + Z-buffer               |
| No external deps              | stdlib + curses only                        |
| No threads                    | Single-threaded render loop                 |
| Terminal size                  | Adapt dynamically to `getmaxyx()`          |

---

## 10. Testing Strategy

| Layer        | Method                                         |
| :----------- | :--------------------------------------------- |
| Math utils   | Unit tests: Vec3/Mat4 operations, projection   |
| Mesh loading | Unit tests: OBJ parse, procedural generators   |
| Canvas       | Unit tests: pixel set, braille encoding        |
| Rasterizer   | Unit tests: DDA line, triangle fill bounds     |
| Integration  | Visual regression: render known scene, compare  |
| Demo         | Manual: launch, verify no crash, controls work |

---

## 11. Future Integration (Space Game)

When the engine is finalized, it will be consumed as a library:

```python
# In the space game project:
from wireframe_cli_renderer import Mesh, Camera, Scene, Renderer, RenderConfig

# Load ship models, build scene, drive camera from game logic
scene.add(Mesh.from_obj("assets/fighter.obj"), transform=ship_matrix)
renderer.render(stdscr, scene, camera, config)
```

The engine must therefore:
- Have **zero game-specific logic**.
- Accept meshes, transforms, and camera from the caller.
- Be installable via `pip install -e .` (editable) or direct import.
- Expose a **stable public API** (Section 3) that the game depends on.
