"""Project setup must be repeatable without replacing working presets."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pv_frd_animation.cli import init_configs
from pv_frd_animation.config import default_config


class ProjectTests(unittest.TestCase):
    def test_init_preserves_existing_local_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configs = root/'examples'
            (configs/'beam').mkdir(parents=True)
            (configs/'modes').mkdir()
            (configs/'beam/config.example.json').write_text('{"speed": 0.5}\n')
            (configs/'modes/config.example.json').write_text('{"seconds_per_cycle": 2}\n')
            (configs/'beam/config.local.json').write_text('{"speed": 0.2}\n')
            with patch('pv_frd_animation.cli.PROJECT_ROOT',root), contextlib.redirect_stdout(io.StringIO()):
                init_configs([])
                init_configs([])
            self.assertEqual((configs/'beam/config.local.json').read_text(),'{"speed": 0.2}\n')
            self.assertEqual((configs/'modes/config.local.json').read_text(),'{"seconds_per_cycle": 2}\n')

    def test_default_prefers_local_then_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'examples/beam').mkdir(parents=True)
            example = root/'examples/beam/config.example.json'
            local = root/'examples/beam/config.local.json'
            example.write_text('{}')
            with patch('pv_frd_animation.config.PROJECT_ROOT',root):
                self.assertEqual(default_config('beam'),example)
                local.write_text('{}')
                self.assertEqual(default_config('beam'),local)


if __name__ == '__main__':
    unittest.main()
