# pv-frd-animation

ParaView displacement animations. One VTU mode or a PVD mode sweep. MP4 and GIF. Run with `uv`.

## Setup

Requires **uv**, **ParaView with pvpython**, and **FFmpeg with H.264 support**. Python 3.10+. No Python runtime dependencies. Tested with ParaView 6.1 on Linux.

```sh
uv sync --locked
uv run animate.py init
```

Put your inputs in `data/` and save your ParaView states in `states/`. Edit the paths in `configs/beam.local.json` or `configs/modes.local.json`. Paths are relative to the config file.

```text
configs/     example presets + ignored local settings
states/      your .pvsm files
data/        your VTU files and PVD collections
output/      generated frames, movies, states, logs
pv_frd_animation/   rendering and orchestration
tests/       regression tests
```

Local inputs, state files, settings, and output stay outside Git. Keep a PVD beside the VTU files it references. Displacement vectors must be named `disp`; export FRD results to VTU/PVD first.

## Run

**One mode.** Warp a VTU through positive and negative displacement. Fixed view, orbit, or fly-through.

```sh
uv run animate.py beam doctor
uv run animate.py beam --workers 4
uv run animate.py beam --config configs/cinematic.local.json --workers 4
```

**Mode sweep.** Hold each PVD time, complete one closed cycle, then advance. Preserve the state camera, annotations, colors, and visibility.

```sh
uv run animate.py modes doctor
uv run animate.py modes --seconds-per-cycle 2 --workers 4
```

Sweep defaults: times **2–16**, warp **±0.1**, **2 seconds per mode**. MP4 **1920×1080**, GIF **960×540**. Letterboxing preserves the saved view's aspect ratio.

## Return to a project

1. Save your changes in ParaView to the `.pvsm` named in the local config.
2. Change input paths or timing in that config.
3. Run `doctor`, then `preview`.
4. Render the animation.

```sh
uv run animate.py modes preview
uv run animate.py modes --workers 4
```

`beam` and `modes` automatically use their `.local.json` when present; otherwise they use `.example.json`. CLI flags override config values. `init` never overwrites existing local settings.

State changes require rendering again. Encoding alone reuses existing PNGs:

```sh
uv run animate.py modes render --workers 4
uv run animate.py modes encode
```

Beam output: `output/beam/beam_animation.{mp4,gif,pvsm}`. Sweep output: `output/modes/allmodes.{mp4,gif,pvsm}`. Both include `preview.png`, frames, settings, and logs. Select another `--output` to keep variants.

## Reference

```sh
uv run animate.py beam --help
uv run animate.py modes --help
uv run python -m unittest discover -s tests -v
```

[Options and defaults](docs/reference.md) · [Architecture and validation](docs/development.md)
