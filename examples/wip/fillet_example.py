from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCC.Display.SimpleGui import init_display
import afem.geometry as ageom
import afem.topology as atop


v, start, add_menu, add_fcn = init_display(backend_str='wx')
### =========================================================== ###
### Create box wing
### =========================================================== ###

box_wing = atop.BoxBy2Points(ageom.Point.by_xyz(-3, -0.5, 0), ageom.Point.by_xyz(3, 0.5, 10)).solid


### =========================================================== ###
### Create wall
### =========================================================== ###

wall_solid = atop.BoxBy2Points(ageom.PointByXYZ(10, 10, 0).point, ageom.PointByXYZ(-10, -10, -0.2).point).solid


### =========================================================== ###
### Fillet creation
### =========================================================== ###

cut_wall = atop.CutShapes(wall_solid, box_wing).shape
fillet_edges = cut_wall.shared_edges(box_wing)

merged = atop.FuseShapes(cut_wall, box_wing).shape

fillet = BRepFilletAPI_MakeFillet(merged._shape)
for edge in fillet_edges:
    fillet.Add(1, edge._shape)
fillet.Build()
print(fillet.IsDone())


### =========================================================== ###
### Extract faces and create mesh
### =========================================================== ###

geom = atop.Shape(fillet.Shape()).faces
geom = atop.CompoundByShapes(geom[:10]).compound

v.DisplayShape(geom.displayed_shape)

start()