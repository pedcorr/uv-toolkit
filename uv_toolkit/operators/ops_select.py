"""UV Toolkit — UV selection operators."""

from __future__ import annotations

import bpy
import bmesh

from ..core.island import get_islands, UVIsland
from ..core import overlap as core_overlap


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _select_islands(bm, islands, indices):
    """Select all faces belonging to the listed island indices."""
    index_set = set(indices)
    for idx, island in enumerate(islands):
        if idx in index_set:
            for face in island.faces:
                face.select = True
    bm.select_flush_mode()


def _selected_islands(islands):
    """Return indices of islands that contain at least one selected face."""
    return [i for i, isl in enumerate(islands) if any(f.select for f in isl.faces)]


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class UVTK_OT_SelectOverlapping(bpy.types.Operator):
    """Select all UV islands that overlap at least one other island."""

    bl_idname = "uvtk.select_overlapping"
    bl_label = "Select Overlapping"
    bl_description = "Select UV islands that overlap one or more other islands"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        if not islands:
            self.report({"WARNING"}, "No UV islands found")
            return {"CANCELLED"}

        overlapping_indices = core_overlap.find_overlapping_islands(islands)

        if not overlapping_indices:
            self.report({"INFO"}, "No overlapping islands found")
            return {"FINISHED"}

        # Deselect all first, then select matched islands.
        for face in bm.faces:
            face.select = False

        _select_islands(bm, islands, overlapping_indices)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Selected {len(overlapping_indices)} overlapping island(s)")
        return {"FINISHED"}


class UVTK_OT_SelectFlipped(bpy.types.Operator):
    """Select all UV islands whose winding is flipped (negative UV area)."""

    bl_idname = "uvtk.select_flipped"
    bl_label = "Select Flipped"
    bl_description = "Select UV islands that are flipped / have inverted winding"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        if not islands:
            self.report({"WARNING"}, "No UV islands found")
            return {"CANCELLED"}

        flipped_indices = core_overlap.find_flipped_islands(islands)

        if not flipped_indices:
            self.report({"INFO"}, "No flipped islands found")
            return {"FINISHED"}

        for face in bm.faces:
            face.select = False

        _select_islands(bm, islands, flipped_indices)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Selected {len(flipped_indices)} flipped island(s)")
        return {"FINISHED"}


class UVTK_OT_SelectStretched(bpy.types.Operator):
    """Select UV islands whose UV/3D area ratio deviates beyond a threshold."""

    bl_idname = "uvtk.select_stretched"
    bl_label = "Select Stretched"
    bl_description = "Select UV islands that are stretched beyond the area-ratio threshold"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        if not islands:
            self.report({"WARNING"}, "No UV islands found")
            return {"CANCELLED"}

        # Use a 0.25 default threshold (25% area deviation).
        stretched_indices = core_overlap.find_stretched_islands(islands, threshold=0.25)

        if not stretched_indices:
            self.report({"INFO"}, "No stretched islands found")
            return {"FINISHED"}

        for face in bm.faces:
            face.select = False

        _select_islands(bm, islands, stretched_indices)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Selected {len(stretched_indices)} stretched island(s)")
        return {"FINISHED"}


class UVTK_OT_SelectSimilar(bpy.types.Operator):
    """Select UV islands with similar area to the active (last-selected) island."""

    bl_idname = "uvtk.select_similar"
    bl_label = "Select Similar Islands"
    bl_description = (
        "Select all UV islands whose UV area is within 10% of the active island's area"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()
        islands = get_islands(bm, uv_layer)

        if not islands:
            self.report({"WARNING"}, "No UV islands found")
            return {"CANCELLED"}

        # Determine the active island from the active face.
        active_face = bm.faces.active
        active_island = None

        if active_face is not None:
            for isl in islands:
                if active_face in isl.faces:
                    active_island = isl
                    break

        if active_island is None:
            # Fall back: use island containing the first selected face.
            for isl in islands:
                if any(f.select for f in isl.faces):
                    active_island = isl
                    break

        if active_island is None:
            self.report({"WARNING"}, "No active island found — select a face first")
            return {"CANCELLED"}

        ref_area = active_island.area_uv
        tolerance = 0.10  # 10% area tolerance

        matched_indices = []
        for idx, isl in enumerate(islands):
            if isl is active_island:
                continue
            if ref_area == 0.0:
                # Both must be zero-area to match.
                if isl.area_uv == 0.0:
                    matched_indices.append(idx)
            else:
                ratio = abs(isl.area_uv - ref_area) / ref_area
                if ratio <= tolerance:
                    matched_indices.append(idx)

        if not matched_indices:
            self.report({"INFO"}, "No similar islands found")
            return {"FINISHED"}

        # Keep active island selected, add matching islands.
        for face in bm.faces:
            face.select = False

        # Re-select active island.
        for face in active_island.faces:
            face.select = True

        _select_islands(bm, islands, matched_indices)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Selected {len(matched_indices)} similar island(s)")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_SelectOverlapping,
    UVTK_OT_SelectFlipped,
    UVTK_OT_SelectStretched,
    UVTK_OT_SelectSimilar,
)
