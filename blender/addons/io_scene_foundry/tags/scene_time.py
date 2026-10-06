"""Driver-free shader time, preferring Blender's native Scene Time node."""
import bpy


def scene_time_node(tree):
    # Discover the registered type by its RNA name and shader-tree support;
    # Scene Time exists in several editors with different API identifiers.
    for name in dir(bpy.types):
        node_type = getattr(bpy.types, name)
        if (isinstance(node_type, type) and issubclass(node_type, bpy.types.Node)
                and node_type.bl_rna.name == 'Scene Time' and node_type.poll(tree)):
            node = tree.nodes.new(node_type.bl_rna.identifier)
            if node.outputs.get('Seconds') is not None:
                return node
            tree.nodes.remove(node)

    # Older builds can read these properties directly in the shader. Unlike a
    # driver, VIEW_LAYER attributes do not retain a pointer to a particular scene.
    name = 'foundry.scene_time_compat'
    group = bpy.data.node_groups.get(name)
    if group is None:
        group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        for output in ('Seconds', 'Frame'):
            group.interface.new_socket(name=output, in_out='OUTPUT', socket_type='NodeSocketFloat')
        output = group.nodes.new('NodeGroupOutput')

        def attribute(name, location):
            node = group.nodes.new('ShaderNodeAttribute')
            node.attribute_type = 'VIEW_LAYER'
            node.attribute_name = name
            node.location = location
            return node.outputs['Fac']

        frame = attribute('frame_current', (-600, 160))
        fps_base = attribute('render.fps_base', (-600, -80))
        fps = attribute('render.fps', (-360, -260))
        scaled = group.nodes.new('ShaderNodeMath')
        scaled.operation = 'MULTIPLY'
        scaled.location = (-340, 100)
        group.links.new(frame, scaled.inputs[0])
        group.links.new(fps_base, scaled.inputs[1])
        seconds = group.nodes.new('ShaderNodeMath')
        seconds.operation = 'DIVIDE'
        seconds.location = (-100, 100)
        group.links.new(scaled.outputs[0], seconds.inputs[0])
        group.links.new(fps, seconds.inputs[1])
        group.links.new(seconds.outputs[0], output.inputs['Seconds'])
        group.links.new(frame, output.inputs['Frame'])
        output.location = (140, 100)
    node = tree.nodes.new('ShaderNodeGroup')
    node.node_tree = group
    node.label = 'Scene Time (compatibility)'
    return node
