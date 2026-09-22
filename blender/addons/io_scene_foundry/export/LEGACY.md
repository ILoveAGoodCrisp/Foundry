# Legacy intermediate export

The project selects the format automatically: H1 uses JMS, H2–ODST use JMS/ASS,
and Reach onward use Granny. There is no format selector.
Use **Intermediate Files Only** and choose an asset folder within the active
project's data directory. The legacy asset-folder setting is separate from the
Granny sidecar path. Existing Granny exports retain their default behavior.

The backend uses `ExportScene.ready_scene`, object selection and Halo property
mapping, `VirtualScene` evaluation/triangulation, and normal animation sampling.
Granny mesh buffers and animation curves are bypassed. Scene restoration runs even
if conversion or writing fails. No sidecar is constructed or written.

| Project | JMS | ASS | JMA |
| --- | --- | --- | --- |
| H1 | 8200 | unavailable | 16392 |
| H2 | 8210 | 2 | 16395 |
| H3 / ODST | 8213 | 7 | 16395 |

Models, particle models, and decorators go in `render`; collision and physics
in `collision` and `physics`. Scenario BSPs and designs go in `structure`, with
design files receiving `_design` in their names. Animations go in `animations`,
using the appropriate JMA-family extension for movement/overlay/replacement.
Each model permutation has its own file. BSP layers combine into a single file
per BSP. H1 structures use JMS; later structures use ASS. Model permutations
containing instanced objects use ASS on supported games, including bone palettes
and region/permutation material variants.

Every JMS contains a skeleton. When the Blender scene has no armature, Foundry
writes one identity bone named `implied_root_node` and binds otherwise unparented
vertices, markers, collision records, and physics records to that serialized
root. The Blender scene itself is not modified.

Resolved mesh and face properties produce deduplicated material variants. The
adapter reads the face arrays after material sorting, so face overrides stay
aligned with triangles. Supported flags include sides, collision/render modes,
ladder, breakable, precise positions, shadow/lightmap exclusion, portal flags,
decal offset and slip surfaces. ASS 7 also writes lighting records. Default Low
lightmap resolution does not add a name override. Collision and physics use
surface material names; pre-H4 BSPs keep shader-derived surface types.

Text serializers reuse the importer's Blender-independent asset models. Output
is staged in temporary files and JMS/ASS files are parsed back before any existing
output is replaced. Staging failure leaves existing outputs intact. Replacing a
batch is not a filesystem-wide atomic transaction.

## Tag writing

Full and Tags Only exports for H3 and ODST model, sky, and animation assets run
the editing kit's documented `bulk-import-model-folder` workflow over the
JMS/ASS source tree (using its draft variant unless **Light Model (PRT)** is
enabled). Animation sources are compiled separately with `model-animations`, as
required by [H3 Tool](https://c20.reclaimers.net/h3/h3-ek/h3-tool/). Native
`blam-tags` documents perform Foundry's tag pre-processing and post-processing,
including animation metadata and model template-reference overrides. Selected
high-level object outputs (such as scenery, crate, biped, vehicle, and weapon)
are created or updated natively and reference the compiled model tag; configured
tag templates are copied before those references are written. Tags Only reuses
the source files already in the asset folder; Full Export writes fresh
intermediates before compiling them.

## Current limits

- Tag compilation for H1/H2 and non-model H3/ODST asset types is not implemented.
  Intermediate Files Only remains available for all supported legacy assets.
  Legacy lightmapping and cache building are not implemented.
- Physics meshes currently write convex records for H2/H3/ODST; analytic primitive
  shapes and constraints need a dedicated conversion pass. Mixed-material convex
  shapes must be split before export. Constraints and tag references are rejected.
- Animation composites, external GR2 references, PCA and vector events are not
  representable by this path and are rejected. Animation event export is not yet
  implemented. JMA has uniform scale and H1 JMS has at most two weights per vertex.
- Not every Reach/H4-only property has a legacy equivalent. ASS 2/JMS cannot carry
  the complete ASS 7 lighting records. Shadow Only is rejected for those dialects.
- LOD-specific naming, light objects and scenario instance proxy relationships
  need further work. Existing output files are not pruned automatically; remove
  obsolete intermediates before compiling a folder if its format or names change.

Validation: `tests/test_legacy_writers.py` checks serializer round trips and
material variants. `tests/test_legacy_export_blender.py` runs the real Foundry
preparation pipeline for all four target games, including skinned geometry,
ASS model instances, collision, convex physics, animation samples, no-sidecar
output and scene restoration. Tool acceptance has not yet been tested.
