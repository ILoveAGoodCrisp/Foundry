

from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector
import numpy as np

from ..constants import WU_SCALAR

from .structure_meta import StructureMetaTag

from .scenario_structure_lighting_info import ScenarioStructureLightingInfoTag

from .connected_geometry import BSP, BSPCollisionMaterial, Cluster, CompressionBounds, Emissive, EnvironmentObject, EnvironmentObjectReference, Instance, InstanceDefinition, Material, Portal, StructureCollision, StructureMarker, SurfaceMapping
from ..utils import jstr
from . import Tag
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
                        element.SelectField("override imposter brightness").Data = nwo.prefab_imposter_brightness
                        
                    if not nwo.prefab_imposter_transition_distance_auto:
                        policy_mask.SetBit("override imposter transition distance policy", True)
                        element.SelectField("override imposter transition distance").Data = nwo.prefab_imposter_transition_distance * WU_SCALAR
                        
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
        
    def to_blend_objects(self, collection: bpy.types.Collection, for_cinematic: bool, lighting_info_path: Path = None, import_geometry=True, import_lights=True, always_get_structure_collision=False, sky_index=-1):
        
        objects = []
        game_objects = []
        bvh = None
        
        if not import_geometry and not import_lights:
            return objects, game_objects, bvh
        
        self.collection = collection
        # Get all collision materials
        collision_materials = []
        for element in self.tag.SelectField("Block:collision materials").Elements:
            collision_materials.append(BSPCollisionMaterial(element))
            
        # Get all emissive data
        emissives = []
        
        if self.corinth:
            for element in self.tag.SelectField("Block:emissive materials").Elements:
                emissives.append(Emissive(element))
                
        if not lighting_info_path:
            if self.corinth:
                path = self.tag.SelectField("structure lighting_info").Path
                if path is not None:
                    lighting_info_path = Path(path.Filename)
            else:
                lighting_info_path = Path(self.tag_path.Filename).with_suffix(".scenario_structure_lighting_info")
        
        if lighting_info_path.exists():
            with ScenarioStructureLightingInfoTag(path=str(lighting_info_path)) as info:
                if not self.corinth:
                    for element in info.tag.SelectField("Block:material info").Elements:
                        emissives.append(Emissive(element))
                    
                    if import_geometry:
                        if not for_cinematic:
                            lightmap_regions = info.lightmap_regions_to_blender()
                            if lightmap_regions:
                                print(f"Imported {len(lightmap_regions)} lightmap regions from {info.tag_path.RelativePathWithExtension}")
                                objects.extend(lightmap_regions)
                
                if import_lights:
                    light_objects = info.to_blender(collection)
                    if light_objects:
                        print(f"Imported {len(light_objects)} lights from {info.tag_path.RelativePathWithExtension}")
                        objects.extend(light_objects)
                            
        if not import_geometry:
            return objects, game_objects, bvh
                    
        # Get all render materials
        render_materials = []
        for element in self.tag.SelectField("Block:materials").Elements:
            render_materials.append(Material(element, emissives, True))
            
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
        if self.block_instances.Elements.Count > 0:
            instance_definitions = []
            print("Creating Instance Definitions")
            for element in self.block_instance_definitions.Elements:
                definition = InstanceDefinition(element, meshes, bounds, render_materials, collision_materials, for_cinematic)
                objects.extend(definition.create(render_model, temp_meshes))
                instance_definitions.append(definition)
            
            # Create instanced geometries
        
            # poops = []
            print("Creating Instanced Objects")
            ig_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_instances")
            self.collection.children.link(ig_collection)
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
                    objects.append(ob)
                    io_collection.objects.link(ob)
        
        # if poops:
        #     with bpy.context.temp_override(selected_editable_objects=poops, object=poops[0]):
        #         bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
        
        def get_collision():
            raw_resources = self.tag.SelectField("Struct:resource interface[0]/Block:raw_resources")
            if raw_resources.Elements.Count > 0:
                collision_bsp = raw_resources.Elements[0].SelectField("Struct:raw_items[0]/Block:collision bsp")
                large_collision_bsp = raw_resources.Elements[0].SelectField("Struct:raw_items[0]/Block:large collision bsp")
                if collision_bsp.Elements.Count > 0:
                    collision = StructureCollision(collision_bsp.Elements[0], "structure_collision", collision_materials, sky_index)
                elif large_collision_bsp.Elements.Count > 0:
                    collision = StructureCollision(large_collision_bsp.Elements[0], "structure_collision", collision_materials, sky_index)
                    
            return collision
            
        # Create structure
        structure_objects = []
        print("Creating Structure")
        collision = None
        
        layer = utils.add_permutation("structure")
        structure_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_structure")
        structure_collection.nwo.type = "permutation"
        structure_collection.nwo.permutation = layer
        self.collection.children.link(structure_collection)
        if for_cinematic:
            structure_surface_triangle_mapping = []
        else:
            collision = get_collision()
            if collision is not None:
                structure_surface_triangle_mapping = [SurfaceMapping(e.Fields[0].Data, e.Fields[1].Data, collision.surfaces[e.ElementIndex], self.tag.SelectField("Block:structure surface to triangle mapping")) for e in self.tag.SelectField("Block:large structure surfaces").Elements]
        
        for element in self.tag.SelectField("Block:clusters").Elements:
            structure = Cluster(element, meshes, render_materials)
            structure_obs = structure.create(render_model, temp_meshes, structure_surface_triangle_mapping, element.ElementIndex)
            for ob in structure_obs:
                if ob is not None and ob.data and ob.data.polygons:
                    # structure_collection.objects.link(ob)

                    if ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_water_surface':
                        objects.append(ob)
                        structure_collection.objects.link(ob)
                    else:
                        structure_objects.append(ob)
            
        # Create Structure Collision
        # self.structure_collision = None
        if collision is not None:
            if self.corinth:
                print("Creating Structure Sky")
            else:
                print("Creating Structure Collision")
            
            collision_only_indices = [idx for idx, mapping in enumerate(structure_surface_triangle_mapping) if mapping.collision_only]
            if collision_only_indices:
                ob = collision.to_object(surface_indices=collision_only_indices)
                collision_mesh = ob.data
                if collision.some_sphere_collision:
                    sphere_coll_face_props = [prop for prop in collision_mesh.nwo.face_props if prop.name == "Sphere Collision Only"]
                    if sphere_coll_face_props:
                        sphere_coll_face_prop = sphere_coll_face_props[0]
                        sphere_coll_attribute = collision_mesh.attributes.get(sphere_coll_face_prop.attribute_name)
                        array = np.zeros(len(collision_mesh.polygons), dtype=np.int8)
                        sphere_coll_attribute.data.foreach_get("value", array)
                        coll_only_array = array ^ 1
                        utils.add_face_prop(collision_mesh, "face_mode", coll_only_array).face_mode = 'collision_only'
                    else:
                        utils.add_face_prop(collision_mesh, "face_mode").face_mode = 'sphere_collision_only'
                    
                elif not collision.sphere_collision_only:
                    utils.add_face_prop(collision_mesh, "face_mode").face_mode = 'collision_only'
                structure_objects.append(ob)
                
        if always_get_structure_collision:
            if collision is None:
                collision = get_collision()
                        
            bvh = collision.to_bvh()
                        
        # Merge all structure objects
        main_structure_ob = None
        print("Merging Structure (Can take a while)")
        if len(structure_objects) > 1:
            main_structure_ob, remaining_structure_obs = structure_objects[0], structure_objects[1:]
            main_structure_ob.name = f"{self.tag_path.ShortName}_structure"
            utils.join_objects([main_structure_ob] + remaining_structure_obs)
            
        elif structure_objects:
            main_structure_ob = structure_objects[0]
        
        if main_structure_ob is not None:
            if not for_cinematic:
                utils.connect_verts_on_edge(main_structure_ob.data)
            objects.append(main_structure_ob)
            # utils.unlink(main_structure_ob)
            structure_collection.objects.link(main_structure_ob)
            main_structure_ob.nwo.proxy_instance = True
            main_structure_ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_structure'
            
            # separate out the seams
            seam_material_indices = {idx for idx, m in enumerate(main_structure_ob.data.materials) if m.name == "+seam"}
            if seam_material_indices:
                seam_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_seams")
                seam_collection.hide_render = True
                structure_collection.children.link(seam_collection)
                seam_ob = main_structure_ob.copy()
                seam_ob.data = main_structure_ob.data.copy()
                
                bm = bmesh.new()
                bm.from_mesh(main_structure_ob.data)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in seam_material_indices], context='FACES')
                bm.to_mesh(main_structure_ob.data)
                bm.free()
                
                bm = bmesh.new()
                bm.from_mesh(seam_ob.data)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in seam_material_indices], context='FACES')
                bm.to_mesh(seam_ob.data)
                bm.free()
                
                seam_ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_seam'
                seam_ob.nwo.seam_back_manual = True
                seam_ob.name = f"{self.tag_path.ShortName}_seams"
                objects.append(seam_ob)
                seam_collection.objects.link(seam_ob)
        
        print("Removing Duplicate Material Slots")
        ob_meshes = {o.data for o in objects if o.type == 'MESH'}
        for me in ob_meshes:
            utils.consolidate_face_attributes(me)
            utils.consolidate_materials(me)
                
        # Create Portals
        if not for_cinematic:
            if self.tag.SelectField("Block:cluster portals").Elements.Count > 0:
                print("Creating Portals")
                layer = utils.add_permutation("portals")
                portals_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_portals")
                portals_collection.hide_render = True
                portals_collection.nwo.type = "permutation"
                portals_collection.nwo.permutation = layer
                self.collection.children.link(portals_collection)
                for element in self.tag.SelectField("Block:cluster portals").Elements:
                    portal = Portal(element)
                    ob = portal.create()
                    objects.append(ob)
                    portals_collection.objects.link(ob)
            
            if self.tag.SelectField("Block:cookie cutters").Elements.Count > 0:
                print("Creating Cookie Cutters")
                layer = utils.add_permutation("cookie_cutters")
                cookies_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_cookie_cutters")
                cookies_collection.hide_render = True
                cookies_collection.nwo.type = "permutation"
                cookies_collection.nwo.permutation = layer
                self.collection.children.link(cookies_collection)
                for element in self.tag.SelectField("Block:cookie cutters").Elements:
                    cookie = BSP(element.Fields[1].Elements[0], f"cookie_cutter{element.ElementIndex}", [])
                    ob = cookie.to_object(cookie_cutter=True)
                    objects.append(ob)
                    cookies_collection.objects.link(ob)
        
            # Create markers
            if self.tag.SelectField("Block:markers").Elements.Count > 0:
                print("Creating Structure Markers")
                layer = utils.add_permutation("markers")
                markers_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_markers")
                markers_collection.nwo.type = "permutation"
                markers_collection.nwo.permutation = layer
                self.collection.children.link(markers_collection)
            
                for element in self.tag.SelectField("Block:markers").Elements:
                    marker = StructureMarker(element)
                    ob = marker.to_object()
                    objects.append(ob)
                    markers_collection.objects.link(ob)
            
        # Now do environment objects
        if self.corinth:
            path = self.tag.SelectField("Reference:structure meta data").Path
            if path is not None:
                structure_meta_path = Path(path.RelativePathWithExtension)
                if structure_meta_path.exists():
                    print("Importing Structure Meta")
                    meta_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_meta")
                    meta_collection.nwo.type = "permutation"
                    meta_collection.nwo.permutation = layer
                    self.collection.children.link(meta_collection)
                    with StructureMetaTag(path=structure_meta_path) as meta:
                        meta_objects, meta_game_objects = meta.to_blender(meta_collection, for_cinematic)
                        objects.extend(meta_objects)
                        objects.extend(meta_game_objects)
                        game_objects.extend(meta_game_objects)
            
            # Prefabs
            prefabs = self._import_prefabs(self.collection)
            objects.extend(prefabs)
            game_objects.extend(prefabs)
                
        else:
            if self.tag.SelectField("Block:environment objects").Elements.Count > 0:
                print("Creating Game Object Markers")
                layer = utils.add_permutation("objects")
                env_objects_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_objects")
                env_objects_collection.nwo.type = "permutation"
                env_objects_collection.nwo.permutation = layer
                self.collection.children.link(env_objects_collection)
                env_objects_palette = [EnvironmentObjectReference(element) for element in self.tag.SelectField("Block:environment object palette").Elements]
                for element in self.tag.SelectField("Block:environment objects").Elements:
                    env_object = EnvironmentObject(element, env_objects_palette)
                    ob = env_object.to_object()
                    if ob is not None:
                        env_objects_collection.objects.link(ob)
                        objects.append(ob)
                        game_objects.append(ob)
            
        return objects, game_objects, bvh
    
    def _import_prefabs(self, parent_collection):
        objects = []
        block_prefabs = self.tag.SelectField("Block:external references")
        if block_prefabs.Elements.Count == 0:
            return objects
        
        print("Importing Prefabs")
        prefabs_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_prefabs")
        prefabs_collection.nwo.type = "permutation"
        prefabs_collection.nwo.permutation = "prefabs"
        parent_collection.children.link(prefabs_collection)
        
        for element in self.block_prefabs.Elements:
            ref = self.get_path_str(element.SelectField("prefab reference").Path, True) 
            if not ref:
                continue
            
            if not Path(ref).exists():
                continue
            
            name = element.SelectField("name").GetStringData()
            ob = bpy.data.objects.new(name=name, object_data=None)
            ob.empty_display_type = "ARROWS"
            
            ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
            ob.nwo.marker_game_instance_tag_name = utils.relative_path(ref)
            
            forward = element.SelectField("forward").Data
            left = element.SelectField("left").Data
            up = element.SelectField("up").Data
            position = element.SelectField("position").Data
            
            ob.matrix_world = Matrix((
                (forward[0], left[0], up[0], position[0] * 100),
                (forward[1], left[1], up[1], position[1] * 100),
                (forward[2], left[2], up[2], position[2] * 100),
                (0, 0, 0, 1),
            ))
            
            scale = element.SelectField("scale").Data
            if scale != 0:
                ob.scale = Vector.Fill(3, scale)
            
            override_flags = element.SelectField("override flags")
            flags_mask = element.SelectField("instance flags Mask")
            policy_mask = element.SelectField("instance policy mask")
            
            # if nwo.prefab_lighting != "no_override":
            #     policy_mask.SetBit("override lightmapping policy", True)
            #     lighting = element.SelectField("override lightmapping policy")
            #     match nwo.prefab_lighting:
            #         case "per_pixel":
            #             lighting.Value = 0
            #         case "per_vertex":
            #             lighting.Value = 1
            #         case "single_probe":
            #             lighting.Value = 2
            #         case "per_vertex_ao":
            #             lighting.Value = 5
                        
            # if nwo.prefab_lightmap_res > 0:
            #     policy_mask.SetBit("override lightmap resolution policy", True)
            #     element.SelectField("override lightmap resolution scale").SetStringData(str(nwo.prefab_lightmap_res))
                    
            # if nwo.prefab_pathfinding != "no_override":
            #     policy_mask.SetBit("override pathfinding policy", True)
            #     pathfinding = element.SelectField("override pathfinding policy")
            #     match nwo.prefab_lighting:
            #         case "cutout":
            #             pathfinding.Value = 0
            #         case "static":
            #             pathfinding.Value = 1
            #         case "none":
            #             pathfinding.Value = 2
                        
            # if nwo.prefab_imposter_policy != "no_override":
            #     policy_mask.SetBit("override lmposter policy", True)
            #     imposter = element.SelectField("override imposter policy")
            #     match nwo.prefab_imposter_policy:
            #         case "polygon_default":
            #             imposter.Value = 0
            #         case "polygon_high":
            #             imposter.Value = 1
            #         case "card_default":
            #             imposter.Value = 2
            #         case "card_high":
            #             imposter.Value = 3
            #         case "never":
            #             imposter.Value = 4
            #     if nwo.prefab_imposter_policy != "never":
            #         if nwo.prefab_imposter_brightness > 0:
            #             policy_mask.SetBit("override imposter brightness", True)
            #             element.SelectField("override imposter brightness").Data = nwo.prefab_imposter_brightness
                        
            #         if not nwo.prefab_imposter_transition_distance_auto:
            #             policy_mask.SetBit("override imposter transition distance policy", True)
            #             element.SelectField("override imposter transition distance").Data = nwo.prefab_imposter_transition_distance * WU_SCALAR
                        
            # if nwo.prefab_streaming_priority != "no_override":
            #     streaming = element.SelectField("override streaming priority")
            #     match nwo.prefab_streaming_priority:
            #         case "_connected_geometry_poop_streamingpriority_default":
            #             streaming.Value = 0
            #         case "_connected_geometry_poop_streamingpriority_higher":
            #             streaming.Value = 1
            #         case "_connected_geometry_poop_streamingpriority_highest":
            #             streaming.Value = 2
            
            # if nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_only':
            #     override_flags.SetBit("cinema only", True)
            #     flags_mask.SetBit("cinema only", True)
            # elif nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_exclude':
            #     override_flags.SetBit("exclude from cinema", True)
            #     flags_mask.SetBit("exclude from cinema", True)
                
            # if nwo.prefab_render_only:
            #     override_flags.SetBit("render only", True)
            #     flags_mask.SetBit("render only", True)
            # if nwo.prefab_does_not_block_aoe:
            #     override_flags.SetBit("does not block aoe damage", True)
            #     flags_mask.SetBit("does not block aoe damage", True)
            # if nwo.prefab_excluded_from_lightprobe:
            #     override_flags.SetBit("not in lightprobes", True)
            #     flags_mask.SetBit("not in lightprobes", True)
            # if nwo.prefab_decal_spacing:
            #     override_flags.SetBit("decal spacing", True)
            #     flags_mask.SetBit("decal spacing", True)
            # if nwo.prefab_remove_from_shadow_geometry:
            #     override_flags.SetBit("remove from shadow geometry", True)
            #     flags_mask.SetBit("remove from shadow geometry", True)
            # if nwo.prefab_disallow_lighting_samples:
            #     override_flags.SetBit("disallow object lighting samples", True)
            #     flags_mask.SetBit("disallow object lighting samples", True)
            
            prefabs_collection.objects.link(ob)
            objects.append(ob)
            
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
            
            for element in igd.SelectField("Struct:collision info[0]/Block:surfaces").Elements:
                surfaces.AddElement()
            self.tag_has_changes = True
    
def are_faces_overlapping(face1, face2):
    if not face1.normal.dot(face2.normal) > 0.999:
        return False
    
    verts1 = {vert.co.to_tuple() for vert in face1.verts}
    verts2 = {vert.co.to_tuple() for vert in face2.verts}
    
    return verts1 == verts2

def auto_merge_and_split():
    ts = bpy.context.scene.tool_settings
    ts.use_mesh_automerge         = True
    ts.use_mesh_automerge_and_split = True
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            bpy.context.view_layer.objects.active = obj

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            bpy.ops.transform.rotate(
                value=0.0,
                orient_axis='X',
                orient_type='GLOBAL'
            )

            # Back to Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')