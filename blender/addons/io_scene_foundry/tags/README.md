# blam-tags migration

See [migration status](MIGRATION_STATUS.md) for the remaining work and dependency audit.

## Migrated workflows

These wrappers now use native blam-tags documents and never initialize ManagedBlam:

- Camera-track import/export (H3, ODST, Reach, H4, H2AMP).
- Global material names, camera FOV and first-person model references.
- Render-method definitions and option parameters/defaults.
- Material-shader parameters/defaults (H4/H2AMP).
- Model references, export path updates, variants, damage states, child objects,
  material mappings, render-region metadata and Reach sky detection.
- Lightmap-region bounds, restriction flags, ambient occlusion and bounce mode
  for H4/H2AMP, plus lightmapper quality names used by the UI.
- Object model references, variants, change colors, seat and weapon names,
  magazine/tether metadata, first-person model edits and scenery lighting references.
- Object attachment references, marker names and scale-function names. Missing
  and unsupported attachments are filtered before opening a legacy converter.
- Cinematic-lighting creation and dynamic-light references, flags and placement
  metadata. Referenced Reach light conversion uses the native light wrapper;
  H4/H2AMP authored-probe conversion remains unimplemented.
- Object-function node creation for supported native editor shapes; unsupported
  shapes raise before any nodes are created.
- Cinematic scenery conversion when the source block layouts match the target
  schema. Incompatible layouts raise explicitly.
- Top-level cinematic import/export and its scenario bookkeeping, including
  transition tags, scripts, scene references, zone sets and anchors.
- Frame-event-list import/export, shared references and partial animation updates.
- Animation-graph names, skeleton ordering, parent indices, node usages, parent
  graph and imported-event references. Template setup and animation command lookup
  use this metadata path without opening ManagedBlam. Graph creation, cinematic
  skeleton copying, parent-graph assignment, node-usage and IK-chain export, and
  compression, world-relative and vehicle-suspension settings are native too.
  Animation weights, loop frames, playback flags, blend overrides and PCA group
  metadata also write natively. Pose-overlay automation reads its blend screens
  through this wrapper. Mode/state graph traversal and Blender animation-rename
  generation are native across all five H3+ profiles. Animation import settings
  and node-usage indices are detached native records. The Python binding exposes
  Rust-decoded, fully composed animation poses, including graph-selected
  overlay/replacement bases, object-space corrections and movement. The Blender
  importer consumes those owned transforms for H3, ODST, Reach, H4 and H2AMP.
- Particle-emitter custom-points tag creation during particle-model export.
- Cinematic event sound-effect names, playback availability and indexed sound-class
  labels.
- H4/H2AMP prefab structure-BSP reference resolution during import.
- H4/H2AMP prefab records and H3/ODST/Reach collision-proxy surface mappings in
  structure BSPs.
- Structure-BSP collision materials, compression bounds, H4/H2AMP emissive
  materials, render-material/lightmap properties and structure-lighting references
  used during geometry import.
- Structure-BSP portals, markers, structure-meta references and legacy environment
  object placements used during import.
- Reach/H4/H2AMP structure-BSP cookie cutters and older lighting-info material
  emissives.
- Multiplayer weapon-source discovery for biped import.
- Terrain-shader global-material lookup through inherited shader references.
- Material/shader albedo, alpha-mode and physics-material metadata used by
  decorator setup, Granny texture extraction and BSP collision import.
- Empty shader-tag creation for non-node material export.
- Cinematic scene creation, scene-level export metadata/scripts, shot settings,
  camera-frame arrays, final scene object/attachment records and camera-authored
  screen-effect/user-input-constraint records where the tag layout supports them.
- Scenario metadata and lightweight editing for type detection, BSP/design/sky
  discovery, zone sets, lightmap settings, sky assignment, cutscene titles,
  scenario copies, default player profiles, debug zone sets, airprobe export,
  cubemap generation, decorator placement export, template palette copying and
  scenario-global tag creation/copying. Scenario import metadata and child-scenario
  discovery also use this path. Placed scenario objects, palettes, names, folders,
  transforms, variants, BSP filters and parent links are decoded natively;
  scenario decals and decorator placement clouds are decoded natively as well.

The Blender-facing classes retain their existing import locations. Their
implementations live in this package. Reference results are detached Python
objects; the few callers still passing them into legacy tag wrappers convert
references at that boundary.

The add-on no longer requires or initializes ManagedBlam for tag access. Startup,
project switching, editing-kit validation and packaging paths do not check for
`ManagedBlam.dll`. The former pure-Python conversion modules have moved into this
package and the historical `managed_blam` package has been removed. The Foundation
plugin installer still uses Python.NET independently of tag access.

## Build and generated assets

Use a Python environment with maturin installed and the Rust/MSVC toolchain:

```powershell
python blender/build_blam_tags.py G:\Halo\Modding\OtherProjects\blam-tags
```

The build uses a temporary source copy, stages the Windows abi3 wheel, registers
it in the extension manifest, and copies schemas needed by migrated workflows.
Every generated Halo 1 and Halo 2 group schema is staged because classic loose
tags do not embed their own layout; later games retain the curated workflow set.
The source checkout is not modified. Use `--schemas-only` to refresh generated
assets without rebuilding the unchanged wheel.

Both `wheels/` and `tags/definitions/` are generated assets excluded from Git.
Build before packaging; the extension needs both. Schema sources remain in
blam-tags, rather than being committed again in Foundry. The current wheel
does not contain JSON schemas. Existing MCC tags carry their own field layouts;
new tags need a schema, and reference extension lookup uses the per-title
`_meta.json` group-name index. `definitions/build.json` records the asset hashes.

The extension packager preserves and includes the locally built blam-tags wheel
when refreshing other dependencies. Install/reinstall the packaged extension
so Blender installs the wheel. Source installations must make the wheel
available to their Blender Python environment separately.

## Validation

With the wheel installed, these suites run without Blender:

- `tests/test_blam_tags_backend.py`
- `tests/test_blam_metadata.py`
- `tests/test_blam_model.py`
- `tests/test_blam_object.py`
- `tests/test_blam_functions.py`
- `tests/test_blam_packaging.py`

The additional camera and wrapper suites run inside Blender:

- `tests/test_blam_camera_blender.py`
- `tests/test_blam_wrappers_blender.py`

All 32 tests pass together in Blender 5.2 with addon dependencies available.
Coverage includes real tag serialization, edits and aborts, stale-handle-safe
block construction, model references/variants, native color channels,
title-specific fields, lightmapper settings, camera keyframes, packaging, and
addon imports. Object tests cover five title profiles, inherited object fields,
reference round trips and aborted edits, colors, weapon metadata and first-person
block growth. Wrapper tests assert that ordinary migrated operations never
initialize ManagedBlam. Attachment tests also cover detached records and marker
parenting with a stubbed light converter. Object custom functions and cinematic
scenery copying now use native operations exclusively; unsupported data raises
an error. Attachment import opens the referenced native light wrapper, though
projected textures still depend on the unported bitmap converter.

Read-only sampling also exercised existing tag files from all five H3+ kits:
global/material metadata, 15 model tags with their render-model references,
and 25 object tags (scenery, weapons, bipeds, vehicles and machines).
A Reach Cortana definition references a missing option tag; this is reported
as a missing dependency instead of silently creating an empty tag. Editing-kit
acceptance of newly written tags and complete import/export parity are still
unverified.

## Remaining binding work

Classic CE/H2 loose tags use `TagFile.read_classic(path, schema_path)`, which
preserves their engine, header and container when saving. Foundry selects this
entry point for H1/H2 documents and identifies their game from the classic header.
`TagFile.new(schema)` still creates an MCC container, so Foundry deliberately
rejects creation of new classic tags until blam-tags exposes an explicit classic
creation API. Broad H1/H2 Blender workflow acceptance is also still required.

Animation pose decoding and the shader function operations used by Foundry are
exposed in the local wheel. The function editor can change master/color graph
types, colors and scalar clamp ranges and serialize the result. Render-model and
structure-BSP mesh decoding are also exposed; bitmap extraction uses the
native/Python path. Remaining work in these areas is workflow and visual
acceptance rather than a ManagedBlam dependency.

Cinematic object conversion now uses native `TagBlock.copy_from` and
`TagField.copy_value_from`. These APIs were added to the local blam-tags checkout;
rebuild the wheel from that checkout before packaging. Block copying checks nested
layouts, preserves raw bytes and remaps layout indices before replacing the target.
Function imports become script-controlled and weapon ammo functions are added once.
The simulation-interpolation reference is copied independently of material effects.

Tests cover five H3+ profiles, nested function bytes and colors, and rejection of
incompatible blocks without destination changes. H3 has a change-color layout
difference (40 versus 36 bytes in a nested function struct). Empty blocks,
static colors and populated functions with the five known fields and zero-only
padding now copy natively. The binding exposes read-only struct bytes and field
offsets/widths so conversion can check every byte it would discard. Initial color
permutations still pass the native layout check. Nonzero padding, unknown fields
and other incompatible layouts retain the legacy fallback. Tests cover colors,
flags, string inputs, nonzero-padding rejection and rollback after unknown fields.
The fallback still needs editing-kit validation.

Light wrappers now use native field reading and function decoding for Reach lights
and Reach/H4/H2AMP cheap lights. Unsupported function shapes raise explicitly;
gel bitmap conversion uses the native bitmap wrapper and Foundry's Python image
decoder. H3/ODST light tags map maximum distance to cutoff and approximate
distance diffusion and angular smoothness with Blender fade controls. Static H4/H2AMP point, spot and directional light
tags now convert, including physical/artistic energy handling and shadow settings.
Animated intensity is supported for artistic point/spot lights. Animated radius
and cones, area lights and linked/projected physical or directional lights remain
unsupported. Unconnected identity curves evaluate at their constant input and
older Midnight layouts preserve defaults for unavailable shadow settings. The
read-only sample now converts 59 of 60 light tags. Unconnected deterministic curves
resolve through native evaluation; periodic or modifier-driven attenuation still
requires animation support. The remaining sampled tag is a physical light.
Light and structure seam/metadata schemas are staged by the build script as
ignored generated assets, not committed sources.

Structure seam import reads native final points and triangle indices, validates
geometry before allocation and preserves Blender normal/orientation handling.
Structure metadata imports effects, airprobes, light cones and object placements
without ManagedBlam. The wrappers retain their existing import paths.

Authored PCA animation also reads native blocks and linked render-model metadata,
then creates Blender shape keys and actions through the existing workflow. This
does not add runtime resource-only animation decoding. PCA schemas remain generated
and ignored alongside the other build assets.

Collision-model import reads native geometry and pathfinding spheres, validates
surface loops and bone bindings, then reuses the existing Blender conversion.
Separate structure-BSP and Havok collision paths still need migration.

Physics constraints read through blam-tags and use the existing Blender marker
conversion. The obsolete legacy physics wrapper has been removed. Standalone spheres
and boxes, nonzero-length capsules, convex polyhedra and flat lists of these shapes
now use native records. Nested lists and MOPP wrappers around supported shapes
also use native geometry, with circular-reference and expansion-limit checks;
other primitives, unbound bodies and unsupported serialized Havok payloads
raise explicit unsupported errors. Constraint-only tags avoid ManagedBlam entirely. Physics
schemas are ignored build assets.
H4/H2AMP Havok bodies with supported authored geometry read mass, center-of-mass,
inertia and damping properties natively through the existing Blender property mapping.
Older H4 layouts without serialized-shape fields also read natively, including
MOPPs that retain a list index instead of a child-shape reference.
Serialized Havok bodies now use native payload extraction and the existing Python
geometry decoder. All shapes decode before Blender allocation; an unsupported
payload raises an error without ManagedBlam fallback. Required bone bindings are checked.
Read-only sampling converted temporary copies of 36 H3 weapons, bipeds and
vehicles and verified their initial color permutations after reopening. All 36
used the native path; no original editing-kit tags were modified.
An additional scan of 933 H3 object tags found three populated color-function
blocks. Copies of all three convert natively, including the non-default colors
and scale inputs on the reactor sky tag. These tests do not establish editing-kit
acceptance of the resulting files.
Blender-facing integrations belong in this package beside their native documents.
Model and object keep their document layer separate from `model_blender.py` and
`object_blender.py`, so scripts can inspect and edit tag data without importing
Blender. Collision, physics, structure, particle, PCA and light import wrappers
follow the same native blam-tags path even where Blender conversion helpers have
not yet been moved out of the legacy package.
`backend.py` annotates its public boundary with the wheel's exported `TagFile`,
`TagStruct`, `TagField`, `TagBlock`, and math types. The wheel includes `py.typed`
stubs, so these definitions are available to VS Code while the runtime binding is
still imported lazily when a document is opened.
- Reach/H4/H2AMP animation graphs export Blender-authored frame events through the
  native graph and frame-event-list wrappers, including the graph reference update.
- Inline graph events import natively across H3 through H2AMP and merge with
  external event-list data before creating Blender frame events.
- Animation-graph IK chains import through typed native node/name records and keep
  the existing Blender proxy/pole helper-bone behavior.
- Cache validation uses native scenario methods for required resources, child
  scenarios, scenery palettes, player starts and generated spawn/camera placements.
- Structure BSP collision geometry, surface-to-triangle mappings, instance
  placements and policies, renderer-ready meshes, and serialized H4/H2AMP Havok
  collision payloads are read through typed blam-tags handles.
