# blam-tags reading limitations

Last updated: 2026-09-22.

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
| READ-004 | Halo 2 V3 `style` tags | A one-file-per-group classic sweep opened 96 other H2 groups, but 9 of 50 real `style` tags fail with `unexpected EOF reading h2 block header: need 16 bytes, have 0`. Reproductions include `ai/all.style`, `ai/bunkering.style`, `ai/guarding.style`, `ai/harrassing.style`, `ai/hunting.style`, `ai/no_vehicle_for_you.style`, `ai/relaxing.style`, `ai/retreating.style`, and `objects/characters/monitor/ai/monitor.style`. All use the raw `BALM` Halo 2 V3 signature; 41 other style tags parse. | Rust classic parser/layout-version handling. No ManagedBlam fallback. | Identify which populated/truncated block in these V3 files lacks the expected 16-byte header and preserve its actual representation. |
| READ-003 | Tag-function editor descriptions: unknown transition functions | The Python describe path raises `unknown transition function` when the transition index has no text mapping. Earlier read-only sampling found two such functions among 266 functions from 60 object tags. Exact asset paths were not retained in this record and must be captured on reproduction. Raw payload reading/round-trip succeeded; semantic description did not. | Function decoding/binding. Unsupported object-function conversion now raises an explicit error; the legacy editor fallback has been removed. | Reproduce and record tag path, field and index; support the missing transition or expose a lossless representation usable by Foundry. |

### Evidence locations

- READ-001: local `blam-tags/definitions/halo4_mcc/cinematic_scene_data.json`,
  `blam-tags-py/src/manual/handles.rs`, and Foundry `tags/cinematic.py`.
- READ-002: Foundry `tags/backend.py`, `CameraTrackDocument.__init__`.
- READ-003: local `blam-tags-py/src/manual/functions.rs` and the historical
  function-decoding sample in [MIGRATION_STATUS.md](MIGRATION_STATUS.md).

## Separate integration work — not confirmed blam-tags read failures

| Area | What remains |
| --- | --- |
| Classic H1/H2 authoring | Existing loose tags use the schema-driven classic reader/writer and preserve their container on save. Representative HCE Captain and H2 Brute object imports now complete end to end with render/collision geometry, H2 physics, materials/bitmaps, filtered animation decoding and frame events. H1 legacy animation paths and aliases are reconstructed from its positional tables; all 213 HCE animation graphs resolved 10,061 authored paths in Blender. Creating a brand-new classic tag remains disabled because `TagFile.new(schema)` creates the MCC container; blam-tags needs an explicit classic creation API. Broad tag-family and visual acceptance and higher-fidelity H1 shader conversion remain. |
| Structure-lighting projected textures | Native bitmap conversion is not implemented. Import refuses existing gobo/gel references before allocating lights. Seven of 60 sampled tags hit this gap, including Reach `foundry/scenarios/a50/default.scenario_structure_lighting_info`, H4 `cinematics/cin_m031_didact/lights/cin_m031_didact_020/cin_m031_didact_020_lighting_segment.scenario_structure_lighting_info`, and H2AMP `levels/sway/ca_ascension/ca_ascension_bsp01.scenario_structure_lighting_info`. The references themselves read correctly. |
| Structure-lighting animated functions | The current converter supports constant scalar functions. Two sampled H4 tags contain other function shapes: `cinematics/cin_m020_crater/lights/cin_m020_crater_000/cin_m020_crater_000_lighting.scenario_structure_lighting_info` and `cinematics/cin_m021_tower/lights/cin_m021_tower_010/lighting_segment.scenario_structure_lighting_info`. Their native function descriptions are readable; Blender conversion raises explicitly. |
| Older structure-lighting instance layout | Reach kit `_temp/s3d_avalanche.scenario_structure_lighting_info` contains only definition index, origin, forward and up in each instance; it lacks later fields including gel reference. Its definition uses `hotspot falloff size` instead of the current cutoff name. Native parsing succeeds; the older-layout converter is unimplemented. |
| Structure-lighting cinematic link export | Reading shot arrays and light-instance links is native. Rebuilding a tag with populated cinematic links raises explicitly until export can preserve/rebuild link indices and IDs correctly. `clear_lights` explicitly clears the links with the lights. Covered by generated fixtures. |
| Frame-event list script events | H4/H2AMP schemas expose readable `script events`, but Foundry has no corresponding animation-event property mapping. Native import/export raises for affected animations instead of dropping the scripts; scripts belonging to untouched animations survive partial exports. Confirmed with generated fixtures; no populated script block appeared in the 60-tag real-file acceptance sample. |
| Structure-design rain geometry | Native fields are readable, but the rain-blocker/sheet render-resource converter is unported. Native import raises before Blender allocation. Reproduced on Reach `foundry/scenarios/cache_build_full_test/default.structure_design` and `foundry/test_scenarios/rain_sheet/default.structure_design`. |
| H3/ODST structure-design water | Older water records expose `direction` and `angle`, without the later flow/fog fields. Mapping to Foundry water properties is unimplemented, so import raises explicitly. Reproduced on H3 `levels/dlc/descent/descent_design.structure_design` and ODST `levels/atlas/h100/h100_design_000.structure_design` (10 of 50 sampled tags). This is a conversion gap, not a byte-reading failure. |
| Render geometry and animation resources | The Python binding exposes the core structure-BSP and render-model mesh decoders plus detached, composed animation poses. A real ODST BSP decoded all 239 meshes, including water data; three real Reach render models covered rigid, skinned and triangle-strip geometry, including 23 distinct resolved bone indices. Real animation graphs from H3, ODST, Reach, H4 and H2AMP decoded in Blender without ManagedBlam, including the sampled H3 codec-slot-0 stream. Classic resource decoding also completed representative end-to-end imports: three filtered HCE Captain actions with six events, and dozens of filtered H2 Brute actions with 104 renames and 68 events. Broad visual, unfiltered full-graph and editing-kit acceptance remains; no concrete blam-tags read failure is recorded. |
| Bitmap resource coverage | Bitmap tag fields and inline `processed pixel data` are read through blam-tags. Foundry now calls the native classic bitmap-to-TIFF decoder for H1/H2, including verified HCE shader bitmaps and H2 P8 bump data; modern supported formats continue through the existing Python decoders. The Tool fallback has been removed. Foundry follows blam-tags/Baboon in deriving modern base-mip byte counts from format and dimensions because real H3 through H2AMP tags commonly store zero in `pixels size`; the reported Reach Magnum diffuse and representative compressed, uncompressed, cubemap and array samples now extract. Resource-backed layouts, non-base mip selection and the remaining format matrix are awaiting final migration review, so failures discovered there must be recorded as concrete cases. |
| Particle-model fidelity | Native particle geometry import is enabled for H3 through H2AMP. Representative tags from all five profiles decoded and allocated Blender meshes without source changes. Gen3 particle-model tags do not retain original object names or materials, so names are synthesized and no material is assigned. Only position, normal and primary UV streams are currently exposed to Python; other vertex attributes have not been found in the acceptance sample and remain unverified. Particle-model authoring/export is also unverified. These are format/integration limits, not observed parser failures. |
| Serialized Havok geometry | Payload bytes read natively. The existing Foundry Python Havok decoder handles the two sampled vehicle payloads; unrecognized payloads now raise an unsupported error without ManagedBlam fallback. No specific failed payload is currently recorded here. |
| Light/function conversion | Native mappings that Foundry cannot reproduce in Blender now raise explicitly instead of reopening the tag through ManagedBlam. Some physical, directional and animated-light combinations remain unimplemented. Projected textures read through the native bitmap wrapper but still need final visual validation. Being able to read a function does not imply Foundry can reproduce its behavior in Blender. |
| Cinematic scripts | Foundry currently decodes script bytes as UTF-8 with an optional BOM and trailing NULs. The 76 sampled scripts passed. Other encodings are unverified, not a confirmed blam-tags byte-reading failure. |
| Writing and custom editors | The top-level cinematic writer, scenario object/decal/decorator import and common scenario edits, including airprobes, cubemaps, decorator placement export and template/global scenario export, are native. Shader functions can be decoded and the master type, color graph, colors and scalar clamp range can be saved through the native editor. Remaining specialized resource and playback work is tracked in the migration status; it is not a read failure. |

## Resolved read limitations

### READ-002 — classic H1/H2 Python loading (resolved 2026-09-22)

The Python binding now exposes `TagFile.read_classic(path, schema_path)`, and
Foundry selects it for H1/H2 documents after identifying the title directly from
the classic header. Real `HCEEK/tags/characters/captain/captain.biped` and
`H2EK/tags/objects/characters/brute/brute.biped` files opened as `HaloCe` and
`Halo2V4`; both serialized byte-for-byte identically without edits. This resolves
the Python entry-point failure. It does not establish broad Blender import parity
or support creating new classic tags.

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
