"""UV Toolkit — Finished/Unfinished face-tagging operators.

Finished state is stored as a custom integer attribute on each BMFace using
a face integer layer named ``uvtk_finished``.  A value of 1 means finished;
0 (the default for new layers) means unfinished.
"""

from __future__ import annotations

import bpy
import bmesh


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _get_or_create_finish_layer(bm):
    """Return the ``uvtk_finished`` face-integer layer, creating it if absent."""
    layer = bm.faces.layers.int.get("uvtk_finished")
    if layer is None:
        layer = bm.faces.layers.int.new("uvtk_finished")
    return layer


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class UVTK_OT_TagFinished(bpy.types.Operator):
    """Tag the selected faces as finished."""

    bl_idname = "uvtk.tag_finished"
    bl_label = "Tag Finished"
    bl_description = "Mark selected faces as finished (value = 1)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        finish_layer = _get_or_create_finish_layer(bm)

        selected = [f for f in bm.faces if f.select]
        if not selected:
            self.report({"WARNING"}, "No faces selected")
            return {"CANCELLED"}

        for face in selected:
            face[finish_layer] = 1

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Tagged {len(selected)} face(s) as finished")
        return {"FINISHED"}


class UVTK_OT_TagUnfinished(bpy.types.Operator):
    """Remove the finished tag from selected faces."""

    bl_idname = "uvtk.tag_unfinished"
    bl_label = "Tag Unfinished"
    bl_description = "Mark selected faces as unfinished (value = 0)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        finish_layer = _get_or_create_finish_layer(bm)

        selected = [f for f in bm.faces if f.select]
        if not selected:
            self.report({"WARNING"}, "No faces selected")
            return {"CANCELLED"}

        for face in selected:
            face[finish_layer] = 0

        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Tagged {len(selected)} face(s) as unfinished")
        return {"FINISHED"}


class UVTK_OT_SelectFinished(bpy.types.Operator):
    """Select all faces tagged as finished."""

    bl_idname = "uvtk.select_finished"
    bl_label = "Select Finished"
    bl_description = "Select all faces that have been tagged as finished"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)

        # If the layer doesn't exist yet, nothing can be finished.
        finish_layer = bm.faces.layers.int.get("uvtk_finished")
        if finish_layer is None:
            self.report({"INFO"}, "No finished faces found (layer not initialised)")
            return {"FINISHED"}

        count = 0
        for face in bm.faces:
            if face[finish_layer] == 1:
                face.select = True
                count += 1
            else:
                face.select = False

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Selected {count} finished face(s)")
        return {"FINISHED"}


class UVTK_OT_SelectUnfinished(bpy.types.Operator):
    """Select all faces that are NOT tagged as finished."""

    bl_idname = "uvtk.select_unfinished"
    bl_label = "Select Unfinished"
    bl_description = "Select all faces that have not yet been tagged as finished"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)

        # If the layer doesn't exist, every face is effectively unfinished.
        finish_layer = bm.faces.layers.int.get("uvtk_finished")

        count = 0
        for face in bm.faces:
            if finish_layer is None or face[finish_layer] == 0:
                face.select = True
                count += 1
            else:
                face.select = False

        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data)
        self.report({"INFO"}, f"Selected {count} unfinished face(s)")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTK_OT_TagFinished,
    UVTK_OT_TagUnfinished,
    UVTK_OT_SelectFinished,
    UVTK_OT_SelectUnfinished,
)
