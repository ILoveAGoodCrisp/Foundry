# ManagedBlam removal status

## Current position

The native foundation works, but most feature migration remains. Removing
ManagedBlam today would break core Foundry workflows.

The source audit after the cinematic-lighting migration found:

- 9 migrated tag workflows: camera tracks, globals, render-method options,
  render-method definitions, material-shader metadata, models, object metadata,
  lightmapper globals and cinematic-lighting metadata.
- 32 tag classes still inherit the legacy `Tag` base, directly or indirectly:
  23 direct wrappers and 9 shader/material/decal subclasses.
- 29 modules under `managed_blam` still contain `SelectField` calls.

These are code-inventory counts, not a percentage of engineering effort. Several
large remaining features depend on ManagedBlam resource decoders or custom editors,
and migrated wrappers can still hand specialized operations to legacy converters.

## Remaining work

| Area | Work needed before removal |
| --- | --- |
| Functions, shaders and lights | Extend the new function-decoding binding to editing operations; port materials, shader variants, decals and light converters. Remove unsupported object-function fallbacks. |
| Geometry and resources | Port render models, collision, physics, particles, decorators and polyart, including resource extraction and Blender mesh/skeleton construction. |
| Animation | Expose animation decoding and port graph edits, frame events, PCA and animation import. |
| Bitmaps | Replace .NET bitmap extraction/conversion with native decoding; validate formats, mipmaps, cubemaps and texture use by materials. |
| Scenarios and cinematics | Port scenario/BSP/structure editors, lighting-info export, cinematic scenes/data/playback helpers and remaining layout fallbacks. |
| Dependency removal and acceptance | Remove startup validation and DLL initialization, revise packaging/UI, and run representative complete imports and exports with ManagedBlam unavailable. |

The Rust library already contains functionality in several of these areas, but
its current Python binding mostly exposes generic tag fields and math. Rust
capability does not yet imply Foundry can call it through Python.

## Recommended implementation order

1. Extend the tag-function decoding binding to remaining light/shader consumers and editing operations; eliminate unsupported-function fallbacks.
2. Expose resource, bitmap and animation APIs needed by Foundry; migrate their callers.
3. Complete geometry and scenario/cinematic workflows and eliminate fallbacks.
4. Remove dependency plumbing and verify complete workflows against editing kits.

H1/H2 classic tag loading/creation through Python is a separate requirement for
the all-MCC goal. It must be validated independently of H3+ MCC tag support.
Removing Python.NET entirely also requires replacing the Foundation plugin
installer's separate .NET assembly inspection in `tools/halo_launcher.py`.

## Validation so far

32 regression tests pass together in Blender, including native tag serialization,
aborted writes, wrapper checks that reject ManagedBlam initialization, camera work,
metadata, object/cinematic copying and cinematic-lighting transforms. There is
also a Rust regression test for preserving unnamed flags during cross-tag copying.

Real-tag sampling includes H3+ editing-kit metadata and objects, 36 H3 conversions,
and all three populated color-function cases found in a 933-tag H3 scan. Tests use
temporary copies for conversions. Full editing-kit acceptance and complete
import/export parity have not yet been established.

Cinematic-lighting metadata now uses blam-tags. Converting referenced dynamic
lights still uses `LightTag`; H4/H2AMP authored-probe conversion remains unimplemented,
matching the previous wrapper's behavior.

The first tag-function binding is implemented: `TagFunctionEditor` decodes and
describes functions, evaluates outputs and normalized shapes, and round-trips bytes.
It exposes basic, periodic, exponent, transition and MultiSpline editor graphs.
Object-function node creation now uses it. Unsupported editor shapes still fall
back before any nodes are created. A read-only sample across 60 H3+ object tags
decoded and round-tripped 266 functions; two unknown transition indices required
fallback. Editing methods and shader/light consumer migration are still pending.
