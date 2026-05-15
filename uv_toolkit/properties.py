"""UV Toolkit — PropertyGroup and AddonPreferences."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)
from bpy.types import AddonPreferences, PropertyGroup


class UVTKProperties(PropertyGroup):
    """All UI-bound properties for the UV Toolkit addon.

    Stored on the scene as ``context.scene.uvtk`` so every panel can
    access the same values regardless of which object or mode is active.
    """

    # --- Seam marking ---
    seam_angle: FloatProperty(
        name="Seam Angle",
        description="Mark seams where the angle between adjacent face normals exceeds this value (degrees)",
        default=66.0,
        min=0.0,
        max=180.0,
        subtype="NONE",
        unit="NONE",
        precision=1,
    )  # type: ignore

    mark_seams: BoolProperty(
        name="Mark Seams",
        description="Apply the seam flag to qualifying edges",
        default=True,
    )  # type: ignore

    mark_sharps: BoolProperty(
        name="Mark Sharps",
        description="Also apply the sharp flag to qualifying edges",
        default=False,
    )  # type: ignore

    # --- Unwrap ---
    unwrap_method: EnumProperty(
        name="Method",
        description="Algorithm used for UV unwrapping",
        items=[
            ("ANGLE_BASED", "Angle Based", "More accurate result, better for organic shapes"),
            ("CONFORMAL",   "Conformal",   "Faster, works well for hard-surface models"),
        ],
        default="ANGLE_BASED",
    )  # type: ignore

    fill_holes: BoolProperty(
        name="Fill Holes",
        description="Fill holes in the mesh before unwrapping",
        default=True,
    )  # type: ignore

    correct_aspect: BoolProperty(
        name="Correct Aspect",
        description="Correct UV aspect ratio based on the active image texture",
        default=True,
    )  # type: ignore

    # --- Packing ---
    pack_margin: FloatProperty(
        name="Margin",
        description="Amount of space to leave between UV islands after packing",
        default=0.005,
        min=0.0,
        max=0.1,
        precision=4,
        subtype="FACTOR",
    )  # type: ignore

    pack_rotate: BoolProperty(
        name="Allow Rotation",
        description="Permit islands to be rotated for a tighter pack",
        default=True,
    )  # type: ignore

    pack_rotate_step: IntProperty(
        name="Rotation Step",
        description="Degrees to step when testing island rotations (1–90)",
        default=90,
        min=1,
        max=90,
        subtype="FACTOR",
    )  # type: ignore

    pack_udim: BoolProperty(
        name="UDIM Mode",
        description="Pack islands into a specific UDIM tile instead of the 0–1 space",
        default=False,
    )  # type: ignore

    pack_target_tile: IntProperty(
        name="Target Tile",
        description="UDIM tile number to pack into (1001 = tile 0,0)",
        default=1001,
        min=1001,
    )  # type: ignore

    # --- Texel Density ---
    td_target: FloatProperty(
        name="Target TD",
        description="Desired texel density in texels per metre (e.g. 512 for 512 px/m)",
        default=512.0,
        min=0.001,
        precision=2,
    )  # type: ignore

    td_texture_size: IntProperty(
        name="Texture Size",
        description="Resolution of the reference texture in pixels (used to compute texel density)",
        default=1024,
        min=1,
    )  # type: ignore

    # --- Finish tracking ---
    finished_color: FloatVectorProperty(
        name="Finished Color",
        description="Overlay colour applied to islands that have been tagged as finished",
        subtype="COLOR",
        default=(0.0, 0.8, 0.2),
        min=0.0,
        max=1.0,
    )  # type: ignore

    unfinished_color: FloatVectorProperty(
        name="Unfinished Color",
        description="Overlay colour applied to islands that are not yet finished",
        subtype="COLOR",
        default=(0.8, 0.2, 0.0),
        min=0.0,
        max=1.0,
    )  # type: ignore

    # --- Transform ---
    rotate_angle: FloatProperty(
        name="Angle",
        description="Angle to rotate the selected UV island (degrees)",
        default=45.0,
        min=-360.0,
        max=360.0,
        precision=1,
    )  # type: ignore


# ---------------------------------------------------------------------------
# Addon Preferences
# ---------------------------------------------------------------------------

class UVTK_Preferences(AddonPreferences):
    """Addon-level preferences shown in Edit > Preferences > Add-ons."""

    bl_idname = __package__

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        col = box.column(align=True)
        col.label(text="UV Toolkit by Meliora Group", icon="UV_DATA")
        col.separator()
        col.label(text="If this addon saves you time, consider supporting its development:")
        col.separator()
        row = col.row()
        row.scale_y = 1.4
        row.operator(
            "wm.url_open",
            text="Support on Ko-fi",
            icon="FUND",
        ).url = "https://ko-fi.com/melioragroup"
        col.separator()
        col.label(text="Documentation & tutorials:", icon="HELP")
        col.operator(
            "wm.url_open",
            text="meliora.group/uv-toolkit",
            icon="URL",
        ).url = "https://meliora.group/uv-toolkit"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    UVTKProperties,
    UVTK_Preferences,
)
