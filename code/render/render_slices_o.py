# pvbatch (ParaView 6.0.1, EGL offscreen): render mesh slices as raw images with exact, known view extents.
# Axes, labels and side-by-side layout are added afterwards with matplotlib (compose_figs.py).
import sys, json
from paraview.simple import *
cases = {'ogrid': sys.argv[1]}
out = sys.argv[2]
VIEWS = {   # name: (slice normal, origin, extents (u0,u1,v0,v1) in D, pixels width)
    'xy_full':   ('z', 2.03, (-4.5, 15.0, -7.0, 7.0), 3600),
    'xy_near':   ('z', 2.03, (-1.5, 3.0, -1.5, 1.5), 3000),
    'xy_corner': ('z', 2.03, (-0.62, -0.32, 0.42, 0.72), 2400),
    'xy_wake':   ('z', 2.03, (0.3, 3.8, -1.2, 1.2), 3000),
    'yz_span':   ('x', 1.003, (-1.2, 1.2, 0.0, 4.0), 2400),   # u = y, v = z
}
meta = {}
for cname, cpath in cases.items():
    r = OpenFOAMReader(FileName=cpath + '/system/controlDict')
    r.CaseType = 'Reconstructed Case'; r.MeshRegions = ['internalMesh']; r.CellArrays = []
    r.UpdatePipeline()
    for vname, (nrm, org, ext, wpx) in VIEWS.items():
        s = Slice(Input=r); s.SliceType = 'Plane'; s.Triangulatetheslice = 0
        s.SliceType.Normal = [0, 0, 1] if nrm == 'z' else [1, 0, 0]
        s.SliceType.Origin = [0, 0, org] if nrm == 'z' else [org, 0, 0]
        v = CreateView('RenderView'); v.OrientationAxesVisibility = 0; v.Background = [1, 1, 1]
        try: v.UseColorPaletteForBackground = 0
        except Exception: pass
        d = Show(s, v); d.SetRepresentationType('Surface With Edges'); d.ColorArrayName = ['POINTS', '']
        d.AmbientColor = [0.93, 0.93, 0.93]; d.DiffuseColor = [0.93, 0.93, 0.93]; d.EdgeColor = [0.0, 0.0, 0.0]
        d.LineWidth = 1.0
        u0, u1, v0, v1 = ext; hpx = int(round(wpx * (v1 - v0) / (u1 - u0)))
        v.ViewSize = [wpx, hpx]; v.CameraParallelProjection = 1
        Render(v)   # first render resets the camera; set the camera afterwards
        cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
        if nrm == 'z':
            v.CameraFocalPoint = [cu, cv, org]; v.CameraPosition = [cu, cv, org + 50]; v.CameraViewUp = [0, 1, 0]
        else:   # look along -x: screen right = +y? use position at x+50 looking -x, up = z -> screen right = -y; flip by looking from -x
            v.CameraFocalPoint = [org, cu, cv]; v.CameraPosition = [org - 50, cu, cv]; v.CameraViewUp = [0, 0, 1]
        v.CameraParallelScale = (v1 - v0) / 2
        Render(v)
        fn = f'{out}/{cname}_{vname}.png'; SaveScreenshot(fn, v, ImageResolution=[wpx, hpx])
        meta[f'{cname}_{vname}'] = {'extent': ext, 'px': [wpx, hpx], 'normal': nrm, 'origin': org}
        Delete(d); Delete(s); Delete(v)
json.dump(meta, open(f'{out}/render_meta.json', 'w'), indent=1)
print('RENDER_OK', len(meta))
