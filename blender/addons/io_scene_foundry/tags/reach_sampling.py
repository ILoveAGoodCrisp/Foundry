"""Reach dependent samples; authored images/mappings remain exportable."""
import math
import bpy
from .. import utils
from .halo3_specialized_io import _math, _value
from .halo3_odst_io import (_put, _vector, _xyz, _mapping, _scale, _copy_sample,
    _tangent_view, _remember, _texture, _set_coordinates)
from .halo3_sampling import setup_parallax, setup_scope_blur, base_uv

class _Helpers:
    """Reuse identical sampler plumbing with Reach's own formula resources."""
    def __init__(self,shader):self.shader=shader
    def __getattr__(self,name):return getattr(self.shader,name)
    def _add_group_node(self,tree,nodes,name):
        names={'.H3 parallax vector':'.Reach parallax vector',
               '.ODST window intersection':'.Reach window intersection',
               'foundry_h3odst - cubemap reflector':'foundry_reach - cubemap reflector'}
        return self.shader._add_group_node(tree,nodes,names.get(name,name))

def _copy_ports(tree,root,helper):
    for port in helper.inputs:
        origin=root.inputs.get(port.name)
        if origin is None:origin=root.inputs.get(port.name+'.rgb')
        if origin is not None:_put(tree,port,_value(origin))

def _flat(shader,tree,root):
    texture=_texture(root,'flat_environment_map')
    if texture is None:return
    reflector=next((n for n in tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.name.startswith('foundry_reach - cubemap reflector')),None)
    if reflector is None:
        reflector=shader._add_group_node(tree,tree.nodes,'foundry_reach - cubemap reflector');_copy_ports(tree,root,reflector)
    vector=shader._add_group_node(tree,tree.nodes,'.Reach flat environment vector');_copy_ports(tree,root,vector)
    tree.links.new(reflector.outputs['Vector'],vector.inputs['Reflection']);tree.links.new(vector.outputs['UV'],texture.inputs['Vector'])

def _fur(shader,tree,root):
    texture=_texture(root,'fur_hairs_map')
    if texture is None:return
    _remember(root,texture,'fur_hairs_map');mapping=_mapping(texture)
    if not texture.inputs['Vector'].is_linked:tree.links.new(base_uv(tree),texture.inputs['Vector'])
    base=texture.inputs['Vector'].links[0].from_socket
    requested=max(1,int(root.inputs['layers_of_4'].default_value))*4;count=min(requested,128)
    view=_tangent_view(tree);parts=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(view,parts.inputs[0])
    shear=_xyz(tree,(_value(root.inputs['fur_shear_x']),_value(root.inputs['fur_shear_y']),0),'Fur shear')
    view=_vector(tree,'NORMALIZE',_vector(tree,'SUBTRACT',view,_vector(tree,'SCALE',shear,parts.outputs['Z'])))
    aspect=_xyz(tree,(_value(root.inputs['texcoord_aspect_ratio']),1,0),'Fur UV aspect')
    offset=_vector(tree,'SCALE',_vector(tree,'MULTIPLY',view,_vector(tree,'MULTIPLY',_scale(tree,mapping),aspect)),_math(tree,'DIVIDE',_value(root.inputs['layer_depth']),requested,'Fur layer depth'))
    rgb=alpha=None
    for index in range(count):
        # Keep the original sample unmoved for its authored transform export.
        sample=_copy_sample(tree,texture,'Fur layer '+str(index))
        delta=_math(tree,'SUBTRACT',_math(tree,'MULTIPLY',_value(root.inputs['fur_fix']),requested,'Fur fixed base'),index,'Fur layer position')
        tree.links.new(_vector(tree,'ADD',base,_vector(tree,'SCALE',offset,delta)),sample.inputs['Vector'])
        weight=_math(tree,'DIVIDE',_math(tree,'POWER',_value(root.inputs['depth_darken']),index,'Fur depth attenuation'),requested,'Fur layer average')
        color=_vector(tree,'SCALE',sample.outputs['Color'],weight);a=_math(tree,'MULTIPLY',sample.outputs['Alpha'],weight,'Fur alpha sample')
        rgb=color if rgb is None else _vector(tree,'ADD',rgb,color)
        alpha=a if alpha is None else _math(tree,'ADD',alpha,a,'Fur accumulated alpha')
    # Zero-weight original image keeps bitmap/transform ownership in the graph.
    rgb=_vector(tree,'ADD',rgb,_vector(tree,'SCALE',texture.outputs['Color'],0))
    tree.links.new(rgb,root.inputs['fur_hairs_map.rgb']);tree.links.new(alpha,root.inputs['fur_hairs_map.a'])
    root['reach_fur_samples']=count
    if requested>128 or root.inputs['layers_of_4'].is_linked:utils.print_warning('Reach fur preview uses up to 128 fixed samples; reimport after layer-count changes.')

def _screen(shader,tree,root,selected):
    coord=tree.nodes.new('ShaderNodeTexCoord');parts=tree.nodes.new('ShaderNodeSeparateXYZ');tree.links.new(coord.outputs['Window'],parts.inputs[0])
    window=_xyz(tree,(parts.outputs['X'],_math(tree,'SUBTRACT',1,parts.outputs['Y'],'Screen origin at top'),0),'Screen UV')
    render=bpy.context.scene.render
    pixel=_vector(tree,'MULTIPLY',window,(render.resolution_x*render.resolution_percentage/100,render.resolution_y*render.resolution_percentage/100,0),'Screen pixel coordinates')
    warp=_texture(root,'warp_map')
    if warp and selected.get('warp')!='none':
        _set_coordinates(tree,warp,pixel if selected['warp']=='pixel_space' else window)
        amount=_value(root.inputs['warp_amount'])
        delta=_vector(tree,'SCALE',_vector(tree,'MULTIPLY',warp.outputs['Color'],(1,1,0)),amount)
        # Both modes offset both coordinate domains; the option only selects
        # which domain samples the warp bitmap (screen.fx apply_warp).
        window=_vector(tree,'ADD',window,delta)
        pixel=_vector(tree,'ADD',pixel,_vector(tree,'MULTIPLY',delta,(render.resolution_x*render.resolution_percentage/100,render.resolution_y*render.resolution_percentage/100,0)))
    mode=selected.get('base','');base=_texture(root,'base_map');palette=_texture(root,'palette')
    if base:_set_coordinates(tree,base,pixel if mode=='single_pixel_space' else window)
    normal=_texture(root,'normal_map')
    if normal and palette and mode.startswith('normal_map'):
        _set_coordinates(tree,normal,window)
        geo=tree.nodes.new('ShaderNodeNewGeometry')
        value=_vector(tree,'DOT_PRODUCT',_vector(tree,'SUBTRACT',_vector(tree,'SCALE',normal.outputs['Color'],2),(1,1,1)),geo.outputs['Incoming'])
        _set_coordinates(tree,palette,_xyz(tree,(value,_value(root.inputs['palette_v']),0),'Screen edge palette'),False)
    detail=_texture(root,'detail_map_a');mask=_texture(root,'detail_mask_a');overlay=selected.get('overlay_a','')
    if detail:
        if overlay=='palette_lookup':
            source=palette if mode.startswith('normal_map') else base
            if source:
                color=source.outputs['Color']
                weights=[_value(root.inputs['intensity_color_'+axis]) for axis in ('u','v')]
                weights=[v if isinstance(v,bpy.types.NodeSocket) else tuple(v[:3]) for v in weights]
                lookup=_xyz(tree,tuple(_vector(tree,'DOT_PRODUCT',color,v) for v in weights)+(0,),'Screen intensity palette')
                _set_coordinates(tree,detail,lookup,False)
        else:_set_coordinates(tree,detail,pixel if overlay=='detail_pixel_space' else window)
    if mask:_set_coordinates(tree,mask,window)

def setup_sampling(shader,tree,root,selected):
    proxy=_Helpers(shader)
    if shader.system_path.suffix!='.shader_decal':setup_parallax(proxy,tree,root,selected)
    if shader.system_path.suffix == '.shader_water':
        from .reach_water import setup_water_sampling
        setup_water_sampling(shader, tree, root)
    shader._setup_h3_cubemap_reflector(tree,root)
    if selected.get('environment_mapping')=='from_flat_texture':_flat(shader,tree,root)
    if selected.get('self_illumination')=='scope_blur':setup_scope_blur(shader,tree,root)
    family=shader.system_path.suffix
    if selected.get('warp')=='from_texture' and family in {'.shader_fur','.shader_halogram'}:
        texture=_texture(root,'warp_map')
        if texture:
            offset=_vector(tree,'MULTIPLY',texture.outputs['Color'],_xyz(tree,(_value(root.inputs['warp_amount_x']),_value(root.inputs['warp_amount_y']),0),'Warp amount'))
            coords=_vector(tree,'ADD',base_uv(tree),offset,'Reach source warp')
            names={'fur_hairs_map','fur_tint_map','self_illum_map','self_illum_detail_map','overlay_map','overlay_detail_map','overlay_multiply_map'}
            for name in names:
                target=_texture(root,name)
                if target:_set_coordinates(tree,target,coords)
    from .halo3_odst_io import setup_multilayer,_custom_specular,_uv
    if selected.get('self_illumination')=='multilayer_additive':setup_multilayer(shader,tree,root)
    if selected.get('material_model')=='custom_specular':_custom_specular(proxy,tree,root)
    if selected.get('material_model')=='hair':
        for name in ('specular_map','specular_noise_map','specular_shift_map'):
            tex=_texture(root,name)
            if tex:_set_coordinates(tree,tex,_uv(tree),False)
    if family=='.shader_fur':_fur(shader,tree,root)
    if family=='.shader_screen':_screen(shader,tree,root,selected)
    if selected.get('self_illumination') in {'palettized_plasma','palettized_plasma_change_color','palettized_depth_fade'}:
        shader._setup_palette_vector_node(tree,root)
