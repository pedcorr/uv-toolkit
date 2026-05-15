"""UV Toolkit — Pack panel."""

import bpy


class UVTK_PT_Pack(bpy.types.Panel):
    bl_label = "Pack"
    bl_idname = "UVTK_PT_pack"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Toolkit"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        props = context.scene.uvtk

        layout.label(text="Packing", icon="PACKAGE")

        # ── Pack settings ────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)

        # Margin slider
        row = col.row(align=True)
        row.label(text="", icon="SNAP_GRID")
        row.prop(props, "pack_margin", slider=True)

        col.separator(factor=0.5)

        # Rotation row: checkbox + step (step is grayed when rotate is off)
        row = col.row(align=True)
        row.prop(props, "pack_rotate", toggle=True)
        sub = row.row(align=True)
        sub.enabled = props.pack_rotate
        sub.prop(props, "pack_rotate_step")

        col.separator(factor=0.5)

        # UDIM row: toggle + target tile (target grayed when UDIM is off)
        row = col.row(align=True)
        row.prop(props, "pack_udim", toggle=True)
        sub = row.row(align=True)
        sub.enabled = props.pack_udim
        sub.prop(props, "pack_target_tile")

        # ── Pack actions ─────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.operator("uvtk.pack",               text="Pack All Islands",   icon="PACKAGE")
        col.operator("uvtk.repack_with_others", text="Repack Selected",    icon="RESTRICT_SELECT_OFF")
        col.operator("uvtk.pack_to_tile",       text="Pack to UDIM Tile",  icon="GRID")
