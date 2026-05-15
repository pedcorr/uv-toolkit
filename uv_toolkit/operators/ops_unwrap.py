"""UV Toolkit — Unwrap operators."""

from __future__ import annotations

import math

import bpy
import bmesh
import numpy as np
from mathutils import Vector

from ..core.island import get_islands, apply_island_transform


class UVTK_OT_SmartUnwrap(bpy.types.Operator):
    """Context-sensitive unwrap: uses selection state to decide strategy."""

    bl_idname = "uvtk.smart_unwrap"
    bl_label = "Smart Unwrap"
    bl_description = (
        "Smart unwrap: selected faces → isolate as island; "
        "selected edges → mark seams then unwrap; nothing → unwrap whole mesh"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)

        mesh_select_mode = context.tool_settings.mesh_select_mode  # (vert, edge, face)
        in_face_mode = mesh_select_mode[2]
        in_edge_mode = mesh_select_mode[1]

        selected_faces = [f for f in bm.faces if f.select]
        selected_edges = [e for e in bm.edges if e.select]

        if in_face_mode and selected_faces:
            # Mark the border edges of the selection as seams so the selection
            # becomes its own island, then unwrap the whole mesh.
            self._mark_face_selection_border_seams(bm, selected_faces)
        elif in_edge_mode and selected_edges:
            # Mark selected edges as seams then unwrap everything.
            for edge in selected_edges:
                edge.seam = True
        # else: use existing seams, unwrap whole mesh

        bmesh.update_edit_mesh(obj.data)

        # Select everything before unwrapping so the built-in op processes the mesh.
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.unwrap(
            method=props.unwrap_method,
            fill_holes=props.fill_holes,
            correct_aspect=props.correct_aspect,
        )

        return {"FINISHED"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mark_face_selection_border_seams(bm, selected_faces):
        """Mark seams on edges that lie on the boundary of the selected face set."""
        selected_face_set = set(selected_faces)
        for face in selected_faces:
            for edge in face.edges:
                # A boundary edge has at least one adjacent face outside the selection.
                neighbor_faces = [f for f in edge.link_faces if f is not face]
                if any(nf not in selected_face_set for nf in neighbor_faces) or not neighbor_faces:
                    edge.seam = True


class UVTK_OT_UnwrapSelected(bpy.types.Operator):
    """Force-unwrap only the selected faces, ignoring the rest of the mesh."""

    bl_idname = "uvtk.unwrap_selected"
    bl_label = "Unwrap Selected"
    bl_description = "Unwrap only the currently selected faces"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        props = context.scene.uvtk
        bm = bmesh.from_edit_mesh(obj.data)

        selected_faces = [f for f in bm.faces if f.select]
        if not selected_faces:
            self.report({"WARNING"}, "No faces selected")
            return {"CANCELLED"}

        bmesh.update_edit_mesh(obj.data)

        bpy.ops.uv.unwrap(
            method=props.unwrap_method,
            fill_holes=props.fill_holes,
            correct_aspect=props.correct_aspect,
        )

        return {"FINISHED"}


class UVTK_OT_Quadrify(bpy.types.Operator):
    """Straighten quad-based UV islands into a regular grid."""

    bl_idname = "uvtk.quadrify"
    bl_label = "Quadrify Islands"
    bl_description = "Straighten quad islands into a rectangular grid layout"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        islands = get_islands(bm, uv_layer)
        selected_islands = [isl for isl in islands if any(f.select for f in isl.faces)]

        if not selected_islands:
            self.report({"WARNING"}, "No selected UV islands found")
            return {"CANCELLED"}

        # Attempt to use Blender's built-in follow_active_quads for each island.
        # We operate island-by-island: deselect all, select island, run operator.
        bm.faces.ensure_lookup_table()

        processed = 0
        for island in selected_islands:
            if not self._is_quad_island(island):
                continue

            # Deselect everything, then select this island's faces.
            for f in bm.faces:
                f.select = False
            for f in island.faces:
                f.select = True

            bmesh.update_edit_mesh(obj.data)

            try:
                bpy.ops.uv.follow_active_quads(mode="LENGTH_AVERAGE")
                processed += 1
            except RuntimeError:
                # Fallback: basic grid-mapping using the boundary walk.
                self._grid_map_island(island, uv_layer)
                bmesh.update_edit_mesh(obj.data)
                processed += 1

        # Restore original selection.
        for isl in selected_islands:
            for f in isl.faces:
                f.select = True

        bmesh.update_edit_mesh(obj.data)

        if processed == 0:
            self.report({"WARNING"}, "No quad islands found in selection")
        else:
            self.report({"INFO"}, f"Quadrified {processed} island(s)")

        return {"FINISHED"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_quad_island(island) -> bool:
        """Return True if every face in the island is a quad."""
        return all(len(f.loops) == 4 for f in island.faces)

    @staticmethod
    def _grid_map_island(island, uv_layer) -> None:
        """
        Fallback grid mapper for a quad island.

        Strategy:
        1. Find a corner face (fewest linked-island neighbours).
        2. Walk in row/column order using shared edges.
        3. Assign UVs on a regular unit grid.
        """
        if not island.faces:
            return

        face_set = set(island.faces)

        # Build adjacency: for each face, find neighbouring faces within the island.
        def island_neighbors(face):
            result = []
            for edge in face.edges:
                for lf in edge.link_faces:
                    if lf is not face and lf in face_set:
                        result.append((lf, edge))
            return result

        # Pick start face: fewest neighbours (likely a corner).
        start = min(island.faces, key=lambda f: len(island_neighbors(f)))

        # BFS to determine grid coordinates.
        from collections import deque
        grid_pos = {}  # face -> (col, row)
        grid_pos[start] = (0, 0)
        queue = deque([start])
        visited = {start}

        while queue:
            face = queue.popleft()
            col, row = grid_pos[face]
            for nb, shared_edge in island_neighbors(face):
                if nb in visited:
                    continue
                visited.add(nb)
                # Determine direction: use centroid offset.
                fc = face.calc_center_median()
                nc = nb.calc_center_median()
                dx = nc.x - fc.x
                dy = nc.y - fc.y
                dz = nc.z - fc.z
                # Project onto predominant axis.
                if abs(dx) >= abs(dy) and abs(dx) >= abs(dz):
                    grid_pos[nb] = (col + (1 if dx > 0 else -1), row)
                elif abs(dy) >= abs(dx) and abs(dy) >= abs(dz):
                    grid_pos[nb] = (col, row + (1 if dy > 0 else -1))
                else:
                    grid_pos[nb] = (col, row + (1 if dz > 0 else -1))
                queue.append(nb)

        if not grid_pos:
            return

        # Normalise so minimum is (0, 0).
        min_col = min(p[0] for p in grid_pos.values())
        min_row = min(p[1] for p in grid_pos.values())

        # Assign UVs: each face occupies a unit cell [col, col+1] x [row, row+1].
        for face in island.faces:
            if face not in grid_pos:
                continue
            col, row = grid_pos[face]
            col -= min_col
            row -= min_row

            loops = list(face.loops)
            # Assign corners: bottom-left, bottom-right, top-right, top-left
            corners = [
                (col,       row),
                (col + 1.0, row),
                (col + 1.0, row + 1.0),
                (col,       row + 1.0),
            ]
            for i, loop in enumerate(loops):
                loop[uv_layer].uv.x = corners[i % 4][0]
                loop[uv_layer].uv.y = corners[i % 4][1]


class UVTK_OT_RelaxOrganic(bpy.types.Operator):
    """Relax UVs for organic shapes using angle-based minimisation."""

    bl_idname = "uvtk.relax_organic"
    bl_label = "Relax Organic"
    bl_description = "Relax UV stretching for organic shapes using angle-based minimisation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bpy.ops.uv.minimize_stretch(fill_holes=True, iterations=0)

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_SmartUnwrap,
    UVTK_OT_UnwrapSelected,
    UVTK_OT_Quadrify,
    UVTK_OT_RelaxOrganic,
)
