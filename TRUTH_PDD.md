# TRUTH_PDD — Wireframe CLI Renderer — Product Design Document

> **Status:** READ-ONLY TRUTH | **Version:** 1.0 | **Date:** 2026-02-19

---

## 1. Vision Statement

A **pure-terminal 3D wireframe rendering engine** that turns any CLI into a
real-time 3D viewport. Ships as a standalone demo (launch it, see a random
space-themed scene with automated camera) and as a reusable Python library with
a clean API for embedding in larger projects — specifically, a future
terminal-based space game.

**Aesthetic:** Retro-futuristic wireframe — glowing colored edges fading into
fog against a dark background. Think *Elite* (1984) meets modern terminal
Unicode capabilities.

---

## 2. Goals & Non-Goals

### 2.1 Goals

| #  | Goal                                                                 |
| :- | :------------------------------------------------------------------- |
| G1 | Real-time 3D wireframe rendering in a standard terminal              |
| G2 | Clean, documented public API suitable for library consumption        |
| G3 | Zero external dependencies (Python stdlib + curses only)             |
| G4 | Graceful degradation across terminal capabilities (color, charset)   |
| G5 | Standalone demo mode with automated camera and random scene          |
| G6 | OBJ model loading for arbitrary geometry                             |
| G7 | Depth-aware rendering (Z-buffer, fog, backface culling)              |
| G8 | Braille-character sub-cell resolution for high visual fidelity       |

### 2.2 Non-Goals

| #   | Non-Goal                                                            |
| :-- | :------------------------------------------------------------------ |
| NG1 | Filled/shaded polygon rendering (wireframe only)                    |
| NG2 | Textures or material systems                                        |
| NG3 | Support for non-curses output (no raw ANSI escape sequences)        |

---

## 3. User Experience

### 3.1 Demo Mode (Primary Showcase)

When launched without arguments, the demo:

1. **Generates a random scene:** Several wireframe objects (cubes, spheres,
   grids, and optionally loaded OBJ models) scattered in 3D space.
2. **Automated camera orbit:** Camera smoothly orbits the scene center with
   gentle pitch oscillation and slow radius breathing, showing off depth fog
   and Z-buffering from multiple angles.
3. **HUD overlay:** A single status line at the top showing FPS, object count,
   vertex/face count, and active render mode flags.
4. **Interactive fallback:** User can press arrow keys to take manual control
   at any time. Press `q` to quit.

### 3.2 Library Mode (For the Space Game)

The game project imports the renderer as a package:

- Constructs `Mesh` objects from OBJ files or procedural generators.
- Builds a `Scene` by adding meshes with transformation matrices.
- Drives the `Camera` from game logic (ship position, tracking, cinematic).
- Calls `Renderer.render()` each frame inside a curses loop.
- The engine **never** reads input or manages game state — that's the caller's
  responsibility.

### 3.3 Interaction Map (Demo Mode)

```
┌────────────────────────────────────────────────┐
│              TERMINAL VIEWPORT                 │
│                                                │
│   ═══ OBJ:5 │ V:128 F:96 │ FPS:30 ═══        │
│                                                │
│          ╱‾‾‾╲     Wireframe objects           │
│         ╱     ╲    with depth fog              │
│        ╱───────╲   fading to background        │
│                                                │
│  [Arrow Keys] Rotate   [+/-] Zoom             │
│  [q] Quit   [Space] Spawn   [c/b/z/g] Toggle  │
└────────────────────────────────────────────────┘
```

---

## 4. Demo Scene Composition

The automated demo showcases engine features through a curated random scene:

### 4.1 Object Pool

| Object     | Count | Placement                        | Purpose                     |
| :--------- | :---- | :------------------------------- | :-------------------------- |
| Cubes      | 3–5   | Random pos in ±20 volume         | Basic geometry, Z-test      |
| Spheres    | 1–2   | Random pos, varying radius       | Curved wireframe density    |
| Grid plane | 1     | Y = -3, centered                 | Ground reference            |
| Axes       | 1     | Origin                           | Orientation reference       |
| OBJ model  | 0–1   | If `--model` supplied, centered  | Real-world geometry demo    |

### 4.2 Camera Path

- **Orbit center:** World origin (0, 0, 0)
- **Radius:** Oscillates between 8 and 25 (sinusoidal, period ~40s)
- **Yaw:** Continuous rotation, ~0.02 rad/frame
- **Pitch:** Oscillates between -0.3 and +0.5 rad (period ~20s)
- Camera path ensures all objects pass through near-field, fog zone, and
  far-field to demonstrate the full depth gradient.

---

## 5. Visual Design

### 5.1 Default Color Scheme

| Element     | Hex       | Description                   |
| :---------- | :-------- | :---------------------------- |
| Wireframe   | `#D0DD14` | Bright yellow-green           |
| Fog         | `#8D0582` | Deep magenta                  |
| Background  | `#0E0E2C` | Near-black navy               |

### 5.2 Depth Fog Zones

```
Distance:  0 ──── fog_start ──── fog_end ──── far_plane ────→
Color:     [Object]───────[Fog blend]───────[BG blend]──[Cull]
Curve:          exponential (fog_exp)
```

Objects near the camera render in full object color. As distance increases,
edges blend through the fog color toward the background, creating depth
perception without filled surfaces.

### 5.3 Resolution Strategy

Braille characters encode a 2×4 pixel grid per terminal cell, giving an
effective resolution of `(cols×2) × (rows×4)` pixels. This is critical for
wireframe rendering where individual edge pixels matter.

Fallback ASCII mode uses density-mapped characters, sacrificing resolution but
ensuring compatibility with any terminal.

---

## 6. Space Game Integration Vision

The space game will use this engine to render:

- **Starships** — OBJ wireframe models with per-ship color.
- **Space stations** — Large structures demonstrating far-field fog.
- **Asteroids** — Procedural low-poly meshes.
- **Star field** — Sparse dots at far distances (fog fades them elegantly).
- **HUD elements** — The game overlays its own UI on top of the rendered frame.

The engine's job ends at **"here are the pixels for this frame."** Everything
above (game loop, input, state, UI) is the game's responsibility.

---

## 7. Quality Bar

| Criterion              | Minimum Acceptable                             |
| :--------------------- | :--------------------------------------------- |
| Startup                | < 1s to first frame on standard terminal       |
| Frame rate             | ≥ 40 FPS with 2000 faces (80×24 terminal)      |
| Crash resistance       | No crash on terminal resize, missing model, 0 faces |
| Terminal compat        | Works on: xterm-256color, gnome-terminal, tmux, Linux console |
| API clarity            | Any feature usable in ≤ 5 lines of caller code |
| Code quality           | No globals, typed dataclasses, docstrings on all public methods |

---

## 8. Milestones

| #  | Milestone                        | Description                                          |
| :- | :------------------------------- | :--------------------------------------------------- |
| M1 | **Modularize**                   | Refactor monolith into package structure (Sec 2.1 of TRUTH_SPEC) |
| M2 | **Stable API**                   | Implement public API surface (Sec 3 of TRUTH_SPEC)  |
| M3 | **Procedural Meshes**            | Add sphere, grid, axes generators                    |
| M4 | **Camera System**                | Orbit camera + automated flyby                       |
| M5 | **Scene Graph**                  | Scene class with multi-mesh transforms               |
| M6 | **Demo Harness**                 | demo.py with random scene + automated camera         |
| M7 | **Polish & Test**                | Docstrings, type hints, unit tests, edge cases       |
| M8 | **Package Release**              | setup.py/pyproject.toml, pip-installable             |
