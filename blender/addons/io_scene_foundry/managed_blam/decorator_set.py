

from pathlib import Path
from typing import cast
import bpy

from .bitmap import BitmapTag
from .. import utils

from .render_model import RenderModelTag

from ..managed_blam import Tag

class DecoratorType:
    def __init__(self):
        self.render_model_instance_index = -1
        self.decorator_type_index = -1
        self.decorator_type_name = ""

class DecoratorSetTag(Tag):
    tag_ext = 'decorator_set'
    
    def _read_fields(self):
        self.reference_base = self.tag.SelectField("Reference:Base")
        self.reference_lod2 = self.tag.SelectField("Reference:Lod2")
        self.reference_lod3 = self.tag.SelectField("Reference:Lod3")
        self.reference_lod4 = self.tag.SelectField("Reference:Lod4")
        self.reference_texture = self.tag.SelectField("Reference:texture")
        self.decorator_types = self.tag.SelectField("Block:decorator types")
        self.model_instances = self.tag.SelectField("Block:render model instance names")
        
    def get_decorator_types(self) -> list[DecoratorType]:
        decorator_types = []
        instance_count = self.model_instances.Elements.Count
        for element in self.decorator_types.Elements:
            value = element.SelectField("LongBlockIndex:mesh").Value
            if value > -1 and value < instance_count:
                name = self.model_instances.Elements[value].Fields[0].GetStringData()
                if name:
                    dec_type = DecoratorType()
                    dec_type.render_model_instance_index = value
                    dec_type.decorator_type_index = element.ElementIndex
                    dec_type.decorator_type_name = name
                    decorator_types.append(dec_type)
                    
        return decorator_types
        
    def to_blender(self, collection, get_material=False, always_extract_bitmaps=False, single_type=None, highest_lod_only=False, only_single_type=False):
        base = self.get_path_str(self.reference_base.Path, True)
        lod2 = self.get_path_str(self.reference_lod2.Path, True)
        lod3 = self.get_path_str(self.reference_lod3.Path, True)
        lod4 = self.get_path_str(self.reference_lod4.Path, True)
        texture = self.get_path_str(self.reference_texture.Path, True)
        
        all_obs = []
        found_highest_lod = False
        single_type_instance_index = None
        
        types = self.get_decorator_types()
        for t in types:
            print(t.decorator_type_name, t.decorator_type_index, t.render_model_instance_index)
        if single_type is not None:
            for t in types:
                if t.decorator_type_name == single_type:
                    single_type_instance_index = t.render_model_instance_index
                    break
                
        if single_type_instance_index is None and only_single_type and types:
            single_type_instance_index = types[0].decorator_type_index
        
        if base and Path(base).exists():
            base_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_high")
            collection.children.link(base_collection)
            with RenderModelTag(path=base) as base_render:
                base_obs = base_render.to_blend_objects(collection, True, False, base_collection, no_armature=True, specific_io_index=single_type_instance_index)
                for ob in base_obs:
                    ob.nwo.decorator_lod = 'high'
                    utils.unlink(ob)
                    base_collection.objects.link(ob)
                    
                all_obs.extend(base_obs)
                found_highest_lod = True
        
        if not highest_lod_only or not found_highest_lod:
            if lod2 and Path(lod2).exists():
                lod2_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_medium")
                collection.children.link(lod2_collection)
                with RenderModelTag(path=lod2) as lod2_render:
                    lod2_obs = lod2_render.to_blend_objects(collection, True, False, lod2_collection, no_armature=True, specific_io_index=single_type_instance_index)
                    for ob in lod2_obs:
                        ob.nwo.decorator_lod = 'medium'
                        utils.unlink(ob)
                        lod2_collection.objects.link(ob)
                        
                    all_obs.extend(lod2_obs)
                    found_highest_lod = True
        
        if not highest_lod_only or not found_highest_lod:
            if lod3 and Path(lod3).exists():
                lod3_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_low")
                collection.children.link(lod3_collection)
                with RenderModelTag(path=lod3) as lod3_render:
                    lod3_obs = lod3_render.to_blend_objects(collection, True, False, lod3_collection, no_armature=True, specific_io_index=single_type_instance_index)
                    for ob in lod3_obs:
                        ob.nwo.decorator_lod = 'low'
                        utils.unlink(ob)
                        lod3_collection.objects.link(ob)
                    
                    all_obs.extend(lod3_obs)
                    found_highest_lod = True
        
        if not highest_lod_only or not found_highest_lod:
            if lod4 and Path(lod4).exists():
                lod4_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_ver_low")
                collection.children.link(lod4_collection)
                with RenderModelTag(path=lod4) as lod4_render:
                    lod4_obs = lod4_render.to_blend_objects(collection, True, False, lod4_collection, no_armature=True, specific_io_index=single_type_instance_index)
                    for ob in lod4_obs:
                        ob.nwo.decorator_lod = 'very_low'
                        utils.unlink(ob)
                        lod4_collection.objects.link(ob)
                        
                    all_obs.extend(lod4_obs)
                    found_highest_lod = True
        
        if texture and Path(texture).exists():
            
            name = Path(texture).with_suffix("").name
            mat = bpy.data.materials.get(name)
            if mat is None:
                mat = bpy.data.materials.new(name)
                mat.use_nodes = True
                if get_material:
                    tree = cast(bpy.types.NodeTree, mat.node_tree)
                    tree.nodes.clear()
                    node_image = tree.nodes.new(type="ShaderNodeTexImage")
                    
                    rel_path = utils.relative_path(texture)
                    
                    system_tiff_path = Path(self.data_dir, rel_path).with_suffix('.tiff')
                    alt_system_tiff_path = system_tiff_path.with_suffix(".tif")
                    with BitmapTag(path=texture) as bitmap:
                        curve = bitmap.tag.SelectField("Block:bitmaps[0]/CharEnum:curve").Value
                        for_normal = bitmap.used_as_normal_map()
                        if always_extract_bitmaps:
                            image_path = bitmap.save_to_tiff(for_normal)
                        else:
                            if system_tiff_path.exists():
                                image_path = str(system_tiff_path)
                            elif alt_system_tiff_path.exists():
                                image_path = str(alt_system_tiff_path)
                            else:
                                image_path = bitmap.save_to_tiff(for_normal)
                                
                        image = bpy.data.images.load(filepath=image_path, check_existing=True)
                        image.nwo.filepath = utils.relative_path(image_path)
                        image.nwo.shader_type = bitmap.get_shader_type()

                        if for_normal or bitmap.tag_path.RelativePathWithExtension == r"shaders\default_bitmaps\bitmaps\default_detail.bitmap":
                            image.colorspace_settings.name = 'Non-Color'
                        elif curve == 3:
                            image.colorspace_settings.name = 'Linear Rec.709'
                            image.alpha_mode = 'CHANNEL_PACKED'
                        else:
                            image.colorspace_settings.name = 'sRGB'
                            image.alpha_mode = 'CHANNEL_PACKED'
                    
                    if image:
                        node_image.image = image
                    node_group = tree.nodes.new(type='ShaderNodeGroup')
                    node_group.node_tree = utils.add_node_from_resources("shared_nodes", "Decorator")
                    tree.links.new(input=node_group.inputs[0], output=node_image.outputs[0])
                    tree.links.new(input=node_group.inputs[1], output=node_image.outputs[1])
                    node_output = tree.nodes.new(type='ShaderNodeOutputMaterial')
                    tree.links.new(input=node_output.inputs[0], output=node_group.outputs[0])
                    render_shader = self.tag.SelectField("CharEnum:render shader").Value
                    if render_shader < 2 or render_shader > 3:
                        mat.surface_render_method = 'BLENDED'
            
            for ob in all_obs:
                ob.data.materials.clear()
                ob.data.materials.append(mat)
                
        return all_obs
    
    def from_blender(self):
        pass