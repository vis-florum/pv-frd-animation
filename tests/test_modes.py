"""Mode sequencing and PVD settings, independent of a ParaView installation."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from pv_frd_animation.modes_config import arguments,selected_modes
from pv_frd_animation.modes_timing import samples_per_mode,sample,frame_count,frame_plan,content_size


class ModesTimingTests(unittest.TestCase):
    def settings(self,**overrides):
        return Namespace(**dict(dict(mode_times=list(range(2,17)),seconds_per_cycle=2,
                                    fps=24,amplitude=0.1),**overrides))

    def test_each_mode_is_a_closed_cycle_with_both_exact_peaks(self):
        a = self.settings()
        n = samples_per_mode(a)
        self.assertEqual(frame_count(a),720)
        for j,mode in enumerate(a.mode_times):
            values = [sample(a,j*n+i) for i in range(n)]
            self.assertTrue(all(time==mode for time,_ in values))
            self.assertEqual(values[0][1],0)
            self.assertEqual(values[-1][1],0)
            self.assertAlmostEqual(max(scale for _,scale in values),0.1)
            self.assertAlmostEqual(min(scale for _,scale in values),-0.1)

    def test_seconds_per_cycle_stays_constant_at_different_fps(self):
        for fps in (12,24,48):
            a = self.settings(fps=fps)
            self.assertEqual(frame_count(a)/fps,30)
            self.assertEqual(samples_per_mode(a)/fps,2)

    def test_reused_poses_never_cross_mode_boundaries(self):
        a = self.settings()
        unique,aliases = frame_plan(a)
        self.assertLess(len(unique),frame_count(a))
        for index,canonical in enumerate(aliases):
            expected,actual = sample(a,index),sample(a,canonical)
            self.assertEqual(expected[0],actual[0])
            self.assertAlmostEqual(expected[1],actual[1])

    def test_saved_view_is_fitted_without_stretching_or_cropping(self):
        self.assertEqual(content_size([1125,563],[1920,1080]),[1920,960])
        self.assertEqual(content_size([1000,1000],[1920,1080]),[1080,1080])


class ModesConfigTests(unittest.TestCase):
    def fixture(self,directory):
        root = Path(directory)
        files = []
        for time in (1,2,3,16,17):
            file = 'mode_%d.vtu'%time
            (root/file).write_text('fixture')
            files.append('<DataSet timestep="%d" file="%s"/>'%(time,file))
        (root/'modes.pvd').write_text('<VTKFile><Collection>'+''.join(files)+'</Collection></VTKFile>')
        (root/'view.pvsm').write_text('<ParaView><ServerManagerState><Proxy type="PVDReader" id="1">'
            '<Property name="FileName"><Element value="modes.pvd"/></Property></Proxy>'
            '<ProxyCollection name="sources"><Item id="1" name="modes.pvd"/></ProxyCollection>'
            '</ServerManagerState></ParaView>')
        config = root/'settings.json'
        config.write_text(json.dumps(dict(state='view.pvsm',pvd=None,output='results')))
        return config

    def test_infers_pvd_and_uses_inclusive_time_range_and_own_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.fixture(directory)
            a = arguments(['--config',str(config),'--seconds-per-cycle','3'])
            self.assertEqual(a.data,str(Path(directory)/'modes.pvd'))
            self.assertEqual(a.mode_times,[2,3,16])
            self.assertEqual(a.seconds_per_cycle,3)
            self.assertEqual((a.width,a.height,a.gif_width),(1920,1080,960))
            self.assertEqual(a.amplitude,0.1)
            self.assertEqual(a.animation_type,'modes')

    def test_invalid_timing_and_missing_modes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.fixture(directory)
            for flags in [['--seconds-per-cycle','0'],['--seconds-per-cycle','0.01'],['--start-time','18']]:
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    arguments(['--config',str(config),*flags])
            with self.assertRaisesRegex(ValueError,'must exist'):
                selected_modes(Path(directory)/'modes.pvd',2,15)

    def test_encode_does_not_need_state_or_pvd(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)/'settings.json'
            config.write_text(json.dumps(dict(state='missing.pvsm',pvd=None)))
            a = arguments(['encode','--config',str(config)])
            self.assertTrue(a.encode_only)
            self.assertEqual(a.mode_times,[])


if __name__ == '__main__':
    unittest.main()
