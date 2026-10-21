"""Small native ParaView entry point, launched by the uv-managed orchestrator."""
from argparse import Namespace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if __name__ == '__main__':
    index, count = (int(x) for x in sys.argv[2:4]) if len(sys.argv) >= 4 else (0, 1)
    a = Namespace(**json.loads(Path(sys.argv[1]).read_text()))
    if getattr(a,'animation_type','beam') == 'turntable':
        from pv_frd_animation.turntable_renderer import render
    elif getattr(a,'animation_type','beam') == 'modes':
        from pv_frd_animation.modes_renderer import render
    else:
        from pv_frd_animation.renderer import render
    render(a, index, count)
