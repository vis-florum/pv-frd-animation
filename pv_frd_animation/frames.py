"""Plan independent renders, deduplicate poses, and assemble ordered frames."""
import json
from pathlib import Path
import shutil

from .camera import moving_camera
from .timing import frame_count, frame_time, displacement


def frame_plan(a):
    if getattr(a,'animation_type','beam') == 'turntable':
        from .turntable_timing import frame_plan as turntable_plan
        return turntable_plan(a)
    if getattr(a,'animation_type','beam') == 'modes':
        from .modes_timing import frame_plan as mode_plan
        return mode_plan(a)
    unique, aliases, seen = [], [], {}
    moving = moving_camera(a)
    for index in range(frame_count(a)):
        key = index if moving else round(displacement(a, frame_time(a, index)), 12)
        if key not in seen:
            seen[key] = index
            unique.append(index)
        aliases.append(seen[key])
    return unique, aliases


def assigned_frames(a, worker_index, worker_count):
    return frame_plan(a)[0][worker_index::worker_count]


def finalize_frames(a, metadata=None):
    """Publish the sequence and settings only after all unique renders exist."""
    out = Path(a.output)
    provisional = out / '.render-metadata.json'
    if metadata is None:
        metadata = json.loads(provisional.read_text())
    frames = out / 'frames'
    unique, aliases = frame_plan(a)
    missing = [i for i in unique if not (frames / ('pose_%05d.png' % i)).is_file()]
    if missing:
        raise RuntimeError('Rendering incomplete; missing pose frames: ' + ', '.join(map(str, missing[:10])))
    for index, canonical in enumerate(aliases):
        image = frames / ('pose_%05d.png' % canonical)
        target = frames / ('frame_%05d.png' % index)
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            target.symlink_to(image.name)
        except OSError:
            shutil.copyfile(image, target)
    metadata['unique_render_count'] = len(unique)
    provisional.write_text(json.dumps(metadata, indent=2) + '\n')
    provisional.replace(out / 'settings.json')
