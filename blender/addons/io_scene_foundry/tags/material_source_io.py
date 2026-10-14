"""Populate and export independently sampled textures in source-built templates."""
import bpy
from ..material_shader_library import parameter_key
from .material_vectors import _time


def make_instance(tree, node):
    node.node_tree=node.node_tree.copy()
    node.node_tree['foundry_source_instance']=True
    node.node_tree.use_fake_user=False
    if node.node_tree.get('foundry_support_level')=='partial':
        node.label=node.node_tree.get('foundry_material_shader',node.node_tree.name)+' (partial preview)'
    if node.inputs.get('Shader time') is not None:
        tree.links.new(_time(tree),node.inputs['Shader time'])
    for label,axis in (('Preview screen width','x'),('Preview screen height','y')):
        if node.inputs.get(label) is None:continue
        value=tree.nodes.new('ShaderNodeValue');value.label=label
        driver=value.outputs[0].driver_add('default_value').driver
        for name,path in (('dimension','render.resolution_'+axis),('percentage','render.resolution_percentage')):
            variable=driver.variables.new();variable.name=name;variable.type='SINGLE_PROP'
            variable.targets[0].id_type='SCENE';variable.targets[0].id=bpy.context.scene;variable.targets[0].data_path=path
        driver.expression='dimension * percentage / 100'
        tree.links.new(value.outputs[0],node.inputs[label])
    for socket in node.inputs:
        if socket.name.endswith('Change Color Alpha'):
            attribute=tree.nodes.new('ShaderNodeAttribute');attribute.attribute_type='INSTANCER'
            attribute.attribute_name=socket.name.replace(' Change Color Alpha',' Color')
            tree.links.new(attribute.outputs['Alpha'],socket)


def populate(reader, surface, parameters):
    tree=surface.node_tree
    by_name={parameter_key(p.name):p for p in parameters.values()}
    images={};alpha_images={}
    for node in list(tree.nodes):
        if node.get('foundry_preview_only'):continue
        name=node.get('foundry_material_parameter')
        if not name:continue
        parameter=by_name.get(parameter_key(name))
        if parameter is None:continue
        if name not in images:
            result=reader._image_from_parameter(parameter)
            if result and result[0] is not None:
                image,wrap,sequence=result
                # Source sample2D/sample2DGamma explicitly controls gamma; never
                # change the image used by another material or sampling branch.
                if image.colorspace_settings.name!='Non-Color':
                    pixels=None
                    if image.source=='GENERATED' or image.is_dirty:
                        import numpy as np
                        pixels=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(pixels)
                    image=image.copy();image.colorspace_settings.name='Non-Color'
                    if pixels is not None:image.pixels.foreach_set(pixels)
                images[name]=(image,wrap,sequence)
            else:images[name]=None
        result=images[name]
        if result is None:continue
        image,wrap,sequence=result
        if node.get('foundry_source_alpha'):
            if name not in alpha_images:
                import numpy as np
                pixels=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(pixels)
                rgba=pixels.reshape((-1,4));rgba[:,:3]=rgba[:,3,None];rgba[:,3]=1.
                alpha=bpy.data.images.new(image.name+' (reflection alpha)',width=image.size[0],height=image.size[1],float_buffer=image.is_float)
                alpha.colorspace_settings.name='Non-Color';alpha.pixels.foreach_set(pixels);alpha.pack()
                alpha_images[name]=alpha
            node.image=alpha_images[name]
        else:node.image=image
        if sequence>1:
            from .connected_material import AnimatedParameterType,Function
            value=reader._value_from_parameter(parameter,AnimatedParameterType.FRAME_INDEX)
            if not isinstance(value,Function):
                function=Function();function.clamp_min=float(value) if isinstance(value,(int,float)) else 0.;value=function
            reader._setup_sequence_driver(tree,node,sequence,value)
        if node.type=='TEX_IMAGE':
            from .shader_address import setup_address
            node['foundry_address_modes']=list(wrap) if not isinstance(wrap,str) else [0,0]
            setup_address(tree,node,wrap)
    for node in list(tree.nodes):
        name=node.get('foundry_material_texture_size')
        if name and images.get(name):node.outputs[0].default_value=max(1,images[name][0].size[node['foundry_texture_size_axis']])
        name=node.get('foundry_material_transform')
        if not name:continue
        parameter=by_name.get(parameter_key(name))
        if parameter is None:continue
        replacement=reader._tiling_from_animated_parameters(tree,parameter)
        if replacement is None:continue
        if node.get('foundry_transform_components'):
            for target in node.inputs:
                original=replacement.inputs.get(target.name)
                if original is not None:
                    if original.is_linked:tree.links.new(original.links[0].from_socket,target)
                    else:target.default_value=original.default_value
            tree.nodes.remove(replacement)
            continue
        replacement['foundry_material_transform']=name
        uv=node.inputs['Vector'].links[0].from_socket if node.inputs['Vector'].links else None
        vector=replacement.inputs.get('Vector') or replacement.inputs[-1]
        if uv is not None:tree.links.new(uv,vector)
        for link in list(node.outputs[0].links):tree.links.new(replacement.outputs[0],link.to_socket)
        replacement.location=node.location;tree.nodes.remove(node)


def textures(surface):
    """One authored bitmap per parameter, regardless of shader sample count."""
    found={}
    for node in surface.node_tree.nodes:
        if node.get('foundry_preview_only'):continue
        name=node.get('foundry_material_parameter')
        if name and not node.get('foundry_source_alpha') and name not in found and node.image is not None and not node.image.get('foundry_source_placeholder'):
            found[name]=node
    return found


def mapping(source, enum):
    name=source.get('foundry_material_parameter')
    transform=next((n for n in source.id_data.nodes if n.get('foundry_material_transform')==name),None)
    values={enum.SCALE_UNIFORM:1.,enum.SCALE_X:1.,enum.SCALE_Y:1.,enum.TRANSLATION_X:0.,enum.TRANSLATION_Y:0.}
    if transform is None:return values
    if transform.type=='MAPPING':
        scale=transform.inputs['Scale'].default_value;location=transform.inputs['Location'].default_value
        values.update({enum.SCALE_X:scale.x,enum.SCALE_Y:scale.y,enum.TRANSLATION_X:location.x,enum.TRANSLATION_Y:location.y})
    else:
        for key,label in ((enum.SCALE_UNIFORM,'Scale Multiplier'),(enum.SCALE_X,'Scale X'),(enum.SCALE_Y,'Scale Y'),
                          (enum.TRANSLATION_X,'Translate X'),(enum.TRANSLATION_Y,'Translate Y')):
            socket=transform.inputs.get(label)
            if socket is not None and not socket.is_linked:values[key]=socket.default_value
            else:values.pop(key,None)
    return values
