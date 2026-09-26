"""Reflect legacy export records by negating their Y coordinates.

Granny's Mirror option reverses its right vector (Y in Foundry's export
coordinate system). Reflect positions and orientation while preserving the
handedness of triangle faces by reversing their winding.
"""


def mirror_vector(value):
    return (value[0], -value[1], value[2])


def mirror_rotation(value):
    # For M = diag(1, -1, 1), the mirrored rotation is M R M.
    # Quaternions are axial vectors, hence the X and Z sign changes.
    return (-value[0], value[1], -value[2], value[3])


def mirror_transform(value):
    value.rotation = mirror_rotation(value.rotation)
    value.translation = mirror_vector(value.translation)
    return value


def mirror_vertices(vertices):
    for vertex in vertices:
        vertex.position = mirror_vector(vertex.position)
        vertex.normal = mirror_vector(vertex.normal)


def mirror_triangles(triangles):
    for triangle in triangles:
        a, b, c = triangle.vertices
        triangle.vertices = (a, c, b)


def mirror_jms(asset):
    for node in asset.nodes:
        mirror_transform(node.transform)
    for marker in asset.markers:
        mirror_transform(marker.transform)
    for shape in asset.shapes:
        mirror_transform(shape.transform)
        shape.vertices = tuple(mirror_vector(v) for v in shape.vertices)
    for constraint in asset.constraints:
        mirror_transform(constraint.parent_transform)
        mirror_transform(constraint.child_transform)
    asset.instances = [
        (name, uid, xref, mirror_transform(value))
        for name, uid, xref, value in asset.instances
    ]
    asset.bounding_spheres = [
        (mirror_vector(position), radius)
        for position, radius in asset.bounding_spheres
    ]
    asset.skylights = [
        (mirror_vector(direction), color, power)
        for direction, color, power in asset.skylights
    ]
    mirror_vertices(asset.vertices)
    mirror_triangles(asset.triangles)
    return asset


def mirror_ass(asset):
    for instance in asset.instances:
        mirror_transform(instance.local)
        mirror_transform(instance.pivot)
    for geometry in asset.geometries:
        mirror_vertices(geometry.vertices)
        mirror_triangles(geometry.triangles)
    return asset
