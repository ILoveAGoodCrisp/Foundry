# ManagedBlam removal status

Track confirmed native read/binding gaps in
[BLAM_TAGS_LIMITATIONS.md](BLAM_TAGS_LIMITATIONS.md). Update that ledger whenever
a new unreadable tag/field is encountered or a recorded limitation is resolved.

## Current position

**ManagedBlam runtime dependency removal: complete.** No tag wrapper inherits the
legacy `Tag` base, no add-on code imports CLR for tag access, startup no longer
validates or initializes `ManagedBlam.dll`, and editing-kit validation no longer
requires that DLL. The old `managed_blam` package name temporarily contains pure
Python Blender converters at stable import paths; its initializer cannot load .NET.

Migration policy: keep ManagedBlam entirely removed. Unsupported native operations must
raise explicit errors rather than fall back to ManagedBlam. Temporary breakage on
this branch is accepted; record gaps for investigation instead of preserving .NET
compatibility. Remaining work is native feature acceptance and direct-API cleanup.
Measured as dependency replacement, the migration is now 100%: the add-on has no
ManagedBlam tag-access path to fall back to. This does not mean every workflow has
completed visual or editing-kit acceptance.

**H1/H2 feature-parity estimate: about 96%.** Core loose-tag loading/saving,
object/model geometry, all H2 LODs, collision/physics, classic animation decoding,
bitmap and cubemap extraction, broad shader construction, scenario metadata,
native legacy export dispatch and inline animation-event writing, and scenario BSP
render/collision geometry are connected. The remaining work is concentrated in
less common resource layouts and broad visual/editing-kit acceptance.

## Editing-kit import acceptance (2026-09-22)

A Blender 5.1 background sweep now covers H3, ODST, Reach, H4 and H2AMP with
real files from the local editing kits. All five profiles imported representative
bipeds, weapons, scenery, particle models and scenario structure BSPs. The object
set comprised 16 import invocations (15 with geometry and one valid model-less
cinematic anchor); the BSP set included the 531-object ODST `c100` sample. H3,
H4 and H2AMP structure-design samples also passed.

The sweep fixed six concrete native-integration bugs: tag references now expose
their filename with extension; collision materials are immutable and hashable;
older render models tolerate absent sky-only flags; empty render parts are
skipped; ODST's direct triangle/section BSP surface mappings are supported; and
H4/H2AMP structure metadata receives its own initialized collection layer. An
invalid object document now stops cleanly rather than being dereferenced after a
parse failure.

The exact reported Reach Elite biped imports render, collision and physics
geometry and reads its animation graph and IK chains. A full action import was
allowed to decode hundreds of actions without an exception before the long smoke
run was stopped; exhaustive action and visual comparison remains part of final
acceptance.

Two structure-design samples continue to raise their existing explicit native
conversion errors: ODST `h100_design_000` needs direction/angle water conversion,
and Reach `cache_build_full_test/default` needs rain-blocker render geometry.
Their fields parse successfully and both are tracked in the limitations ledger.
Classic H1/H2 loose tags now cross the Python boundary through the Rust classic
reader/writer. Real HCE Captain and H2 Brute bipeds open with the correct engine,
group and schema and serialize byte-for-byte identically without edits. Foundry
also identifies these titles directly from all known classic header signatures.
The schema staging step now includes every generated H1/H2 group instead of the
H3+-focused subset. A one-real-file-per-group sweep opened 75 H1 and 96 H2 tag
groups. The former Halo 2 V3 `style` failure is resolved: all 50 style tags now
open and round-trip byte-for-byte. Broad Blender import acceptance
has now begun with full representative object imports. The HCE Captain biped
completed render and collision geometry, four shader-model materials and their
bitmaps and three filtered idle animations (29 objects, 18
meshes and 7 materials). The H2 Brute biped completed render, collision and
physics geometry, eight referenced shader material builds and classic bitmap
extraction including P8 bump data, dozens of filtered idle animations, 104
renames and 68 frame events (75 objects, 46 meshes and 12 materials). These
paths use native classic resource decoders exposed by blam-tags. Broad
tag-family and visual acceptance, an unfiltered full-graph pass and complete H1
shader fidelity remain unfinished. Fresh H1/H2 classic-tag creation now uses
the explicit `TagFile.new_classic(schema, game)` API. H2 creation emits its
required versioned root block header, and classic defaults use the engine's byte
order throughout their nested field tree. H1 and H2 biped tags survive an
unchanged byte-exact reopen/save cycle; Foundry camera-track documents also
survive create, block edit, save and reopen with their authored control point.
H1 legacy
animation paths are now reconstructed directly from its positional object,
seat, weapon, vehicle, device, first-person and unit-damage tables. A Blender
sweep opened all 213 HCE `model_animations` tags and resolved 10,061 authored
paths, including 8,246 aliases caused by animations reused across graph states.
The Captain sample now maps its shared `stand airborne-dead` animation to the
authored `alert:airborne-dead` state as well as its canonical stand state. H1
unit look and weapon aim screens are also read from their owning positional
records for Reach-style conversion. All 213 HCE graphs accepted the conversion
metadata; 35 graphs exposed 158 distinct look/aim overlays. When an animation
is shared by seats with different screen dimensions, Foundry keeps the screen
belonging to the animation's canonical authored path because a Blender action
can carry only one converted pose-overlay screen.

Classic scenario decals now use their actual H1/H2 layout instead of the H3+
quaternion/scale fields. Foundry resolves `decal type` through the classic palette,
expands the signed normalized yaw/pitch bytes to a unit quaternion, and derives the
display diameter from the referenced decal tag's radius bounds. H1 `.decal` map,
upper color bound and alpha and the equivalent H2 bitmap/color fields now build a
Blender material through the native tag document. A complete metadata sweep decoded
3,735 placements from 17 HCE scenarios and 6,216 placements from 183 H2 scenarios;
all references, positive dimensions and unit rotations validated without changing
source tags.

Bitmap extraction now derives base-mip storage size from the image dimensions
and format instead of trusting the tag's `pixels size` field. A cross-kit scan
found this field set to zero on otherwise valid H3, ODST, Reach, H4 and H2AMP
images across compressed, uncompressed, HDR and normal-map formats. The reported
Reach `magnum_diffuse.bitmap` now extracts as 512x512 from both HREK and HR3EK.
Smoke extraction also passed DXT1, DXT5, DXN, A8, V8U8, an H3 cubemap and an H4
three-layer texture array; arrays are emitted as a vertical layer strip.
Bitmap format enums are now normalized by their schema names before byte-size and
decode selection. H3 places DXN at enum index 33, where Reach places R16G16; treating
the index as cross-game made the reported 768x768 Hunter `hunter_zbump.bitmap`
appear four times larger than its payload. It now resolves as DXN and extracts to
a validated 768x768 TIFF.

Tag imports no longer require the owning editing kit to be registered as a
Foundry project. For an absolute path under a `tags` directory, Foundry first
asks blam-tags for the container game. Classic H1/H2 containers identify their
title directly; the shared H3+ container cannot distinguish H3, ODST, Reach,
H4 or H2AMP, so Foundry walks upward to `tool.exe` and reads its file
description. The resulting tags/data roots and game are held in an ephemeral
import context and are never added to preferences. With the configured project
list empty, real tags from all five H3+ kits resolved to the correct title and
the external Reach Elite imported 102 objects from its original location.
Configured cross-project imports now hold the same source-kit snapshot through
all Blender scene changes. Referenced models, animation graphs, shaders and
bitmaps therefore continue resolving under the imported tag's tags directory.
A probe switched the active scene back to H3 during a Reach Brute import and
still opened `HREK/tags/shaders/default_bitmaps/bitmaps/default_detail.bitmap`
with the Reach schema and tags root, covering the reported material-build crash.

The drag-and-drop object importer now establishes that ephemeral context before
reading invoke-time metadata such as variants. With Reach as the only configured
and selected project, the reported external ODST pod vehicle resolved to H3ODSTEK,
read all seven variants, and completed a Blender 5.2 import with 74 objects. Its
six physics bodies use node index `-1`; Foundry now preserves these model-space
bodies by parenting them to the armature object without assigning a bone. This
matches blam-tags' JMS physics representation and removes the previous unbound-body
conversion gap.

Latest integration: cinematic import and the top-level cinematic writer now use
native root, scene and scene-data entry points. The live scene wrapper and its
event adapters now reside in `tags`; obsolete `SelectField` readers/writers and
the old `managed_blam/cinematic_scene.py` module have been removed. Cinematic export writes settings,
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
Cache multiplayer/firefight validation now reads and writes required-resource
references, child-scenario presence, scenery palettes, player starts and generated
spawn/camera placements through typed `ScenarioMetadataTag` methods. The cache
builder also reads zone-set names natively and contains no `SelectField` calls.
Save/reopen checks covered Reach, Halo 4 and H2AMP scenario layouts.

The native foundation now owns every tag-wrapper lifecycle. Representative native
animation and shader/material reads pass in Blender with the legacy `Tag` base
deleted.

Animation-graph metadata now has a typed native wrapper for animation names,
skeleton nodes and parent indices, node usages, parent-graph references and frame
event-list references. Template node-order setup, imported first-person arm
parenting and the animation-command picker use it directly. New graph creation,
cinematic skeleton copying, parent-graph assignment and export-time node-usage
and IK-chain updates are native as well. Per-animation and forced-compression
settings also use the native graph writer, so pre-Tool graph setup no longer needs
ManagedBlam. Post-Tool world-relative animation flags are native across H3 through
H2AMP, as are vehicle-suspension marker, depth and destroyed-region updates. The
Reach animation importer now temporarily forces uncompressed data and restores the
original graph setting through the native wrapper; H3/ODST layouts without that
field and H4/H2AMP retain their existing no-change behavior. The
animation importer also reads IK-chain names and node bindings natively, updates
Blender's chain collection and creates the existing proxy/pole helper bones without
using the legacy graph field reader. The
pose-overlay automation now reads legacy blend-screen angles and frame grids
through the native graph wrapper. Reach/H4/H2AMP pose-overlay blend-screen setup
also writes its animation bindings, sources, flags, rates and weight functions
natively. Animation weights, loop frames, playback flags,
blend-time overrides and H4/H2AMP PCA group settings also write natively. The H1
post-Tool path now restores the subset its `model_animations` layout can
represent: weight, loop frame, compatible flags and world-relative state. A
save/reopen check on the real HCE Cyborg graph confirmed those edits through the
classic writer. Unsupported newer playback flags still raise rather than being
silently discarded. The generated graph schemas remain ignored build assets. Animation resource import
now uses the Rust pose decoder; specialized composite behavior and broad visual
acceptance remain.

H2 scenario export now carries Blender point, spot, directional and ambient
lights into each BSP's ASS source as native `GENERIC_LIGHT` geometry. Color,
intensity, cone angles, attenuation distances, area shape/aspect and transforms
round-trip through the existing ASS reader. H1 JMS has no corresponding light
record, so this is intentionally H2-and-later legacy behavior.
Cubemap checksum registration points and model-to-instance physics material maps
now use native fields; their tool callers no longer traverse ManagedBlam elements.

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
in UI and export setup paths. The full Blender render-model importer now lives in
`tags` and inherits the native document; its old ManagedBlam module has been
removed. Empty region/permutation insertion, first-material lookup, mesh resources,
materials, nodes, regions, markers, instances, compression bounds and skylights all
use blam-tags.
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
graph now discovers animation names/frame counts and assigns the imported-event
reference natively for export and the manual event-export operator. H3/ODST inline
graph events and Reach/H4/H2AMP shared animation events now import natively too,
including sound/effect/dialogue references and range collapsing. External event-list
events retain priority when merged with inline graph events. H3/ODST still reject
external event-list export because those layouts have no imported-event reference.
Animation rename generation now traverses the mode/state graph through blam-tags
for H3, ODST, Reach, H4 and H2AMP. It handles the older direct weapon-type layout,
the newer animation-set layout, damage directions/regions and both transition
representations; the importer no longer asks the legacy animation resource class
to generate Blender rename entries. Animation weights, loop frames, playback flags,
blend-time values, PCA group names and node-usage indices are now read by the same
native wrapper before resource decoding; the legacy importer consumes detached,
typed settings rather than selecting those graph fields through ManagedBlam. The
H4/H2AMP authored-PCA reference and mesh-group ranges also use detached native
metadata. Skeleton names, parent indices and additional-node default transforms
now travel in the same typed metadata bundle, removing those ManagedBlam field
reads from the resource importer.
Animation resource import now calls the Rust decoder through the typed
`TagFile.animation_pose()` binding. The binding returns owned transforms after
graph-selected overlay/replacement base composition, object-space correction and
movement decoding. The Blender importer converts those native tuples directly and
no longer initializes ManagedBlam or calls its former Python resource decoder.
Blender 5.1.2 checks decoded real H3, ODST, Reach, H4 and H2AMP graphs with a forced
failure if ManagedBlam starts. The sampled H3 codec-slot-0 stream also decodes
successfully through the Rust pipeline. Baboon's animation extractor uses the
same `blam_tags::extract` implementation.
H3/ODST shared-animation records omit the later FIK-anchor, object-space-offset
and extended-event blocks. The Blender importer now treats these blocks as absent
instead of dereferencing missing fields. Fresh Blender 5.2 imports decoded the
reported Brute `any any airborne_dead` action from both H3 and ODST. The bundled
wheel and the Python 3.14 installation expose `TagFile.animation_pose`; when an
older native module is already resident, the importer now requests a Blender
restart with a direct compatibility error.
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
The importer and shader/material/decal wrappers open native documents. The package
initializer no longer contains a ManagedBlam loader.
The read-only H4/H2AMP sample reaches conversion for 59 of 60 light tags. The last
tag is a physical light with periodic, modifier-driven attenuation. Sampling mocks
light allocation, final lighting setup and bitmap conversion; visual parity and
complete import/export acceptance are still outstanding.

The source audit updated on 2026-09-22 found:

- 17 migrated tag workflows: camera tracks, globals, render-method options,
  render-method definitions, material-shader metadata, models, object metadata,
  lightmapper globals, cinematic-lighting metadata, light tags, cheap lights,
  structure seams, structure metadata, authored PCA animation, collision models,
  scenario metadata/editing and scenario airprobes.
- No tag class inherits the legacy `Tag` base. Shader, material, decal and animation
  wrappers now inherit native documents.
- 6 modules under `managed_blam` still contain `SelectField` calls (excluding
  the legacy base and generated type declarations).
- 14 Python modules remain in `managed_blam`; the cinematic-scene, render-model
  and structure-BSP entry points have moved to `tags`.
- No ManagedBlam loader, `mb_init` call, DLL check or CLR tag-access import remains.
  Python.NET is retained only by the separate Foundation plugin installer.

Terrain-shader global-material lookup and inherited reference traversal now use a
native metadata wrapper. Terrain shader node construction and authoring run through
the native shader document and its temporary field-view adapter.
H4/H2AMP material metadata and H3/ODST/Reach shader metadata now provide albedo
bitmap, alpha-mode and physics-material reads. Decorator texture setup, Granny
texture extraction and BSP collision-material lookup use these native readers;
full node construction and material authoring now open native documents, with broad
visual acceptance still outstanding.
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

These sample rates are feature-acceptance evidence, not overall percentages.
Remaining specialized converters are Python code and native blam-tags adapters;
none can initialize ManagedBlam.

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

| Area | Post-removal acceptance work |
| --- | --- |
| Functions, shaders and lights | Shader/material/decal lifecycle, ordinary fields and the function edits currently used by shader authoring are native. Finish broad node-graph and light visual acceptance. |
| Geometry and resources | Complete acceptance of native render-model and structure-BSP import, including the H2 weather-volume representation, then port the remaining decorator, polyart and specialized resource paths. Render-model geometry, BSP render/collision/portal geometry, markers, environment objects and particle-model import are native. |
| Animation | Native decoding, pose composition, graph metadata/edits, frame events and PCA metadata are connected. Finish broad action-level visual acceptance and specialized composite cases. |
| Bitmaps | Classic H1/H2 processed-data coverage has a full-corpus audit: all genuine failures found there (3D volumes and H2 RGBFP32 radiance maps) are implemented in the bundled wheel. Review non-base mip selection, material texture use and resource layouts not represented by processed pixel data. |
| Scenarios and cinematics | Port remaining BSP/structure editors, lighting-info export and referenced-resource workflows. Scenario object/decal/decorator import, cinematic scene/data import and writing, template/global scenario export and common scenario/cubemap/decorator edits are native. |
| Dependency removal and acceptance | Dependency removal is complete. Run representative complete imports/exports with no ManagedBlam installation and finish visual parity review. |

The Rust library already contains functionality in several of these areas. Its
Python binding now also exposes the renderer-ready model/BSP meshes, classic
animation poses, bitmap conversion and authored physics shapes used by Foundry;
other Rust capabilities still need explicit Python entry points before Foundry
can use them.

## Recommended implementation order

1. Validate complete H1/H2 exports in Tool, including imported H2 weather hulls.
2. Run representative complete imports/exports against H1 and H2 editing kits and compare the resulting Blender data visually and in Tool.
3. Run the same acceptance pass against each H3+ editing kit.
4. Close specialized composite-animation, bitmap-format, resource-layout and scenario/cinematic gaps found by that review.

H1/H2 classic loading, saving and new-tag creation are exposed through Python.
They have real-file coverage across object, model, shader, bitmap, animation,
scenario and BSP paths; broad workflow and visual acceptance remain separate
requirements for the all-MCC goal.
The Foundation plugin installer now reads Windows PE file-version resources
through the standard library. The extension manifest and build helper no longer
ship Python.NET, clr-loader, cffi or pycparser; none are needed by tag access or
plugin version checks.

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

The tag-function binding is implemented: `TagFunctionEditor` decodes and
describes functions, evaluates outputs and normalized shapes, and round-trips bytes.
It exposes basic, periodic, exponent, transition and MultiSpline editor graphs.
Object-function node creation now uses it. Unsupported editor shapes raise before
any nodes are created. blam-tags 0.1.8 expands transition descriptions to all
eight schema-defined values. A read-only scan across 14,108 H3-through-H2AMP
object tags described 9,491 function payloads and eliminated all 27 former
index-4/index-5 failures. blam-tags 0.1.9 also reconstructs editor-shaped spline
controls from optimized `MultiSpline` compacts which omit their editor trailer.
The three unique camera-acceleration mappings duplicated across two seats in the
H4 Elite drop-pod vehicle now describe successfully, eliminating the final six
failures from that corpus scan.
H3 and ODST object-function records omit Reach's ranged-interpolation-name field;
the native converter now preserves those functions with no range dependency. The
reported ODST Hunter biped completed a Blender 5.2 render, collision and physics
import with 61 objects after this older-layout correction.
The binding now also writes master types, color graph types, colors and scalar
clamp ranges. Shader/material/decal wrappers use native documents, and a real H3
animated shader parameter was decoded, changed, saved and reopened successfully.
Broader node-graph visual acceptance remains.

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
tags (376 primitives), with no errors or source changes. At that stage, 26 vehicle
tags had unbound bodies and two had serialized Havok shapes; both forms have since
been connected to the native Blender import path. Broader visual validation remains.

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
The native backend now carries concrete blam-tags annotations for tag files,
structs, fields, blocks and generated camera-track math values. Its public `tag`
property remains precisely typed while the optional closed-state handle stays
private. Model/object helpers propagate the wheel's struct and block types, and
the Blender mixin accepts the shared native tag-path protocol. The wheel's shipped
`py.typed` stubs provide completion without importing Blender or eagerly loading
the binding during add-on startup.

The standalone animation resource codec now lives in `tags/animation_resource.py`.
The unused ManagedBlam assembly-loader helper was removed.
Structure BSP collision resources now traverse the blam-tags resource-interface
struct. Standard and large collision BSPs are detached with validated edge loops,
surface flags and material indices, then passed to the existing Blender mesh
converter. Structure surface-to-render-triangle mappings and H4/H2AMP serialized
Havok payloads are also detached natively. The old safe-SelectField helper and
debug Havok reader have been removed. Cluster-to-mesh indices are native across all
five H3+ profiles. Instance transforms, names, flags and policy metadata are also
detached through typed native records; their legacy constructor and field reads
have been removed. Instance-definition collision BSPs, surface mappings, cookie
cutters and Reach physics polyhedra now follow the same path. The blam-tags Python
binding now exposes its existing renderer-ready structure-BSP mesh decoder, so
the final render-resource reads and ManagedBlam render-model helper have also been
removed. A real ODST BSP decoded 192 definitions, 239 meshes, 273,970 vertices and
160,637 triangles, including nine water meshes, without ManagedBlam. The BSP
import wrapper now inherits the native document directly and lives in `tags`.
A Blender 5.2 background smoke check converted a detached native mesh record into
the expected Blender vertices, polygon, material, normals and UV layer.
Render-model geometry now uses the same detached renderer-ready mesh path. The
local Python binding exposes `TagFile.render_model_meshes()` over the existing
cross-game Rust decoder, and the Blender importer no longer allocates
`_GameRenderModel` or reads its raw vertex/index blocks. Real Reach weapon,
character and triangle-strip models decoded 6 meshes, 21,941 vertices and 22,612
source triangles in about 0.13 seconds total. A skinned grunt model resolved 23
distinct bone indices across 5,681 weighted vertices; this also fixed unsigned
byte node-index decoding and applies per-mesh node maps in the Rust render layer.
A Blender 5.2 background check converted the strip-heavy sample into 240 vertices
and 228 Blender faces after Foundry collapsed the 228 reverse-wound duplicates to
two-sided face metadata. Nodes, regions/permutations, markers and instance
placements now enter the importer as typed native records too; a real character
sample detached 30 nodes, four regions and 19 marker groups and passed their
existing conversion classes. Render materials, compression bounds and skylights
are native as well. The compatibility importer now inherits the native document,
moved into `tags/render_model_blender.py`, and the old ManagedBlam render-model
module was deleted. It still reuses Blender conversion classes from the
legacy-named `connected_geometry.py`; separating those helpers and broad editing-kit
acceptance remain, but opening/importing a render model no longer initializes
ManagedBlam.

Halo 2 render-model permutations now retain all six classic section references
instead of selecting one section. The Blender importer creates and labels every
valid L1-L6 object, including separate semantic LOD objects when multiple levels
share one section. Object properties expose the hardcoded L1-L6 choice beside
Region and Permutation for Halo 2 projects; L5 is the default and L6 is reserved
for cinematic geometry. Legacy JMS import/export carries the same LOD value.
A Blender 5.1 background import of the real H2 Brute render model decoded 18
permutations and produced 108 meshes, six per permutation, with all L1-L6 labels.

Legacy tag export now supports H1 and H2 as well as H3/ODST. H2 uses its
available `bulk-import-model-folder` command rather than the H3-only draft verb,
then uses `model-animations` and the native classic object writer. H1 writes
render JMS files under `models`, combines collision/physics source geometry in
Tool's `physics` directory, and dispatches the separate `model`,
`collision-geometry`, `physics` and `animations` verbs. Newly created H1 object
tags receive independent gbxmodel, model-collision, model-animations and physics
references through blam-tags. Isolated editing-kit probes produced valid H1
gbxmodel/collision/physics files and H2 model/render-model files; command-dispatch
checks cover both games. H1 skips the H2+ graph pre/post-processing pass because
its animation tag and metadata layout are distinct.

Classic animation events are now written after Tool compiles the JMA sources.
H1 exports its representable left-foot, right-foot and single-sound slots; H2
exports inline frame, sound and effect blocks and reuses or appends the graph's
shared references. Partial animation exports update sampled animations plus any
unsampled scene animation carrying authored events. Unsupported event kinds,
reference flags and data fields raise before saving rather than being discarded.
Save/reopen roundtrips passed against copies of the real HCE Sniper first-person
graph and H2 Brute graph, including newly appended sound/effect references. H1
import also now treats its zero foot-frame value as the format's empty sentinel.

H1 tag compilation now always invokes `tool.exe`, so selecting `tool_fast` in
Foundry no longer breaks an H1 export. H1 Tool reads its shader-class question
directly from the Windows console, so Foundry now prevents the prompt by creating
missing material tags first. Model-family compilation creates `shader_model`,
while scenario structure compilation creates `shader_environment`. H1 and H2
scenario exports now dispatch one `structure` command per exported BSP source,
then use blam-tags to create or update the parent `.scenario` and append any
missing compiled BSP references without replacing existing scenario data. New
classic scenarios also receive the selected scenario type and a default player
start/profile; this now applies to H1 even though its animation-graph
preprocessing remains intentionally separate.

Legacy export now canonicalizes the resolved asset destination before handing it
to the backend. The initial `data\\halo\\halo.asset` fallback no longer overrides
an asset marker, and the backend always derives the asset name from the resolved
folder.

H1–ODST sidecars are restored as lightweight asset markers. The export operator
uses a saved sidecar path first and a `.blend` folder inside `data` second to
initialize Legacy Asset Folder, which repairs stale `data\\halo` settings when a
blend already belongs to another asset. Export creates the marker when absent;
legacy Tool commands continue to consume JMS/ASS/JMA sources directly.

Asset-marker resolution remains read-only in the export operator constructor;
Blender disallows Scene ID writes in that context. The resolved path is applied
and persisted during operator execution instead, including Quick Export.

H1 JMS material generation no longer emits the later precise-position `)`
suffix. H1 Tool interpreted that character as part of the shader name and could
create tags such as `invalid).shader_model`; new H1 sources now resolve the
intended `invalid.shader_model` name.

Classic Sky export now writes the correct `.sky` group through blam-tags. H1
updates its gbxmodel and optional model-animations references; H2 updates its
render-model and optional model-animation-graph references. Existing sky
radiosity, fog, shader-function and light data is preserved.

Classic scenario metadata now treats zone sets, per-BSP default skies and
structure-lighting references as layout-dependent fields. H1/H2 scenario import
can enumerate its BSPs and skies without requiring the later zone-set records;
H1 uses the first available sky where its BSP reference has no default-sky
field. Scenario type enum names are normalized to Foundry's existing numeric
campaign/multiplayer/main-menu contract.

Classic scenario geometry now uses the existing native H1 JMS and H2 ASS
extractors through the typed `TagFile.classic_sbsp_scene()` Python entry point.
The result carries renderer-ready meshes, placements, transforms and an explicit
render/collision/helper classification; it does not route classic tags through
the H3+ `render geometry` resource layout. A Blender 5.1 background import of the
real HCE Wizard BSP produced one structure mesh and one collision mesh (13,622
vertices / 5,804 polygons total). The real H2 Zanzibar BSP produced 117 placed
structure objects, 125 portals and one collision mesh. A second H2 sample,
`01outro_bsp`, produced five structure markers and one referenced
environment-object marker. Classic BSP materials now carry their complete tag
paths and group extensions into Blender rather than requiring a basename search.
H2 weather planes now normalize the title's offset-form distance and inconsistent
normal directions against each record's bounding-sphere center. Foundry imports
the recovered `+weather` hulls as a dedicated Weather Polyhedron mesh type. The
type is available only in Halo 2 scenario UI and maps back to Tool's special
object/material convention during legacy ASS export. A full H2EK scan
reconstructed 99 of 100 weather records across all 12 BSPs that contain them.
The remaining `08b_deltacontrol/deltacontrolroom_bsp0` record 9 has no Y-bound
planes and therefore does not define a closed hull. A Blender 5.1 end-to-end
check of the real Lockout BSP imported all ten closed hulls with the dedicated
type and exported a parseable ASS retaining one `+weather` material plus the
ten `+weather_0` through `+weather_9` instances. Direct H2 ASS import also
recognizes `+weather` materials and assigns the dedicated type; other project
types continue to treat that legacy marker as ordinary structure geometry.

Classic object acceptance now covers representative H1 and H2 weapons, vehicles
and scenery as well as bipeds. H1 positional object functions retain their input
dependencies without assuming Halo 2's named function fields. H1 object physics
metadata is no longer mistaken for a geometric physics-model tag, and its
collision material flags read through the native field handle. Halo 2 empty tag
references no longer acquire a bogus extension from unused group bytes. Its
classic 20-byte object-function layout now decodes identity, constant, transition,
periodic, linear, linear-key and spline curves directly. A full scan opened all
296 H2 biped, vehicle, weapon and scenery tags in the local kit and decoded 144
candidate object functions without an error. Blender 5.1 imports completed HCE
Pistol and Warthog plus H2 Magnum, Warthog and Elite Jetpack samples; the H2
Warthog imported render LODs, collision and physics as 472 objects/401 meshes.
A separate metadata sweep opened 429 HCE and 804 H2 biped, vehicle, weapon and
scenery tags and read their inherited object records, model references, variants,
attachments, change colors and weapon metadata with no failures.
An expanded H2 acceptance sweep now covers all 1,527 concrete object tags across
bipeds, crates, creatures, devices, equipment, garbage, projectiles, scenery,
sound scenery, vehicles and weapons. It decoded all 274 stored object-function
mappings without a failure; every mapping in this editing kit uses scalar output.

Halo 2 decorator-set tags now use their native classic layout rather than the
later render-model-reference layout. Foundry imports embedded model vertices,
indices, normals, UVs and shader references, and creates representative source
planes for billboard, rotating-quad and decal classes. A Blender 5.1 sweep imported
all 24 local H2 decorator sets as 184 objects with 2,784 vertices and 1,778 faces.
Halo 2 scenario decorator placement caches now traverse their sparse spatial
octree and decode the cell-relative 10/10/10-bit positions, palette/class and
permutation selections, tint, surface-normal orientation, axial rotation and
per-permutation scale. The complete `internal data 1` layout and quantization
constants were recovered from H2 Tool's runtime decoder; referenced decorator-set
tags provide each selected permutation's scale bounds. A Cairo Station sample
produced 326 records; four packed positions checked against generated decal-vertex
centers agreed within 0.007 world units. A Python 3.14 sweep decoded 1,485,497 importable placements
from all 237 populated scenarios among the 333 local H2 scenario files without an
invalid range or decorator-class index. It separately found and skipped 14,246
orphaned groups whose source palette index is `-1`, concentrated in editor backups.

Classic shader acceptance now builds Blender node trees for all 1,412 genuine HCE
shader-family tags in the local kit, covering model, environment, glass, water,
meter, plasma, Chicago and generic families. It also builds all 3,107 H2 shader
tags across the kit. H1 model shaders now apply their authored detail map and UV
scale using double-biased multiplication. H2 shaders now combine primary and
secondary detail maps, carry their authored UV scales, apply separate alpha maps
and constant opacity, and recognize `emissive_color` alongside the older
`self_illum_color` name. This is broad construction acceptance; environment-map,
change-color and exact blend-template behavior still need visual review.

H1 model-shader multipurpose maps now honor the H1A/PC and optional Xbox channel
orders. Their change-color masks read Primary through Quaternary instance colors,
self-illumination uses the green mask, and the reflection channel drives the
Principled specular level. H2 `change_color_map` RGBA channels now drive the same
four instance colors; authored multiply maps and emissive-map tint colors are also
connected. The complete 1,412/3,107 shader construction sweep still passes after
these additions.

Classic cubemap references now use Blender environment textures fed by reflection
coordinates, matching the equirectangular images produced by the native bitmap
extractor. H1 model reflections apply the authored perpendicular/parallel tint
and brightness and the correct multipurpose-map reflection channel. H2
environment/specular cubemaps apply their normal and glancing tint/brightness
parameters. The full construction sweep passes with 228 H1 and 152 H2
environment-texture nodes, including three H1 transparent shaders whose cubemap
stages correctly omit unavailable alpha outputs. Visual comparison of reflection
strength and exact transparent blend-template behavior remains.

The classic extraction branch now performs that conversion explicitly. The
blam-tags H1/H2 decoder returns a Tool-compatible 4x3 DirectX face cross; Foundry
reads its uncompressed RGBA TIFF, maps the +Y/-Y and +X/+Z/-X/-Z cells, and writes
a 4x2 equirectangular TIFF for Blender's environment texture. Its cache key and
returned path point to the converted image rather than the intermediate cross.
Real HCE and H2 samples converted 256x192 to 256x128 and 16x12 to 16x8 through
the public `save_to_tiff` and `bitmap_to_image` paths, including a repeated
cached lookup. The four-image H2 sample writes numbered equirectangular frames;
Blender loads the first as a valid environment image while the metadata retains
the full frame count.

Classic alpha-test intent is now preserved separately from ordinary transparency.
H1 transparent-family flags select Blender's dithered surface mode, while H2
alpha-test templates/parameters do the same and connect their authored alpha-test
map to the Principled alpha input. The complete shader construction sweep remains
clean after this change; additive, subtractive and multiply framebuffer modes
still require visual parity work.

Representative unfiltered classic animation resource decoding is now complete.
The HCE Captain graph decoded all 22 animations (1,048 composed frames), and the
H2 Brute graph decoded all 406 animations (12,965 composed frames) through the
native blam-tags pose path. This closes the earlier filtered-resource coverage;
full Blender action creation and visual pose comparison across more graphs remain.

Classic root movement is also native. Foundry consumes the detached movement
records returned with each blam-tags pose, prepends the stationary first frame,
uses the movement kind reported by the decoded payload, and accumulates local
translation and rotation onto the root or converted pedestal. Unknown movement
kinds fail explicitly instead of being interpreted through stale tag metadata.
The HCE Cyborg sample decoded 4,910 movement frames across 153 animations, while
the H2 Brute decoded 4,616 movement frames across 144 animations. The importer UI
no longer reports this already connected path as unsupported.

Halo 1 render-model skeleton construction now inverts each stored default node
rotation before composing the Blender rest pose, matching the Halo 1 tag
convention and the io_scene_halo importer. Blender 5.1 validation against the
19-node HCE cyborg model confirmed that 18 non-identity rotations take the
corrected path. Halo 2 and later node rotations retain their existing convention.

The Foundry importer now accepts Halo 1 `.model_animations` files as direct
animation imports. File grouping, the animation options dialog, and Blender's
drag-and-drop file handler route both `.model_animations` and the later
`.model_animation_graph` extension through the native animation importer. Halo 1
overlay and replacement actions also tolerate the object-space node metadata
blocks that are absent from its tag layout. A Blender 5.2 import of the HCE
cyborg graph completed all 254 actions, including `G-driver acc-front-back`.

Halo 1 skeletal animation quaternions now use the title's inverse rotation
convention during Blender action construction, matching its rest skeleton and
the io_scene_halo reference importer. Foundry also restores the authored two-node
H1 vertex skinning from each `gbxmodel` part through the native blam-tags mesh
decoder. Blender 5.2 validation of the HCE cyborg produced 16 bone groups and
2,256 weighted vertices; its animated
`stand rifle idle` bounds remained vertically oriented.

Halo 1 animation skeleton metadata now normalizes a node that names itself as
its parent to a root node. HCE stores the first animation node with parent index
zero, which previously made Foundry skip its root-only scene-forward conversion.
Blender 5.2 validation with the scene set to negative Y imported the cyborg
`alert rifle move-front` action and moved its root 1.709 units along negative Y
instead of positive X.

Halo 2 render-model imports now expose an LOD selector with `All` as the default
and individual L1 through L6 choices. Imported Halo 2 geometry is placed in a
child collection for each available LOD. Blender 5.2 validation of the H2
Master Chief render model produced six collections and 24 meshes for `All`, and
only the four L3 meshes in a single L3 collection when that LOD was selected.
The same selector is registered on the drag-and-drop operator, where it was
previously absent from biped and other object-tag dialogs.

Halo 2 render-model skinning now reads the authored four node indices and
weights from each raw vertex and resolves section-local indices through the
section node map in the native semantic decoder. A scan of all 1,120 H2EK render
models found
1,435,973 raw vertices using the new-index layout, including 115,947 vertices
with multiple influences. Blender 5.2 validation of Master Chief L5 produced
31 bone groups, 2,256 weighted vertices and 484 multi-weighted vertices.

Halo 1 model and object drag-and-drop dialogs now show a Permutation selector
instead of the later-game Variant selector. Permutation names are read from the
referenced H1 model through blam-tags, with All Permutations as the default, and
the selection filters render geometry and markers across matching regions. The
HCE grunt biped resolved `base00` and `shellback` from its referenced model.

Halo 1 and Halo 2 overlay and replacement animation imports now use Foundry's
Reach-style base-animation search before native pose decoding. The chosen idle
or locomotion frame is supplied to blam-tags as the composition base, and the
native leading frame is retained as frame 1 of the Blender action. Targeted HCE
cyborg and H2 Master Chief checks covered both overlay and replacement clips;
each imported action contained one leading frame and matched its selected base
pose within floating-point tolerance.
