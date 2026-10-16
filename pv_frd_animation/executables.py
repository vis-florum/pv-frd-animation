"""Find native tools without assuming a machine-specific installation path."""
import os
from pathlib import Path
import shutil
import subprocess
import time


def executable(value):
    if not value:
        return None
    found = shutil.which(os.path.expanduser(value))
    return str(Path(found).resolve()) if found else None


def find_pvpython(override=None):
    requested = override or os.environ.get('PVPYTHON')
    if requested:
        found = executable(requested)
        if not found:
            raise RuntimeError('pvpython is not executable: ' + requested)
        return found
    candidates = [shutil.which('pvpython')]
    if os.environ.get('PARAVIEW_HOME'):
        candidates.append(str(Path(os.environ['PARAVIEW_HOME']) / 'bin' / 'pvpython'))
        candidates.append(str(Path(os.environ['PARAVIEW_HOME']) / 'bin' / 'pvpython.exe'))
    for base, pattern in [(Path.home()/'Software', 'ParaView*/bin/pvpython'),
                          (Path.home()/'Applications', 'ParaView*/bin/pvpython'),
                          (Path('/opt'), 'ParaView*/bin/pvpython'),
                          (Path('/Applications'), 'ParaView*.app/Contents/bin/pvpython'),
                          (Path(os.environ.get('ProgramFiles', 'C:/Program Files')), 'ParaView*/bin/pvpython.exe')]:
        candidates.extend(str(p) for p in sorted(base.glob(pattern), reverse=True))
    for candidate in candidates:
        found = executable(candidate)
        if found:
            return found
    raise RuntimeError('ParaView not found. Install ParaView and set PVPYTHON, PARAVIEW_HOME, or --pvpython.')


def find_ffmpeg(override='ffmpeg'):
    found = executable(os.environ.get('FFMPEG') if override == 'ffmpeg' else override)
    found = found or executable(override)
    if not found:
        raise RuntimeError('FFmpeg not found. Install FFmpeg and set FFMPEG or --ffmpeg.')
    return found


def launch_renderer(a):
    import json
    from .config import PROJECT_ROOT
    from .frames import frame_plan, finalize_frames
    started = time.perf_counter()
    request = Path(a.output) / '.render-request.json'
    request.write_text(json.dumps(vars(a), indent=2) + '\n')
    env = os.environ.copy()
    # ParaView owns its Python/VTK libraries; do not inject the uv environment.
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    env.pop('VIRTUAL_ENV', None)
    cmd = [a.pvpython, '--no-mpi', '--force-offscreen-rendering',
           str(PROJECT_ROOT / 'pv_frd_animation' / 'worker.py'), str(request)]
    count = 1 if a.preview_only else min(a.workers, len(frame_plan(a)[0]))
    threads = a.threads_per_worker
    if threads == 0 and count > 1:
        cpus = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
        threads = max(1, min(8, cpus // count))
    if threads:
        for variable in ('VTK_SMP_MAX_THREADS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'LP_NUM_THREADS'):
            env[variable] = str(threads)
    print('Rendering with %d ParaView process(es)%s: %s' %
          (count, ('; %d CPU threads each' % threads) if threads else '', a.pvpython), flush=True)
    if count == 1:
        env['XDG_CONFIG_HOME'] = str(Path(a.output) / '.config')
        env['MPLCONFIGDIR'] = str(Path(a.output) / '.config' / 'matplotlib')
        subprocess.run(cmd, env=env, check=True)
    else:
        run_worker_pool(cmd, env, Path(a.output), count)
        finalize_frames(a)
    if not a.preview_only:
        settings = Path(a.output) / 'settings.json'
        metadata = json.loads(settings.read_text())
        metadata.update(render_seconds=time.perf_counter()-started, render_workers=count,
                        effective_threads_per_worker=threads or None)
        settings.write_text(json.dumps(metadata, indent=2) + '\n')
        print('Rendering complete in %.2fs.' % metadata['render_seconds'], flush=True)


def run_worker_pool(command, env, output, count):
    """Supervise independent native processes and stop all on error/cancellation."""
    logs = output / 'worker_logs'
    logs.mkdir(exist_ok=True)
    processes, handles = [], []
    try:
        # Start every process before waiting, so frames are rendered concurrently.
        for index in range(count):
            worker_env = dict(env)
            config = output / '.config' / ('worker_%d' % (index+1))
            worker_env['XDG_CONFIG_HOME'] = str(config)
            worker_env['MPLCONFIGDIR'] = str(config / 'matplotlib')
            log = logs / ('worker_%d.log' % (index+1))
            handle = log.open('w')
            handles.append(handle)
            process = subprocess.Popen([*command, str(index), str(count)], env=worker_env,
                                       stdout=handle, stderr=subprocess.STDOUT)
            processes.append(process)
            print('Started worker %d (PID %d); log: %s' % (index+1, process.pid, log), flush=True)
        pending = set(range(count))
        while pending:
            for index in list(pending):
                code = processes[index].poll()
                if code is None:
                    continue
                if code != 0:
                    log = logs / ('worker_%d.log' % (index+1))
                    tail = '\n'.join(log.read_text(errors='replace').splitlines()[-12:])
                    raise RuntimeError('Render worker %d failed (exit %d). See %s\n%s' %
                                       (index+1, code, log, tail))
                pending.remove(index)
                print('Worker %d finished (%d/%d).' % (index+1, count-len(pending), count), flush=True)
            if pending:
                time.sleep(0.2)
    finally:
        # Includes startup errors and Ctrl-C: never leave native renderers running.
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for handle in handles:
            handle.close()
