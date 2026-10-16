"""Camera placement, orbit geometry, and ParaView camera keyframes."""
import math

def rotate(vector, axis, degrees):
    """Rodrigues rotation in world coordinates, without extra dependencies."""
    length = math.hypot(*axis)
    x, y, z = [v / length for v in axis]
    vx, vy, vz = vector
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    dot = x*vx + y*vy + z*vz
    cross = [y*vz-z*vy, z*vx-x*vz, x*vy-y*vx]
    return [v*c + w*s + u*dot*(1-c) for v, w, u in zip(vector, cross, (x, y, z))]


def camera_pose(view):
    return dict(position=list(view.CameraPosition), focal=list(view.CameraFocalPoint),
                up=list(view.CameraViewUp), angle=float(view.CameraViewAngle),
                parallel_scale=float(view.CameraParallelScale))


def orbit_pose(initial, axis, degrees):
    offset = [p-f for p, f in zip(initial['position'], initial['focal'])]
    return dict(initial, position=[f+d for f, d in zip(initial['focal'], rotate(offset, axis, degrees))],
                up=rotate(initial['up'], axis, degrees))


def apply_camera(view, pose):
    view.CameraPosition = pose['position']
    view.CameraFocalPoint = pose['focal']
    view.CameraViewUp = pose['up']
    view.CameraViewAngle = pose['angle']
    view.CameraParallelScale = pose['parallel_scale']


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def unit(vector):
    length = math.hypot(*vector)
    return [x/length for x in vector]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def moving_camera(a):
    return bool(a.orbit_degrees or a.orbit2_degrees or a.fly_through)


def orbital_pose(a, initial, progress):
    first = orbit_pose(initial, a.orbit_axis, a.orbit_degrees*progress)
    return orbit_pose(first, a.orbit2_axis, a.orbit2_degrees*progress)


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x*x*x*(10 + x*(-15 + 6*x))


def path_pose(a, initial, seconds, target=None):
    from .timing import duration, displacement
    pose = orbital_pose(a, initial, seconds/duration(a))
    if not a.fly_through:
        return pose
    center = a.fly_through_at
    span = a.fly_through_duration
    u = (seconds - (center-span/2)) / span
    if u <= 0:
        return pose
    offset = [p-f for p, f in zip(pose['position'], pose['focal'])]
    if u >= 1:
        return dict(pose, position=[f-d for f, d in zip(pose['focal'], offset)])
    # Cross the center of a real mesh cell, following its modal displacement.
    beam = [p + displacement(a, seconds)*d for p, d in zip(target['point'], target['disp'])]
    blend = math.sin(math.pi*u)**2
    pivot = [f + blend*(p-f) for p, f in zip(beam, pose['focal'])]
    signed_radius = 1 - 2*smoothstep(u)
    position = [p + signed_radius*d for p, d in zip(pivot, offset)]
    # Keep looking forward through the crossing; turn back toward the beam on exit.
    turn = 180 * smoothstep((u-0.5)/0.3)
    forward = rotate([-d for d in unit(offset)], pose['up'], turn)
    focal = [p + math.hypot(*offset)*d for p, d in zip(position, forward)]
    return dict(pose, position=position, focal=focal)


def fitted_extents(a, initial, bounds, angle):
    """Fit every projected envelope into the frame, leaving room for the legend."""
    import itertools
    pivot = [(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)]
    corners = [[v-c for v, c in zip(point, pivot)]
               for point in itertools.product(*[(bounds[2*i], bounds[2*i+1]) for i in range(3)])]
    samples = min(4096, max(64, math.ceil((abs(a.orbit_degrees)+abs(a.orbit2_degrees))/3))) if moving_camera(a) else 1
    vertical = math.tan(math.radians(angle/2))
    aspect = a.width/a.height
    distance, scale = 0.0, 0.0
    for i in range(samples+1):
        pose = orbital_pose(a, initial, i/samples)
        normal = unit([p-f for p, f in zip(pose['position'], pose['focal'])])
        for sign in ((1, -1) if a.fly_through else (1,)):
            n = [v*sign for v in normal]
            right = unit(cross(pose['up'], n))
            up = unit(cross(n, right))
            for point in corners:
                x, y, z = dot(point, right), dot(point, up), dot(point, n)
                # Bottom 21% is reserved for the color legend; 4% side margin.
                extent = max(abs(x)/(aspect*0.92), y/0.90 if y >= 0 else -y/0.58)
                scale = max(scale, extent)
                distance = max(distance, z + extent/vertical)
    return distance*1.02, scale*1.02


def configure_camera(a, view, bounds):
    camera = view.GetActiveCamera()
    camera.Azimuth(a.azimuth)
    camera.Elevation(a.elevation)
    camera.OrthogonalizeViewUp()
    camera.Roll(a.roll)
    if a.fly_through:
        view.CameraParallelProjection = 0
    if not a.state_camera:
        initial = dict(position=list(camera.GetPosition()), focal=list(camera.GetFocalPoint()),
                       up=list(camera.GetViewUp()))
        distance, scale = fitted_extents(a, initial, bounds, camera.GetViewAngle())
        normal = unit([p-f for p, f in zip(initial['position'], initial['focal'])])
        focal = [(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)]
        camera.SetFocalPoint(focal)
        camera.SetPosition([f+distance*d for f, d in zip(focal, normal)])
        camera.SetParallelScale(scale)
    camera.Zoom(a.zoom)
    pose = dict(position=list(camera.GetPosition()), focal=list(camera.GetFocalPoint()),
                up=list(camera.GetViewUp()), angle=camera.GetViewAngle(),
                parallel_scale=camera.GetParallelScale())
    apply_camera(view, pose)
    return pose


def add_orbit_track(a, pv, view, initial, count, target=None):
    from .timing import frame_time
    # Animate the three camera vectors directly. ParaView 6.1's camera
    # interpolator can produce an undefined position at the first keyframe.
    poses = [path_pose(a, initial, frame_time(a, i), target) for i in range(count)]
    for property_name, field in [('CameraPosition', 'position'),
                                 ('CameraFocalPoint', 'focal'), ('CameraViewUp', 'up')]:
        cue = pv.GetAnimationTrack(property_name, index=-1, proxy=view)
        keys = []
        for i, pose in enumerate(poses):
            key = pv.CompositeKeyFrame()
            key.KeyTime = i/(count-1)
            key.KeyValues = pose[field]
            key.Interpolation = 'Ramp'
            pv.servermanager.ProxyManager().RegisterProxy('animation', 'Beam%sKey%d' % (property_name, i), key)
            keys.append(key)
        cue.KeyFrames = keys
