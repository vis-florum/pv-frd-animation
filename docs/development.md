# Development

```sh
uv sync --locked
uv run python -m unittest discover -s tests -v
```

The application uses the Python standard library. FFmpeg regression tests run when FFmpeg is present. ParaView is external: renderers run under its bundled Python/VTK, independently of the uv environment. CI tests Python 3.10 and 3.12 with FFmpeg; it does not run ParaView rendering.

| Module | Responsibility |
|---|---|
| `cli` | Workflow selection and local config initialization |
| `pipeline` | Stages, diagnostics, errors |
| `config`, `modes_config` | Defaults, validation, portable paths |
| `timing`, `modes_timing` | Sampling and mode sequencing |
| `camera`, `geometry` | Camera paths and interior mesh target |
| `renderer`, `modes_renderer` | ParaView scenes and captures |
| `frames` | Deduplication, worker assignments, ordered sequence |
| `executables`, `worker` | Native tool discovery and process supervision |
| `encoding` | Bounded frame input, MP4/GIF export |

Public examples belong in `examples/<name>/config.example.json`. Working presets belong in ignored `examples/<name>/config.local.json`. Scientific inputs, `.pvsm` files, rendered frames, and output are local. A fresh clone requires its own inputs.

For rendering changes, check a short beam render and a two-mode sweep. Verify both exports with `ffprobe`/`ffmpeg`, reopen the generated state, and inspect the first/last zero poses, displacement peaks, annotation values, and camera. A mode sweep should leave camera and annotation settings identical to its input state.
