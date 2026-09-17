# ManagedBlam removal status

## Current position

The native foundation works, but most feature migration remains. Removing
ManagedBlam today would break core Foundry workflows.

Latest light validation: 39 regression tests pass without starting ManagedBlam.
The read-only H4/H2AMP sample reaches conversion for 59 of 60 light tags. The last
tag is a physical light with periodic, modifier-driven attenuation. Sampling mocks
light allocation, final lighting setup and bitmap conversion; visual parity and
complete import/export acceptance are still outstanding.

The source audit after the light-reader migration found:

- 11 migrated tag workflows: camera tracks, globals, render-method options,
  render-method definitions, material-shader metadata, models, object metadata,
  lightmapper globals, cinematic-lighting metadata, Reach lights and cheap lights.
- 30 tag classes still inherit the legacy `Tag` base, directly or indirectly:
  21 direct wrappers and 9 shader/material/decal subclasses.
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

39 regression tests pass together in Blender, including native tag serialization,
aborted writes, wrapper checks that reject ManagedBlam initialization, camera work,
metadata, object/cinematic copying and cinematic-lighting transforms. There is
also a Rust regression test for preserving unnamed flags during cross-tag copying.

Real-tag sampling includes H3+ editing-kit metadata and objects, 36 H3 conversions,
and all three populated color-function cases found in a 933-tag H3 scan. Tests use
temporary copies for conversions. Full editing-kit acceptance and complete
import/export parity have not yet been established.

Cinematic-lighting metadata now uses blam-tags. Converting referenced dynamic
lights uses the native `LightTag` reader for Reach; H4/H2AMP authored-probe conversion remains unimplemented,
matching the previous wrapper's behavior.

The first tag-function binding is implemented: `TagFunctionEditor` decodes and
describes functions, evaluates outputs and normalized shapes, and round-trips bytes.
It exposes basic, periodic, exponent, transition and MultiSpline editor graphs.
Object-function node creation now uses it. Unsupported editor shapes still fall
back before any nodes are created. A read-only sample across 60 H3+ object tags
decoded and round-tripped 266 functions; two unknown transition indices required
fallback. Editing methods and shader consumer migration are still pending.

Reach lights and Reach/H4/H2AMP cheap lights now decode mappings natively, including
input variables, range variables and output modifiers. Unsupported mappings use a
shared legacy editor fallback before Blender lights or nodes are allocated. Projected
gel textures still use the legacy bitmap decoder. Static H4/H2AMP point, spot and
directional light tags now convert natively; H3/ODST falloff conversion is explicitly unsupported because
its fields differ from Reach. H3/ODST have no cheap-light tag group.

A read-only sample of 120 real light/cheap-light tags across Reach, H4 and H2AMP
decoded and byte-round-tripped all 330 mappings without fallback. Regression tests
check color, intensity, distance scaling, spotlight angles, attachment dependencies,
unchanged source bytes and fallback before light creation. Full visual parity in
Blender and editing-kit acceptance remain to be checked.

The static H4/H2AMP converter follows the existing scenario-lighting mapping for
color, intensity, physical energy scaling, attenuation, cones and shadow/cinema
properties. Animated intensity/radius/cones, area lights and linked/projected
physical or directional lights are explicitly unsupported before allocation.
Artistic point/spot lights retain the existing Halo light node setup and bitmap
decoder boundary. A read-only sample of 60 real light tags reached conversion for
only two: 54 need unavailable curve-editor descriptions and four need animated
intensity support. This probe mocked Blender allocation, node construction and
bitmap decoding; it verified field conversion and unchanged tag bytes, not visual
parity. Decoder coverage and animated light conversion are the next priority.

Follow-up: all 54 unavailable descriptions were identity functions (type 0), which
have no editor trailer. The Python binding now describes their exact normalized
line, y = x, and preserves the original bytes. All 180 intensity, attenuation and
cone mappings in the same 60-tag sample now describe successfully. Identity curves
also produce verified Blender float-curve nodes. This resolves the decoder error;
it does not make input-dependent lights static, so animated H4/H2AMP conversion is
still required. Rebuild the wheel from the updated local blam-tags checkout.

Animated intensity now uses native function nodes for artistic H4/H2AMP point and
spot lights. Input, range and output-modifier dependencies reach attachments.
Scalar curves with equal finite output limits are accepted as static radius/cone
values; genuinely animated radius/cones and physical/directional intensity remain
unsupported. Animated intensity requires a finite positive normalization scale.
Basic function nodes now apply output modifiers and return the correct socket;
normalized additive modifiers retain their original units.

The same 60-tag sample now converts three lights; 57 stop at animated distance
attenuation. The probe built actual intensity node groups but mocked light
allocation, final Halo-light setup, bitmap decoding and UI node arrangement.
All original tag bytes remained unchanged. Visual parity remains unverified.

Follow-up on attenuation: 54 of those 57 failures were unconnected identity curves,
not animated inputs. These now evaluate natively at the same constant input (one)
and default range (zero) used by the Blender function graph. Their resolved output
is used for intensity, radius and cone size, rather than taking clamp_min. Connected
identity inputs, ranged inputs and output modifiers remain dynamic. The updated
fixtures check that an unconnected radius curve from 2 to 8 resolves to 8, while a
connected radius curve is rejected before light allocation.

Older Midnight layouts lacking dynamic shadow quality, shadow clip/bias fields or
cinema-object filtering now leave the corresponding Blender defaults intact. Legacy
Shadow Edge Filter is not reinterpreted as modern shadow quality. Active barn-door
or volume clipping remains explicitly unsupported. With these changes, 57 of the
same 60 real tags convert in the read-only probe; three still require animated
distance attenuation. The probe's mocked rendering/bitmap boundaries still apply.

Unconnected deterministic transition, MultiSpline and exponent curves now resolve
through the native evaluator too. This recovers two additional H4 lights and brings
the current sample to 59/60. Tests verify evaluated values beyond the stored clamp
bounds and ensure connected inputs, ranged inputs, output modifiers and periodic
functions are not incorrectly classified as constants. The remaining H2AMP tag,
`objects/weapons/h2a_oddball_ricochet/fx/ca_oddball_01a_red.light`, uses physically
correct lighting with periodic, modifier-driven attenuation and remains unsupported.
