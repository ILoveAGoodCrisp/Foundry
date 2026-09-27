# Reach tag creation and null defaults

## Reproduced failures

Reach Tool's `verify-tag-load` reproduces the reported
`wrapped_arrays.h(36)` assertion on the generated Forge World scenario. The
failure happens while loading layout fields, before geometry compilation.

The generated layout has custom block-index definitions pointing at entry zero
of an empty custom-search-name table. The native reader tolerates this, but
Reach Tool does not.

Separately, blam-tags zero-filled scalar data for new tags and block elements.
This incorrectly initializes nullable block indices to element zero instead of
NONE (`-1`). This is distinct from an ordinary enum's first choice, which may
correctly be zero.

## Native fixes

Changes are in the existing dependency checkout:
`G:/Halo/Modding/OtherProjects/blam-tags/blam-tags/src/`.

- `schema.rs`: custom block indices now reference an actual search-name entry.
  Explicit schema search names are retained. Definitions missing this metadata
  use the engine's `void` search name. This fallback makes the layout valid; it
  does not reconstruct game-specific editor search callbacks absent from JSON.
- `data.rs`: initialize all six ordinary/custom 8/16/32-bit block-index types
  to `-1`. Apply defaults recursively to inline structures and arrays, for root
  creation and block add/insert. Duplicate and existing-tag reads retain their
  stored values. Ordinary enums, flags and integers retain their generic defaults.
- `api.rs`: newly initialized resource headers use the same scalar defaults.

The wheel was rebuilt and installed in Blender 5.2's extension environment.
The previous installation is preserved in
`site-packages/foundry-tag-defaults-fix-6bl1vl_i/previous`.
Running Blender processes must restart to load the new native module.

## Comparison against Reach's own library

Diagnostic reference tags were created with HREK's ManagedBlam library, using
tag-only initialization. This is a development check, not a new Foundry runtime
dependency. New scenario blocks were expanded three block levels deep; animation
graph defaults were inspected in memory at the same depth.

- The scenario comparison initially found 329 differing enum/integer/index
  fields. The generic index fix removes 316 of them.
- The remaining 13 scenario differences are per-tag initialization callbacks:
  squad/template and AI hint integer indices, weighted-choice chances, and an
  area-density preset enum. They are not fixed by treating enums as null indices.
- In the sampled animation graph, all 37 block indices default to `-1`.
  Of 27 enum fields, 26 default to zero and the facial wrinkle region defaults
  to 8. No sampled enum defaults to `-1`.
- Animation graph callbacks also initialize some plain integer fields to `-1`,
  including graph indices and several event data indices. These callbacks are
  **not implemented by the generic block-index fix**. Root graph creation also
  sets codec pack 6; Foundry already explicitly sets that and the Reach default
  gait group in its animation graph wrapper.

This audit is not a claim of complete parity with every engine placement
callback. Reproducing those remaining per-tag defaults needs explicit schema
metadata or separately verified callback handling, rather than a blanket enum
or integer rewrite.

## Verification

- `python blender/test_tag_defaults.py`: four tests pass, covering every index
  width, ordinary and custom indices, nested structures, arrays, add/insert,
  duplicate, round-trip persistence, legitimate zero/one choices, and valid
  custom-search table references.
- Blender `test_scenario_export.py`: three export-preprocessing tests pass.
- Blender `test_reach_geometry.py`: all seven geometry/water tests still pass.
- Reach Tool accepts both a fresh native scenario and the repaired Forge World
  scenario, exit code 0. Existing dependency warnings remain. This validates
  the reported tag-layout crash; a full geometry/tag export has not been rerun.

## Existing Forge World scenario

Prepared a corrected copy at:
`G:/Halo/Modding/Main/HREK/tags/foundry_blam/_codex_defaults_20260927/repaired.scenario`.
Compared the original's serialized tag data against fresh creation with the old
zero index defaults: all 5,387 bytes match. Thus the file has no additional edits
that would be lost by replacing it with the corrected creation result.

Original backed up beside the scenario as
`forge_world.scenario.before-defaults-fix.bak`.
Windows currently blocks replacing the active scenario because another process
has it open. The installed native fix and validated repair copy are ready;
replacement is pending release of that file lock.
