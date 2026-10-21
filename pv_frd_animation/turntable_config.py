"""Camera-only tours of complete ParaView states."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .config import PROJECT_ROOT, default_config
from .modes_config import PRESETS

DEFAULTS = dict(state=str(PROJECT_ROOT/'examples/turntable/states/showcase.pvsm'),
                output=str(PROJECT_ROOT/'examples/turntable/output'),
                seconds_per_orbit=8.0, zoom=0.9, framing='fit', volume_renderer='state', fps=24, width=1920, height=1080,
                crf=14, preset='slow', gif_width=960, gif_fps=24, gif_colors=256,
                workers=1, threads_per_worker=0, pvpython=None, ffmpeg='ffmpeg')


def state_inputs(state):
    """Report file-backed readers without altering their saved configuration."""
    root = ET.parse(state).getroot()
    files = []
    for proxy in root.findall(".//Proxy[@group='sources']"):
        for element in proxy.findall("Property[@name='FileName']/Element"):
            value = element.get('value')
            if value:
                path = (Path(state).parent/Path(value).expanduser()).resolve()
                if path not in files:
                    files.append(path)
    return files


def arguments(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    selected_default = default_config('turntable')
    pre.add_argument('--config', type=Path, default=selected_default)
    selected, _ = pre.parse_known_args(argv)
    defaults = dict(DEFAULTS)
    if selected.config.is_file():
        config = json.loads(selected.config.read_text())
        if not isinstance(config, dict) or set(config)-set(DEFAULTS):
            pre.error('Config must use the keys in examples/turntable/config.example.json')
        for key, value in config.items():
            expected = DEFAULTS[key]
            valid = (value is None or isinstance(value, str)) if key == 'pvpython' else (
                type(value) is int if type(expected) is int else
                type(value) in (int, float) if type(expected) is float else isinstance(value, str))
            if not valid:
                pre.error('Invalid type for turntable config setting: '+key)
        defaults.update(config)
        for key in ('state', 'output', 'pvpython', 'ffmpeg'):
            value = defaults[key]
            if value and (key in ('state', 'output') or '/' in value or '\\' in value):
                defaults[key] = str((selected.config.resolve().parent/Path(value).expanduser()).resolve())
    elif selected.config != selected_default:
        pre.error('Config file does not exist: '+str(selected.config))
    p = argparse.ArgumentParser(description='Preserve a state scene; rotate 360 degrees around world Y, then 360 around world Z.', parents=[pre])
    p.add_argument('stage', nargs='?', choices=['run','render','preview','encode','doctor'], default='run')
    for key in ('state','output','pvpython','ffmpeg'):
        p.add_argument('--'+key, default=defaults[key])
    p.add_argument('--seconds-per-orbit', type=float, default=defaults['seconds_per_orbit'], help='Seconds per 360-degree rotation (default: 8)')
    p.add_argument('--zoom', type=float, default=defaults['zoom'], help='Relative to selected framing; less than 1 zooms out (default: 0.9)')
    for key in ('fps','width','height','crf','gif_width','gif_fps','gif_colors','workers','threads_per_worker'):
        p.add_argument('--'+key.replace('_','-'), type=int, default=defaults[key])
    p.add_argument('--framing', choices=['fit','state'], default=defaults['framing'], help='Fit all orbit angles around visible bounds, or retain the saved focal point and framing')
    p.add_argument('--volume-renderer', choices=['state','cpu','gpu'], default=defaults['volume_renderer'], help='Keep saved mapper, or select CPU/GPU volume rendering')
    p.add_argument('--preset', choices=PRESETS, default=defaults['preset'])
    a = p.parse_args(argv)
    for key in ('fps','width','height','gif_width','gif_fps','workers'):
        if getattr(a,key) < 1:
            p.error('--'+key.replace('_','-')+' must be positive')
    if a.width%2 or a.height%2:
        p.error('Width and height must be even')
    if a.threads_per_worker < 0 or not 0 <= a.crf <= 51 or not 4 <= a.gif_colors <= 256:
        p.error('Require threads-per-worker >= 0, CRF 0..51, and GIF colors 4..256')
    if a.framing not in ('fit','state'):
        p.error('Invalid framing')
    if a.volume_renderer not in ('state','cpu','gpu'):
        p.error('Invalid volume renderer')
    if a.preset not in PRESETS:
        p.error('Invalid encoding preset')
    if not all(math.isfinite(v) and v > 0 for v in (a.zoom, a.seconds_per_orbit)):
        p.error('Zoom and seconds-per-orbit must be positive and finite')
    if round(a.seconds_per_orbit*a.fps) < 4:
        p.error('Each orbit needs at least four frame intervals')
    a.config = str(a.config.resolve())
    for key in ('state','output'):
        setattr(a,key,str(Path(getattr(a,key)).expanduser().resolve()))
    a.animation_type = 'turntable'
    a.output_stem = 'turntable'
    a.data = a.state  # This workflow keeps every reader from the state.
    a.preview_only = a.stage == 'preview'
    a.encode_only = a.stage == 'encode'
    return a
