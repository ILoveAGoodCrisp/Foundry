import bpy
import bmesh

from .. import utils

class ModelInstance:
    def __init__(self, model_tag):
        self.model_tag = None
        self.armature = None
        self.render_objects = []
        self.collision_objects = []
        self.physics_objects = []
        self.instance = None
        
    def from_armature(self, armature: bpy.types.Object):
        self.armature = armature
        
        for ob in self.armature.children_recursive:
            if ob.type != 'MESH':
                continue
            
            mesh_type = ob.nwo.mesh_type
            
            match mesh_type:
                case '_connected_geometry_mesh_type_default':
                    self.render_objects.append(ob)
                case '_connected_geometry_mesh_type_collision':
                    self.collision_objects.append(ob)
                case '_connected_geometry_mesh_type_physics':
                    self.physics_objects.append(ob)
                    
                    
    def map_model_materials(self):
        pass
    
    def to_instance(self):
        render_name = self.armature.name
        render_mesh = bpy.data.meshes.new(render_name)
        bm = bmesh.new()
        for ob in self.render_objects:
            bm.from_mesh(ob.data)

        bm.to_mesh(render_mesh)
        bm.free()
        
        render_ob = bpy.data.objects.new(render_name, render_mesh)
        
        render_ob.users_collection = self.armature.users_collection
        
        collision_name = f"{self.armature.name}_collision"
        collision_mesh = bpy.data.meshes.new(collision_name)
        
        bm = bmesh.new()
        for ob in self.collision_objects:
            bm.from_mesh(ob.data)

        bm.to_mesh(collision_mesh)
        bm.free()
        
        collision_ob = bpy.data.objects.new(collision_name, render_mesh)
        
        collision_ob.nwo.proxy_parent = render_ob.parent.data
        collision_ob.nwo.proxy_type = 'collision'
        proxy_scene = utils.get_foundry_storage_scene()
        proxy_scene.collection.objects.link(ob)
        
        render_mesh.nwo.proxy_collision = collision_ob
