# UV Toolkit — Blender Addon Architecture Spec
**Meliora Group | Free + Donations**

---

## Overview

A free, all-in-one UV unwrapping and packing addon for Blender that replaces the need to own both Zen UV and UV Packmaster. Distributed via Blender Extensions with a donation link. Built in pure Python with optional numpy acceleration for MVP; a CUDA packing backend planned for V2.

**Target Blender version:** 4.2+ (LTS) through 5.x  
**License:** GPL v3 (required by Blender Extensions platform)  
**Donation platform:** Ko-fi or Gumroad (name your price)

---

## Directory Structure

```
uv_toolkit/
├── __init__.py               # Addon metadata, bl_info, register/unregister
├── properties.py             # All PropertyGroups and AddonPreferences
├── panels/
│   ├── __init__.py
│   ├── panel_seam.py         # Mark / Unwrap panel
│   ├── panel_pack.py         # Pack panel
│   ├── panel_transform.py    # Island transform panel
│   ├── panel_select.py       # Selection tools panel
│   ├── panel_density.py      # Texel density panel
│   └── panel_finish.py       # Finished / Unfinished tracking panel
├── operators/
│   ├── __init__.py
│   ├── ops_seam.py           # Seam marking operators
│   ├── ops_unwrap.py         # Smart unwrap operators
│   ├── ops_pack.py           # Pack operators
│   ├── ops_transform.py      # Align, distribute, orient, quadrify
│   ├── ops_select.py         # Select overlapped/flipped/stretched/similar
│   ├── ops_density.py        # Texel density set/normalize/copy
│   └── ops_finish.py         # Tag finished/unfinished
├── core/
│   ├── __init__.py
│   ├── island.py             # UVIsland data class
│   ├── packer.py             # MaxRects bin packing algorithm
│   ├── seam.py               # Seam detection logic
│   ├── density.py            # Texel density math
│   ├── geometry.py           # UV geometry utilities (AABB, polygon ops)
│   └── overlap.py            # 2D polygon intersection tests
└── assets/
    └── icons/                # Optional custom icons (PNG, 32x32)
```

---

## `__init__.py`

```python
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

# Register all submodules in dependency order:
# properties → operators → panels
```

All operator and panel classes are collected via each subpackage's `__init__.py` into a flat `classes` list for a single `bpy.utils.register_class` pass.

---

## Properties (`properties.py`)

One `PropertyGroup` stored on the scene, accessed via `context.scene.uvtk`.

```python
class UVTKProperties(bpy.types.PropertyGroup):

    # --- Seam marking ---
    seam_angle: FloatProperty(name="Seam Angle", default=66.0, min=0, max=180,
                               description="Mark seams where face angle exceeds this value")
    mark_seams:  BoolProperty(name="Mark Seams", default=True)
    mark_sharps: BoolProperty(name="Mark Sharps", default=False)

    # --- Unwrap ---
    unwrap_method: EnumProperty(items=[
        ("ANGLE_BASED", "Angle Based", "More accurate, slower"),
        ("CONFORMAL",   "Conformal",   "Faster, good for hard surface"),
    ], default="ANGLE_BASED")
    fill_holes:    BoolProperty(name="Fill Holes", default=True)
    correct_aspect: BoolProperty(name="Correct Aspect", default=True)

    # --- Packing ---
    pack_margin:      FloatProperty(name="Margin", default=0.005, min=0, max=0.1)
    pack_rotate:      BoolProperty(name="Allow Rotation", default=True)
    pack_rotate_step: IntProperty(name="Rotation Step", default=90, min=1, max=90)
    pack_udim:        BoolProperty(name="UDIM Mode", default=False)
    pack_target_tile: IntProperty(name="Target Tile", default=1001)

    # --- Texel Density ---
    td_target:    FloatProperty(name="Target TD", default=512.0,
                                description="Texels per meter (e.g. 512 for 512px/m)")
    td_texture_size: IntProperty(name="Texture Size", default=1024, min=1)

    # --- Finished system ---
    finished_color:   FloatVectorProperty(name="Finished Color",
                                          subtype="COLOR", default=(0.0, 0.8, 0.2))
    unfinished_color: FloatVectorProperty(name="Unfinished Color",
                                          subtype="COLOR", default=(0.8, 0.2, 0.0))
```

---

## Core: Island Data (`core/island.py`)

The central data structure. Every operator works in terms of `UVIsland` objects extracted from BMesh.

```python
@dataclass
class UVIsland:
    loops: list          # BMLoop references
    faces: list          # BMFace references
    uvs:   np.ndarray    # Shape (N, 2), the UV coordinates
    area_3d: float       # Surface area in 3D space
    area_uv: float       # Area in UV space
    bbox: tuple          # (min_u, min_v, max_u, max_v)
    finished: bool       # Finished tag

def get_islands(bm, uv_layer) -> list[UVIsland]:
    """
    Walk the BMesh face graph to collect contiguous UV islands.
    Two faces are in the same island if they share a seam-free edge
    with matching UV coordinates at the shared loops.
    Returns a list of UVIsland objects.
    """

def apply_island_transform(island: UVIsland, matrix: np.ndarray, uv_layer):
    """Apply a 2x3 affine transform to all UV coords in the island."""
```

---

## Core: Seam Detection (`core/seam.py`)

```python
def mark_seams_by_angle(bm, angle_threshold_deg: float,
                         mark_seams: bool, mark_sharps: bool):
    """
    Iterate all interior edges.
    Compute the angle between the two adjacent face normals.
    If angle > threshold: mark as seam and/or sharp.
    O(E) where E = edge count.
    """

def mark_seams_by_open_edges(bm, mark_seams: bool, mark_sharps: bool):
    """Mark all boundary (open) edges as seams."""

def mark_seams_by_uv_borders(bm, uv_layer, mark_seams: bool):
    """
    Find edges where the two adjacent faces have discontinuous
    UV coordinates at the shared loops — i.e., existing UV splits.
    Mark those edges as seams.
    """

def clear_seams(bm):
    """Remove all seam and sharp flags from all edges."""

def mirror_seams(bm, axis: str):
    """Mirror seam placement across X or Y axis for symmetrical models."""
```

---

## Core: Packing Algorithm (`core/packer.py`)

Implements the **MaxRects** algorithm — the same family used by professional packers. Produces ~85–95% utilization on typical UV maps.

```python
class Rect:
    x: float; y: float; w: float; h: float

class MaxRectsPacker:
    """
    Bin packing using the MaxRects / BSSF (Best Short Side Fit) heuristic.
    Pure Python + numpy for MVP. Operates in normalized [0,1] UV space.

    Steps:
    1. Collect all island bounding boxes (w, h).
    2. If allow_rotation: also consider (h, w) variant per island.
    3. Sort islands by area descending (largest first).
    4. For each island, find the free rect that minimizes wasted space
       (Best Short Side Fit scores both dimensions, picks lowest score).
    5. Place island, split remaining free space into up to 2 new rects.
    6. Prune free rects that are fully contained inside other free rects.
    7. Apply margin/padding by inflating each island rect before placement.
    8. Scale all placed rects to fill [0,1] box.
    """

    def __init__(self, bin_w=1.0, bin_h=1.0, margin=0.005):
        ...

    def pack(self, islands: list[UVIsland], rotate_step=90) -> list[tuple]:
        """
        Returns list of (x, y, rotation_deg) placement for each island,
        in same order as input.
        """

    def _score_rect(self, free_rect: Rect, island_w, island_h) -> float:
        """BSSF score: min(short_side_leftover, long_side_leftover)."""

    def _split_free_rect(self, free_rect: Rect, placed: Rect) -> list[Rect]:
        """Guillotine split: produce up to 2 new free rects."""

    def _prune_contained(self):
        """Remove free rects fully covered by other free rects."""
```

**UDIM support:** Before packing, remap all island UVs to [0,1]. After packing, offset by tile column/row based on `pack_target_tile`.

**V2 CUDA path:** Replace `MaxRectsPacker.pack()` with a subprocess call to a compiled Forge/C extension that runs the same algorithm parallelized across GPU threads — each thread tests one (island, free_rect) placement candidate simultaneously.

---

## Core: Texel Density (`core/density.py`)

```python
def compute_texel_density(island: UVIsland, texture_size: int) -> float:
    """
    TD = (uv_area_in_texels) / (3d_surface_area_in_m²)
    uv_area_in_texels = island.area_uv * texture_size²
    Returns texels per meter.
    """

def set_texel_density(island: UVIsland, target_td: float,
                       texture_size: int, uv_layer):
    """
    Compute current TD, derive scale factor = target_td / current_td,
    scale island UVs uniformly around island center.
    """

def normalize_texel_density(islands: list[UVIsland],
                              texture_size: int, uv_layer):
    """
    Compute average TD across all islands.
    Scale each island so all islands share the same TD.
    Useful for consistent texture resolution across a model.
    """
```

---

## Core: Geometry Utilities (`core/geometry.py`)

```python
# All operate on numpy arrays for performance

def bbox(uvs: np.ndarray) -> tuple:
    """Return (min_u, min_v, max_u, max_v)."""

def island_center(uvs: np.ndarray) -> np.ndarray:
    """Return centroid of bounding box."""

def rotate_uvs(uvs: np.ndarray, angle_deg: float,
               pivot: np.ndarray) -> np.ndarray:
    """Rotate UV coords around pivot point."""

def align_to_axis(uvs: np.ndarray, axis: str) -> np.ndarray:
    """Rotate island so its longest edge aligns to U or V axis."""

def world_orient(island: UVIsland, obj) -> np.ndarray:
    """
    Rotate the UV island so it aligns with the dominant world-space
    direction of its faces (up = +Y in UV).
    Uses the average face normal projected onto world Z.
    """
```

---

## Core: Overlap Detection (`core/overlap.py`)

```python
def find_overlapping_islands(islands: list[UVIsland]) -> list[int]:
    """
    Two-phase detection:
    Phase 1: AABB broad phase — skip pairs whose bounding boxes don't overlap.
    Phase 2: Separating Axis Theorem (SAT) narrow phase for remaining pairs.
    Returns list of island indices that overlap at least one other island.
    O(N²) worst case but fast in practice due to AABB culling.
    """

def find_flipped_islands(islands: list[UVIsland]) -> list[int]:
    """
    A UV island is flipped if the signed area of its UV polygon is negative.
    signed_area = 0.5 * sum((u[i+1]-u[i]) * (v[i+1]+v[i]))
    Returns indices of flipped islands.
    """

def find_stretched_islands(islands: list[UVIsland],
                            threshold=0.25) -> list[int]:
    """
    Stretch ratio = abs(uv_area / 3d_area - 1.0).
    Islands with ratio > threshold are considered stretched.
    """
```

---

## Operators

### Seam Operators (`operators/ops_seam.py`)

| Operator | idname | Description |
|---|---|---|
| MarkSeamsByAngle | `uvtk.mark_seams_angle` | Mark using scene angle threshold |
| MarkSeamsByOpenEdges | `uvtk.mark_seams_open` | Mark all boundary edges |
| MarkSeamsByUVBorders | `uvtk.mark_seams_uv_borders` | Seams from existing UV splits |
| MarkSelectedAsSeam | `uvtk.mark_selected_seam` | Manual mark selection |
| ClearSeams | `uvtk.clear_seams` | Remove all seams |
| MirrorSeams | `uvtk.mirror_seams` | Mirror seams across axis |

### Unwrap Operators (`operators/ops_unwrap.py`)

| Operator | idname | Description |
|---|---|---|
| SmartUnwrap | `uvtk.smart_unwrap` | Context-sensitive: selected faces → new island, no selection → whole mesh |
| UnwrapSelected | `uvtk.unwrap_selected` | Force unwrap selection only |
| Quadrify | `uvtk.quadrify` | Straighten quad-based islands into grid |
| RelaxOrganic | `uvtk.relax_organic` | Angle-based relax for organic shapes (wraps `uv.minimize_stretch`) |

**SmartUnwrap logic:**
```
if face selection mode and faces selected:
    mark borders of selection as seams
    unwrap whole mesh (new island created naturally)
elif edge selection mode and edges selected:
    mark selected edges as seams
    unwrap whole mesh
elif nothing selected:
    unwrap whole mesh using existing seams
```

### Pack Operators (`operators/ops_pack.py`)

| Operator | idname | Description |
|---|---|---|
| PackIslands | `uvtk.pack` | Run MaxRects packer on all/selected islands |
| RepackWithOthers | `uvtk.repack_with_others` | Repack selected, keep unselected in place |
| PackToTile | `uvtk.pack_to_tile` | Pack into specific UDIM tile |

### Transform Operators (`operators/ops_transform.py`)

| Operator | idname | Description |
|---|---|---|
| AlignIslands | `uvtk.align_islands` | Align to left/right/top/bottom/center |
| DistributeIslands | `uvtk.distribute_islands` | Even spacing H or V |
| WorldOrient | `uvtk.world_orient` | Orient by world-space face normals |
| RotateIsland | `uvtk.rotate_island` | Rotate by step (90/45/custom) |
| FlipIsland | `uvtk.flip_island` | Flip H or V |
| FitToUVSpace | `uvtk.fit_uv_space` | Scale island to fill [0,1] |
| StackIslands | `uvtk.stack_islands` | Stack identical islands on top of each other |
| UnstackIslands | `uvtk.unstack_islands` | Separate stacked islands |
| RandomizeIslands | `uvtk.randomize` | Random pos/rot/scale (tileable textures) |

### Select Operators (`operators/ops_select.py`)

| Operator | idname | Description |
|---|---|---|
| SelectOverlapping | `uvtk.select_overlapping` | Select overlapping islands |
| SelectFlipped | `uvtk.select_flipped` | Select flipped/inverted islands |
| SelectStretched | `uvtk.select_stretched` | Select islands above stretch threshold |
| SelectSimilar | `uvtk.select_similar` | Select islands with similar shape/area |

### Texel Density Operators (`operators/ops_density.py`)

| Operator | idname | Description |
|---|---|---|
| SetTexelDensity | `uvtk.td_set` | Set all/selected islands to target TD |
| NormalizeTD | `uvtk.td_normalize` | Match all islands to average TD |
| GetTexelDensity | `uvtk.td_get` | Read TD of active island into target field |
| CopyTD | `uvtk.td_copy` | Copy TD from active to selected islands |

### Finish Operators (`operators/ops_finish.py`)

| Operator | idname | Description |
|---|---|---|
| TagFinished | `uvtk.tag_finished` | Lock selected islands from re-unwrap |
| TagUnfinished | `uvtk.tag_unfinished` | Unlock islands |
| SelectFinished | `uvtk.select_finished` | Select all finished islands |
| SelectUnfinished | `uvtk.select_unfinished` | Select all unfinished islands |

Finished state is stored as a custom property on each BMFace: `face[uv_layer].tag`.

---

## UI Panels

All panels live in the **N panel of the UV Editor**, tab name `UV Toolkit`. Each section is a collapsible sub-panel using `bl_options = {"DEFAULT_CLOSED"}` where appropriate.

```
N Panel > UV Toolkit
├── [MARK & UNWRAP]
│   ├── Seam Angle slider
│   ├── ☑ Mark Seams  ☑ Mark Sharps
│   ├── [Mark by Angle] [Mark Open Edges] [Mark UV Borders]
│   ├── [Clear Seams] [Mirror Seams ▾ X Y]
│   ├── ─────────────
│   ├── Method: [Angle Based ▾]
│   ├── ☑ Fill Holes  ☑ Correct Aspect
│   └── [Smart Unwrap] [Quadrify] [Relax Organic]
│
├── [PACK]
│   ├── Margin: 0.005
│   ├── ☑ Allow Rotation   Step: 90°
│   ├── ☑ UDIM Mode        Tile: 1001
│   └── [Pack All] [Repack Selected] [Pack to Tile]
│
├── [TRANSFORM]
│   ├── Align: [◀][▶][▲][▼][↔][↕]
│   ├── Distribute: [H] [V]
│   ├── [World Orient] [Flip H] [Flip V]
│   ├── [Stack] [Unstack] [Randomize]
│   └── [Fit to UV Space]
│
├── [TEXEL DENSITY]
│   ├── Texture Size: 1024
│   ├── Target TD: 512.0 px/m
│   ├── [Get from Active]
│   └── [Set Selected] [Normalize All] [Copy to Selected]
│
├── [SELECT]
│   ├── [Overlapping] [Flipped] [Stretched]
│   └── [Similar Islands]
│
└── [FINISH TRACKING]
    ├── ● Finished  ● Unfinished  (color swatches)
    ├── [Tag Finished] [Tag Unfinished]
    └── [Select Finished] [Select Unfinished]
```

---

## Registration Pattern

```python
# Each subpackage exposes a `classes` tuple
# __init__.py collects them all:

from .operators import classes as op_classes
from .panels    import classes as panel_classes
from .properties import classes as prop_classes

all_classes = prop_classes + op_classes + panel_classes

def register():
    for cls in all_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.uvtk = bpy.props.PointerProperty(type=UVTKProperties)

def unregister():
    for cls in reversed(all_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.uvtk
```

---

## BMesh Usage Pattern

All operators follow the same safe BMesh pattern:

```python
class UVTK_OT_SomeOperator(bpy.types.Operator):
    bl_idname  = "uvtk.some_op"
    bl_label   = "Some Op"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj.mode != "EDIT":
            self.report({"ERROR"}, "Must be in Edit Mode")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        islands = get_islands(bm, uv_layer)

        # ... do work ...

        bmesh.update_edit_mesh(obj.data)
        return {"FINISHED"}
```

---

## V1 Scope (Ship This)

- All seam marking operators
- SmartUnwrap + Quadrify + RelaxOrganic
- MaxRects packer (CPU, pure Python + numpy)
- Full alignment / transform tools
- Texel density (set, normalize, copy, get)
- Overlap / flipped / stretched selection
- Finished/Unfinished tagging system
- Clean N-panel UI

## V2 Scope (After Donations Validate Demand)

- CUDA packing backend (Forge C extension, subprocess call)
- UDIM multi-tile packing
- StackIslands (similar island detection via shape hash)
- Per-island rotation locking
- Mirror seams (full symmetry workflow)
- World Orient

---

## Distribution

- **Blender Extensions** (extensions.blender.org) — primary channel, requires GPL v3 and a manifest `blender_manifest.toml`
- **GitHub** — source of truth, issues, changelog
- **Ko-fi donation link** in the addon preferences panel and README
- **YouTube** — one tutorial video at launch covers the full workflow; algorithm for organic vs hard surface is the hook

### `blender_manifest.toml` (required for Extensions platform)
```toml
schema_version = "1.0.0"
id             = "uv_toolkit"
version        = "1.0.0"
name           = "UV Toolkit"
tagline        = "All-in-one UV unwrapping, packing, and texel density"
maintainer     = "Meliora Group <hello@meliora.group>"
type           = "add-on"
blender_version_min = "4.2.0"
license        = ["SPDX:GPL-3.0-or-later"]
[build]
paths_exclude_pattern = ["*.pyc", "__pycache__", ".git"]
```
