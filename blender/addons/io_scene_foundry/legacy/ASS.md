# ASS interchange

`ass_format.py` reads versions 1–7 without Blender dependencies. The public API
is exposed by `ass.py`. Geometry definitions, instances, material variants,
lighting records, local transforms, pivots, skin palettes and header strings are
kept separate. Positions and distances remain in source units; rotations retain
XYZW order. Version 1 has vector scales; later versions have uniform scales.

`ass_importer.py` shares mesh construction, Foundry face-property conversion,
primitive creation, armature reuse and failure cleanup with the JMS adapter.
Neither import path invokes the Halo toolset or `transform_scene`.

`bpy.ops.nwo.convert_scene()` applies the same authoring rules to existing
Toolset objects: frame display meshes become hierarchy helpers, H3/ODST
instance lighting comes from each instance's name, water is explicitly SURFACE
or PHYSICS, and collision children are combined in the owning render instance's
local coordinates. Collision shaders and per-face collision modes survive that
combination. Exact embedded game-object references use the same resolver as
ASS import; structural XREF payloads remain geometry. Conversion and file import
add Precise only for an explicit source flag or material symbol. Neither path
creates a Not Precise override for unflagged faces; existing authored Foundry
properties are retained. Both paths use the shared legacy exporter, including
its triangle-order, seam-name and boundary-material handling.

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

Halo 3 and ODST seam surfaces use `+seam:<bsp_name>` materials, for example
`+seam:example_seams_1`. Assign the material to the seam faces to identify their
BSP in Tool. Named materials keep their BSP identity through ASS/JMS import,
toolset scene conversion and export, including multiple seam names on one mesh.
Seams authored with Foundry's Seam mesh type or Auto Seam export the same naming
format from their BSP assignment; the generated backface uses the back-facing BSP.
Material-authored named seams are exported as supplied without an automatic
backface; author the other side separately when needed.

Halo 2 structure files include a scene wrapper and a named child export frame.
Geometry, markers and collision-proxy parent indices are placed beneath that
frame. Tool can reject geometry attached directly to the wrapper with the
misleading message "unable to parse any materials". Max material symbols may be
separated by spaces; the importer retains the complete trailing symbol group,
including render-only flags before a later symbol.

Halo 3/ODST structure exports run `tool structure-seams <level_directory>` before
compiling BSPs, only when seam faces exist and the native `.structure_seams` tag
is missing or its geometry differs. The check uses the complete level's ASS
sources, including for Tags Only and selected-BSP exports. It ignores winding
and coplanar triangulation diagonals, but retains seam points and boundaries.
No scene properties or separate cache files are stored. If Tool has rebuilt a
surface so that equivalence cannot be established, Foundry regenerates seams.
When shared seams change, all level BSPs compile once to pick up their new seam
indices. Otherwise only the requested BSPs compile. Design-only exports do not
regenerate seams. Removing all seam faces also clears the scenario's local seam
reference, even if an older generated seams tag remains on disk.

`BM_FLAGS`, lightmap resolution/transparency/tint, emissive power/color/quality,
shader gel, focus, attenuation and frustum records become editable Foundry
properties and export back to ASS 7. Attenuation preserves its enabled state and
both authored distances even when disabled. Frustum blend and angular limits
are distinct from Reach's bounce ratio. Legacy colour values stay in RGB 0–1;
focus is converted once, and frustum angles use degrees in ASS and radians in
Blender. Explicit zero-power records and shader gel without a power record
survive. Photon fidelity is editable. Records without an editable Blender or
Foundry representation are not saved as hidden source metadata.

An embedded XREF whose source asset directory resolves to an existing scenery or
device-machine tag becomes an editable game-object reference. Its preview mesh
does not become static BSP geometry. Structural XREFs and unresolved embedded
XREFs retain their vertices and triangles; dropping that payload can remove
structural walls. Empty XREF meshes also become reference markers.
Shared Max files can resolve a named XREF through the child asset directory
beside the source file (for example, `cinematic_objects.max` contains
`cinematic_anchor`). Primitive device references remain references, not physics
shapes. Halo 2 reference placement uses the accumulated node transform without
the embedded preview's object-offset pivot, matching Tool's environment objects.
Authored normals, color seams and the third UV component remain per corner
through the final import cleanup. Material symbols are read from the suffix;
interior punctuation, such as `Material #3451`, remains part of the shader name.

Photon fidelity is an editable face/material property. Different tint,
transparency and numeric variants remain separate during cleanup even when their
display names agree. Absent basic emissive records remain absent on unlit faces.

ASS import does not persist source transforms, instance records, identifiers,
ordering, pivots, policy snapshots, material tables or reference payloads in
custom properties. Export never reads those properties, including in older
saved scenes. Current evaluated geometry, Blender transforms, names and visible
Foundry settings are the authoring state. Parent transforms and pivots are
represented by Blender's actual hierarchy and geometry during import.

Embedded BSP sources are culled to the authored frame before helper frames are
removed. Frame selection recognizes the `b_`, `b `, `bip_` and `bip ` names used
by Max, as well as `frame` names. Siblings attached to the scene wrapper remain
outside the asset. Lighting-name tokens such as `LP:6` are case-insensitive and
do not hide preceding material symbols or become part of shader lookup names.

Instances referencing the same geometry and skin palette, with compatible mesh
and collision-proxy settings, share Blender mesh data. Frame cleanup ignores
floating-point transform noise, including inverse translation cancellation far
from the origin. During frame cleanup, mesh data is only separated when an
actual shear correction needs to be baked into the geometry.

Export retains representable signed uniform scale and bakes nonuniform scale
or shear into the evaluated vertices. Collision proxy coordinates are local to
their current owning instance. Instance IDs and geometry tables are generated
from the export batch. Game-object references use the current editable tag
path. ASS output uses fixed decimal precision to avoid truncating large
translations.

The legacy exporter populates `ASS` from evaluated virtual geometry, with
material variants from Foundry face properties and separate geometry and
instance tables. Reverse unit and axis conversion happens exactly once,
accounting for conversion already performed by virtual geometry.

Tests: `blender/tests/test_import_info_blender.py` verifies source hierarchy
culling, world geometry, collision proxies and absence of ASS snapshots.
`blender/tests/test_legacy_structure_markers_blender.py` checks mesh and marker
export with deliberately invalid stale metadata, shared meshes, mirrored and
nonuniform transforms, and geometry edits. Standalone export is covered by
`blender/tests/test_standalone_export_blender.py`.
