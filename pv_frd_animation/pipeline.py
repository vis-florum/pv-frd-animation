"""Run the complete pipeline or its independent stages."""
from pathlib import Path
import subprocess
import sys

from .config import arguments
from .encoding import encode
from .executables import find_ffmpeg, find_pvpython, launch_renderer


def doctor(a):
    good = True
    print('Python:', sys.executable)
    for label, find, override in [('ParaView', find_pvpython, a.pvpython), ('FFmpeg', find_ffmpeg, a.ffmpeg)]:
        try:
            print(label + ':', find(override))
        except RuntimeError as exc:
            print(label + ':', exc)
            good = False
    for label, path in [('State', a.state), ('Data', a.data)]:
        exists = bool(path) and Path(path).is_file()
        print(label + ':', path, '(OK)' if exists else '(MISSING)')
        good &= exists
    return 0 if good else 1


def main(argv=None, parse=arguments):
    try:
        a = parse(argv)
        if a.stage == 'doctor':
            return doctor(a)
        Path(a.output).mkdir(parents=True, exist_ok=True)
        if a.stage in ('run', 'encode'):
            a.ffmpeg = find_ffmpeg(a.ffmpeg)
        if a.stage in ('run', 'render', 'preview'):
            for filename in (a.state, a.data):
                if not Path(filename).is_file():
                    raise FileNotFoundError(filename)
            if a.workers > 1 and not a.preview_only:
                a.pvpython = find_pvpython(a.pvpython)
                launch_renderer(a)
            else:
                try:
                    import paraview.simple
                except ImportError:
                    a.pvpython = find_pvpython(a.pvpython)
                    launch_renderer(a)
                else:
                    if getattr(a,'animation_type','beam') == 'modes':
                        from .modes_renderer import render
                    else:
                        from .renderer import render
                    render(a)
        if a.stage in ('run', 'encode'):
            encode(a)
        return 0
    except KeyboardInterrupt:
        print('Rendering cancelled.', file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print('Error:', exc, file=sys.stderr)
        return 1
