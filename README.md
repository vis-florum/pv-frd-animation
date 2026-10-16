# pv-frd-animation

ParaView displacement animations. One VTU mode or a PVD mode sweep. MP4 and GIF. Run with `uv`.

## Setup

Requires **uv**, **ParaView with pvpython**, and **FFmpeg with H.264 support**. Python 3.10+. No Python runtime dependencies. Tested with ParaView 6.1 on Linux.

```sh
uv sync --locked
uv run animate.py init
```

Edit `examples/beam/config.local.json` or `examples/modes/config.local.json`. Put inputs in that example’s `data/` and ParaView states in its `states/`. Paths are relative to the config file.

```text
examples/beam/       single-mode preset, local inputs and output
examples/modes/      PVD sweep preset, local inputs and output
examples/cinematic/  camera-motion preset; shares beam inputs
pv_frd_animation/   rendering and orchestration
tests/       regression tests
```

Only `config.example.json` and documentation inside `examples/` are tracked. Local settings, inputs, states, frames, logs, and results stay outside Git. See [example layout](examples/README.md). Keep a PVD beside the VTU files it references. Displacement vectors must be named `disp`; export FRD results to VTU/PVD first.

## Run

**One mode.** Warp a VTU through positive and negative displacement. Fixed view, orbit, or fly-through.

```sh
uv run animate.py beam doctor
uv run animate.py beam --workers 4
uv run animate.py beam --config examples/cinematic/config.local.json --workers 4
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

Beam output: `examples/beam/output/beam_animation.{mp4,gif,pvsm}`. Sweep output: `examples/modes/output/allmodes.{mp4,gif,pvsm}`. Both include `preview.png`, frames, settings, and logs. Select another `--output` to keep variants.

## Reference

```sh
uv run animate.py beam --help
uv run animate.py modes --help
uv run python -m unittest discover -s tests -v
```

[Options and defaults](docs/reference.md) · [Architecture and validation](docs/development.md)
