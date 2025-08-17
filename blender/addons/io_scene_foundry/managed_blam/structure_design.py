

from collections import defaultdict
import math
from pathlib import Path
from statistics import mean
import bmesh
import bpy
from mathutils import Vector

from ..constants import WU_SCALAR

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
                render_materials.append(Material(element, [], False))
                
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
                        io_collection = io.get_collection(ig_collection, permitted_collections, self.tag_path.ShortName)
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
                
                verts = [Vector((*e.Fields[0].Data,)) * 100 for e in block_vertices.Elements]
                face_indices = [[i, i+1, i+2] for i in range(0, len(verts), 3)]
                mesh.from_pydata(vertices=verts, edges=[], faces=face_indices)

                ob = bpy.data.objects.new(name, mesh)
                ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_planar_fog_volume'
                ob.nwo.fog_appearance_tag = self.get_path_str(element.SelectField("Reference:appearance settings").Path)
                ob.nwo.fog_volume_depth = element.SelectField("Real:depth").Data
                
                apply_props_material(ob, "Fog")
                
                collection.objects.link(ob)
                objects.append(ob)
                
        if self.block_water_instances.Elements.Count > 0:
            print("Creating Water Physics Volumes")
            water_groups = [e.Fields[0].GetStringData() for e in self.block_water_groups.Elements]
            
            instance_groups = defaultdict(list)
            
            for element in self.block_water_instances.Elements:
                block_triangles = element.SelectField("Block:water debug triangles block")
                if block_triangles.Elements.Count < 1:
                    continue
                
                group_index = element.SelectField("ShortBlockIndex:group").Value
                if group_index > -1 and group_index < len(water_groups):
                    instance_groups[water_groups[group_index]].append(element)
                    
            for name, elements in instance_groups.items():
                # For each instance only get the triangle with the highest Z position
                # Depth is calculated by distance to the lowest Z vertex
                
                mesh = bpy.data.meshes.new(name)
                verts = []
                
                highest_z = -math.inf
                lowest_z = math.inf
                
                for element in elements:
                    block_triangles = element.SelectField("Block:water debug triangles block")
                    instance_verts = [Vector((*f.Data,)) * 100 for e in block_triangles.Elements for f in (e.Fields[0], e.Fields[1], e.Fields[2])]
                    # Last 3 verts are always the highest tri
                    highest_tri_z = -math.inf
                    triangle = None
                    for i in range(0, len(instance_verts), 3):
                        tri = [instance_verts[i], instance_verts[i+1], instance_verts[i+2]]
                        zs = tri[0].z, tri[1].z, tri[2].z
                        average = mean(zs)
                        if average > highest_tri_z:
                            highest_tri_z = average
                            triangle = tri

                    lowest_instance_z = highest_instance_z = max(*[v.z for v in triangle])
                    for v in instance_verts:
                        lowest_instance_z = min(v.z, lowest_instance_z)
                        
                    highest_z = max(highest_instance_z, highest_z)
                    lowest_z = min(lowest_instance_z, lowest_z)
                    
                    verts.extend(triangle)
                    
                face_indices = [[i, i+1, i+2] for i in range(0, len(verts), 3)]
                
                mesh.from_pydata(vertices=verts, edges=[], faces=face_indices)

                ob = bpy.data.objects.new(name, mesh)
                ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_water_surface'
                ob.nwo.water_volume_depth = (highest_z - lowest_z) / 100 * (1 / WU_SCALAR)
                direction, velocity = get_water_flow_direction_velocity(Vector((*element.SelectField("RealVector3d:flow velocity").Data,)))
                
                ob.nwo.water_volume_flow_direction = direction
                ob.nwo.water_volume_flow_velocity = velocity
                color = [utils.srgb_to_linear(c) for c in element.SelectField("RealArgbColor:fog color").Data]
                ob.nwo.water_volume_fog_color = color[1], color[2], color[3], color[0]
                ob.nwo.water_volume_fog_murkiness = element.SelectField("Real:fog murkiness").Data
                
                water_material = bpy.data.materials.get("WaterDirection")
                if water_material is None:
                    lib_blend = Path(utils.MATERIAL_RESOURCES, 'shared_nodes.blend')
                    with bpy.data.libraries.load(str(lib_blend), link=False) as (_, data_to):
                        data_to.materials = ["WaterDirection"]
                        
                    water_material = bpy.data.materials["WaterDirection"]
                        
                mesh.materials.append(water_material)
                
                collection.objects.link(ob)
                objects.append(ob)
                
        if self.block_soft_ceilings.Elements.Count > 0:
            print("Creating Map Boundaries")
            for element in self.block_soft_ceilings.Elements:
                triangles = element.SelectField("Block:soft ceiling triangles")
                if triangles.Elements.Count < 1:
                    continue
                
                name = element.SelectField("StringId:name").GetStringData()
                
                verts = [Vector((*f.Data,)) * 100 for e in triangles.Elements for f in (e.Fields[3], e.Fields[4], e.Fields[5])]
                
                mesh = bpy.data.meshes.new(name)
                face_indices = [[i, i+1, i+2] for i in range(0, len(verts), 3)]
                mesh.from_pydata(vertices=verts, edges=[], faces=face_indices)
                
                ob = bpy.data.objects.new(name, mesh)
                ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_boundary_surface'
                
                match element.SelectField("ShortEnum:type").Value:
                    case 0:
                        mesh.nwo.boundary_surface_type = 'SOFT_CEILING'
                        apply_props_material(ob, 'SoftCeiling')
                        if not name:
                            mesh.name = "soft_ceiling"
                            ob.name = mesh.name
                    case 1:
                        mesh.nwo.boundary_surface_type = 'SOFT_KILL'
                        apply_props_material(ob, 'SoftKill')
                        if not name:
                            mesh.name = "soft_kill"
                            ob.name = mesh.name
                    case 2:
                        mesh.nwo.boundary_surface_type = 'SLIP_SURFACE'
                        apply_props_material(ob, 'SlipSurface')
                        if not name:
                            mesh.name = "slip_surface"
                            ob.name = mesh.name
                        
                collection.objects.link(ob)
                objects.append(ob)

        return objects
    
def get_water_flow_direction_velocity(flow_velocity_vector):
    
    match bpy.context.scene.nwo.forward_direction:
        case 'y-':
            global_forward = Vector((0, -1, 0))
        case 'y':
            global_forward = Vector((0, 1, 0))
        case 'x-':
            global_forward = Vector((-1, 0, 0))
        case 'x':
            global_forward = Vector((1, 0, 0))
            
    # global_forward = Vector((1, 0, 0))
    
    
    global_up = Vector((0, 0, 1))

    velocity = flow_velocity_vector.length

    if velocity == 0:
        return 0.0, 0.0

    direction_vector = flow_velocity_vector.normalized()

    direction_flat = direction_vector - global_up * direction_vector.dot(global_up)
    direction_flat.normalize()

    dot = global_forward.dot(direction_flat)
    cross = global_forward.cross(direction_flat).dot(global_up)
    angle = math.atan2(cross, dot)

    return angle, velocity