# blam-tags migration

## Reach, Halo 4 and Halo 2AMP overlay groups

Animation Graph settings now include **Set Up Overlay Groups on Export** (on by
default), an Automatic/Character/First Person/Vehicle profile, optional JSON
overrides, and **Preview Overlay Group Changes**. Preview validates an edited
in-memory clone and writes its proposed changes/notices to Blender's
`Overlay Group Preview` text; it does not save tags or ownership data.

Setup runs after successful Tool imports, including single/child animations and
tag-only exports. It uses the compiled graph, so aliases and function overlays
can be reconciled even when no new pose overlays were exported. H1/H2/H3/ODST
keep their existing export behaviour.

Authored groups, assignments, masks, member flags, function overlays, screen
settings and ordering take precedence. Empty authored groups and explicit `-1`
node masks are preserved. Missing local screen animation references are repaired
only when their exact source name identifies one overlay animation; otherwise
the record is retained with a diagnostic. Definition tables are never compacted,
so unrelated block indices cannot shift. Existing inherited screen references
retain their graph/animation pair; an unresolved inherited source is reported
instead of being interpreted as an index into the local animation table.

New character groups combine matching aim/look variants, separate pain regions,
transition in/out weights, throttle/defense and applicable pill-fix screens. H4
and H2AMP also support locomotion and composite turns. Literal `any` levels stay
in their correct positions. Explicit graph aliases precede source-name fallback;
ambiguous alternatives are reported, not selected by list order. New first-person
groups use idle and separate movement/look settings. New vehicle groups bind at
mode level and include valid function overlays, including function-only groups.
Known suspension channels use their exported suspension records. Custom object
functions need explicit mappings. Existing vehicle screen inputs always win over
defaults inferred from names.

Generated records are tracked beside the graph's corresponding data path in
`<graph>.overlay_groups.generated.json`. Keep this file with the asset's source
data if subsequent exports should update generated groups. Ownership requires an
exact match to the last saved record and its group assignments: manually edited
records become authored. A missing or stale ledger conservatively preserves
existing records. Removing a generated group's sources clears its generated
binding while retaining table slots. Setup twice on unchanged input is a no-op.
The tag is validated on a clone and saved atomically before the ledger is updated.
A ledger write failure is reported and does not grant ownership of edited data.

Overrides only affect new or unchanged generated records. Screen keys and group
keys use the full five-component graph path; a group may instead name a mode,
weapon class, weapon type or set. Function keys name source animations. Example:

```json
{
  "screens": {
    "any:any:any:any:steering": {
      "yaw source": "aim yaw",
      "pitch source": "aim pitch",
      "weight source": "object function",
      "weight source object function": "driver_seat_power"
    }
  },
  "functions": {
    "vehicle:open_close": {"frame ratio object function": "door_open"}
  },
  "groups": {
    "any": {
      "screens": ["vehicle:steering"],
      "functions": ["vehicle:open_close"]
    }
  }
}
```

Each generated group is limited to ten blend screens and 32 function overlays;
the definition tables have independent limits of 1024 screens, 32 function
overlays and 1056 groups. Overflow or invalid explicit settings abort setup
before saving; authored legacy faults remain diagnostic rather than destructive
cleanup targets. Custom skeleton masks are not fabricated from bone-name guesses.

Run `python blender/tests/test_animation_overlay_groups.py`; add
`--reference-root <Main editing-kit directory>` for read-only reference checks.
The suite covers all three native layouts, aliases, partial/repeated exports,
authored settings, index stability, inherited references, capacity and write
failures. Run `test_animation_overlay_groups_blender.py` in factory-background
Blender for property registration, preview and document-lifecycle checks.
These checks verify tag construction and preservation, not in-game blending.

## Halo 4 Havok collision audit

Scenario, BSP and prefab imports recover Havok collision automatically unless
Render Geometry Only is enabled. Cinematic imports remain render-only. The
experimental checkbox has been removed from both import dialogs and presets.
Embedded GR2 sources retain their authored collision and proxies without an
additional compiled Havok overlay. Prefab source lookup accepts the native
filesystem path returned by `PrefabTag.bsp_path()`.

Binary tagfiles use the decoded object graph for both standalone compressed
meshes and static compounds, including MOPP children and every storage pool.
Malformed or unsupported tagfile shapes raise a contextual error instead of
falling back to a byte scan. Missing render mappings retain physical geometry;
an undecodable legacy payload produces a warning. Instance-local vertices,
placement transforms, winding, collision layers and material overrides are
retained. Shared definition recovery requires equivalent local geometry and
mappings across placements; differing coverage stays standalone. Conflicting
materials/layers, incomplete mappings and deleted render triangle IDs cannot
silently consume collision faces.

Mapped render collision stays editable on the original instance definition.
Residual collision of the same layer joins it as collision-only faces, since
attaching a partial proxy would replace the mapped collision during export.
Definitions are completed before making linked placements. Unmapped render
geometry is marked render-only; collision-only definitions and unmapped layers
remain explicit geometry. Source shape identities, where available, continue
through the existing shape recovery. Compiled Havok cannot recover arbitrary
original quads, deleted geometry, source names or pivots absent from the tags.

`blender/tests/test_havok_collision_blender.py` runs in factory Blender. Pass
`-- --tags-root <H4EK/tags>` for real payload and `maintenance_pump` prefab checks,
and add `--full-import --scan-tags` for the broader audit. The October 2026 audit
read 26 H4 BSPs, 76 payloads and 4,807,385 collision triangles; it also imported
both `ca_warhouse` and `ca_warhouse_planet` BSPs with all 364 lights and 56
referenced unique prefabs. The main
Warhouse payloads retain all 454,851 nondegenerate collision triangles and their
tag placement transforms. All tag access was read-only; audit BSPs were checksummed.
This verifies Blender reconstruction, not acceptance of a recompiled H4 map by
Tool. The shared H2AMP path has synthetic coverage, but no real H2AMP tag audit.

Older lighting-info layouts, including the Warhouse planet BSP, omit `Cinema
Objects Only`. Import retains the default off value when this field is absent
and validates/preserves authored values when present, matching standalone light
imports. `blender/tests/test_structure_lighting_blender.py` covers both layouts;
pass `-- --tags-root <H4EK/tags>` to verify the actual Warhouse lighting tags.

## Halo 4 source shape recovery

Halo 4 render-model and structure-BSP imports use `render geometry/shapeNames`
and each mesh's `vertex keys` to recover named source shapes. `key2` selects
the shape; the full `key1` is an opaque vertex identity within that shape.
Identical duplicate name entries are accepted. Missing blocks, mismatched
vertex counts, ambiguous names and unresolved/mixed-shape triangles retain
the existing import path for the affected geometry. Other games are unchanged.

Recovered meshes preserve materials, UVs, corner normals, skin weights and
face properties. Exact keyed vertex splits reconnect only when retained point
data agree and no faces would collapse or overlap. Source names and keys are
stored as custom properties; namespaces are retained. Separate region,
permutation, rigid-parent and PCA mesh identities remain separate objects.
PCA's original point/corner IDs survive splitting and keyed welding, including
later animation imports. These keys do not restore original quads or pivots.

BSP cluster joining now separates known shapes again after combining cluster
geometry; the existing skip-merge option retains cluster boundaries. Generated
or unmapped geometry follows the existing collision-repair path. Instance
placements retain their names, transforms, policies and shared mesh data;
multi-shape placements get one object per shape. Complete collision, physics
and cookie-cutter proxies stay attached once per placement. Additional render
pieces covered by a complete collision/physics proxy are render-only.

Run `blender/tests/test_source_shapes_blender.py` with Blender's background,
factory-startup and python-exit-code options. Append `-- --tags-root <H4EK/tags>`
to test Del Rio, its hologram selection and PCA idle clip, plus the box,
headlong and grind-windows BSPs. Tests never save source tags.

See [Halo 3 and ODST cinematic camera conversion](H3_CINEMATIC_CAMERAS.md) for camera
projection, anchor units and axes, executable evidence, and regression coverage.

See [migration status](MIGRATION_STATUS.md) for the remaining work and dependency audit.

See [Halo Reach animation resources](ANIMATION_RESOURCES_REACH.md) for the
resource section layout, codec streams, retained authoring poses, and IK data.

## Migrated workflows

These wrappers now use native blam-tags documents and never initialize ManagedBlam:

- Camera-track import/export (H3, ODST, Reach, H4, H2AMP).
- Global material names, camera FOV and first-person model references.
- Render-method definitions and option parameters/defaults.
- Material-shader parameters/defaults (H4/H2AMP).
- Model references, export path updates, variants, damage states, child objects,
  material mappings, render-region metadata and Reach sky detection.
- Lightmap-region bounds, restriction flags, ambient occlusion and bounce mode
  for H4/H2AMP, plus lightmapper quality names used by the UI.
- Object model references, variants, change colors, seat and weapon names,
  magazine/tether metadata, first-person model edits and scenery lighting references.
- Object attachment references, marker names and scale-function names. Missing
  and unsupported attachments are filtered before opening a legacy converter.
- Cinematic-lighting creation and dynamic-light references, flags and placement
  metadata. Referenced Reach light conversion uses the native light wrapper;
  H4/H2AMP authored-probe conversion remains unimplemented.
- Object-function node creation for supported native editor shapes; unsupported
  shapes raise before any nodes are created.
- Cinematic scenery conversion when the source block layouts match the target
  schema. Incompatible layouts raise explicitly.
- Top-level cinematic import/export and its scenario bookkeeping, including
  transition tags, scripts, scene references, zone sets and anchors.
- Frame-event-list import/export, shared references and partial animation updates.
- Animation-graph names, skeleton ordering, parent indices, node usages, parent
  graph and imported-event references. Template setup and animation command lookup
  use this metadata path without opening ManagedBlam. Graph creation, cinematic
  skeleton copying, parent-graph assignment, node-usage and IK-chain export, and
  compression, world-relative and vehicle-suspension settings are native too.
  Animation weights, loop frames, playback flags, blend overrides and PCA group
  metadata also write natively. Pose-overlay automation reads its blend screens
  through this wrapper. Mode/state graph traversal and Blender animation-rename
  generation are native across all five H3+ profiles. Animation import settings
  and node-usage indices are detached native records. The Python binding exposes
  Rust-decoded, fully composed animation poses, including graph-selected
  overlay/replacement bases, object-space corrections and movement. The Blender
  importer consumes those owned transforms for H3, ODST, Reach, H4 and H2AMP.
- Particle-emitter custom-points tag creation during particle-model export.
- Cinematic event sound-effect names, playback availability and indexed sound-class
  labels.
- H4/H2AMP prefab structure-BSP reference resolution during import.
- H4/H2AMP prefab records and H3/ODST/Reach collision-proxy surface mappings in
  structure BSPs.
- Structure-BSP collision materials, compression bounds, H4/H2AMP emissive
  materials, render-material/lightmap properties and structure-lighting references
  used during geometry import.
- Structure-BSP portals, markers, structure-meta references and legacy environment
  object placements used during import.
- Reach/H4/H2AMP structure-BSP cookie cutters and older lighting-info material
  emissives.
- Multiplayer weapon-source discovery for biped import.
- Terrain-shader global-material lookup through inherited shader references.
- Material/shader albedo, alpha-mode and physics-material metadata used by
  decorator setup, Granny texture extraction and BSP collision import.
- Empty shader-tag creation for non-node material export.
- Cinematic scene creation, scene-level export metadata/scripts, shot settings,
  camera-frame arrays, final scene object/attachment records and camera-authored
  screen-effect/user-input-constraint records where the tag layout supports them.
- Scenario metadata and lightweight editing for type detection, BSP/design/sky
  discovery, zone sets, lightmap settings, sky assignment, cutscene titles,
  scenario copies, default player profiles, debug zone sets, airprobe export,
  cubemap generation, decorator placement export, template palette copying and
  scenario-global tag creation/copying. Scenario import metadata and child-scenario
  discovery also use this path. Placed scenario objects, palettes, names, folders,
  transforms, variants, BSP filters and parent links are decoded natively;
  scenario decals and decorator placement clouds are decoded natively as well.

The Blender-facing classes retain their existing import locations. Their
implementations live in this package. Reference results are detached Python
objects; the few callers still passing them into legacy tag wrappers convert
references at that boundary.

The add-on no longer requires or initializes ManagedBlam for tag access. Startup,
project switching, editing-kit validation and packaging paths do not check for
`ManagedBlam.dll`. The former pure-Python conversion modules have moved into this
package and the historical `managed_blam` package has been removed. The Foundation
plugin installer still uses Python.NET independently of tag access.

## Build and generated assets

Use a Python environment with maturin installed and the Rust/MSVC toolchain:

```powershell
python blender/build_blam_tags.py G:\Halo\Modding\OtherProjects\blam-tags
```

The build uses a temporary source copy, stages the Windows abi3 wheel, registers
it in the extension manifest, and copies schemas needed by migrated workflows.
Every generated Halo 1 and Halo 2 group schema is staged because classic loose
tags do not embed their own layout; later games retain the curated workflow set.
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

BC7 bitmap extraction requires blam-tags 0.1.10 or later. The native Halo
bitmap path uses the same `bcdec_rs` BC7 decoder as Baboon's Unreal texture
viewer, including alpha and partial 4x4 blocks. TIFF extraction retains the
existing mip, array, cubemap and Foundry color-conversion paths. Rebuild the
wheel after updating the shared blam-tags checkout and restart Blender after
installing it.

The real-bitmap regression can be run with Blender's Python using
`blender/tests/test_bitmap_bc7.py`. Set `FOUNDRY_BC7_BITMAP` to a BC7 Halo CE
bitmap and, when testing a staged wheel, `FOUNDRY_NATIVE_ROOT` to its extracted
package directory. It checks native TIFF output and Foundry's material bitmap
save method without modifying the source tag.

## Halo 3 / ODST detail mip previews

Shader import adds distance-based preview groups to static detail colour and
detail bump textures using the lower mip levels stored in their bitmap tags.
This retains authored fading and neutral colours that would be lost by simply
downsampling the extracted full-resolution TIFF. Supported inputs are single
2D detail bitmaps with PC pixel data in DXT1, DXT3, DXT5, DXN, A8R8G8B8 or
X8R8G8B8 format. Other layouts keep their existing preview.

After updating Foundry, use **Convert Shader to Blender Material Nodes** to
rebuild an existing material. Each detail texture gains a labelled fade group:

- **Mip 1 Distance** defaults to one metre, converted for Foundry's scene scale.
  Mip 0 is retained up to half that distance; mip 2 is reached at twice the
  distance, mip 3 at four times, and subsequent levels follow the same pattern.
  Adjacent levels blend continuously in logarithmic distance.
- **Fade Amount** controls the preview effect; zero restores the original image.

The original image nodes, tag references and UV transforms remain connected for
export. Lower mip images are packed inside the blend, excluded from bitmap
export (including Shader Farm's all-images option) and skipped by bulk image
reload. Colour mips use the bitmap's transfer curve; normal components and alpha
remain linear. Uniform mip levels use constants to reduce texture sampling.

This is a camera-distance approximation for Eevee and Cycles, rather than Halo's
screen-footprint LOD selection: it does not account for UV density, surface
angle or render resolution. The distance and amount controls affect Blender
only. Rebuild the material after changing the source bitmap or its mip chain.

`blender/tests/test_detail_mip_fade_blender.py` checks mip decoding, colour/alpha,
rendered distance blending, packed-image persistence and export references.
Set `FOUNDRY_H3_TAGS_ROOT` to also inspect and render the Voi small-door shader
without modifying its source tags.

## First-person weapon animations (Halo 1 through ODST)

Create an Animation asset with its animation type set to First Person. New
animations and the name editor use the first-person naming form for the selected
project: `first-person reload-full` in H1 and `first_person reload_full` in
H2/H3/ODST. H1 variants use `%N`; later games use `varN`. Dual-wield naming is
available for H2 and later. Custom names remain literal, so use the target
weapon's existing graph as the reference for its state names.

Use base animations for weapon actions and overlays for movement/aim poses.
The legacy exporter writes JMM/JMA/JMT/JMZ base sources, JMO overlays and JMR
replacements, then applies Blender frame events to Tool's compiled graph.

For H1, add a single Primary Keyframe or Secondary Keyframe event at the action
frame (for example, the melee impact or reload completion). These write to
`key frame index` and `second key frame index`, respectively, as zero-based
30 Hz offsets from the animation's start. Left/right foot events use H1's
one-based foot slots. H1 has one slot per event type and one sound per animation;
keyframe/foot ranges and duplicate slots are rejected. H2/H3/ODST use frame-event
blocks and support event ranges. Sound data can be attached to keyframes in all
four games. Clearing authored events clears the exported animation's slots;
animations outside a partial export retain their events.

Run `tests/test_first_person_animation_blender.py` with Blender's
`--background --factory-startup --python-exit-code 1 --python` options. It checks
names, keyframes, sounds, ranges, partial updates and native tag save/reopen for
all four games. Optionally append `-- BLEND TAG` with an H1 asset's absolute blend
and model-animations paths to check its actual events against a temporary tag
copy. The source blend and tag remain unchanged.

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
parenting with a stubbed light converter. Object custom functions and cinematic
scenery copying now use native operations exclusively; unsupported data raises
an error. Attachment import opens the referenced native light wrapper, though
projected textures still depend on the unported bitmap converter.

Read-only sampling also exercised existing tag files from all five H3+ kits:
global/material metadata, 15 model tags with their render-model references,
and 25 object tags (scenery, weapons, bipeds, vehicles and machines).
A Reach Cortana definition references a missing option tag; this is reported
as a missing dependency instead of silently creating an empty tag. Editing-kit
acceptance of newly written tags and complete import/export parity are still
unverified.

## Remaining binding work

Classic CE/H2 loose tags use `TagFile.read_classic(path, schema_path)`, which
preserves their engine, header and container when saving. Foundry selects this
entry point for H1/H2 documents and identifies their game from the classic header.
`TagFile.new(schema)` still creates an MCC container, so Foundry deliberately
rejects creation of new classic tags until blam-tags exposes an explicit classic
creation API. Broad H1/H2 Blender workflow acceptance is also still required.

Animation pose decoding and the shader function operations used by Foundry are
exposed in the local wheel. The function editor can change master/color graph
types, colors and scalar clamp ranges and serialize the result. Render-model and
structure-BSP mesh decoding are also exposed; bitmap extraction uses the
native/Python path. Remaining work in these areas is workflow and visual
acceptance rather than a ManagedBlam dependency.

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
and Reach/H4/H2AMP cheap lights. Unsupported function shapes raise explicitly;
gel bitmap conversion uses the native bitmap wrapper and Foundry's Python image
decoder. H3/ODST light tags map maximum distance to cutoff and approximate
distance diffusion and angular smoothness with Blender fade controls. Static H4/H2AMP point, spot and directional light
tags now convert, including physical/artistic energy handling and shadow settings.
Animated intensity is supported for artistic point/spot lights. Animated radius
and cones, area lights and linked/projected physical or directional lights remain
unsupported. Unconnected identity curves evaluate at their constant input and
older Midnight layouts preserve defaults for unavailable shadow settings. The
read-only sample now converts 59 of 60 light tags. Unconnected deterministic curves
resolve through native evaluation; periodic or modifier-driven attenuation still
requires animation support. The remaining sampled tag is a physical light.
Light and structure seam/metadata schemas are staged by the build script as
ignored generated assets, not committed sources.

Structure seam import reads native final points and triangle indices, validates
geometry before allocation and preserves Blender normal/orientation handling.
Structure metadata imports effects, airprobes, light cones and object placements
without ManagedBlam. The wrappers retain their existing import paths.

Portal imports from H1, H2, H3, ODST, Reach, H4 and H2A share guarded fragment
merging, seam removal, bounded plane correction and rectangular outline recovery.
Merging preserves winding, the ordered cluster pair and portal flags. New outline
area requires a complete solid-volume proof and must preserve other portal
junctions. Missing collision data keeps the existing outline. Packed collision
nodes and supernode roots are decoded per tag layout; later games use strict
solid proofs rather than assuming collision leaves reproduce every visibility
cluster. Reach retains its cluster-volume recovery before shared mesh cleanup.
Fragile single-face outlines can receive an automatic triangulation modifier;
their editable perimeter stays unchanged. Authored exact flags are not invented.
Fragments with different known source plane indices remain separate even when
their normals nearly agree; combining these cuts can erase a shallow partition.
Portals with a vertex at an identical native structure vertex keep their complete
source outline. The comparison uses tag coordinates before Blender scaling;
nearby points do not trigger preservation. These contacts bypass expansion,
cluster-volume recovery and later outline cleanup across all supported games.
Preserved portals use the native structure's single coordinate transform so
float32 rounding does not separate an exact contact during Blender conversion.

Reach structure imports repair the native collision shell before merging actual
mapped render/collision surfaces into one editable structure object per BSP.
Tag section and triangle identities survive cluster joining and separation.
Mapped render coverage subdivides the repaired native polygons; shared faces
use native positions, interpolated render corners and native collision flags.
Only uncovered native coverage remains collision-only. Coincident unmapped
render detail cannot claim a collision surface. Exact welding protects those
independent visual overlays while reconnecting shared physical boundaries.
Export derives both compiler streams from the shared editable triangles. Native
boundary connectivity is recorded without another set of coordinates. On a
private compiler copy, unchanged face groups recover their simpler native
polygons using current mesh vertices. Geometry hashes and matching face flags
prevent recovery from replacing edits. The physical copy restores native face
and material traversal order and flat corners without render UV/color cuts;
Tool's tolerant plane fitting otherwise turns very small cuts into open edges.
Temporary compiler copies are removed and the merged authoring scene restored.
Render boundary recipes refer to the live shared corners and retain small
precision offsets from the original compiled renderer. Unchanged triangle
families recover their source traversal and corners only when materials, face
flags and interpolated UV/normal/color data agree. Geometry edits invalidate
the recipe; nonuniform corner edits retain their subdivisions. These offsets
guide Tool's reconstruction without restoring another authoring geometry body.
Independent imported vertex fans preserve their encoded custom normals through
the native join and compiler partition. Private render copies normalize only
near-identical corner normals within 0.001 vector distance, below 0.06 degrees;
larger hard splits and the authoring normals remain unchanged.
Render structure remains to help reproduce Tool's solid planes. Every child of
a subdivided source triangle retains its source seam-detail classification.
Collision
faces retain their material and surface flags,
and compiler subdivisions dissolve only when the original plane, material,
winding and all face properties agree. Boundary and junction vertices remain.
In reconstructed Reach seam shells, sky subdivisions retain their native
topology when joining them would introduce
a concave ear within float32 rounding bounds. Ordinary sky partitions still
dissolve; distant sky-box corners can otherwise create almost collinear ears
and introduce overlapping-surface warnings. Unseamed BSPs and other imports
retain the established sky dissolution; changing those partitions regressed
visibility portals during the unseamed Reach regression.
Known-plane collision outlines cancel zero-width compiler spurs and replace only
triangulations with nearly collinear ears. The replacement maximizes the smallest
triangle altitude inside the original outline, retains source vertex positions
and face masks, and reconnects exposed junctions within float32 rounding bounds.
Nearly collapsed seam triangles can also be joined to a contiguous surface
within the same rounding bound, provided material and authored flags agree.
Those repaired seam patches and the solid surfaces sharing their boundary
vertices receive stable triangulation together. Changing only the seam side
lets Tool move the two boundaries apart during its plane reconstruction.
This recovery retains boundary positions and avoids retriangulating unrelated
surfaces or replacing the shell with the separately compiled seam tag.
It is shared by BSP imports with native plane provenance; unknown-plane render
meshes and meshes with custom normals remain excluded. Tool verification of
this seam recovery currently covers Reach firefight BSPs.
Seam objects discard the inherited collision-only override and retain their
normal seam mode.
Native collision records retain plane provenance across H1, H2, H3, ODST, Reach,
H4 and H2AMP; the complete native structure reconstruction currently applies to Reach.
The complete Reach shell skips the opposite-surface sidedness inference used
for render/collision merging. Native instance proxies stitch only open
boundaries; closed thin parts are excluded from proximity-based edge splitting.
Native cookie cutters retain opposite face pairs as closed loops instead of
collapsing them into two-sided face flags, which Tool does not use to close
cookie-cutter volumes. Distant legacy render-only instance meshes without collision,
physics or cookie-cutter proxies use a centred private mesh. Placement, UVs,
normals and authored face properties are retained; smaller local coordinates
avoid Tool's plane-through-point assertion on large sky geometry.
Corinth instance origins stay with the later Havok proxy reconstruction.

Authored PCA animation also reads native blocks and linked render-model metadata,
then creates Blender shape keys and actions through the existing workflow. This
does not add runtime resource-only animation decoding. PCA schemas remain generated
and ignored alongside the other build assets.
Raw PCA position bases are deltas in the render model's normalized bounds; they
use the render mesh's scene-unit conversion without a bounds translation. Shared
groups preserve each clip's signed coefficients and expand their shape-key ranges
across clips. Import creates actions without activating them: the animation manager
selects the facial action, so clips without PCA do not inherit the last imported face.
Corinth compiled render meshes retain their source render-model path, mesh index,
vertex count, and one-based source IDs on points and corners. Corner IDs preserve
both sides of a welded seam. PCA import uses these identities instead of current
vertex counts and separates a weld when a later group needs different motion or
wrinkle values. Existing keys, skin weights, UVs and face data survive the split.
Make Meshes Editable preserves differing PCA point data and carries the source IDs
through cleanup; the mapping also survives saving and reopening the blend file.
Missing/invalid mappings on mapped meshes are rejected. Older unmodified meshes
retain the unique-vertex-count fallback; already-welded older imports need a fresh
model import. This correspondence does not reconstruct arbitrary remeshing or
map independently authored GR2/JMS topology onto compiled tag vertices.

Collision-model import reads native geometry and pathfinding spheres, validates
surface loops and bone bindings, then reuses the existing Blender conversion.
Separate structure-BSP and Havok collision paths still need migration.

Physics constraints read through blam-tags and use the existing Blender marker
conversion. The obsolete legacy physics wrapper has been removed. Standalone spheres
and boxes, nonzero-length capsules, convex polyhedra and flat lists of these shapes
now use native records. Nested lists and MOPP wrappers around supported shapes
also use native geometry, with circular-reference and expansion-limit checks;
other primitives, unbound bodies and unsupported serialized Havok payloads
raise explicit unsupported errors. Constraint-only tags avoid ManagedBlam entirely. Physics
schemas are ignored build assets.
H4/H2AMP Havok bodies with supported authored geometry read mass, center-of-mass,
inertia and damping properties natively through the existing Blender property mapping.
Older H4 layouts without serialized-shape fields also read natively, including
MOPPs that retain a list index instead of a child-shape reference.
Serialized Havok bodies now use native payload extraction and the existing Python
geometry decoder. All shapes decode before Blender allocation; an unsupported
payload raises an error without ManagedBlam fallback. Required bone bindings are checked.
Read-only sampling converted temporary copies of 36 H3 weapons, bipeds and
vehicles and verified their initial color permutations after reopening. All 36
used the native path; no original editing-kit tags were modified.
An additional scan of 933 H3 object tags found three populated color-function
blocks. Copies of all three convert natively, including the non-default colors
and scale inputs on the reactor sky tag. These tests do not establish editing-kit
acceptance of the resulting files.
Blender-facing integrations belong in this package beside their native documents.
Model and object keep their document layer separate from `model_blender.py` and
`object_blender.py`, so scripts can inspect and edit tag data without importing
Blender. Collision, physics, structure, particle, PCA and light import wrappers
follow the same native blam-tags path even where Blender conversion helpers have
not yet been moved out of the legacy package.
`backend.py` annotates its public boundary with the wheel's exported `TagFile`,
`TagStruct`, `TagField`, `TagBlock`, and math types. The wheel includes `py.typed`
stubs, so these definitions are available to VS Code while the runtime binding is
still imported lazily when a document is opened.

For development, the repository's `pyrightconfig.json` points VS Code/Pylance to
`typings/blam_tags/__init__.pyi`. This checked-in copy includes the wheel's native
method documentation, including `TagField.set_flag`, so hover descriptions and
Go to Definition work even when the editor's Python environment does not have
blam-tags installed. Open Foundry's repository root as the VS Code workspace.
`build_blam_tags.py` refreshes these stubs when staging a wheel. To refresh them
from the wheel already listed in the extension manifest, run
`python blender/update_blam_tags_typings.py`. After changing the stubs or config,
use **Python: Restart Language Server** if Pylance has not picked them up.

- Reach/H4/H2AMP animation graphs export Blender-authored frame events through the
  native graph and frame-event-list wrappers, including the graph reference update.
- Inline graph events import natively across H3 through H2AMP and merge with
  external event-list data before creating Blender frame events.
- Animation-graph IK chains import through typed native node/name records and keep
  the existing Blender proxy/pole helper-bone behavior.
- Cache validation uses native scenario methods for required resources, child
  scenarios, scenery palettes, player starts and generated spawn/camera placements.
- Structure BSP collision geometry, surface-to-triangle mappings, instance
  placements and policies, renderer-ready meshes, and serialized H4/H2AMP Havok
  collision payloads are read through typed blam-tags handles.
