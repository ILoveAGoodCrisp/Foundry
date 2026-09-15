# blam-tags migration

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

The Blender-facing classes retain their existing import locations. Their
implementations live in this package. Reference results are detached Python
objects; the few callers still passing them into legacy tag wrappers convert
references at that boundary.

The addon still requires ManagedBlam/Python.NET for unmigrated workflows:
object tag operations, full geometry import, animation, bitmap operations,
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
- `tests/test_blam_packaging.py`

The additional camera and wrapper suites run inside Blender:

- `tests/test_blam_camera_blender.py`
- `tests/test_blam_wrappers_blender.py`

All 18 tests pass together in Blender 5.2 with addon dependencies available.
Coverage includes real tag serialization, edits and aborts, stale-handle-safe
block construction, model references/variants, native color channels,
title-specific fields, lightmapper settings, camera keyframes, packaging, and
addon imports. Wrapper tests assert that ManagedBlam is never initialized.

Read-only sampling also exercised existing tag files from all five H3+ kits:
global/material metadata and 15 model tags with their render-model references.
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
