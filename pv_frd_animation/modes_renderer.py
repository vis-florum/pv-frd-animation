"""PVD mode sweep preserving the supplied ParaView scene and its presentation."""
import json
import math
from pathlib import Path

from .frames import assigned_frames, finalize_frames
from .modes_config import state_reader
from .modes_timing import frame_count, samples_per_mode, sample, content_size


def camera_settings(view):
    return {name:list(getattr(view,name)) if name in ('CameraPosition','CameraFocalPoint','CameraViewUp','ViewSize') else getattr(view,name)
            for name in ('CameraPosition','CameraFocalPoint','CameraViewUp','CameraViewAngle',
                         'CameraParallelScale','CameraParallelProjection','ViewSize')}


def build_tracks(pv,a,view,warp):
    scene = pv.GetAnimationScene()
    scene.Cues = []
    total = frame_count(a)
    per_mode = samples_per_mode(a)
    scene.PlayMode = 'Sequence'
    scene.StartTime = 0
    scene.EndTime = (total-1)/a.fps
    scene.NumberOfFrames = total
    manager = pv.servermanager.ProxyManager()
    time_keys,warp_keys = [],[]
    for mode_index,mode in enumerate(a.mode_times):
        start = mode_index*per_mode
        key = pv.CompositeKeyFrame()
        key.KeyTime = start/(total-1)
        key.KeyValues = [mode]
        key.Interpolation = 'Boolean'
        manager.RegisterProxy('animation','SweepTime%d'%mode_index,key)
        time_keys.append(key)
        for quarter in range(5):
            index = start+round(quarter*(per_mode-1)/4)
            key = pv.CompositeKeyFrame()
            key.KeyTime = index/(total-1)
            key.KeyValues = [sample(a,index)[1]]
            key.Interpolation = 'Ramp'
            manager.RegisterProxy('animation','SweepWarp%d_%d'%(mode_index,quarter),key)
            warp_keys.append(key)
    end = pv.CompositeKeyFrame()
    end.KeyTime = 1
    end.KeyValues = [a.mode_times[-1]]
    end.Interpolation = 'Boolean'
    manager.RegisterProxy('animation','SweepTimeEnd',end)
    time_keys.append(end)
    pv.GetAnimationTrack('Time',index=0,proxy=pv.GetTimeKeeper()).KeyFrames = time_keys
    pv.GetAnimationTrack('ScaleFactor',index=0,proxy=warp).KeyFrames = warp_keys
    scene.AnimationTime = 0


def setup_scene(a):
    import paraview.simple as pv
    pv._DisableFirstRenderCameraReset()
    reader_id,reader_name,_ = state_reader(a.state)
    pv.LoadState(a.state,filenames=[dict(id=reader_id,name=reader_name,FileName=a.data)])
    sources = list(pv.GetSources().values())
    reader = next(source for source in sources if source.SMProxy.GetXMLName() == 'PVDReader')
    warps = [source for source in sources if source.SMProxy.GetXMLName() == 'WarpVector' and source.Input == reader]
    if len(warps) != 1:
        raise RuntimeError('Expected exactly one displacement warp attached to the PVD reader')
    warp = warps[0]
    views = [view for view in pv.GetViews() if view.SMProxy.GetXMLName() == 'RenderView']
    if len(views) != 1:
        raise RuntimeError('Mode sweep currently expects one RenderView in the state')
    view = views[0]
    initial = camera_settings(view)
    annotations = [source for source in sources if source.SMProxy.GetXMLName() in ('AnnotateAttributeData','PythonAnnotation')]
    # Retain all representations, LUTs, camera values, and annotation properties.
    build_tracks(pv,a,view,warp)
    return pv,reader,warp,view,annotations,initial


def set_frame(pv,reader,warp,view,annotations,mode,scale):
    pv.GetTimeKeeper().Time = mode
    view.ViewTime = mode
    reader.UpdatePipeline(mode)
    warp.ScaleFactor = scale
    warp.UpdatePipeline(mode)
    for annotation in annotations:
        annotation.UpdatePipeline(mode)


def screenshot(pv,view,path,a):
    """Scale the saved composition proportionally and letterbox it to Full HD."""
    size = content_size(list(view.ViewSize),[a.width,a.height])
    from vtkmodules.vtkIOImage import vtkPNGReader,vtkPNGWriter
    from vtkmodules.vtkImagingCore import vtkImageConstantPad,vtkImageResize
    native = list(view.ViewSize)
    # Integer magnification avoids ParaView rounding the text scaling when
    # the requested resolution is a noninteger multiple of the saved viewport.
    magnification = max(1,math.ceil(max(size[i]/native[i] for i in range(2))))
    capture = [value*magnification for value in native]
    raw = path.with_name('.'+path.stem+'.capture.png')
    try:
        pv.SaveScreenshot(str(raw),view,ImageResolution=capture,FontScaling='Scale fonts proportionally')
        image = vtkPNGReader()
        image.SetFileName(str(raw))
        image.Update()
        resize = vtkImageResize()
        resize.SetInputConnection(image.GetOutputPort())
        resize.SetOutputDimensions(size[0],size[1],1)
        resize.InterpolateOn()
        width,height = size
        left,bottom = (a.width-width)//2,(a.height-height)//2
        pad = vtkImageConstantPad()
        pad.SetInputConnection(resize.GetOutputPort())
        pad.SetOutputWholeExtent(-left,a.width-left-1,-bottom,a.height-bottom-1,0,0)
        pad.SetConstant(0)
        writer = vtkPNGWriter()
        writer.SetInputConnection(pad.GetOutputPort())
        writer.SetFileName(str(path))
        writer.SetCompressionLevel(5)
        writer.Write()
        if writer.GetErrorCode():
            raise RuntimeError('Could not write letterboxed screenshot: '+str(path))
    finally:
        raw.unlink(missing_ok=True)


def render(a,worker_index=0,worker_count=1):
    pv,reader,warp,view,annotations,initial = setup_scene(a)
    out = Path(a.output)
    first = a.mode_times[0]
    set_frame(pv,reader,warp,view,annotations,first,0)
    if worker_index == 0:
        pv.SaveState(str(out/'allmodes.pvsm'))
        set_frame(pv,reader,warp,view,annotations,first,a.amplitude)
        screenshot(pv,view,out/'preview.png',a)
    if a.preview_only:
        return
    frames = out/'frames'
    frames.mkdir(exist_ok=True)
    count = frame_count(a)
    frequencies = {}
    previous_mode = None
    for index in assigned_frames(a,worker_index,worker_count):
        mode,scale = sample(a,index)
        set_frame(pv,reader,warp,view,annotations,mode,scale)
        if mode != previous_mode:
            if 'frequency_hz' in reader.FieldData.keys():
                frequencies[str(mode)] = reader.FieldData['frequency_hz'].GetRange()[0]
            previous_mode = mode
        screenshot(pv,view,frames/('pose_%05d.png'%index),a)
        print('Worker %d: PVD time %g, frame %d/%d, warp %+.5f' %
              (worker_index+1,mode,index+1,count,scale),flush=True)
    metadata = dict(vars(a),frame_count=count,render_workers=worker_count,
                    samples_per_mode=samples_per_mode(a),duration_seconds=count/a.fps,
                    effective_seconds_per_cycle=samples_per_mode(a)/a.fps,
                    saved_camera=initial,content_resolution=content_size(initial['ViewSize'],[a.width,a.height]),
                    letterboxed=content_size(initial['ViewSize'],[a.width,a.height]) != [a.width,a.height],
                    observed_frequencies_hz=frequencies,
                    motion='one closed triangular +/- amplitude cycle per PVD time; fixed state camera')
    if camera_settings(view) != initial:
        raise RuntimeError('The saved camera or viewport changed while rendering the mode sweep')
    if worker_index == 0:
        if worker_count == 1:
            finalize_frames(a,metadata)
        else:
            (out/'.render-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    set_frame(pv,reader,warp,view,annotations,first,0)
    print('Worker %d complete.'%(worker_index+1),flush=True)
