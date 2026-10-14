"""Derive Halo 2's global ocean height from evaluated export geometry."""
from math import isfinite


def water_plane_height(objects, world_unit_scale, depsgraph):
    """Measure face vertices using instance transforms and Halo world units.

    H2 has one horizontal ocean per BSP, so tilted planes or surfaces at
    different elevations cannot be represented by a single height. Forward
    axis correction and export mirroring only affect XY, leaving Z unchanged.
    """
    lower, upper = float('inf'), float('-inf')
    for ob in objects:
        evaluated = ob.eval_ob
        try:
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            if mesh is None or not mesh.polygons:
                raise ValueError(f'Water object [{ob.name}] has no faces')
            # Loose vertices are not exported surfaces and must not move the ocean.
            indices = {loop.vertex_index for loop in mesh.loops}
            for index in indices:
                height = (ob.matrix_world @ mesh.vertices[index].co).z * world_unit_scale
                if not isfinite(height):
                    raise ValueError(f'Water object [{ob.name}] has an invalid height')
                lower, upper = min(lower, height), max(upper, height)
        finally:
            evaluated.to_mesh_clear()
    if not isfinite(lower):
        raise ValueError('No water surface vertices were found')
    # Allow small float evaluation errors, including on large map coordinates.
    tolerance = max(0.0001, max(abs(lower), abs(upper)) * 0.000001)
    if upper - lower > tolerance:
        names = ', '.join(f'[{ob.name}]' for ob in objects)
        raise ValueError(
            f'Halo 2 water must be horizontal and at the same height within a BSP. '
            f'Check {names}')
    return (lower + upper) * 0.5
