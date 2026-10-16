"""Resolve native and legacy water UV streams without rescaling their values."""
import bpy


def mesh_uv_maps(mesh):
    """Recognize native water streams and the legacy three-component base_tex."""
    layers = mesh.uv_layers
    wave = 'UVMap0' if 'UVMap0' in layers else 'UVMap' if 'UVMap' in layers else ''
    paint = 'UVMap1'
    if paint not in layers and 'UVMap.003' in layers and 'W:UVMap.003' in layers:
        paint = 'UVMap.003'
    return wave, paint


def uv_maps(tree):
    """Use the material's existing mesh layout when rebuilding its shader.

    Native tag imports name the two streams UVMap0/UVMap1. Legacy water
    imports can retain base_tex as UVMap.003 plus its third component in
    W:UVMap.003. Do not infer water paint from an arbitrary fourth UV layer.
    Import finalization binds these again after mesh creation and separates
    shared materials when their meshes require different UV names.
    """
    layouts = set()
    for mesh in bpy.data.meshes:
        if not any(mat and mat.node_tree == tree for mat in mesh.materials):
            continue
        layouts.add(mesh_uv_maps(mesh))
    return next(iter(layouts)) if len(layouts) == 1 else ('UVMap0', 'UVMap1')


def add_uv_nodes(tree, *, wave_uv=None, paint_uv=None):
    """Use editable UV maps directly, bypassing old scaled coordinate groups."""
    mesh_wave, mesh_paint = uv_maps(tree)
    wave = tree.nodes.new('ShaderNodeUVMap')
    wave.name = 'Water wave UV'
    wave.label = 'Wave and foam coordinates'
    wave.uv_map = mesh_wave if wave_uv is None else wave_uv
    wave.location = (-1500, 200)
    paint = tree.nodes.new('ShaderNodeUVMap')
    paint.name = 'Water paint UV'
    paint.label = 'Shoreline, water color and painted foam'
    paint.uv_map = mesh_paint if paint_uv is None else paint_uv
    paint.location = (-1300, -100)
    return wave.outputs['UV'], paint.outputs['UV']


def _coordinate_nodes(tree):
    """Return the UV nodes and their optional Reach coordinate group instance."""
    if tree is None:
        return None
    wave = tree.nodes.get('Water wave UV')
    paint = tree.nodes.get('Water paint UV')
    if wave and paint and wave.type == paint.type == 'UVMAP':
        return wave, paint, None
    for node in tree.nodes:
        if node.type != 'GROUP' or node.node_tree is None:
            continue
        if not node.node_tree.name.startswith('foundry_reach.shader_water - texture coordinates'):
            continue
        output = next((n for n in node.node_tree.nodes if n.type == 'GROUP_OUTPUT'), None)
        if output is None:
            continue
        ports = [output.inputs.get(name) for name in ('Wave UV', 'Paint UV')]
        if all(port and port.is_linked and port.links[0].from_node.type == 'UVMAP' for port in ports):
            return ports[0].links[0].from_node, ports[1].links[0].from_node, node
    return None


def _bind_uv_maps(tree, layout):
    wave, paint, group = _coordinate_nodes(tree)
    if (wave.uv_map, paint.uv_map) == layout:
        return
    if group is not None:
        # Resource groups and material copies can share the same node tree.
        group.node_tree = group.node_tree.copy()
        wave, paint, _ = _coordinate_nodes(tree)
    wave.uv_map, paint.uv_map = layout


def bind_water_materials(meshes):
    """Bind imported water after geometry, shader copying and material reuse.

    A material can be shared by native and legacy imports. Give conflicting
    layouts separate material instances, keeping the editable UV data intact
    and leaving materials on meshes outside this import unchanged.
    """
    meshes = set(meshes)
    materials = {mat for mesh in meshes for mat in mesh.materials
                 if mat is not None and mat.is_editable and _coordinate_nodes(mat.node_tree)}
    outside_materials = {mat for mesh in bpy.data.meshes if mesh not in meshes
                         for mat in mesh.materials if mat in materials}
    for material in materials:
        layouts = {}
        for mesh in meshes:
            if material.name in mesh.materials:
                layouts.setdefault(mesh_uv_maps(mesh), []).append(mesh)
        wave, paint, _ = _coordinate_nodes(material.node_tree)
        current = (wave.uv_map, paint.uv_map)
        preferred = current if material in outside_materials or current in layouts else next(iter(layouts))
        _bind_uv_maps(material.node_tree, preferred)
        variants = {preferred: material}
        for layout, users in layouts.items():
            variant = variants.get(layout)
            if variant is None:
                variant = material.copy()
                _bind_uv_maps(variant.node_tree, layout)
                variants[layout] = variant
            for mesh in users:
                for index, mat in enumerate(mesh.materials):
                    if mat == material:
                        mesh.materials[index] = variant


def texture(root, parameter):
    """Painted bank alpha may be the only connected channel of its bitmap."""
    for suffix in ('.rgb', '.a'):
        port = root.inputs.get(parameter + suffix)
        if port is None or not port.is_linked:
            continue
        node = port.links[0].from_node
        while node.type == 'REROUTE' and node.inputs[0].is_linked:
            node = node.inputs[0].links[0].from_node
        if node.type == 'TEX_IMAGE':
            return node
    return None
