# Turntable

One complete camera rotation around world Y, then one around world Z. Keep the state's volume, profiles, colors, opacity, annotations, and data time.

```sh
uv run animate.py init
# Edit examples/turntable/config.local.json.
uv run animate.py turntable doctor
uv run animate.py turntable preview
uv run animate.py turntable --workers 2
```

| Setting | Default |
|---|---|
| `state` | `./states/showcase.pvsm` |
| `output` | `./output` |
| `seconds_per_orbit` | `8` |
| `zoom` | `0.9` |
| `framing` | `fit`: center visible bounds and fit both rotations |
| `volume_renderer` | `state`: keep saved mapper; `cpu` avoids GPU texture-size limits |
| `fps` | `24` |
| `width`, `height` | `1920`, `1080` |
| `crf`, `preset` | `14`, `slow` |
| `gif_width`, `gif_fps`, `gif_colors` | `960`, `24`, `256` |

Paths in JSON are relative to that JSON. The state references its own input datasets; keep those files accessible. Only the portable example preset and documentation are tracked. Local settings, inputs, and results are ignored.

`framing: state` retains the saved focal point and camera framing. `framing: fit` preserves the starting direction, centers the visible object, and keeps it in frame throughout both orbits. Zoom below 1 adds space. The saved aspect ratio is preserved with letterboxing.

Outputs: `turntable.mp4`, `turntable.gif`, `preview.png`, frames, metadata, and a snapshot `turntable.pvsm`. Rendering again reads your latest state. Use `encode` to change compression/GIF settings without rendering again.

[All flags](../../docs/reference.md#saved-scene-turntable)
