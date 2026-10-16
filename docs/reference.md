# Reference

```sh
uv run animate.py {beam,modes} [stage] [flags]
```

Stages: `run` (default, render + encode), `preview`, `render`, `encode`, `doctor`.

Configs: `examples/beam/config.local.json` and `examples/modes/config.local.json`, falling back to the corresponding `.example.json`. Other configs require `--config FILE`. `uv run animate.py init` creates local configs without replacing existing files.

CLI flags override the selected config. Config paths resolve relative to the config file; CLI paths resolve relative to the working directory. JSON keys use underscores: `seconds_per_cycle`, `orbit2_degrees`, `gif_width`.

## Common

| Flag | Meaning | Default |
|---|---|---|
| `--config FILE` | Select a JSON preset | Local config, then example |
| `--state FILE` | ParaView state | `examples/{beam,modes}/states/{beam,modes}.pvsm` |
| `--output DIR` | Output directory | `examples/{beam,modes}/output` |
| `--amplitude X` | Positive/negative warp scale | Beam: `0.7`; sweep: `0.1` |
| `--fps N` | Frames per second | `24` |
| `--width N`, `--height N` | PNG/MP4 dimensions; even values | `1920`, `1080` |
| `--crf N` | MP4 quality; lower is higher quality, range 0–51 | `14` |
| `--preset NAME` | x264 compression speed | `slow` |
| `--gif-width N` | GIF width | Beam: `1920`; sweep: `960` |
| `--gif-fps N` | GIF sampling rate, capped at movie fps | `24` |
| `--gif-colors N` | GIF palette, range 4–256 | `256` |
| `--workers N` | Concurrent ParaView processes | `1` |
| `--threads-per-worker N` | CPU thread limits; 0 is automatic | `0` |
| `--pvpython PATH` | ParaView Python executable | Discovery |
| `--ffmpeg PATH` | FFmpeg executable | `ffmpeg` / `FFMPEG` |
| `-h`, `--help` | Command reference | — |

Encoding presets: `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`.

Tool discovery supports PATH, `PVPYTHON`, `PARAVIEW_HOME`, and `FFMPEG`, plus common ParaView installation directories. Supply explicit paths when discovery is ambiguous. Native graphics support depends on the ParaView build.

## Beam

| Flag | Meaning | Default |
|---|---|---|
| `--data FILE` | Single VTU input | `examples/beam/data/beam.vtu` |
| `--cycles N` | Full oscillations | `3` |
| `--speed X` | Oscillations per second | `0.5` |
| `--azimuth DEG` | Rotate around the initial camera up direction | `0` |
| `--elevation DEG` | Tilt from the state view | `0` |
| `--roll DEG` | Rotate the image plane | `0` |
| `--zoom X` | Zoom relative to a fitted view | `1` |
| `--state-camera` | Keep state framing; use zoom 1 | Off |
| `--no-state-camera` | Restore automatic fitting | — |
| `--orbit-degrees DEG` | Total primary rotation across the movie | `0` |
| `--orbit-axis X Y Z` | World-space primary axis | `0 1 0` |
| `--orbit2-degrees DEG` | Simultaneous second rotation | `0` |
| `--orbit2-axis X Y Z` | World-space second axis | `0 0 1` |
| `--fly-through` | One interior crossing, then resume on the far side | Off |
| `--no-fly-through` | Disable a configured crossing | — |
| `--fly-through-at SEC` | Crossing time; snapped to an output frame | Movie midpoint |
| `--fly-through-duration SEC` | Flight window | `min(2, movie duration / 3)` |
| `--preview-only` | Legacy alias for `preview` | — |
| `--encode-only` | Legacy alias for `encode` | — |

Cycle: `0 → +amplitude → 0 → −amplitude → 0`. Motion duration: `cycles / speed`. Frame count: `round(duration × fps) + 1`, including a closing zero pose. At least four samples per cycle are required. The former `steps` setting is replaced by `speed`; equivalent speed is `old_fps / (4 × old_steps)`.

The beam workflow builds its surface/outline display and magnitude legend. The input state supplies the initial camera direction; use `--state-camera --zoom 1` to retain its framing. For full scene and annotation preservation, use the PVD sweep workflow.

Different orbit axes produce a spiral-like path at fixed radius. Rotations apply in sequence around the two world axes. During fly-through, radius changes as the camera crosses an interior mesh point following the displacement. It resumes at the original radius on the far side. The flight window must lie inside the movie and span at least four frame intervals. Fly-through uses perspective projection.

```sh
uv run animate.py beam --config examples/cinematic/config.local.json --workers 4
uv run animate.py beam --orbit-degrees 360 --orbit2-degrees 75 --fly-through
```

GIF repeats continuously. Partial orbits, nonclosed secondary rotations, and fly-through can produce a cut at the loop boundary.

## Mode sweep

| Flag | Meaning | Default |
|---|---|---|
| `--pvd FILE` | Override the PVD referenced by the state | Config or state reader |
| `--start-time X` | First PVD pseudo-time, inclusive | `2` |
| `--end-time X` | Last PVD pseudo-time, inclusive | `16` |
| `--seconds-per-cycle SEC` | One closed warp cycle per mode | `2` |

Each selected time stays fixed through `0 → +amplitude → 0 → −amplitude → 0`. Both exact peaks and both zero endpoints are sampled. The next time starts only after the previous cycle closes. All actual PVD times between the selected endpoints are included; both endpoints must exist.

Frames per mode: `round(seconds_per_cycle × fps)`, minimum five. Mode duration is rounded to the nearest frame. At defaults, 15 modes × 48 frames = 720 frames / 30 seconds. PVD pseudo-time and frequency labels do not set playback speed.

The state defines camera position, focal point, up direction, projection, colors, visibility, legend, and annotation settings. The camera stays static. Frequency text updates from each mode through the annotation already in the state. The renderer preserves the saved aspect ratio, scales the complete composition, and letterboxes it into the requested output size.

```sh
uv run animate.py modes --seconds-per-cycle 4 --start-time 2 --end-time 16
uv run animate.py modes --pvd /path/to/series.pvd --state /path/to/view.pvsm
```

A same-named PVD beside the state is preferred when inferring paths. Paths within the PVD remain relative to that PVD. Keep its referenced VTU files together.

## Execution

Start with 2–4 workers. Each worker loads the mesh and owns a graphics context. Workers share the GPU. Unique fixed-camera poses are rendered once across all workers; cached poses never cross a PVD mode boundary.

The controller waits for every worker, assembles the ordered sequence, then encodes. A worker failure or Ctrl-C stops the pool. Logs are in `<configured output>/worker_logs/`. Preview uses one renderer.

Automatic CPU thread limits leave serial ParaView defaults unchanged. Parallel workers share available cores, capped at eight threads per worker. A positive `--threads-per-worker` sets VTK, OpenMP, BLAS, and Mesa limits. FFmpeg controls its own encoding threads.

`settings.json` records inputs, render settings, camera, frame count, unique renders, worker count, and render time. `encoding.json` records encoding settings and movie duration. Both codecs receive only the active frame count; stale frames from older runs are excluded.

Re-render after changing a state, mesh, camera, timing, or dimensions. `encode` changes compression and GIF settings using existing PNGs. Changing fps during re-encoding retimes those frames; changing fps during rendering preserves the requested motion speed.
