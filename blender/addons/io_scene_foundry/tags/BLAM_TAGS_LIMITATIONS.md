# blam-tags reading limitations

Last updated: 2026-09-23.

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

| ID | Games / data | Failure and evidence | Layer / current workaround | Resolution needed |
| --- | --- | --- | --- | --- |
| READ-003 | Tag-function editor descriptions: unknown transition functions | The Python describe path raises `unknown transition function` when the transition index has no text mapping. Earlier read-only sampling found two such functions among 266 functions from 60 object tags. Exact asset paths were not retained in this record and must be captured on reproduction. Raw payload reading/round-trip succeeded; semantic description did not. | Function decoding/binding. Unsupported object-function conversion now raises an explicit error; the legacy editor fallback has been removed. | Reproduce and record tag path, field and index; support the missing transition or expose a lossless representation usable by Foundry. |
| READ-005 | Halo 1 `gbxmodel` and Halo 2 `render_model` render-mesh skinning | `TagFile.render_model_meshes()` currently returns `[0, 0, 0, 0]` and `[1, 0, 0, 0]` for every H1 and H2 vertex, discarding the authored node indices and weights. This made the HCE cyborg and H2 Master Chief meshes contain only a pelvis group. | Rust semantic render-model decoder. Foundry reads H1's two authored influences and optional part-local map, plus H2's four influences and per-section node map, through blam-tags' structured fields before Blender allocation. | Populate `RenderVertex.node_indices/node_weights` in `read_gbxmodel_render_vertex` and `read_h2_render_vertex`, applying each format's local node map, then rebuild the Python wheel. |
| READ-006 | Halo 2 scenario decorator placement transforms | blam-tags exposes the two packed 32-bit placement words only as `internal data 1` and `compressed position`; it has no semantic H2 decorator-placement decoder. Foundry now expands the octree-cell-relative 10/10/10-bit position exactly and resolves the decorator set, class and tint. Rotation and per-instance scale remain inside `internal data 1`, so imported H2 decorator clouds currently use identity rotation and unit scale. | Rust semantic scenario/decorator decoder. Foundry performs the verified position/type/tint decoding through structured fields and records the remaining loss explicitly rather than falling back to ManagedBlam. | Expose decoded H2 placement rotation and scale from blam-tags, backed by fixture values from Tool/Sapien, then replace the temporary identity/unit values. |

### Evidence locations

- READ-001: local `blam-tags/definitions/halo4_mcc/cinematic_scene_data.json`,
  `blam-tags-py/src/manual/handles.rs`, and Foundry `tags/cinematic.py`.
- READ-002: Foundry `tags/backend.py`, `CameraTrackDocument.__init__`.
- READ-003: local `blam-tags-py/src/manual/functions.rs` and the historical
  function-decoding sample in [MIGRATION_STATUS.md](MIGRATION_STATUS.md).
- READ-005: local `blam-tags/src/render_model.rs` functions
  `read_gbxmodel_render_vertex` and `read_h2_render_vertex`; verified with
  `HCEEK/tags/characters/cyborg/cyborg.gbxmodel` and
  `H2EK/tags/objects/characters/masterchief/masterchief.render_model`.
- READ-006: H2 `temp_scenario/scenarios/solo/01b_spacestation/01b_spacestation.scenario`;
  packed placement positions were checked against the centers of the tag's
  generated decal vertices and agreed within 0.007 world units.

## Separate integration work — not confirmed blam-tags read failures

| Area | What remains |
| --- | --- |
| Classic H1/H2 authoring | Existing loose tags use the schema-driven classic reader/writer and preserve their container on save. Representative HCE Captain/Pistol/Warthog and H2 Brute/Magnum/Warthog/Elite-Jetpack imports now complete the applicable render, collision and H2 physics paths. H1 legacy animation paths and aliases are reconstructed from its positional tables; all 213 HCE animation graphs resolved 10,061 authored paths in Blender. Unfiltered native decoding passed all 22 HCE Captain and 406 H2 Brute animations (14,013 composed frames). Metadata sweeps opened 429 HCE and 804 H2 biped, vehicle, weapon and scenery tags without a failure. A focused scan decoded all 144 candidate object functions from 296 H2 tags, including classic linear-key and spline payloads. Blender node construction also completed for all 1,412 HCE shader-family tags and all 3,107 H2 shaders; detail/multiply maps, UV scales, H1/H2 change colors, H2 alpha opacity and common emissive colors are connected. Classic cubemap references use Blender environment textures with reflection coordinates; H1 multipurpose masks and perpendicular/parallel reflection controls and H2 normal/glancing reflection controls are connected. H1 alpha-test flags and H2 alpha-test templates/maps now use the dithered Blender path. Fresh classic creation now uses `TagFile.new_classic(schema, game)`. H1/H2 biped defaults round-trip byte-exactly, and Foundry camera-track creation plus block editing survives save/reopen for both games. Model/sky/animation tag export now dispatches each editing kit's native commands; H1 object output writes its four independent model references and H2 writes the compiled model reference. Broad visual acceptance, exact additive/subtractive/multiply blend behavior, specialized animation metadata export and less common tag families remain. |
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
| Halo 2 scenario decorators | Standalone `.decorator_set` tags now import their native embedded model buffers and generated quad/decal classes. All 24 local tags produced Blender geometry. Scenario import now traverses H2's sparse decorator octree, expands cell-relative packed positions, resolves palette/class indices and preserves tint; the class is selected by the low three bits of `internal data 1`, independently of the group's shader index. A Cairo Station sample produced 326 placement records and packed positions agreed with generated decal centers within 0.007 world units. A Python 3.14 sweep decoded 1,485,497 importable placements from all 237 populated scenarios among the 333 local scenario files without an invalid class or range; it also found and skipped 14,246 orphaned groups with the source palette index `-1`, concentrated in editor backups. The remaining packed rotation/scale decoder is tracked as READ-006, so those two attributes temporarily import as identity/unit values. |
| Bitmap resource coverage | Bitmap tag fields and inline `processed pixel data` are read through blam-tags. Foundry now calls the native classic bitmap-to-TIFF decoder for H1/H2, including verified HCE shader bitmaps and H2 P8 bump data; its classic 4x3 cubemap crosses are converted to 4x2 equirectangular TIFFs before Blender loads them. Modern supported formats continue through the existing Python decoders. The Tool fallback has been removed. Foundry follows blam-tags/Baboon in deriving modern base-mip byte counts from format and dimensions because real H3 through H2AMP tags commonly store zero in `pixels size`; the reported Reach Magnum diffuse and representative compressed, uncompressed, cubemap and array samples now extract. Resource-backed layouts, non-base mip selection and the remaining format matrix are awaiting final migration review, so failures discovered there must be recorded as concrete cases. |
| Particle-model fidelity | Native particle geometry import is enabled for H3 through H2AMP. Representative tags from all five profiles decoded and allocated Blender meshes without source changes. Gen3 particle-model tags do not retain original object names or materials, so names are synthesized and no material is assigned. Only position, normal and primary UV streams are currently exposed to Python; other vertex attributes have not been found in the acceptance sample and remain unverified. Particle-model authoring/export is also unverified. These are format/integration limits, not observed parser failures. |
| Serialized Havok geometry | Payload bytes read natively. The existing Foundry Python Havok decoder handles the two sampled vehicle payloads; unrecognized payloads now raise an unsupported error without ManagedBlam fallback. No specific failed payload is currently recorded here. |
| Light/function conversion | Native mappings that Foundry cannot reproduce in Blender now raise explicitly instead of reopening the tag through ManagedBlam. Some physical, directional and animated-light combinations remain unimplemented. Projected textures read through the native bitmap wrapper but still need final visual validation. Being able to read a function does not imply Foundry can reproduce its behavior in Blender. |
| Cinematic scripts | Foundry currently decodes script bytes as UTF-8 with an optional BOM and trailing NULs. The 76 sampled scripts passed. Other encodings are unverified, not a confirmed blam-tags byte-reading failure. |
| Writing and custom editors | The top-level cinematic writer, scenario object/decal/decorator import and common scenario edits, including airprobes, cubemaps, decorator placement export and template/global scenario export, are native. Shader functions can be decoded and the master type, color graph, colors and scalar clamp range can be saved through the native editor. Remaining specialized resource and playback work is tracked in the migration status; it is not a read failure. |

## Resolved read limitations

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
