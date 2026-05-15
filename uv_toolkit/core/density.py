"""UV Toolkit core engine — texel density computation and normalisation.

Texel density (TD) quantifies how many texels of a given texture resolution
cover one square metre of 3-D surface.

    TD = (area_uv * texture_size²) / area_3d   [texels / m²]

All functions accept :class:`~uv_toolkit.core.island.UVIsland` objects and
operate on their UV coordinates through the provided ``uv_layer``.
``bpy`` is intentionally **not** imported at module level so this module can
be exercised in unit tests outside Blender.
"""

from __future__ import annotations

import math
from typing import List, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .island import UVIsland


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_affine_scale(scale: float, pivot: np.ndarray) -> np.ndarray:
    """Return a 2×3 affine matrix that scales uniformly around *pivot*.

    The matrix encodes::

        u' = scale * (u - pivot_u) + pivot_u
        v' = scale * (v - pivot_v) + pivot_v

    which expands to::

        [[scale,    0, pivot_u * (1 - scale)],
         [   0, scale, pivot_v * (1 - scale)]]
    """
    tx = pivot[0] * (1.0 - scale)
    ty = pivot[1] * (1.0 - scale)
    return np.array(
        [[scale, 0.0,   tx],
         [0.0,   scale, ty]],
        dtype=np.float64,
    )


def _island_bbox_center(island: "UVIsland") -> np.ndarray:
    """Return the bounding-box centre of *island* as a (2,) numpy array."""
    min_u, min_v, max_u, max_v = island.bbox
    return np.array(
        [(min_u + max_u) * 0.5, (min_v + max_v) * 0.5],
        dtype=np.float64,
    )


def _apply_scale(island: "UVIsland", scale: float, uv_layer) -> None:
    """Scale *island* UVs uniformly around the island bounding-box centre.

    Updates ``island.uvs``, the ``uv_layer`` loop data, ``island.bbox``,
    and ``island.area_uv``.
    """
    # Lazy import to avoid a hard dependency on the island module at the
    # top level (allows unit testing geometry/density independently).
    from .island import apply_island_transform  # noqa: PLC0415

    pivot = _island_bbox_center(island)
    matrix = _build_affine_scale(scale, pivot)
    apply_island_transform(island, matrix, uv_layer)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_texel_density(island: "UVIsland", texture_size: int) -> float:
    """Compute the texel density of *island* in texels per square metre.

    Parameters
    ----------
    island:
        A :class:`~uv_toolkit.core.island.UVIsland` instance with valid
        ``area_uv`` and ``area_3d`` fields.
    texture_size:
        Edge length of the square texture in pixels (e.g. 1024, 2048, 4096).

    Returns
    -------
    float
        Texels per square metre, or 0.0 when ``area_3d`` is zero (degenerate
        geometry).
    """
    if island.area_3d <= 0.0:
        return 0.0
    return (island.area_uv * texture_size ** 2) / island.area_3d


def set_texel_density(
    island: "UVIsland",
    target_td: float,
    texture_size: int,
    uv_layer,
) -> None:
    """Scale *island* UVs so its texel density matches *target_td*.

    The scale factor is derived from::

        scale = sqrt(target_td / current_td)

    because both ``area_uv`` (and hence TD) scale with the **square** of the
    linear UV scale.  The island is scaled uniformly around its bounding-box
    centre.

    Parameters
    ----------
    island:
        The UV island to adjust.
    target_td:
        Desired texel density in texels per square metre.
    texture_size:
        Edge length of the square texture in pixels.
    uv_layer:
        Active UV data layer used to update loop UV coordinates.
    """
    current_td = compute_texel_density(island, texture_size)
    if current_td <= 0.0 or target_td <= 0.0:
        # Cannot scale a degenerate island or to a non-positive target.
        return

    # area_uv scales as scale², so TD scales as scale² too.
    scale = math.sqrt(target_td / current_td)
    _apply_scale(island, scale, uv_layer)


def normalize_texel_density(
    islands: List["UVIsland"],
    texture_size: int,
    uv_layer,
) -> None:
    """Scale all islands so they share the same average texel density.

    1. Compute the texel density of every island.
    2. Calculate the mean TD (ignoring islands with zero 3-D area).
    3. Set each valid island to that average TD using :func:`set_texel_density`.

    Parameters
    ----------
    islands:
        List of :class:`~uv_toolkit.core.island.UVIsland` objects to
        normalise.
    texture_size:
        Edge length of the square texture in pixels.
    uv_layer:
        Active UV data layer used to update loop UV coordinates.
    """
    if not islands:
        return

    densities = [compute_texel_density(isl, texture_size) for isl in islands]
    valid_densities = [td for td in densities if td > 0.0]

    if not valid_densities:
        return

    average_td = sum(valid_densities) / len(valid_densities)

    for island, td in zip(islands, densities):
        if td > 0.0:
            set_texel_density(island, average_td, texture_size, uv_layer)
