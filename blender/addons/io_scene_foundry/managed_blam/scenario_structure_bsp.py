# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

import bmesh
import bpy
from mathutils import Vector

from .connected_geometry import BSPCollisionMaterial, Cluster, CompressionBounds, Instance, InstanceDefinition, Material, Mesh, Portal, StructureCollision
from ..utils import jstr
from ..managed_blam import Tag
from .. import utils

class ScenarioStructureBspTag(Tag):
    tag_ext = 'scenario_structure_bsp'
    
    def _read_fields(self):
        self.block_instances = self.tag.SelectField("instanced geometry instances")
        if self.corinth:
            self.block_prefabs = self.tag.SelectField("Block:external references")
            
        self.block_instance_definitions = self.tag.SelectField("Struct:resource interface[0]/Block:raw_resources[0]/Struct:raw_items[0]/Block:instanced geometries definitions")
    
    def write_prefabs(self, prefabs):
        if not self.corinth or (not prefabs and self.block_prefabs.Elements.Count == 0): return
        self.block_prefabs.RemoveAllElements()
        for prefab in prefabs:
            element = self.block_prefabs.AddElement()
            element.SelectField("prefab reference").Path = self._TagPath_from_string(prefab.reference)
            element.SelectField("name").SetStringData(prefab.name)
            element.SelectField("scale").SetStringData(prefab.scale)
            element.SelectField("forward").SetStringData(prefab.forward)
            element.SelectField("left").SetStringData(prefab.left)
            element.SelectField("up").SetStringData(prefab.up)
            element.SelectField("position").SetStringData(prefab.position)
            
            override_flags = element.SelectField("override flags")
            flags_mask = element.SelectField("instance flags Mask")
            policy_mask = element.SelectField("instance policy mask")
            
            nwo = prefab.props
            
            if nwo.prefab_lighting != "no_override":
                policy_mask.SetBit("override lightmapping policy", True)
                lighting = element.SelectField("override lightmapping policy")
                match nwo.prefab_lighting:
                    case "_connected_geometry_poop_lighting_per_pixel":
                        lighting.Value = 0
                    case "_connected_geometry_poop_lighting_per_vertex":
                        lighting.Value = 1
                    case "_connected_geometry_poop_lighting_single_probe":
                        lighting.Value = 2
                    case "_connected_geometry_poop_lighting_per_vertex_ao":
                        lighting.Value = 5
                        
            if nwo.prefab_lightmap_res > 0:
                policy_mask.SetBit("override lightmap resolution policy", True)
                element.SelectField("override lightmap resolution scale").SetStringData(str(nwo.prefab_lightmap_res))
                    
            if nwo.prefab_pathfinding != "no_override":
                policy_mask.SetBit("override pathfinding policy", True)
                pathfinding = element.SelectField("override pathfinding policy")
                match nwo.prefab_lighting:
                    case "_connected_poop_instance_pathfinding_policy_cutout":
                        pathfinding.Value = 0
                    case "_connected_poop_instance_pathfinding_policy_static":
                        pathfinding.Value = 1
                    case "_connected_poop_instance_pathfinding_policy_none":
                        pathfinding.Value = 2
                        
            if nwo.prefab_imposter_policy != "no_override":
                policy_mask.SetBit("override lmposter policy", True)
                imposter = element.SelectField("override imposter policy")
                match nwo.prefab_imposter_policy:
                    case "_connected_poop_instance_imposter_policy_polygon_default":
                        imposter.Value = 0
                    case "_connected_poop_instance_imposter_policy_polygon_high":
                        imposter.Value = 1
                    case "_connected_poop_instance_imposter_policy_card_default":
                        imposter.Value = 2
                    case "_connected_poop_instance_imposter_policy_card_high":
                        imposter.Value = 3
                    case "_connected_poop_instance_imposter_policy_never":
                        imposter.Value = 4
                if nwo.prefab_imposter_policy != "_connected_poop_instance_imposter_policy_never":
                    if nwo.prefab_imposter_brightness > 0:
                        policy_mask.SetBit("override imposter brightness", True)
                        element.SelectField("override imposter brightness").SetStringData(jstr(nwo.prefab_imposter_brightness))
                        
                    if not nwo.prefab_imposter_transition_distance_auto:
                        policy_mask.SetBit("override imposter transition distance policy", True)
                        element.SelectField("override imposter transition distance").SetStringData(jstr(nwo.prefab_imposter_transition_distance))
                        
            if nwo.prefab_streaming_priority != "no_override":
                streaming = element.SelectField("override streaming priority")
                match nwo.prefab_streaming_priority:
                    case "_connected_geometry_poop_streamingpriority_default":
                        streaming.Value = 0
                    case "_connected_geometry_poop_streamingpriority_higher":
                        streaming.Value = 1
                    case "_connected_geometry_poop_streamingpriority_highest":
                        streaming.Value = 2
            
            if nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_only':
                override_flags.SetBit("cinema only", True)
                flags_mask.SetBit("cinema only", True)
            elif nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_exclude':
                override_flags.SetBit("exclude from cinema", True)
                flags_mask.SetBit("exclude from cinema", True)
                
            if nwo.prefab_render_only:
                override_flags.SetBit("render only", True)
                flags_mask.SetBit("render only", True)
            if nwo.prefab_does_not_block_aoe:
                override_flags.SetBit("does not block aoe damage", True)
                flags_mask.SetBit("does not block aoe damage", True)
            if nwo.prefab_excluded_from_lightprobe:
                override_flags.SetBit("not in lightprobes", True)
                flags_mask.SetBit("not in lightprobes", True)
            if nwo.prefab_decal_spacing:
                override_flags.SetBit("decal spacing", True)
                flags_mask.SetBit("decal spacing", True)
            if nwo.prefab_remove_from_shadow_geometry:
                override_flags.SetBit("remove from shadow geometry", True)
                flags_mask.SetBit("remove from shadow geometry", True)
            if nwo.prefab_disallow_lighting_samples:
                override_flags.SetBit("disallow object lighting samples", True)
                flags_mask.SetBit("disallow object lighting samples", True)
            
        self.tag_has_changes = True
        
    def to_blend_objects(self, collection: bpy.types.Collection):
        objects = []
        self.collection = collection
        # Get all collision materials
        collision_materials = []
        for element in self.tag.SelectField("Block:collision materials").Elements:
            collision_materials.append(BSPCollisionMaterial(element))
            
        # Get all render materials
        render_materials = []
        for element in self.tag.SelectField("Block:materials").Elements:
            render_materials.append(Material(element))
            
        # Get all compression bounds
        bounds = []
        for element in self.tag.SelectField("Struct:render geometry[0]/Block:compression info"):
            bounds.append(CompressionBounds(element))
            
        # Create RenderModel object
        render_model = self._GameRenderModel()
        
        # Get render geometry temp meshes block
        temp_meshes = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh temporary")
        meshes = self.tag.SelectField("Struct:render geometry[0]/Block:meshes")
        # Get all instance definitions
        instance_definitions = []
        # print("Creating Instance Definitions")
        # for element in self.block_instance_definitions.Elements:
        #     definition = InstanceDefinition(element, meshes, bounds, render_materials, collision_materials)
        #     objects.extend(definition.create(render_model, temp_meshes))
        #     instance_definitions.append(definition)
            
        # # # # Create instanced geometries
        # print("Creating Instanced Objects")
        # for element in self.block_instances.Elements:
        #     io = Instance(element, instance_definitions)
        #     ob = io.create()
        #     objects.append(ob)
        #     self.collection.objects.link(ob)
            
        # Create structure
        structure_objects = []
        print("Creating Structure")
        for element in self.tag.SelectField("Block:clusters").Elements:
            structure = Cluster(element, meshes, render_materials)
            ob = structure.create(render_model, temp_meshes)
            structure_objects.append(ob)
            self.collection.objects.link(ob)
            
        # Merge structure
        if structure_objects:
            # print("Merging Structure")
            utils.deselect_all_objects()
            # bm = bmesh.new()
            # for ob in structure_objects:
            #     if ob.type == "MESH":
            #         ob.select_set(True)
            
            # if bpy.context.selected_objects:
            #     utils.set_active_object(bpy.context.selected_objects[0])
            #     bpy.ops.nwo.join_halo()
                
            #     joined_structure = utils.get_active_object()
            #     structure_mesh = joined_structure.data
            #     joined_structure.name = self.collection.name + "_structure"
                
            utils.deselect_all_objects()
            
            # bm = bmesh.new()
            # bm.from_mesh(structure_mesh)
            for ob in structure_objects:
                objects.append(ob)
                if ob.type != 'MESH' or ob.data.nwo != "_connected_geometry_mesh_type_structure": continue
                structure_mesh = ob.data
                structure_mesh.nwo.mesh_type = "_connected_geometry_mesh_type_structure"
                ob.nwo.proxy_instance = True
                bm = bmesh.new()
                bm.from_mesh(structure_mesh)
                water_layer = bm.faces.layers.int.get("water_surface")
                if water_layer:
                    water_mesh = structure_mesh.copy()
                    water_mesh.name = "water_surface"
                    bmw = bm.copy()
                    bmw_water_layer = bmw.faces.layers.int.get("water_surface")
                    bmesh.ops.delete(bmw, geom=[f for f in bmw.faces if not f[bmw_water_layer]], context='FACES')
                    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[water_layer]], context='FACES')
                    bmw.faces.layers.int.remove(bmw_water_layer)
                    bm.faces.layers.int.remove(water_layer)
                    bmw.to_mesh(water_mesh)
                    if water_mesh.polygons:
                        water_ob = bpy.data.objects.new(water_mesh.name, water_mesh)
                        self.collection.objects.link(water_ob)
                        utils.apply_loop_normals(water_mesh)
                        water_mesh.nwo.mesh_type = "_connected_geometry_mesh_type_water_surface"
                        water_ob.nwo.water_volume_depth = 0 # depth to be handled by structure design
                        utils.loop_normal_magic(water_ob.data)
                        water_ob.select_set(True)
                        utils.set_active_object(water_ob)
                        bpy.ops.object.editmode_toggle()
                        bpy.ops.mesh.separate(type="LOOSE")
                        bpy.ops.object.editmode_toggle()
                        for ob in bpy.context.selected_objects:
                            objects.append(ob)
                        utils.deselect_all_objects()

                    # bm.to_mesh(structure_mesh)
                bm.free()
            # if structure_mesh.polygons:
            #     utils.loop_normal_magic(structure_mesh)
            #     structure_mesh.nwo.mesh_type = "_connected_geometry_mesh_type_structure"
            #     joined_structure.nwo.proxy_instance = True
            #     objects.append(joined_structure)
            #     structure_mesh.nwo.render_only = True
            #     if structure_mesh.nwo.face_props:
            #         bm = bmesh.new()
            #         bm.from_mesh(structure_mesh)
            #         for face_layer in structure_mesh.nwo.face_props:
            #             face_layer.face_count = utils.layer_face_count(bm, bm.faces.layers.int.get(face_layer.layer_name))
            #         bm.free()
            
        # Create Structure Collision
        if self.corinth:
            print("Creating Structure Sky")
        else:
            print("Creating Structure Collision")
        raw_resources = self.tag.SelectField("Struct:resource interface[0]/Block:raw_resources")
        if raw_resources.Elements.Count > 0:
            collision = None
            collision_bsp = raw_resources.Elements[0].SelectField("Struct:raw_items[0]/Block:collision bsp")
            large_collision_bsp = raw_resources.Elements[0].SelectField("Struct:raw_items[0]/Block:large collision bsp")
            if collision_bsp.Elements.Count > 0:
                collision = StructureCollision(collision_bsp.Elements[0], "structure_collision", collision_materials)
            elif large_collision_bsp.Elements.Count > 0:
                collision = StructureCollision(large_collision_bsp.Elements[0], "structure_collision", collision_materials)
            
            if collision is not None:
                ob = collision.to_object()
                ob.data.nwo.mesh_type = "_connected_geometry_mesh_type_structure"
                ob.data.nwo.collision_only = True
                objects.append(ob)
                self.collection.objects.link(ob)
                ob.hide_set(True)
                ob.data.nwo.collision_only = True
        
        # Create Portals
        print("Creating Portals")
        for element in self.tag.SelectField("Block:cluster portals").Elements:
            portal = Portal(element)
            ob = portal.create()
            objects.append(ob)
            self.collection.objects.link(ob)
            
        return objects
    
    def get_seam_ids(self):
        seam_ids = []
        for element in self.tag.SelectField("Block:seam identifiers").Elements:
            id = element.SelectField("Struct:seams identifier[0]/LongInteger:seam_id0").Data
            seam_ids.append(id)
            
        return seam_ids
    
def are_faces_overlapping(face1, face2):
    # Check if faces are coplanar (i.e., their normals are parallel)
    if not face1.normal.dot(face2.normal) > 0.999:  # or a small epsilon
        return False
    
    verts1 = {vert.co.to_tuple() for vert in face1.verts}
    verts2 = {vert.co.to_tuple() for vert in face2.verts}
    
    # Check if the sets are identical
    return verts1 == verts2