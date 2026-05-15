"""UV Toolkit — Select panel."""

import bpy


class UVTK_PT_Select(bpy.types.Panel):
    bl_label = "Select"
    bl_idname = "UVTK_PT_select"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Toolkit"
    bl_order = 3

    def draw(self, context):
        layout = self.layout

        layout.label(text="Select by Issue", icon="VIEWZOOM")

        box = layout.box()
        col = box.column(align=True)
        col.operator("uvtk.select_overlapping", text="Overlapping Islands", icon="SELECT_INTERSECT")
        col.operator("uvtk.select_flipped",     text="Flipped Islands",     icon="MOD_MIRROR")
        col.operator("uvtk.select_stretched",   text="Stretched Islands",   icon="FULLSCREEN_ENTER")
        col.operator("uvtk.select_similar",     text="Similar Islands",     icon="ZOOM_SELECTED")
