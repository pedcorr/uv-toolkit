"""UV Toolkit core engine — seam and sharp-edge utilities.

All functions accept a live BMesh object and mutate it in place.
``bmesh`` and ``math`` are imported at module level.
"""

from __future__ import annotations

import math

import bmesh  # noqa: F401  (used via bm argument — imported for completeness)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _edge_midpoint(edge) -> tuple:
    """Return the (x, y, z) midpoint of a BMEdge."""
    co_a = edge.verts[0].co
    co_b = edge.verts[1].co
    return (
        (co_a.x + co_b.x) * 0.5,
        (co_a.y + co_b.y) * 0.5,
        (co_a.z + co_b.z) * 0.5,
    )


def _midpoint_distance_sq(mid_a: tuple, mid_b: tuple) -> float:
    """Squared Euclidean distance between two 3-D midpoints."""
    return (
        (mid_a[0] - mid_b[0]) ** 2
        + (mid_a[1] - mid_b[1]) ** 2
        + (mid_a[2] - mid_b[2]) ** 2
    )


def _uv_key(loop, uv_layer) -> tuple:
    """Return a rounded (u, v) tuple for dict-key usage."""
    uv = loop[uv_layer].uv
    return (round(uv.x, 6), round(uv.y, 6))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mark_seams_by_angle(
    bm,
    angle_threshold_deg: float,
    mark_seams: bool,
    mark_sharps: bool,
) -> None:
    """Mark interior edges as seams and/or sharp based on dihedral angle.

    Iterates every edge that has exactly two linked faces (interior edge).
    Computes the angle between the two adjacent face normals using the dot
    product.  If the angle exceeds *angle_threshold_deg*, the edge is marked
    as a UV seam and/or a sharp edge according to the flags.

    Complexity: O(E) — one pass over all edges.

    Parameters
    ----------
    bm:
        Live BMesh.
    angle_threshold_deg:
        Dihedral angle threshold in degrees.  Edges with a face-normal angle
        strictly greater than this value will be marked.
    mark_seams:
        When True, qualifying edges are flagged as UV seams.
    mark_sharps:
        When True, qualifying edges are flagged as sharp (``use_smooth=False``
        on the underlying MEdge after ``bmesh.update_edit_mesh`` is called).
    """
    threshold_rad = math.radians(angle_threshold_deg)

    for edge in bm.edges:
        linked = edge.link_faces
        if len(linked) != 2:
            # Boundary or non-manifold edge — skip.
            continue

        normal_a = linked[0].normal
        normal_b = linked[1].normal

        # Clamp dot product to [-1, 1] to guard against floating-point drift.
        dot = max(-1.0, min(1.0, normal_a.dot(normal_b)))
        angle = math.acos(dot)

        if angle > threshold_rad:
            if mark_seams:
                edge.seam = True
            if mark_sharps:
                edge.smooth = False


def mark_seams_by_open_edges(bm, mark_seams: bool, mark_sharps: bool) -> None:
    """Mark all boundary (open) edges as seams and/or sharp.

    A boundary edge is one with fewer than two linked faces (it lies on the
    geometric border of the mesh).

    Parameters
    ----------
    bm:
        Live BMesh.
    mark_seams:
        When True, boundary edges are flagged as UV seams.
    mark_sharps:
        When True, boundary edges are flagged as sharp.
    """
    for edge in bm.edges:
        if len(edge.link_faces) < 2:
            if mark_seams:
                edge.seam = True
            if mark_sharps:
                edge.smooth = False


def mark_seams_by_uv_borders(bm, uv_layer, mark_seams: bool) -> None:
    """Mark edges as seams wherever adjacent faces have discontinuous UVs.

    An edge is a UV border when the UV coordinates at its shared vertices
    differ between the two adjacent faces — i.e. the UV shell is split at
    that edge even if no explicit seam flag was set.

    Parameters
    ----------
    bm:
        Live BMesh.
    uv_layer:
        Active UV data layer (``bm.loops.layers.uv.active`` or similar).
    mark_seams:
        When True, UV-border edges are flagged as UV seams.
    """
    if not mark_seams:
        return

    for edge in bm.edges:
        linked = edge.link_faces
        if len(linked) != 2:
            continue

        face_a, face_b = linked[0], linked[1]
        shared_verts = {v for v in edge.verts}

        def uv_at_vert(face, vert):
            for loop in face.loops:
                if loop.vert is vert:
                    return _uv_key(loop, uv_layer)
            return None

        is_border = False
        for vert in shared_verts:
            uv_a = uv_at_vert(face_a, vert)
            uv_b = uv_at_vert(face_b, vert)
            if uv_a is None or uv_b is None or uv_a != uv_b:
                is_border = True
                break

        if is_border:
            edge.seam = True


def clear_seams(bm) -> None:
    """Remove all seam and sharp flags from every edge in the mesh.

    Parameters
    ----------
    bm:
        Live BMesh.
    """
    for edge in bm.edges:
        edge.seam = False
        edge.smooth = True  # smooth=True means "not sharp"


def mirror_seams(bm, axis: str) -> None:
    """Mirror seam placement across the X or Y axis for symmetrical models.

    For each edge that is already marked as a seam, the function finds the
    geometrically closest edge whose midpoint is the reflection of the
    original edge's midpoint across the chosen axis.  If such an edge is
    found within a small epsilon, it is also marked as a seam.

    The search is O(S × E) where S is the number of seam edges and E is the
    total number of edges, which is acceptable for typical mesh sizes.  For
    very large meshes a spatial lookup structure could be used instead.

    Parameters
    ----------
    bm:
        Live BMesh.
    axis:
        ``'X'`` to mirror across the X axis (negate Y), or
        ``'Y'`` to mirror across the Y axis (negate X).
    """
    if axis not in ('X', 'Y'):
        raise ValueError(f"axis must be 'X' or 'Y', got {axis!r}")

    # Tolerance: if the closest candidate midpoint is further away than this
    # (squared), we consider there to be no matching mirrored edge.
    EPSILON_SQ = 1e-8

    # Collect seam edges and build a full midpoint list for lookup.
    seam_edges = [e for e in bm.edges if e.seam]
    all_edges = list(bm.edges)
    all_midpoints = [_edge_midpoint(e) for e in all_edges]

    edges_to_mark = []

    for seam_edge in seam_edges:
        mid = _edge_midpoint(seam_edge)

        # Reflect midpoint across the chosen axis.
        if axis == 'X':
            # Mirror across XZ plane: negate Y component.
            reflected = (mid[0], -mid[1], mid[2])
        else:
            # Mirror across YZ plane: negate X component.
            reflected = (-mid[0], mid[1], mid[2])

        # Find the closest edge midpoint to the reflected point.
        best_dist_sq = float('inf')
        best_edge = None

        for edge, edge_mid in zip(all_edges, all_midpoints):
            if edge is seam_edge:
                continue
            dist_sq = _midpoint_distance_sq(reflected, edge_mid)
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_edge = edge

        if best_edge is not None and best_dist_sq <= EPSILON_SQ:
            edges_to_mark.append(best_edge)

    # Apply seam flags after the search loop to avoid interfering with it.
    for edge in edges_to_mark:
        edge.seam = True
