"""UV Toolkit core engine — MaxRects bin-packing algorithm.

Implements the Best Short Side Fit (BSSF) heuristic of the MaxRects
algorithm for packing UV islands into the [0, 1] UV tile.

Reference:
    Jukka Jylänki, "A Thousand Ways to Pack the Bin – A Practical
    Approach to Two-Dimensional Rectangle Bin Packing", 2010.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Rect:
    """Axis-aligned rectangle in normalised UV space."""
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    def area(self) -> float:
        return self.w * self.h

    def contains(self, other: "Rect") -> bool:
        """Return True when *other* is fully inside (or equal to) *self*."""
        return (
            self.x <= other.x
            and self.y <= other.y
            and self.x2 >= other.x2
            and self.y2 >= other.y2
        )

    def intersects(self, other: "Rect") -> bool:
        """Return True when *self* and *other* overlap (share area)."""
        return (
            self.x < other.x2
            and self.x2 > other.x
            and self.y < other.y2
            and self.y2 > other.y
        )


class MaxRectsPacker:
    """Bin packing using the MaxRects / BSSF heuristic.

    Pure Python (no numpy required).  Operates entirely in normalised
    [0, 1] UV space.  After all islands are placed the results are
    uniformly scaled so the tightest axis fills [0, 1].

    Parameters
    ----------
    bin_w, bin_h:
        Dimensions of the packing bin (default 1.0 × 1.0).
    margin:
        Gap to add around every island on each side.
    """

    def __init__(
        self,
        bin_w: float = 1.0,
        bin_h: float = 1.0,
        margin: float = 0.005,
    ) -> None:
        self.bin_w = bin_w
        self.bin_h = bin_h
        self.margin = margin
        self.free_rects: List[Rect] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def pack(
        self,
        islands: list,
        rotate_step: int = 90,
        occupied_rects: Optional[List[Tuple[float, float, float, float]]] = None,
    ) -> List[Tuple[float, float, float]]:
        """Pack *islands* and return placement tuples.

        Parameters
        ----------
        islands:
            List of :class:`~uv_toolkit.core.island.UVIsland` objects.
        rotate_step:
            Angle increment (degrees) to try when rotating islands.
            Pass 0 or 360 to disable rotation (only 0° is tried).
        occupied_rects:
            Optional list of (x, y, w, h) tuples for areas that are already
            occupied and must not be used (e.g. unselected islands during
            RepackWithOthers).

        Returns
        -------
        list of (x, y, rotation_deg)
            One entry per island **in input order**.  ``x`` and ``y`` are
            the bottom-left corner of the placed rectangle in [0, 1] UV
            space (after final scaling).  ``rotation_deg`` is the
            rotation that was applied to the island before placement.
        """
        if not islands:
            return []

        # Reset free-rect list for this pack run.
        self.free_rects = [Rect(0.0, 0.0, self.bin_w, self.bin_h)]

        # Carve out any pre-occupied regions so we never place inside them.
        if occupied_rects:
            for ox, oy, ow, oh in occupied_rects:
                occ = Rect(ox, oy, ow, oh)
                remaining: List[Rect] = []
                for fr in self.free_rects:
                    if fr.intersects(occ):
                        remaining.extend(self._split_free_rect_result(fr, occ))
                    else:
                        remaining.append(fr)
                self.free_rects = remaining
                self._prune_contained()

        # Build (island_index, width, height) tuples with margin applied.
        island_sizes: List[Tuple[int, float, float]] = []
        for idx, island in enumerate(islands):
            min_u, min_v, max_u, max_v = island.bbox
            w = (max_u - min_u) + 2.0 * self.margin
            h = (max_v - min_v) + 2.0 * self.margin
            if w <= 0.0:
                w = self.margin * 2.0
            if h <= 0.0:
                h = self.margin * 2.0
            island_sizes.append((idx, w, h))

        # Sort by area descending to improve packing efficiency.
        island_sizes.sort(key=lambda t: t[1] * t[2], reverse=True)

        # Placement results keyed by original island index.
        placements: dict[int, Tuple[float, float, float]] = {}

        # Rotation candidates: clamp to [1, 360] and derive step count.
        # rotate_step=0 or 360 → only try 0° (no rotation).
        _step = max(1, min(360, int(rotate_step)))
        n_rotations = max(1, 360 // _step)

        for original_idx, w, h in island_sizes:
            best_score = float('inf')
            best_rect: Optional[Rect] = None
            best_w = w
            best_h = h
            best_rotation = 0.0

            for step in range(n_rotations):
                angle = step * rotate_step

                # For 90°/270° we swap width and height.
                if step % 2 == 0:
                    rw, rh = w, h
                else:
                    rw, rh = h, w

                for free_rect in self.free_rects:
                    if rw <= free_rect.w and rh <= free_rect.h:
                        score = self._score_rect(free_rect, rw, rh)
                        if score < best_score:
                            best_score = score
                            best_rect = free_rect
                            best_w = rw
                            best_h = rh
                            best_rotation = float(angle)

            if best_rect is None:
                # Island did not fit — place at origin as a fallback.
                placements[original_idx] = (0.0, 0.0, 0.0)
                continue

            # Place the island.
            placed = Rect(best_rect.x, best_rect.y, best_w, best_h)
            self._split_free_rect(best_rect, placed)
            self.free_rects.remove(best_rect)
            self._prune_contained()

            placements[original_idx] = (placed.x, placed.y, best_rotation)

        # Determine the actual bounding box of all placements to scale into [0,1].
        if placements:
            # Build a lookup: island index -> (placed_w, placed_h) accounting
            # for any rotation swap that occurred during packing.
            size_by_idx: dict[int, Tuple[float, float]] = {}
            for t in island_sizes:
                orig_idx, iw, ih = t
                if orig_idx not in placements:
                    continue
                _px, _py, rot = placements[orig_idx]
                # Odd rotation steps (90°, 270°, …) swap width and height.
                if int(rot) % 180 != 0:
                    size_by_idx[orig_idx] = (ih, iw)
                else:
                    size_by_idx[orig_idx] = (iw, ih)

            max_x2 = max(
                placements[i][0] + size_by_idx[i][0]
                for i in placements
                if i in size_by_idx
            )
            max_y2 = max(
                placements[i][1] + size_by_idx[i][1]
                for i in placements
                if i in size_by_idx
            )

            scale = 1.0 / max(max_x2, max_y2, 1e-9)
        else:
            scale = 1.0

        # Return results in original island order.
        result: List[Tuple[float, float, float]] = []
        for idx in range(len(islands)):
            if idx in placements:
                px, py, rot = placements[idx]
                result.append((px * scale, py * scale, rot))
            else:
                result.append((0.0, 0.0, 0.0))

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_rect(self, free_rect: Rect, w: float, h: float) -> float:
        """Best Short Side Fit (BSSF) score.

        Returns the length of the shorter leftover side after placing a
        rectangle of size *w* × *h* into *free_rect*.  A lower score means a
        tighter fit.
        """
        leftover_w = free_rect.w - w
        leftover_h = free_rect.h - h
        return min(leftover_w, leftover_h)

    def _split_free_rect_result(self, free_rect: Rect, placed: Rect) -> List[Rect]:
        """Return new free rectangles produced by guillotine-splitting *free_rect*
        around *placed*.  Does not mutate :attr:`free_rects`.
        """
        new_rects: List[Rect] = []

        # Right of placed inside free_rect.
        if placed.x2 < free_rect.x2:
            new_rects.append(Rect(
                placed.x2,
                free_rect.y,
                free_rect.x2 - placed.x2,
                free_rect.h,
            ))

        # Above placed inside free_rect.
        if placed.y2 < free_rect.y2:
            new_rects.append(Rect(
                free_rect.x,
                placed.y2,
                free_rect.w,
                free_rect.y2 - placed.y2,
            ))

        # Left of placed inside free_rect.
        if placed.x > free_rect.x:
            new_rects.append(Rect(
                free_rect.x,
                free_rect.y,
                placed.x - free_rect.x,
                free_rect.h,
            ))

        # Below placed inside free_rect.
        if placed.y > free_rect.y:
            new_rects.append(Rect(
                free_rect.x,
                free_rect.y,
                free_rect.w,
                placed.y - free_rect.y,
            ))

        return new_rects

    def _split_free_rect(self, free_rect: Rect, placed: Rect) -> None:
        """Guillotine-split *free_rect* around *placed* and add the new free
        rectangles to :attr:`free_rects`.
        """
        self.free_rects.extend(self._split_free_rect_result(free_rect, placed))

    def _prune_contained(self) -> None:
        """Remove every free rectangle that is fully enclosed by another.

        After splitting, some free rectangles can become redundant because
        they are entirely contained within a larger one.  Keeping them
        generates unnecessary candidate placements.  This is O(F²) in the
        number of free rectangles, which remains fast for typical UV work.
        """
        to_remove: List[int] = []

        for i in range(len(self.free_rects)):
            for j in range(len(self.free_rects)):
                if i == j or i in to_remove:
                    continue
                # If rect j fully contains rect i, mark i for removal.
                if self.free_rects[j].contains(self.free_rects[i]):
                    to_remove.append(i)
                    break

        # Remove in reverse order to preserve indices.
        for idx in sorted(set(to_remove), reverse=True):
            del self.free_rects[idx]
