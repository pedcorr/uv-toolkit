"""UV Toolkit — Texel Density panel."""

import bpy


class UVTK_PT_Density(bpy.types.Panel):
    bl_label = "Texel Density"
    bl_idname = "UVTK_PT_density"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Toolkit"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        props = context.scene.uvtk

        layout.label(text="Texel Density", icon="TEXTURE_DATA")

        # ── Settings ─────────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)

        row = col.row(align=True)
        row.label(text="Texture Size (px)", icon="IMAGE_DATA")
        row.prop(props, "td_texture_size", text="")

        row = col.row(align=True)
        row.label(text="Target TD (px/m)", icon="DRIVER_DISTANCE")
        row.prop(props, "td_target", text="")

        col.separator(factor=0.5)
        col.operator("uvtk.td_get", text="Get from Active", icon="EYEDROPPER")

        layout.separator()

        # ── Actions ──────────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.operator("uvtk.td_set",       text="Set Selected",     icon="CHECKMARK")
        col.operator("uvtk.td_normalize", text="Normalize All",    icon="DRIVER_TRANSFORM")
        col.operator("uvtk.td_copy",      text="Copy to Selected", icon="COPYDOWN")
