

from pathlib import Path
import bmesh
import bpy
from mathutils import Vector

from .connected_geometry import CompressionBounds, Instance, InstanceDefinition, Material
from . import Tag
from .. import utils
from ..tools.property_apply import apply_props_material

class StructureDesignTag(Tag):
    tag_ext = 'structure_design'
    
    def _read_fields(self):
        self.block_soft_ceilings = self.tag.SelectField("Struct:physics[0]/Block:soft ceilings block")
        self.block_water_groups = self.tag.SelectField("Struct:physics[0]/Block:water groups block")
        self.block_water_instances = self.tag.SelectField("Struct:physics[0]/Block:water instances block")
        self.block_planar_fogs = self.tag.SelectField("Struct:planar fog set[0]/Block:planar fogs")
        self.block_meshes = self.tag.SelectField("Struct:render geometry[0]/Block:meshes")
        self.block_compression_info = self.tag.SelectField("Struct:render geometry[0]/Block:compression info")
        self.block_per_mesh_temporary = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh temporary")
        self.block_definitions = self.tag.SelectField("Block:instanced geometries definitions")
        self.block_instances = self.tag.SelectField("Block:instanced geometry instances")
        self.block_materials = self.tag.SelectField("Block:materials")
        
    def to_blender(self, collection: bpy.types.Collection):
        
        objects = []
        
        if self.block_definitions.Elements.Count > 0:
            print("Creating Rain Blockers and Vertical Rain Sheets")
            # Rain blockers
            
            # Get all render materials
            render_materials = []
            for element in self.tag.SelectField("Block:materials").Elements:
                render_materials.append(Material(element, [], True))
                
            # Get all compression bounds
            bounds = []
            for element in self.block_compression_info.Elements:
                bounds.append(CompressionBounds(element))
                
            # Create RenderModel object
            render_model = self._GameRenderModel()
            
            # Get render geometry temp meshes block
            temp_meshes = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh temporary")
            meshes = self.tag.SelectField("Struct:render geometry[0]/Block:meshes")
            # Get all instance definitions
            if self.block_instances.Elements.Count > 0:
                instance_definitions = []
                print("Creating Instance Definitions")
                for element in self.block_definitions.Elements:
                    definition = InstanceDefinition(element, meshes, bounds, render_materials, [], True)
                    objects.extend(definition.create(render_model, temp_meshes))
                    instance_definitions.append(definition)
                
                # Create instanced geometries
            
                # poops = []
                print("Creating Instance Rain Blockers & Sheets")
                ig_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_instances")
                collection.children.link(ig_collection)
                # Keeping track of the collections we add in this bsp import
                # This avoids putting objects in collections that already existed prior to export
                # and therefore prevents incorrect bsp assignment
                permitted_collections = set()
                for element in self.block_instances.Elements:
                    io = Instance(element, instance_definitions)
                    if io.definition.blender_render or io.definition.blender_collision:
                        io_collection = io.get_collection(ig_collection, permitted_collections)
                        permitted_collections.add(io_collection)
                        ob = io.create()
                        if element.SelectField("flags").TestBit("vertical rain sheet"):
                            ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_poop_vertical_rain_sheet'
                        else:
                            ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_poop_rain_blocker'
                        objects.append(ob)
                        io_collection.objects.link(ob)
                        
        if self.block_planar_fogs.Elements.Count > 0:
            print("Creating Fog Sheets")
            for element in self.block_planar_fogs.Elements:
                block_vertices = element.SelectField("Block:vertices")
                if block_vertices.Elements.Count < 3:
                    continue
                
                name = element.SelectField("StringId:name").GetStringData()
                
                mesh = bpy.data.meshes.new(name)
                
                verts = [Vector((*e.Fields[0].Data,)) for e in block_vertices.Elements]
                face_indices = [[i, i+1, i+2] for i in range(0, len(verts), 3)]
                mesh.from_pydata(vertices=verts, edges=[], faces=face_indices)

                ob = bpy.data.objects.new(name, mesh)
                ob.nwo.data.mesh_type = '_connected_geometry_mesh_type_planar_fog_volume'
                ob.nwo.fog_appearance_tag = self.get_path_str(element.SelectField("Reference:appearance settings").Path)
                ob.nwo.fog_volume_depth = element.SelectField("Real:depth").Data
                
                apply_props_material(ob, "Fog")
                
                collection.objects.link(ob)
                objects.append(ob)
                
        if self.block_water_instances.Count > 0:
            print("Creating Water Physics Volumes")
            water_groups = [e.Fields[0].GetStringData() for e in self.block_water_groups.Elements]
            
            for element in self.block_water_instances.Elements:
                group_index = element.SelectField("ShortBlockIndex:group").Value
                if group_index > -1 and group_index < len(water_groups):
                    name = water_groups[group_index]
                else:
                    name = "water_physics"
                    
            mesh = bpy.data.meshes.new(name)
            
            verts = [Vector((*f.Data,)) for e in block_vertices.Elements for f in (e.Fields[0], e.Fields[1], e.Fields[2])]
            face_indices = [[i, i+1, i+2] for i in range(0, len(verts), 3)]
            
            mesh.from_pydata(vertices=verts, edges=[], faces=face_indices)

            ob = bpy.data.objects.new(name, mesh)
            ob.nwo.data.mesh_type = '_connected_geometry_mesh_type_water_surface'
            ob.nwo.water_volume_depth = element.SelectField("Real:depth").Data
            ob.nwo.water_volume_flow_direction = element.SelectField("")
            
            apply_props_material(ob, "WaterVolume")
            
            collection.objects.link(ob)
            objects.append(ob)
                    
                
                
                
        return objects