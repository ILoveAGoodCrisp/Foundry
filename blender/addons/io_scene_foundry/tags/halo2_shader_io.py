"""Classic H2 template parameter IO and lossless imported-tag preservation."""
from pathlib import Path
import base64,hashlib,json,math,struct,tempfile,zlib
import bpy
from blam_tags import TagFile,RealRgbColor

SCHEMA=Path(__file__).parent/'definitions/halo2_mcc/shader.json'
ANIMATIONS=json.loads(SCHEMA.read_text())['enums_flags']['type_enum_2']['options']

def signature(socket):
    """Stable upstream fingerprint; excludes layout and current scene time."""
    def value(s):
        v=getattr(s,'default_value',None)
        return list(v) if v is not None and not isinstance(v,(str,int,float,bool)) else v
    seen=set();groups=set()
    def group(tree):
        if tree.name in groups:return tree.name
        groups.add(tree.name)
        return [tree.name,[node(n) for n in tree.nodes]]
    def node(n):
        key=(n.id_data.name,n.name)
        if key in seen:return key
        seen.add(key)
        return [n.bl_idname,n.name,getattr(n,'operation',None),getattr(n,'attribute_name',None),
                group(n.node_tree) if n.type=='GROUP' else None,
                [n.image.name,n.image.filepath,n.image.get('source_bitmap','')] if getattr(n,'image',None) else None,
                [(s.identifier,value(s),[(l.from_socket.identifier,node(l.from_node)) for l in s.links]) for s in n.inputs],
                [value(s) for s in n.outputs] if n.type in {'VALUE','RGB'} else None]
    return hashlib.sha256(json.dumps([value(socket),[(l.from_socket.identifier,node(l.from_node)) for l in socket.links]],sort_keys=True).encode()).hexdigest()

def scalar(socket):
    if not socket.is_linked:return socket.default_value
    source=socket.links[0].from_socket
    if source.node.type in {'VALUE','RGB'}:return source.default_value
    raise ValueError(f'Cannot export edited procedural input {socket.name}; use a constant or retain the imported animation')

def set_basic_animation(parameter,kind,value):
    block=parameter.field('animation properties').as_block()
    match=next((x for x in block if x.field('type').options().current_name==kind),None)
    if match is None:match=block[block.add()];match.field('type').set(ANIMATIONS.index(kind))
    match.field('input name').set('');match.field('range name').set('');match.field('time period').set(0)
    data=match.field('function').as_struct().field('data').as_block()
    raw=bytes([1,0,0,0])+struct.pack('<4f',float(value),float(value),0,0)
    while len(data):data.delete(len(data)-1)
    for byte in raw:data[data.add()].field('Value').set(byte if byte<128 else byte-256)

def finish_import(shader,material,group):
    """Add missing transforms and record enough state for safe round trips."""
    tree=material.node_tree;root=shader.tag.root()
    parameters={str(p.field('name').value):p for p in root.field('parameters').as_block()}
    def animation(p,kind):
        if p is None:return None
        try:return shader._halo2_parameter_function(p,kind)
        except (ValueError,NotImplementedError) as exc:
            from .. import utils
            utils.print_warning(f'H2 {p.field("name").value}: {kind} preview unavailable ({exc}); original animation preserved')
            return None
    for image in list(tree.nodes):
        if image.type not in {'TEX_IMAGE','TEX_ENVIRONMENT'}:continue
        name=image.name;p=parameters.get(name)
        image['h2_parameter']=name
        if image.type=='TEX_ENVIRONMENT':continue
        scale_node=tree.nodes.get(name+' animated scale')
        if scale_node:
            scale_node['h2_animation_controls']=json.dumps({axis:dict(parameter=name,kind='bitmap scale '+axis.lower(),signature=signature(scale_node.inputs[axis])) for axis in ('X','Y')})
        elif image.inputs['Vector'].is_linked:
            upstream=image.inputs['Vector'].links[0].from_node
            if upstream.type=='MAPPING':upstream['h2_static_scale']=json.dumps(dict(parameter=name,value=list(upstream.inputs['Scale'].default_value)))
        functions={k:animation(p,k) for k in ['bitmap translation x','bitmap translation y','bitmap rotation angle']}
        if not any(v is not None for v in functions.values()):continue
        # Additional transforms go after established scale helpers. Keep these
        # controls in tag units (rotation turns), converting only at the node.
        vector=image.inputs['Vector'].links[0].from_socket if image.inputs['Vector'].is_linked else None
        if vector is None:
            coord=tree.nodes.new('ShaderNodeTexCoord');coord.location=(image.location.x-1000,image.location.y)
            vector=coord.outputs['Generated' if shader.generated_uvs else 'UV']
        mapping=tree.nodes.new('ShaderNodeMapping');mapping.name=name+' translation and rotation';mapping.location=(image.location.x-250,image.location.y)
        tree.links.new(vector,mapping.inputs['Vector']);tree.links.new(mapping.outputs[0],image.inputs['Vector'])
        translate=tree.nodes.new('ShaderNodeCombineXYZ');translate.name=name+' translation';translate.location=(image.location.x-500,image.location.y-200)
        for axis in ('x','y'):
            port=translate.inputs[axis.upper()];fn=functions['bitmap translation '+axis]
            if fn is not None:shader._setup_input_with_function(port,fn,uses_time=True)
        tree.links.new(translate.outputs[0],mapping.inputs['Location'])
        angle=tree.nodes.new('ShaderNodeMath');angle.name=name+' rotation turns';angle.operation='MULTIPLY';angle.inputs[1].default_value=math.tau;angle.location=(image.location.x-750,image.location.y-300)
        if functions['bitmap rotation angle'] is not None:shader._setup_input_with_function(angle.inputs[0],functions['bitmap rotation angle'],uses_time=True)
        rotation=tree.nodes.new('ShaderNodeCombineXYZ');rotation.name=name+' rotation';rotation.location=(image.location.x-500,image.location.y-380)
        tree.links.new(angle.outputs[0],rotation.inputs['Z']);tree.links.new(rotation.outputs[0],mapping.inputs['Rotation'])
        for node,port,kind in [(translate,'X','bitmap translation x'),(translate,'Y','bitmap translation y'),(angle,0,'bitmap rotation angle')]:
            key=str(port);bindings=json.loads(node.get('h2_animation_controls','{}'))
            bindings[key]=dict(parameter=name,kind=kind,signature=signature(node.inputs[port]));node['h2_animation_controls']=json.dumps(bindings)
    # Preserve unknown fields, source functions and postprocess data verbatim.
    group['h2_shader_snapshot']=base64.b64encode(zlib.compress(shader.tag.write_to_bytes(),9)).decode('ascii')
    group['h2_import_signatures']=json.dumps({s.name:signature(s) for s in group.inputs})
    group['h2_import_template']=group.node_tree.get('h2_template_path','')

def restore_snapshot(shader,encoded):
    raw=zlib.decompress(base64.b64decode(encoded))
    with tempfile.TemporaryDirectory(prefix='foundry_h2_shader_') as temp:
        path=Path(temp)/'snapshot.shader';path.write_bytes(raw)
        source=TagFile.read_classic(path,SCHEMA)
        # Classic containers cannot copy blocks across native documents. Keep
        # the complete deserialized handle, including opaque postprocess data.
        shader._tag=source
        if hasattr(shader,'_native_root'):
            from .field_view import NativeTagStruct
            shader._native_root=NativeTagStruct(shader,source.root())

def write_shader(shader):
    group=shader.group_node
    if group is None or not group.node_tree.get('h2_template'):
        raise ValueError('H2 linked export requires a named H2 template group')
    metadata=json.loads(group.node_tree.get('h2_parameter_metadata','{}'))
    template=group.node_tree.get('h2_template_path')
    if not metadata or not template:raise ValueError('This H2 group has no reviewed parameter-export metadata yet')
    if group.get('h2_shader_snapshot') and group.get('h2_import_template')==template:
        restore_snapshot(shader,group['h2_shader_snapshot'])
    root=shader.tag.root();shader.set_reference(root,'template',template+'.shader_template')
    block=root.field('parameters').as_block();by_name={p.field('name').value:p for p in block}
    original=json.loads(group.get('h2_import_signatures','{}'))
    def ensure(name):
        if name not in by_name:
            p=block[block.add()];p.field('name').set(name);p.field('type').set(['bitmap','value','color','switch'].index(metadata[name]['type']));by_name[name]=p
        return by_name[name]
    def unchanged(s):return original.get(s.name)==signature(s)
    for name,m in metadata.items():
        s=group.inputs.get(name) or group.inputs.get(name+'.rgb')
        if s is None:continue
        if m['type']=='bitmap':
            if unchanged(s):continue
            p=ensure(name);pending=[l.from_node for l in s.links];seen=set();texture=None
            while pending:
                n=pending.pop()
                if n in seen:continue
                seen.add(n)
                if n.type in {'TEX_IMAGE','TEX_ENVIRONMENT'}:texture=n;break
                pending.extend(l.from_node for x in n.inputs for l in x.links)
            if texture is None or texture.image is None:p.field('bitmap').set(None)
            else:shader.set_reference(p,'bitmap',shader._get_bitmap_path(texture))
        elif not unchanged(s):
            value=scalar(s);p=ensure(name)
            if m['type']=='color':p.field('const color').set(RealRgbColor(*value[:3]))
            else:p.field('const value').set(float(value))
            animations=p.field('animation properties').as_block()
            for j in range(len(animations)-1,-1,-1):
                if animations[j].field('type').options().current_name in {'value','color'}:animations.delete(j)
    for n in shader.blender_material.node_tree.nodes:
        for port,b in json.loads(n.get('h2_animation_controls','{}')).items():
            s=n.inputs[int(port) if port.isdigit() else port]
            if signature(s)!=b['signature']:set_basic_animation(ensure(b['parameter']),b['kind'],scalar(s))
        if n.get('h2_static_scale'):
            b=json.loads(n['h2_static_scale']);s=n.inputs['Scale']
            if list(s.default_value)!=b['value'] or s.is_linked:
                values=scalar(s)
                for j,axis in enumerate('xy'):set_basic_animation(ensure(b['parameter']),'bitmap scale '+axis,values[j])
    shader.tag_has_changes=True
