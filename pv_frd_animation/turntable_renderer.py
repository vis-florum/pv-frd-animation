"""Rotate saved render views without rebuilding or recoloring their scene."""
import json
from pathlib import Path

from .camera import apply_camera, camera_pose
from .frames import assigned_frames, finalize_frames
from .modes_renderer import camera_settings, screenshot
from .turntable_timing import frame_count, intervals_per_orbit, pose, fitted_pose


def render(a, worker_index=0, worker_count=1):
    import paraview.simple as pv
    pv._DisableFirstRenderCameraReset()
    pv.LoadState(a.state)
    views = [view for view in pv.GetViews() if view.SMProxy.GetXMLName() == 'RenderView']
    if len(views) != 1:
        raise RuntimeError('Turntable currently expects exactly one RenderView in the state')
    view = views[0]
    if a.volume_renderer != 'state':
        for representation in view.Representations:
            if representation.GetProperty('VolumeRenderingMode') is not None:
                representation.VolumeRenderingMode = 'Ray Cast Only' if a.volume_renderer == 'cpu' else 'GPU Based'
    saved = camera_settings(view)
    # Keep the saved data time and all representations, transfer functions,
    # legends, annotations, lights, and projection. Only move the camera.
    pv.GetAnimationScene().Cues = []
    visible_bounds = None
    if a.framing == 'fit':
        pv.Render(view)
        visible_bounds = list(view.GetClientSideObject().GetRenderer().ComputeVisiblePropBounds())
        apply_camera(view, fitted_pose(camera_pose(view), visible_bounds, view.ViewSize[0]/view.ViewSize[1]))
    view.GetActiveCamera().Zoom(a.zoom)
    initial = camera_pose(view)
    out = Path(a.output)

    def set_pose(index):
        apply_camera(view, pose(a, initial, index))

    set_pose(0)
    if worker_index == 0:
        pv.SaveState(str(out/'turntable.pvsm'))
        screenshot(pv, view, out/'preview.png', a)
    if a.preview_only:
        return
    frames = out/'frames'
    frames.mkdir(exist_ok=True)
    count = frame_count(a)
    for index in assigned_frames(a, worker_index, worker_count):
        set_pose(index)
        screenshot(pv, view, frames/('pose_%05d.png'%index), a)
        print('Worker %d: frame %d/%d'%(worker_index+1,index+1,count), flush=True)
    if worker_index == 0:
        metadata = dict(vars(a), frame_count=count, saved_camera=saved,
                        initial_camera=initial, visible_bounds=visible_bounds, intervals_per_orbit=intervals_per_orbit(a),
                        effective_seconds_per_orbit=intervals_per_orbit(a)/a.fps,
                        motion='360 degrees around world Y, then 360 degrees around world Z')
        if worker_count == 1:
            finalize_frames(a, metadata)
        else:
            (out/'.render-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Worker %d complete.'%(worker_index+1), flush=True)
