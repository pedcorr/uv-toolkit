"""UV Toolkit core engine — overlap, flip, and stretch detection.

Uses a two-phase broad/narrow approach for overlap detection:
  - Broad phase:  AABB (axis-aligned bounding box) intersection test — O(N²).
  - Narrow phase: SAT (Separating Axis Theorem) per-polygon test.

``bpy`` is intentionally **not** imported at module level so this module can
be exercised in unit tests outside Blender.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .island import UVIsland


# ---------------------------------------------------------------------------
# SAT helpers
# ---------------------------------------------------------------------------

def _get_polygon_axes(poly: np.ndarray) -> np.ndarray:
    """Return the edge-normal axes for a convex polygon.

    For each edge (v_i, v_{i+1}) the outward normal is computed as the
    left-perpendicular of the edge direction vector.  The axes are returned
    as unit vectors of shape (N, 2).

    Parameters
    ----------
    poly:
        Polygon vertices, shape (N, 2).  Need not be convex for the axis
        computation itself, but SAT correctness requires convexity.
    """
    edges = np.roll(poly, -1, axis=0) - poly          # (N, 2)
    # Left-perpendicular: (dx, dy) -> (-dy, dx)
    normals = np.stack([-edges[:, 1], edges[:, 0]], axis=1)  # (N, 2)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    # Avoid division by zero for degenerate edges.
    lengths = np.where(lengths < 1e-12, 1.0, lengths)
    return normals / lengths


def _project_polygon(poly: np.ndarray, axis: np.ndarray) -> tuple:
    """Project *poly* onto *axis* and return (min, max) of the projection.

    Parameters
    ----------
    poly:
        Shape (N, 2).
    axis:
        Unit vector, shape (2,).
    """
    projections = poly @ axis  # dot product of each vertex with axis
    return float(projections.min()), float(projections.max())


def _sat_polygons_overlap(poly_a: np.ndarray, poly_b: np.ndarray) -> bool:
    """Return True when *poly_a* and *poly_b* overlap using SAT.

    Tests all edge-normal axes from both polygons.  If a separating axis is
    found the polygons do not overlap.

    Parameters
    ----------
    poly_a, poly_b:
        Convex polygon vertex arrays of shape (M, 2) and (K, 2).

    Notes
    -----
    For non-convex islands the polygon is used as-is.  This may produce false
    negatives (missed overlaps in concave regions) but never false positives,
    keeping the result conservative.
    """
    axes_a = _get_polygon_axes(poly_a)   # (M, 2)
    axes_b = _get_polygon_axes(poly_b)   # (K, 2)
    all_axes = np.vstack([axes_a, axes_b])  # (M+K, 2)

    for axis in all_axes:
        min_a, max_a = _project_polygon(poly_a, axis)
        min_b, max_b = _project_polygon(poly_b, axis)

        # Separating axis found — no overlap.
        if max_a <= min_b or max_b <= min_a:
            return False

    # No separating axis found — polygons overlap.
    return True


def _get_island_outline(island: "UVIsland") -> np.ndarray:
    """Return a representative convex hull polygon for *island*.

    We compute the convex hull of all UV points using a simple gift-wrapping
    approach so that SAT (which requires convex polygons) can be applied.
    Falls back to the raw UV array when fewer than 3 points exist.

    Returns
    -------
    np.ndarray
        Shape (K, 2) convex hull vertices in counter-clockwise order.
    """
    uvs = island.uvs
    if len(uvs) < 3:
        return uvs

    return _convex_hull(uvs)


def _convex_hull(points: np.ndarray) -> np.ndarray:
    """Compute the convex hull of *points* using the Gift-Wrapping algorithm.

    Returns the hull vertices in counter-clockwise order.  If all points are
    collinear the function returns the two extreme points.

    Parameters
    ----------
    points:
        Shape (N, 2) array of 2-D points.
    """
    pts = np.unique(points, axis=0)  # remove exact duplicates
    n = len(pts)
    if n < 3:
        return pts

    # Start from the leftmost (then bottom-most) point.
    start_idx = int(np.lexsort((pts[:, 1], pts[:, 0]))[0])
    hull_indices = []
    current = start_idx

    while True:
        hull_indices.append(current)
        # Find the point that is most counter-clockwise from current.
        candidate = (current + 1) % n
        for i in range(n):
            if i == current:
                continue
            # Cross product of (candidate - current) and (i - current).
            ax = pts[candidate, 0] - pts[current, 0]
            ay = pts[candidate, 1] - pts[current, 1]
            bx = pts[i, 0] - pts[current, 0]
            by = pts[i, 1] - pts[current, 1]
            cross = ax * by - ay * bx
            if cross < 0:
                # i is more counter-clockwise than candidate.
                candidate = i
            elif cross == 0:
                # Collinear — prefer the farther point.
                dist_cand = ax * ax + ay * ay
                dist_i = bx * bx + by * by
                if dist_i > dist_cand:
                    candidate = i

        current = candidate
        if current == start_idx:
            break

        # Safety guard against infinite loops on degenerate input.
        if len(hull_indices) > n:
            break

    return pts[hull_indices]


# ---------------------------------------------------------------------------
# AABB broad-phase helper
# ---------------------------------------------------------------------------

def _aabbs_overlap(bbox_a: tuple, bbox_b: tuple) -> bool:
    """Return True when two AABBs share area.

    Parameters
    ----------
    bbox_a, bbox_b:
        (min_u, min_v, max_u, max_v) tuples.
    """
    min_u_a, min_v_a, max_u_a, max_v_a = bbox_a
    min_u_b, min_v_b, max_u_b, max_v_b = bbox_b
    return (
        max_u_a > min_u_b
        and max_u_b > min_u_a
        and max_v_a > min_v_b
        and max_v_b > min_v_a
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_overlapping_islands(islands: List["UVIsland"]) -> List[int]:
    """Return the indices of islands that overlap at least one other island.

    Detection is two-phase:

    1. **Broad phase** — axis-aligned bounding box test O(N²).
    2. **Narrow phase** — Separating Axis Theorem on convex hulls.

    Parameters
    ----------
    islands:
        List of :class:`~uv_toolkit.core.island.UVIsland` objects.

    Returns
    -------
    list[int]
        Sorted list of island indices (into *islands*) that participate in
        at least one overlap.
    """
    n = len(islands)
    overlapping: set[int] = set()

    # Pre-compute convex hulls once per island.
    hulls = [_get_island_outline(isl) for isl in islands]

    for i in range(n):
        for j in range(i + 1, n):
            # Broad phase.
            if not _aabbs_overlap(islands[i].bbox, islands[j].bbox):
                continue

            # Narrow phase — SAT.
            hull_i = hulls[i]
            hull_j = hulls[j]

            # Need at least 2 vertices on each side to form axes.
            if len(hull_i) < 2 or len(hull_j) < 2:
                # Degenerate — fall back to AABB result.
                overlapping.add(i)
                overlapping.add(j)
                continue

            if _sat_polygons_overlap(hull_i, hull_j):
                overlapping.add(i)
                overlapping.add(j)

    return sorted(overlapping)


def find_flipped_islands(islands: List["UVIsland"]) -> List[int]:
    """Return the indices of islands whose UV winding is reversed (flipped).

    A flipped island has a negative signed area when the UV loops are
    traversed in the order stored in the mesh.  The signed area is computed
    using the shoelace formula aggregated over every face of the island.

    The shoelace signed area for a polygon with vertices (u_i, v_i) is::

        A = 0.5 * Σ (u_i * v_{i+1} - u_{i+1} * v_i)

    A negative result means the polygon is wound clockwise (flipped in UV
    space).

    Parameters
    ----------
    islands:
        List of :class:`~uv_toolkit.core.island.UVIsland` objects.

    Returns
    -------
    list[int]
        Sorted list of indices of flipped islands.
    """
    flipped: List[int] = []

    for idx, island in enumerate(islands):
        uvs = island.uvs
        if len(uvs) < 3:
            continue

        # Shoelace sum over all UV vertices in sequence (per-face ordering is
        # preserved in island.loops / island.uvs).
        u = uvs[:, 0]
        v = uvs[:, 1]
        # Cross-term: Σ (u_i * v_{i+1} - u_{i+1} * v_i)
        signed_area = float(
            np.dot(u, np.roll(v, -1)) - np.dot(np.roll(u, -1), v)
        ) * 0.5

        if signed_area < 0.0:
            flipped.append(idx)

    return flipped


def find_stretched_islands(
    islands: List["UVIsland"],
    threshold: float = 0.25,
) -> List[int]:
    """Return the indices of islands with significant UV stretch.

    Stretch is measured as::

        stretch_ratio = |area_uv / area_3d - 1.0|

    This compares the normalised UV area to the normalised 3-D area.  When
    both are equal (no stretch) the ratio is 0.  A threshold of 0.25 means
    more than 25 % deviation.

    Islands with ``area_3d == 0`` are skipped (degenerate geometry).

    Parameters
    ----------
    islands:
        List of :class:`~uv_toolkit.core.island.UVIsland` objects.
    threshold:
        Stretch ratio above which an island is considered stretched.
        Default is 0.25 (25 %).

    Returns
    -------
    list[int]
        Sorted list of indices of stretched islands.
    """
    stretched: List[int] = []

    for idx, island in enumerate(islands):
        if island.area_3d <= 0.0:
            continue
        if island.area_uv <= 0.0:
            # Zero UV area but non-zero 3-D area — maximally stretched.
            stretched.append(idx)
            continue

        stretch_ratio = abs(island.area_uv / island.area_3d - 1.0)
        if stretch_ratio > threshold:
            stretched.append(idx)

    return stretched
