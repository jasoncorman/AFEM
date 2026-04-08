from OCC.Core.STEPControl import STEPControl_Writer
from OCC.Core.gp import gp_Pnt

from afem.config import Settings
from math import tan, radians
from afem.oml import Body
from afem.sketch import *
from afem.geometry import *
from afem.structure import *
from afem.topology import *
from OCC.Display.SimpleGui import init_display
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs

# Crude Mesh Visualizer
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex

# Bounding box generation
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib

v, start, add_menu, add_fcn = init_display(backend_str='wx')

Settings.log_to_console()

# Set units to inch.
Settings.set_units('in')

# Parameters
semispan = 107.  # wing semi-span
sweep = 34.  # Leading edge sweep
uk = 0.28  # Percent semi-span to locate section cross-section
c1 = 51.5  # Root chord
c2 = 31.  # Chord of second section
c3 = 7.  # Tip chord
t3 = 3.  # Tip washout in degrees

# Define leading edge points of cross-sections
p1x, p1y = 0., 0.
p2x = semispan * uk * tan(radians(sweep))
p2y = semispan * uk
p3x = semispan * tan(radians(sweep))
p3y = semispan

# Create a cross-section using an UIUC airfoil file
cs = Airfoil()
cs.read_uiuc('clarky.txt')

# Define cross section planes
pln1 = PlaneByAxes((p1x, p1y, 0), axes='xz').plane
pln2 = PlaneByAxes((p2x, p2y, 0), axes='xz').plane
pln3 = PlaneByAxes((p3x, p3y, 0), axes='xz').plane

# Build cross sections
cs.build(pln1, scale=c1)
wire1 = cs.wires[0]
cs.build(pln2, scale=c2)
wire2 = cs.wires[0]
cs.build(pln3, scale=c3, rotate=t3)
wire3 = cs.wires[0]

# Loft a solid
shape = LoftShape([wire1, wire2, wire3], True, make_ruled=True).shape

# Make a body
wing = Body(shape, 'Wing')
wing.set_transparency(0.5)
wing.set_color(1, 0, 0)

# to be between 0 and 1 for convenience.
chord1 = cs.build_chord(pln1, scale=c1)
chord2 = cs.build_chord(pln2, scale=c2)
chord3 = cs.build_chord(pln3, scale=c3, rotate=t3)
sref = NurbsSurfaceByInterp([chord1, chord2, chord3], 1).surface
sref.set_udomain(0., 1.)
sref.set_vdomain(0., 1.)

# Set the wing reference surface
wing.set_sref(sref)


# Define a group to put the structure in
wingbox = GroupAPI.create_group('wing box')
spars_assy = wingbox.create_subgroup('spar assy', active=False)
ribs_assy = wingbox.create_subgroup('rib assy', active=False)
# skin_assy = wingbox.create_subgroup('skin assy', active=False)
# Activate spar assembly
spars_assy.activate()

# Define a front spar between parameters on the wing reference surface
fspar = SparByParameters('fspar', 0.15, 0.2, 0.15, 0.98, wing).part
# Define a rear spar between parameters on the wing reference surface
rspar = SparByParameters('rspar', 0.7, 0.2, 0.7, 0.98, wing).part

# Activate rib assembly
ribs_assy.activate()

# Define root rib between front and rear spar
root = RibByPoints('root', fspar.cref.p1, rspar.cref.p1, wing).part

# Define tip rib between front and rear spar
tip = RibByPoints('tip', fspar.cref.p2, rspar.cref.p2, wing).part

# Add ribs between root and tip perpendicular to rear spar reference curve
ribs = RibsAlongCurveByDistance('rib', rspar.cref, 10., fspar, rspar, wing,
                                d1=10., d2=-10.).parts

# Activate spar assembly
spars_assy.activate()

# Add a front center spar considering the intersection between the front
# spar and the root rib. If this is not considered, the front center spar
# may be oriented in such a way that causes it to have a gap with the front

# spar and root rib.
p1 = wing.sref.eval(0.3, .0)
pln = PlaneByIntersectingShapes(fspar.shape, root.shape, p1).plane
fcspar = SparByPoints('fcspar', p1, root.cref.p1, wing, pln).part

# Add rear center spar
p1 = wing.sref.eval(0.75, .0)
pln = PlaneByIntersectingShapes(rspar.shape, root.shape, p1).plane
rcspar = SparByPoints('rcspar', p1, root.cref.p2, wing, pln).part

# Activate rib assembly
ribs_assy.activate()

# Add center ribs using a reference plane alonge the rear center spar
ref_pln = PlaneByAxes(origin=(0., 0., 0.), axes='xz').plane
ribs2 = RibsAlongCurveByNumber('center rib', rcspar.cref, 3, fcspar, rcspar,
                              wing, ref_pln, d1=6, d2=-5).parts

super_root = RibByPoints('sroot', fcspar.cref.p1, rcspar.cref.p1, wing).part
# Join the internal structure using their reference curves to check for
# actual intersection
internal_parts = wingbox.get_parts()


FuseSurfacePartsByCref(parts=internal_parts)



# Discard faces of parts using the reference curve
DiscardByCref(internal_parts)

# # Display final result
# for part in wingbox.get_parts():
#     v.DisplayShape(part.displayed_shape)
# # v.DisplayShape(skin.displayed_shape)
# start()

# Activate wingbox assembly
wingbox.activate()




# Extract the shell of wing to define the wing skin
skin = SkinByBody('skin', wing).part
skin.set_transparency(0.5)



# Join the wing skin with the internal structure
skin.fuse(*internal_parts)



# Discard wing skin that is touching the wing reference surface. This
# should leave only the upper and lower skins.
print(skin.shape.shape_type)
skin.discard_by_dmin(wing.sref, 0.1)




# After removing the faces, the skin is now a compound of two shells, one
# upper shell and one lower. Use the Part.fix() to alter the shape from an
# invalid shell to a compound of two shells.
print('Skin shape type before fix:', skin.shape.shape_type)
skin.fix()
print('Skin shape type after fix:', skin.shape.shape_type)

wingbox.activate()

# Check for free edges
shape = GroupAPI.get_shape()
tool = ExploreFreeEdges(shape)

# Step 1: Get the final wingbox group
wingbox_shape = GroupAPI.get_shape()

# Step 2: Export the wingbox shape to STEP
export_file = False
if export_file:
    step_writer = STEPControl_Writer()
    step_writer.Transfer(wingbox_shape.displayed_shape, STEPControl_AsIs)
    step_writer.Write('wingbox.step')

# Step 3: Create physical groups for analysis (e.g., root rib nodes)
spar_parts = spars_assy.parts
rib_parts = ribs_assy.parts
skin_parts = wingbox.parts

all_parts = skin_parts + rib_parts + spar_parts
part_metadata = {}
store_individual_components = False
for a_part in all_parts:
    bbox = Bnd_Box()
    brepbndlib.Add(a_part.shape.displayed_shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    part_name = a_part.name
    part_metadata[part_name] = {}
    a_shape = a_part.displayed_shape
    print("Bounding box for "+part_name)
    print(str(xmin)+'in '+str(ymin)+'in '+str(zmin)+'in '+str(xmax)+'in '+str(ymax)+'in '+str(zmax)+'in ')
    # OPTIONAL it is possible to export the individual parts and join them through boolean operations in GMSH
    if store_individual_components:
        part_step_writer = STEPControl_Writer()
        part_step_writer.Transfer(a_shape, STEPControl_AsIs)
        part_step = a_part.name + '.step'
        part_metadata[part_name]['step_filename'] = part_step
        part_step_writer.Write(part_step)
    part_id = a_part.id
    part_metadata[part_name]['id'] = part_id
    part_metadata[part_name]['name'] = a_part.name
    part_metadata[part_name]['bbox'] = (xmin, ymin, zmin, xmax, ymax, zmax)


for part in wingbox.get_parts():
    v.DisplayShape(part.displayed_shape, transparency=0.25)
v.DisplayShape(skin.displayed_shape, transparency=0.25)
start()
