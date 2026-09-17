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
  for H4/H2AMP.
- Object model references, variants, change colors, seat and weapon names,
  magazine/tether metadata, first-person model edits and scenery lighting references.
- Object attachment references, marker names and scale-function names. Missing
  and unsupported attachments are filtered before opening a legacy converter.
- Cinematic-lighting creation and dynamic-light references, flags and placement
  metadata. Referenced light conversion still uses the legacy light wrapper.
- Object-function node creation for supported native editor shapes; unsupported
  shapes retain the legacy fallback before any nodes are created.
- Cinematic scenery conversion when the source block layouts match the target
  schema. Incompatible layouts use the isolated legacy copy fallback.

The Blender-facing classes retain their existing import locations. Their
implementations live in this package. Reference results are detached Python
objects; the few callers still passing them into legacy tag wrappers convert
references at that boundary.

The addon still requires ManagedBlam/Python.NET for unmigrated workflows:
object custom functions/light attachments and cinematic object conversion,
full geometry import, animation, bitmap operations,
shader functions, scenario/cinematic editors and other specialized helpers.
Removing that dependency now would break those workflows. The Foundation plugin
installer also still uses .NET independently of tag access.

## Build and generated assets

Use a Python environment with maturin installed and the Rust/MSVC toolchain:

```powershell
python blender/build_blam_tags.py G:\Halo\Modding\OtherProjects\blam-tags
```

The build uses a temporary source copy, stages the Windows abi3 wheel, registers
it in the extension manifest, and copies schemas needed by migrated workflows.
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
parenting with a stubbed light converter. Object custom functions and the cinematic
layout compatibility fallback use `managed_blam/object_legacy.py`; attachment import opens only
the referenced `LightTag` or `CheapLightTag` through the legacy converter.

Read-only sampling also exercised existing tag files from all five H3+ kits:
global/material metadata, 15 model tags with their render-model references,
and 25 object tags (scenery, weapons, bipeds, vehicles and machines).
A Reach Cortana definition references a missing option tag; this is reported
as a missing dependency instead of silently creating an empty tag. Editing-kit
acceptance of newly written tags and complete import/export parity are still
unverified.

## Remaining binding work

The current Python `TagFile.read` calls the MCC reader. Classic CE/H2 loose tags
need the Rust classic reader/creator exposed in Python. The camera wrapper
explicitly reports that capability gap. Creating an MCC container from an H1/H2
schema does not prove classic editing-kit compatibility.

Bitmap, render-geometry, animation and custom shader helper APIs need additional
Python binding coverage. Keep specific title selection distinct from tag-format
generation when migrating these systems.

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
and Reach/H4/H2AMP cheap lights. Unsupported function shapes retain a shared legacy
editor fallback; gel bitmap decoding also still requires ManagedBlam. H3/ODST light
falloff remains unimplemented. Static H4/H2AMP point, spot and directional light
tags now convert, including physical/artistic energy handling and shadow settings.
Animated intensity is supported for artistic point/spot lights. Animated radius
and cones, area lights and linked/projected physical or directional lights remain
unsupported. Unconnected identity curves evaluate at their constant input and
older Midnight layouts preserve defaults for unavailable shadow settings. The
read-only sample now converts 59 of 60 light tags. Unconnected deterministic curves
resolve through native evaluation; periodic or modifier-driven attenuation still
requires animation support. The remaining sampled tag is a physical light.
Light schemas
are staged by the build script as ignored generated assets, not committed sources.
Read-only sampling converted temporary copies of 36 H3 weapons, bipeds and
vehicles and verified their initial color permutations after reopening. All 36
used the native path; no original editing-kit tags were modified.
An additional scan of 933 H3 object tags found three populated color-function
blocks. Copies of all three convert natively, including the non-default colors
and scale inputs on the reactor sky tag. These tests do not establish editing-kit
acceptance of the resulting files.
