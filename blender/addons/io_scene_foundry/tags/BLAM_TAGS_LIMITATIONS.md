# blam-tags reading limitations

Last updated: 2026-09-24.

This is the ongoing issue record for limitations encountered while migrating
Foundry. Scope is the local blam-tags checkout and Python wheel used by Foundry,
not a claim that every limitation exists in the Rust library.

## Maintaining this record

Add an entry whenever a tag or field cannot be read or decoded. Record the game,
tag/field, actual failure, layer responsible, reproduction evidence and workaround.
Distinguish confirmed failures from untested capabilities. When fixed, move the
entry to the resolved section with its verification; do not silently delete it.
Do not classify an unfinished Foundry converter as a blam-tags parsing failure.

Migration policy: no ManagedBlam fallback for migrated operations. Unsupported
physics placement/decoding and object-function descriptions now raise explicit
errors before allocating their Blender objects/nodes. Retained legacy code is
unfinished migration work, not the intended workaround.

## Confirmed open limitations

There are currently no confirmed open byte-reading failures in the audited tag
corpus. Unfinished converters and acceptance work remain listed separately below.

### Evidence locations

- READ-001: local `blam-tags/definitions/halo4_mcc/cinematic_scene_data.json`,
  `blam-tags-py/src/manual/handles.rs`, and Foundry `tags/cinematic.py`.
- READ-002: Foundry `tags/backend.py`, `CameraTrackDocument.__init__`.

## Separate integration work — not confirmed blam-tags read failures

| Area | What remains |
| --- | --- |
| Classic H1/H2 authoring | Existing loose tags use the schema-driven classic reader/writer and preserve their container on save. Representative HCE Captain/Pistol/Warthog and H2 Brute/Magnum/Warthog/Elite-Jetpack imports now complete the applicable render, collision and H2 physics paths. H1 legacy animation paths and aliases are reconstructed from its positional tables; all 213 HCE animation graphs resolved 10,061 authored paths in Blender. Unfiltered native decoding passed all 22 HCE Captain and 406 H2 Brute animations (14,013 composed frames). Metadata sweeps opened 429 HCE and 804 H2 biped, vehicle, weapon and scenery tags without a failure. A focused scan decoded all 144 candidate object functions from 296 H2 tags, including classic linear-key and spline payloads. Blender node construction also completed for all 1,412 HCE shader-family tags and all 3,107 H2 shaders; detail/multiply maps, UV scales, H1/H2 change colors, H2 alpha opacity and common emissive colors are connected. Classic cubemap references use Blender environment textures with reflection coordinates; H1 multipurpose masks and perpendicular/parallel reflection controls and H2 normal/glancing reflection controls are connected. H1 alpha-test flags and H2 alpha-test templates/maps now use the dithered Blender path. Fresh classic creation now uses `TagFile.new_classic(schema, game)`. H1/H2 biped defaults round-trip byte-exactly, and Foundry camera-track creation plus block editing survives save/reopen for both games. Model/sky/animation tag export now dispatches each editing kit's native commands; H1 object output writes its four independent model references and H2 writes the compiled model reference. H1 post-Tool animation updates preserve weight, loop frame, compatible flags, world-relative state and supported inline events. H2 scenario ASS output includes L1-L6 material definitions, weather polyhedra, BSP light objects, parented collision/physics proxies and referenced-tag XREF geometry. H2 render JMS also writes deduplicated XREF tables and transformed instances, preserving imported reference metadata where possible. H2 physics JMS preserves sphere, box, pill and convex shapes plus hinge/socket constraints. H1 JMS 8200 cannot encode XREF records, and classic XREFs cannot carry Foundry's object-variant setting. Broad visual acceptance, exact additive/subtractive/multiply blend behavior and less common tag families remain. |
| Classic animation-event export | Post-Tool tag updates now write H1 left/right foot and single-sound slots plus H2 frame, sound and effect blocks. New shared references and save/reopen behavior passed focused real-tag-copy roundtrips. Dialogue, music/function data, newer reference flags and other event types cannot be represented by these classic layouts and raise explicitly. |
| Structure-lighting projected textures | Native bitmap conversion is not implemented. Import refuses existing gobo/gel references before allocating lights. Seven of 60 sampled tags hit this gap, including Reach `foundry/scenarios/a50/default.scenario_structure_lighting_info`, H4 `cinematics/cin_m031_didact/lights/cin_m031_didact_020/cin_m031_didact_020_lighting_segment.scenario_structure_lighting_info`, and H2AMP `levels/sway/ca_ascension/ca_ascension_bsp01.scenario_structure_lighting_info`. The references themselves read correctly. |
| Structure-lighting animated functions | The current converter supports constant scalar functions. Two sampled H4 tags contain other function shapes: `cinematics/cin_m020_crater/lights/cin_m020_crater_000/cin_m020_crater_000_lighting.scenario_structure_lighting_info` and `cinematics/cin_m021_tower/lights/cin_m021_tower_010/lighting_segment.scenario_structure_lighting_info`. Their native function descriptions are readable; Blender conversion raises explicitly. |
| Older structure-lighting instance layout | Reach kit `_temp/s3d_avalanche.scenario_structure_lighting_info` contains only definition index, origin, forward and up in each instance; it lacks later fields including gel reference. Its definition uses `hotspot falloff size` instead of the current cutoff name. Native parsing succeeds; the older-layout converter is unimplemented. |
| Structure-lighting cinematic link export | Reading shot arrays and light-instance links is native. Rebuilding a tag with populated cinematic links raises explicitly until export can preserve/rebuild link indices and IDs correctly. `clear_lights` explicitly clears the links with the lights. Covered by generated fixtures. |
| Frame-event list script events | H4/H2AMP schemas expose readable `script events`, but Foundry has no corresponding animation-event property mapping. Native import/export raises for affected animations instead of dropping the scripts; scripts belonging to untouched animations survive partial exports. Confirmed with generated fixtures; no populated script block appeared in the 60-tag real-file acceptance sample. |
| Structure-design rain geometry | Native fields are readable, but the rain-blocker/sheet render-resource converter is unported. Native import raises before Blender allocation. Reproduced on Reach `foundry/scenarios/cache_build_full_test/default.structure_design` and `foundry/test_scenarios/rain_sheet/default.structure_design`. |
| H3/ODST structure-design water | Older water records expose `direction` and `angle`, without the later flow/fog fields. Mapping to Foundry water properties is unimplemented, so import raises explicitly. Reproduced on H3 `levels/dlc/descent/descent_design.structure_design` and ODST `levels/atlas/h100/h100_design_000.structure_design` (10 of 50 sampled tags). This is a conversion gap, not a byte-reading failure. |
| Render geometry and animation resources | The Python binding exposes the core structure-BSP and render-model mesh decoders plus detached, composed animation poses. A real ODST BSP decoded all 239 meshes, including water data; three real Reach render models covered rigid, skinned and triangle-strip geometry, including 23 distinct resolved bone indices. Real animation graphs from H3, ODST, Reach, H4 and H2AMP decoded in Blender without ManagedBlam, including the sampled H3 codec-slot-0 stream. Classic resource decoding also completed representative end-to-end imports: three filtered HCE Captain actions, and dozens of filtered H2 Brute actions with 104 renames and 68 events. Broad visual, unfiltered full-graph and editing-kit acceptance remains; no concrete failure is recorded for those H3+ geometry or classic animation samples. |
| Classic H1/H2 BSP auxiliary geometry | The Python binding exposes the native classic BSP scene extractor. Foundry imports render, collision and H2 portal geometry without the H3+ resource layout; it also creates H2 structure markers and referenced environment-object markers. Real HCE `levels/test/wizard/wizard` produced one structure mesh plus one collision mesh (13,622 Blender vertices / 5,804 polygons total). H2 `!extracted/zanzibar/zanzibar` produced 117 structure placements, 125 portals and one collision mesh. H2 `scenarios/solo/01b_spacestation/01outro_bsp` additionally produced five structure markers and one environment-object marker. Material records carry their complete shader paths and group extensions; 17/18 Wizard and 94/97 Zanzibar slots resolve, with the remaining slots being generated special materials. The decoder normalizes H2's offset-form and inconsistently oriented weather planes using each record's bounding-sphere center; Foundry imports the resulting `+weather` hulls as the Halo 2-only Weather Polyhedron mesh type, which legacy ASS export maps to Tool's special name/material convention. A full H2EK scan reconstructed 99 of 100 records across all 12 BSPs containing weather volumes. A Blender 5.1 Lockout roundtrip retained all ten typed weather instances and their `+weather` ASS material. `scenarios/solo/08b_deltacontrol/deltacontrolroom_bsp0` weather record 9 is an open four-plane prism with no Y bounds, so no closed hull can be recovered without inventing geometry. |
| Classic H1/H2 scenario decals | The compact classic placement records are now decoded directly: palette type, signed normalized yaw/pitch, position and the referenced decal's radius bounds. Native H1/H2 decal fields also feed Blender bitmap/color/alpha materials. A full local sweep decoded 3,735 HCE placements and 6,216 H2 placements with positive dimensions and unit rotations. Visual comparison of decal orientation and title-specific blend modes remains part of final acceptance; this is not a parser gap. |
| Halo 2 scenario decorators | Standalone `.decorator_set` tags now import their native embedded model buffers and generated quad/decal classes. All 24 local tags produced Blender geometry. Scenario import traverses H2's sparse decorator octree and decodes cell-relative position, class, permutation, surface-normal orientation, axial rotation, per-permutation scale and tint. A Cairo Station sample produced 326 placement records and packed positions agreed with generated decal centers within 0.007 world units. A Python 3.14 sweep decoded 1,485,497 importable placements from all 237 populated scenarios among the 333 local scenario files without an invalid class or range; it also found and skipped 14,246 orphaned groups with the source palette index `-1`, concentrated in editor backups. |
| Bitmap resource coverage | Bitmap tag fields and inline `processed pixel data` are read through blam-tags. Foundry now calls the native classic bitmap-to-TIFF decoder for H1/H2, including verified HCE shader bitmaps, H2 P8 bump data, mip-major 3D volumes and H2 RGBFP32 radiance maps; its classic 4x3 cubemap crosses are converted to 4x2 equirectangular TIFFs before Blender loads them. Modern supported formats continue through the existing Python decoders. The Tool fallback has been removed. Foundry follows blam-tags/Baboon in deriving modern base-mip byte counts from format and dimensions because real H3 through H2AMP tags commonly store zero in `pixels size`; the reported Reach Magnum diffuse and representative compressed, uncompressed, cubemap and array samples now extract. Full classic sweeps covered 1,825 HCE files and 4,636 H2 files. Eight HCE `shaders/foundry/bitmaps` helpers have non-classic headers and were excluded; every other pre-fix failure was one of the native cases resolved in READ-007. Resource-backed layouts and non-base mip selection are awaiting final migration review, so failures discovered there must be recorded as concrete cases. |
| Particle-model fidelity | Native particle geometry import is enabled for H3 through H2AMP. Representative tags from all five profiles decoded and allocated Blender meshes without source changes. Gen3 particle-model tags do not retain original object names or materials, so names are synthesized and no material is assigned. Only position, normal and primary UV streams are currently exposed to Python; other vertex attributes have not been found in the acceptance sample and remain unverified. H2 authoring now emits an 8210 JMI plus `<child>/render/<child>.jms` and dispatches Tool's dedicated particle-model or decorator-set importer. Rigid one-bone acceptance sources compiled into native `.particle_model` and `.decorator_set` tags; Tool rejects skinned particle sections, and Foundry validates both asset types before compilation. Final in-game acceptance and H3+ authoring remain. These are format/integration limits, not observed parser failures. |
| Serialized Havok geometry | Payload bytes read natively. The existing Foundry Python Havok decoder handles the two sampled vehicle payloads; unrecognized payloads now raise an unsupported error without ManagedBlam fallback. No specific failed payload is currently recorded here. |
| Light/function conversion | Native mappings that Foundry cannot reproduce in Blender now raise explicitly instead of reopening the tag through ManagedBlam. Some physical, directional and animated-light combinations remain unimplemented. Projected textures read through the native bitmap wrapper but still need final visual validation. Being able to read a function does not imply Foundry can reproduce its behavior in Blender. |
| Cinematic scripts | Foundry currently decodes script bytes as UTF-8 with an optional BOM and trailing NULs. The 76 sampled scripts passed. Other encodings are unverified, not a confirmed blam-tags byte-reading failure. |
| Writing and custom editors | The top-level cinematic writer, scenario object/decal/decorator import and common scenario edits, including airprobes, cubemaps, decorator placement export and template/global scenario export, are native. Shader functions can be decoded and the master type, color graph, colors and scalar clamp range can be saved through the native editor. Remaining specialized resource and playback work is tracked in the migration status; it is not a read failure. |

## Resolved read limitations

### READ-008 — optimized multipart curves without editor data (resolved 2026-09-24)

Some shipping Halo 4 tags retain only a `MultiSpline` compact and omit the
148-byte editable control-point trailer. blam-tags 0.1.9 reconstructs Linear and
Spline control points directly from the compact line or cubic coefficients;
Spline reconstruction is mathematically exact. Spline2 endpoints and tangents
are retained, although its original handle spacing cannot be recovered after
optimization. The three distinct forward/back, left/right and up/down camera
acceleration mappings in
`objects/props/covenant/drop_pod_elite/drop_pod_elite.vehicle` now describe as
one or two spline segments in both seat records. This removes all six remaining
failures from the 9,491-function corpus scan.

### READ-006 — Halo 2 decorator placement transforms (resolved 2026-09-24)

Foundry now decodes the complete 32-bit `internal data 1` placement word. The
layout was recovered from the H2 Tool runtime decoder: bits 0–2 select the
decorator class, bits 3–8 select its permutation, bits 9–12 encode a full-circle
axial rotation, bits 16–19 interpolate across that permutation's scale bounds,
and bits 20–31 store three signed 4-bit surface-normal components. Foundry reads
the referenced `.decorator_set` through blam-tags to resolve the scale bounds and
builds the placement quaternion from the decoded normal and axial angle. No
ManagedBlam or Tool subprocess fallback is used. Packed positions in H2
`temp_scenario/scenarios/solo/01b_spacestation/01b_spacestation.scenario` were
also checked against generated decal centers and agreed within 0.007 world units.

### READ-003 — complete transition-function descriptions (resolved 2026-09-23)

The native editor's transition option table previously stopped at index 3 even
though the engine lookup table and generated schemas define eight serialized
values. blam-tags 0.1.8 now exposes indices 0 through 7 as `linear`, `early`,
`very early`, `late`, `very late`, `cosine`, `one` and `zero`. A read-only scan
of 14,108 object tags across H3, ODST, Reach, H4 and H2AMP described 9,491
function payloads. All 27 former index-4/index-5 failures now decode; the only
remaining description failures at that stage were the compact-only H4 curves
subsequently resolved in READ-008.

### READ-005 — H1/H2 render-model skinning (resolved 2026-09-23)

`TagFile.render_model_meshes()` now returns authored skinning for both classic
model layouts. Halo 1 reads its two index/weight pairs and applies each part's
local-node table when the model flag enables it. Halo 2 selects the OLD or NEW
four-index array and applies the section node map. The rebuilt wheel matched an
independent structured-field decode exactly for all 6,025 HCE cyborg vertices
(16 distinct bones) and all 6,656 H2 Master Chief vertices (31 distinct bones).
Foundry's duplicate Python reconstruction was removed after this comparison.

### READ-007 — classic 3D volumes and RGBFP32 bitmaps (resolved 2026-09-23)

The native TIFF path previously rejected H1/H2 `3D texture` images and did not
recognize Halo 2's `rgbfp32` enum spelling. Real volume storage is mip-major: each
level contains all of its Z slices, and depth shrinks with the mip dimensions.
blam-tags now calculates that complete byte range and stacks the base level's Z
slices vertically for TIFF output. It also maps `rgbfp32` to the 96-bit float RGB
format and emits a clamped RGBA8 preview. The pre-fix corpus sweep decoded 1,814
of 1,825 HCE files and 4,586 of 4,636 H2 files. The genuine failures were three
volume tags in each game and 47 H2 lightmap-radiance tags; the other eight HCE
files were later-format Foundry helpers with non-classic headers. The rebuilt
0.1.6 wheel compiled successfully and a focused post-build check decoded all six
volume tags plus a representative RGBFP32 radiance tag (7/7) without an error.

### READ-004 — Halo 2 V3 `style` blocks (resolved 2026-09-22)

Some V3 style roots retain a stale inline count of one for an empty `special
movement` block. The following header belongs to the behavior-list block and
declares 128 elements, exceeding the special-movement schema maximum of one.
The classic reader now leaves an impossible header for the following field and
treats the stale block as empty. All 50 H2EK style tags open and serialize
byte-for-byte identically, including the nine former failures.

### READ-002 — classic H1/H2 Python loading (resolved 2026-09-22)

The Python binding now exposes `TagFile.read_classic(path, schema_path)`, and
Foundry selects it for H1/H2 documents after identifying the title directly from
the classic header. Real `HCEEK/tags/characters/captain/captain.biped` and
`H2EK/tags/objects/characters/brute/brute.biped` files opened as `HaloCe` and
`Halo2V4`; both serialized byte-for-byte identically without edits. This resolves
the Python entry-point failure. Fresh classic creation is now also available
through `TagFile.new_classic`; broad Blender import parity remains separate.

### READ-001 — fixed-array Python access (resolved 2026-09-18)

Added TagField.as_array() in the local binding and rebuilt Foundry's wheel.
H4/H2AMP cinematic visibility now reads stored 32-bit chunks directly, without
the ManagedBlam custom-field fallback. Tests cover bits 0/31/32/33, shot bounds,
save/reopen, field edits and stale handles. The 20-tag object sample (453 records)
also reads without errors or source changes. Older installed wheels must be
updated to use the accessor. Full visual cinematic parity remains unverified.

Recent migrations of older H4 physics layouts and cinematic fields removed Foundry
assumptions about layouts; they should not be reported as blam-tags parser fixes.

## New issue template

```text
ID / date:
Status: confirmed / needs reproduction / resolved
Game and tag path (relative to tags root):
Field path and type:
Operation / error:
Layer: Rust parser / Python binding / semantic decoder / Foundry integration
Minimal reproduction and expected result:
Current fallback or impact:
Fix and verification (when resolved):
```
