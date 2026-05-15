# UV Toolkit

**All-in-one UV unwrapping, packing, and texel density addon for Blender 4.2+**

Free to use · [Support on Ko-fi](https://ko-fi.com/melioragroup) · GPL v3

---

## Features

### Mark & Unwrap
- **Mark Seams by Angle** — detect hard edges automatically with a configurable dihedral threshold
- **Mark by Open Edges** — seal boundary edges as seams in one click
- **Mark by UV Borders** — convert existing UV splits back into mesh seams
- **Mirror Seams** — propagate seams across X or Y symmetry axis
- **Smart Unwrap** — context-sensitive: selected faces become their own island, selected edges become seams, nothing selected unwraps the whole mesh
- **Quadrify** — straighten quad-based islands into a clean rectangular grid
- **Relax Organic** — angle-based stretch minimization for organic shapes

### Pack
- **MaxRects / BSSF packing** — the same algorithm family used by professional packers, achieving 85–95% UV utilization
- Optional island rotation at configurable degree steps (90°, 45°, custom)
- **Repack Selected** — pack only chosen islands into the remaining free space without moving others
- **UDIM support** — pack directly into any target tile (1001–1099+)

### Transform
- **Align** — left, right, top, bottom, center H/V
- **Distribute** — even spacing horizontally or vertically
- **World Orient** — rotate islands to match dominant world-space face direction
- **Flip** H / V, **Rotate** by arbitrary angle, **Fit to UV Space**
- **Stack / Unstack** — overlap identical islands or spread them apart
- **Randomize** — random position, rotation, and scale (useful for tileable textures)

### Texel Density
- **Get from Active** — read the texel density of the active island into the target field
- **Set Selected** — scale all selected islands to a target TD (px/m)
- **Normalize All** — make every island share the same average TD
- **Copy to Selected** — propagate the active island's density to the rest of the selection

### Select
- **Overlapping** — two-phase AABB broad + SAT narrow detection
- **Flipped** — islands with negative UV winding
- **Stretched** — islands whose UV/3D area ratio deviates beyond a threshold
- **Similar** — islands matching the active island's area within 10%

### Finish Tracking
- Tag islands as **Finished** or **Unfinished** with configurable overlay colors
- Select all finished or unfinished islands to review progress across complex meshes

---

## Installation

### Blender Extensions (recommended, 4.2+)

1. Download **`uv_toolkit-1.0.0.zip`** from [Releases](https://github.com/pedcorr/uv-toolkit/releases)
2. Open Blender → *Edit › Preferences › Get Extensions*
3. Click the dropdown arrow (top-right) → **Install from Disk**
4. Select the zip — the addon appears immediately under *Installed*

### Legacy Add-on Install

1. Download **`uv_toolkit_legacy.zip`** from [Releases](https://github.com/pedcorr/uv-toolkit/releases)
2. Open Blender → *Edit › Preferences › Add-ons › Install*
3. Select the zip and enable **UV: UV Toolkit**

### From Source

```
git clone https://github.com/pedcorr/uv-toolkit.git
```

Symlink or copy the `uv_toolkit/` folder into your Blender scripts add-ons directory:

```
# Windows
%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\

# macOS / Linux
~/.config/blender/4.x/scripts/addons/
```

---

## Usage

After installation the **UV Toolkit** tab appears in the **N-panel of the UV Editor** (`N` key).

### Typical hard-surface workflow

1. Select your mesh, enter Edit Mode
2. **Mark & Unwrap** panel → set *Seam Angle* (66° is a good default) → **By Angle**
3. **Smart Unwrap** — Blender unwraps along the detected seams
4. **Pack** panel → **Pack All Islands** — MaxRects fills the UV space
5. **Texel Density** panel → **Get from Active** → **Set Selected** to match across all objects

### Organic workflow

1. Manually mark seams or use **Mark by Open Edges** on a sculpted mesh
2. **Smart Unwrap** → **Relax Organic** to minimize stretch
3. Check quality with **Select › Stretched** and re-relax problem islands
4. Pack and normalize TD as above

### Finish tracking

Tag islands as you go with **Tag Finished** (green by default). Use **Select Unfinished** at any time to see what's left — useful for large assets with hundreds of islands across multiple meshes.

---

## Requirements

| Blender | Status |
|---|---|
| 4.2 LTS | ✅ Supported |
| 4.5 LTS | ✅ Tested |
| 5.x | ✅ Forward compatible |

No external Python dependencies. Optional numpy acceleration is used automatically when available (bundled with Blender 3.x+).

---

## Architecture

```
uv_toolkit/
├── core/           # Pure-Python engine — no bpy imports at module level
│   ├── island.py   # BFS UV island extraction + affine transforms
│   ├── packer.py   # MaxRects / BSSF bin packing
│   ├── seam.py     # Seam detection and mirroring
│   ├── density.py  # Texel density math
│   ├── geometry.py # bbox, rotate, align, world_orient
│   └── overlap.py  # AABB broad-phase + SAT narrow-phase
├── operators/      # 34 bpy.types.Operator subclasses
├── panels/         # 6 IMAGE_EDITOR N-panel sections
└── properties.py   # UVTKProperties + AddonPreferences
```

The `core/` layer has no `bpy` dependency (except `geometry.py` and `seam.py` which need `mathutils`/`bmesh`), making the math independently testable outside Blender.

---

## Roadmap

**V1 (current)**
- All seam marking, smart unwrap, quadrify, relax
- MaxRects CPU packer
- Full transform suite
- Texel density, overlap/flipped/stretched selection
- Finished/Unfinished tracking

**V2** *(planned, subject to donation demand)*
- CUDA packing backend — parallel island placement on GPU
- Multi-tile UDIM packing
- StackIslands with shape-hash similarity detection
- Per-island rotation locking
- Full mirror-seams symmetry workflow

---

## Support

UV Toolkit is free. If it saves you time on a project, consider buying a coffee:

**[☕ Ko-fi — ko-fi.com/melioragroup](https://ko-fi.com/melioragroup)**

Bug reports and feature requests → [GitHub Issues](https://github.com/pedcorr/uv-toolkit/issues)

---

## License

GNU General Public License v3.0 — required for distribution on the Blender Extensions platform.
See [LICENSE](LICENSE) for the full text.
