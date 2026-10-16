"""FFmpeg exports, independent of the ParaView interpreter."""
from contextlib import contextmanager
import json
import os
import shutil
import tempfile
from pathlib import Path
import subprocess

@contextmanager
def bounded_frames(out, count):
    """Give FFmpeg exactly the active sequence, excluding stale trailing PNGs.

    A filter-level trim is insufficient: a later resolution change resets
    FFmpeg's filter graph and can replace buffered palette-generation frames.
    Hard links cost no extra image storage; copies are the portable fallback.
    """
    if type(count) is not int or count < 1:
        raise ValueError('settings.json frame_count must be a positive integer')
    with tempfile.TemporaryDirectory(prefix='.encode-', dir=out) as directory:
        sequence = Path(directory)
        for index in range(count):
            source = (out / 'frames' / ('frame_%05d.png' % index)).resolve(strict=True)
            destination = sequence / ('frame_%05d.png' % index)
            try:
                os.link(source, destination)
            except OSError:
                shutil.copyfile(source, destination)
        yield sequence / 'frame_%05d.png'


def encode(a):
    out = Path(a.output)
    meta = json.loads((out / 'settings.json').read_text())
    n = meta['frame_count']
    with bounded_frames(out, n) as pattern:
        encode_sequence(a, out, n, pattern)
    (out / 'encoding.json').write_text(json.dumps(dict(fps=a.fps, crf=a.crf, preset=a.preset,
        gif_fps=min(a.gif_fps, a.fps), gif_width=a.gif_width, gif_colors=a.gif_colors,
        frames=n, duration_seconds=n/a.fps), indent=2) + '\n')
    print('Saved MP4 and GIF to ' + str(out), flush=True)




def encode_sequence(a, out, n, pattern):
    stem = getattr(a,'output_stem','beam_animation')
    common = [a.ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-framerate', str(a.fps),
              '-start_number', '0', '-i', str(pattern)]
    print('Encoding MP4...', flush=True)
    subprocess.run(common + ['-frames:v', str(n), '-c:v', 'libx264', '-crf', str(a.crf),
                            '-preset', a.preset, '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                            str(out / (stem+'.mp4'))], check=True)
    print('Encoding GIF...', flush=True)
    filters = ('[0:v]trim=end_frame=%d,setpts=PTS-STARTPTS,fps=%d,scale=%d:-1:flags=lanczos,split[s0][s1];'
               '[s0]palettegen=max_colors=%d:stats_mode=full[p];'
               '[s1][p]paletteuse=dither=sierra2_4a[out]') % (n, min(a.gif_fps, a.fps), a.gif_width, a.gif_colors)
    subprocess.run(common + ['-filter_complex', filters, '-map', '[out]', '-loop', '0',
                            str(out / (stem+'.gif'))], check=True)
