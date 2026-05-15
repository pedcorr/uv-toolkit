"""UV Toolkit — Finish Tracking panel."""

import bpy


class UVTK_PT_Finish(bpy.types.Panel):
    bl_label = "Finish Tracking"
    bl_idname = "UVTK_PT_finish"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Toolkit"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        props = context.scene.uvtk

        layout.label(text="Island Tracking", icon="OUTLINER_OB_MESH")

        # ── Color swatches ───────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)

        row = col.row(align=True)
        row.label(text="Finished")
        row.prop(props, "finished_color", text="")

        row = col.row(align=True)
        row.label(text="Unfinished")
        row.prop(props, "unfinished_color", text="")

        # ── Tag actions ──────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)

        row = col.row(align=True)
        row.operator("uvtk.tag_finished",   text="Tag Finished",   icon="CHECKMARK")
        row.operator("uvtk.tag_unfinished", text="Tag Unfinished", icon="PANEL_CLOSE")

        col.separator(factor=0.5)

        row = col.row(align=True)
        row.operator("uvtk.select_finished",   text="Select Finished",   icon="RESTRICT_SELECT_OFF")
        row.operator("uvtk.select_unfinished", text="Select Unfinished", icon="RESTRICT_SELECT_ON")
