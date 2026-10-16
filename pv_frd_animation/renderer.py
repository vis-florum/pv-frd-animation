"""ParaView-only scene setup and frame rendering."""
import json
from pathlib import Path

from .camera import configure_camera, add_orbit_track, apply_camera, path_pose, moving_camera
from .timing import duration, frame_count, frame_time, displacement
from .geometry import fly_through_target
from .frames import assigned_frames, finalize_frames

def setup_scene(a):
    import paraview.simple as pv
    import xml.etree.ElementTree as ET

    for filename in (a.state, a.data):
        if not Path(filename).is_file():
            raise FileNotFoundError(filename)
    # Find the reader in the supplied state, so moving the input file is safe.
    root = ET.parse(a.state).getroot()
    readers = root.findall(".//Proxy[@type='XMLUnstructuredGridReader']")
    if len(readers) != 1:
        raise RuntimeError('Expected one VTU reader in the state file')
    reader_id = readers[0].get('id')
    reader_name = next(item.get('name') for item in root.findall(".//ProxyCollection[@name='sources']/Item") if item.get('id') == reader_id)
    pv.LoadState(a.state, filenames=[{'id': reader_id, 'name': reader_name, 'FileName': a.data}])
    sources = list(pv.GetSources().values())
    reader = next(s for s in sources if s.SMProxy.GetXMLName() == 'XMLUnstructuredGridReader')
    warp = next((s for s in sources if s.SMProxy.GetXMLName() == 'WarpVector' and s.Input == reader), None)
    if warp is None:
        warp = pv.WarpByVector(registrationName='Animated beam', Input=reader)
    reader.UpdatePipeline()
    if 'disp' not in reader.PointData.keys():
        raise RuntimeError('The input has no point-vector array named disp')
    warp.Vectors = ['POINTS', 'disp']
    warp.UpdatePipeline()
    view = pv.GetActiveViewOrCreate('RenderView')
    pv.SetActiveView(view)
    # Hide loaded representations and scalar bars, then show just these two.
    for rep in view.Representations:
        if hasattr(rep, 'Visibility'):
            rep.Visibility = 0
    outline = pv.Show(reader, view)
    outline.Representation = 'Outline'
    pv.ColorBy(outline, None)
    outline.DiffuseColor = [1, 1, 1]
    outline.AmbientColor = [1, 1, 1]
    outline.LineWidth = 1.5
    display = pv.Show(warp, view)
    display.Representation = 'Surface'
    pv.ColorBy(display, ('POINTS', 'disp', 'Magnitude'))
    lut = pv.GetColorTransferFunction('disp')
    lut.VectorMode = 'Magnitude'
    maximum = reader.PointData['disp'].GetRange(-1)[1]
    lut.RescaleTransferFunction(0.0, maximum)
    lut.AutomaticRescaleRangeMode = 'Never'
    display.SetScalarBarVisibility(view, True)
    bar = pv.GetScalarBar(lut, view)
    bar.Title = 'Displacement magnitude'
    bar.ComponentTitle = ''
    bar.Orientation = 'Horizontal'
    bar.WindowLocation = 'Any Location'
    bar.Position = [0.26, 0.07]
    bar.ScalarBarLength = 0.48
    bar.TitleFontSize = 16
    bar.LabelFontSize = 14
    number_format = '{:.3g}' if pv.GetParaViewVersion() >= (6, 1) else '%.3g'
    bar.RangeLabelFormat = number_format
    bar.LabelFormat = number_format
    bar.AutomaticLabelFormat = 0
    view.ViewSize = [a.width, a.height]
    # Preserve the loaded viewing direction; fit both signs and the original.
    bounds = [reader.GetDataInformation().GetBounds()]
    for scale in (-a.amplitude, a.amplitude):
        warp.ScaleFactor = scale
        warp.UpdatePipeline()
        bounds.append(warp.GetDataInformation().GetBounds())
    union = [min(b[i] for b in bounds) if i % 2 == 0 else max(b[i] for b in bounds) for i in range(6)]
    initial_camera = configure_camera(a, view, union)
    warp.ScaleFactor = 0
    warp.UpdatePipeline()

    # The saved state also plays the animation inside the ParaView GUI.
    scene = pv.GetAnimationScene()
    # Replace any camera motion carried by an input animated state.
    for old_cue in list(scene.Cues):
        if old_cue.SMProxy.GetXMLName() == 'CameraAnimationCue' or getattr(old_cue, 'AnimatedProxy', None) == view:
            scene.Cues.remove(old_cue)
    scene.PlayMode = 'Sequence'
    scene.StartTime = 0
    scene.EndTime = duration(a)
    scene.NumberOfFrames = frame_count(a)
    cue = pv.GetAnimationTrack('ScaleFactor', proxy=warp)
    keys = []
    for quarter in range(4 * a.cycles + 1):
        key = pv.CompositeKeyFrame()
        key.KeyTime = quarter / (4 * a.cycles)
        key.KeyValues = [a.amplitude * (0, 1, 0, -1)[quarter % 4]]
        key.Interpolation = 'Ramp'
        # Explicit registration is needed for these keyframes to survive SaveState.
        pv.servermanager.ProxyManager().RegisterProxy('animation', 'BeamKeyFrame%d' % quarter, key)
        keys.append(key)
    cue.KeyFrames = keys
    target = fly_through_target(pv, reader) if a.fly_through else None
    if moving_camera(a):
        add_orbit_track(a, pv, view, initial_camera, scene.NumberOfFrames, target)
    scene.AnimationTime = 0
    apply_camera(view, initial_camera)
    pv.SetActiveSource(warp)
    return pv, view, warp, maximum, initial_camera, target


def render(a, worker_index=0, worker_count=1):
    pv, view, warp, maximum, initial_camera, flight_target = setup_scene(a)
    out = Path(a.output)
    if worker_index == 0:
        pv.SaveState(str(out / 'beam_animation.pvsm'))
        warp.ScaleFactor = a.amplitude
        pv.SaveScreenshot(str(out / 'preview.png'), view, ImageResolution=[a.width, a.height])
    if a.preview_only:
        return
    frames = out / 'frames'
    frames.mkdir(exist_ok=True)
    count = frame_count(a)
    for index in assigned_frames(a, worker_index, worker_count):
        seconds = frame_time(a, index)
        scale = displacement(a, seconds)
        image = frames / ('pose_%05d.png' % index)
        if moving_camera(a):
            apply_camera(view, path_pose(a, initial_camera, seconds, flight_target))
        warp.ScaleFactor = scale
        warp.UpdatePipeline()
        pv.SaveScreenshot(str(image), view, ImageResolution=[a.width, a.height])
        print('Worker %d: rendered frame %d/%d, time %.3fs, displacement scale %.4f' % (worker_index+1, index+1, count, seconds, warp.ScaleFactor), flush=True)
    metadata = dict(vars(a), frame_count=count, displacement_magnitude_max=maximum,
                    peak_geometric_displacement=a.amplitude * maximum,
                    color='original modal |disp|, fixed range', motion='symmetric triangular cycle',
                    initial_camera=initial_camera, nominal_duration_seconds=duration(a),
                    fly_through_target=flight_target, render_workers=worker_count)
    if worker_index == 0:
        if worker_count == 1:
            finalize_frames(a, metadata)
        else:
            (out / '.render-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    warp.ScaleFactor = 0
    warp.UpdatePipeline()
    apply_camera(view, initial_camera)
    print('Worker %d complete.' % (worker_index+1), flush=True)
