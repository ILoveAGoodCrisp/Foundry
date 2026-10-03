# GR2 import

`reader.py` uses the selected source project's `granny2_x64.dll` to read GR2
files, convert their coordinate system, unpack vertices, and sample compressed
animation curves. It detaches all data before freeing the native file. The
bindings follow the Granny 2.9 SDK header and the existing exporter structures.

`importer.py` reconstructs triangulated Blender meshes, split normals, named UV
and color layers, materials and shader paths, bones, skin weights, rigid bone
parents, markers, and sampled skeletal actions. Exported object and face
properties are mapped back to Foundry properties. Unknown metadata remains in
custom properties; numeric face annotations remain as exportable attributes.
The file's BungieExportInfo tables determine native enum and region values.
Older Max exports with nested Bungie property containers, enum tables, and
material attributes are supported too. Meshes with topology material groups
but no material bindings import without material assignments; their original
groups are retained in custom properties. Generic Granny skeletons without Halo
object metadata retain their bones, hierarchy, and skin bindings.
Empty or whitespace-only enum attributes use the relevant import default.
Halo export headers keep untyped static mesh transforms from becoming armatures;
empty string properties such as instance proxy paths remain empty.
Mesh records without vertex data or triangle topology (such as Max line nodes)
import as non-exporting empties. Their placements, Foundry grouping, source
properties and binding names are retained; the importer reports each helper.
Meshes with geometry still undergo vertex and triangle-index validation.
Name tables honor explicit IDs, including sparse tables, and supplied sidecar
names fill missing entries. When the source omits a region or global-material
name, the importer preserves the face group using `gr2_region_<id>` or
`gr2_global_material_<id>` and reports the missing name once. Original IDs remain
in `gr2_original_bungie_*` face attributes for recovery; those attributes do not
override the reconstructed names on export. Default tessellation and compression
values create no Foundry override, and empty Max attribute containers do not
overwrite scalar defaults.
Raw keyframe arrays are read by sample index; compressed spline curves use the
runtime evaluator. Identity rotation and scale curves keep their identity values.
The skeleton's armature wrapper root becomes the Blender armature object rather
than an extra pose bone. Its placement and animated motion are preserved on that
object, with child bones, markers, and skin influences retained.

GR2 files can be selected through Foundry's model/animation importer or dropped
into Blender. Embedded GR2 sources are used for Reach, Halo 4, and Halo 2A tags
when **Use Import Info** is enabled. Tag routing preserves component selection,
region/permutation filters, tag skeletons, graph settings, and events. Missing,
corrupt, or unsupported sources fall back to compiled tag data; partial source
objects are removed first. Cinematic imports retain the compiled-data path.

Foundry also accepts `sidecar.xml` and `*.sidecar.xml` through the import dialog
and file drop handler. The sidecar importer resolves data-relative, absolute, and
asset-relative GR2 references, including paths in copied asset folders. It loads
skeletons before geometry and animations, shares rigs between components, and
organizes meshes by content, BSP, and permutation. Duplicate references within
the same content are imported once. Missing or failed files are reported and
other components continue importing.

Sidecar animation names, movement, compression, overlays, replacements,
renames, and copies are restored. Region activity and global-material tables
are restored too. With **Setup as Asset** enabled, the scene receives the asset
type, sidecar path, main armature, and declared output tag selections. The source
XML and network metadata remain on the asset collection for properties which
cannot yet be reconstructed. Sidecar imports are independent of **Use Import
Info**, which governs source payloads embedded in tags.

This is an initial reconstruction of exported data. It does not recover original
modifiers, quads, authoring control rigs, metadata-only physics
primitives, source lights, or morph/PCA animation. Source vertices stay split at
export seams. Tag lighting and physics can still use the existing tag importer.
Graph conversion, PCA, and skeleton-rescaling options retain compiled motion.
Sidecar composites, material clones, full cinematic shot assembly, and referenced
child sidecars are retained as metadata rather than reconstructed. Animation
GR2s without skeleton data require a matching imported or reused armature.

Run the selection tests from the repository root:

```text
python tests/test_gr2_import_info.py
python tests/test_sidecar_import.py
```

Run scene reconstruction and rollback checks in Blender:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/test_gr2_import_blender.py
```

Append `-- <granny2_x64.dll> <sample.gr2> [...]` to also check native source files.
The Blender checks include sidecar assembly, missing/corrupt file handling,
rig sharing, and animation settings. Appending the local Foundry scenario
`foundry.sidecar.xml` also checks its native structure source and BSP assignments.
The original Reach `skiff.sidecar.xml` checks its three component meshes, shared skeleton,
component types, and idle animation, including its render mesh with no materials.
The original Reach `warthog.sidecar.xml` checks all nine animations and the
27-bone skeleton without its wrapper root. Synthetic checks cover raw scale
keyframes, armature root motion, marker parenting, and mixed wrapper/bone weights.
The original Reach `scarab_test_render.gr2` checks all 220 meshes and 15,519
triangles, its eleven unnamed region IDs, and preservation of the original face IDs.
The original Reach `40_boat.gr2` checks all 159 meshes and 49,998 triangles,
including empty object-type metadata and untyped static mesh transforms.
The original Reach Powerhouse `room01.gr2` checks its 165 drawable meshes and
86,771 triangles, plus its three geometryless line nodes retained as empties.
