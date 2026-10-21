"""Two sequential full orbits with exact join and closing poses."""
import itertools
import math

from .camera import orbit_pose, unit, cross, dot


def intervals_per_orbit(a):
    return round(a.seconds_per_orbit*a.fps)


def frame_count(a):
    return 2*intervals_per_orbit(a)+1


def pose(a, initial, index):
    steps = intervals_per_orbit(a)
    if index in (0, steps, 2*steps):
        return dict(initial)
    if index < steps:
        return orbit_pose(initial, [0,1,0], 360*index/steps)
    return orbit_pose(initial, [0,0,1], 360*(index-steps)/steps)


def frame_plan(a):
    steps = intervals_per_orbit(a)
    aliases = [0 if i in (steps, 2*steps) else i for i in range(frame_count(a))]
    return list(dict.fromkeys(aliases)), aliases


def fitted_pose(initial, bounds, aspect):
    """Fit visible bounds across both full orbits; retain the saved direction."""
    if len(bounds) != 6 or any(not math.isfinite(x) for x in bounds) or any(bounds[2*i] > bounds[2*i+1] for i in range(3)):
        raise ValueError('Cannot fit an empty scene; check the saved visibility and input paths')
    focal = [(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)]
    if not any(bounds[2*i+1] > bounds[2*i] for i in range(3)):
        raise ValueError('Visible scene has zero-size bounds')
    corners = [[p-f for p,f in zip(point,focal)] for point in itertools.product(
        *[(bounds[2*i],bounds[2*i+1]) for i in range(3)])]
    tangent = math.tan(math.radians(initial['angle']/2))
    distance, scale = 0.0, 0.0
    for axis in ([0,1,0],[0,0,1]):
        for degrees in range(361):
            camera = orbit_pose(initial,axis,degrees)
            normal = unit([p-f for p,f in zip(camera['position'],camera['focal'])])
            right = unit(cross(camera['up'],normal))
            up = unit(cross(normal,right))
            for point in corners:
                extent = max(abs(dot(point,right))/aspect,abs(dot(point,up)))
                scale = max(scale,extent)
                distance = max(distance,dot(point,normal)+extent/tangent)
    normal = unit([p-f for p,f in zip(initial['position'],initial['focal'])])
    return dict(initial, focal=focal, position=[f+1.03*distance*n for f,n in zip(focal,normal)],
                parallel_scale=1.03*scale)
