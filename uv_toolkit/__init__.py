"""UV Toolkit — All-in-one UV unwrapping, packing, and texel density tools.

Meliora Group | https://meliora.group/uv-toolkit
License: GPL v3 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.html)
"""

bl_info = {
    "name": "UV Toolkit",
    "author": "Meliora Group",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "UV Editor > N Panel > UV Toolkit",
    "description": "All-in-one UV unwrapping, packing, and density tools",
    "category": "UV",
    "doc_url": "https://meliora.group/uv-toolkit",
    "support": "COMMUNITY",
}

import bpy
from bpy.props import PointerProperty

# Import each subpackage in dependency order:
#   properties  (no deps)
#   operators   (depends on core — already imported internally)
#   panels      (depends on operators for operator idnames)
from .properties import classes as _prop_classes
from .properties import UVTKProperties
from .operators  import classes as _op_classes
from .panels     import classes as _panel_classes

all_classes = _prop_classes + _op_classes + _panel_classes


def register() -> None:
    for cls in all_classes:
        bpy.utils.register_class(cls)

    # Attach the property group to every scene so any panel can access
    # `context.scene.uvtk` regardless of the active object or mode.
    bpy.types.Scene.uvtk = PointerProperty(type=UVTKProperties)


def unregister() -> None:
    del bpy.types.Scene.uvtk

    for cls in reversed(all_classes):
        bpy.utils.unregister_class(cls)
