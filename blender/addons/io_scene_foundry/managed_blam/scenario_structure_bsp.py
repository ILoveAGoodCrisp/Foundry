

import bmesh
import bpy

from ..tools.property_apply import apply_props_material

from .connected_geometry import BSPCollisionMaterial, BSPSeam, Cluster, CompressionBounds, Instance, InstanceDefinition, Material, Mesh, Portal, StructureCollision
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
                    case "per_pixel":
                        lighting.Value = 0
                    case "per_vertex":
                        lighting.Value = 1
                    case "single_probe":
                        lighting.Value = 2
                    case "per_vertex_ao":
                        lighting.Value = 5
                        
            if nwo.prefab_lightmap_res > 0:
                policy_mask.SetBit("override lightmap resolution policy", True)
                element.SelectField("override lightmap resolution scale").SetStringData(str(nwo.prefab_lightmap_res))
                    
            if nwo.prefab_pathfinding != "no_override":
                policy_mask.SetBit("override pathfinding policy", True)
                pathfinding = element.SelectField("override pathfinding policy")
                match nwo.prefab_lighting:
                    case "cutout":
                        pathfinding.Value = 0
                    case "static":
                        pathfinding.Value = 1
                    case "none":
                        pathfinding.Value = 2
                        
            if nwo.prefab_imposter_policy != "no_override":
                policy_mask.SetBit("override lmposter policy", True)
                imposter = element.SelectField("override imposter policy")
                match nwo.prefab_imposter_policy:
                    case "polygon_default":
                        imposter.Value = 0
                    case "polygon_high":
                        imposter.Value = 1
                    case "card_default":
                        imposter.Value = 2
                    case "card_high":
                        imposter.Value = 3
                    case "never":
                        imposter.Value = 4
                if nwo.prefab_imposter_policy != "never":
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
        
    def to_blend_objects(self, collection: bpy.types.Collection, for_scenario: bool, for_cinematic: bool):
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
        print("Creating Instance Definitions")
        for element in self.block_instance_definitions.Elements:
            definition = InstanceDefinition(element, meshes, bounds, render_materials, collision_materials, for_cinematic)
            objects.extend(definition.create(render_model, temp_meshes))
            instance_definitions.append(definition)
            
        # Create instanced geometries
        print("Creating Instanced Objects")
        # poops = []
        for element in self.block_instances.Elements:
            io = Instance(element, instance_definitions)
            if io.definition.blender_render or io.definition.blender_collision:
                ob = io.create()
                objects.append(ob)
                # poops.append(ob)
                self.collection.objects.link(ob)
        
        # if poops:
        #     with bpy.context.temp_override(selected_editable_objects=poops, object=poops[0]):
        #         bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
            
        # Create structure
        structure_objects = []
        print("Creating Structure")
        for element in self.tag.SelectField("Block:clusters").Elements:
            structure = Cluster(element, meshes, render_materials)
            ob = structure.create(render_model, temp_meshes)
            if ob is not None and ob.data and ob.data.polygons:
                structure_objects.append(ob)
                self.collection.objects.link(ob)
            
        # Merge structure
        utils.deselect_all_objects()
        print("Separating Water Surfaces from Structure")
        for ob in structure_objects:
            structure_mesh = ob.data
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
                bm.to_mesh(structure_mesh)
                bm.free()
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
                    for loose_water_ob in bpy.context.selected_objects:
                        objects.append(loose_water_ob)
                    utils.deselect_all_objects()
                
            if structure_mesh.polygons:
                structure_mesh.nwo.mesh_type = "_connected_geometry_mesh_type_structure"
                ob.nwo.proxy_instance = True
                objects.append(ob)
                structure_mesh.nwo.render_only = True
                if structure_mesh.nwo.face_props:
                    bm = bmesh.new()
                    bm.from_mesh(structure_mesh)
                    for face_layer in structure_mesh.nwo.face_props:
                        face_layer.face_count = utils.layer_face_count(bm, bm.faces.layers.int.get(face_layer.layer_name))
                    bm.free()
            
        # Create Structure Collision
        self.structure_collision = None
        if not for_cinematic:
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
                    self.structure_collision = ob
                    
                    if for_scenario:
                        print("Creating Seams")
                        seams_mesh = ob.data.copy()
                        # Remove seam faces
                        bm = bmesh.new()
                        seam_bm = bmesh.new()
                        bm.from_mesh(ob.data)
                        seam_bm.from_mesh(seams_mesh)
                        seam_material_indices = set()
                        for idx, material in enumerate(ob.data.materials):
                            seam_collision_mat = next((cm for cm in collision_materials if cm.blender_material == material and cm.is_seam), None)
                            if seam_collision_mat:
                                seam_material_indices.add(idx)
                                
                        bmesh.ops.delete(seam_bm, geom=[f for f in seam_bm.faces if f.material_index not in seam_material_indices], context='FACES')
                        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in seam_material_indices], context='FACES')
                        seam_bm.to_mesh(seams_mesh)
                        seam_bm.free()
                        bm.to_mesh(ob.data)
                        bm.free()
                        
                        if seams_mesh.polygons:
                            seam_ob = ob.copy()
                            seam_ob.data = seams_mesh
                            seam_ob.name = "seams"
                            seams_mesh.nwo.mesh_type = "_connected_geometry_mesh_type_seam"
                            seam_ob.nwo.seam_back_manual = True
                            apply_props_material(seam_ob, "Seam")
                            objects.append(seam_ob)
                            collection.objects.link(seam_ob)
                        
            # Create Portals
            print("Creating Portals")
            for element in self.tag.SelectField("Block:cluster portals").Elements:
                portal = Portal(element)
                ob = portal.create()
                objects.append(ob)
                self.collection.objects.link(ob)
            
        return objects
    
    # def get_seams(self, name, existing_seams: list[BSPSeam]=[]):
    #     seams = []
    #     print(self.tag_path.RelativePathWithExtension, self.tag.SelectField("Block:seam identifiers").Elements.Count, )
    #     for element in self.tag.SelectField("Block:seam identifiers").Elements:
    #         if existing_seams:
    #             existing_seams[element.ElementIndex].update(element, name)
    #         else:
    #             seam = BSPSeam(element)
    #             seam.update(element, name)
    #             seams.append(seam)
                
    #     if existing_seams:
    #         return existing_seams

    #     return seams
    
    def fix_collision_render_surface_mapping(self):
        '''
        Adds a single surfaces element to instance geometry surface mapping
        The game skips calculating this data when an instanced geometry has proxy collision
        Not having any data here prevents decals rendering on the collision surface
        '''
        if self.corinth:
            return
        
        for igd in self.block_instance_definitions.Elements:
            surfaces = igd.SelectField("Block:surfaces")
            if surfaces.Elements.Count > 0: # Already has data
                continue
            
            surfaces.AddElement().Fields[0].Data = -1
            self.tag_has_changes = True
    
def are_faces_overlapping(face1, face2):
    # Check if faces are coplanar (i.e., their normals are parallel)
    if not face1.normal.dot(face2.normal) > 0.999:  # or a small epsilon
        return False
    
    verts1 = {vert.co.to_tuple() for vert in face1.verts}
    verts2 = {vert.co.to_tuple() for vert in face2.verts}
    
    # Check if the sets are identical
    return verts1 == verts2