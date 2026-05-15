"""UV Toolkit — Mark & Unwrap panel."""

import bpy


class UVTK_PT_SeamUnwrap(bpy.types.Panel):
    bl_label = "Mark & Unwrap"
    bl_idname = "UVTK_PT_seam_unwrap"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Toolkit"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        props = context.scene.uvtk

        # ── SEAM MARKING ────────────────────────────────────────────────────
        layout.label(text="Seam Marking", icon="SNAP_EDGE")

        # Seam angle controls
        box = layout.box()
        col = box.column(align=True)
        col.prop(props, "seam_angle", slider=True)
        col.separator(factor=0.5)
        row = col.row(align=True)
        row.prop(props, "mark_seams", toggle=True)
        row.prop(props, "mark_sharps", toggle=True)

        # Seam marking buttons
        box = layout.box()
        col = box.column(align=True)
        col.operator("uvtk.mark_seams_angle",      text="By Angle",      icon="MOD_EDGESPLIT")
        col.operator("uvtk.mark_seams_open",        text="Open Edges",    icon="SNAP_EDGE")
        col.operator("uvtk.mark_seams_uv_borders",  text="UV Borders",    icon="UV_DATA")
        col.operator("uvtk.clear_seams",            text="Clear All",     icon="X")

        # Mirror seams
        box = layout.box()
        box.label(text="Mirror Seams", icon="ARROW_LEFTRIGHT")
        row = box.row(align=True)
        op_x = row.operator("uvtk.mirror_seams", text="Mirror X", icon="MOD_MIRROR")
        op_x.axis = "X"
        op_y = row.operator("uvtk.mirror_seams", text="Mirror Y", icon="MOD_MIRROR")
        op_y.axis = "Y"

        layout.separator()

        # ── UNWRAP ──────────────────────────────────────────────────────────
        layout.label(text="Unwrap", icon="MOD_UVPROJECT")

        # Unwrap settings
        box = layout.box()
        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(props, "unwrap_method", expand=True)
        col.separator(factor=0.5)
        split = col.split(factor=0.5, align=True)
        split.prop(props, "fill_holes",      toggle=True)
        split.prop(props, "correct_aspect",  toggle=True)

        # Unwrap action buttons
        box = layout.box()
        col = box.column(align=True)
        col.operator("uvtk.smart_unwrap",    text="Smart Unwrap",     icon="UV_DATA")
        col.operator("uvtk.unwrap_selected", text="Unwrap Selected",  icon="FACESEL")
        col.operator("uvtk.quadrify",        text="Quadrify",         icon="SNAP_GRID")
        col.operator("uvtk.relax_organic",   text="Relax Organic",    icon="SMOOTHCURVE")
