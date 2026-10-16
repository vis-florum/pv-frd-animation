# Examples

Run commands from the repository root. Create working presets once:

```sh
uv run animate.py init
```

| Example | Command | Inputs relative to its config |
|---|---|---|
| `beam/` | `uv run animate.py beam` | `states/beam.pvsm`, `data/beam.vtu` |
| `modes/` | `uv run animate.py modes` | `states/modes.pvsm`, `data/series.pvd` and its VTUs |
| `cinematic/` | `uv run animate.py beam --config examples/cinematic/config.local.json` | Shares `../beam/states/` and `../beam/data/` |

Each directory contains a tracked `config.example.json`. Edit the ignored `config.local.json` created by `init`; it is never overwritten. `beam` and `modes` select their local preset automatically. Create `data/` and `states/` as needed, or point the config to inputs elsewhere. Keep PVD files with the VTUs they reference.

All config paths resolve relative to that JSON, including `output`. Each preset writes frames, previews, MP4, GIF, saved state, settings, and logs to its own `output/`. CLI path overrides resolve relative to your current working directory.

Only `config.example.json` and `README.md` files under `examples/` are eligible for Git. Local presets, datasets, states, generated JSON metadata, and results are ignored. Copy an example directory to start another job; select its config with `--config`. Review portable paths before publishing a new example preset.
