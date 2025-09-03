from afem.graphics import Viewer
import afem.topology as atop
import afem.geometry as ageom
from OCC.Display.SimpleGui import init_display


sphere = atop.SphereByRadius().solid
rect = ageom.NurbsSurfaceByInterp([
    ageom.NurbsCurveByPoints([
        ageom.Point.by_xyz(0, 0, 0),
        ageom.Point.by_xyz(3, 0, 0)
    ]).curve,
    ageom.NurbsCurveByPoints([
        ageom.Point.by_xyz(0, 3, 0),
        ageom.Point.by_xyz(3, 3, 0)
    ]).curve,
]).surface


v, start, add_menu, add_fcn = init_display(backend_str='wx')
v.DisplayShape(sphere.object)
v.DisplayShape(rect.object)
start()

debug = True
