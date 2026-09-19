# blam-tags reading limitations

Last updated: 2026-09-19.

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
| READ-002 | H1/H2 classic tag files | Foundry's camera-track entry point explicitly rejects these games pending Python bindings for classic reading/creation. Creating an MCC-style test container from a schema is not proof of classic-format support. | Python integration gap. Rust support for these games does not establish that the current Python entry point can read their classic files. No classic-file acceptance result recorded. | Expose/verify the classic reader against real H1/H2 files before enabling Foundry workflows. |
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
| Structure-lighting projected textures | Native bitmap conversion is not implemented. Import refuses existing gobo/gel references before allocating lights. Seven of 60 sampled tags hit this gap, including Reach `foundry/scenarios/a50/default.scenario_structure_lighting_info`, H4 `cinematics/cin_m031_didact/lights/cin_m031_didact_020/cin_m031_didact_020_lighting_segment.scenario_structure_lighting_info`, and H2AMP `levels/sway/ca_ascension/ca_ascension_bsp01.scenario_structure_lighting_info`. The references themselves read correctly. |
| Structure-lighting animated functions | The current converter supports constant scalar functions. Two sampled H4 tags contain other function shapes: `cinematics/cin_m020_crater/lights/cin_m020_crater_000/cin_m020_crater_000_lighting.scenario_structure_lighting_info` and `cinematics/cin_m021_tower/lights/cin_m021_tower_010/lighting_segment.scenario_structure_lighting_info`. Their native function descriptions are readable; Blender conversion raises explicitly. |
| Older structure-lighting instance layout | Reach kit `_temp/s3d_avalanche.scenario_structure_lighting_info` contains only definition index, origin, forward and up in each instance; it lacks later fields including gel reference. Its definition uses `hotspot falloff size` instead of the current cutoff name. Native parsing succeeds; the older-layout converter is unimplemented. |
| Structure-lighting cinematic link export | Reading shot arrays and light-instance links is native. Rebuilding a tag with populated cinematic links raises explicitly until export can preserve/rebuild link indices and IDs correctly. `clear_lights` explicitly clears the links with the lights. Covered by generated fixtures. |
| Frame-event list script events | H4/H2AMP schemas expose readable `script events`, but Foundry has no corresponding animation-event property mapping. Native import/export raises for affected animations instead of dropping the scripts; scripts belonging to untouched animations survive partial exports. Confirmed with generated fixtures; no populated script block appeared in the 60-tag real-file acceptance sample. |
| Structure-design rain geometry | Native fields are readable, but the rain-blocker/sheet render-resource converter is unported. Native import raises before Blender allocation. Reproduced on Reach `foundry/scenarios/cache_build_full_test/default.structure_design` and `foundry/test_scenarios/rain_sheet/default.structure_design`. |
| H3/ODST structure-design water | Older water records expose `direction` and `angle`, without the later flow/fog fields. Mapping to Foundry water properties is unimplemented, so import raises explicitly. Reproduced on H3 `levels/dlc/descent/descent_design.structure_design` and ODST `levels/atlas/h100/h100_design_000.structure_design` (10 of 50 sampled tags). This is a conversion gap, not a byte-reading failure. |
| Render geometry, bitmaps and animation resources | Foundry still has legacy decoder consumers. Audit Python exposure and test concrete payloads before logging individual library failures. |
| Unbound physics bodies | Their fields can be read; correct Blender placement when the node index is -1 is unresolved. This is a conversion decision. |
| Serialized Havok geometry | Payload bytes read natively. The existing Foundry Python Havok decoder handles the two sampled vehicle payloads; unrecognized payloads now raise an unsupported error without ManagedBlam fallback. No specific failed payload is currently recorded here. |
| Light/function conversion | Some mappings, physical lights and projected textures retain fallbacks. Being able to read a function does not imply Foundry can reproduce its behavior in Blender. |
| Cinematic scripts | Foundry currently decodes script bytes as UTF-8 with an optional BOM and trailing NULs. The 76 sampled scripts passed. Other encodings are unverified, not a confirmed blam-tags byte-reading failure. |
| Writing and custom editors | Unported writers, playback helpers and function editing are tracked in the migration status; they are not read failures. |

## Resolved read limitations

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
