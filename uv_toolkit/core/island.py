"""UV Toolkit core engine — island extraction and transformation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class UVIsland:
    """Represents a contiguous group of faces sharing a connected UV region.

    Attributes:
        loops:    All BMLoop objects whose UV coordinates belong to this island.
        faces:    All BMFace objects that make up this island.
        uvs:      UV coordinates of every loop, shape (N, 2), float64.
        area_3d:  Sum of 3-D face areas in object space (metres²).
        area_uv:  Absolute UV-space area computed via the shoelace formula.
        bbox:     (min_u, min_v, max_u, max_v) axis-aligned bounding box.
        finished: True when every face in the island is tagged (selected).
    """

    loops: List = field(default_factory=list)
    faces: List = field(default_factory=list)
    uvs: np.ndarray = field(default_factory=lambda: np.empty((0, 2), dtype=np.float64))
    area_3d: float = 0.0
    area_uv: float = 0.0
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    finished: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _uv_key(loop, uv_layer) -> Tuple[float, float]:
    """Return a rounded UV coordinate tuple suitable for use as a dict key."""
    uv = loop[uv_layer].uv
    return (round(uv.x, 6), round(uv.y, 6))


def _faces_share_uv_edge(face_a, face_b, shared_edge, uv_layer) -> bool:
    """Return True when *face_a* and *face_b* have matching UV coordinates at
    both endpoints of *shared_edge* (i.e. the edge is seam-free in UV space).

    We compare the UV values of the loops that belong to each face and touch
    each vertex of the shared edge.
    """
    verts = {v for v in shared_edge.verts}

    # Collect per-face UV values at the two shared vertices.
    def uv_at_vert(face, vert):
        for loop in face.loops:
            if loop.vert is vert:
                return _uv_key(loop, uv_layer)
        return None

    for vert in verts:
        uv_a = uv_at_vert(face_a, vert)
        uv_b = uv_at_vert(face_b, vert)
        if uv_a is None or uv_b is None or uv_a != uv_b:
            return False
    return True


def _shoelace_area(uvs: np.ndarray) -> float:
    """Compute the absolute area of a polygon from its UV vertices using the
    shoelace formula.  *uvs* has shape (N, 2).  Handles non-convex polygons
    and returns the absolute (unsigned) area.
    """
    if len(uvs) < 3:
        return 0.0
    x = uvs[:, 0]
    y = uvs[:, 1]
    # Sum of (x_i * y_{i+1} - x_{i+1} * y_i) over all edges (wrapping)
    signed = np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)
    return abs(signed) * 0.5


def _compute_face_uv_area(face, uv_layer) -> float:
    """Compute UV area of a single face using the shoelace formula."""
    uvs = np.array([[loop[uv_layer].uv.x, loop[uv_layer].uv.y]
                    for loop in face.loops], dtype=np.float64)
    return _shoelace_area(uvs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_islands(bm, uv_layer) -> List[UVIsland]:
    """Walk the BMesh face graph and collect contiguous UV islands.

    Two adjacent faces belong to the same island when they share an edge that
    is not a seam **and** the UV coordinates at both shared vertices are
    identical (within a small epsilon).  A BFS flood-fill is used so that the
    result is O(F + E).

    Parameters
    ----------
    bm:
        A BMesh object (already in edit mode, ensure_lookup_table called by
        the caller if index access is needed).
    uv_layer:
        The active UV data layer retrieved via ``bm.loops.layers.uv.active``.

    Returns
    -------
    list[UVIsland]
        One entry per contiguous UV island.
    """
    visited: set = set()
    islands: List[UVIsland] = []

    for start_face in bm.faces:
        if start_face in visited:
            continue

        # BFS flood-fill from start_face
        queue: deque = deque([start_face])
        visited.add(start_face)

        island_faces = []
        island_loops = []

        while queue:
            face = queue.popleft()
            island_faces.append(face)
            island_loops.extend(face.loops)

            for edge in face.edges:
                # Skip seam edges — they are UV island boundaries.
                if edge.seam:
                    continue

                for linked_face in edge.link_faces:
                    if linked_face is face or linked_face in visited:
                        continue
                    # Confirm UV continuity across this edge.
                    if _faces_share_uv_edge(face, linked_face, edge, uv_layer):
                        visited.add(linked_face)
                        queue.append(linked_face)

        # Build UV coordinate array for this island.
        uvs = np.array(
            [[loop[uv_layer].uv.x, loop[uv_layer].uv.y] for loop in island_loops],
            dtype=np.float64,
        )

        # Bounding box.
        if len(uvs):
            min_u, min_v = uvs.min(axis=0)
            max_u, max_v = uvs.max(axis=0)
            bbox = (float(min_u), float(min_v), float(max_u), float(max_v))
        else:
            bbox = (0.0, 0.0, 0.0, 0.0)

        # 3-D area: sum of individual face areas.
        area_3d = sum(f.calc_area() for f in island_faces)

        # UV area: sum shoelace over each face's UV polygon.
        area_uv = sum(_compute_face_uv_area(f, uv_layer) for f in island_faces)

        # finished: True if every face is tagged (selected).
        finished = all(f.select for f in island_faces)

        island = UVIsland(
            loops=island_loops,
            faces=island_faces,
            uvs=uvs,
            area_3d=float(area_3d),
            area_uv=float(area_uv),
            bbox=bbox,
            finished=finished,
        )
        islands.append(island)

    return islands


def apply_island_transform(island: UVIsland, matrix: np.ndarray, uv_layer) -> None:
    """Apply a 2×3 affine transform to all UV coordinates of *island* in place.

    The transform is applied as::

        [u', v'] = matrix[:, :2] @ [u, v] + matrix[:, 2]

    The ``uv_layer`` loop data is updated so Blender sees the new coordinates.
    After transformation, ``island.uvs``, ``island.bbox``, and
    ``island.area_uv`` are recalculated.

    Parameters
    ----------
    island:
        The UVIsland to transform.
    matrix:
        A (2, 3) numpy array representing the affine transformation::

            [[a, b, tx],
             [c, d, ty]]

    uv_layer:
        The active UV data layer.
    """
    if matrix.shape != (2, 3):
        raise ValueError(f"matrix must have shape (2, 3), got {matrix.shape}")

    A = matrix[:, :2]   # 2×2 linear part
    t = matrix[:, 2]    # 2   translation

    # Transform all stored UV coords at once.
    new_uvs = (island.uvs @ A.T) + t  # shape (N, 2)
    island.uvs = new_uvs

    # Write back to BMesh loop UV data.
    for i, loop in enumerate(island.loops):
        loop[uv_layer].uv.x = float(new_uvs[i, 0])
        loop[uv_layer].uv.y = float(new_uvs[i, 1])

    # Recalculate bounding box.
    min_u, min_v = new_uvs.min(axis=0)
    max_u, max_v = new_uvs.max(axis=0)
    island.bbox = (float(min_u), float(min_v), float(max_u), float(max_v))

    # Recalculate UV area (shoelace over per-face loop blocks).
    # We re-read per-face UV polygons from the updated loop data.
    total_area = 0.0
    loop_idx = 0
    for face in island.faces:
        n = len(face.loops)
        face_uvs = new_uvs[loop_idx: loop_idx + n]
        total_area += _shoelace_area(face_uvs)
        loop_idx += n
    island.area_uv = total_area
