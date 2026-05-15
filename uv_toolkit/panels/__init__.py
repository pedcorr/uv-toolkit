"""UV Toolkit panels package — collects all panel classes for registration."""

from .panel_seam      import UVTK_PT_SeamUnwrap
from .panel_pack      import UVTK_PT_Pack
from .panel_transform import UVTK_PT_Transform
from .panel_select    import UVTK_PT_Select
from .panel_density   import UVTK_PT_Density
from .panel_finish    import UVTK_PT_Finish

classes = (
    UVTK_PT_SeamUnwrap,
    UVTK_PT_Pack,
    UVTK_PT_Transform,
    UVTK_PT_Select,
    UVTK_PT_Density,
    UVTK_PT_Finish,
)

__all__ = ["classes"]
