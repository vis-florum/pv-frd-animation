"""Regression checks that run without ParaView or third-party test tools."""
import contextlib
import io
import json
import math
import os
import itertools
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

from pv_frd_animation.camera import orbit_pose, orbital_pose, path_pose, fitted_extents, unit, cross, dot
from pv_frd_animation.config import arguments
from pv_frd_animation.timing import displacement, duration, frame_count, frame_time
from pv_frd_animation.frames import frame_plan, assigned_frames, finalize_frames
from pv_frd_animation.executables import run_worker_pool


class CameraTests(unittest.TestCase):
    def settings(self, *options):
        return arguments(list(options))

    def test_orbit_preserves_radius_focal_point_and_camera_up(self):
        start = dict(position=[3, 4, 5], focal=[1, 2, 3], up=[0, 1, 0])
        for angle in [0, 45, 90, 180, 270, 360, -90, 720]:
            pose = orbit_pose(start, [0, 2, 0], angle)
            self.assertEqual(pose['focal'], start['focal'])
            self.assertEqual(pose['up'], start['up'])
            self.assertAlmostEqual(math.dist(pose['position'], pose['focal']), math.sqrt(12))
        self.assertAlmostEqual(orbit_pose(start, [0, 1, 0], 90)['position'][0], 3)
        self.assertLess(math.dist(orbit_pose(start, [0, 1, 0], 360)['position'], start['position']), 1e-12)

    def test_orbit_supports_arbitrary_axis(self):
        start = dict(position=[2, 0, 0], focal=[0, 0, 0], up=[0, 1, 0])
        pose = orbit_pose(start, [0, 0, 1], 90)
        self.assertLess(math.dist(pose['position'], [0, 2, 0]), 1e-12)
        self.assertLess(math.dist(pose['up'], [-1, 0, 0]), 1e-12)

    def test_two_orbits_keep_radius_but_leave_the_first_orbit_plane(self):
        a = self.settings('--orbit-degrees', '360', '--orbit2-degrees', '75')
        start = dict(position=[4, 0, 0], focal=[0, 0, 0], up=[0, 1, 0])
        for i in range(101):
            pose = orbital_pose(a, start, i/100)
            self.assertAlmostEqual(math.dist(pose['position'], pose['focal']), 4)
        self.assertGreater(abs(orbital_pose(a, start, 0.2)['position'][1]), 0.1)

    def test_fly_through_crosses_the_moving_beam_and_rejoins_on_far_side(self):
        a = self.settings('--fly-through', '--fly-through-at', '2.5', '--orbit-degrees', '360', '--orbit2-degrees', '75')
        start = dict(position=[4, 2, 3], focal=[1, 2, 3], up=[0, 1, 0])
        target = dict(point=[1.1, 2.2, 3.1], disp=[0.2, 0.1, 0])
        center_pose = path_pose(a, start, a.fly_through_at, target)
        expected = [p+displacement(a, a.fly_through_at)*d for p, d in zip(target['point'],target['disp'])]
        self.assertLess(math.dist(center_pose['position'], expected), 1e-12)
        self.assertGreater(math.dist(center_pose['position'], center_pose['focal']), 1)
        before = path_pose(a, start, 0, target)
        self.assertEqual(before['position'], start['position'])
        after = path_pose(a, start, duration(a), target)
        orbit = orbital_pose(a, start, 1)
        self.assertLess(math.dist(after['position'],[2*f-p for f,p in zip(orbit['focal'],orbit['position'])]), 1e-12)
        # No direction singularity or positional jump at the entry/exit.
        for boundary in [a.fly_through_at-a.fly_through_duration/2, a.fly_through_at+a.fly_through_duration/2]:
            left = path_pose(a, start, boundary-1e-7, target)
            right = path_pose(a, start, boundary+1e-7, target)
            self.assertLess(math.dist(left['position'], right['position']), 1e-5)
            self.assertLess(math.dist(left['focal'], right['focal']), 1e-5)

    def test_fitted_view_leaves_space_for_legend_throughout_dual_orbit(self):
        a = self.settings('--orbit-degrees', '360', '--orbit2-degrees', '75')
        start = dict(position=[-3, 2, 4], focal=[0, 0, 0], up=[0, 1, 0])
        bounds = [-1, 1, -0.2, 0.2, -0.3, 0.3]
        distance, _ = fitted_extents(a, start, bounds, 30)
        tangent = math.tan(math.radians(15))
        for i in range(101):
            pose = orbital_pose(a, start, i/100)
            normal = unit(pose['position'])
            right = unit(cross(pose['up'], normal))
            up = unit(cross(normal, right))
            for point in itertools.product(*[(bounds[j],bounds[j+1]) for j in (0,2,4)]):
                depth = distance-dot(point,normal)
                x = dot(point,right)/(depth*tangent*a.width/a.height)
                y = dot(point,up)/(depth*tangent)
                self.assertLessEqual(abs(x), 0.92)
                self.assertLessEqual(y, 0.90)
                self.assertGreaterEqual(y, -0.58)


class ConfigTests(unittest.TestCase):
    def test_paths_are_relative_to_config_and_cli_overrides_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'example.json'
            config.write_text(json.dumps(dict(state='scene.pvsm', data='beam.vtu', output='result', zoom=2, orbit_degrees=180)))
            a = arguments(['preview', '--config', str(config), '--zoom', '1.2'])
            self.assertEqual(a.output, str(Path(directory)/'result'))
            self.assertEqual(a.data, str(Path(directory)/'beam.vtu'))
            self.assertEqual(a.zoom, 1.2)
            self.assertEqual(a.orbit_degrees, 180)
            self.assertTrue(a.preview_only)

    def test_invalid_camera_settings_are_rejected(self):
        for options in [ ['--zoom', '0'], ['--orbit-axis', '0', '0', '0'], ['--azimuth', 'nan'] ]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                arguments(options)

    def test_config_type_errors_are_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'bad.json'
            config.write_text('{"speed": "fast"}')
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                arguments(['--config', str(config)])
            self.assertIn('Invalid type for config setting: speed', error.getvalue())

    def test_invalid_speed_and_flight_windows_are_rejected(self):
        for options in [ ['--speed','0'], ['--speed','nan'], ['--speed','10','--fps','24'],
                         ['--fly-through','--fly-through-at','0'],
                         ['--fly-through','--fly-through-duration','0.01'] ]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                arguments(options)


class TimingTests(unittest.TestCase):
    def test_frame_rate_changes_sampling_and_not_beam_speed(self):
        low = arguments(['--speed','0.5','--fps','12'])
        high = arguments(['--speed','0.5','--fps','48'])
        self.assertEqual(duration(low), 6)
        self.assertEqual(duration(high), 6)
        self.assertEqual(frame_count(low), 73)
        self.assertEqual(frame_count(high), 289)
        for seconds in [0, 0.5, 1, 1.5, 2, 3.75, 6]:
            self.assertAlmostEqual(displacement(low,seconds),displacement(high,seconds))
        self.assertAlmostEqual(displacement(low,0.5), low.amplitude)
        self.assertAlmostEqual(displacement(low,1.5), -low.amplitude)
        self.assertEqual(frame_time(high,frame_count(high)-1),6)


class ParallelFrameTests(unittest.TestCase):
    def test_static_camera_reuses_poses_across_workers_and_cycles(self):
        a = arguments(['--workers','4'])
        unique, aliases = frame_plan(a)
        self.assertEqual(len(unique),25)
        self.assertEqual(len(aliases),145)
        self.assertEqual(aliases[0],aliases[48])
        self.assertEqual(aliases[48],aliases[144])
        assignments = [assigned_frames(a,i,4) for i in range(4)]
        flattened = [index for group in assignments for index in group]
        self.assertEqual(sorted(flattened),unique)
        self.assertEqual(len(flattened),len(set(flattened)))

    def test_moving_camera_assigns_every_frame_once_including_flight(self):
        a = arguments(['--workers','3','--orbit-degrees','360','--fly-through'])
        unique, aliases = frame_plan(a)
        self.assertEqual(unique,list(range(frame_count(a))))
        self.assertEqual(aliases,unique)
        assignments = [assigned_frames(a,i,3) for i in range(3)]
        self.assertEqual(sorted(index for group in assignments for index in group),unique)

    def test_finalize_rejects_missing_frames_before_publishing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            a = arguments(['--output',directory])
            with self.assertRaisesRegex(RuntimeError,'missing pose frames'):
                finalize_frames(a,dict(frame_count=frame_count(a)))
            self.assertFalse((Path(directory)/'settings.json').exists())

    def test_failed_worker_stops_its_sibling_process(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable,'-c',
                       'import sys,time; time.sleep(0.3 if sys.argv[1]=="0" else 30); sys.exit(7)']
            processes = []
            native_popen = subprocess.Popen
            def record(*args,**kwargs):
                p = native_popen(*args,**kwargs)
                processes.append(p)
                return p
            with patch('pv_frd_animation.executables.subprocess.Popen',side_effect=record), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError,'worker 1 failed'):
                    run_worker_pool(command,dict(os.environ),Path(directory),2)
            self.assertEqual(len(processes),2)
            self.assertTrue(all(p.poll() is not None for p in processes))

    def test_invalid_worker_limits_are_rejected(self):
        for options in [['--workers','0'], ['--workers','-1'], ['--threads-per-worker','-2']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                arguments(options)


if __name__ == '__main__':
    unittest.main()
