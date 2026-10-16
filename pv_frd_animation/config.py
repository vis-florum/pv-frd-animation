"""Shared defaults and command-line/config-file validation."""
import argparse
import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def default_config(workflow):
    local = PROJECT_ROOT / 'configs' / (workflow+'.local.json')
    return local if local.is_file() else PROJECT_ROOT / 'configs' / (workflow+'.example.json')


DEFAULTS = dict(
    state=str(PROJECT_ROOT / 'states' / 'beam.pvsm'),
    data=str(PROJECT_ROOT / 'data' / 'beam.vtu'),
    output=str(PROJECT_ROOT / 'output' / 'beam'),
    amplitude=0.7,        # WarpByVector scale factor, NOT a target displacement.
    cycles=3,            # Each cycle: 0 -> +amplitude -> 0 -> -amplitude -> 0.
    speed=0.5,           # Beam cycles per second, independent of frame rate.
    fps=24,              # Samples per second.
    workers=1,           # Independent ParaView processes rendering separate frames.
    threads_per_worker=0, # 0: native default for serial; up to 8 per parallel worker.
    width=1920,
    height=1080,
    crf=14,              # MP4 quality: 0 lossless; 14 very high; 23 smaller.
    preset='slow',       # MP4 encoding speed/compression tradeoff.
    gif_width=1920,
    gif_fps=24,
    gif_colors=256,
    azimuth=0.0,         # Degrees around the initial camera's up direction.
    elevation=0.0,       # Degrees above/below the initial view.
    roll=0.0,            # Degrees rotating the image in its plane.
    zoom=1.0,            # 1 fits the beam; larger values bring it closer.
    state_camera=False,  # Preserve the state's framing instead of fitting bounds.
    orbit_degrees=0.0,   # Total rotation across the whole movie; 0 disables orbit.
    orbit_axis=[0.0, 1.0, 0.0],  # World-space axis through the camera focal point.
    orbit2_degrees=0.0,  # Second simultaneous rotation, at the same radius.
    orbit2_axis=[0.0, 0.0, 1.0],
    fly_through=False,
    fly_through_at=None,       # Seconds; default is the middle of the movie.
    fly_through_duration=None, # Seconds; default min(2, movie duration / 3).
    pvpython=None,
    ffmpeg='ffmpeg',
)


def arguments(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    selected_default = default_config('beam')
    pre.add_argument('--config', type=Path, default=selected_default)
    selected, _ = pre.parse_known_args(argv)
    defaults = dict(DEFAULTS)
    if selected.config.is_file():
        try:
            config = json.loads(selected.config.read_text())
            if not isinstance(config, dict) or set(config) - set(DEFAULTS):
                raise ValueError('Config must use the keys in configs/beam.example.json')
            for key, value in config.items():
                expected = DEFAULTS[key]
                if key in ('orbit_axis', 'orbit2_axis'):
                    valid = isinstance(value, list) and len(value) == 3 and all(type(x) in (int, float) for x in value)
                elif key in ('fly_through_at', 'fly_through_duration'):
                    valid = value is None or type(value) in (int, float)
                elif key == 'pvpython':
                    valid = value is None or isinstance(value, str)
                elif isinstance(expected, bool):
                    valid = isinstance(value, bool)
                elif isinstance(expected, int):
                    valid = type(value) is int
                elif isinstance(expected, float):
                    valid = type(value) in (int, float)
                else:
                    valid = isinstance(value, str)
                if not valid:
                    raise ValueError('Invalid type for config setting: ' + key)
            defaults.update(config)
            for key in ('state', 'data', 'output', 'pvpython', 'ffmpeg'):
                value = defaults[key]
                if value and (key in ('state', 'data', 'output') or '/' in value or '\\' in value):
                    path = Path(value).expanduser()
                    defaults[key] = str((selected.config.resolve().parent / path).resolve())
        except (ValueError, TypeError) as exc:
            pre.error(str(exc))
    elif selected.config != selected_default:
        pre.error('Config file does not exist: ' + str(selected.config))
    p = argparse.ArgumentParser(description='Animate a beam mode with camera controls, optional orbit, and MP4/GIF export.', parents=[pre])
    p.add_argument('stage', nargs='?', choices=['run', 'render', 'preview', 'encode', 'doctor'], default='run', help='Pipeline stage (default: run = render + encode)')
    for key in ('state', 'data', 'output'):
        p.add_argument('--' + key, default=DEFAULTS[key])
    p.add_argument('--amplitude', type=float, default=DEFAULTS['amplitude'], help='Warp scale factor (default: 0.7)')
    camera_help = {
        'speed': 'Beam cycles per second (default: 0.5); duration = cycles / speed',
        'zoom': 'Zoom relative to fitted view (default: 1); larger brings the beam closer',
        'orbit2_degrees': 'Second simultaneous orbit rotation in degrees (default: 0)',
        'fly_through_at': 'Crossing time in seconds (default: movie midpoint)',
        'fly_through_duration': 'Flight window in seconds (default: min(2, movie duration / 3))',
    }
    for key in ('speed', 'azimuth', 'elevation', 'roll', 'zoom', 'orbit_degrees', 'orbit2_degrees', 'fly_through_at', 'fly_through_duration'):
        p.add_argument('--' + key.replace('_', '-'), type=float, default=DEFAULTS[key], help=camera_help.get(key))
    p.add_argument('--orbit-axis', type=float, nargs=3, metavar=('X', 'Y', 'Z'), default=DEFAULTS['orbit_axis'], help='World-space orbit axis (default: 0 1 0)')
    p.add_argument('--orbit2-axis', type=float, nargs=3, metavar=('X', 'Y', 'Z'), default=DEFAULTS['orbit2_axis'], help='Second world-space orbit axis (default: 0 0 1)')
    p.add_argument('--fly-through', action=argparse.BooleanOptionalAction, default=DEFAULTS['fly_through'], help='Cross the moving beam once, then resume orbiting on the far side')
    p.add_argument('--state-camera', action=argparse.BooleanOptionalAction, default=DEFAULTS['state_camera'], help='Use the state camera framing; --zoom 1 preserves its zoom exactly')
    p.add_argument('--workers', type=int, default=DEFAULTS['workers'], help='Concurrent ParaView frame renderers (default: 1)')
    p.add_argument('--threads-per-worker', type=int, default=DEFAULTS['threads_per_worker'], help='CPU rendering threads per process; 0 uses automatic limits (default: 0)')
    for key in ('cycles', 'fps', 'width', 'height', 'crf', 'gif_width', 'gif_fps', 'gif_colors'):
        p.add_argument('--' + key.replace('_', '-'), type=int, default=DEFAULTS[key])
    p.add_argument('--preset', default=DEFAULTS['preset'], choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'])
    p.add_argument('--pvpython', help='Override automatic ParaView executable discovery')
    p.add_argument('--ffmpeg', default='ffmpeg')
    p.add_argument('--encode-only', action='store_true', help='Reuse existing PNGs; change fps/CRF/GIF settings without rendering')
    p.add_argument('--preview-only', action='store_true', help='Save one peak-displacement PNG and an animated PVSM, without movies')
    p.set_defaults(**defaults)
    a = p.parse_args(argv)
    if a.preset not in ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']:
        p.error('Invalid MP4 preset: ' + a.preset)
    a.config = str(a.config.resolve())
    if a.encode_only and a.preview_only:
        p.error('--encode-only and --preview-only cannot be combined')
    if a.encode_only:
        a.stage = 'encode'
    if a.preview_only:
        a.stage = 'preview'
    a.preview_only = a.stage == 'preview'
    a.encode_only = a.stage == 'encode'
    for key in ('workers', 'cycles', 'fps', 'width', 'height', 'gif_width', 'gif_fps'):
        if getattr(a, key) < 1:
            p.error('--' + key.replace('_', '-') + ' must be positive')
    if a.threads_per_worker < 0:
        p.error('--threads-per-worker must be nonnegative')
    if not math.isfinite(a.amplitude) or a.amplitude <= 0 or not 0 <= a.crf <= 51 or not 4 <= a.gif_colors <= 256:
        p.error('Require amplitude > 0, CRF 0..51, GIF colors 4..256')
    if a.width % 2 or a.height % 2:
        p.error('Width and height must be even for H.264')
    if not math.isfinite(a.speed) or a.speed <= 0:
        p.error('--speed must be positive cycles per second')
    if a.fps < 4 * a.speed:
        p.error('--fps must be at least 4 times --speed to sample each oscillation')
    camera_values = [a.azimuth, a.elevation, a.roll, a.zoom, a.orbit_degrees, a.orbit2_degrees, *a.orbit_axis, *a.orbit2_axis]
    if not all(math.isfinite(x) for x in camera_values) or a.zoom <= 0:
        p.error('Camera settings must be finite and zoom must be positive')
    for key in ('orbit_axis', 'orbit2_axis'):
        if len(getattr(a, key)) != 3 or math.hypot(*getattr(a, key)) < 1e-12:
            p.error('--' + key.replace('_', '-') + ' must be a nonzero vector of three components')
    from .timing import duration, frame_count
    for key in ('fly_through_at', 'fly_through_duration'):
        value = getattr(a, key)
        if value is not None and (not math.isfinite(value) or value < 0):
            p.error('--' + key.replace('_', '-') + ' must be finite and nonnegative')
    if a.fly_through:
        length = duration(a)
        interval = length / (frame_count(a) - 1)
        center = length/2 if a.fly_through_at is None else a.fly_through_at
        # Ensure an output frame is exactly inside the moving beam.
        a.fly_through_at = round(center / interval) * interval
        a.fly_through_duration = min(2.0, length/3) if a.fly_through_duration is None else a.fly_through_duration
        if a.fly_through_duration < 4*interval:
            p.error('--fly-through-duration must span at least four frame intervals; increase fps or reduce speed')
        if not a.fly_through_duration/2 < a.fly_through_at < length-a.fly_through_duration/2:
            p.error('The fly-through window must lie inside the movie; adjust --fly-through-at/duration')
    for key in ('state', 'data', 'output'):
        setattr(a, key, str(Path(getattr(a, key)).expanduser().resolve()))
    return a
