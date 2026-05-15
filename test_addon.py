"""
UV Toolkit — Blender background-mode test script.
Run: blender --background --factory-startup --python test_addon.py

Tests:
  1. Addon import + registration (no syntax errors, all classes register)
  2. Operator idnames are all present in bpy.ops
  3. Core math functions (packer, density, overlap, geometry) run without errors
  4. Seam operators work on a real BMesh
  5. Pack operator runs on a cube
  6. Texel density get/set/normalize work
  7. Select operators (overlapping, flipped, stretched, similar) work
"""

import sys
import os
import traceback

ADDON_DIR = r"C:\Projects\UV_toolkit"
sys.path.insert(0, ADDON_DIR)

import bpy
import bmesh
import numpy as np

PASS = []
FAIL = []

def ok(name):
    PASS.append(name)
    print(f"  PASS  {name}")

def fail(name, exc=None):
    FAIL.append(name)
    msg = f"  FAIL  {name}"
    if exc:
        msg += f"\n        {exc}"
    print(msg)
    if exc:
        traceback.print_exc()

# ── 1. Import + register ─────────────────────────────────────────────────────
print("\n=== 1. Import & Register ===")
try:
    import uv_toolkit
    uv_toolkit.register()
    ok("addon import + register")
except Exception as e:
    fail("addon import + register", e)
    sys.exit(1)  # Cannot continue if registration fails

# ── 2. Operator idnames ──────────────────────────────────────────────────────
print("\n=== 2. Operator idnames ===")
EXPECTED_OPS = [
    "uvtk.mark_seams_angle", "uvtk.mark_seams_open", "uvtk.mark_seams_uv_borders",
    "uvtk.mark_selected_seam", "uvtk.clear_seams", "uvtk.mirror_seams",
    "uvtk.smart_unwrap", "uvtk.unwrap_selected", "uvtk.quadrify", "uvtk.relax_organic",
    "uvtk.pack", "uvtk.repack_with_others", "uvtk.pack_to_tile",
    "uvtk.align_islands", "uvtk.distribute_islands", "uvtk.world_orient",
    "uvtk.rotate_island", "uvtk.flip_island", "uvtk.fit_uv_space",
    "uvtk.stack_islands", "uvtk.unstack_islands", "uvtk.randomize",
    "uvtk.select_overlapping", "uvtk.select_flipped", "uvtk.select_stretched",
    "uvtk.select_similar",
    "uvtk.td_set", "uvtk.td_normalize", "uvtk.td_get", "uvtk.td_copy",
    "uvtk.tag_finished", "uvtk.tag_unfinished", "uvtk.select_finished",
    "uvtk.select_unfinished",
]
for idname in EXPECTED_OPS:
    mod, op = idname.split(".")
    if hasattr(getattr(bpy.ops, mod, None), op):
        ok(f"op: {idname}")
    else:
        fail(f"op: {idname}")

# ── 3. Core math unit tests ──────────────────────────────────────────────────
print("\n=== 3. Core math ===")

# Packer
try:
    from uv_toolkit.core.packer import MaxRectsPacker, Rect

    class FakeIsland:
        bbox = (0.1, 0.1, 0.5, 0.6)
        uvs = np.array([[0.1,0.1],[0.5,0.1],[0.5,0.6],[0.1,0.6]], dtype=np.float64)

    class FakeIsland2:
        bbox = (0.0, 0.0, 0.3, 0.3)
        uvs = np.array([[0,0],[0.3,0],[0.3,0.3],[0,0.3]], dtype=np.float64)

    packer = MaxRectsPacker(margin=0.005)
    results = packer.pack([FakeIsland(), FakeIsland2()], rotate_step=90)
    assert len(results) == 2, f"expected 2 placements, got {len(results)}"
    for x, y, r in results:
        assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0, f"placement out of [0,1]: {x},{y}"
    ok("packer.pack() — 2 islands, rotations enabled")

    # No-rotation path
    packer2 = MaxRectsPacker(margin=0.002)
    results2 = packer2.pack([FakeIsland(), FakeIsland2()], rotate_step=360)
    assert len(results2) == 2
    ok("packer.pack() — rotation disabled (rotate_step=360)")
except Exception as e:
    fail("packer", e)

# Geometry
try:
    from uv_toolkit.core.geometry import bbox, island_center, rotate_uvs, align_to_axis

    uvs = np.array([[0.1, 0.2], [0.4, 0.2], [0.4, 0.7], [0.1, 0.7]], dtype=np.float64)
    b = bbox(uvs)
    assert b == (0.1, 0.2, 0.4, 0.7), f"bbox wrong: {b}"
    ok("geometry.bbox()")

    c = island_center(uvs)
    assert abs(c[0] - 0.25) < 1e-6 and abs(c[1] - 0.45) < 1e-6, f"center wrong: {c}"
    ok("geometry.island_center()")

    rotated = rotate_uvs(uvs, 90.0, c)
    assert rotated.shape == uvs.shape
    ok("geometry.rotate_uvs(90°)")

    aligned = align_to_axis(uvs, 'U')
    assert aligned.shape == uvs.shape
    ok("geometry.align_to_axis()")
except Exception as e:
    fail("geometry", e)

# Density
try:
    from uv_toolkit.core.density import compute_texel_density

    class MockIsland:
        area_uv = 0.25  # 25% of UV space
        area_3d = 1.0   # 1 m²
        bbox = (0.0, 0.0, 0.5, 0.5)
        uvs = np.zeros((4, 2))

    td = compute_texel_density(MockIsland(), texture_size=1024)
    expected = 0.25 * 1024**2 / 1.0  # = 262144
    assert abs(td - expected) < 1.0, f"TD wrong: {td} vs {expected}"
    ok("density.compute_texel_density()")
except Exception as e:
    fail("density", e)

# Overlap
try:
    from uv_toolkit.core.overlap import (find_overlapping_islands,
                                          find_flipped_islands,
                                          find_stretched_islands)

    class Isl:
        def __init__(self, bbox, uvs, area_uv=0.1, area_3d=0.1):
            self.bbox = bbox
            self.uvs = np.array(uvs, dtype=np.float64)
            self.area_uv = area_uv
            self.area_3d = area_3d

    # Two non-overlapping islands
    a = Isl((0.0, 0.0, 0.3, 0.3), [[0,0],[0.3,0],[0.3,0.3],[0,0.3]])
    b = Isl((0.5, 0.5, 0.8, 0.8), [[0.5,0.5],[0.8,0.5],[0.8,0.8],[0.5,0.8]])
    assert find_overlapping_islands([a, b]) == [], "expected no overlap"
    ok("overlap.find_overlapping_islands() — no overlap")

    # Two overlapping islands
    c_isl = Isl((0.0, 0.0, 0.4, 0.4), [[0,0],[0.4,0],[0.4,0.4],[0,0.4]])
    d_isl = Isl((0.2, 0.2, 0.6, 0.6), [[0.2,0.2],[0.6,0.2],[0.6,0.6],[0.2,0.6]])
    ov = find_overlapping_islands([c_isl, d_isl])
    assert set(ov) == {0, 1}, f"expected both overlapping, got {ov}"
    ok("overlap.find_overlapping_islands() — overlap detected")

    # Flipped island (CW winding = negative signed area)
    flipped = Isl((0, 0, 1, 1), [[0,0],[0,1],[1,1],[1,0]])  # CW
    normal  = Isl((0, 0, 1, 1), [[0,0],[1,0],[1,1],[0,1]])  # CCW
    fi = find_flipped_islands([normal, flipped])
    assert 1 in fi, f"expected island 1 to be flipped, got {fi}"
    ok("overlap.find_flipped_islands()")

    # Stretched island
    stretched = Isl((0,0,0.01,0.01), [[0,0],[0.01,0],[0.01,0.01],[0,0.01]],
                    area_uv=0.0001, area_3d=10.0)  # huge 3D area, tiny UV
    ok_isl = Isl((0,0,0.5,0.5), [[0,0],[0.5,0],[0.5,0.5],[0,0.5]],
                  area_uv=0.25, area_3d=0.25)
    si = find_stretched_islands([ok_isl, stretched], threshold=0.25)
    assert 1 in si, f"expected island 1 to be stretched, got {si}"
    ok("overlap.find_stretched_islands()")
except Exception as e:
    fail("overlap", e)

# ── 4. BMesh seam operators on a real cube ────────────────────────────────────
print("\n=== 4. BMesh / Operator tests on cube ===")

try:
    # Create a cube in the scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')

    # Mark seams by angle — should work in edit mode
    result = bpy.ops.uvtk.mark_seams_angle()
    assert result == {'FINISHED'}, f"mark_seams_angle returned {result}"
    ok("op: uvtk.mark_seams_angle on cube")

    result = bpy.ops.uvtk.mark_seams_open()
    assert result == {'FINISHED'}, f"mark_seams_open returned {result}"
    ok("op: uvtk.mark_seams_open on cube")

    result = bpy.ops.uvtk.clear_seams()
    assert result == {'FINISHED'}, f"clear_seams returned {result}"
    ok("op: uvtk.clear_seams on cube")

    # Smart unwrap (re-mark seams first for clean island layout)
    bpy.ops.uvtk.mark_seams_angle()
    result = bpy.ops.uvtk.smart_unwrap()
    assert result == {'FINISHED'}, f"smart_unwrap returned {result}"
    ok("op: uvtk.smart_unwrap on cube")

    bpy.ops.object.mode_set(mode='OBJECT')
except Exception as e:
    fail("BMesh operator tests", e)
    bpy.ops.object.mode_set(mode='OBJECT')

# ── 5. Pack operator ─────────────────────────────────────────────────────────
print("\n=== 5. Pack operator ===")
try:
    bpy.ops.object.mode_set(mode='EDIT')
    result = bpy.ops.uvtk.pack()
    assert result == {'FINISHED'}, f"pack returned {result}"
    ok("op: uvtk.pack on cube")
    bpy.ops.object.mode_set(mode='OBJECT')
except Exception as e:
    fail("pack operator", e)
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except: pass

# ── 6. Texel density operators ───────────────────────────────────────────────
print("\n=== 6. Texel density operators ===")
try:
    bpy.ops.object.mode_set(mode='EDIT')
    # Select all faces
    bpy.ops.mesh.select_all(action='SELECT')

    result = bpy.ops.uvtk.td_get()
    assert result == {'FINISHED'}, f"td_get returned {result}"
    ok("op: uvtk.td_get")

    result = bpy.ops.uvtk.td_set()
    assert result == {'FINISHED'}, f"td_set returned {result}"
    ok("op: uvtk.td_set")

    result = bpy.ops.uvtk.td_normalize()
    assert result == {'FINISHED'}, f"td_normalize returned {result}"
    ok("op: uvtk.td_normalize")

    bpy.ops.object.mode_set(mode='OBJECT')
except Exception as e:
    fail("texel density operators", e)
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except: pass

# ── 7. Select operators ──────────────────────────────────────────────────────
print("\n=== 7. Select operators ===")
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    result = bpy.ops.uvtk.select_overlapping()
    assert result in ({'FINISHED'}, {'CANCELLED'}), f"unexpected: {result}"
    ok("op: uvtk.select_overlapping (no crash)")

    result = bpy.ops.uvtk.select_flipped()
    assert result in ({'FINISHED'}, {'CANCELLED'}), f"unexpected: {result}"
    ok("op: uvtk.select_flipped (no crash)")

    result = bpy.ops.uvtk.select_stretched()
    assert result in ({'FINISHED'}, {'CANCELLED'}), f"unexpected: {result}"
    ok("op: uvtk.select_stretched (no crash)")

    bpy.ops.object.mode_set(mode='OBJECT')
except Exception as e:
    fail("select operators", e)
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except: pass

# ── 8. Finish tagging ────────────────────────────────────────────────────────
print("\n=== 8. Finish tagging ===")
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    result = bpy.ops.uvtk.tag_finished()
    assert result == {'FINISHED'}, f"tag_finished returned {result}"
    ok("op: uvtk.tag_finished")

    result = bpy.ops.uvtk.select_finished()
    assert result == {'FINISHED'}, f"select_finished returned {result}"
    ok("op: uvtk.select_finished")

    result = bpy.ops.uvtk.tag_unfinished()
    assert result == {'FINISHED'}, f"tag_unfinished returned {result}"
    ok("op: uvtk.tag_unfinished")

    bpy.ops.object.mode_set(mode='OBJECT')
except Exception as e:
    fail("finish tagging", e)
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except: pass

# ── 9. Transform operators ───────────────────────────────────────────────────
print("\n=== 9. Transform operators ===")
try:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    result = bpy.ops.uvtk.rotate_island(angle_deg=45.0)
    assert result == {'FINISHED'}, f"rotate_island returned {result}"
    ok("op: uvtk.rotate_island(45°)")

    result = bpy.ops.uvtk.flip_island(axis='H')
    assert result == {'FINISHED'}, f"flip_island H returned {result}"
    ok("op: uvtk.flip_island(H)")

    result = bpy.ops.uvtk.fit_uv_space()
    assert result == {'FINISHED'}, f"fit_uv_space returned {result}"
    ok("op: uvtk.fit_uv_space")

    bpy.ops.object.mode_set(mode='OBJECT')
except Exception as e:
    fail("transform operators", e)
    try: bpy.ops.object.mode_set(mode='OBJECT')
    except: pass

# ── Unregister ───────────────────────────────────────────────────────────────
print("\n=== Cleanup ===")
try:
    uv_toolkit.unregister()
    ok("addon unregister")
except Exception as e:
    fail("addon unregister", e)

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print(f"  PASSED: {len(PASS)}")
print(f"  FAILED: {len(FAIL)}")
if FAIL:
    print("\nFailed tests:")
    for f in FAIL:
        print(f"  - {f}")
print("="*60)

sys.exit(0 if not FAIL else 1)
