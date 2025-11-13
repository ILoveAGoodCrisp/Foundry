from collections import defaultdict
from pathlib import Path
import bpy
import bmesh
from mathutils import Euler, Matrix, Vector
import numpy as np

from ..constants import WU_SCALAR

from ..managed_blam.physics_model import PhysicsTag

from ..managed_blam.material import MaterialTag
from ..managed_blam.model import ModelTag
from ..managed_blam.object import ObjectTag
from ..managed_blam.shader import ShaderTag

from .. import utils

class ModelInstance:
    def __init__(self, object_tag: str, variant: str, corinth: bool):
        self.object_tag = utils.relative_path(object_tag)
        self.name = Path(object_tag).with_suffix("").name
        if variant:
            self.name += f" [{variant}]"
        self.variant = variant
        self.render_objects = []
        self.collision_objects = []
        self.physics_objects = []
        self.other_objects = []
        self.instance = None
        self.corinth = corinth
        
    def _collect_objects(self, objects: list[bpy.types.Object]):
        for ob in objects:
            if ob.type != 'MESH':
                self.other_objects.append(ob)
                continue
            
            mesh_type = ob.nwo.mesh_type
            
            match mesh_type:
                case '_connected_geometry_mesh_type_default':
                    self.render_objects.append(ob)
                case '_connected_geometry_mesh_type_collision':
                    self.collision_objects.append(ob)
                case '_connected_geometry_mesh_type_physics':
                    self.physics_objects.append(ob)
                case _:
                    self.other_objects.append(ob)
        
    def from_objects(self, objects: list[bpy.types.Object]):
        self._collect_objects(objects)
                    
    def _map_materials_to_shaders(self):
        model_materials_map = {}
        materials_shader_map = {}
        phantom_materials = set()
        
        blender_materials = sorted({mat for ob in self.render_objects for mat in ob.data.materials}, key=lambda x: x.name)
        
        with ObjectTag(path=self.object_tag) as obj:
            if not obj.path_exists(obj.reference_model.Path):
                return materials_shader_map
            with ModelTag(path=obj.reference_model.Path) as model:
                
                if not model.path_exists(model.reference_render_model.Path):
                    return materials_shader_map
                
                for element in model.tag.SelectField("Block:model materials").Elements:
                    name = element.SelectField("material name").GetStringData()
                    global_material = element.SelectField("global material name").GetStringData()
                    
                    if not name:
                        continue
                    
                    if global_material:
                        model_materials_map[name] = global_material
                    else:
                        model_materials_map[name] = name
                        
                if model.path_exists(model.reference_physics_model.Path):
                    with PhysicsTag(path=model.reference_physics_model.Path) as physics:
                        for element in physics.block_materials.Elements:
                            
                            name = element.SelectField("name").GetStringData()
                            global_material = element.SelectField("global material name").GetStringData()
                            
                            if not name:
                                continue
                            
                            if element.SelectField("phantom type").Value > -1:
                                phantom_materials.add(name)
                                continue
                            
                            if global_material:
                                model_materials_map[name] = global_material
                            else:
                                model_materials_map[name] = name
                
                materials_model_map = defaultdict(list)
                for name, global_material in model_materials_map.items():
                    materials_model_map[global_material].append(name)
                
                for mat in blender_materials:
                    shader_path = utils.relative_path(mat.nwo.shader_path)
                    if not mat.nwo.shader_path or not Path(utils.get_tags_path(), shader_path).exists():
                        continue
                    
                    with ShaderTag(path=shader_path) as shader:
                        shader_material = shader.get_global_material()
                        if not shader_material:
                            continue
                            
                    name_list = materials_model_map.get(shader_material)
                    if name_list is None:
                        continue
                    
                    for name in name_list:
                        materials_shader_map[name] = mat
                    
        return materials_shader_map, phantom_materials
    
    def _copy_props(self, new_ob, old_ob, do_materials=False):
        new_mesh = new_ob.data
        old_mesh = old_ob.data
        
        if do_materials:
            for mat in old_mesh.materials:
                new_mesh.materials.append(mat)
            
        for k, v in old_ob.items():
            if type(v).__name__ != 'IDPropertyGroup': # Blender why can't I do not isinstance(v, bpy.types.IDPropertyGroup) ???
                new_ob[k] = v
                new_ob.id_properties_ui(k).update(**old_ob.id_properties_ui(k).as_dict())
        
        for prop in old_mesh.nwo.face_props:
            copy_prop = new_mesh.nwo.face_props.add()
            for k, v in prop.items():
                copy_prop[k] = v
                
    def _global_materials_to_shaders_mesh(self, materials_shaders: dict, mesh: bpy.types.Mesh):
        attributes = []
        to_remove_props = []
        for idx, prop in enumerate(mesh.nwo.face_props):
            if prop.type != 'global_material':
                continue
            
            blender_material = materials_shaders.get(prop.global_material)
            if blender_material is None:
                if not self.corinth:
                    shader_name = f"bsp_{prop.global_material}.shader"
                    expected_shader_path = Path(utils.get_tags_path(), r"levels\reference\sound\shaders", shader_name)
                    if expected_shader_path.exists():
                        mat = bpy.data.materials.get(shader_name)
                        if mat is None:
                            mat = bpy.data.materials.new(shader_name)
                            mat.nwo.shader_path = utils.relative_path(expected_shader_path)
                        blender_material = mat
                        
            if blender_material is None:
                continue
            
            attribute = mesh.attributes.get(prop.attribute_name)
            if attribute is not None:
                attributes.append(attribute)
                to_remove_props.append(idx)
                mesh.materials.append(blender_material)
                
        material_indices = np.zeros(len(mesh.polygons), dtype=np.int32)
        for idx, attribute in enumerate(attributes):
            buffer = np.empty(len(mesh.polygons), dtype=np.int8)
            attribute.data.foreach_get("value", buffer)
            material_indices[buffer] = idx
            
        mesh.polygons.foreach_set("material_index", material_indices)
        
        for i in reversed(to_remove_props):
            utils.delete_face_prop(mesh, i)
        
    def _global_materials_to_shaders_object(self, materials_shaders: dict, ob: bpy.types.Object, global_material: str):
        blender_material = materials_shaders.get(global_material)
        if blender_material is None:
            if self.corinth:
                prop = utils.add_face_prop(ob.data, "global_material")
                prop.global_material = global_material
            else:
                shader_name = f"bsp_{global_material}.shader"
                expected_shader_path = Path(utils.get_tags_path(), r"levels\reference\sound\shaders", shader_name)
                if expected_shader_path.exists():
                    mat = bpy.data.materials.get(shader_name)
                    if mat is None:
                        mat = bpy.data.materials.new(shader_name)
                        mat.nwo.shader_path = utils.relative_path(expected_shader_path)
                        
                    blender_material = mat
                    
        if blender_material is not None:
            ob.data.materials.append(blender_material)
    
    def to_instance(self, collection: bpy.types.Collection):
        objects = []
        
        if not self.render_objects:
            utils.print_warning("No render objects")
            return objects
        
        materials_shaders, phantom_materials = self._map_materials_to_shaders()
        
        render_name = self.name
        render_mesh = bpy.data.meshes.new(render_name)
        render_ob = bpy.data.objects.new(render_name, render_mesh)
        bm = bmesh.new()
        for ob in self.render_objects:
            self._copy_props(render_ob, ob, True)
            bm.from_mesh(ob.data)

        bm.to_mesh(render_mesh)
        bm.free()
        
        utils.consolidate_face_attributes(render_mesh)
        
        collection.objects.link(render_ob)
        
        objects.append(render_ob)
        
        if self.collision_objects or self.physics_objects:
            proxy_scene = utils.get_foundry_storage_scene()
        
        collision_ob = None
        if self.collision_objects:
            collision_name = f"{self.name}_collision"
            collision_mesh = bpy.data.meshes.new(collision_name)
            collision_ob = bpy.data.objects.new(collision_name, collision_mesh)
            
            bm = bmesh.new()
            for ob in self.collision_objects:
                self._copy_props(collision_ob, ob)
                bm.from_mesh(ob.data)

            bm.to_mesh(collision_mesh)
            bm.free()
            
            # collision_ob.nwo.proxy_parent = render_ob.data
            collision_ob.nwo.proxy_type = 'collision'
            proxy_scene = utils.get_foundry_storage_scene()
            proxy_scene.collection.objects.link(collision_ob)
            
            render_mesh.nwo.proxy_collision = collision_ob
            objects.append(collision_ob)
            utils.consolidate_face_attributes(collision_mesh)
            self._global_materials_to_shaders_mesh(materials_shaders, collision_mesh)
            
        else:
            render_ob.nwo.poop_render_only = True
            
        for idx, ob in enumerate(self.physics_objects):
            if ob.nwo.global_material in phantom_materials:
                continue
            
            physics_name = f"{self.name}_physics{idx}"
            physics_mesh = bpy.data.meshes.new(physics_name)
            physics_ob = bpy.data.objects.new(physics_name, physics_mesh)
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.to_mesh(physics_mesh)
            bm.free()
            
            physics_mesh.transform(ob.matrix_world)
                    
            # physics_ob.nwo.proxy_parent = render_ob.data
            physics_ob.nwo.proxy_type = 'physics'
            proxy_scene.collection.objects.link(physics_ob)
            setattr(render_ob.data.nwo, f"proxy_physics{idx}", physics_ob)
            objects.append(physics_ob)
            self._global_materials_to_shaders_object(materials_shaders, physics_ob, ob.nwo.global_material)
        
        self.instance = render_ob
        
        return objects
    
    def clean_up(self):
        to_remove = self.render_objects + self.collision_objects + self.physics_objects + self.other_objects
        redundant_collections = {coll for ob in to_remove for coll in ob.users_collection if coll}
        bpy.data.batch_remove(to_remove)
        redundant_collections = {coll for coll in redundant_collections if not coll.all_objects}
        bpy.data.batch_remove(redundant_collections)