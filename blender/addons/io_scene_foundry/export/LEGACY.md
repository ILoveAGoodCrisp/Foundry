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

Text serializers reuse the importer's Blender-independent asset models. Output
is staged in temporary files and JMS/ASS files are parsed back before any existing
output is replaced. Staging failure leaves existing outputs intact. Replacing a
batch is not a filesystem-wide atomic transaction.

## Tag writing

Full and Tags Only exports support H1 through ODST model, sky, and animation
assets. H1 and H2 scenario exports compile each structure BSP and create or
update the parent `.scenario` tag with the compiled BSP references. Existing
scenario contents and existing BSP entries are preserved; a new scenario also
receives its selected scenario type and a default player start/profile. H2–ODST run the editing kit's `bulk-import-model-folder` workflow over
the JMS/ASS source tree; H2 always uses its standard command because that kit
does not provide the H3 draft variant. H1 dispatches its separate `model`,
`collision-geometry`, and `physics` commands according to the available source
directories. H1 always launches `tool.exe`, even when the project preference is
set to `tool_fast`, because H1 does not provide a compatible fast executable.
Before H1 Tool runs, Foundry creates any unresolved material tags so Tool does
not open its interactive shader-class prompt: scenario structure uses
`shader_environment`, while all other asset types use `shader_model`. Animation
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

An isolated H2 Tool acceptance run compiled a rigid one-bone child from the
generated `<child>/render/<child>.jms` layout through `import-particle-model` and
created the expected `.particle_model` tag. Tool rejects skinned particle-model
sections, so Foundry now validates that every particle vertex has one influence
and every material section uses one bone before invoking Tool.

## Current limits

- Tag compilation for other non-model legacy asset types is not implemented.
  Intermediate Files Only remains available for all supported legacy assets.
  H1 does not run the H2+ animation-graph pre/post-processing pass; Tool compiles
  its `model_animations` tag directly. Legacy lightmapping and cache building are
  not implemented.
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
