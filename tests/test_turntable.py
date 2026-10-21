"""Camera tours must preserve the join, orbit order, and portable settings."""
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from pv_frd_animation.frames import assigned_frames, frame_plan
from pv_frd_animation.turntable_config import arguments, state_inputs
from pv_frd_animation.turntable_timing import frame_count, intervals_per_orbit, pose, fitted_pose


class TurntableTests(unittest.TestCase):
    def test_y_then_z_with_exact_join_and_closing_pose(self):
        a = arguments(['--seconds-per-orbit','2','--fps','12'])
        initial = dict(position=[2,0,0],focal=[0,0,0],up=[0,1,0])
        n = intervals_per_orbit(a)
        self.assertEqual(frame_count(a),49)
        self.assertLess(math.dist(pose(a,initial,n//4)['position'],[0,0,-2]),1e-12)
        self.assertLess(math.dist(pose(a,initial,n+n//4)['position'],[0,2,0]),1e-12)
        for i in (0,n,2*n):
            self.assertEqual(pose(a,initial,i),initial)
        for i in range(frame_count(a)):
            self.assertAlmostEqual(math.dist(pose(a,initial,i)['position'],initial['focal']),2)
        unique, aliases = frame_plan(a)
        self.assertEqual([aliases[i] for i in (0,n,2*n)],[0,0,0])
        self.assertEqual(sorted(i for worker in range(3) for i in assigned_frames(a,worker,3)),unique)

    def test_fit_recenters_and_contains_bounds_through_both_orbits(self):
        import itertools
        from pv_frd_animation.camera import unit, cross, dot
        a = arguments(['--seconds-per-orbit','4','--fps','24'])
        bounds = [0,370,0,380,0,2510]
        initial = dict(position=[-700,-530,2870],focal=[1890,1740,-550],up=[.39,-.88,-.29],angle=30,parallel_scale=1259)
        fitted = fitted_pose(initial,bounds,2)
        self.assertEqual(fitted['focal'],[185,190,1255])
        for i in range(frame_count(a)):
            camera = pose(a,fitted,i)
            normal = unit([p-f for p,f in zip(camera['position'],camera['focal'])])
            right = unit(cross(camera['up'],normal))
            up = unit(cross(normal,right))
            for point in itertools.product(*[(bounds[j],bounds[j+1]) for j in (0,2,4)]):
                relative = [p-f for p,f in zip(point,camera['focal'])]
                half_height = (math.dist(camera['position'],camera['focal'])-dot(relative,normal))*math.tan(math.radians(15))
                self.assertLess(abs(dot(relative,right)),2*half_height)
                self.assertLess(abs(dot(relative,up)),half_height)

    def test_config_relative_paths_and_cli_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)/'config.json'
            config.write_text(json.dumps(dict(state='scene.pvsm',output='animation',zoom=.9)))
            a = arguments(['preview','--config',str(config),'--zoom','.8'])
            self.assertEqual(a.state,str(Path(directory)/'scene.pvsm'))
            self.assertEqual(a.output,str(Path(directory)/'animation'))
            self.assertEqual(a.zoom,.8)
            self.assertTrue(a.preview_only)
            self.assertEqual(a.animation_type,'turntable')

    def test_invalid_timing_zoom_and_quality_are_rejected(self):
        for options in (['--zoom','0'],['--zoom','nan'],['--seconds-per-orbit','inf'],
                        ['--seconds-per-orbit','.01'],['--width','1919'],['--crf','52']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                arguments(options)

    def test_reader_inputs_resolve_relative_to_the_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'view.pvsm'
            state.write_text('<ServerManagerState><Proxy group="sources"><Property name="FileName">'
                             '<Element value="volume.nrrd"/><Element value="profiles.vtm"/>'
                             '</Property></Proxy></ServerManagerState>')
            self.assertEqual(state_inputs(state),[Path(directory)/'volume.nrrd',Path(directory)/'profiles.vtm'])


if __name__ == '__main__':
    unittest.main()
