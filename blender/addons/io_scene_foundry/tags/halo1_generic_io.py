"""Panel-aware H1 generic shader IO and the two resource coordinate groups."""
import json
from math import degrees
import bpy
from blam_tags import RealArgbColor

COLOR_INPUTS=['zero','one','one half','negative one','negative one half',
    *['map color '+str(i) for i in range(4)],'vertex color 0 / diffuse light','vertex color 1 / fade(perpendicular)',
    'scratch color 0','scratch color 1','constant color 0','constant color 1',
    *['map alpha '+str(i) for i in range(4)],'vertex alpha 0 / fade(none)','vertex alpha 1 / fade(perpendicular)',
    'scratch alpha 0','scratch alpha 1','constant alpha 0','constant alpha 1']
ALPHA_INPUTS=['zero','one','one half','negative one','negative one half',
    *['map alpha '+str(i) for i in range(4)],'vertex alpha 0 / fade(none)','vertex alpha 1 / fade(perpendicular)',
    'scratch alpha 0','scratch alpha 1','constant alpha 0','constant alpha 1',
    *['map blue '+str(i) for i in range(4)],'vertex blue 0 / blue light','vertex blue 1 / fade(parallel)',
    'scratch blue 0','scratch blue 1','constant blue 0','constant blue 1']
COLOR_OUTPUTS=['discard','scratch color 0 / final color','scratch color 1','vertex color 0','vertex color 1',*['map color '+str(i) for i in range(4)]]
ALPHA_OUTPUTS=['discard','scratch alpha 0 / final alpha','scratch alpha 1','vertex alpha 0 / fog','vertex alpha 1',*['map alpha '+str(i) for i in range(4)]]
MAPPINGS=['clamp(x)','1 - clamp(x)','2*clamp(x) - 1','1 - 2*clamp(x)','clamp(x) - 1/2','1/2 - clamp(x)','x','-x']
OUTPUT_MAPPINGS=['identity','scale by 1/2','scale by 2','scale by 4','bias by -1/2','expand normal']
FIRST_TYPES=['2D map','reflection cube map','object-centered cube map','viewer-centered cube map']

def inputs_by_path(node):
    sockets={s.identifier:s for s in node.inputs};result={}
    for s in node.node_tree.interface.items_tree:
        if s.item_type!='SOCKET' or s.in_out!='INPUT':continue
        path=[];p=s.parent
        while p:
            if p.name:path.insert(0,p.name)
            p=p.parent
        result[tuple(path+[s.name])]=sockets[s.identifier]
    return result

def menu_labels(field,path):
    channel=path[-2] if len(path)>1 else ''
    if field.startswith('input '):
        if 'mapping' in field:return MAPPINGS
        return ALPHA_INPUTS if field.endswith(' alpha') else COLOR_INPUTS
    if field.startswith('output mapping'):return OUTPUT_MAPPINGS
    if field.startswith('output ') and 'function' not in field:
        return ALPHA_OUTPUTS if field.endswith(' alpha') else COLOR_OUTPUTS
    if field=='first map type':return FIRST_TYPES
    return None

def enum_value(shader,struct,field,labels=None):
    options=shader.required_field(struct,field).options();index=list(options.names).index(options.current_name)
    return labels[index] if labels else options.current_name.replace('variable period','(variable period)')

def vector_node(shader,tree,root,parameters,properties,flags,index,resources,map_flags=None):
    name='foundry_h1.shader_transparent_generic_map0_vector' if index==0 else 'foundry_h1.shader_transparent_generic_map_vector'
    group_tree=resources('h1_nodes',name)
    if group_tree is None:raise ValueError('Missing H1 generic coordinate resource '+name)
    node=tree.nodes.new('ShaderNodeGroup');node.node_tree=group_tree
    node.label=f'map{index} coordinates'
    node.location=(-700,-240*index)
    for field,port in [('map u scale','map u-scale'),('map v scale','map v-scale'),('map u offset','map u-offset'),
            ('map v offset','map v-offset'),('map rotation','map rotation')]:
        value=float(shader.value(parameters,field))
        node.inputs[port].default_value=(value or 1) if field.endswith(' scale') else value
    if index==0:
        node.inputs['first map type'].default_value=enum_value(shader,properties,'first map type',FIRST_TYPES)
        node.inputs['first map is in screenspace'].default_value=flags.get_flag('first map is in screenspace')
    if map_flags is not None:
        for axis in ('u','v'):
            socket=node.inputs.get(axis+' clamped')
            if socket is not None:socket.default_value=map_flags.get_flag(axis+' clamped')
    return node

def write_generic_shader(shader):
    root_node=shader.group_node
    if root_node is None or shader._normalize_group_name(root_node.node_tree.name)!='foundry_h1.shader_transparent_generic':
        raise ValueError('H1 generic export requires a shader_transparent_generic group connected to the material output')
    root=shader.tag.root();inputs=inputs_by_path(root_node)
    def field(s,name):return shader.required_field(s,name)
    def block(s,name):return field(s,name).as_block()
    def struct(s,name):return field(s,name).as_struct()
    def scalar(s,name,value):field(s,name).set(value)
    def menu(s,name,value,labels=None):
        options=field(s,name).options();choices=labels or [x.replace('variable period','(variable period)') for x in options.names]
        if value not in choices:raise ValueError(f'Unsupported {name} value: {value}')
        field(s,name).set(choices.index(value))
    def get(path,default=None):
        s=inputs.get(path);return s.default_value if s is not None else default
    properties=struct(root,'properties');flags=field(properties,'flags')
    for name,label in [('alpha tested','alpha-tested'),('two sided','two-sided')]:flags.set_flag(name,get(('generic transparent shader',label),False))
    menu(properties,'framebuffer blend function',get(('generic transparent shader','framebuffer blend function')))
    maps=block(root,'maps');stages=block(root,'stages')
    map_count=max((i+1 for i in range(4) if get(('MAPS',f'map{i}',f'map{i}'),False)),default=0)
    stage_count=max((i+1 for i in range(7) if get(('STAGES',f'stage{i}',f'stage{i}'),False)),default=0)
    # Keep existing rows and their unsupported animation fields. Only resize the
    # trailing range; sparse disabled stages become explicit no-op combiners.
    for data,count in ((maps,map_count),(stages,stage_count)):
        while len(data)>count:data.delete(len(data)-1)
        while len(data)<count:data.add()
    for index,row in enumerate(maps):
        prefix=('MAPS',f'map{index}');parameters=struct(row,'parameters')
        source_socket=inputs[(*prefix,'map')]
        image=source_socket.links[0].from_node if source_socket.is_linked else None
        if image is not None and image.type not in {'TEX_IMAGE','TEX_ENVIRONMENT'}:
            raise ValueError(f'map{index} Color must come from a texture node for generic tag export')
        enabled=get((*prefix,f'map{index}'),False)
        shader.set_reference(parameters,'map',shader._get_bitmap_path(image) if image and enabled else None)
        if image is None:continue
        vector=image.inputs['Vector'].links[0].from_node if image.inputs['Vector'].is_linked else None
        wanted='foundry_h1.shader_transparent_generic_map0_vector' if index==0 else 'foundry_h1.shader_transparent_generic_map_vector'
        if vector and vector.type=='GROUP' and shader._normalize_group_name(vector.node_tree.name)==wanted:
            for name,port in [('map u scale','map u-scale'),('map v scale','map v-scale'),('map u offset','map u-offset'),('map v offset','map v-offset'),('map rotation','map rotation')]:
                scalar(parameters,name,float(vector.inputs[port].default_value))
            if index==0:
                menu(properties,'first map type',vector.inputs['first map type'].default_value,FIRST_TYPES)
                flags.set_flag('first map is in screenspace',vector.inputs['first map is in screenspace'].default_value)
            for axis in ('u','v'):
                if vector.inputs.get(axis+' clamped') is not None:
                    field(row,'flags').set_flag(axis+' clamped',vector.inputs[axis+' clamped'].default_value)
        elif vector and vector.type=='MAPPING':
            # Retain compatibility with older imported graphs.
            for name,value in [('map u scale',vector.inputs['Scale'].default_value.x),('map v scale',vector.inputs['Scale'].default_value.y),
                    ('map u offset',vector.inputs['Location'].default_value.x),('map v offset',vector.inputs['Location'].default_value.y),
                    ('map rotation',degrees(vector.inputs['Rotation'].default_value.z))]:scalar(parameters,name,float(value))
        elif vector is not None:raise ValueError(f'map{index} uses an unsupported coordinate graph; connect its H1 vector group directly')
        row_flags=field(row,'flags');row_flags.set_flag('unfiltered',image.interpolation=='Closest')
        # Axis-specific flags not changed in the node graph remain preserved.
        if image.type=='TEX_IMAGE' and image.extension=='EXTEND' and not (vector and vector.type=='GROUP'):
            row_flags.set_flag('u clamped',True);row_flags.set_flag('v clamped',True)
    for index,row in enumerate(stages):
        prefix=('STAGES',f'stage{index}');constants=(*prefix,'constants and animation')
        if not get((*prefix,f'stage{index}'),False):
            for name in ('output ab','output bc','output ab cd mux sum','output ab alpha','output cd alpha','output ab cd mux sum alpha'):scalar(row,name,0)
            continue
        menu(row,'color0 animation function',get((*constants,'color0 animation function')))
        scalar(row,'color0 animation period',float(get((*constants,'color0 animation period'))))
        for name in ('color0 animation lower bound','color0 animation upper bound','color1'):
            c=get((*constants,name));alpha=float(get((*constants,name+' alpha'),c[3]))
            scalar(row,name,RealArgbColor(alpha,float(c[0]),float(c[1]),float(c[2])))
        row_flags=field(row,'flags')
        for channel in ('color','alpha'):
            mux=get((*prefix,channel+' outputs',channel+' mux'))
            if mux is not None:row_flags.set_flag(channel+' mux',bool(mux))
            suffix=' alpha' if channel=='alpha' else ''
            for letter in 'ABCD':
                for mapping in ('',' mapping'):
                    name=f'input {letter.lower()}{mapping}{suffix}'
                    menu(row,name,get((*prefix,channel+' inputs',f'input {letter}{mapping}')),menu_labels(name,()))
            for dest in ('AB','CD','AB CD mux/sum','mapping'):
                name='output mapping'+(' alpha' if suffix else ' color') if dest=='mapping' else 'output '+dest.lower().replace('mux/sum','mux sum')+suffix
                if channel=='color' and dest=='CD':name='output bc'
                menu(row,name,get((*prefix,channel+' outputs','output '+dest)),menu_labels(name,()))
            if channel=='color':
                for dest in ('AB','CD'):menu(row,'output '+dest.lower()+' function',get((*prefix,'color outputs','output '+dest+' function')))
