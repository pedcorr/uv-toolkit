"""UV Toolkit operators package.

Imports all operator classes from each ops_*.py module and exposes them
as a single flat ``classes`` tuple for the top-level register/unregister pass.
"""

from __future__ import annotations

from .ops_seam import classes as _seam_classes
from .ops_unwrap import classes as _unwrap_classes
from .ops_pack import classes as _pack_classes
from .ops_transform import classes as _transform_classes
from .ops_select import classes as _select_classes
from .ops_density import classes as _density_classes
from .ops_finish import classes as _finish_classes

# Flat tuple of every operator class in dependency-safe import order.
classes: tuple = (
    *_seam_classes,
    *_unwrap_classes,
    *_pack_classes,
    *_transform_classes,
    *_select_classes,
    *_density_classes,
    *_finish_classes,
)

__all__ = ["classes"]
