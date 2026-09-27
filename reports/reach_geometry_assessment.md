# Reach BSP extraction: H1 fixes assessed

## Changes

Reach now reuses `weld_classic_vertices` from the H1 import path. The helper
joins vertices only when their positions are exactly equal, preserves corner
UVs/custom normals and face attributes, protects stacked faces, and checks that
welding does not remove faces.

The repair runs on merged structure, individual/unmerged clusters, shared
instance meshes, collision proxies and water. Shared meshes are processed by
mesh identity rather than once for every placement. Where structure collision
edge stitching runs, exact welding also runs before that operation.

Reach cluster joins now disable the generic geometry cleanup. That cleanup
uses a fixed 0.01 Blender-coordinate merge distance, which can collapse thin
triangles and has different physical effects at the two import scales. The
exact weld reconnects UV/normal splits without moving nearby vertices. The
change is restricted to Reach.

## Applicability of other H1 fixes

| H1 behavior | Reach assessment |
| --- | --- |
| Exact vertex welding with attribute preservation | Ported by reusing the existing helper. |
| Join without distance cleanup | Ported. |
| Material and face-attribute preservation during joins | Already shared through `utils.join_objects`. |
| Reconstruct render/collision coverage using coplanar patches | Not directly ported. Reach already imports native surface-to-triangle mappings; replacing them needs separate evidence and collision-property validation. |
| Convert material-less H1 collision shells to sky/seamsealer using cluster lookup | H1-specific tag semantics; not ported. |
| H1 collision flags, shader transparency and opposite collision-patch handling | Not copied into Reach's existing mapping/material path. |

This repairs disconnected coincident vertices and prevents destructive joining.
It does not fill arbitrary holes, snap nearly coincident vertices, or make every
mesh watertight. Cluster boundaries, render-only surfaces and separate collision
shells can legitimately retain boundary edges. Reach's existing edge-stitching
routine is otherwise unchanged.

## Validation

Blender 5.2 background tests in `blender/test_reach_geometry.py` cover:

- Closed thin shells split across clusters, at both import scales.
- Single clusters and imports with structure merging disabled.
- Instance-definition cleanup through BSP import orchestration.
- Preservation of coordinates, UVs, custom normals and face properties.
- Preservation of stacked faces and nearby distinct shells.

All five tests pass. Existing classic geometry tests also pass (four tests;
the optional b40 fixture was not run).

Read-only audit of the installed HREK
`levels/multi/forge_halo/forge_halo_shared.scenario_structure_bsp`:

| Check | Result |
| --- | --- |
| Complete geometry import, including collision, without lights | Succeeded: 39 unique meshes, 32,304 faces. |
| Exact weld on 28 extracted render meshes | Boundary edges decreased from 15,561 to 3,798. |
| Face preservation during that weld | All 31,399 pre-weld faces retained. |
| Structure cluster join and exact weld | All 1,788 pre-join faces retained; 354 boundary edges remain. |

The boundary-edge comparison measures the exact-weld operation on decoded
meshes, not a before/after comparison of the complete previous importer.

A second audit initially exposed a native water decoder error in Sword Base:
`base texcoord` was read as `RealPoint3d` when Reach stores `RealPoint2d`.
The same error caused the reported main Forge World BSP import crash.

## Follow-up: Forge World water decoder crash

Fixed both native water-reading paths in the local dependency source,
`G:/Halo/Modding/OtherProjects/blam-tags/blam-tags/src/render_model.rs`, to use
one schema-aware reader. Reach/H4 2D water UVs are preserved with a zero third
component in the shared output representation; H3's 3D UVs, local information
and water velocity remain intact. Missing Reach flow fields retain their zero
defaults. No tag schema or source tag is changed.

Rebuilt the bundled `blam_tags-0.1.9-cp38-abi3-win_amd64.whl` and updated the
installed Blender 5.2 extension dependency. The previous installed package is
backed up under the extension's `site-packages/foundry-water-fix-a0fjobs2/previous`.
Already-running Blender sessions must restart to load the updated native module.

The main Forge World import then exposed a separate performance problem in
structure edge stitching: the original routine scans every vertex for every
edge. Reach now enables a KD-tree candidate lookup before the existing geometric
tests. It retains the original tolerance, candidate order and split behavior;
the other game paths keep their existing default. A regression test compares
both routines on several edge splits and nearby/off-edge vertices.

Validation of the fix:

- All seven regression tests pass, including a synthetic water triangle decoded
  through H3, Reach and H4 schemas, with explicit UV/flow-value assertions.
- Sword Base now completes its full BSP geometry import: 1,635 unique meshes,
  287,239 faces. Its decoded render meshes retain all 260,533 pre-weld faces.
- A direct check using Blender's installed decoder successfully reads the main
  Forge World BSP: 137 meshes, including four water meshes with 5,716 triangles.
- With spatial edge stitching enabled, the full main Forge World BSP geometry
  import also completes: 913 unique meshes, 175,363 faces (lights excluded).

To repeat a fixture audit, run Blender in background mode with
`--factory-startup --python-exit-code 1 --python blender/test_reach_geometry.py`
and append `-- --reach-bsp <absolute BSP tag path>`. The source tag is not saved.

## Follow-up: island_rock_1 and portal leaks

Reviewed the saved `data/foundry_blam/forge_world/forge_world.blend` against
`tags/levels/multi/forge_halo/forge_halo.scenario_structure_bsp` in HREK.
Both source files remain unchanged.

`island_rock_1` is placement 412, using instance definition/render mesh 26.
The saved mesh has 862 vertices, 1,610 faces and 127 boundary edges. Its source
render mesh has 1,550 triangles; the importer supplies 60 collision-only faces.
Separate render/collision decoding produces slightly different floating-point
coordinates along their shared boundary. Exact welding alone cannot join them.

A distance weld was tested but is not the implemented repair: it leaves a
second defect and can damage thin geometry. The new alignment moves only
collision boundary vertices to unambiguous, one-to-one render positions within
0.000025 tag units. Render vertices stay fixed; nearby competing layers and
many-to-one matches are rejected. The existing exact weld then joins the seams.
Structure collision uses the union of cluster render vertices when checking
ambiguity, rather than snapping independently to successive clusters.

The remaining defect is a two-sided face. Collision surfaces 731 and 866 have
opposite winding and both map to render triangle 1503, but that render triangle
previously lost its sidedness. Reach instance import now recognizes matching
opposite collision surfaces and transfers the two-sided property to mapped
render faces. This includes the source's unmaterialed compiler backface paired
with its rock-shader face; two genuinely different materials remain distinct.
Collision-only meshes now also retain explicit source sidedness flags.

After reconstruction, the rock has 808 vertices and all 1,610 faces. Its
1,609-face solid shell has **zero boundary edges and zero overused edges**.
The remaining face is explicitly two-sided; its two free edges are not holes
in the solid shell. These are topology checks, not a completed Tool compile.

Reach portal import now reuses H1's conservative portal reconstruction and
outline simplification. For this BSP, 10 of 21 fragments qualify for rebuilding;
the result still has 21 portals, with 262 rather than 270 vertices. The H1
intersection guards retain unsafe candidates. No H1 collision-solid classifier
is reused: Reach's collision representation is different, so the additional
solid-edge extension for rejected candidates is not enabled.

Also fixed portal flags that were read but not applied to Blender objects:
one-way/no-way types now survive import, and one-way-reversed records reverse
their winding. These changes preserve portal behavior independently of geometry.

Validation:

- Ten Reach tests cover thin shells, normals/UVs/face properties, water decoding,
  exact welding, collision boundary ambiguity, duplicate surface selection,
  sidedness, portal types and portal intersection guards.
- H1 surface tests pass (four tests; the optional external-fixture test skipped).
- Full Forge World BSP geometry import completes with 913 unique meshes and
  175,362 faces. Raw render decoding still retains all 144,528 faces.
- The real-BSP audit checks `island_rock_1`'s face count and closed solid shell.

The saved scene predates these fixes and must be reimported to obtain them.
Portal leaks still require a new export/Tool compilation to confirm; the source
portal reconstruction and Blender topology checks alone cannot establish that
all compiled visibility boundaries are valid.

## Follow-up: tunnel sliver and portal volumes (2026-09-27)

The current saved scene reproduces the `for_tunnel_column05` problem in instance
definition 119. A collision-only `+seamsealer` triangle has area approximately
`7.54e-7` Blender units squared. It bridges a long collision edge against two
render edges. Blender counts the sliver as closing the shell, but Tool rejects
the triangle and then reports its edges as open.

The importer now dissolves that long edge into its adjacent collision polygon.
It retains the middle boundary vertex, render positions and face properties.
The operation requires the matching render edge chain, consistent winding,
matching materials and matching face attributes; it does not delete arbitrary
thin triangles. The tunnel now has 258 faces. After triangulation it has 288
triangles, minimum area `0.0034898`, and no open or overused edges.

The portal issue is not simply a missing terrain face. The original tag's
horizontal portal outline itself ends in open space along part of its boundary.
Those compiled visibility outlines cannot always be reused as sealed authoring
polygons. Direct H1-style extension and corner snapping were insufficient in
actual Tool comparisons.

Reach connected portal volumes now use the original collision tree and the
root leaf-to-cluster table to recover the cuts. Uniform-cluster branches collapse;
solid-only branches inherit their neighbour's cluster. Each portal plane is
partitioned on both sides, retaining only the original cluster connections.
Portal types, winding and sound flags remain attached to their original
connections. Isolated openings retain the conservative H1 reconstruction, which
avoids introducing extra disconnected pieces in those openings.

Reach's supernodes must be traversed before ordinary BSP nodes. Their wire
layout is 15 plane values, 16 child indices, then packed axis dimensions. The
editor schema labels the final words misleadingly, so the reader uses wire order.
Compact 24-bit child designators and large 32-bit nodes are both supported.
The layout and traversal were cross-checked against TagTool's
[collision structures](https://github.com/TheGuardians/TagTool/blob/master/TagTool/Geometry/BspCollisionGeometry/CollisionGeometry.cs)
and [BSP verifier](https://github.com/TheGuardians/TagTool/blob/master/TagTool/Geometry/BspCollisionGeometry/Utils/VerifyBsp3d.cs).

Validation:

- Final Reach regression suite: 14 tests passed. H1 surface tests: four passed,
  one optional fixture skipped. H1 portal export tests: five passed.
- Full original main BSP import: 913 unique meshes and 176,443 faces. Render
  decoding still retains all 144,528 original render faces. Rock and tunnel
  closed-shell checks pass, including tunnel triangulation.
- Recovered geometry stays in 21 Blender portal objects, containing 1,103
  convex pieces. They represent the recovered cuts rather than 1,103 separately
  authored portal connections.
- The baseline Tool compile reproduced two portal leakage reports. The final
  grouped-mesh export compiled in 4m37s with **zero portal leakage reports and
  zero tunnel open-edge/degenerate-triangle reports**. Tool rebuilt 21 portals
  and nine main-BSP clusters. The source has 11 clusters, including two tiny
  compiler-generated clusters; this is not a byte-identical visibility rebuild.
  Runtime visibility has not been visually checked in Sapien.
- Two separate degenerate-triangle warnings remain on `forerunner_tower04` in
  the shared BSP, alongside existing material and collision-size warnings.
  These were present in the baseline too.

Saved and reopened the repaired scene at
`G:/Halo/Modding/Main/HREK/data/foundry_blam/forge_world/forge_world_geometry_fixed.blend`.
It keeps the original asset sidecar path. The original `forge_world.blend` and
source BSP were not overwritten. The final diagnostic tags and sidecar are under
`foundry_blam/codex_geometry_final` in HREK's `tags` and `data` directories.
