# ManagedBlam removal status

Track confirmed native read/binding gaps in
[BLAM_TAGS_LIMITATIONS.md](BLAM_TAGS_LIMITATIONS.md). Update that ledger whenever
a new unreadable tag/field is encountered or a recorded limitation is resolved.

## Current position

Migration policy: remove ManagedBlam entirely. Unsupported native operations must
raise explicit errors rather than fall back to ManagedBlam. Temporary breakage on
this branch is accepted; record gaps for investigation instead of preserving .NET
compatibility. Unported readers and writers still need replacement.

Latest integration: cinematic import and the top-level cinematic writer now use
native root, scene and scene-data entry points. Cinematic export writes settings,
scripts, scene/data references and transition tags through blam-tags. Its scenario
update also uses native blocks for the cinematic link, zone-set flags, anchors,
generated-script removal and Reach cinematic-resource synchronization. Camera
allocation and complete referenced-asset import remain to be validated. Physics
and object-function imports no longer call their legacy fallback wrappers.
Common scenario metadata and lightweight edits now use `ScenarioMetadataTag`:
scenario type/firefight detection, BSP/design/sky discovery, zone sets, lightmap
settings, sky assignment, cutscene titles and anchors, scenario copies, debug zone
sets, default starting profiles, airprobe export, cubemap generation and decorator
export, plus template palette and scenario-global tag export. Launcher, cache builder, lightmapper, cinematic UI and scenario import
setup callers use this native path. The full scenario importer now uses it for
scenario type, BSP/design/sky metadata and child-scenario discovery. Placed objects read their
palettes, names, transforms, variants, BSP membership, editor folders and parent
links natively; decals and decorator placement clouds also read native records.
The obsolete legacy scenario wrapper has been removed. Cubemap split-resource mirroring and BSP bitmap
references are native; bitmap checksum edits use the native bitmap wrapper. The
scenario and child-scenario import no longer use the legacy scenario wrapper.
The lightmap-quality menu now reads its names through the native lightmapper-globals
document rather than opening ManagedBlam directly.

The native foundation works, but most feature migration remains. Removing
ManagedBlam today would break core Foundry workflows.

Latest validation: 60 regression tests pass without starting ManagedBlam.
Bitmap field access, creation settings, processed-pixel extraction and Granny
preview data now use blam-tags plus Foundry's existing Python bitmap decoders.
The external Tool extraction fallback was removed. This bitmap batch has only
received static validation; full format and editing-kit review is intentionally
deferred until the broader migration review.
The obsolete ManagedBlam cinematic-scene wrapper has been removed; cinematic
scene import now lives directly on `NativeCinematicSceneTag`. Cinematic debug-menu
scene lookup and BSP-zone flags are also native. Common render-model metadata
queries (nodes, regions, permutations and marker groups) now use a native wrapper
in UI and export setup paths. That wrapper now lives in `tags`; the ManagedBlam
render-model module contains only the remaining geometry importer. Empty
region/permutation insertion and first-material lookup use the same wrapper; full
render geometry remains legacy.
The old `CinematicTag(Tag)` wrapper and its duplicate import path are gone. The
replacement creates and updates `.cinematic`, `.cinematic_transition`, `.scenario`
and Reach `.scenario_cinematics_resource` records without ManagedBlam. Generated
schemas remain ignored build assets sourced from blam-tags rather than committed
per-tag definitions. A focused in-memory schema check covered Reach, H4 and H2AMP;
complete editing-kit export acceptance is deferred to the final migration review.
The native cinematic-scene-data wrapper now lives with its camera document under
`tags`; the obsolete `managed_blam` forwarding module has been removed.
Focused schema checks exercised scenario BSP, sky, zone-set and lightmap fields for
H3, ODST, Reach, H4 and H2AMP. Block flags are edited through their native integer
value because blam-tags intentionally does not expose block-reference names as
ordinary flag options. No ManagedBlam fallback is used.
Additional layout checks covered default player profiles, cubemap records and
decorator placement fields across the same five profiles, plus H3/ODST/Reach
scenario cubemap resources. Decorator export now writes native fields directly;
the legacy serialized-block optimization and fallback writer were removed.
Particle-model import now calls the native blam-tags geometry decoder directly;
the legacy render-model bridge and eager `_GameRenderModel` allocation are gone.
Foundry validates every detached mesh before creating Blender data, then imports
positions, normals, primary UVs and variant-separated triangles. Read-only native
and Blender-allocation checks passed representative H3, ODST, Reach, H4 and H2AMP
tags (15 objects / 1,158 triangles) without changing source bytes. Gen3 object
names remain synthesized and material data is absent from that tag format.
Structure-lighting info now uses native reads and writes for Reach/H4/H2AMP,
including constant light functions, definition/instance indices, cinematic shot
flags and Reach lightmap-region geometry. Tests create real Blender point/spot/sun
lights and region meshes, reopen saved tags, replace definitions and check failed
writes leave saved bytes unchanged. Updating populated cinematic light links during
export is an explicit unsupported operation; clearing lights clears those links too.
Sampling 60 real tags (870 definitions, 1,652 instances) imported 334 light objects
from 50 tags. The other ten stop at documented texture/function/layout gaps.
The sampling uses identity transforms and stubs final light-node setup/energy
conversion; visual parity and editing-kit acceptance still need verification.
All sampled source bytes were unchanged. No ManagedBlam fallback was used.
Frame-event lists now read and write natively for Reach/H4/H2AMP. Partial exports
preserve other animations and shared reference indices; repeated exports reuse
references. Ranges, detached sound/effect/dialogue events, clearing and aborted
writes are covered by save/reopen tests. Populated script events have no Blender
mapping and raise explicitly for affected animations. The containing animation
graph is still legacy, so this does not complete animation import/export migration.
The native wrapper and Blender event records now live under `tags`; the legacy
animation graph keeps its graph-field adapter locally and no longer imports a
ManagedBlam frame-event module.
Read-only sampling of 60 real frame-event lists decoded 4,696 animation entries
and 3,623 event records with no errors or source-byte changes. Editing-kit
acceptance of newly written event lists remains unverified.
Particle-model export now creates an empty custom-points tag through blam-tags;
its schema is an ignored generated build asset and the export processor no longer
imports the ManagedBlam base for this operation.
The cinematic event UI now reads usable sound-effect names and playback contents
through a native sound-effect-collection document. Sound-class display labels use
the canonical indexed enum in the generated blam-tags schemas, replacing the final
ManagedBlam read in that UI module.
Standalone H4/H2AMP prefab import now resolves its structure-BSP reference through
a native prefab document instead of opening the prefab through ManagedBlam.
H4/H2AMP prefab export now writes structure-BSP external-reference records through
blam-tags. H3/ODST/Reach collision proxy export also restores omitted render-surface
mapping entries through the native structure-BSP document. The BSP importer now
gets collision-material metadata, compression bounds, H4/H2AMP emissive materials
render-material/lightmap properties and the structure-lighting reference from the
same native document. H3/ODST material property blocks and newer direct fields are
normalized into one record; geometry and resource decoding remain legacy.
Cluster portals, structure markers, H4/H2AMP structure-meta references and
H3/ODST/Reach environment-object placements now enter the BSP importer as native
detached records too.
Reach/H4/H2AMP cookie-cutter collision geometry now uses native bounded edge-loop
decoding. H3/ODST/Reach lighting-info material emissives are also native. The
already-native structure-lighting wrapper and shared coordinate-transform utility
have moved out of `managed_blam`, so their callers no longer import that package
solely for native lighting or transform operations.
The native camera-track Blender wrapper and its correction matrix now live in
`tags` as well; camera sync, import and cinematic export use that path directly.
The biped weapon-source picker now resolves multiplayer object-type indices and
weapon references through a native multiplayer-object-type-list document.

The local blam-tags API update had stashed Foundry's earlier function-editor and
lossless copy bindings. Those additions were restored alongside the new anchored
API without consuming the stash, and the wheel was rebuilt. The build now checks
required APIs before staging a replacement wheel. These source changes also live
in the separate blam-tags checkout and must accompany a reproducible build.
Structure-design boundaries now use native records across H3 through H2AMP;
Reach/H4/H2AMP water and fog are also native. Tests create actual Blender meshes,
check properties and reject malformed data before allocation. Material assignment
and transforms are stubbed in these tests; visual acceptance remains outstanding.
Read-only sampling decoded 38/50 real tags. Ten H3/ODST water cases and two Reach
rain cases report explicit conversion gaps, with all source bytes unchanged.
The importer no longer eagerly starts ManagedBlam. Unported tag wrappers can
still initialize it and must be replaced.
The read-only H4/H2AMP sample reaches conversion for 59 of 60 light tags. The last
tag is a physical light with periodic, modifier-driven attenuation. Sampling mocks
light allocation, final lighting setup and bitmap conversion; visual parity and
complete import/export acceptance are still outstanding.

The source audit updated on 2026-09-20 found:

- 17 migrated tag workflows: camera tracks, globals, render-method options,
  render-method definitions, material-shader metadata, models, object metadata,
  lightmapper globals, cinematic-lighting metadata, light tags, cheap lights,
  structure seams, structure metadata, authored PCA animation, collision models,
  scenario metadata/editing and scenario airprobes.
- 13 tag classes still inherit the legacy `Tag` base, directly or indirectly:
  4 direct wrappers and 9 shader/material/decal subclasses.
- 9 modules under `managed_blam` still contain `SelectField` calls (excluding
  the legacy base and generated type declarations).
- No direct `with Tag(...)` ManagedBlam call sites remain outside legacy wrappers.
  Indirect legacy wrapper calls remain, including shader template generation after
  native blank-tag creation.

Terrain-shader global-material lookup and inherited reference traversal now use a
native metadata wrapper. Terrain shader node construction and authoring still run
through the legacy shader base.
H4/H2AMP material metadata and H3/ODST/Reach shader metadata now provide albedo
bitmap, alpha-mode and physics-material reads. Decorator texture setup, Granny
texture extraction and BSP collision-material lookup use these native readers;
full node construction and material authoring remain legacy.
Native tag-reference lookup normalizes space-padded group codes from the generated
group index, including the H4/H2AMP `mat ` material group.
Non-node shader export now creates the selected empty shader tag through blam-tags.
The subsequent render-method template inspection/generation remains legacy.
Cinematic scene export now creates both scene files and writes scene-level name,
anchor, reset mode, header/footer scripts and the split data reference natively.
Shot settings and camera-frame arrays are also written natively across H3, ODST,
Reach, H4 and H2AMP. Scene objects, attachments, creation flags/scripts, references
and shot masks are written natively in both combined and split layouts. Lighting,
music, object functions, scripts, dialogue, effects, screen effects and user-input
constraints also write through blam-tags; cinematic export no longer opens a
ManagedBlam `Tag`. Focused schema checks covered these records and both 32-bit
shot-mask layouts across all five supported cinematic profiles. H3 lacks persistent
lighting, screen-effect and user-input-constraint fields and rejects populated
settings explicitly.

Physics also uses native records for constraints, spheres, capsules, boxes, convex
polyhedra, nested lists/MOPPs, H4/H2AMP body properties and supported serialized
Havok geometry. Native decoding covers 90/100 sampled weapon tags and 74/100
sampled vehicle tags. The remaining sampled vehicle cases have unbound bodies
and now raise an explicit unsupported error. The obsolete physics and object
legacy wrappers have been deleted. Cinematic scenery copying now propagates
native layout errors without reopening either tag through ManagedBlam.
These sample rates are not overall migration percentages.

These are code-inventory counts, not a percentage of engineering effort. Several
large remaining features depend on ManagedBlam resource decoders or custom editors,
and migrated wrappers can still hand specialized operations to legacy converters.

## Remaining work

Cinematic import now reads shot lengths, anchor and structure-lighting references
natively and iterates detached shot/object records. There are no direct SelectField
calls remaining in CinematicSceneTag.to_blender. NativeCinematicSceneTag exposes
that conversion through a native constructor, and top-level cinematic export is
native. Next: validate complete imports/exports and replace the remaining referenced
asset/resource readers.

READ-001 is resolved in the local binding: TagField.as_array returns fixed-array
struct handles with lifetime checks. H4/H2AMP shot visibility now reads native
32-bit chunks, and the ManagedBlam visibility fallback is removed. Unknown layouts
fail before object allocation. Tests cover cross-chunk bits, editing, save/reopen
and stale handles. Foundry's wheel has been rebuilt; older installed wheels need
updating to use the new accessor.

Cinematic object shot visibility now reads native 32-bit block flags for H3, ODST
and Reach. Enabled bits are bounded to the actual shot count before camera lookup.
H4/H2AMP fixed arrays use the local `TagField.as_array()` binding. Tests cover
native masks, cross-chunk bits and out-of-shot bits without a ManagedBlam fallback.

Cinematic object metadata now reads natively: scene names/variants and data-side
animation-graph/object references feed existing import logic. H4/H2AMP split tag
layouts are covered alongside older combined layouts. Scene/data object-count
mismatches are rejected before Blender allocation. All 53 regression tests pass.
Shot-active flags use native integer chunks; animation/resource import remains
legacy, so this is not a complete cinematic object migration.

Cinematic custom-script records now read natively from the camera/event source tag
and feed the existing SCRIPT event conversion. UTF-8 text, optional BOM and trailing
NUL terminators are handled without changing line endings; undecodable text raises
before Blender allocation. Frame/flag/identifier metadata is retained, including
defaults for fields absent in older layouts. Tests cover all five H3+ profiles and
event text. Read-only sampling decoded 76 scripts from 20 tags / 196 shots without
errors or source changes. All 53 tests pass. Existing event timing behavior and
script writing/language conversion are unchanged; full cinematic parity remains.

Cinematic lighting assignments now read natively: lighting-tag references, target
object indices, marker names and persistence flags feed the existing native
cinematic-lighting reader. Invalid subjects and empty references are skipped;
missing lighting files retain the existing import skip. Five-profile tests cover
references and invalid subjects. Read-only sampling decoded 757 assignments across
196 shots in 20 tags without errors or source changes. All 53 tests pass. This does
not establish full lighting visual parity or migrate assignment writing.

Cinematic user-input constraints now read natively from the scene tag, correcting
the H4/H2AMP import's previous scene-data lookup. Native records retain signed
top/left/bottom/right limits, frame, ticks and friction. Missing H3 blocks are empty;
camera application retains the existing last-record selection and absolute limits.
Five-profile tests cover layout differences and rectangle ordering. Real-tag
sampling decoded two constraints from 20 tags / 196 shots without errors or source
changes. All 53 tests pass; constraint writing is now native, while full camera
behavior validation remains outstanding.

Cinematic object-function keyframes and screen-effect records now read natively.
Function import preserves repeated-frame replacement, clear flags and interpolation
timing; the real-tag sample decoded 273 keyframes. Screen-effect import preserves
the existing last-valid-reference camera selection; H3's absent block is empty.
The same 20-tag / 196-shot sample decoded 64 screen effects without errors or source
changes. Timing/persistence metadata is read but camera application remains as
before. Writers now use native fields; complete cinematic validation remains.

Cinematic music cues now read natively from cinematic_scene, including H4/H2AMP
where camera/dialogue/effect data lives in a separate cinematic_scene_data tag.
Start/stop flags, references and frame offsets pass five-profile event-mapping
tests. Empty references are skipped, and mismatched scene/data shot counts are
rejected before Blender allocation. A read-only sample decoded 15 music cues from
20 tags / 196 shots without errors or source changes. Music writing now uses native
fields; full cinematic import/export validation remains.

Cinematic effect import now uses native references, frame timing, marker-parent
names, flags and H4/H2AMP state/function metadata. Empty references are skipped
before event creation; missing H3/ODST fields receive the legacy class defaults.
Five-profile fixtures exercise event conversion and title-specific frame offsets.
Read-only sampling decoded 266 effects across 196 shots in 20 real tags without
errors or source changes. Effect writing now uses native fields. Referenced-resource
workflows and full visual parity remain unvalidated.

Cinematic dialogue import now consumes native detached records for sound references,
timing, scale, actor and subtitle metadata. H3/ODST layouts omit female dialogue,
female subtitle and character fields; these receive empty defaults. Existing event
creation and title-specific frame offsets are preserved. Five-profile regression
tests exercise native records through the Blender event mapping. A read-only sample
decoded 123 dialogue entries across 196 shots in 20 tags without errors or source
changes. Dialogue/effect writing now uses native fields. Object animation and full
cinematic import parity remain.

Cinematic camera-frame decoding now uses native records for position, forward/up
axes and focal length. The existing cinematic import consumes these detached
records; the corresponding scene/data writer is native. Object animation and
complete visual validation remain.
Five-profile tests cover both camera layouts, save/reopen, detached record lifetime
and empty-shot rejection. A read-only sample decoded 196 shots / 27,495 camera frames
from 20 real cinematic tags without errors or source changes. This validates camera
data decoding, not complete cinematic import or visual parity. All 52 tests pass.

Polyart tag import/export now uses native vertex, index and placement blocks.
H4/H2AMP regression tests save/reopen fixture tags and create real Blender meshes,
checking position scaling, UVs, half-float alpha and invalid-index rejection before
mutation. Existing placement blocks are preserved. Camera creation retains the
previous fixed placement behavior; editing-kit acceptance and real-asset visual
parity remain unverified. Generated polyart schemas are ignored build assets.

Decorator-set metadata now reads natively, including H3/ODST single-model layouts
and later LOD references, instance names and decorator mesh indices. Render-model
geometry and bitmap conversion still use legacy readers. Tests cover five H3+
profiles, invalid indices, reference selection and unchanged source bytes.
The standalone `blender/example_edit_tag.py` demonstrates native read/edit/save;
its mass update was verified by reopening a temporary physics tag.

| Area | Work needed before removal |
| --- | --- |
| Functions, shaders and lights | Extend the new function-decoding binding to editing operations; port materials, shader variants, decals and light converters. Remove unsupported object-function fallbacks. |
| Geometry and resources | Port render models and the remaining collision, physics, decorator and polyart resource paths, including Blender mesh/skeleton construction. Particle-model import is native. |
| Animation | Expose animation decoding and port graph edits, frame events, PCA and animation import. |
| Bitmaps | Review the native/Python extraction path across formats, mipmaps, cubemaps and material texture use; complete any resource layouts not represented by processed pixel data. |
| Scenarios and cinematics | Port BSP/structure editors, lighting-info export and remaining referenced-resource workflows. Scenario object/decal/decorator import, cinematic scene/data writing, template/global scenario export and common scenario/cubemap/decorator edits are native. |
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

49 regression tests pass together in Blender, including native tag serialization,
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
Object-function node creation now uses it. Unsupported editor shapes raise before
any nodes are created. A read-only sample across 60 H3+ object tags decoded and
round-tripped 266 functions; two unknown transition indices remain unsupported.
Editing methods and shader consumer migration are still pending.

Reach lights and Reach/H4/H2AMP cheap lights now decode mappings natively, including
input variables, range variables and output modifiers. Unsupported mappings raise
before Blender lights or nodes are allocated; the shared ManagedBlam editor fallback
has been removed. Projected gel textures use the native bitmap wrapper and Foundry's
Python image decoder. Static H4/H2AMP point, spot and
directional light tags now convert natively; H3/ODST falloff conversion is explicitly unsupported because
its fields differ from Reach. H3/ODST have no cheap-light tag group.

A read-only sample of 120 real light/cheap-light tags across Reach, H4 and H2AMP
decoded and byte-round-tripped all 330 mappings without fallback. Regression tests
check color, intensity, distance scaling, spotlight angles, attachment dependencies
and unchanged source bytes. Full visual parity in
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

Older self-describing H4 physics layouts now use native authored geometry when
the serialized-shapes field is absent. Missing Havok flags are accepted only for
these older layouts, and MOPP traversal chooses the stored child-reference or list
field from the actual layout. A regression fixture exercises the older layout in
an H4 game context. All 47 migration tests pass without initializing ManagedBlam.
Read-only sampling now decodes 90/100 weapon tags (107 primitives) and 72/100 vehicle
tags (376 primitives), with no errors or source changes. The remaining vehicle
fallbacks are 26 tags with unbound bodies and two with serialized Havok shapes.
Unbound-body placement remains unresolved; complete Blender import validation is
still outstanding.

Serialized Havok payloads and per-shape material, friction, restitution and volume
metadata can now be detached through PhysicsDocument.serialized_shapes. Tests
cover H4/H2AMP byte-exact save/reopen, detached record lifetime and invalid indices.
All 49 migration tests pass without initializing ManagedBlam. A read-only scan of
40 H4/H2AMP vehicle tags extracted two serialized records (214,435 bytes); the
existing Python Havok decoder decoded both without errors or source changes.
This is preparation for native serialized-body import: the live import path still
uses its legacy fallback for these bodies, and Blender placement is not validated.

Serialized bodies are now connected to native PhysicsTag import. Native payloads
feed the existing Havok decoder; supported serialized shapes carry their material
and rigid-body properties into the existing mesh conversion. Authored primitives
on the same body are retained, and an absent primitive reference is accepted when
serialized geometry exists. All shapes decode before object allocation, with
whole-tag fallback for unsupported payloads and preflight checks for missing bones.
All 49 migration tests pass; H4/H2AMP wrapper tests cover serialized-only bodies,
parenting, property transfer and no object linking when a bone is missing. These
wrapper tests mock Havok decoding and object creation; real mesh import validation
for serialized bodies is covered separately below.

Native physics verification now also constructs real Blender meshes for spheres,
boxes, capsules and tetrahedral convex polyhedra through RigidBody.to_objects,
checking polygon creation, physics mesh classification and material assignment.
This uses fixture records and temporary property definitions, not full real-asset
imports. Non-finite friction/restitution values are rejected before object linking.
All 48 migration tests pass without initializing ManagedBlam. Unbound-body
placement remains unresolved and still uses the legacy fallback.

Real H4 Mammoth and Pelican physics tags pass native Blender mesh import in a
headless probe: 33 meshes / 5,228 faces and eight meshes / 584 faces respectively.
The probe uses real tag/Havok decoding, mesh creation, physics properties and bone
parenting, with synthetic skeletons, identity import transforms, temporary property
definitions and mocked region/permutation assignment. Source tags remain unchanged
and ManagedBlam is never initialized. Alignment to actual model skeletons and
visual/game parity remain unverified. Regression tests also exercise Havok mesh
triangle-mapping attributes and verify decoder failure selects legacy fallback
before native object creation. The complete suite contains 49 passing tests.
Native Blender-facing wrappers for model/object metadata, globals, lightmapper
globals, render-method definitions/options, material shaders, collision and physics
models, particle models, structure metadata/seams/design, PCA animation, lights and
cinematic lighting now live in the tags package. The model and object document
layers remain Blender-independent; their Blender behavior is isolated in dedicated
wrapper modules. Several of these wrappers still reuse conversion helpers from the
legacy-named connected geometry/material modules, which are the next separation
target.
