"""UV Toolkit core engine — UV-space geometry utilities.

All public functions operate on numpy arrays unless otherwise noted.
``bmesh`` and ``mathutils`` are imported at module level because this module
is tightly coupled to the Blender math library.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import bmesh  # noqa: F401  (imported for type completeness; not used directly here)
import mathutils
import numpy as np

if TYPE_CHECKING:
    from .island import UVIsland


# ---------------------------------------------------------------------------
# Basic UV geometry
# ---------------------------------------------------------------------------

def bbox(uvs: np.ndarray) -> tuple:
    """Return the axis-aligned bounding box of *uvs*.

    Parameters
    ----------
    uvs:
        Array of shape (N, 2).

    Returns
    -------
    tuple
        ``(min_u, min_v, max_u, max_v)``
    """
    if uvs.ndim != 2 or uvs.shape[1] != 2:
        raise ValueError(f"uvs must have shape (N, 2), got {uvs.shape}")
    min_uv = uvs.min(axis=0)
    max_uv = uvs.max(axis=0)
    return (float(min_uv[0]), float(min_uv[1]),
            float(max_uv[0]), float(max_uv[1]))


def island_center(uvs: np.ndarray) -> np.ndarray:
    """Return the centroid of the bounding box of *uvs*.

    Parameters
    ----------
    uvs:
        Array of shape (N, 2).

    Returns
    -------
    np.ndarray
        ``array([cx, cy])``
    """
    min_u, min_v, max_u, max_v = bbox(uvs)
    return np.array([(min_u + max_u) * 0.5, (min_v + max_v) * 0.5],
                    dtype=np.float64)


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

def rotate_uvs(uvs: np.ndarray, angle_deg: float, pivot: np.ndarray) -> np.ndarray:
    """Rotate UV coordinates around *pivot* by *angle_deg* degrees.

    Parameters
    ----------
    uvs:
        Array of shape (N, 2).
    angle_deg:
        Counter-clockwise rotation angle in degrees.
    pivot:
        Centre of rotation, shape (2,).

    Returns
    -------
    np.ndarray
        Rotated UV array of shape (N, 2).
    """
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    # 2×2 rotation matrix
    R = np.array([[cos_a, -sin_a],
                  [sin_a,  cos_a]], dtype=np.float64)
    centered = uvs - pivot
    rotated = centered @ R.T
    return rotated + pivot


# ---------------------------------------------------------------------------
# Axis alignment
# ---------------------------------------------------------------------------

def align_to_axis(uvs: np.ndarray, axis: str) -> np.ndarray:
    """Rotate *uvs* so the longest edge of the island aligns to U or V.

    The algorithm:
    1. Compute all edge vectors from consecutive UV pairs across all loops.
    2. Find the longest edge.
    3. Compute the angle that edge makes with the horizontal axis.
    4. Rotate all UV coords by the negative of that angle (aligning to U),
       or by ``90° - angle`` (aligning to V).

    Parameters
    ----------
    uvs:
        Array of shape (N, 2).  The points are assumed to form one or more
        closed polygons with consecutive vertices.
    axis:
        ``'U'`` to align the longest edge along the U (horizontal) axis, or
        ``'V'`` to align along the V (vertical) axis.

    Returns
    -------
    np.ndarray
        Rotated UV array of shape (N, 2).
    """
    if axis not in ('U', 'V'):
        raise ValueError(f"axis must be 'U' or 'V', got {axis!r}")

    if len(uvs) < 2:
        return uvs.copy()

    # Build edge vectors between consecutive UV pairs (closed polygon assumed).
    edges = np.roll(uvs, -1, axis=0) - uvs  # shape (N, 2)
    lengths = np.linalg.norm(edges, axis=1)  # shape (N,)

    if lengths.max() == 0.0:
        return uvs.copy()

    longest_idx = int(np.argmax(lengths))
    longest_edge = edges[longest_idx]

    # Angle of the longest edge from the U axis.
    edge_angle_deg = math.degrees(math.atan2(longest_edge[1], longest_edge[0]))

    if axis == 'U':
        # Rotate so the edge lies along U (0°).
        rotation_deg = -edge_angle_deg
    else:
        # Rotate so the edge lies along V (90°).
        rotation_deg = 90.0 - edge_angle_deg

    pivot = island_center(uvs)
    return rotate_uvs(uvs, rotation_deg, pivot)


# ---------------------------------------------------------------------------
# World-space orientation
# ---------------------------------------------------------------------------

def world_orient(island: "UVIsland", obj):
    """Return a 2×3 affine rotation matrix to align the island with the dominant
    world-space direction, or ``None`` when no meaningful rotation can be computed.

    The dominant direction is found by:
    1. Averaging all face normals of the island in object-local space.
    2. Transforming to world space via the inverse-transpose of ``matrix_world``.
    3. Projecting onto the world XY plane.
    4. Computing the angle from the projected normal to world +Y.
    5. Returning a rotation matrix around the island's bounding-box centre.

    Parameters
    ----------
    island:
        A :class:`~uv_toolkit.core.island.UVIsland` instance.
    obj:
        A Blender object whose ``matrix_world`` provides the object-to-world
        transform.

    Returns
    -------
    np.ndarray or None
        A (2, 3) affine matrix suitable for :func:`~uv_toolkit.core.island.apply_island_transform`,
        or ``None`` when the island has no faces or the normal has no XY component.
    """
    if not island.faces:
        return None

    # Average face normal in local space.
    avg_normal = mathutils.Vector((0.0, 0.0, 0.0))
    for face in island.faces:
        avg_normal += face.normal
    if avg_normal.length_squared < 1e-12:
        return None
    avg_normal.normalize()

    # Transform to world space using inverse-transpose of the 3×3 part.
    mat_world = obj.matrix_world
    normal_world = mat_world.to_3x3().inverted_safe().transposed() @ avg_normal
    normal_world.normalize()

    # Project onto the XY plane.
    proj = mathutils.Vector((normal_world.x, normal_world.y))
    if proj.length < 1e-6:
        return None
    proj.normalize()

    # Angle from +Y axis (CCW).
    angle_deg = math.degrees(math.atan2(proj.x, proj.y))

    pivot = island_center(island.uvs)

    # Build a 2×3 rotation matrix around pivot.
    a = math.radians(angle_deg)
    cos_a = math.cos(a)
    sin_a = math.sin(a)
    R = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float64)
    t = -R @ pivot + pivot
    return np.hstack([R, t.reshape(2, 1)])
