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
Collision geometry uses Foundry's Collision material and face properties, even
for a single source material. Physics geometry uses Foundry's Physics material.
Matching scenario collision children are linked as instance collision proxies.

`BM_FLAGS`, lightmap resolution/transparency/tint, emissive power/color/quality,
shader gel, focus and attenuation records become Foundry properties. Frustum,
photon-fidelity and unknown lighting records are retained in the collection's
source material metadata where Foundry has no equivalent. Instance metadata
preserves pivots, unique IDs and inheritance flags. Third UV components, xref
paths and source light records are also retained.

For a future exporter, populate `ASS` from evaluated virtual geometry. Generate
source material variants from Foundry face properties, and preserve the separate
geometry and instance tables. Reverse unit and axis conversion exactly once,
accounting for conversion already performed by virtual geometry. Do not interpret
ASS parent indices as unique IDs or apply ancestor pivots to children.

Tests: `test_ass.py` runs in ordinary Python; `test_ass_blender.py` runs in
background Blender with actual Foundry property classes and shared helpers.
