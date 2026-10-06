# ASS interchange

`ass_format.py` reads versions 1–7 without Blender dependencies. The public API
is exposed by `ass.py`. Geometry definitions, instances, material variants,
lighting records, local transforms, pivots, skin palettes and header strings are
kept separate. Positions and distances remain in source units; rotations retain
XYZW order. Version 1 has vector scales; later versions have uniform scales.

`ass_importer.py` shares mesh construction, Foundry face-property conversion,
primitive creation, armature reuse and failure cleanup with the JMS adapter.
Neither import path invokes the Halo toolset or `transform_scene`.

Instance world transforms accumulate ancestor local transforms. Pivots affect
the instance geometry, not its children. Non-exporting frame helpers preserve
this distinction in Blender. Unit conversion happens once when constructing
mesh coordinates, distances and transform translations. Axis rotation is applied
at the world-transform boundary. Repeated instances share geometry only when
their mesh role and skin palette agree. Vertex weights use the instance's local
palette, never its unique ID or a reordered node list.

For models, each region/permutation has its own object. BSP imports use one BSP
named after the ASS file (without its extension), with the default layer; material
variants do not create BSPs, layers or geometry splits. Both paths split
incompatible mesh types and portal policies. For models, ASS's optional global-material prefix
is stored as a Collision Material property. ASS BSPs never receive these
properties: ASS targets pre-H4 games, where BSP collision materials come from
shaders. Shader materials are deduplicated independently.
Model collision geometry uses Foundry's Collision material and face properties,
even for a single source material. BSP collision geometry keeps its shader slots
and collision-only face properties. Physics geometry uses Foundry's Physics material.
Matching scenario collision children are linked as instance collision proxies.
Every collision child is retained and transformed into its render instance's
local coordinates before combining them. Two-sided collision flags and combined
collision/sphere-only flags survive that conversion. Authoring objects outside
the source export frame remain excluded, and unassigned triangles retain -1.
Shader collection prefixes and the compiled BSP's shader references resolve
full shader paths before basename searches, including shared shader basenames.

`BM_FLAGS`, lightmap resolution/transparency/tint, emissive power/color/quality,
shader gel, focus, attenuation and frustum records become editable Foundry
properties and export back to ASS 7. Attenuation preserves its enabled state and
both authored distances even when disabled. Frustum blend and angular limits
are distinct from Reach's bounce ratio. Legacy colour values stay in RGB 0–1;
focus is converted once, and frustum angles use degrees in ASS and radians in
Blender. Explicit zero-power records and shader gel without a power record
survive. Photon fidelity is editable; unknown lighting records are retained in
the collection's source material metadata where Foundry has no equivalent. Instance metadata
preserves pivots, unique IDs and inheritance flags. Third UV components, xref
paths and source light records are also retained.

An XREF mesh with embedded vertices and triangles is imported as geometry,
retaining its reference path and name on export. Only empty XREF meshes become
reference markers. Dropping embedded XREF geometry can remove structural walls.
Authored normals, color seams and the third UV component remain per corner
through the final import cleanup. Material symbols are read from the suffix;
interior punctuation, such as `Material #3451`, remains part of the shader name.

Photon fidelity is an editable face/material property. Different tint,
transparency and numeric variants remain separate during cleanup even when their
display names agree. Absent basic emissive records remain absent on unlit faces.

Unchanged local points and uniformly scaled placements retain their original
ASS coordinates and transforms. Export compares the evaluated points and object
matrix with the imported values before using this data; edits use the current
Blender geometry and transforms. This avoids unit/axis conversion drift on large
BSPs. Legacy virtual geometry uses exact vertex keys, including deformation,
instead of Granny's tolerance weld, so thin valid faces survive export.
Source positions also participate in both weld keys when unit conversion rounds
two distinct source floats to one Blender coordinate.
Signed uniform scale is retained rather than baking mirrored instances into
world coordinates. Unmoved BSP objects keep their source parent transforms,
pivots, names and instance order. Collision proxies inherit the owning pivot;
ASS does not implicitly apply a parent's geometry pivot to its children.
Imported face order, corner order and vertex order are retained for Tool's
positional welding and plane construction. ASS output uses fixed decimal
precision to avoid truncating large translations.

Unchanged native BSP scenes retain their complete source compiler records,
including geometry helpers, unused vertices, degenerate authoring faces and the
original ASS version (1–7). A canonical fingerprint is captured after import
finishes. Editable vertex welding does not change it. Geometry, normals, UVs,
colours, materials, face properties, transforms, hierarchy, collection filters,
modifiers, shape keys and added/removed objects invalidate reuse. Edited scenes
use the evaluated mesh exporter. The source scene and fingerprints are saved in
the import collection so the guard also works after saving and reopening Blender.
This avoids changes to Tool's BSP construction on a no-edit round trip; it does
not remove warnings Tool also reports when importing the untouched source.

Equivalent authored lighting records retain their numeric text, including zero
overrides and values at packed-colour rounding boundaries. Numeric name tokens
are omitted when ASS already supplies the corresponding lighting record.
Unedited collision proxies can retain their separate source children, local
coordinates and pivots. Edited proxies export their evaluated combined mesh.

The legacy exporter populates `ASS` from evaluated virtual geometry, with
material variants from Foundry face properties and separate geometry and
instance tables. Reverse unit and axis conversion happens exactly once,
accounting for conversion already performed by virtual geometry.

Tests: `test_ass.py` runs in ordinary Python; `test_ass_blender.py` runs in
background Blender with actual Foundry property classes and shared helpers.
`blender/test_legacy_import_info_blender.py` exercises embedded XREFs, material
and instance policies, collision proxies, authoring-frame exclusion, shader
identity, unassigned faces, source-coordinate preservation, edited geometry,
normals, color seams, 3D UVs and emissive lighting through the complete legacy
export preparation path.
