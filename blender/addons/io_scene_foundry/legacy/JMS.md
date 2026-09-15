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
Material flags become Foundry face properties before shader names are deduplicated;
collision/physics materials also become Foundry global material properties.
The source material table is retained on the collection for metadata that does
not have a Foundry equivalent.

Hinge and ragdoll constraints become Foundry constraints. Car-wheel,
point-to-point and prismatic records have no matching Foundry constraint type:
they are retained on non-exporting empties with a warning. Both constraint
frames and source limits remain in metadata. Xrefs, bounding spheres and
skylights also retain their source metadata.

## Future exporter

Populate the format dataclasses from evaluated geometry (for example a
`VirtualScene`/`VirtualMesh` adapter), then add a version-aware writer. Do not
reuse Blender material slot indices as JMS property variants: derive variants
from face properties together with region/permutation/LOD. Reverse the adapter's
unit/axis conversion exactly once, accounting for any conversion already done
by virtual geometry. Rebuild version-specific node transforms and quaternion
conventions at the writer boundary. Import does not initialize virtual geometry
or its tag/export dependencies.

## Checks

`tests/test_jms.py` runs in ordinary Python. `tests/test_jms_blender.py` runs in
background Blender and uses actual Foundry property classes and face helpers,
isolating unrelated add-on startup dependencies. It checks scale, parenting,
material masks, partitioning, UVs, colors, weights, physics and failure cleanup.
