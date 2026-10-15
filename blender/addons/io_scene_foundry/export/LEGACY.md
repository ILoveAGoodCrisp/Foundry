# Legacy intermediate export

The project selects the format automatically: H1 uses JMS, H2–ODST use JMS/ASS,
and Reach onward use Granny. There is no format selector.
Use **Intermediate Files Only** and choose an asset folder within the active
project's data directory. The legacy asset-folder setting is separate from the
Granny sidecar path. Existing Granny exports retain their default behavior.
H1–ODST assets retain a lightweight `.sidecar.xml` marker. Foundry resolves the
authoritative data and tag destination from that marker during export, then
falls back to a saved `.blend` location inside the project's data directory and
finally the Legacy Asset Folder field. A missing marker is created on export
without using it as Tool input.

The backend uses `ExportScene.ready_scene`, object selection and Halo property
mapping, `VirtualScene` evaluation/triangulation, and normal animation sampling.
Granny mesh buffers and animation curves are bypassed. Scene restoration runs even
if conversion or writing fails. No sidecar is constructed or written.

| Project | JMS | ASS | JMA |
| --- | --- | --- | --- |
| H1 | 8200 | unavailable | 16392 |
| H2 | 8210 | 2 | 16395 |
| H3 / ODST | 8213 | 7 | 16395 |

H2–ODST models, particle models, and decorators go in `render`; collision and
physics go in `collision` and `physics`. H1 model geometry goes in `models`, and
its collision/physics geometry shares the `physics` directory expected by Tool.
Scenario BSPs and designs go in `structure`, with
design files receiving `_design` in their names. Animations go in `animations`,
using the appropriate JMA-family extension for movement/overlay/replacement.
Each model permutation has its own file. BSP layers combine into a single file
per BSP. H1 structures use JMS; later structures use ASS. Model permutations
containing instanced objects use ASS on supported games, including bone palettes
and region/permutation material variants.

H3/ODST design ASS files use Tool's `structure-design` command. Their compiled
`.structure_design` tags are linked in the scenario's structure-BSP row using
the Foundry BSP assignment; selected-BSP exports include the associated design.
Water surfaces retain their shader and use the `!'` material symbols. Physics
water uses `~` ASS instances with `+unused` material, so Tool generates water
physics instead of processing an open plane as solid BSP geometry.

H1 BSP tag import repairs compiled portal roundoff before creating the Blender
meshes. It tests plane stability, retains repaired outlines as clean ngons,
and gives enclosed openings a bounded wall overlap only when the
source collision BSP confirms the entire expanded boundary is solid. Overlap
is limited to 0.01 tag units; plane correction is limited to 0.0005 tag units.
Adjacent fragments with matching flags and front/back clusters become one
object. Compiled contacts are welded, and redundant internal edges are dissolved
into one flat face when the source collision walls still cover its perimeter
and junctions with other portals fit the same plane. Joining allows at most
0.03 tag units of contact welding; plane changes are bounded by 0.1 tag units
and 0.1% of the opening's size. Necessary cutting faces and holes are retained.
Point contacts and different cluster connections stay separate. Export uses ordinary triangulation
and the final JMS plane correction; stability probes do not become visible
triangle fans. This runs on fresh tag imports without a WRL file or
portal-number-specific rules.

A fresh `levels/a30/a30_a` import, Blender save/reopen and production JMS export
compiled through HCE Tool with no yellow portal-closure errors. It retained all
38 clusters and the original 47 cluster connections (including sky assignments),
with no invalid portal links. Nearly-coplanar, non-dividing-surface and
clipped-surface warnings remain. The 65 source fragments import as 51 portal
objects with 54 faces, removing 11 internal fragment boundaries. Portals 20
and 35 each have one face. The clean surfaces compile to 69 portal fragments,
compared with 94 from the previous visible-fan repair.

H1 import also restores shared corners where distinct source portal planes
intersect. Independent wall recovery can move those endpoints apart even when
each resulting face is planar. The final import pass uses the original BSP
junctions, bounds movement to 0.03 tag units, and rejects ambiguous, collapsed,
reversed, or warped results. Coplanar fragment contacts retain their wall overlap.
This is ordinary editable mesh geometry; it adds no saved source metadata.
For `levels/b40/b40_a`, fresh portal import and a repaired saved/reopened blend
compiled without portal-closure errors. The complete production export retained
all 65 clusters, 92 unique connections, and sky assignments; the failing JMS had
six yellow closure faces and 91 connections. Its five degenerate-triangle and
nearly-coplanar warnings remain.

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
The H1 JMS dialect omits the later precise-position `)` material suffix because
H1 Tool treats it as part of the shader name rather than as a surface flag.

Text serializers reuse the importer's Blender-independent asset models and trust
the prepared export data. Export does not run model validation, scan numeric
records for non-finite values, or parse generated files back. Serializer
compatibility and round trips are checked in tests. Output is staged in temporary
files before any existing output is replaced. Staging failure leaves existing
outputs intact. Replacing a batch is not a filesystem-wide atomic transaction.

## Tag writing

Full and Tags Only exports support H1 through ODST model, sky, and animation
assets. H1 and H2 scenario exports compile each structure BSP and create or
update the parent `.scenario` tag with the compiled BSP references. Existing
scenario contents and existing BSP entries are preserved; a new scenario also
receives its selected scenario type and a default player start/profile. H2–ODST run the editing kit's `bulk-import-model-folder` workflow only when
render, collision, and physics source files are all present. Otherwise, Foundry
runs only the individual `render`, `collision`, and `physics` commands with
available JMS/ASS sources, then creates or updates the parent `.model` tag and
its component references natively. H3/ODST individual render imports preserve
the selected final/draft mode. H2 always uses its standard bulk command because
that kit does not provide the H3 draft variant. H1 dispatches its separate `model`,
`collision-geometry`, and `physics` commands according to the available source
directories; the shared H1 physics folder only triggers the collision or physics
step when the corresponding geometry is present and enabled for export.
H1 always launches `tool.exe`, even when the project preference is
set to `tool_fast`, because H1 does not provide a compatible fast executable.
Before H1 Tool runs, Foundry resolves selected shader paths and supplies a shared
grey fallback for unresolved materials so Tool does not open its interactive
shader-class prompt. Scenario exports preserve the selected shader classes,
including `shader_model`. Non-scenario exports convert `shader_environment` to
`shader_model`, keeping the original tag and assigning the new path to the
material. Animation
sources use `animations` on H1 and `model-animations`
on H2–ODST. Native
`blam-tags` documents perform Foundry's tag pre-processing and post-processing,
including animation metadata and model template-reference overrides. Selected
high-level object outputs (such as scenery, crate, biped, vehicle, and weapon)
are created or updated natively. H2–ODST objects reference the compiled model
tag. H1 objects receive their separate gbxmodel, collision, animation and
physics references; configured
tag templates are copied before those references are written. Tags Only reuses
the source files already in the asset folder; Full Export writes fresh
intermediates before compiling them.
H1 and H2 Sky assets create their native `.sky` tag rather than a scenery tag:
H1 writes gbxmodel/model-animations references, while H2 writes
render-model/model-animation-graph references. Existing sky lighting and fog
settings remain intact. H2 particle-model and decorator-set exports write an
8210 JMI manifest plus its child render JMS, then invoke Tool's dedicated
`import-particle-model` or `import-decorator-set` command and verify the expected
tag was created.

H3/ODST cinematic assets use the shared cinematic scene and actor sampling path.
The armature transform is included in the root bone, as in Reach. Each actor's
shots are written as normal `.jmm` animations, with no world-relative flag
override. Tool also requires a skeleton-only render JMS; Foundry derives its
bind transforms and node order from the actor's existing render-model tag.
Sources live under `objects/<cinematic-scene>/<actor>/render` and `animations`,
and `model-animations` compiles a separate graph for each actor and scene.
An extra terminal held JMM sample keeps compiled animation and camera lengths
equal. Cinematic, scene, event, scenario-link and anchor data are written directly
to tags; the asset marker never drives cinematic compilation.

Camera Only leaves actor sources and graphs untouched. Objects Only skips camera
frame sampling and scene-tag writing. Tags Only reuses existing JMS/JMM files and
samples current camera data. Current-scene exports retain the complete root scene
list; current-shot exports preserve the other shots' sources and camera frames
and require an existing scene tag. H3/ODST supports up to 32 shots per scene.
Fade colors and durations are stored directly in the cinematic tag and exposed
in the cinematic settings instead of a Reach transition tag.

Isolated H2 Tool acceptance runs compiled rigid one-bone children from the
generated `<child>/render/<child>.jms` layout through `import-particle-model` and
`import-decorator-set`, creating the expected `.particle_model` and
`.decorator_set` tags. Tool rejects skinned particle-model sections, so Foundry
validates that every particle-model and decorator-set vertex has one influence
and every material section uses one bone before invoking Tool.

## Current limits

- Tag compilation for other non-model legacy asset types is not implemented.
  Intermediate Files Only remains available for all supported legacy assets.
  H1 does not run the H2+ animation-graph pre/post-processing pass; Tool compiles
  its `model_animations` tag directly. H1 scenario exports can run Tool radiosity
  after compiling BSP and scenario tags; each selected BSP uses its name, quality,
  stop threshold and optional `-noassert` flag. H2/H3/ODST lightmapping and legacy
  cache building are not implemented.
- Physics meshes write native sphere, box, pill or convex records for H2/H3/ODST.
  Hinge and socket markers write hinge/ragdoll constraint records. Mixed-material
  shapes must be split before export. H2-ODST tag-reference markers write native
  JMS XREF tables/instances or ASS referenced geometries. Imported XREF paths,
  object names and JMS identifiers are retained. New references derive the H2
  `data/.../<asset>/render/<asset>.max` source convention from the Foundry tag
  path, use the asset filename as the object name and a stable signed identifier. H1's
  JMS 8200 dialect cannot represent XREF records and rejects these markers.
  Classic XREF records have no object-variant field, so a marker's requested
  variant is not serialized.
- Animation composites, external GR2 references, PCA and vector events are not
  representable by this path and are rejected. H1/H2 frame, sound and effect data
  are written to the compiled classic tag where that game's layout supports them.
  H1 export also restores authored animation weight, loop frame, supported playback
  flags and world-relative state after Tool compiles `model_animations`. JMA has
  uniform scale and H1 JMS has at most two weights per vertex.
- Not every Reach/H4-only property has a legacy equivalent. ASS 2/JMS cannot carry
  the complete ASS 7 lighting records. Shadow Only is rejected for those dialects.
- H2 L1-L6 material definitions, BSP light objects and instance collision/physics
  proxy relationships are written to ASS. Existing output files are not pruned automatically; remove
  obsolete intermediates before compiling a folder if its format or names change.

Validation: `tests/test_legacy_writers.py` checks serializer round trips and
material variants. `tests/test_legacy_export_blender.py` runs the real Foundry
preparation pipeline for all four target games, including skinned geometry,
ASS model instances, collision, convex physics, animation samples, no-sidecar
output and scene restoration. Isolated Tool acceptance compiled H1 gbxmodel,
model-collision and physics tags and an H2 model/render-model pair from the
folder layouts used by this exporter.

## Standalone file exports

**File > Export** also offers Halo JMS, Halo ASS, Halo Animation and Granny GR2.
These save directly to the chosen file, without an asset folder, sidecar, tag
processing or editing-kit tools. A configured project is optional.

The file browser can limit export to selected objects, visible objects and the
active collection (including children). Filters intersect; required skeleton
dependencies are included. Scale and forward conversion can each be disabled.
JMS/ASS/JMA versions start at the project default and can be changed in the
dialog. Supported versions are JMS 8197–8213, ASS 1–7 and JMA 16392–16395.
Halo Animation offers JMA, JMM, JMT, JMZ, JMO, JMR, JMW, JMV and JMH.

GR2's **Halo Properties** switch controls BungieExportInfo and Halo metadata on
materials, meshes, faces and bones. Disabling it also permits multiple root
bones. **Include Animation** samples currently assigned skeletal and object
actions together over the scene frame range, alongside geometry. Independent
rigs use separate track groups. JMA exports the currently assigned skeletal
actions over the same frame range. Export restores the scene even after failure.

`blender/tests/test_standalone_export_blender.py` checks the registered operators,
all supported text versions and animation extensions, scope and conversion
options, skinned geometry, physics, non-Halo GR2, assigned actions and restoration.
