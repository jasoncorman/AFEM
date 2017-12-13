#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017 Laughlin Research, L.L.C.
#
# This file is subject to the license agreement that was delivered
# with this source code.
#
# THE SOFTWARE AND INFORMATION ARE PROVIDED ON AN "AS IS" BASIS,
# WITHOUT ANY WARRANTIES OR REPRESENTATIONS EXPRESS, IMPLIED OR
# STATUTORY; INCLUDING, WITHOUT LIMITATION, WARRANTIES OF QUALITY,
# PERFORMANCE, MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.

import json

from OCCT.BRep import BRep_Builder, BRep_Tool
from OCCT.BRepBuilderAPI import (BRepBuilderAPI_MakeFace,
                                 BRepBuilderAPI_MakeWire, BRepBuilderAPI_Sewing)
from OCCT.BRepCheck import BRepCheck_Analyzer
from OCCT.BRepGProp import BRepGProp
from OCCT.GProp import GProp_GProps
from OCCT.Geom import Geom_Plane
from OCCT.GeomLib import GeomLib_IsPlanarSurface
from OCCT.IFSelect import (IFSelect_ItemsByEntity, IFSelect_RetDone,
                           IFSelect_RetVoid)
from OCCT.Interface import Interface_Static
from OCCT.STEPControl import STEPControl_Reader
from OCCT.ShapeAnalysis import ShapeAnalysis
from OCCT.ShapeFix import ShapeFix_Solid, ShapeFix_Wire
from OCCT.ShapeUpgrade import (ShapeUpgrade_ShapeDivideClosed,
                               ShapeUpgrade_SplitSurface,
                               ShapeUpgrade_UnifySameDomain)
from OCCT.TColStd import TColStd_HSequenceOfReal
from OCCT.TopAbs import TopAbs_COMPOUND, TopAbs_FACE
from OCCT.TopExp import TopExp_Explorer
from OCCT.TopoDS import TopoDS_Compound, TopoDS_Iterator, TopoDS_Shell

from afem.config import Settings, logger
from afem.geometry.create import NurbsSurfaceByInterp, NurbsCurveByPoints
from afem.geometry.entities import NurbsSurface
from afem.oml.entities import Body
from afem.topology.check import CheckShape
from afem.topology.create import CompoundByShapes, FaceBySurface
from afem.topology.explore import ExploreShape
from afem.topology.props import LinearProps

__all__ = ["ImportVSP"]


class ImportVSP(object):
    """
    Automated import an OpenVSP file.
    """
    _bodies = {}

    @classmethod
    def clear(cls):
        """
        Clear imported data.

        :return: None.
        """
        cls._bodies.clear()
        return True

    @classmethod
    def get_body(cls, name):
        """
        Return OML body by name.

        :param str name: Body name.

        :return: OML body.
        :rtype: afem.oml.entities.Body
        """
        return cls._bodies[name]

    @classmethod
    def get_bodies(cls):
        """
        Return all bodies in a dictionary. They key will be the body name.

        :return: The dictionary of bodies.
        :rtype: dict
        """
        return cls._bodies

    @classmethod
    def step_file(cls, fn, divide_closed=True):
        """
        Import a STEP file generated by the OpenVSP version that has been
        modified to include metadata.

        :param str fn: The full path to the file.
        :param bool divide_closed: Option to divide closed faces.

        :return: None.
        """
        # Store data as dictionaries.
        bodies = {}
        indx = 0

        # Dictionaries to attach wing reference surfaces to wing bodies using
        # reference surface ID as the key.
        wing_bodies = {}
        ref_surfs = {}

        # Build a compound for geometric sets.
        compound = TopoDS_Compound()
        BRep_Builder().MakeCompound(compound)

        # Read file with OCCT.
        step_reader = STEPControl_Reader()
        status = step_reader.ReadFile(fn)
        if status not in [IFSelect_RetVoid, IFSelect_RetDone]:
            return bodies

        # Convert to desired units.
        Interface_Static.SetCVal_("xstep.cascade.unit", Settings.units)

        # Check.
        failsonly = False
        step_reader.PrintCheckLoad(failsonly, IFSelect_ItemsByEntity)
        step_reader.PrintCheckTransfer(failsonly, IFSelect_ItemsByEntity)

        # Transfer. OpenVSP STEP files result in one root and one shape (a
        # compound).
        step_reader.TransferRoot(1)
        master_shape = step_reader.Shape(1)

        # Things needed to extract names from STEP entities.
        session = step_reader.WS()
        transfer_reader = session.TransferReader()

        # Iterate over master shape to find compounds for geometric sets. These
        # sets contain the metadata and the surfaces that make up the
        # component.
        iterator = TopoDS_Iterator(master_shape, True, True)
        more = True
        while iterator.More() and more:
            # The compound.
            compound = iterator.Value()
            # Hack to handle single component for now...
            if compound.ShapeType() != TopAbs_COMPOUND:
                compound = master_shape
                more = False
            # Get the metadata.
            rep_item = transfer_reader.EntityFromShapeResult(compound, 1)
            name = rep_item.Name().ToCString()

            # Unnamed body
            if not name:
                indx += 1
                comp_name = '.'.join(['Body', str(indx)])
                msg = ' '.join(['---Processing OpenVSP component:', comp_name])
                logger.info(msg)
                solid = _build_solid(compound, divide_closed)
                if solid:
                    body = Body(solid)
                    bodies[comp_name] = body
                iterator.Next()
                continue
            metadata = json.loads(name)

            # Process wing reference surface and continue.
            key = 'm_SurfType'
            if key in metadata and metadata[key] == 99:
                # Get surface
                sref = cls.process_sref(compound)
                # Get Sref ID
                sref_id = metadata['ID']
                ref_surfs[sref_id] = sref
                # Next shape.
                iterator.Next()
                continue

            comp_name = metadata['m_Name']
            if comp_name in bodies:
                indx += 1
                comp_name = '.'.join([comp_name, str(indx)])

            # Process component.
            msg = ' '.join(['---Processing OpenVSP component:', comp_name])
            logger.info(msg)

            # Wing
            if metadata['m_Type'] == 5 and metadata['m_SurfType'] != 99:
                wing = _process_wing(compound, divide_closed)
                if wing is not None:
                    wing.set_name(comp_name)
                    bodies[comp_name] = wing
                    sref_id = metadata['Sref ID']
                    wing_bodies[sref_id] = wing

            # Fuselage
            elif metadata['m_Type'] in [4, 9]:
                fuse = _process_fuse(compound, divide_closed)
                if fuse is not None:
                    fuse.set_name(comp_name)
                    bodies[comp_name] = fuse

            # Unknown
            else:
                solid = _build_solid(compound, divide_closed)
                if solid:
                    body = Body(solid)
                    bodies[comp_name] = body

            # Next shape.
            iterator.Next()

        # Attach wing reference surfaces to the bodies.
        for sref_id in wing_bodies:
            if sref_id not in ref_surfs:
                continue
            wing = wing_bodies[sref_id]
            sref = ref_surfs[sref_id]
            wing.set_sref(sref)

        # Update
        cls._bodies.update(bodies)

    @staticmethod
    def rebuild_wing_solid(srfs, divide_closed=True):
        """
        Rebuild a solid shape from the OpenVSP wing surface(s). If only one
        surface is provided then it is assumed that a single surface models the
        OML and it will be split and modified at the root, tip, and trailing
        edge. This single surface should have similar form and
        parametrization as the original OpenVSP surface. If more than once
        surface is provided then it is assumed that the surfaces were split
        during OpenVSP export and are simply sewn together to form the solid.

        :param srfs: The wing surface(s) used to rebuild the solid.
        :type srfs: collections.Sequence(afem.geometry.entities.Surface)
        :param bool divide_closed: Option to divide closed faces.

        :return: The new solid.
        :rtype: OCCT.TopoDS.TopoDS_Solid

        :raise ValueError: If no surfaces are provided.
        """
        faces = [FaceBySurface(s).face for s in srfs]
        compound = CompoundByShapes(faces).compound

        nsrfs = len(srfs)
        if nsrfs == 1:
            return _process_unsplit_wing(compound, divide_closed)
        elif nsrfs > 1:
            return _build_solid(compound, divide_closed)
        else:
            raise ValueError('No surfaces provided.')

    @staticmethod
    def process_sref(compound):
        """
        Process a wing reference surface. The compound should contain a single
        face. The underlying surface of this faces will be used to generate a
        new NurbsSurface. Since the OpenVSP surface uses uniform
        parametrization, a chord line is extracted at each unique knot in the
        v-direction. Then a linear surface is lofted through these lines to
        form a bilinear surface where the u-direction is chordwise and the
        v-direction is spanwise.

        :param OCCT.TopoDS.TopoDS_Compound compound: The compound.

        :return: The reference surface.
        :rtype: afem.geometry.entities.NurbsSurface

        :raise TypeError: If the underlying surface cannot be downcasted to a
            NurbsSurface.
        """
        # Get underlying surface
        top_exp = TopExp_Explorer(compound, TopAbs_FACE)
        face = CheckShape.to_face(top_exp.Current())
        hsrf = BRep_Tool.Surface_(face)

        # Create NurbsSurface
        srf = NurbsSurface(hsrf)

        # Loft new surface
        vknots = srf.vknots
        crvs = []
        for vi in vknots:
            c = srf.v_iso(vi)
            crvs.append(c)
        srf = NurbsSurfaceByInterp(crvs, 1).surface
        return srf

    @staticmethod
    def rebuild_wing_sref(srf):
        """
        Attempt to rebuild a wing reference surface using the given OML
        surface. This method is intended to operate on OpenVSP surfaces that
        define the OML of a wing component and/or have similar parametrization.

        :param afem.geometry.entities.NurbsSurface srf: The surface.

        :return: The reference surface.
        :rtype: afem.geometry.entities.NurbsSurface
        """
        # For VSP, wing surfaces are degree=1 in the spanwise direction, so
        # each knot vector usually represents where a wing cross section is
        # located. For each knot vector in spanwise direction, generate a
        # straight line segment between the LE and TE (i.e., the chord line).
        # These chords will serve as the wing reference surface. This assumes
        # that the LE is at v=0.5 in the local parametric domain.
        uknots = srf.uknots
        le_param = srf.local_to_global_param('v', 0.5)
        te_param = srf.local_to_global_param('v', 0.)
        chords = []
        for u in uknots:
            le = srf.eval(u, le_param)
            te = srf.eval(u, te_param)
            c = NurbsCurveByPoints([le, te]).curve
            chords.append(c)

        # VSP wing components wrap around the ends and there may be duplicate
        # chord lines at the root and tip. Retain only unique lines based on LE
        # point.
        unique_chords = [chords[0]]
        for i in range(1, len(chords)):
            c0 = unique_chords[-1]
            ci = chords[i]
            if not ci.eval(0.).is_equal(c0.eval(0.)):
                unique_chords.append(ci)

        # Create degree=1 reference surface by skinning chord lines
        sref = NurbsSurfaceByInterp(unique_chords, 1).surface

        # Set domains to be 0 to 1.
        sref.set_udomain(0., 1.)
        sref.set_vdomain(0., 1.)

        return sref


def _build_solid(compound, divide_closed):
    # Get all the faces in the compound. The surfaces must be split. Discard
    # any with zero area.
    top_exp = TopExp_Explorer(compound, TopAbs_FACE)
    faces = []
    while top_exp.More():
        shape = top_exp.Current()
        face = CheckShape.to_face(shape)
        fprop = GProp_GProps()
        BRepGProp.SurfaceProperties_(face, fprop, 1.0e-7)
        a = fprop.Mass()
        if a <= 1.0e-7:
            top_exp.Next()
            continue
        faces.append(face)
        top_exp.Next()

    # Replace any planar B-Spline surfaces with planes.
    non_planar_faces = []
    planar_faces = []
    for f in faces:
        hsrf = BRep_Tool.Surface_(f)
        try:
            is_pln = GeomLib_IsPlanarSurface(hsrf, 1.0e-7)
            if is_pln.IsPlanar():
                w = ShapeAnalysis.OuterWire_(f)
                # Fix the wire because they are usually degenerate edges in
                # the planar end caps.
                builder = BRepBuilderAPI_MakeWire()
                for e in ExploreShape.get_edges(w):
                    if LinearProps(e).length > 1.0e-7:
                        builder.Add(e)
                w = builder.Wire()
                fix = ShapeFix_Wire()
                fix.Load(w)
                geom_pln = Geom_Plane(is_pln.Plan())
                fix.SetSurface(geom_pln)
                fix.FixReorder()
                fix.FixConnected()
                fix.FixEdgeCurves()
                fix.FixDegenerated()
                w = fix.WireAPIMake()
                # Build the planar face.
                fnew = BRepBuilderAPI_MakeFace(w, True).Face()
                planar_faces.append(fnew)
            else:
                non_planar_faces.append(f)
        except RuntimeError:
            logger.info('Failed to check for planar face...')
            non_planar_faces.append(f)

    # # Check the faces.
    # for i, f in enumerate(non_planar_faces):
    #     check = BRepCheck_Analyzer(f, True)
    #     if not check.IsValid():
    #         print('Non-planar face is not valid...')
    #         fix = ShapeFix_Face(f)
    #         fix.Perform()
    #         fnew = fix.Result()
    #         check = BRepCheck_Analyzer(fnew, True)
    #         if not check.IsValid():
    #             print('...face could not be fixed.')
    #         else:
    #             non_planar_faces[i] = fnew
    #
    # for i, f in enumerate(planar_faces):
    #     check = BRepCheck_Analyzer(f, True)
    #     if not check.IsValid():
    #         print('Planar face is not valid...')
    #         fix = ShapeFix_Face(f)
    #         fix.Perform()
    #         fnew = fix.Result()
    #         check = BRepCheck_Analyzer(fnew, True)
    #         if not check.IsValid():
    #             print('...face could not be fixed.')
    #         else:
    #             planar_faces[i] = fnew

    # Make a shell and a solid.
    shell = TopoDS_Shell()
    builder = BRep_Builder()
    builder.MakeShell(shell)
    for f in non_planar_faces + planar_faces:
        builder.Add(shell, f)

    # Sew shape.
    sew = BRepBuilderAPI_Sewing(1.0e-7)
    sew.Load(shell)
    sew.Perform()
    sewn_shape = sew.SewedShape()

    if sewn_shape.ShapeType() == TopAbs_FACE:
        face = sewn_shape
        sewn_shape = TopoDS_Shell()
        builder = BRep_Builder()
        builder.MakeShell(sewn_shape)
        builder.Add(sewn_shape, face)

    # Attempt to unify planar domains.
    unify_shp = ShapeUpgrade_UnifySameDomain(sewn_shape, False, False, False)
    try:
        unify_shp.UnifyFaces()
        shape = unify_shp.Shape()
    except RuntimeError:
        logger.info('...failed to unify faces on solid.')
        shape = sewn_shape

    # Make solid.
    shell = ExploreShape.get_shells(shape)[0]
    solid = ShapeFix_Solid().SolidFromShell(shell)

    # Split closed faces of the solid to make OCC more robust.
    if divide_closed:
        divide = ShapeUpgrade_ShapeDivideClosed(solid)
        divide.Perform()
        solid = divide.Result()

    # Make sure it's a solid.
    solid = CheckShape.to_solid(solid)

    # Check the solid and attempt to fix.
    check_shp = BRepCheck_Analyzer(solid, True)
    if not check_shp.IsValid():
        logger.info('Fixing the solid...')
        fix = ShapeFix_Solid(solid)
        fix.Perform()
        solid = fix.Solid()
        check_shp = BRepCheck_Analyzer(solid, True)
        if not check_shp.IsValid():
            logger.info('...solid could not be fixed.')
    else:
        tol = ExploreShape.global_tolerance(solid)
        logger.info('Successfully generated solid. Tol={0}'.format(tol))

    return solid


def _process_wing(compound, divide_closed):
    # Note that for VSP wings, the spanwise direction is u and the chord
    # direction is v, where v=0 is the TE and follows the lower surface fwd to
    # the LE, and then aft along the upper surface to the TE.

    # Process based on number of faces in compound assuming split/no split
    # option was used.
    faces = ExploreShape.get_faces(compound)
    vsp_surf = None
    if len(faces) == 1:
        solid = _process_unsplit_wing(compound, divide_closed)
        vsp_surf = ExploreShape.surface_of_face(faces[0])
    else:
        solid = _build_solid(compound, divide_closed)

    if not solid:
        return None

    wing = Body(solid)

    if vsp_surf:
        vsp_surf = NurbsSurface(vsp_surf.handle)
        wing.add_metadata('vsp surface', vsp_surf)
        upr_srf = vsp_surf.copy()
        v_le = vsp_surf.local_to_global_param('v', 0.5)
        upr_srf.segment(vsp_surf.u1, vsp_surf.u2, v_le, vsp_surf.v2)
        wing.add_metadata('upper surface', upr_srf)
        lwr_srf = vsp_surf.copy()
        lwr_srf.segment(vsp_surf.u1, vsp_surf.u2, vsp_surf.v1, v_le)
        wing.add_metadata('lower surface', lwr_srf)

    return wing


def _process_fuse(compound, divide_closed):
    # For VSP fuselages, the longitudinal direction is u, and the
    # circumferential direction is v.
    # Build the solid.
    solid = _build_solid(compound, divide_closed)
    if not solid:
        return None

    fuselage = Body(solid)

    faces = ExploreShape.get_faces(compound)
    if len(faces) == 1:
        vsp_surf = ExploreShape.surface_of_face(faces[0])
        vsp_surf = NurbsSurface(vsp_surf.handle)
        fuselage.add_metadata('vsp surface', vsp_surf)

    return fuselage


def _process_unsplit_wing(compound, divide_closed):
    # Process a wing that was generated without "Split Surfs" option.

    faces = ExploreShape.get_faces(compound)
    if len(faces) != 1:
        return None
    face = faces[0]

    # Get the surface.
    master_surf = ExploreShape.surface_of_face(face)
    master_surf = NurbsSurface(master_surf.handle)
    uknots, vknots = master_surf.uknots, master_surf.vknots
    vsplit = master_surf.local_to_global_param('v', 0.5)

    # Segment off the end caps and the trailing edges.
    u1, u2 = uknots[1], uknots[-2]
    v1, v2 = vknots[1], vknots[-2]
    s1 = master_surf.copy()
    s1.segment(u1, u2, v1, v2)

    # Segment off end caps and the trailing edge and split at LE.
    u1, u2 = uknots[0], uknots[1]
    v1, v2 = vknots[1], vsplit
    s2 = master_surf.copy()
    s2.segment(u1, u2, v1, v2)

    u1, u2 = uknots[0], uknots[1]
    v1, v2 = vsplit, vknots[-2]
    s3 = master_surf.copy()
    s3.segment(u1, u2, v1, v2)

    u1, u2 = uknots[-2], uknots[-1]
    v1, v2 = vknots[1], vsplit
    s4 = master_surf.copy()
    s4.segment(u1, u2, v1, v2)

    u1, u2 = uknots[-2], uknots[-1]
    v1, v2 = vsplit, vknots[-2]
    s5 = master_surf.copy()
    s5.segment(u1, u2, v1, v2)

    # Make faces of surface.
    new_faces = []
    for s in [s1, s2, s3, s4, s5]:
        f = BRepBuilderAPI_MakeFace(s.handle, 0.).Face()
        new_faces.append(f)

    # Segment off TE.
    u1, u2 = uknots[0], uknots[-1]
    v1, v2 = vknots[0], vknots[1]
    s6 = master_surf.copy()
    s6.segment(u1, u2, v1, v2)

    u1, u2 = uknots[0], uknots[-1]
    v1, v2 = vknots[-2], vknots[-1]
    s7 = master_surf.copy()
    s7.segment(u1, u2, v1, v2)

    # Split the TE surface at each uknot.
    usplits = TColStd_HSequenceOfReal()
    for ui in uknots[1:-1]:
        usplits.Append(ui)

    split = ShapeUpgrade_SplitSurface()
    split.Init(s6.handle)
    split.SetUSplitValues(usplits)
    split.Perform()
    comp_surf1 = split.ResSurfaces()

    split = ShapeUpgrade_SplitSurface()
    split.Init(s7.handle)
    split.SetUSplitValues(usplits)
    split.Perform()
    comp_surf2 = split.ResSurfaces()

    # For each patch in the composite surfaces create a face.
    for i in range(1, comp_surf1.NbUPatches() + 1):
        for j in range(1, comp_surf1.NbVPatches() + 1):
            hpatch = comp_surf1.Patch(i, j)
            f = BRepBuilderAPI_MakeFace(hpatch, 0.).Face()
            new_faces.append(f)

    for i in range(1, comp_surf2.NbUPatches() + 1):
        for j in range(1, comp_surf2.NbVPatches() + 1):
            hpatch = comp_surf2.Patch(i, j)
            f = BRepBuilderAPI_MakeFace(hpatch, 0.).Face()
            new_faces.append(f)

    # Put all faces into a compound a generate solid.
    new_compound = CompoundByShapes(new_faces).compound

    return _build_solid(new_compound, divide_closed)
