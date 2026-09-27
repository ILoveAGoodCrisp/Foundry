# JMS interchange

`jms_format.py` owns the format data and streaming reader (8197–8213). It has no
Blender dependency. `jms.py` exposes that API; `jms_importer.py` creates Foundry
objects. `tools/importer.py` dispatches JMS directly to this builder. ASS uses
its own native adapter and shares geometry/material helpers (see `ASS.md`).

## Coordinate contract

- Interchange positions, radii and lengths remain in JMS units.
- Interchange rotations retain file-order XYZW, including the original signs.
- Before 8205, node transforms are parent-relative and node quaternions are
  inverted on import. From 8205, node transforms are absolute. CE marker
  quaternions have their own convention.
- Mesh vertices are absolute. Markers and physics shapes are node-relative.
- The Blender adapter applies Foundry's unit scale to positions and dimensions,
  and its forward-axis rotation to world-space geometry and transforms. Normals
  receive rotation only. Existing armatures are reused by node names and never
  transformed or edited.

## Materials and geometry

Triangles retain source material indices. Partitioning first separates each
region/permutation/LOD, then separates incompatible mesh types and portal
policies. Local vertex maps preserve UVs, normals, colors and skin weights.
BSP imports create a Foundry BSP collection whose BSP identity is the JMS/ASS
filename without its extension. All imported objects belong to that BSP,
including frames, markers, lights and reused ASS instances. Model imports keep
their source regions and an ordinary import collection.
Material flags become Foundry face properties before shader names are deduplicated;
collision/physics materials also become Foundry global material properties.
The source material table is retained on the collection for metadata that does
not have a Foundry equivalent.

Hinge and ragdoll constraints become Foundry constraints. Car-wheel,
point-to-point and prismatic records have no matching Foundry constraint type:
they are retained on non-exporting empties with a warning. Both constraint
frames and source limits remain in metadata. Xrefs, bounding spheres and
skylights also retain their source metadata.

## Export and round trips

`export/legacy.py` adapts evaluated VirtualScene/VirtualMesh geometry to JMS;
`writers.py` serializes the selected dialect. Material variants come from
resolved face properties and region/permutation/LOD, not Blender slot indices.
Unit/axis conversion is reversed at the adapter boundary. Import remains
independent of virtual geometry and tag/export initialization.

For Halo 1, exact and ordinary portals are partitioned separately. Exact Portal
is stored on the object and survives replacing its display material. An explicit
setting takes precedence over the legacy +exactportal material-name fallback.
Real shaders beginning with + (such as +ladder stair) retain their collision and
ladder properties even without a resolved shader path. H1 helper-face flags are
also preserved during import and export cleanup.

Auto import respects an explicit Model/BSP choice first. In Auto mode, an
attached tag armature implies a model; BSP material kinds imply structure;
render/collision/physics folders imply a model; scenario/prefab context implies
structure. Node presence is only a fallback: BSP JMS also has a root node.

## Converting an existing Toolset scene

`bpy.ops.nwo.convert_scene()` uses the current asset type by default. Scenario
and prefab assets receive BSP conversion; model assets retain model conversion.
The converter uses the shared JMS material interpretation, separates exact and
ordinary portals, preserves Halo 1 helper/ladder/collision flags, and makes
scenario `@` meshes collision-only even without a material suffix. Private
material copies retain their clean shader identity when Blender adds a numeric
suffix, so subsequent JMS exports do not duplicate legacy flags or rename shaders.

Scenario conversion preserves existing Foundry BSP collections and child
categories. Otherwise it uses each source collection's name, removing a terminal
`.jms` or `.ass`. Toolset scenes do not retain their original import filepath;
use `bpy.ops.nwo.convert_scene(jms_type='scenario', bsp_name='a10e')` when an
explicit BSP identity is needed. Objects linked only to the scene root use the
saved blend filename, or `default` for an unsaved file. Every converted object,
including frames, markers and lights, receives its BSP assignment. Selected-only
conversion does not reclassify collections or materials shared with unselected
objects. Repeating conversion skips previously converted objects.

## Checks

Run `blender/test_jms_roundtrip.py` with Blender in background factory-startup
mode and `--python-exit-code 1`. The tests use real Foundry properties, importer,
mesh-level property processing, VirtualMesh, the legacy export adapter and JMS
writer. They check portal partitioning, exact-portal material replacement and
explicit disabling, unresolved + shader properties, collision and helper-face
flags, UVs, Auto mode, and a scaled/rotated round trip.

Optional arguments after Blender's `--`:

- `--source input.jms --output directory`: also round-trip a real BSP, comparing
  triangle/material counts, face properties, geometry and UVs. Portal positions
  allow the existing final-coordinate planarization tolerance; other positions
  and UVs must remain within serialization precision.
- `--tool-fixture directory`: write a small sealed BSP and its two exported
  generations for Halo 1 Tool validation. The directory can be an isolated
  editing kit's data/levels/roundtrip/models. Provide wall.shader_environment and
  +ladder stair.shader_environment under tags/levels/roundtrip/shaders, then run
  Tool structure on room_first and room_second. Both must produce BSP tags and
  identical portal/cluster counts, with no import errors.

`blender/test_halo1_portal_export.py` checks bounded portal planarization;
`blender/test_export_output.py` checks export output handling without Blender.

`blender/test_scene_converter.py` checks conversion with actual Toolset RNA
properties, including a JMS export/import/export regression, selected-only
isolation, BSP/category preservation, and the operator's Auto mode. Pass
`-- --toolset PATH_TO_IO_SCENE_HALO` after the Blender script arguments.
