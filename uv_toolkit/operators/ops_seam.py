"""UV Toolkit — Seam marking operators."""

from __future__ import annotations

import bpy
import bmesh
from bpy.props import EnumProperty

from ..core.island import get_islands
from ..core import seam as core_seam


class UVTK_OT_MarkSeamsByAngle(bpy.types.Operator):
    """Mark seams on edges where the dihedral angle exceeds the scene threshold."""

    bl_idname = "uvtk.mark_seams_angle"
    bl_label = "Mark Seams by Angle"
    bl_description = "Mark seams where adjacent face angle exceeds the threshold"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)

        core_seam.mark_seams_by_angle(
            bm,
            angle_threshold_deg=props.seam_angle,
            mark_seams=props.mark_seams,
            mark_sharps=props.mark_sharps,
        )

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_MarkSeamsByOpenEdges(bpy.types.Operator):
    """Mark all boundary (open) edges as seams."""

    bl_idname = "uvtk.mark_seams_open"
    bl_label = "Mark Open Edges as Seams"
    bl_description = "Mark all boundary edges (edges with only one adjacent face) as seams"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)

        core_seam.mark_seams_by_open_edges(
            bm,
            mark_seams=props.mark_seams,
            mark_sharps=props.mark_sharps,
        )

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_MarkSeamsByUVBorders(bpy.types.Operator):
    """Mark seams based on existing UV splits in the mesh."""

    bl_idname = "uvtk.mark_seams_uv_borders"
    bl_label = "Mark Seams by UV Borders"
    bl_description = "Mark edges as seams wherever UV coordinates are split"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        core_seam.mark_seams_by_uv_borders(bm, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_MarkSelectedAsSeam(bpy.types.Operator):
    """Mark currently selected edges as UV seams."""

    bl_idname = "uvtk.mark_selected_seam"
    bl_label = "Mark Selected as Seam"
    bl_description = "Mark selected edges as UV seams"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)

        marked = 0
        for edge in bm.edges:
            if edge.select:
                edge.seam = True
                marked += 1

        if marked == 0:
            self.report({"WARNING"}, "No edges selected")
            return {"CANCELLED"}

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Marked {marked} edge(s) as seams")
        return {"FINISHED"}


class UVTK_OT_ClearSeams(bpy.types.Operator):
    """Remove all seam and sharp flags from the mesh."""

    bl_idname = "uvtk.clear_seams"
    bl_label = "Clear Seams"
    bl_description = "Remove all seam (and optionally sharp) flags from every edge"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        core_seam.clear_seams(bm)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_MirrorSeams(bpy.types.Operator):
    """Mirror seam placement across a symmetry axis."""

    bl_idname = "uvtk.mirror_seams"
    bl_label = "Mirror Seams"
    bl_description = "Mirror seam placement across X or Y axis for symmetrical models"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        description="Axis to mirror seams across",
        items=[
            ("X", "X", "Mirror across the X axis"),
            ("Y", "Y", "Mirror across the Y axis"),
        ],
        default="X",
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        core_seam.mirror_seams(bm, axis=self.axis)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_MarkSeamsByAngle,
    UVTK_OT_MarkSeamsByOpenEdges,
    UVTK_OT_MarkSeamsByUVBorders,
    UVTK_OT_MarkSelectedAsSeam,
    UVTK_OT_ClearSeams,
    UVTK_OT_MirrorSeams,
)
