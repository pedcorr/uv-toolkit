"""UV Toolkit — Pack operators."""

from __future__ import annotations

import math

import bpy
import bmesh
import numpy as np

from ..core.island import get_islands, apply_island_transform, UVIsland
from ..core import packer as core_packer


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _selected_islands(islands):
    """Return islands that contain at least one selected face."""
    return [isl for isl in islands if any(f.select for f in isl.faces)]


def _unselected_islands(islands):
    """Return islands where no face is selected."""
    return [isl for isl in islands if not any(f.select for f in isl.faces)]


def _apply_placement(island: UVIsland, x: float, y: float,
                     rotation_deg: float, uv_layer) -> None:
    """
    Apply a (x, y, rotation_deg) placement result from the packer to *island*.

    Steps:
    1. Rotate UVs around their bounding-box centre by *rotation_deg*.
    2. Translate so the rotated bbox min lands at (x, y).
    """
    min_u, min_v, max_u, max_v = island.bbox
    cx = (min_u + max_u) * 0.5
    cy = (min_v + max_v) * 0.5

    # Build a 2×3 rotation matrix around the island centre.
    angle_rad = math.radians(rotation_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Rotate around centre, then translate to target position.
    # Combined affine: T_dest * R_centre
    # new_uv = R @ (uv - centre) + centre + translation
    #
    # Written as a single 2×3 matrix:
    #   A = R
    #   t = -R @ centre + centre + (target_min - rotated_min)

    # First rotate to get new bbox.
    R = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float64)
    centre = np.array([cx, cy], dtype=np.float64)

    rotated_uvs = (island.uvs - centre) @ R.T + centre
    rot_min_u = float(rotated_uvs[:, 0].min())
    rot_min_v = float(rotated_uvs[:, 1].min())

    # Translation to place rotated bbox at (x, y).
    tx = x - rot_min_u
    ty = y - rot_min_v

    # Full combined translation vector for apply_island_transform.
    # apply_island_transform applies: new_uvs = uvs @ A.T + t
    # We want: new_uvs = (uvs - centre) @ R.T + centre + [tx, ty]
    #        = uvs @ R.T - centre @ R.T + centre + [tx, ty]
    # So A = R, t = -R @ centre + centre + [tx, ty]
    t = -centre @ R.T + centre + np.array([tx, ty])

    matrix = np.hstack([R, t.reshape(2, 1)])  # shape (2, 3)
    apply_island_transform(island, matrix, uv_layer)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class UVTK_OT_PackIslands(bpy.types.Operator):
    """Pack all UV islands using the MaxRects algorithm."""

    bl_idname = "uvtk.pack"
    bl_label = "Pack Islands"
    bl_description = "Pack all UV islands into the UV space using MaxRects bin packing"
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

        packer = core_packer.MaxRectsPacker(
            bin_w=1.0,
            bin_h=1.0,
            margin=props.pack_margin,
        )

        placements = packer.pack(
            islands,
            rotate_step=props.pack_rotate_step if props.pack_rotate else 360,
        )

        for island, (x, y, rot) in zip(islands, placements):
            _apply_placement(island, x, y, rot, uv_layer)

        # UDIM offset: shift into the target tile after packing.
        if props.pack_udim:
            tile = props.pack_target_tile
            tile_col = (tile - 1001) % 10
            tile_row = (tile - 1001) // 10
            offset = np.array([float(tile_col), float(tile_row)], dtype=np.float64)
            identity = np.array([[1, 0, offset[0]], [0, 1, offset[1]]], dtype=np.float64)
            for island in islands:
                apply_island_transform(island, identity, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Packed {len(islands)} island(s)")
        return {"FINISHED"}


class UVTK_OT_RepackWithOthers(bpy.types.Operator):
    """Repack selected islands while keeping unselected islands in place."""

    bl_idname = "uvtk.repack_with_others"
    bl_label = "Repack With Others"
    bl_description = (
        "Pack selected islands into remaining free space, "
        "leaving unselected islands untouched"
    )
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
        sel_islands = _selected_islands(islands)
        unsel_islands = _unselected_islands(islands)

        if not sel_islands:
            self.report({"WARNING"}, "No selected islands to pack")
            return {"CANCELLED"}

        # Collect bounding boxes already occupied by unselected islands.
        occupied_rects = []
        for isl in unsel_islands:
            min_u, min_v, max_u, max_v = isl.bbox
            w = max_u - min_u + props.pack_margin * 2
            h = max_v - min_v + props.pack_margin * 2
            x = min_u - props.pack_margin
            y = min_v - props.pack_margin
            occupied_rects.append((x, y, w, h))

        packer = core_packer.MaxRectsPacker(
            bin_w=1.0,
            bin_h=1.0,
            margin=props.pack_margin,
        )

        # Pass occupied regions so packer avoids them.
        placements = packer.pack(
            sel_islands,
            rotate_step=props.pack_rotate_step if props.pack_rotate else 360,
            occupied_rects=occupied_rects,
        )

        for island, (x, y, rot) in zip(sel_islands, placements):
            _apply_placement(island, x, y, rot, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Repacked {len(sel_islands)} island(s)")
        return {"FINISHED"}


class UVTK_OT_PackToTile(bpy.types.Operator):
    """Pack all UV islands into a specific UDIM tile."""

    bl_idname = "uvtk.pack_to_tile"
    bl_label = "Pack to Tile"
    bl_description = "Pack UV islands into a specific UDIM tile"
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

        tile = props.pack_target_tile
        # UDIM tile numbering: 1001 = (col=0, row=0), 1002 = (col=1, row=0), etc.
        tile_col = (tile - 1001) % 10
        tile_row = (tile - 1001) // 10

        # Remap all island UVs to [0,1] before packing.
        # Find global bounds across all islands.
        all_uvs = np.vstack([isl.uvs for isl in islands if len(isl.uvs)])
        global_min = all_uvs.min(axis=0)
        global_max = all_uvs.max(axis=0)
        global_range = global_max - global_min
        global_range = np.where(global_range == 0, 1.0, global_range)

        for island in islands:
            if not len(island.uvs):
                continue
            # Translate to [0,1] space for packing.
            scale = 1.0 / global_range
            # Build normalisation matrix.
            norm_mat = np.array([
                [scale[0], 0.0, -global_min[0] * scale[0]],
                [0.0, scale[1], -global_min[1] * scale[1]],
            ], dtype=np.float64)
            apply_island_transform(island, norm_mat, uv_layer)

        # Pack into [0,1].
        packer = core_packer.MaxRectsPacker(
            bin_w=1.0,
            bin_h=1.0,
            margin=props.pack_margin,
        )
        placements = packer.pack(
            islands,
            rotate_step=props.pack_rotate_step if props.pack_rotate else 360,
        )

        for island, (x, y, rot) in zip(islands, placements):
            _apply_placement(island, x, y, rot, uv_layer)

        # Offset by tile coordinates.
        offset = np.array([float(tile_col), float(tile_row)], dtype=np.float64)
        tile_mat = np.array([
            [1.0, 0.0, offset[0]],
            [0.0, 1.0, offset[1]],
        ], dtype=np.float64)
        for island in islands:
            apply_island_transform(island, tile_mat, uv_layer)

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Packed {len(islands)} island(s) into tile {tile}")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_PackIslands,
    UVTK_OT_RepackWithOthers,
    UVTK_OT_PackToTile,
)
