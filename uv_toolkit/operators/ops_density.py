"""UV Toolkit — Texel density operators."""

from __future__ import annotations

import bpy
import bmesh

from ..core.island import get_islands, UVIsland
from ..core import density as core_density


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _selected_islands(islands):
    """Return islands that contain at least one selected face."""
    return [isl for isl in islands if any(f.select for f in isl.faces)]


def _active_island(bm, islands):
    """Return the island containing the active face, or None."""
    active_face = bm.faces.active
    if active_face is None:
        return None
    for isl in islands:
        if active_face in isl.faces:
            return isl
    return None


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class UVTK_OT_SetTexelDensity(bpy.types.Operator):
    """Set all selected UV islands to the target texel density."""

    bl_idname = "uvtk.td_set"
    bl_label = "Set Texel Density"
    bl_description = "Scale selected UV islands so they match the target texel density"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        for island in sel:
            if island.area_3d == 0.0:
                continue
            core_density.set_texel_density(
                island,
                target_td=props.td_target,
                texture_size=props.td_texture_size,
                uv_layer=uv_layer,
            )

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Set TD to {props.td_target:.1f} px/m on {len(sel)} island(s)")
        return {"FINISHED"}


class UVTK_OT_NormalizeTD(bpy.types.Operator):
    """Normalise all UV islands to the same (average) texel density."""

    bl_idname = "uvtk.td_normalize"
    bl_label = "Normalize Texel Density"
    bl_description = "Scale all islands so they share the same average texel density"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        if not islands:
            self.report({"WARNING"}, "No UV islands found")
            return {"CANCELLED"}

        core_density.normalize_texel_density(
            islands,
            texture_size=props.td_texture_size,
            uv_layer=uv_layer,
        )

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Normalised TD across {len(islands)} island(s)")
        return {"FINISHED"}


class UVTK_OT_GetTexelDensity(bpy.types.Operator):
    """Read the texel density of the active island into the target TD property."""

    bl_idname = "uvtk.td_get"
    bl_label = "Get Texel Density"
    bl_description = "Read the texel density of the active island into the TD target field"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        island = _active_island(bm, islands)

        if island is None:
            # Fall back to first selected island.
            sel = _selected_islands(islands)
            if sel:
                island = sel[0]

        if island is None:
            self.report({"WARNING"}, "No active island — select a face first")
            return {"CANCELLED"}

        if island.area_3d == 0.0:
            self.report({"WARNING"}, "Active island has zero 3D area")
            return {"CANCELLED"}

        td = core_density.compute_texel_density(island, props.td_texture_size)
        props.td_target = td

        self.report({"INFO"}, f"Got TD: {td:.2f} px/m from active island")
        return {"FINISHED"}


class UVTK_OT_CopyTD(bpy.types.Operator):
    """Copy the texel density from the active island to all other selected islands."""

    bl_idname = "uvtk.td_copy"
    bl_label = "Copy Texel Density"
    bl_description = "Apply the active island's texel density to all other selected islands"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        source_island = _active_island(bm, islands)
        if source_island is None:
            self.report({"WARNING"}, "No active island — make a face active first")
            return {"CANCELLED"}

        if source_island.area_3d == 0.0:
            self.report({"WARNING"}, "Active island has zero 3D area")
            return {"CANCELLED"}

        source_td = core_density.compute_texel_density(source_island, props.td_texture_size)

        sel = _selected_islands(islands)
        targets = [isl for isl in sel if isl is not source_island]

        if not targets:
            self.report({"WARNING"}, "No other selected islands to copy TD to")
            return {"CANCELLED"}

        for island in targets:
            if island.area_3d == 0.0:
                continue
            core_density.set_texel_density(
                island,
                target_td=source_td,
                texture_size=props.td_texture_size,
                uv_layer=uv_layer,
            )

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Copied {source_td:.2f} px/m to {len(targets)} island(s)")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_SetTexelDensity,
    UVTK_OT_NormalizeTD,
    UVTK_OT_GetTexelDensity,
    UVTK_OT_CopyTD,
)
