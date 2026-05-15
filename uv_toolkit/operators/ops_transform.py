"""UV Toolkit — Island transform operators."""

from __future__ import annotations

import math
import random

import bpy
import bmesh
import numpy as np
from bpy.props import EnumProperty, FloatProperty
from mathutils import Vector

from ..core.island import get_islands, apply_island_transform, UVIsland
from ..core import geometry as core_geometry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _selected_islands(islands):
    """Return islands that contain at least one selected face."""
    return [isl for isl in islands if any(f.select for f in isl.faces)]


def _make_translation_matrix(tx: float, ty: float) -> np.ndarray:
    return np.array([[1.0, 0.0, tx], [0.0, 1.0, ty]], dtype=np.float64)


def _make_rotation_matrix(angle_deg: float, pivot: np.ndarray) -> np.ndarray:
    """2x3 affine matrix: rotate around *pivot* by *angle_deg* degrees."""
    a = math.radians(angle_deg)
    cos_a = math.cos(a)
    sin_a = math.sin(a)
    R = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float64)
    t = -R @ pivot + pivot
    return np.hstack([R, t.reshape(2, 1)])


def _make_scale_matrix(sx: float, sy: float, pivot: np.ndarray) -> np.ndarray:
    """2x3 affine matrix: scale around *pivot*."""
    S = np.array([[sx, 0.0], [0.0, sy]], dtype=np.float64)
    t = -S @ pivot + pivot
    return np.hstack([S, t.reshape(2, 1)])


def _island_center(island: UVIsland) -> np.ndarray:
    min_u, min_v, max_u, max_v = island.bbox
    return np.array([(min_u + max_u) * 0.5, (min_v + max_v) * 0.5], dtype=np.float64)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class UVTK_OT_AlignIslands(bpy.types.Operator):
    """Align selected islands' bounding boxes to a shared edge or axis."""

    bl_idname = "uvtk.align_islands"
    bl_label = "Align Islands"
    bl_description = "Align selected UV islands relative to each other or the UV space"
    bl_options = {"REGISTER", "UNDO"}

    align_to: EnumProperty(
        name="Align To",
        description="Edge or axis to align islands against",
        items=[
            ("LEFT",     "Left",             "Align left edges"),
            ("RIGHT",    "Right",            "Align right edges"),
            ("TOP",      "Top",              "Align top edges"),
            ("BOTTOM",   "Bottom",           "Align bottom edges"),
            ("CENTER_H", "Centre Horizontal","Centre horizontally"),
            ("CENTER_V", "Centre Vertical",  "Centre vertically"),
        ],
        default="LEFT",
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if len(sel) < 2:
            self.report({"WARNING"}, "Need at least 2 selected islands to align")
            return {"CANCELLED"}

        mode = self.align_to

        # Compute the target coordinate from all selected island bboxes.
        if mode == "LEFT":
            target = min(isl.bbox[0] for isl in sel)
        elif mode == "RIGHT":
            target = max(isl.bbox[2] for isl in sel)
        elif mode == "BOTTOM":
            target = min(isl.bbox[1] for isl in sel)
        elif mode == "TOP":
            target = max(isl.bbox[3] for isl in sel)
        elif mode == "CENTER_H":
            target = sum((isl.bbox[0] + isl.bbox[2]) * 0.5 for isl in sel) / len(sel)
        else:  # CENTER_V
            target = sum((isl.bbox[1] + isl.bbox[3]) * 0.5 for isl in sel) / len(sel)

        for island in sel:
            min_u, min_v, max_u, max_v = island.bbox
            if mode == "LEFT":
                delta = np.array([target - min_u, 0.0])
            elif mode == "RIGHT":
                delta = np.array([target - max_u, 0.0])
            elif mode == "BOTTOM":
                delta = np.array([0.0, target - min_v])
            elif mode == "TOP":
                delta = np.array([0.0, target - max_v])
            elif mode == "CENTER_H":
                cx = (min_u + max_u) * 0.5
                delta = np.array([target - cx, 0.0])
            else:  # CENTER_V
                cy = (min_v + max_v) * 0.5
                delta = np.array([0.0, target - cy])

            mat = _make_translation_matrix(delta[0], delta[1])
            apply_island_transform(island, mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_DistributeIslands(bpy.types.Operator):
    """Distribute selected islands with even spacing along an axis."""

    bl_idname = "uvtk.distribute_islands"
    bl_label = "Distribute Islands"
    bl_description = "Evenly space selected islands horizontally or vertically"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        name="Direction",
        items=[
            ("H", "Horizontal", "Distribute along the U axis"),
            ("V", "Vertical",   "Distribute along the V axis"),
        ],
        default="H",
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if len(sel) < 3:
            self.report({"WARNING"}, "Need at least 3 selected islands to distribute")
            return {"CANCELLED"}

        if self.direction == "H":
            sel.sort(key=lambda isl: isl.bbox[0])  # sort by left edge
            total_width = sum(isl.bbox[2] - isl.bbox[0] for isl in sel)
            span = sel[-1].bbox[2] - sel[0].bbox[0]
            gap = (span - total_width) / (len(sel) - 1)

            cursor = sel[0].bbox[0]
            for island in sel:
                w = island.bbox[2] - island.bbox[0]
                delta_u = cursor - island.bbox[0]
                mat = _make_translation_matrix(delta_u, 0.0)
                apply_island_transform(island, mat, uv_layer)
                cursor += w + gap
        else:
            sel.sort(key=lambda isl: isl.bbox[1])  # sort by bottom edge
            total_height = sum(isl.bbox[3] - isl.bbox[1] for isl in sel)
            span = sel[-1].bbox[3] - sel[0].bbox[1]
            gap = (span - total_height) / (len(sel) - 1)

            cursor = sel[0].bbox[1]
            for island in sel:
                h = island.bbox[3] - island.bbox[1]
                delta_v = cursor - island.bbox[1]
                mat = _make_translation_matrix(0.0, delta_v)
                apply_island_transform(island, mat, uv_layer)
                cursor += h + gap

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_WorldOrient(bpy.types.Operator):
    """Orient UV islands to align with world-space face normals."""

    bl_idname = "uvtk.world_orient"
    bl_label = "World Orient"
    bl_description = "Rotate UV islands to align with the dominant world-space direction"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        for island in sel:
            matrix = core_geometry.world_orient(island, obj)
            if matrix is not None:
                apply_island_transform(island, matrix, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_RotateIsland(bpy.types.Operator):
    """Rotate selected UV islands around their centres."""

    bl_idname = "uvtk.rotate_island"
    bl_label = "Rotate Island"
    bl_description = "Rotate selected UV islands around their bounding-box centres"
    bl_options = {"REGISTER", "UNDO"}

    angle_deg: FloatProperty(
        name="Angle",
        description="Rotation angle in degrees (positive = counter-clockwise)",
        default=90.0,
        min=-360.0,
        max=360.0,
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        for island in sel:
            pivot = _island_center(island)
            mat = _make_rotation_matrix(self.angle_deg, pivot)
            apply_island_transform(island, mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_popup(self, event)


class UVTK_OT_FlipIsland(bpy.types.Operator):
    """Flip selected UV islands horizontally or vertically."""

    bl_idname = "uvtk.flip_island"
    bl_label = "Flip Island"
    bl_description = "Mirror selected UV islands around their centres"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        items=[
            ("H", "Horizontal", "Flip left–right (U axis)"),
            ("V", "Vertical",   "Flip top–bottom (V axis)"),
        ],
        default="H",
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        for island in sel:
            pivot = _island_center(island)
            if self.axis == "H":
                # Flip U: scale x by -1 around pivot.
                mat = _make_scale_matrix(-1.0, 1.0, pivot)
            else:
                # Flip V: scale y by -1 around pivot.
                mat = _make_scale_matrix(1.0, -1.0, pivot)
            apply_island_transform(island, mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_FitToUVSpace(bpy.types.Operator):
    """Scale each selected island uniformly to fill the [0,1] UV space."""

    bl_idname = "uvtk.fit_uv_space"
    bl_label = "Fit to UV Space"
    bl_description = "Scale and centre selected islands to fill the [0,1] UV square"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        for island in sel:
            min_u, min_v, max_u, max_v = island.bbox
            w = max_u - min_u
            h = max_v - min_v
            if w == 0.0 or h == 0.0:
                continue

            # Uniform scale: fit the larger dimension to 1.0.
            scale = 1.0 / max(w, h)
            pivot = np.array([min_u, min_v], dtype=np.float64)

            # Scale, then translate so the result is centred in [0,1].
            scale_mat = _make_scale_matrix(scale, scale, pivot)
            apply_island_transform(island, scale_mat, uv_layer)

            # Centre in [0,1] after scaling.
            new_min_u, new_min_v, new_max_u, new_max_v = island.bbox
            new_w = new_max_u - new_min_u
            new_h = new_max_v - new_min_v
            tx = (1.0 - new_w) * 0.5 - new_min_u
            ty = (1.0 - new_h) * 0.5 - new_min_v
            trans_mat = _make_translation_matrix(tx, ty)
            apply_island_transform(island, trans_mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}


class UVTK_OT_StackIslands(bpy.types.Operator):
    """Move all selected islands to overlap the active (last-selected) island exactly."""

    bl_idname = "uvtk.stack_islands"
    bl_label = "Stack Islands"
    bl_description = "Move all selected islands to overlap the active island exactly"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if len(sel) < 2:
            self.report({"WARNING"}, "Need at least 2 selected islands to stack")
            return {"CANCELLED"}

        # The "active" island is the one containing the active face.
        active_face = bm.faces.active
        active_island = None
        if active_face is not None:
            for isl in sel:
                if active_face in isl.faces:
                    active_island = isl
                    break

        # Fall back to last island in selection list.
        if active_island is None:
            active_island = sel[-1]

        target_center = _island_center(active_island)

        for island in sel:
            if island is active_island:
                continue
            src_center = _island_center(island)
            delta = target_center - src_center
            mat = _make_translation_matrix(delta[0], delta[1])
            apply_island_transform(island, mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Stacked {len(sel) - 1} island(s) onto active")
        return {"FINISHED"}


class UVTK_OT_UnstackIslands(bpy.types.Operator):
    """Separate stacked (overlapping) islands by distributing them with even spacing."""

    bl_idname = "uvtk.unstack_islands"
    bl_label = "Unstack Islands"
    bl_description = "Distribute overlapping islands with even horizontal spacing"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        # Find the left-most starting position.
        start_u = min(isl.bbox[0] for isl in sel)
        margin = 0.01  # small gap between unstacked islands

        cursor = start_u
        for island in sel:
            w = island.bbox[2] - island.bbox[0]
            delta_u = cursor - island.bbox[0]
            mat = _make_translation_matrix(delta_u, 0.0)
            apply_island_transform(island, mat, uv_layer)
            cursor += w + margin

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Unstacked {len(sel)} island(s)")
        return {"FINISHED"}


class UVTK_OT_RandomizeIslands(bpy.types.Operator):
    """Apply random position, rotation, and scale offsets to selected islands."""

    bl_idname = "uvtk.randomize"
    bl_label = "Randomize Islands"
    bl_description = "Apply random position, rotation, and scale offsets to selected islands"
    bl_options = {"REGISTER", "UNDO"}

    pos_range: FloatProperty(
        name="Position Range",
        description="Maximum random offset in UV units",
        default=0.1,
        min=0.0,
        max=1.0,
    )
    rot_range: FloatProperty(
        name="Rotation Range",
        description="Maximum random rotation in degrees",
        default=15.0,
        min=0.0,
        max=180.0,
    )
    scale_range: FloatProperty(
        name="Scale Range",
        description="Maximum random scale deviation (0 = no scale change)",
        default=0.1,
        min=0.0,
        max=1.0,
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)
        sel = _selected_islands(islands)

        if not sel:
            self.report({"WARNING"}, "No selected islands")
            return {"CANCELLED"}

        rng = random.Random()  # uses global seed so result is different each call

        for island in sel:
            pivot = _island_center(island)

            # Random scale (uniform, centred on 1.0).
            if self.scale_range > 0.0:
                s = 1.0 + rng.uniform(-self.scale_range, self.scale_range)
                scale_mat = _make_scale_matrix(s, s, pivot)
                apply_island_transform(island, scale_mat, uv_layer)
                # Pivot has not moved; recompute after scale.
                pivot = _island_center(island)

            # Random rotation.
            if self.rot_range > 0.0:
                angle = rng.uniform(-self.rot_range, self.rot_range)
                rot_mat = _make_rotation_matrix(angle, pivot)
                apply_island_transform(island, rot_mat, uv_layer)

            # Random position offset.
            if self.pos_range > 0.0:
                du = rng.uniform(-self.pos_range, self.pos_range)
                dv = rng.uniform(-self.pos_range, self.pos_range)
                trans_mat = _make_translation_matrix(du, dv)
                apply_island_transform(island, trans_mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_popup(self, event)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_AlignIslands,
    UVTK_OT_DistributeIslands,
    UVTK_OT_WorldOrient,
    UVTK_OT_RotateIsland,
    UVTK_OT_FlipIsland,
    UVTK_OT_FitToUVSpace,
    UVTK_OT_StackIslands,
    UVTK_OT_UnstackIslands,
    UVTK_OT_RandomizeIslands,
)
