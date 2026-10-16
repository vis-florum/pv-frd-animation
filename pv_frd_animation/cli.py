"""Two workflows. One entry point."""
import argparse
import sys
from .config import PROJECT_ROOT

from .pipeline import main as run_pipeline


def init_configs(argv):
    parser = argparse.ArgumentParser(prog='animate.py init',description='Create local configs without overwriting existing settings.')
    parser.parse_args(argv)
    for example in sorted((PROJECT_ROOT/'examples').glob('*/config.example.json')):
        local = example.with_name(example.name.replace('.example.json','.local.json'))
        try:
            with local.open('x') as target:
                target.write(example.read_text())
            print('Created '+str(local.relative_to(PROJECT_ROOT)))
        except FileExistsError:
            print('Kept '+str(local.relative_to(PROJECT_ROOT)))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog='animate.py',
        description='ParaView displacement animations: single modes and PVD sweeps.',
        epilog='Examples: uv run animate.py beam doctor | uv run animate.py modes --seconds-per-cycle 2')
    parser.add_argument('workflow',choices=['beam','modes','init'],help='beam: one VTU; modes: PVD sweep; init: create local configs')
    if not argv:
        parser.print_help()
        return 0
    selected = parser.parse_args(argv[:1])
    if selected.workflow == 'init':
        return init_configs(argv[1:])
    if selected.workflow == 'modes':
        from .modes_config import arguments
    else:
        from .config import arguments
    return run_pipeline(argv[1:],parse=arguments)
