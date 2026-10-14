"""Bind game lighting models to Blender data and shared node sockets."""
from math import pi
import numpy as np


def configure_light(data, node, game, model=None):
    from . import utils
    if node.inputs.get('Engine') is None:
        # An older appended local group is user data; do not overwrite its graph.
        return
    units = 3.048 / utils.get_unit_conversion_factor(None)
    nwo = data.nwo
    h3 = game in {'halo3', 'halo3odst'}
    if model is None:
        model = nwo.light_preview_model
    if model == 'AUTO':
        model = 'H3_BAKED' if h3 else 'LEGACY'
    labels = {'H3_DYNAMIC': 'Halo 3 / ODST Dynamic', 'H3_BAKED': 'Halo 3 / ODST Baked',
              'H2_BAKED': 'Halo 2 Baked',
              'LEGACY': 'Halo 1 / Halo 2 Dynamic' if game in {'halo1', 'halo2'} else 'Reach / Halo 4+'}
    node.inputs['Engine'].default_value = labels[model]
    node.inputs['Scene Units Per WU'].default_value = units
    kind = nwo.light_source_type if nwo.light_source_type != 'AUTO' else data.type
    node.inputs['Light Type'].default_value = {'POINT': 0, 'SPOT': 1, 'SUN': 2}.get(kind, 0)
    if h3:
        data.energy = 1 if kind == 'SUN' else 4 * pi * units ** 2
    node.inputs['Power Conversion'].default_value = (1 if kind == 'SUN' else 4 * pi * units ** 2 / max(data.energy, 1e-8))
    paths = {'Distance Diffusion': 'light_distance_diffusion', 'Angular Smoothness': 'light_angular_smoothness',
             'Percent Spherical': 'light_percent_spherical', 'Cone Angle': 'light_cone_angle',
             'Hotspot Angle': 'light_hotspot_angle', 'Use Near Attenuation': 'light_use_near_attenuation',
             'Use Far Attenuation': 'light_use_far_attenuation', 'Near Start': 'light_near_attenuation_start',
             'Near End': 'light_near_attenuation_end', 'Half Life': 'light_half_life',
             'Lightmap Scale': 'light_lightmap_scale', 'Emitter Radius': 'light_emitter_radius'}
    for name, prop in paths.items():
        socket = node.inputs[name]
        socket.default_value = float(getattr(nwo, prop))
        driver = socket.driver_add('default_value').driver
        driver.type = 'AVERAGE'
        for variable in tuple(driver.variables):
            driver.variables.remove(variable)
        variable = driver.variables.new()
        variable.name = 'setting'
        variable.type = 'SINGLE_PROP'
        variable.targets[0].id_type = 'LIGHT'
        variable.targets[0].id = data
        variable.targets[0].data_path = 'nwo.' + prop
    # A point carrier permits the H3 cone's spherical floor and exact angular
    # ramp; a Blender spot would clip that floor and apply a second smoothstep.
    if h3 and kind == 'SPOT':
        nwo.light_source_type = 'SPOT'
        if model == 'H3_BAKED' and nwo.light_preview_model == 'AUTO' and data.type == 'SPOT':
            nwo.light_cone_angle = data.spot_size
            nwo.light_hotspot_angle = data.spot_size * (1 - data.spot_blend)
        data.type = 'POINT'
    if h3:
        # Radius is a sampling/shadow size, never the near-attenuation interval.
        data.shadow_soft_size = 0 if model == 'H3_DYNAMIC' else 0.02 * units


def patch_areas(mesh, values, wu_per_scene_unit):
    """Local connected same-material/emission patch areas, in wu squared.

    Recompute when refreshing face properties. Apply object scale before the
    refresh for non-unit instances (shared mesh attributes are local data).
    """
    count = len(mesh.polygons)
    parents = list(range(count))
    def root(a):
        while parents[a] != a:
            parents[a] = parents[parents[a]]
            a = parents[a]
        return a
    signatures = []
    for face in mesh.polygons:
        signatures.append((face.material_index, *(tuple(np.atleast_1d(values[name][face.index]))
                          for name in ('foundry_emissive', 'foundry_power', 'foundry_color',
                                       'foundry_emissive_settings', 'foundry_emissive_attenuation') if name in values)))
    edges = {}
    for face in mesh.polygons:
        for edge in face.edge_keys:
            key = (edge, signatures[face.index])
            other = edges.setdefault(key, face.index)
            parents[root(face.index)] = root(other)
    areas = {}
    for face in mesh.polygons:
        key = root(face.index)
        areas[key] = areas.get(key, 0.0) + face.area * wu_per_scene_unit ** 2
    return np.array([areas[root(i)] for i in range(count)], dtype=np.single)
