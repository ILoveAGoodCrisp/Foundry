# ManagedBlam removal status

## Current position

The native foundation works, but most feature migration remains. Removing
ManagedBlam today would break core Foundry workflows.

Latest validation: 47 regression tests pass without starting ManagedBlam.
The read-only H4/H2AMP sample reaches conversion for 59 of 60 light tags. The last
tag is a physical light with periodic, modifier-driven attenuation. Sampling mocks
light allocation, final lighting setup and bitmap conversion; visual parity and
complete import/export acceptance are still outstanding.

The source audit after the structure seam/metadata migration found:

- 15 migrated tag workflows: camera tracks, globals, render-method options,
  render-method definitions, material-shader metadata, models, object metadata,
  lightmapper globals, cinematic-lighting metadata, light tags, cheap lights,
  structure seams, structure metadata, authored PCA animation and collision models.
- 26 tag classes still inherit the legacy `Tag` base, directly or indirectly:
  17 direct wrappers and 9 shader/material/decal subclasses.
- 25 modules under `managed_blam` still contain `SelectField` calls.

Physics constraints also use native records. Rigid-body shapes remain behind a
separate `LegacyPhysicsTag` fallback, so this does not reduce the legacy class count.

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

47 regression tests pass together in Blender, including native tag serialization,
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

Structure seams now read native final-point geometry and validate triangle indices
before Blender allocation. Triangles reference final points, correcting the old
reader's use of original vertices. Final edges are not required to build triangle
faces. Tests cover five H3+ schemas, rejected invalid indices, metadata count checks,
actual Blender mesh construction, BSP assignments and normal orientation. A read-only
sample of 25 real tags across five games read 102 seams and 1,220 triangles without
errors or source changes.

H4/H2AMP structure metadata now imports effects, airprobes, light cones and object
placements through native named fields. Tests cover quaternion/position/scale,
palette references, variants, script flags, collection names and objects-only mode.
The light-cone curve path now uses its string property instead of overwriting the
numeric intensity. Generated schemas remain ignored; full in-game acceptance of
both workflows is still outstanding.

Authored PCA animation now reads blendshape vertices, frame coefficients, animation
ranges and render-model mesh/compression metadata through blam-tags. The wrapper
no longer opens the legacy RenderModelTag for metadata. Tests cover both H4/H2AMP
schemas and create actual Blender shape keys and linear keyframes, checking vertex
deltas, weights and rejection of invalid frame ranges before allocation. In a
read-only sample, five PCA tags yielded 5,724 frame rows and 642,496 blendshape
vertices with no errors or source changes. All five lacked usable linked render
metadata, so this sample does not validate complete real-asset animation import.
Runtime resource-only PCA decoding and the existing vertex-count-based mesh
matching limitations remain separate work.

Collision models now read materials, regions/permutations, surfaces, vertices,
edges, node bindings and pathfinding spheres through native fields. Detached records
feed the existing Blender conversion, preserving surface-property handling. Surface
loops are validated with bounded traversal before allocation; missing armature bones
also fail before creating objects. H3/ODST plane orientation and H4/H2AMP unsigned
indices are handled explicitly. Tests cover five H3+ schemas, flags, materials,
pathfinding spheres, malformed loops, missing bones and a Blender BVH raycast.
A read-only sample decoded 50 real tags, 86 meshes, 3,631 polygons and six spheres
without errors or source changes. Full collision-mesh material/face-property and
armature validation in complete imports remains outstanding. This does not migrate
the separate structure-BSP or Havok collision readers.

Physics constraints now read natively for hinge, limited hinge, ragdoll, stiff spring,
ball/socket and prismatic types. Constraint-only physics tags do not start ManagedBlam;
tags containing rigid bodies still open the isolated legacy shape converter. Native
constraint/bone validation happens before object allocation. This fixes the duplicate
placeholder class hiding the hinge implementation, the child transform using the
parent Z position, and prismatic maximum limits incorrectly reading the minimum.
Tests cover all six types across five H3+ profiles, transforms, limits and missing
bones. Read-only sampling decoded 184 constraints (76 limited hinges and 108 ragdolls)
from 22 real character physics tags without errors or source changes. Full rigid-body
shape migration and complete physics import validation remain outstanding.

Standalone sphere rigid bodies now read native region/permutation assignments,
shape references, dimensions, materials and bone bindings. All referenced shapes
are checked before Blender allocation; unsupported primitives, compound shapes,
serialized shapes and explicit Havok bodies select the legacy shape converter for
the whole tag. Sphere conversion reuses the existing mesh/material code. Tests
cover five H3+ profiles, radius/translation scaling, materials, parenting and the
unsupported-shape boundary. Rigid-body migration remains partial.
In a read-only sample of 100 weapon physics tags, one contained a supported native
sphere body; the other 99 selected the legacy path, including six older H4 layouts.
This sample validates native eligibility and field decoding, not execution of the
legacy fallback or complete rigid-body mesh import.

Standalone box bodies now join spheres on the native path, including material,
half-extents, convex radius padding, translation and rotation metadata. The existing
box rotation calculation is preserved, including its known H4/H2AMP caveat. Expanded
tests cover all five profiles, matrix scale/translation, invalid extents and unbound
body fallback. The same 100-tag weapon sample now reads 13 native primitives from
seven tags; 93 still select legacy conversion, including four unbound bodies.

Standalone capsules (pill shapes) now read native endpoints and radius and reuse
the existing capsule mesh/transform convention. Tests across five H3+ profiles check
radius scaling, both transformed capsule endpoints and bone placement. Non-finite
endpoints are rejected; zero-length capsules select legacy conversion before any
objects are created. The 100-tag sample now reads 14 native primitives from eight
tags; 92 still select the legacy path. Compound shapes and Havok bodies remain the
main rigid-body migration work. Capsule mesh construction itself is unchanged.

Standalone convex polyhedra now decode packed vertex groups through blam-tags and
reuse the existing Blender convex-hull conversion. Tests across five H3+ profiles
cover nonzero vertex-group offsets, coordinate scaling, a real tetrahedron hull,
bone placement and invalid group ranges. All 47 migration tests pass without
initializing ManagedBlam. The same read-only 100-tag weapon sample now decodes 83
native primitives from 77 tags, with 23 selecting legacy conversion and no errors
or source changes. This sample checks metadata decoding, not complete Blender
imports. Compound shapes, serialized Havok bodies and older/unbound body layouts
still require the legacy path; full physics visual validation remains outstanding.

Flat lists of supported primitives now decode natively. Child ranges are derived
from list indices and packed child counts, independently of rigid-body traversal
order. Every child is decoded before Blender allocation; nested lists and other
unsupported child types retain the whole-tag fallback. Five-profile tests cover
nonzero list offsets, multiple children, repeated decoding, parenting, invalid
ranges and negative counts. All 47 migration tests pass without ManagedBlam.
The 100-tag weapon sample now decodes 101 primitives from 84 tags; 16 still select
legacy conversion, with no decoding errors or source changes. Complete Blender
mesh imports and visual parity remain unverified by this read-only sample.

MOPP wrappers now resolve native child geometry: H3/ODST/Reach use the stored list
index, while H4/H2AMP use the child shape reference. Supported primitives and flat
lists then follow the existing native path. This imports authored child geometry;
it does not interpret MOPP acceleration bytecode or serialized Havok bodies.
Five-profile tests cover MOPP-to-list traversal, invalid MOPP indices, H4/H2AMP
direct primitive children and nested MOPP fallback. All 47 migration tests pass
without initializing ManagedBlam. The weapon sample remains 84 native tags / 101
primitives out of 100 tags. A separate 100-tag vehicle sample decodes 71 native
tags / 371 primitives, with 29 selecting legacy conversion. Both samples report
no decoding errors or source changes; complete Blender imports remain unverified.

Nested lists and MOPP wrappers now traverse natively using an explicit stack.
Active-path cycle detection permits shared child lists while rejecting circular
references before Blender allocation. Expansion is bounded at 100,000 references
per rigid-body traversal. Unsupported leaf types still select whole-tag legacy
conversion. Expanded five-profile tests cover nested lists, shared children,
list cycles, H4/H2AMP MOPP self-cycles and no object linking on invalid input.
All 47 migration tests pass without initializing ManagedBlam. Serialized Havok
bodies, unsupported leaf shapes and older/unbound body layouts still require
migration; full Blender mesh and visual validation remains outstanding.

H4/H2AMP Havok rigid-body properties now read natively when the referenced authored
geometry is supported. The existing Blender mapping is preserved for mass and its
override flag, center-of-mass offset, inertia scaling and linear/angular damping.
Non-finite values are rejected; serialized Havok shapes still select the fallback.
Tests cover both profiles and exercise the actual property assignment helper.
All 47 migration tests pass without initializing ManagedBlam. This does not yet
validate Havok simulation behavior or complete Blender mesh imports.
