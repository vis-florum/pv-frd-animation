"""Settings for PVD mode sweeps; independent of the single-mode camera options."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .config import PROJECT_ROOT,default_config

DEFAULTS = dict(state=str(PROJECT_ROOT/'examples'/'modes'/'states'/'modes.pvsm'),pvd=None,
                output=str(PROJECT_ROOT/'examples'/'modes'/'output'),start_time=2.0,end_time=16.0,
                seconds_per_cycle=2.0,amplitude=0.1,fps=24,width=1920,height=1080,
                crf=14,preset='slow',gif_width=960,gif_fps=24,gif_colors=256,
                workers=1,threads_per_worker=0,pvpython=None,ffmpeg='ffmpeg')
PRESETS = ['ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow']


def state_reader(state):
    root = ET.parse(state).getroot()
    readers = root.findall(".//Proxy[@type='PVDReader']")
    if len(readers) != 1:
        raise ValueError('The mode-sweep state must contain exactly one PVD reader')
    reader = readers[0]
    name = next(item.get('name') for item in root.findall(".//ProxyCollection[@name='sources']/Item")
                if item.get('id') == reader.get('id'))
    filename = reader.find("Property[@name='FileName']/Element").get('value')
    return reader.get('id'),name,filename


def selected_modes(pvd,start,end):
    root = ET.parse(pvd).getroot()
    datasets = root.findall('.//DataSet')
    available = sorted({float(item.get('timestep')) for item in datasets})
    if start not in available or end not in available:
        raise ValueError('Start/end times must exist in the PVD. Available: ' + ', '.join(map(str,available)))
    modes = [time for time in available if start <= time <= end]
    if not modes:
        raise ValueError('No PVD mode times in the requested interval')
    for item in datasets:
        if float(item.get('timestep')) in modes:
            file = (Path(pvd).parent/item.get('file')).resolve()
            if not file.is_file():
                raise FileNotFoundError('PVD references a missing mode file: ' + str(file))
    return modes


def arguments(argv=None):
    pre = argparse.ArgumentParser(add_help=False)
    selected_default = default_config('modes')
    pre.add_argument('--config',type=Path,default=selected_default)
    selected,_ = pre.parse_known_args(argv)
    defaults = dict(DEFAULTS)
    if selected.config.is_file():
        config = json.loads(selected.config.read_text())
        if not isinstance(config,dict) or set(config)-set(DEFAULTS):
            pre.error('Mode config must use the keys in examples/modes/config.example.json')
        for key,value in config.items():
            expected = DEFAULTS[key]
            if key in ('pvd','pvpython'):
                valid = value is None or isinstance(value,str)
            elif isinstance(expected,int):
                valid = type(value) is int
            elif isinstance(expected,float):
                valid = type(value) in (int,float)
            else:
                valid = isinstance(value,str)
            if not valid:
                pre.error('Invalid type for mode config setting: ' + key)
        defaults.update(config)
        for key in ('state','pvd','output','pvpython','ffmpeg'):
            value = defaults[key]
            if value and (key in ('state','pvd','output') or '/' in value or '\\' in value):
                defaults[key] = str((selected.config.resolve().parent/Path(value).expanduser()).resolve())
    elif selected.config != selected_default:
        pre.error('Config file does not exist: ' + str(selected.config))
    p = argparse.ArgumentParser(description='Sweep PVD modes with one closed warp cycle at each time, preserving the state view and annotations.',parents=[pre])
    p.add_argument('stage',nargs='?',choices=['run','render','preview','encode','doctor'],default='run')
    descriptions = dict(state='ParaView state; camera and annotation settings are preserved',
                        pvd='Override the PVD path inferred from the state',output='Output directory',
                        start_time='First PVD time, inclusive (default: 2)',
                        end_time='Last PVD time, inclusive (default: 16)',
                        seconds_per_cycle='Seconds per complete warp cycle at each mode (default: 2)',
                        amplitude='Positive/negative peak warp scale (default: 0.1)')
    for key in ('state','pvd','output','pvpython','ffmpeg'):
        p.add_argument('--'+key,default=defaults[key],help=descriptions.get(key))
    for key in ('start_time','end_time','seconds_per_cycle','amplitude'):
        p.add_argument('--'+key.replace('_','-'),type=float,default=defaults[key],help=descriptions.get(key))
    for key in ('fps','width','height','crf','gif_width','gif_fps','gif_colors','workers','threads_per_worker'):
        p.add_argument('--'+key.replace('_','-'),type=int,default=defaults[key])
    p.add_argument('--preset',choices=PRESETS,default=defaults['preset'])
    a = p.parse_args(argv)
    a.config = str(a.config.resolve())
    for key in ('fps','width','height','gif_width','gif_fps','workers'):
        if getattr(a,key) < 1:
            p.error('--'+key.replace('_','-')+' must be positive')
    if a.threads_per_worker < 0 or not 0 <= a.crf <= 51 or not 4 <= a.gif_colors <= 256:
        p.error('Require threads-per-worker >= 0, CRF 0..51, and GIF colors 4..256')
    if a.preset not in PRESETS:
        p.error('Invalid encoding preset')
    if a.width%2 or a.height%2:
        p.error('Width and height must be even')
    if not all(math.isfinite(getattr(a,key)) for key in ('start_time','end_time','seconds_per_cycle','amplitude')):
        p.error('Mode times, seconds-per-cycle, and amplitude must be finite')
    if a.start_time > a.end_time or a.seconds_per_cycle <= 0 or a.amplitude <= 0:
        p.error('Require start-time <= end-time, seconds-per-cycle > 0, and amplitude > 0')
    if round(a.seconds_per_cycle*a.fps) < 5:
        p.error('Each cycle needs at least five frames; increase seconds-per-cycle or fps')
    for key in ('state','output','pvd'):
        if getattr(a,key):
            setattr(a,key,str(Path(getattr(a,key)).expanduser().resolve()))
    if a.pvd is None and Path(a.state).is_file():
        _,_,filename = state_reader(a.state)
        local = Path(a.state).parent/Path(filename).name
        a.pvd = str(local if local.is_file() else (Path(a.state).parent/filename).resolve())
    a.data = a.pvd
    if a.stage != 'encode' and not a.data:
        p.error('Cannot locate the PVD from the state; supply --pvd /path/to/modes.pvd')
    a.mode_times = []
    if a.stage != 'encode' and (a.stage != 'doctor' or (a.data and Path(a.data).is_file())):
        a.mode_times = selected_modes(a.data,a.start_time,a.end_time)
    a.animation_type = 'modes'
    a.output_stem = 'allmodes'
    a.preview_only = a.stage == 'preview'
    a.encode_only = a.stage == 'encode'
    return a
