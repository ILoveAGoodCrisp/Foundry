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
