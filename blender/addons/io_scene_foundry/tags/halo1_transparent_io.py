"""Tag-backed IO for the remaining Halo 1 transparent material families.

Bindings refer to schema paths, never socket order. Unrepresented fields (fog,
extra passes, CPU-only options) survive export through a typed tag snapshot.
"""
import json
import math
from pathlib import Path
import bpy
from blam_tags import RealRgbColor, RealArgbColor

KINDS={f'shader_transparent_{name}' for name in
       ('chicago','chicago_extended','glass','meter','plasma','water')}

def resolve(root,path):
    current=root
    for i,key in enumerate(path):
        if isinstance(key,int):current=current[key]
        else:
            field=current.field(key)
            if field is None:raise KeyError('.'.join(map(str,path)))
            if i==len(path)-1:return field
            current=field.as_block() if isinstance(path[i+1],int) else field.as_struct()
    return current

def schema(kind):
    return json.loads((Path(__file__).parent/'definitions/haloce_mcc'/(kind+'.json')).read_text())

def snapshot(root,kind):
    d=schema(kind)
    def walk(s,name):
        out={}
        for f in d['structs'][name]['fields']:
            n=f.get('name');t=f['type']
            if not n or t in {'pad','useless_pad','skip','explanation','custom','terminator'}:continue
            field=s.field(n)
            if field is None:continue
            if t=='struct':out[n]=walk(field.as_struct(),f['definition'])
            elif t=='block':out[n]=[walk(x,d['blocks'][f['definition']]['struct']) for x in field.as_block()]
            elif t.endswith('_flags'):out[n]={x:field.get_flag(x) for x in d['enums_flags'][f['definition']]['options']}
            elif t.endswith('_enum'):out[n]=field.options().current
            else:
                v=field.value
                if hasattr(v,'red'):v=[v.red,v.green,v.blue]+([v.alpha] if hasattr(v,'alpha') else [])
                elif hasattr(v,'x'):v=[v.x,v.y]+([v.z] if hasattr(v,'z') else [])
                elif hasattr(v,'i'):v=[v.i,v.j,v.k]
                elif not isinstance(v,(int,float,str,bool,tuple,list,type(None))):continue
                out[n]=v
        return out
    return walk(root,d['blocks'][d['block']]['struct'])

def restore(root,kind,data):
    d=schema(kind)
    def walk(s,name,values):
        for f in d['structs'][name]['fields']:
            n=f.get('name');t=f['type']
            if n not in values:continue
            value=values[n];field=s.field(n)
            if t=='struct':walk(field.as_struct(),f['definition'],value)
            elif t=='block':
                block=field.as_block()
                while len(block)>len(value):block.delete(len(block)-1)
                while len(block)<len(value):block.add()
                for i,v in enumerate(value):walk(block[i],d['blocks'][f['definition']]['struct'],v)
            elif t.endswith('_flags'):
                for flag,on in value.items():field.set_flag(flag,on)
            elif t=='tag_reference':field.set(tuple(value) if value is not None else None)
            else:set_field(field,value)
    walk(root,d['blocks'][d['block']]['struct'],data)

def set_field(field,value):
    old=field.value
    if hasattr(old,'red'):
        value=(RealArgbColor(value[3],*value[:3]) if hasattr(old,'alpha') else RealRgbColor(*value[:3]))
    elif hasattr(old,'x') or hasattr(old,'i'):value=type(old)(*value)
    elif isinstance(old,tuple):value=tuple(value) if value is not None else None
    field.set(value)

class MaterialGraph:
    def __init__(self,tree):self.tree=tree;self.frame=None;self.index=0
    def section(self,label,x,y):
        self.frame=None;f=self.node('NodeFrame',label);f.location=(x,y);f.label_size=24;self.frame=f;self.index=0
    def node(self,kind,label):
        n=self.tree.nodes.new(kind);n.label=label;n.name=label;n.width=190
        if self.frame:n.parent=self.frame;n.location=((self.index%4)*230,-(self.index//4)*220);self.index+=1
        return n
    def put(self,s,v):
        if isinstance(v,bpy.types.NodeSocket):self.tree.links.new(v,s)
        else:s.default_value=v
    def math(self,label,op,a,b=0):
        n=self.node('ShaderNodeMath',label);n.operation=op;self.put(n.inputs[0],a);self.put(n.inputs[1],b);return n.outputs[0]
    def vec(self,label,op,a,b=(0,0,0)):
        n=self.node('ShaderNodeVectorMath',label);n.operation=op;self.put(n.inputs[0],a);self.put(n.inputs[1],b);return n.outputs[0]
    def scale(self,label,a,b):
        n=self.node('ShaderNodeVectorMath',label);n.operation='SCALE';self.put(n.inputs[0],a);self.put(n.inputs[3],b);return n.outputs[0]
    def mix(self,label,a,b,f,color=False):
        n=self.node('ShaderNodeMix',label);n.data_type='RGBA' if color else 'FLOAT';n.clamp_factor=False
        self.put(n.inputs[0],f);self.put(n.inputs[6 if color else 2],a);self.put(n.inputs[7 if color else 3],b);return n.outputs[2 if color else 0]
    def xyz(self,label,x,y,z=0):
        n=self.node('ShaderNodeCombineXYZ',label)
        for i,v in enumerate((x,y,z)):self.put(n.inputs[i],v)
        return n.outputs[0]
    def control(self,root,path,component=None):
        value=resolve(root,path).value
        if component is not None:
            keys=('x','y','z') if hasattr(value,'x') else ('i','j','k')
            value=getattr(value,keys[component])
        n=self.node('ShaderNodeValue',str(path[-1])+(' '+str(component) if component is not None else ''))
        n.outputs[0].default_value=value
        n['h1_value_binding']=json.dumps(dict(path=path,component=component))
        return n.outputs[0]
    def zero_default(self,label,value,default=1):
        equal=self.math(label+' zero','COMPARE',value,0)
        equal.node.inputs[2].default_value=0.0000001
        return self.mix(label,value,default,equal)

def control_image(image):
    if image.colorspace_settings.name=='Non-Color' and image.alpha_mode=='CHANNEL_PACKED':return image
    name=image.name+' [H1 control]';copy=bpy.data.images.get(name)
    if copy is None:
        copy=image.copy();copy.name=name;copy.colorspace_settings.name='Non-Color';copy.alpha_mode='CHANNEL_PACKED'
    return copy

def texture(g,result,path,role):
    n=g.node('ShaderNodeTexEnvironment' if result.cubemap else 'ShaderNodeTexImage',str(path[-1]))
    n.image=control_image(result.image) if role in ('bitmap_data','bitmap_volume','bitmap_ripples') else result.image
    n['h1_bitmap_binding']=json.dumps(path)
    return n

def reflection_vector(g,bump=None,mode=None,mask=None):
    geo=g.node('ShaderNodeNewGeometry','Reflection geometry');normal=geo.outputs['Normal']
    if bump is not None:
        n=g.node('ShaderNodeNormalMap','DirectX cubemap normal');n.convention='DIRECTX';g.put(n.inputs['Color'],bump)
        normal=n.outputs[0]
        use=g.math('Bumped mode','COMPARE',mode,0) if mode is not None else 1
        if mask is not None:use=g.math('No bump for RGB mask','MULTIPLY',use,g.math('Not mask','SUBTRACT',1,mask))
        if mode is not None or mask is not None:
            n=g.node('ShaderNodeMix','Flat or bumped normal');n.data_type='VECTOR'
            g.put(n.inputs[0],use);g.put(n.inputs[4],geo.outputs['Normal']);g.put(n.inputs[5],normal);normal=n.outputs[1]
    incoming=g.scale('Incident direction',geo.outputs['Incoming'],-1)
    return g.vec('Reflected cubemap direction','REFLECT',incoming,normal)

def chicago_vector(shader,g,row,props,flags,index,resources):
    from .halo1_generic_io import vector_node
    parameters=resolve(shader.tag.root(),row+['parameters']).as_struct()
    node=vector_node(shader,g.tree,None,parameters,props,flags,index,resources,resolve(shader.tag.root(),row+['flags']))
    node['h1_chicago_vector_path']=json.dumps(row)
    # Keep the established coordinate helper and apply time animation to its
    # existing offset/rotation ports. All editable controls map to tag fields.
    for axis in ('u','v','rotation'):
        path=row+['animation'];anim=resolve(shader.tag.root(),path).as_struct()
        wave=g.node('ShaderNodeGroup',axis+' animation');wave.node_tree=resources('h1_nodes','foundry_h1.tag_animation')
        # tag_animation uses the native schema names, without display parentheses.
        fn=anim.field(axis+' animation function').options().current_name
        wave.inputs['Animation Function'].default_value=fn
        wave.inputs['Animation Period'].default_value=float(anim.field(axis+' animation period').value) or 1
        wave.inputs['Animation Phase'].default_value=anim.field(axis+' animation phase').value
        wave.inputs['No Random Phase'].default_value=True
        wave['h1_animation_binding']=json.dumps(dict(path=path,axis=axis))
        scale=g.control(shader.tag.root(),path+[axis+' animation scale'])
        scale=g.zero_default(axis+' default animation scale',scale,360 if axis=='rotation' else 1)
        offset=g.control(shader.tag.root(),row+['parameters','map rotation' if axis=='rotation' else 'map '+axis+' offset'])
        value=g.math(axis+' animated transform','ADD',offset,g.math(axis+' wave scale','MULTIPLY',wave.outputs[0],scale))
        g.put(node.inputs['map rotation' if axis=='rotation' else 'map '+axis+'-offset'],value)
    # CPU-dependent source modulation and off-center rotation remain preserved
    # in the snapshot; the native helper currently rotates around its origin.
    return node.outputs['Vector']

def volume_sample(shader,g,result,path):
    """Trilinear sample of native bitmap_tiff's vertically stacked slices."""
    import numpy as np
    from blam_tags import TagFile
    image=control_image(result.image)
    # The extraction records dimensions only in the bitmap tag.
    field=resolve(shader.tag.root(),path);relative=field.value[1]
    tags=shader.system_path
    while tags.name.lower()!='tags' and tags.parent!=tags:tags=tags.parent
    tag=TagFile.read_classic(tags/(relative+'.bitmap'),Path(__file__).parent/'definitions/haloce_mcc/bitmap.json')
    b=tag.root().field('bitmaps').as_block()[0]
    w,h,d=(int(b.field(k).value) for k in ('width','height','depth'))
    if d<=1:
        n=texture(g,result,path,'bitmap_volume');return n.outputs['Color'],n.outputs['Alpha']
    if tuple(image.size)!=(w,h*d):raise ValueError(f'Expected all {d} volume slices for {relative}; got {tuple(image.size)}')
    name=image.name+' [volume gutters]';atlas=bpy.data.images.get(name)
    if atlas is None:
        pixels=np.empty(w*h*d*4,dtype=np.float32);image.pixels.foreach_get(pixels)
        slices=pixels.reshape(d,h,w,4)
        padded=np.pad(slices,((0,0),(1,1),(1,1),(0,0)),mode='wrap')
        atlas=bpy.data.images.new(name,width=w+2,height=(h+2)*d,alpha=True,float_buffer=True)
        atlas.colorspace_settings.name='Non-Color';atlas.alpha_mode='CHANNEL_PACKED';atlas.pixels.foreach_set(padded.ravel());atlas.pack()
        # Keep original bitmap provenance for Foundry's adaptive image mapper.
        for key in image.keys():atlas[key]=image[key]
        atlas['h1_volume_source']=relative
    coord=g.node('ShaderNodeTexCoord','Object-space volume coordinates').outputs['Object']
    units=g.node('ShaderNodeAttribute','Scene length units');units.attribute_type='VIEW_LAYER';units.attribute_name='unit_settings.scale_length'
    coord=g.scale('Object position in Halo units',coord,g.math('Meters to Halo units','DIVIDE',units.outputs['Fac'],3.048))
    scale=g.control(shader.tag.root(),path[:-1]+['noise map scale'])
    coord=g.scale('Noise scale',coord,g.zero_default('Default noise scale',scale))
    seconds=g.node('GeometryNodeInputSceneTime','Scene Time').outputs['Seconds']
    period=g.control(shader.tag.root(),path[:-1]+['animation period'])
    time=g.math('Noise animation time','DIVIDE',seconds,g.zero_default('Default noise period',period))
    direction=g.xyz('Noise direction',*[g.control(shader.tag.root(),path[:-1]+['animation direction'],i) for i in range(3)])
    coord=g.vec('Animated noise position','ADD',coord,g.scale('Noise scroll',direction,time))
    separate=g.node('ShaderNodeSeparateXYZ','Volume XYZ');g.put(separate.inputs[0],coord)
    xyz=[g.math('Wrapped '+str(i),'FRACT',s) for i,s in enumerate(separate.outputs)]
    z=g.math('Slice centered Z','SUBTRACT',g.math('Slice Z','MULTIPLY',xyz[2],d),.5)
    base=g.math('Lower slice','FLOOR',z);weight=g.math('Slice interpolation','FRACT',z)
    u=g.math('Atlas U','DIVIDE',g.math('Gutter U','ADD',g.math('Image U','MULTIPLY',xyz[0],w),1),w+2)
    samples=[]
    for j in range(2):
        idx=g.math('Wrapped slice '+str(j),'FLOORED_MODULO',g.math('Slice '+str(j),'ADD',base,j),d)
        idx=g.math('Top down slice '+str(j),'SUBTRACT',d-1,idx)
        v=g.math('Atlas V '+str(j),'DIVIDE',g.math('Slice V '+str(j),'ADD',g.math('Slice origin '+str(j),'MULTIPLY',idx,h+2),g.math('Gutter V '+str(j),'ADD',g.math('Image V '+str(j),'MULTIPLY',xyz[1],h),1)),(h+2)*d)
        n=g.node('ShaderNodeTexImage','Noise volume slice '+str(j));n.image=atlas;n['h1_bitmap_binding']=json.dumps(path)
        n['h1_bitmap_reference']=relative;n.extension='EXTEND';g.put(n.inputs['Vector'],g.xyz('Atlas coordinate '+str(j),u,v));samples.append(n)
    return (g.mix('Volume RGB interpolation',samples[0].outputs['Color'],samples[1].outputs['Color'],weight,True),
            g.mix('Volume alpha interpolation',samples[0].outputs['Alpha'],samples[1].outputs['Alpha'],weight))

def import_shader(shader,material,resources,bitmap_to_image,reference,warning):
    kind=shader.system_path.suffix[1:].lower();resource=resources('h1_nodes','foundry_h1.'+kind)
    if resource is None:raise ValueError('Missing H1 node resource: '+kind)
    material.use_nodes=True;tree=material.node_tree;tree.nodes.clear();g=MaterialGraph(tree)
    out=g.node('ShaderNodeOutputMaterial','Material Output');out.location=(450,0)
    group=g.node('ShaderNodeGroup',kind);group.node_tree=resource;tree.links.new(group.outputs['Shader'],out.inputs['Surface'])
    root=shader.tag.root();group['h1_tag_snapshot']=json.dumps(snapshot(root,kind))
    bindings=json.loads(resource['h1_socket_bindings']);by_path={};images={};mapblock=None
    if 'chicago' in kind:
        mapblock='4 stage maps' if kind.endswith('extended') else 'maps'
        if kind.endswith('extended') and not len(resolve(root,[mapblock]).as_block()):mapblock='2 stage maps'
        group['h1_chicago_map_block']=mapblock
    def actual(path):
        return [mapblock,*path[1:]] if mapblock and path[0]=='4 stage maps' else path
    for identifier,binding in bindings.items():
        path=actual(binding['path']);socket=group.inputs[identifier];role=binding.get('role');by_path.setdefault(tuple(path),{})[role or 'value']=socket
        if role=='enabled':socket.default_value=path[1]<len(resolve(root,[path[0]]).as_block());continue
        try:field=resolve(root,path)
        except IndexError:continue
        if role and role.startswith('bitmap'):continue
        if role=='alpha':continue
        if binding.get('flag'):value=field.get_flag(binding['flag'])
        elif binding.get('enum'):value=binding['enum'][field.options().current]
        else:
            value=field.value
            if hasattr(value,'red'):value=(value.red,value.green,value.blue,1)
        socket.default_value=value
    material.surface_render_method='BLENDED'
    for i,(path,ports) in enumerate(by_path.items()):
        role=next((r for r in ports if r.startswith('bitmap')),None)
        if role is None:continue
        try:field=resolve(root,path)
        except IndexError:continue
        value=field.value
        if not value or not value[1]:continue
        owner=resolve(root,list(path[:-1])).as_struct() if path[:-1] else root
        ref=reference(shader,owner,path[-1]);result=bitmap_to_image(ref.Filename,shader.always_extract_bitmaps)
        if result.image is None:raise ValueError('Failed to extract '+value[1])
        g.section(' / '.join(map(str,path)),-1500,-i*1900)
        if role=='bitmap_volume':
            color,alpha=volume_sample(shader,g,result,list(path));g.put(ports[role],color)
            if 'alpha' in ports:g.put(ports['alpha'],alpha)
            continue
        n=texture(g,result,list(path),role);images[path]=n;g.put(ports[role],n.outputs['Color'])
        if kind=='shader_transparent_water' and path==('properties','base map'):
            n.extension='EXTEND'
        if 'alpha' in ports and n.outputs.get('Alpha'):g.put(ports['alpha'],n.outputs['Alpha'])
        shader._setup_sequence_driver(tree,n,result.sequence_length)
        if 'chicago' in kind:
            row=list(path[:2]);props=resolve(root,['properties']).as_struct();flags=props.field('flags')
            n.interpolation='Closest' if resolve(root,row+['flags']).get_flag('unfiltered') else 'Linear'
            if not result.cubemap and any(resolve(root,row+['flags']).get_flag(a+' clamped') for a in ('u','v')):n.extension='EXTEND'
            g.put(n.inputs['Vector'],chicago_vector(shader,g,row,props,flags,path[1],resources))
        elif not result.cubemap:
            uv=g.node('ShaderNodeTexCoord','UV coordinates').outputs['Generated' if shader.generated_uvs else 'UV']
            scale_path=list(path[:-1])+[path[-1]+' scale']
            try:resolve(root,scale_path)
            except KeyError:scale_path=None
            if scale_path:uv=g.scale('Tag texture scale',uv,g.zero_default('Scale zero means one',g.control(root,scale_path)))
            g.put(n.inputs['Vector'],uv)
    # Resolve reflection directions after all bump/ripple textures are available.
    for path,n in images.items():
        if n.type!='TEX_ENVIRONMENT':continue
        if 'chicago' in kind:continue
        g.section('Cubemap reflection coordinates',-2700,0)
        bump=images.get(('reflection','bump map')) or images.get(('ripples','maps'))
        mode=group.inputs.get('reflection type');mask=group.inputs.get('bump map is specular mask')
        mode_value=None
        if mode:
            modes=['bumped cube map','flat cube map','dynamic mirror'];mode_value=modes.index(mode.default_value)
            if mode_value==2:warning('H1 dynamic mirror uses the tag cubemap as a preview; planar scene capture is unavailable')
        g.put(n.inputs['Vector'],reflection_vector(g,bump.outputs['Color'] if bump else None,mode_value,bool(mask.default_value) if mask else None))
    if kind=='shader_transparent_water':setup_ripples(shader,g,group,images,bitmap_to_image,reference)
    if kind=='shader_transparent_meter':
        image=images.get(('properties','map'))
        if image:image.interpolation='Closest' if resolve(root,['properties','flags']).get_flag('unfiltered') else 'Linear'
    if 'chicago' in kind:
        # Destination framebuffer color is unavailable; the group records the limitation.
        if len(resolve(root,['properties','extra layers']).as_block()):warning('H1 extra shader layers are preserved but not composited in the material preview')
    return True

def setup_ripples(shader,g,group,images,bitmap_to_image,reference):
    """Animate the tag's ripple layers; CPU render-target/mip convolution is approximate."""
    root=shader.tag.root();block=resolve(root,['ripples','ripples']).as_block();source=images.get(('ripples','maps'))
    if source is None or not len(block):return
    g.section('Animated ripple layers',-3900,-2100)
    tex=g.node('ShaderNodeTexCoord','Ripple UV').outputs['UV'];seconds=g.node('GeometryNodeInputSceneTime','Scene Time').outputs['Seconds']
    scale=g.zero_default('Ripple scale zero means one',g.control(root,['ripples','scale']))
    total=(0,0,0)
    for i,row in enumerate(block):
        path=['ripples','ripples',i]
        repeats=g.zero_default('Ripple repeats '+str(i),g.control(root,path+['map repeats']))
        uv=g.scale('Ripple repeat '+str(i),tex,g.math('Total ripple scale '+str(i),'MULTIPLY',scale,repeats))
        angle=g.math('Ripple angle '+str(i),'ADD',g.control(root,['ripples','animation angle']),g.control(root,path+['animation angle']))
        velocity=g.math('Ripple speed '+str(i),'ADD',g.control(root,['ripples','animation velocity']),g.control(root,path+['animation velocity']))
        travel=g.math('Ripple distance '+str(i),'MULTIPLY',velocity,seconds)
        x=g.math('Ripple U scroll '+str(i),'ADD',g.control(root,path+['map offset'],0),g.math('Ripple U velocity '+str(i),'MULTIPLY',travel,g.math('Cos angle '+str(i),'COSINE',angle)))
        y=g.math('Ripple V scroll '+str(i),'ADD',g.control(root,path+['map offset'],1),g.math('Ripple V velocity '+str(i),'MULTIPLY',travel,g.math('Sin angle '+str(i),'SINE',angle)))
        uv=g.vec('Animated ripple UV '+str(i),'ADD',uv,g.xyz('Ripple offset '+str(i),x,y))
        ref=reference(shader,resolve(root,['ripples']).as_struct(),'maps')
        result=bitmap_to_image(ref.Filename,shader.always_extract_bitmaps,frame_index=int(row.field('map index').value))
        n=texture(g,result,['ripples','maps'],'bitmap_ripples');n.label='Ripple '+str(i);g.put(n.inputs['Vector'],uv)
        normal=g.vec('Signed ripple '+str(i),'SUBTRACT',g.scale('Twice ripple '+str(i),n.outputs['Color'],2),(1,1,1))
        total=g.vec('Ripple sum '+str(i),'ADD',total,g.scale('Ripple contribution '+str(i),normal,g.control(root,path+['contribution factor'])))
    normal=g.vec('Normalized ripple sum','NORMALIZE',total)
    color=g.scale('Encoded ripple normal',g.vec('Ripple normal bias','ADD',normal,(1,1,1)),.5)
    g.put(group.inputs['ripples maps'],color)
    # Both visible reflection and cube lookup must consume the same normal.
    for n in g.tree.nodes:
        if n.type=='NORMAL_MAP' and n.name.startswith('DirectX cubemap normal'):g.put(n.inputs['Color'],color)

def write_shader(shader):
    group=shader.group_node;kind=shader.system_path.suffix[1:].lower()
    if group is None or group.node_tree.get('h1_shader_type')!=kind:
        raise ValueError(f'{kind} export requires its matching H1 shader group at the material output')
    root=shader.tag.root()
    if group.get('h1_tag_snapshot'):restore(root,kind,json.loads(group['h1_tag_snapshot']))
    bindings=json.loads(group.node_tree['h1_socket_bindings']);block=group.get('h1_chicago_map_block','4 stage maps' if kind.endswith('extended') else 'maps')
    def actual(path):return [block,*path[1:]] if path[0]=='4 stage maps' else path
    enabled=[(actual(b['path']),bool(group.inputs[k].default_value)) for k,b in bindings.items() if b.get('role')=='enabled']
    if enabled:
        count=max((p[1]+1 for p,on in enabled if on),default=0);rows=resolve(root,[block]).as_block()
        if count==0:raise ValueError('Chicago shaders require at least one enabled map')
        if any(not on for p,on in enabled if p[1]<count):raise ValueError('Chicago maps must be contiguous; only disable trailing maps')
        while len(rows)>count:rows.delete(len(rows)-1)
        while len(rows)<count:rows.add()
    nodes=shader.blender_material.node_tree.nodes
    def retained_map(path):
        # Disabling trailing map sockets removes tag rows, while their texture
        # and animation nodes may remain in the material for later reuse.
        return (path[0] not in {'maps','4 stage maps','2 stage maps'} or
                path[1]<len(resolve(root,[path[0]]).as_block()))
    def linked_images(socket):
        pending=[l.from_node for l in socket.links];seen=set()
        while pending:
            n=pending.pop()
            if n in seen:continue
            seen.add(n)
            if n.type in {'TEX_IMAGE','TEX_ENVIRONMENT'}:yield n
            else:pending.extend(l.from_node for s in n.inputs for l in s.links)
    for identifier,binding in bindings.items():
        path=actual(binding['path']);role=binding.get('role');s=group.inputs[identifier]
        if role in {'alpha','enabled'}:continue
        try:field=resolve(root,path)
        except IndexError:continue
        if role and role.startswith('bitmap'):
            textures=list(linked_images(s))
            if not textures:
                # Retain typed empty references exactly; clear an actual map
                # when its texture was deliberately disconnected.
                if field.value and field.value[1]:field.set(None)
                continue
            tex=textures[0];relative=tex.get('h1_bitmap_reference') or tex.image.get('h1_volume_source')
            owner=resolve(root,path[:-1]).as_struct()
            shader.set_reference(owner,path[-1],relative+'.bitmap' if relative else shader._get_bitmap_path(tex))
        elif binding.get('flag'):field.set_flag(binding['flag'],bool(s.default_value))
        elif binding.get('enum'):field.set(binding['enum'].index(s.default_value))
        else:
            if s.is_linked:raise ValueError(f'Animated {s.name} cannot be written as a static tag value')
            set_field(field,list(s.default_value) if s.type in {'RGBA','VECTOR'} else s.default_value)
    for n in nodes:
        if n.get('h1_value_binding'):
            b=json.loads(n['h1_value_binding'])
            if not retained_map(b['path']):continue
            field=resolve(root,b['path']);value=n.outputs[0].default_value
            if b['component'] is not None:
                old=field.value;keys=('x','y','z') if hasattr(old,'x') else ('i','j','k');v=[getattr(old,k) for k in keys if hasattr(old,k)];v[b['component']]=value;value=v
            if isinstance(field.value,int):value=int(value)
            set_field(field,value)
        if n.get('h1_animation_binding'):
            b=json.loads(n['h1_animation_binding']);path=b['path'];axis=b['axis']
            if not retained_map(path):continue
            field=resolve(root,path+[axis+' animation function']);names=list(field.options().names)
            field.set(names.index(n.inputs['Animation Function'].default_value))
            for suffix in ('Period','Phase'):resolve(root,path+[axis+' animation '+suffix.lower()]).set(n.inputs['Animation '+suffix].default_value)
        if n.get('h1_chicago_vector_path'):
            row=json.loads(n['h1_chicago_vector_path'])
            if not retained_map(row):continue
            for name,port in [('map u scale','map u-scale'),('map v scale','map v-scale')]:resolve(root,row+['parameters',name]).set(n.inputs[port].default_value)
            for axis in ('u','v'):resolve(root,row+['flags']).set_flag(axis+' clamped',n.inputs[axis+' clamped'].default_value)
            if row[1]==0:
                from .halo1_generic_io import FIRST_TYPES
                resolve(root,['properties','first map type']).set(FIRST_TYPES.index(n.inputs['first map type'].default_value))
                resolve(root,['properties','flags']).set_flag('first map is in screenspace',n.inputs['first map is in screenspace'].default_value)
        if n.type in {'TEX_IMAGE','TEX_ENVIRONMENT'} and n.get('h1_bitmap_binding'):
            p=json.loads(n['h1_bitmap_binding'])
            if p[0] in {'maps','4 stage maps','2 stage maps'}:
                try:resolve(root,p[:2]+['flags']).set_flag('unfiltered',n.interpolation=='Closest')
                except IndexError:pass
            elif kind=='shader_transparent_meter':resolve(root,['properties','flags']).set_flag('unfiltered',n.interpolation=='Closest')
    shader.tag_has_changes=True
