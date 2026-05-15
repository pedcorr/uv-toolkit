"""UV Toolkit — Transform panel."""

import bpy


class UVTK_PT_Transform(bpy.types.Panel):
    bl_label = "Transform"
    bl_idname = "UVTK_PT_transform"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Toolkit"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        props = context.scene.uvtk

        # ── ALIGN ────────────────────────────────────────────────────────────
        layout.label(text="Align", icon="ALIGN_CENTER")

        box = layout.box()
        # 3-column grid for the 6 alignment directions
        grid = box.grid_flow(row_major=True, columns=3, align=True, even_columns=True)
        op = grid.operator("uvtk.align_islands", text="Left",     icon="TRIA_LEFT")
        op.align_to = "LEFT"
        op = grid.operator("uvtk.align_islands", text="Right",    icon="TRIA_RIGHT")
        op.align_to = "RIGHT"
        op = grid.operator("uvtk.align_islands", text="Top",      icon="TRIA_UP")
        op.align_to = "TOP"
        op = grid.operator("uvtk.align_islands", text="Bottom",   icon="TRIA_DOWN")
        op.align_to = "BOTTOM"
        op = grid.operator("uvtk.align_islands", text="Center H", icon="ANCHOR_CENTER")
        op.align_to = "CENTER_H"
        op = grid.operator("uvtk.align_islands", text="Center V", icon="ANCHOR_CENTER")
        op.align_to = "CENTER_V"

        # ── DISTRIBUTE ───────────────────────────────────────────────────────
        layout.label(text="Distribute", icon="SNAP_MIDPOINT")

        row = layout.row(align=True)
        op = row.operator("uvtk.distribute_islands", text="Horizontal", icon="ALIGN_JUSTIFY")
        op.axis = "H"
        op = row.operator("uvtk.distribute_islands", text="Vertical",   icon="ALIGN_JUSTIFY")
        op.axis = "V"

        layout.separator()

        # ── ORIENT & FLIP ────────────────────────────────────────────────────
        layout.label(text="Orient & Flip", icon="ORIENTATION_GLOBAL")

        box = layout.box()
        col = box.column(align=True)

        # World orient + fit to UV space
        row = col.row(align=True)
        row.operator("uvtk.world_orient",  text="World Orient",   icon="WORLD")
        row.operator("uvtk.fit_uv_space",  text="Fit to UV",      icon="FULLSCREEN_ENTER")

        # Flip H / Flip V
        row = col.row(align=True)
        op = row.operator("uvtk.flip_island", text="Flip H", icon="ARROW_LEFTRIGHT")
        op.axis = "H"
        op = row.operator("uvtk.flip_island", text="Flip V", icon="SORT_DESC")
        op.axis = "V"

        # Angle + rotate button on same row; pass angle from scene prop to op
        col.separator(factor=0.5)
        row = col.row(align=True)
        row.prop(props, "rotate_angle")
        op = row.operator("uvtk.rotate_island", text="Rotate", icon="FILE_REFRESH")
        op.angle_deg = props.rotate_angle

        layout.separator()

        # ── STACK & DISTRIBUTE ───────────────────────────────────────────────
        layout.label(text="Stack & Distribute", icon="DUPLICATE")

        box = layout.box()
        col = box.column(align=True)
        col.operator("uvtk.stack_islands",   text="Stack Islands",   icon="DUPLICATE")
        col.operator("uvtk.unstack_islands", text="Unstack Islands", icon="UV_ISLANDSEL")
        col.operator("uvtk.randomize",       text="Randomize",       icon="RNDCURVE")
