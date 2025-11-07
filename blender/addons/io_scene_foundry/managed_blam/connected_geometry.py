"""Classes to help with importing geometry from tags"""

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from math import radians, sqrt
import math
from pathlib import Path
import re
from statistics import mean
from typing import Iterable
import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector, geometry, bvhtree
import numpy as np

from ..constants import LIGHTMAP_ADDITIVE_TRANSPARENCY_COLOR, LIGHTMAP_ANALYTICAL_LIGHT_ABSORB, LIGHTMAP_CHART_GROUP_INDEX, LIGHTMAP_IGNORE_DEFAULT_RESOLUTION_SCALE, LIGHTMAP_LIGHTING_FROM_BOTH_SIDES, LIGHTMAP_NORMAL_LIGHT_ABSORD, LIGHTMAP_RESOLUTION_SCALE, LIGHTMAP_TRANSLUCENCY_TINT_COLOR, LIGHTMAP_TRANSPARENCY_OVERRIDE, WU_SCALAR

from ..tools.append_foundry_materials import add_special_materials

from ..tools.property_apply import apply_props_material

from .material import MaterialTag
from .shader import ShaderTag
from ..tools import materials as special_materials

from .. import utils
from .Tags import TagFieldBlock, TagFieldBlockElement, TagPath
from mathutils.geometry import tessellate_polygon

mat_props_cache = {}

class PartType(Enum): # Thank you Halo 2!
    not_drawn = 0
    opaque_shadow_only = 1
    opaque_shadow_casting = 2
    opaque_non_shadowing = 3
    transparent = 4
    lightmap_only = 5

class BSPSeam:
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.bsps = []
        self.origin = Vector()
                
    def update(self, element: TagFieldBlockElement, bsp):
        clusters = element.SelectField("Block:cluster mapping")
        for cluster_element in clusters.Elements:
            if cluster_element.Fields[0].Data > -1:
                if not self.bsps:
                    self.origin = Vector((p for p in cluster_element.Fields[1].Data))
                self.bsps.append(bsp)
                break

class PortalType(Enum):
    _connected_geometry_portal_type_no_way = 0
    _connected_geometry_portal_type_one_way = 1
    _connected_geometry_portal_type_two_way = 2

class Portal:
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.type = PortalType._connected_geometry_portal_type_two_way
        flags = element.SelectField("flags")
        if flags.TestBit("one-way") or flags.TestBit("one-way-reversed"):
            self.type = PortalType._connected_geometry_portal_type_one_way
        elif flags.TestBit("no-way"):
            self.type = PortalType._connected_geometry_portal_type_no_way
            
        self.ai_deafening = flags.TestBit("ai can't hear through this shit")
        self.blocks_sounds = flags.TestBit("no one can hear through this")
        self.is_door = flags.TestBit("door")
            
        vertices_block = element.SelectField("Block:vertices")
        self.vertices = []
        for e in vertices_block.Elements:
            self.vertices.append(Vector(n for n in e.Fields[0].Data) * 100)
            
    def create(self) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(f"portal:{self.index}")
        mesh.from_pydata(vertices=self.vertices, edges=[], faces=[list(range(len(self.vertices)))])
        mesh.nwo.mesh_type = "_connected_geometry_mesh_type_portal"
        ob = bpy.data.objects.new(mesh.name, mesh)
        apply_props_material(ob, "Portal")
        nwo = ob.nwo
        
        nwo.portal_ai_deafening = self.ai_deafening
        nwo.portal_blocks_sounds = self.blocks_sounds
        nwo.portal_is_door = self.is_door
        
        return ob
    
class BSPMarkerType(Enum):
    none = 0
    cheap_light = 1
    falling_leaf_generator = 2
    light = 3
    sky = 4
    model = 5
    
class PathfindingPolicy(Enum):
    cutout = 0
    static = 1
    none = 2
    
class LightmappingPolicy(Enum):
    per_pixel = 0
    per_vertex = 1
    single_probe = 2
    _connected_geometry_poop_lighting_exclude = 3
    per_pixel_ao = 4
    per_vertex_ao = 5
    
class ImposterPolicy(Enum):
    polygon_default = 0
    polygon_high = 1
    card_default = 2
    card_high = 3
    _connected_poop_instance_imposter_policy_none = 4
    never = 5

class CinemaType(Enum):
    _connected_geometry_poop_cinema_default = 0
    _connected_geometry_poop_cinema_only = 1
    _connected_geometry_poop_cinema_exclude = 2
    
class StreamingPriority(Enum):
    _connected_geometry_poop_streamingpriority_default = 0
    _connected_geometry_poop_streamingpriority_higher = 1
    _connected_geometry_poop_streamingpriority_highest = 2
    
class Cluster:
    def __init__(self, element: TagFieldBlockElement, mesh_block: TagFieldBlock, render_materials: list['Material']):
        self.index = element.ElementIndex
        self.mesh_index = element.SelectField("mesh index").Data
        self.mesh = Mesh(mesh_block.Elements[self.mesh_index], materials=render_materials)
        # self.sky_index = -1
        # sky_index_field = element.SelectField("CharInteger:scenario sky index")
        # if sky_index_field is not None:
        #     self.sky_index = sky_index_field.Data
        
    def create(self, render_model, temp_meshes, cluster_surface_triangle_mapping=[], section_index=0) -> bpy.types.Object:
        return self.mesh.create(render_model, temp_meshes, name=f"cluster:{self.index}", surface_triangle_mapping=cluster_surface_triangle_mapping, section_index=section_index)
        
class TriangleMapping:
    def __init__(self, value: int):
        self.tri = int(((value >> 12) + 1) / 3 - 1)
        self.section = value & 0xFFF
        # print(self.tri, self.section)
        
class SurfaceMapping:
    def __init__(self, first: int, count: int, surface: 'CollisionSurface', surf_to_tri_block: TagFieldBlock):
        self.surface = surface
        self.triangle_indices: list[TriangleMapping] = []
        self.collision_only = False
        if count:
            for i in range(first, first + count):
                value = surf_to_tri_block.Elements[i].Fields[0].Data
                mapping = TriangleMapping(value)
                self.triangle_indices.append(mapping)
        else:
            self.collision_only = True
            
class InstanceDefinition:
    def __init__(self, element: TagFieldBlockElement, mesh_block: TagFieldBlock, compression_bounds: list['CompressionBounds'], render_materials: list['Material'], collision_materials: list['BSPCollisionMaterial'], for_cinematic = False):
        self.index = element.ElementIndex
        self.mesh_index = element.SelectField("mesh index").Data
        self.compression_index = element.SelectField("compression index").Data
        self.compression = compression_bounds[self.compression_index]
        self.mesh = Mesh(mesh_block.Elements[self.mesh_index], self.compression, materials=render_materials)
        self.has_collision = False
        self.collision_is_proxy = False
        self.surface_triangle_mapping = []
        self.collision_info = None
        self.collision_only_surface_indices = []
        self.has_cookie = False
        self.cookie_info = None
        self.blender_collision = None
        self.blender_cookie = None
        self.has_physics = False
        self.blender_physics = []
        self.blender_render = None
        if not utils.is_corinth() and not for_cinematic:
            self.has_collision = element.SelectField("Struct:collision info[0]/Block:surfaces").Elements.Count > 0
            self.collision_is_proxy = self.has_collision and (element.SelectField("Block:surfaces").Elements.Count == 0 or element.SelectField("Block:render bsp").Elements.Count > 0)
            if self.has_collision:
                self.collision_info = InstanceCollision(element.SelectField("Struct:collision info").Elements[0], f"instance_collision:{self.index}", collision_materials)
                if not self.collision_is_proxy:
                    surf_to_tri_block = element.SelectField("Block:surface to triangle mapping")
                    self.surface_triangle_mapping = [SurfaceMapping(e.Fields[0].Data, e.Fields[1].Data, self.collision_info.surfaces[e.ElementIndex], surf_to_tri_block) for e in element.SelectField("Block:surfaces").Elements]
                    self.collision_only_surface_indices = [idx for idx, mapping in enumerate(self.surface_triangle_mapping) if mapping.collision_only]
            self.has_cookie = element.SelectField("Struct:poopie cutter collision[0]/Block:surfaces").Elements.Count > 0
            if self.has_cookie:
                self.cookie_info = InstanceCollision(element.SelectField("Struct:poopie cutter collision").Elements[0], f"instance_cookie_cutter:{self.index}", collision_materials)
            
            self.has_physics = element.SelectField("Block:polyhedra_with_materials").Elements.Count > 0
            if self.has_physics:
                self.physics_info = InstancePhysics(element, f"instance_physics:{self.index}", collision_materials)
    
    def create(self, render_model, temp_meshes) -> list[bpy.types.Object]:
        objects = []
        
        result = self.mesh.create(render_model, temp_meshes, name=f"instance_definition:{self.index}", surface_triangle_mapping=self.surface_triangle_mapping)
        self.blender_render = None
        if result:
            self.blender_render = result[0]
            
        render_valid = self.blender_render and self.blender_render.type == 'MESH'
            
        if not utils.is_corinth():
            if self.has_collision:
                if render_valid:
                    if self.collision_is_proxy:
                        self.blender_collision = self.collision_info.to_object()
                        if self.blender_render and self.blender_render.type == 'MESH':
                            self.blender_collision.name = f"{self.blender_render.name}_proxy_collision"
                            self.blender_collision.nwo.proxy_parent = self.blender_render.data
                            self.blender_collision.nwo.proxy_type = "collision"
                            self.blender_render.data.nwo.proxy_collision = self.blender_collision
                    elif self.collision_only_surface_indices:
                        collision_mesh = self.collision_info.to_object(mesh_only=True, surface_indices=self.collision_only_surface_indices)
                        
                        mat_to_idx = {m: i for i, m in enumerate(collision_mesh.materials)}
                        for mat in self.blender_render.data.materials:
                            if mat not in mat_to_idx:
                                mat_to_idx[mat] = len(collision_mesh.materials)
                                collision_mesh.materials.append(mat)
                                
                        idx_map = np.asarray([mat_to_idx[m] for m in self.blender_render.data.materials])
                        material_indices = np.empty(len(self.blender_render.data.polygons), dtype=np.int32)
                        self.blender_render.data.polygons.foreach_get("material_index", material_indices)
                        remap = idx_map[material_indices]

                        self.blender_render.data.materials.clear()
                        for mat in collision_mesh.materials:
                            self.blender_render.data.materials.append(mat)
                            
                        self.blender_render.data.polygons.foreach_set("material_index", remap)
                                
                        if self.collision_info.some_sphere_collision:
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
                            
                        elif not self.collision_info.sphere_collision_only:
                            utils.add_face_prop(collision_mesh, "face_mode").face_mode = 'collision_only'
                            
                        utils.save_loop_normals_mesh(self.blender_render.data)
                        bm = bmesh.new()
                        bm.from_mesh(collision_mesh)
                        bm.from_mesh(self.blender_render.data)
                        bm.to_mesh(self.blender_render.data)
                        bm.free()
                                
                        utils.apply_loop_normals(self.blender_render.data)
                        utils.set_two_sided(self.blender_render.data, False) 
                        utils.loop_normal_magic(self.blender_render.data)
                        
                        for prop in collision_mesh.nwo.face_props:
                            new_prop = self.blender_render.data.nwo.face_props.add()
                            for k, v in prop.items():
                                new_prop[k] = v
                else:
                    self.blender_render = self.collision_info.to_object()
                    self.blender_render.name = f"instance_definition:{self.index}"
                    if self.collision_info.sphere_collision_only:
                        utils.add_face_prop(self.blender_render.data, "face_mode").face_mode = 'sphere_collision_only'
                    else:
                        utils.add_face_prop(self.blender_render.data, "face_mode").face_mode = 'collision_only'
                    render_valid = True
                    
            elif self.blender_render and self.blender_render.data:
                utils.add_face_prop(self.blender_render.data, "face_mode").face_mode = 'render_only'
                
            if self.has_physics:
                for idx, polyhedra in enumerate(self.physics_info.polyhedra):
                    phys = polyhedra.to_object()
                    phys.data.materials.append(polyhedra.material.blender_material)
                    if self.blender_render and self.blender_render.type == 'MESH':
                        phys.name = f"{self.blender_render.name}_proxy_physics{idx}"
                        phys.nwo.proxy_parent = self.blender_render.data
                        phys.nwo.proxy_type = "physics"
                        setattr(self.blender_render.data.nwo, f"proxy_physics{idx}", phys)
                        
                    elif self.blender_collision and (utils.test_face_prop_all(self.blender_collision.data, "Collision Only") or utils.test_face_prop_all(self.blender_collision.data, "Sphere Collision Only")):
                        phys.name = f"{self.blender_collision.name}_proxy_physics{idx}"
                        phys.nwo.proxy_parent = self.blender_collision.data
                        phys.nwo.proxy_type = "physics"
                        setattr(self.blender_collision.data.nwo, f"proxy_physics{idx}", phys)
                    else:
                        utils.print_warning("Found physics but no render or collision!!!")
                    self.blender_physics.append(phys)
                    
            if self.has_cookie:
                self.blender_cookie = self.cookie_info.to_object()
                self.blender_cookie.name = f"{self.blender_render.name}_proxy_cookie_cutter"
                self.blender_cookie.nwo.proxy_parent = self.blender_render.data
                self.blender_cookie.nwo.proxy_type = "cookie_cutter"
                self.blender_render.data.nwo.proxy_cookie_cutter = self.blender_cookie

        if self.blender_render:
            if self.has_collision and not self.collision_is_proxy:
                utils.connect_verts_on_edge(self.blender_render.data)
            objects.append(self.blender_render)
        if self.blender_collision:
            utils.connect_verts_on_edge(self.blender_collision.data)
            objects.append(self.blender_collision)
        if self.blender_cookie:
            objects.append(self.blender_cookie)
        if self.blender_physics:
            objects.extend(self.blender_physics)
            
        return objects
            
    
class Instance:
    def __init__(self, element: TagFieldBlockElement, definitions: list[InstanceDefinition]):
        self.index = element.ElementIndex
        self.mesh_index = element.SelectField("ShortInteger:mesh_index").Data
        self.definition = definitions[self.mesh_index]
        self.scale = element.SelectField("scale").Data
        forward = element.SelectField("forward").Data
        left = element.SelectField("left").Data
        up = element.SelectField("up").Data
        position = element.SelectField("position").Data
        
        self.matrix = Matrix((
            (forward[0], left[0], up[0], position[0] * 100),
            (forward[1], left[1], up[1], position[1] * 100),
            (forward[2], left[2], up[2], position[2] * 100),
            (0, 0, 0, 1),
        ))
        
        flags = element.SelectField("flags")
        self.not_in_lightprobes = flags.TestBit("not in lightprobes")
        self.render_only = flags.TestBit("render only")
        self.not_block_aoe = flags.TestBit("does not block aoe damage")
        self.decal = flags.TestBit("decal spacing")
                
        self.imposter_transition = element.SelectField("imposter transition complete distance").Data
        
        self.pathfinding = PathfindingPolicy(element.SelectField("pathfinding policy").Value)
        self.lightmapping = LightmappingPolicy(element.SelectField("lightmapping policy").Value)
        self.imposter = ImposterPolicy(element.SelectField("imposter policy").Value)
        
        self.lightmap_res = element.SelectField("lightmap resolution scale").Data
        
        self.name = element.SelectField("name").Data
        
        self.remove_from_shadow = False
        self.cinema_type = CinemaType._connected_geometry_poop_cinema_default
        self.imposter_brightness = 0
        self.disallow_lighting_samples = False
        self.streaming = StreamingPriority._connected_geometry_poop_streamingpriority_default
        if utils.is_corinth():
            self.imposter_brightness = element.SelectField("imposter brightness").Data
            self.streaming = StreamingPriority(element.SelectField("streaming priority").Value)
            self.remove_from_shadow = flags.TestBit("remove from shadow geometry")
            self.disallow_lighting_samples = flags.TestBit("disallow object lighting samples")
            if flags.TestBit("cinema only"):
                self.cinema_type = CinemaType._connected_geometry_poop_cinema_only
            elif flags.TestBit("exclude from cinema"):
                self.cinema_type = CinemaType._connected_geometry_poop_cinema_exclude
                
        self.world_bound_sphere_radius = element.SelectField("Real:world bounding sphere radius").Data
        
        
    def create(self) -> list[bpy.types.Object]:
        if (not self.definition.blender_render or self.definition.blender_render.type == 'EMPTY') and self.definition.blender_collision:
            ob = self.definition.blender_collision.copy()
        else:
            ob = self.definition.blender_render.copy()
        ob.name = utils.any_partition(self.name, "__(")
        ob.matrix_world = self.matrix
        ob.scale = Vector.Fill(3, self.scale)
        nwo = ob.nwo
        nwo.poop_excluded_from_lightprobe = self.not_in_lightprobes
        nwo.poop_render_only = self.render_only
        nwo.poop_does_not_block_aoe = self.not_block_aoe
        nwo.poop_decal_spacing = self.decal
        nwo.poop_remove_from_shadow_geometry = self.remove_from_shadow
        nwo.poop_disallow_lighting_samples = self.disallow_lighting_samples
        nwo.poop_cinematic_properties = self.cinema_type.name
        if self.lightmapping.value > 2:
            if self.lightmapping == LightmappingPolicy.per_pixel_ao:
                nwo.poop_ao = True
                nwo.poop_lighting = "per_pixel"
            elif self.lightmapping == LightmappingPolicy.per_vertex_ao:
                nwo.poop_ao = True
                nwo.poop_lighting = "per_vertex"
        else:
            nwo.poop_lighting = self.lightmapping.name
            
        nwo.poop_pathfinding = self.pathfinding.name
        if self.imposter == ImposterPolicy._connected_poop_instance_imposter_policy_none:
            nwo.poop_imposter_policy = "never"
        else:
            nwo.poop_imposter_policy = self.imposter.name
        nwo.poop_streaming_priority = self.streaming.name
        nwo.poop_imposter_brightness = self.imposter_brightness
        nwo.poop_imposter_transition_distance = self.imposter_transition * (1 / WU_SCALAR)
        nwo.poop_imposter_transition_distance_auto = self.imposter_transition <= 0
        
        nwo.poop_lightmap_resolution_scale = self.lightmap_res
        
        # Check that object origin is not too far away from instance
        # This can cause the plane builder to fail
        if False and self.world_bound_sphere_radius > 500:
            ob.data = ob.data.copy() # so we don't break any other instances
            utils.set_origin_to_centre(ob)
            # utils.set_origin_to_floor(ob)
        
        
        return ob

    def get_collection(self, ig_collection, permitted_collections, bsp_name: str) -> bpy.types.Collection:
        def find_collection(name: str) -> bpy.types.Collection | None:
            """Finds a collection by name, ignoring .001/.002 suffixes."""
            col = bpy.data.collections.get(name)
            if col:
                return col
            base = name.rsplit(".", 1)[0]
            for c in bpy.data.collections:
                if c.name.rsplit(".", 1)[0] == base:
                    return c
            return None

        if "(" in self.name and ")" in self.name.rpartition("(")[2]:
            collection_part = re.findall(r'\((.*?)\)', self.name)[0]
            if ":" in collection_part:
                sub_collection_name, _, main_collection_name_main = collection_part.rpartition(":")
                main_collection_name_main = main_collection_name_main.strip("_")
                sub_collection_name = sub_collection_name.strip("_")
            else:
                sub_collection_name = None
                main_collection_name_main = collection_part

            main_collection_name = main_collection_name_main
            if main_collection_name == bsp_name:
                main_collection_name = f"layer_{main_collection_name}"

            # ---- MAIN COLLECTION ----
            main_collection = find_collection(main_collection_name)
            if main_collection is None:
                # truly doesn't exist → create it
                main_collection = bpy.data.collections.new(name=main_collection_name)
                ig_collection.children.link(main_collection)
                utils.add_permutation(main_collection_name_main)
                main_collection.nwo.type = 'permutation'
                main_collection.nwo.permutation = main_collection_name_main
            elif main_collection not in permitted_collections:
                # exists but not permitted → just link it instead of creating duplicates
                if main_collection.name not in ig_collection.children:
                    ig_collection.children.link(main_collection)

            # ---- SUB COLLECTION ----
            if sub_collection_name is not None:
                if sub_collection_name == bsp_name:
                    sub_collection_name = f"sublayer_{main_collection_name}"

                sub_collection = find_collection(sub_collection_name)
                if sub_collection is None:
                    sub_collection = bpy.data.collections.new(name=sub_collection_name)
                    main_collection.children.link(sub_collection)
                elif sub_collection not in permitted_collections:
                    if sub_collection.name not in main_collection.children:
                        main_collection.children.link(sub_collection)

                return sub_collection
            else:
                return main_collection

        return ig_collection

class StructureMarker:
    def __init__(self, element: TagFieldBlockElement):
        self.name = element.SelectField("String:marker parameter").GetStringData()
        self.rotation: Quaternion = utils.ijkw_to_wxyz([n for n in element.SelectField("rotation").Data])
        self.position: Vector = ([n * 100 for n in element.SelectField("position").Data])
        
    def to_object(self):
        ob = bpy.data.objects.new(name=self.name, object_data=None)
        ob.empty_display_type = "ARROWS"
        ob.empty_display_size *= (1 / 0.03048)
        ob.matrix_world = Matrix.LocRotScale(self.position, self.rotation, Vector.Fill(3, 1))
        return ob
        
class EnvironmentObjectReference:
    def __init__(self, element: TagFieldBlockElement):
        self.definition = None
        def_path = element.Fields[0].Path
        if def_path is not None:
            if Path(def_path.Filename).exists():
                self.definition = def_path.RelativePathWithExtension
    
class EnvironmentObject:
    def __init__(self, element: TagFieldBlockElement, palette: list[EnvironmentObjectReference]):
        self.name = element.SelectField("name").GetStringData()
        self.rotation: Quaternion = utils.ijkw_to_wxyz([n for n in element.SelectField("rotation").Data])
        self.translation: Vector = ([n * 100 for n in element.SelectField("translation").Data])
        self.scale = element.SelectField("scale").Data
        palette_index = element.SelectField("ShortBlockIndex:palette_index").Value
        self.reference = palette[palette_index] if palette_index > -1  and palette_index < len(palette) else None
        self.variant = element.SelectField("StringId:variant name").GetStringData()
        
    def to_object(self):
        if self.reference is None or self.reference.definition is None:
            return print(f"Found environment object named {self.name} but it has no valid tag reference")
            
        ob = bpy.data.objects.new(name=self.name, object_data=None)
        ob.empty_display_type = "ARROWS"
        ob.matrix_world = Matrix.LocRotScale(self.translation, self.rotation, Vector.Fill(3, self.scale))
        
        ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
        ob.nwo.marker_game_instance_tag_name = self.reference.definition
        ob.nwo.marker_game_instance_tag_variant_name = self.variant
        
        return ob
         
#     index: int
#     palette_index: int
#     palette: EnvironmentObjectPalette
#     name: str
#     rotation: Quaternion
#     translation: Vector
#     scale: float
#     variant: str

class Face:
    def __init__(self,indices: list[int], subpart: 'MeshSubpart', index: int):
        self.indices = indices
        self.subpart = subpart
        self.index = index

class Node:
    def __init__(self, name):
        self.name = name
        self.parent = None

class Permutation: 
    def __init__(self, element: TagFieldBlockElement, region: 'Region'):
        self.region = region
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.mesh_index = element.SelectField("mesh index").Data
        self.mesh_count = element.SelectField("mesh count").Data
        self.clone_name = ""
        self.instance_indices = []
        if utils.is_corinth():
            self.clone_name = element.SelectField("clone name").GetStringData()
        flags_1 = element.SelectField("instance mask 0-31")
        for i in range(31):
            if flags_1.TestBit(str(i)):
                self.instance_indices.append(i)
        flags_2 = element.SelectField("instance mask 32-63")
        for i in range(31):
            if flags_2.TestBit(str(i)):
                self.instance_indices.append(i + 32)
        flags_3 = element.SelectField("instance mask 64-95")
        for i in range(31):
            if flags_3.TestBit(str(i)):
                self.instance_indices.append(i + 64)
        flags_4 = element.SelectField("instance mask 96-127")
        for i in range(31):
            if flags_4.TestBit(str(i)):
                self.instance_indices.append(i + 96)
    
class Region:
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.permutations_block = element.SelectField("permutations")
        self.permutations = []
        for element in self.permutations_block.Elements:
            self.permutations.append(Permutation(element, self))

class RenderArmature():
    def __init__(self, name, existing_armature=None):
        if existing_armature is None:
            self.data = bpy.data.armatures.new(name)
            self.ob = bpy.data.objects.new(name, self.data)
        else:
            self.ob = existing_armature
            self.data = existing_armature.data
        self.bones: Node = []
        
    def create_bone(self, node: Node):
        bone = self.data.edit_bones.new(node.name)
        bone.length = 5
        
        loc = (node.inverse_position)
        rot = Matrix((node.inverse_forward, node.inverse_left, node.inverse_up))
        scale = Vector.Fill(3, node.inverse_scale)
        transform_matrix = Matrix.LocRotScale(loc, rot, scale)
        
        try:
            transform_matrix.invert()
        except:
            transform_matrix.identity()
        
        transform_matrix = Matrix.Translation(node.translation) @ node.rotation.to_matrix().to_4x4()
        node.transform_matrix = transform_matrix
        bone.matrix = transform_matrix
        node.bone = bone
        
    def parent_bone(self, node: Node):
        if node.parent:
            parent = self.data.edit_bones[node.parent]
            node.bone.parent = parent
            transform_matrix = parent.matrix @ node.transform_matrix
            node.bone.matrix = transform_matrix
            
            
class ConstraintType(Enum):
    hinge = 0
    limited_hinge = 1
    ragdoll = 2
    stiff_spring = 3
    ball_and_socket = 4
    prismatic = 5
    powered_chain = 6
    
class Hinge:
    def __init__(self, element: TagFieldBlockElement, nodes: list[str]):
        self.constraint_body = element.SelectField("Struct:constraint bodies").Elements[0]
        self.index = element.ElementIndex
        self.name = self.constraint_body.Fields[0].Data
        self.node_a_index = self.constraint_body.Fields[1].Value
        self.node_b_index = self.constraint_body.Fields[2].Value
        self.bone_parent = nodes[self.node_a_index]
        self.bone_child = nodes[self.node_b_index]
        
        afi, afj, afk = self.constraint_body.SelectField("a forward").Data
        ali, alj, alk = self.constraint_body.SelectField("a left").Data
        aui, auj, auk = self.constraint_body.SelectField("a up").Data
        api, apj, apk = self.constraint_body.SelectField("a position").Data
        
        bfi, bfj, bfk = self.constraint_body.SelectField("b forward").Data
        bli, blj, blk = self.constraint_body.SelectField("b left").Data
        bui, buj, buk = self.constraint_body.SelectField("b up").Data
        bpi, bpj, bpk = self.constraint_body.SelectField("b position").Data
        
        # self.matrix_a = Matrix((
        #     (afi, afj, afk, 0.0),
        #     (ali, alj, alk, 0.0),
        #     (aui, auj, auk, 0.0),
        #     (api, apj, apk, 1.0),
        # ))
        # self.matrix_b = Matrix((
        #     (bfi, bfj, bfk, 0.0),
        #     (bli, blj, blk, 0.0),
        #     (bui, buj, buk, 0.0),
        #     (bpi, bpj, bpk, 1.0),
        # ))
        
        self.matrix_a = Matrix((
            (afi, ali, aui, api * 100),
            (afj, alj, auj, apj * 100),
            (afk, alk, auk, apk * 100),
            (0, 0, 0, 1),
        ))
        
        self.matrix_b = Matrix((
            (bfi, bli, bui, bpi * 100),
            (bfj, blj, buj, bpj * 100),
            (bfk, blk, buk, apk * 100),
            (0, 0, 0, 1),
        ))
        
    def to_object(self, armature) -> bpy.types.Object:
        ob = bpy.data.objects.new(self.name, None)
        ob.empty_display_type = 'ARROWS'
        nwo = ob.nwo
        nwo.marker_type = "_connected_geometry_marker_type_physics_constraint"
        nwo.physics_constraint_parent = armature
        nwo.physics_constraint_parent_bone = self.bone_parent
        nwo.physics_constraint_child = armature
        nwo.physics_constraint_child_bone = self.bone_child
        self._set_constraint_props(nwo)
        
        return ob
    
    def _set_constraint_props(self, nwo):
        nwo.physics_constraint_type = "_connected_geometry_marker_type_physics_hinge_constraint"
    
    
class LimitedHinge(Hinge):
    def __init__(self, element: TagFieldBlockElement, nodes: list[str]):
        super().__init__(element, nodes)
        self.limit_min_angle = element.SelectField("limit min angle").Data
        self.limit_max_angle = element.SelectField("limit max angle").Data
        
    def _set_constraint_props(self, nwo):
        nwo.physics_constraint_type = "_connected_geometry_marker_type_physics_hinge_constraint"
        nwo.physics_constraint_uses_limits = True
        nwo.hinge_constraint_minimum = radians(self.limit_min_angle)
        nwo.hinge_constraint_maximum = radians(self.limit_max_angle)

class Ragdoll(Hinge):
    def __init__(self, element: TagFieldBlockElement, nodes: list[str]):
        super().__init__(element, nodes)
        self.min_twist = element.SelectField("min twist").Data
        self.max_twist = element.SelectField("max twist").Data
        self.cone = element.SelectField("max cone").Data
        self.min_plane = element.SelectField("min plane").Data
        self.max_plane = element.SelectField("max plane").Data
            
    def _set_constraint_props(self, nwo):
        nwo.physics_constraint_type = "_connected_geometry_marker_type_physics_socket_constraint"
        nwo.physics_constraint_uses_limits = True
        nwo.cone_angle = radians(self.cone)
        nwo.plane_constraint_minimum = radians(self.min_plane)
        nwo.plane_constraint_maximum = radians(self.max_plane)
        nwo.twist_constraint_start = radians(self.min_twist)
        nwo.twist_constraint_end = radians(self.max_twist)
            
class Constraint:
    def to_object(self) -> bpy.types.Object:
        pass
    
class ShapeType(Enum):
    sphere = 0
    pill = 1
    box = 2
    triangle = 3
    polyhedron = 4
    multi_sphere = 5
    unused_0 = 6
    unused_1 = 7
    unused_2 = 8
    unused_3 = 9
    unused_4 = 10
    unused_5 = 11
    unused_6 = 12
    unused_7 = 13
    _list = 14
    mopp = 15
    
class Shape:
    def __init__(self, element: TagFieldBlockElement, materials: list[str], for_bsp=False):
        if for_bsp:
            self.name = "instance_physics"
            self.material_index = element.SelectField("LongInteger:material index").Data
            self.material = materials[self.material_index]
        else:
            base = element.SelectField("Struct:base").Elements[0]
            self.name = base.SelectField("name").Data
            self.material_index = base.SelectField("material").Value
            self.material = materials[self.material_index]
    
class Sphere(Shape):
    def __init__(self, element: TagFieldBlockElement, materials):
        super().__init__(element, materials)
        self.radius = element.SelectField("Struct:translate shape[0]/Struct:convex[0]/Real:radius").Data * 100
        self.translation = Vector([n for n in element.SelectField("Struct:translate shape[0]/RealVector3d:translation").Data]) * 100
        self.matrix = Matrix.Translation(self.translation)
        
    def to_object(self) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(self.name)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=self.radius)
        bm.to_mesh(mesh)
        bm.free()
        self.ob = bpy.data.objects.new(self.name, mesh)
        self.ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_sphere"

class Pill(Shape):
    def __init__(self, element: TagFieldBlockElement, materials):
        super().__init__(element, materials)
        radius = element.SelectField("Struct:capsule shape[0]/Real:radius").Data
        bottom = Vector([n for n in element.SelectField("bottom").Data])
        top = Vector([n for n in element.SelectField("top").Data])
        self.radius = radius * 100
        self.bottom = bottom * 100
        self.top = top * 100
        difference_vector = top - bottom
        self.rotation = difference_vector.normalized().to_track_quat('Z', 'X')
        height = difference_vector.length * 100
        inverse = (self.bottom - self.top).normalized() * self.radius
        self.translation = self.bottom + inverse
        self.matrix = Matrix.LocRotScale(self.translation, self.rotation, Vector((self.radius, self.radius, (self.radius + (height / 2)))))
        
    def to_object(self) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(self.name)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=1, radius2=1, depth=2)
        bm.transform(Matrix.Translation((0, 0, 1)))
        bm.to_mesh(mesh)
        bm.free()
        self.ob = bpy.data.objects.new(self.name, mesh)
        self.ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_pill"

class Box(Shape):
    def __init__(self, element: TagFieldBlockElement, materials, corinth: bool):
        super().__init__(element, materials)
        self.translation = Vector([n for n in element.SelectField("Struct:convex transform shape[0]/RealVector3d:translation").Data]) * 100
        radius = element.SelectField("Struct:box shape[0]/Real:radius").Data
        self.width, self.length, self.height = ((n + radius) * 2 * 100 for n in element.SelectField("RealVector3d:half extents").Data)
        ii, ij, ik = element.SelectField("Struct:convex transform shape[0]/RealVector3d:rotation i").Data
        ji, jj, jk = element.SelectField("Struct:convex transform shape[0]/RealVector3d:rotation j").Data
        ki, kj, kk = element.SelectField("Struct:convex transform shape[0]/RealVector3d:rotation k").Data
        # iw = element.SelectField("Struct:convex transform shape[0]/Real:havok w rotation i").Data
        # jw = element.SelectField("Struct:convex transform shape[0]/Real:havok w rotation j").Data
        # kw = element.SelectField("Struct:convex transform shape[0]/Real:havok w rotation k").Data
        
        rotation = self.calculate_box_rotation(ii, ik, ij, ji, jj, jk, ki, kj, kk)
            
        self.matrix = Matrix.LocRotScale(self.translation, rotation, Vector((self.width, self.length, self.height)))
    
    @staticmethod
    def calculate_box_rotation(ii, ik, ij, ji, jj, jk, ki, kj, kk):
        #TODO this doesn't quite work right for corinth, need to figure this out
        qw = math.sqrt(max(0, 1 + ii + jj + kk)) / 2
        qx = math.sqrt(max(0, 1 + ii - jj - kk)) / 2
        qy = math.sqrt(max(0, 1 - ii + jj - kk)) / 2
        qz = math.sqrt(max(0, 1 - ii - jj + kk)) / 2

        qx = math.copysign(qx, ki - ik)
        qy = math.copysign(qy, kj - jk)
        qz = math.copysign(qz, ji - ij)

        return Quaternion((qw, qx, qy, qz))
        
    def to_object(self):
        mesh = bpy.data.meshes.new(self.name)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.create_cube(bm, size=1)
        bm.to_mesh(mesh)
        bm.free()
        self.ob = bpy.data.objects.new(self.name, mesh)
        self.ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_box"
        
class PolyhedronFourVectors:
    def __init__(self, element: TagFieldBlockElement):
        a = element.SelectField("four vectors x").Data
        b = element.SelectField("four vectors y").Data
        c = element.SelectField("four vectors z").Data
        d = element.SelectField("havok w four vectors x").Data, element.SelectField("havok w four vectors y").Data, element.SelectField("havok w four vectors z").Data
        
        self.xi, self.yi, self.zi = a[0], b[0], c[0]
        self.xj, self.yj, self.zj = a[1], b[1], c[1]
        self.xk, self.yk, self.zk = a[2], b[2], c[2]
        self.xw, self.yw, self.zw = d
        
    def to_vectors(self) -> list[Vector]:
        vectors = []
        vectors.append(Vector((self.xi, self.yi, self.zi)) * 100)
        vectors.append(Vector((self.xj, self.yj, self.zj)) * 100)
        vectors.append(Vector((self.xk, self.yk, self.zk)) * 100)
        vectors.append(Vector((self.xw, self.yw, self.zw)) * 100)
        
        return vectors
        
class Polyhedron(Shape):
    def __init__(self, element: TagFieldBlockElement, materials, vectors_block: TagFieldBlockElement, four_vectors_map: list, for_bsp=False):
        super().__init__(element, materials, for_bsp)
        if for_bsp:
            four_vectors_size = element.SelectField("Struct:polyhedron[0]/LongInteger:four vectors size").Data
        else:
            four_vectors_size = element.SelectField("four vectors size").Data
        self.vertices = []
        self.offset = four_vectors_map[element.ElementIndex] - four_vectors_size
        for i in range(self.offset, self.offset + four_vectors_size):
            four_vectors = PolyhedronFourVectors(vectors_block.Elements[i])
            self.vertices.extend(four_vectors.to_vectors())
            
        self.matrix = Matrix.Identity(4)
        if for_bsp:
            self.radius = element.SelectField("Struct:polyhedron[0]/Struct:polyhedron shape[0]/Real:radius").Data
        else:
            self.radius = element.SelectField("Struct:polyhedron shape[0]/Real:radius").Data
            
    def to_object(self) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(vertices=self.vertices, edges=[], faces=[])
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.convex_hull(bm, input=bm.verts)
        # scale_factor = self.radius * 2 + 1
        # bmesh.ops.scale(bm, vec=Vector((scale_factor, scale_factor, scale_factor)), verts=bm.verts)
        bm.to_mesh(mesh)
        bm.free()
        self.ob = bpy.data.objects.new(self.name, mesh)
        return self.ob
    
class RigidBody:
    def __init__(self, element: TagFieldBlockElement, region, permutation, materials, four_vectors_map, tag, list_shapes_offset, corinth: bool):
        self.valid = False
        self.list_shapes_offset = list_shapes_offset
        self.index = element.ElementIndex
        if tag.corinth and element.SelectField("ShortBlockIndex:serialized shapes").Value > -1:
            return utils.print_warning(f"Serialized Shapes are not supported. Skipping Rigid body {self.index}")
        self.node_index = element.SelectField("node").Value
        self.region = region
        self.permuation = permutation
        shape_element = element.SelectField("Struct:shape reference").Elements[0]
        self.shape_type = ShapeType(shape_element.SelectField("shape type").Value)
        self.shapes = []
        shape_index = shape_element.SelectField("shape").Value
        self.get_shape(shape_index, materials, four_vectors_map, tag, list_shapes_offset, corinth)
        self.valid = True
        
    def get_shape(self, shape_index, materials, four_vectors_map, tag, list_shapes_offset, corinth: bool):
        match self.shape_type:
            case ShapeType.sphere:
                self.shapes.append(Sphere(tag.block_spheres.Elements[shape_index], materials))
            case ShapeType.pill:
                self.shapes.append(Pill(tag.block_pills.Elements[shape_index], materials))
            case ShapeType.box:
                self.shapes.append(Box(tag.block_boxes.Elements[shape_index], materials, corinth))
            case ShapeType.polyhedron:
                self.shapes.append(Polyhedron(tag.block_polyhedra.Elements[shape_index], materials, tag.block_polyhedron_four_vectors, four_vectors_map))
                self.four_vectors_offset = self.shapes[-1].offset
            case ShapeType.mopp | ShapeType._list:
                if self.shape_type == ShapeType.mopp:
                    mopp = tag.block_mopps.Elements[shape_index]
                    if corinth:
                        self.shape_type = ShapeType(mopp.SelectField("Struct:childShapePointer[0]/ShortEnum:shape type").Value)
                        return self.get_shape(mopp.SelectField("Struct:childShapePointer[0]/ShortBlockIndexCustomSearch:shape").Value, materials, four_vectors_map, tag, list_shapes_offset, corinth)
                    else:
                        list_element = tag.block_lists.Elements[mopp.SelectField("list").Value]
                else:
                    list_element = tag.block_lists.Elements[shape_index]
                    
                list_shapes_count = list_element.SelectField("child shapes size").Data
                self.list_shapes_offset += list_shapes_count
                for i in range(list_shapes_offset, list_shapes_offset + list_shapes_count):
                    l_element = tag.block_list_shapes.Elements[i]
                    list_shape_ref = l_element.SelectField("Struct:shape reference").Elements[0]
                    list_shape_index = list_shape_ref.SelectField("shape").Value
                    match ShapeType(list_shape_ref.SelectField("shape type").Value):
                        case ShapeType.sphere:
                            self.shapes.append(Sphere(tag.block_spheres.Elements[list_shape_index], materials))
                        case ShapeType.pill:
                            self.shapes.append(Pill(tag.block_pills.Elements[list_shape_index], materials))
                        case ShapeType.box:
                            self.shapes.append(Box(tag.block_boxes.Elements[list_shape_index], materials, corinth))
                        case ShapeType.polyhedron:
                            self.shapes.append(Polyhedron(tag.block_polyhedra.Elements[list_shape_index], materials, tag.block_polyhedron_four_vectors, four_vectors_map))
                            self.four_vectors_offset = self.shapes[-1].offset
                        case _:
                            print(f"Unsupported physics shape type: {self.shape_type.name}")
            case _:
                print(f"Unsupported physics shape type: {self.shape_type.name}")
                
    def to_objects(self) -> bpy.types.Object:
        for shape in self.shapes:
            shape.to_object()
            
            render_mat = bpy.data.materials.get("Physics")
            if not render_mat:
                render_mat = bpy.data.materials.new("Physics")
                render_mat.use_fake_user = True
                render_mat.diffuse_color = special_materials.Physics.color
                render_mat.use_nodes = True
                bsdf = render_mat.node_tree.nodes[0]
                bsdf.inputs[0].default_value = special_materials.Physics.color
                bsdf.inputs[4].default_value = special_materials.Physics.color[3]
                render_mat.surface_render_method = 'BLENDED'
                
            shape.ob.data.materials.append(render_mat)
            shape.ob.data.nwo.mesh_type = "_connected_geometry_mesh_type_physics"
            if shape.material.name != "default":
                shape.ob.data.nwo.face_global_material = shape.material.name
        
            
class CollisionMaterial:
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.name = element.Fields[0].Data

class BSPCollisionMaterial:
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.render_method = ""
        self.tag_shader = None
        self.name = ""
        render = element.SelectField("Reference:render method").Path
        if render:
            self.render_method = render.RelativePathWithExtension
            self.tag_shader = render
            self.name = render.ShortName
        
        self.global_material = ""
        if utils.is_corinth():
            override = element.SelectField("override material name").Data
            if override:
                self.global_material = override
                
        if not self.global_material and render and Path(render.Filename).exists():
            if utils.is_corinth():
                with MaterialTag(path=self.render_method) as shader:
                    self.global_material = shader.tag.SelectField("physics material name").Data
            else:
                with ShaderTag(path=self.render_method) as shader:
                    self.global_material = shader.tag.SelectField("material name").Data
        
        if self.name:
            self.blender_material = get_blender_material(self.name, self.render_method)
        else:
            self.blender_material = None
            
        seam_flag = element.SelectField("WordFlags:flags")
        self.is_seam = seam_flag.TestBit("is seam")
        
class CollisionVertex:
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.element = element
        self.point = element.Fields[0].Data
        self.first_edge = utils.unsigned_int16(element.Fields[1].Data)
        
    @property
    def position(self) -> Vector:
        return Vector(self.point) * 100
        
class CollisionSurface:
    def __init__(self, element: TagFieldBlockElement, materials: list[CollisionMaterial] | list[BSPCollisionMaterial]):
        self.index = element.ElementIndex
        self.first_edge = utils.unsigned_int16(element.SelectField("first edge").Data)
        material_index = element.SelectField("material").Data
        if material_index < 0 or material_index >= len(materials):
            self.material = None
        else:
            self.material = materials[material_index]
        flags = element.SelectField("flags")
        self.negated = flags.TestBit("plane negated")
        self.invalid = flags.TestBit("invalid")
        self.ladder = flags.TestBit("climbable")
        self.breakable = flags.TestBit("breakable")
        self.slip_surface = flags.TestBit("slip")
        self.invisible = flags.TestBit("invisible")
        self.two_sided = flags.TestBit("two sided") and not (self.breakable or self.invisible)
        
class CollisionEdge:
    def __init__(self, element: TagFieldBlockElement):
        self.element = element
        self.index = element.ElementIndex
        self.start_vertex = utils.unsigned_int16(element.SelectField("start vertex").Data)
        self.end_vertex = utils.unsigned_int16(element.SelectField("end vertex").Data)
        self.forward_edge = utils.unsigned_int16(element.SelectField("forward edge").Data)
        self.reverse_edge = utils.unsigned_int16(element.SelectField("reverse edge").Data)
        self.left_surface = utils.unsigned_int16(element.SelectField("left surface").Data)
        self.right_surface = utils.unsigned_int16(element.SelectField("right surface").Data)
        
class BSP:
    def __init__(self, element: TagFieldBlockElement, name, materials: list[CollisionMaterial]):
        self.name = name
        # self.index = element.ElementIndex
        self.uses_materials = False
        self.surfaces = [CollisionSurface(e, materials) for e in element.SelectField("Block:surfaces").Elements]
        self.vertices = [CollisionVertex(e) for e in element.SelectField("Block:vertices").Elements]
        self.edges = [CollisionEdge(e) for e in element.SelectField("Block:edges").Elements]
        
        self.sphere_collision_only = all(surf.invisible for surf in self.surfaces)
        self.some_sphere_collision = any(surf.invisible for surf in self.surfaces)
        
        self.sky_index = -1
        
    def yield_indices(self):
        surfaces = self.surfaces
        for surface in surfaces:
            first_edge = self.edges[surface.first_edge]
            edge = first_edge
            polygon = []
            
            while True:
                if edge.left_surface == surface.index:
                    polygon.append(edge.start_vertex)
                    next_edge_index = edge.forward_edge
                else:
                    polygon.append(edge.end_vertex)
                    next_edge_index = edge.reverse_edge
                
                if next_edge_index == surface.first_edge:
                    break
                
                edge = self.edges[next_edge_index]
            
            yield polygon
        
    def to_bvh(self):
        verts = [Vector(v.position) for v in self.vertices]
        tris = []

        for poly in self.yield_indices():
            if len(poly) == 3:
                tris.append(tuple(poly))
            elif len(poly) > 3:
                # face_verts is a list of vertex indices
                face_verts = [verts[i] for i in poly]
                # tessellate_polygon returns triangles as tuples of indices (0..len(poly)-1)
                tri_indices = tessellate_polygon([face_verts])
                for tri in tri_indices:
                    tris.append(tuple(poly[i] for i in tri))
            # ignore degenerate faces (<3 verts)

        if tris:
            return bvhtree.BVHTree.FromPolygons(verts, tris)
        
    def to_object(self, mesh_only=False, surface_indices=[], cookie_cutter=False) -> bpy.types.Object:
                
        indices = self.yield_indices()
        # Create the bpy mesh
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(vertices=[v.position for v in self.vertices], edges=[], faces=list(indices))
        any_ladder = any_breakable = any_slip = any_invisible = False
        # Check if we need to set any per face properties
        map_material, map_two_sided, map_ladder, map_breakable, map_slip, map_negated, map_invalid, map_invisible = [], [], [], [], [], [], [], []
        for surface in self.surfaces:
            material = surface.material
            two_sided = surface.two_sided
            ladder = surface.ladder
            breakable = surface.breakable
            slip = surface.slip_surface
            negated = surface.negated
            invalid = surface.invalid
            invisible = surface.invisible
            
            if ladder:
                any_ladder = True
            if breakable:
                any_breakable = True
            if slip:
                any_slip = True
            if invisible:
                any_invisible = True
            
            map_material.append(material)
            map_two_sided.append(two_sided)
            map_ladder.append(ladder)
            map_breakable.append(breakable)
            map_slip.append(slip)
            map_negated.append(negated)
            map_invalid.append(invalid)
            map_invisible.append(invisible)
            
        # map_negated_and_not_two_sided = np.logical_and(map_negated, np.logical_not(two_sided))

        materials_set = set(map_material)
        two_sided_set = set(map_two_sided)
        ladder_set = set(map_ladder)
        breakable_set = set(map_breakable)
        slip_set = set(map_slip)
        negated_set = set(map_negated)
        invisible_set = set(map_invisible)

        split_material = len(materials_set) > 1
        split_two_sided = len(two_sided_set) > 1
        split_ladder = len(ladder_set) > 1
        split_breakable = len(breakable_set) > 1
        split_slip = len(slip_set) > 1
        split_negated = len(negated_set) > 1
        split_invisible = len(invisible_set) > 1

        blender_materials_map = {}
        
        if self.uses_materials:
            if split_material:
                for idx, mat in enumerate(sorted(materials_set, key=lambda x: x.name if x is not None else "+")):
                    if mat is None:
                        if isinstance(self, StructureCollision):
                            sky_suffix = self.sky_index if self.sky_index > -1 else ""
                            bmat = get_blender_material(f"+sky{sky_suffix}")
                        else:
                            bmat = get_blender_material("+seamsealer")
                            
                        mesh.materials.append(bmat)
                        blender_materials_map[mat] = idx
                    elif mat.is_seam:
                        bmat = get_blender_material("+seam")
                        mesh.materials.append(bmat)
                        blender_materials_map[mat] = idx
                    else:
                        mesh.materials.append(mat.blender_material)
                        blender_materials_map[mat] = idx
            elif surface.material:
                mesh.materials.append(surface.material.blender_material)
        
        if any_ladder:
            utils.add_face_prop(mesh, "ladder", map_ladder if split_ladder else None)
        if any_breakable:
            utils.add_face_prop(mesh, "face_mode", map_breakable if split_breakable else None).face_mode = 'breakable'
        if any_slip:
            utils.add_face_prop(mesh, "slip_surface", map_slip if split_slip else None)
        if any_invisible:
            utils.add_face_prop(mesh, "face_mode", map_invisible if split_invisible else None).face_mode = 'sphere_collision_only'
        
        if self.uses_materials:
            if split_material:
                material_indices = [blender_materials_map[mat] for mat in map_material]
                mesh.polygons.foreach_set("material_index", material_indices)
        elif not cookie_cutter:
            if split_material:
                indices = np.asarray([s.material.index for s in self.surfaces])
                for mat in materials_set:
                    material_indices = indices == mat.index
                    utils.add_face_prop(mesh, "global_material", material_indices).global_material = mat.name
            elif materials_set:
                utils.add_face_prop(mesh, "global_material").global_material = surface.material.name

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        # bmesh.ops.delete(bm, geom=[bm.faces[i] for i in invalid_indices], context='FACES')
        
        to_remove = set(np.nonzero(map_invalid)[0])
        # bad_faces = set(np.nonzero(map_negated_and_not_two_sided)[0])
        
        # if bad_faces:
        #     bad_vert_coords = [set([v.co.to_tuple() for v in f.verts]) for f in bm.faces if f.index in bad_faces]
        #     final_bad_faces = [f.index for f in bm.faces if set(v.co.to_tuple() for v in f.verts) in bad_vert_coords]
        #     to_remove.update(set(final_bad_faces))
            
                    
        if surface_indices:
            to_remove.update({idx for idx in range(len(bm.faces)) if idx not in set(surface_indices)})
        
        # print(to_remove)
        
        if to_remove:
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in to_remove], context='FACES')
        
        bm.to_mesh(mesh)
        bm.free()
        
        utils.set_two_sided(mesh)
        
        utils.calc_face_prop_counts(mesh)
        
        if mesh_only:
            return mesh
        
        ob = bpy.data.objects.new(self.name, mesh)
        if cookie_cutter:
            mesh.nwo.mesh_type = "_connected_geometry_mesh_type_cookie_cutter"
            apply_props_material(ob, "CookieCutter")
        elif not self.uses_materials:
            mesh.nwo.mesh_type = "_connected_geometry_mesh_type_collision"
            apply_props_material(ob, 'Collision')
        return ob
    
class ModelCollision(BSP):
    def __init__(self, element: TagFieldBlockElement, name, collision_materials: list[CollisionMaterial], nodes: list[str] = None):
        super().__init__(element.SelectField("Struct:bsp").Elements[0], name, collision_materials)
        self.node_index = element.Fields[0].Data
        self.bone = ""
        if nodes:
            self.bone = nodes[self.node_index]
    
class InstanceCollision(BSP):
    def __init__(self, element: TagFieldBlockElement, name, collision_materials: list[CollisionMaterial]):
        super().__init__(element, name, collision_materials)
        self.uses_materials = True
        
class InstancePhysics():
    def __init__(self, element: TagFieldBlockElement, name, physics_materials: list[CollisionMaterial]):
        polyhedra_block = element.SelectField("Block:polyhedra_with_materials")
        four_vectors_block = element.SelectField("Block:polyhedron four vectors")
        four_vectors_map = []
        self.polyhedra: list[Polyhedron] = []
        for poly_element in polyhedra_block.Elements:
            size = poly_element.SelectField("Struct:polyhedron[0]/LongInteger:four vectors size").Data
            if poly_element.ElementIndex == 0:
                four_vectors_map.append(size)
            else:
                four_vectors_map.append(size + four_vectors_map[-1])
                
            self.polyhedra.append(Polyhedron(poly_element, physics_materials, four_vectors_block, four_vectors_map, True))
        
class StructureCollision(BSP):
    def __init__(self, element: TagFieldBlockElement, name, collision_materials: list[CollisionMaterial], sky_index: int):
        super().__init__(element, name, collision_materials)
        self.uses_materials = True
        self.sky_index = sky_index
    
class PathfindingSphere:
    def __init__(self, element: TagFieldBlockElement, nodes: list[str] = None):
        self.index = element.ElementIndex
        self.node_index = element.Fields[0].Value
        self.bone = ""
        if nodes:
            self.bone = nodes[self.node_index]
            
        flags = element.SelectField("flags")
        self.when_open = flags.TestBit("remains when open")
        self.vehicle = flags.TestBit("vehicle only")
        self.sectors = flags.TestBit("with sectors")
        self.center = element.SelectField("center").Data
        self.radius = element.SelectField("radius").Data
        
    def to_object(self):
        name = "pathfinding_sphere"
        if self.when_open:
            name += "::remains_when_open"
        if self.vehicle:
            name += "::vehicle"
        if self.sectors:
            name += "::sectors"
            
        ob = bpy.data.objects.new(name, None)
        ob.empty_display_size = self.radius * 100
        ob.empty_display_type = 'SPHERE'
        ob.nwo.marker_type = "_connected_geometry_marker_type_pathfinding_sphere"
        
        return ob
        
            
class CompressionBounds:
    def __init__(self, element: TagFieldBlockElement):
        first = element.SelectField("position bounds 0").Data
        second = element.SelectField("position bounds 1").Data
        
        self.x0 = first[0] * 100
        self.x1 = first[1] * 100
        self.y0 = first[2] * 100
        self.y1 = second[0] * 100
        self.z0 = second[1] * 100
        self.z1 = second[2] * 100
        
        self.co_matrix = Matrix((
            (self.x1-self.x0, 0, 0, self.x0),
            (0, self.y1-self.y0, 0, self.y0),
            (0, 0, self.z1-self.z0, self.z0),
            (0, 0, 0, 1),
        ))
        
        third = element.SelectField("texcoord bounds 0").Data
        fourth = element.SelectField("texcoord bounds 1").Data
        
        self.u0 = third[0]
        self.u1 = third[1]
        self.v0 = fourth[0]
        self.v1 = fourth[1]
        
class Emissive:
    def __init__(self, element: TagFieldBlockElement):
        self.power = element.Fields[0].Data
        self.color = tuple([utils.srgb_to_linear(n) for n in element.Fields[1].Data])
        self.quality = element.Fields[2].Data
        self.focus = element.Fields[3].Data
        flags = element.Fields[4]
        self.power_per_unit_area = flags.TestBit("power per unit area")
        self.use_shader_gel = flags.TestBit("use shader gel")
        self.attenuation_falloff = element.Fields[5].Data
        self.attenuation_cutoff = element.Fields[6].Data
        self.bounce_ratio = element.Fields[7].Data

class Material:
    def __init__(self, element: TagFieldBlockElement, emissives: list[Emissive] = [], for_bsp=False):
        self.index = element.ElementIndex
        render_method_path = element.SelectField("render method").Path
        self.name = render_method_path.ShortName
        self.new = not bool(bpy.data.materials.get(self.name, 0))
        self.shader_path = render_method_path.RelativePathWithExtension
        self.emissive_index = element.SelectField("imported material index").Data
        self.lm_res = int(element.SelectField("Real:lightmap resolution scale").Data)
        self.lm_transparency = element.SelectField("lightmap additive transparency color").Data
        self.lm_translucency = element.SelectField("lightmap traslucency tint color").Data
        flags = element.SelectField("lightmap flags")
        self.lm_both_sides = flags.TestBit("lighting from both sides")
        self.lm_transparency_override = flags.TestBit("transparency override")
        self.lm_ignore_default_res = flags.TestBit("ignore default resolution scale")
        self.lm_chart_group_index = element.SelectField("ShortInteger:lightmap chart group index").Data
        self.breakable_surface_index = element.SelectField("breakable surface index").Data
        
        self.lm_analytical_absorb = element.SelectField("Real:lightmap analytical light absorb").Data
        self.lm_normal_absorb = element.SelectField("Real:lightmap normal light absorb").Data
        
        self.emissive_invalid = False
        
        self.blender_material = get_blender_material(self.name, self.shader_path)
        
        # Emissive Properties
        self.emissive: Emissive = None
        if for_bsp:
            if self.emissive_index > -1:
                if self.emissive_index < len(emissives):
                    emissive = emissives[self.emissive_index]
                    if emissive.power > 0:
                        self.emissive = emissive
                        # self.blender_material.nwo.emits = True
                elif emissives or self.emissive_index > 0:
                    self.emissive_invalid = True
                    utils.print_warning(f"Invalid emissive on tag material {self.name}, material index={self.index}, emissive index={self.emissive_index}")
    
class IndexLayoutType(Enum):
    DEFAULT = 0
    LINE_LIST = 1
    LINE_STRIP = 2
    TRIANGLE_LIST = 3
    TRIANGLE_FAN = 4
    TRIANGLE_STRIP = 5
    QUAD_LIST = 6
    RECT_LIST = 7
    
class IndexBuffer:
    def __init__(self, index_buffer_type: int, indices: list[int]):
        self.index_layout = IndexLayoutType(index_buffer_type)
        self.indices = indices

    def get_faces(self, mesh: 'Mesh', subparts=None) -> list[Face]:
        idx = 0
        faces = []
        if mesh.subparts:
            if subparts is None:
                for subpart in mesh.subparts:
                    start = subpart.index_start
                    count = subpart.index_count
                    list_indices = list(self._get_indices(start, count))
                    indices = [list_indices[n:n+3] for n in range(0, len(list_indices), 3) if len(list_indices[n:n+3]) == 3]
                    for i in indices:
                        faces.append(Face(indices=i, subpart=subpart, index=idx))
                        idx += 1
            else:
                for subpart in subparts:
                    start = subpart.index_start
                    count = subpart.index_count
                    list_indices = list(self._get_indices(start, count))
                    indices = [list_indices[n:n+3] for n in range(0, len(list_indices), 3) if len(list_indices[n:n+3]) == 3]
                    for i in indices:
                        faces.append(Face(indices=i, subpart=subpart, index=idx))
                        idx += 1
        else:
            start = 0
            count = len(self.indices)
            list_indices = list(self._get_indices(start, count))
            indices = [list_indices[n:n+3] for n in range(0, len(list_indices), 3) if len(list_indices[n:n+3]) == 3]
            for i in indices:
                faces.append(Face(indices=i, subpart=None, index=idx))
                idx += 1
                
        return faces

    def _get_indices(self, start: int, count: int):
        end = len(self.indices) if count < 0 else start + count
        subset = (self.indices[i] for i in range(start, end))
        if self.index_layout == IndexLayoutType.TRIANGLE_LIST:
            return subset
        elif self.index_layout == IndexLayoutType.TRIANGLE_STRIP:
            return self._unpack(subset)
        else:
            raise ValueError(f"Unsupported Index Layout Type {self.index_layout}")

    def _unpack(self, indices) -> list[int]:
        indices = list(indices)
        for pos in range(len(indices) - 2):
            if indices[pos] == indices[pos+1] or indices[pos] == indices[pos+2] or indices[pos+1] == indices[pos+2]:
                continue  # Skip degenerate triangles
            if pos % 2 == 0:
                yield indices[pos]
                yield indices[pos+1]
                yield indices[pos+2]
            else:
                yield indices[pos]
                yield indices[pos+2]
                yield indices[pos+1]
                
class Tessellation(Enum):
    none = 0
    _4x = 1
    _9x = 2
    _36x = 3
    
class DrawDistance(Enum):
    normal = 0
    detail_mid = 1
    detail_close = 2

class MeshPart:    
    def __init__(self, element: TagFieldBlockElement, materials: list[Material]):
        self.index = element.ElementIndex
        self.material_index = element.SelectField("render method index").Value
        self.index_start = element.SelectField("index start").Data
        self.index_count = element.SelectField("index count").Data
        
        self.draw_distance = DrawDistance.normal
        flags = element.SelectField("part flags")
        if flags.TestBit("draw cull distance close"):
            self.draw_distance = DrawDistance.detail_close
        elif flags.TestBit("draw cull distance medium"):
            self.draw_distance = DrawDistance.detail_mid
            
        self.lm_type_per_vertex = flags.TestBit("per vertex lightmap part")
        
        self.water_surface = False
        if flags.TestBit("is water surface"):
            self.water_surface = True
            
        self.part_type = PartType(element.SelectField("part type").Data)
        self.tessellation = Tessellation(element.SelectField("tessellation").Value)
        self.material = next((m for m in materials if m.index == self.material_index), None)
        if self.material is None:
            invalid_mat = bpy.data.materials.get("invalid")
            if invalid_mat is None:
                invalid_mat = bpy.data.materials.new("invalid")
            self.material = invalid_mat
            
class MeshSubpart:
    def __init__(self, element: TagFieldBlockElement, parts: list[MeshPart], water_indices: list[int]):
        self.index = element.ElementIndex
        self.index_start = element.SelectField("index start").Data
        self.index_count = element.SelectField("index count").Data
        self.part_index = element.SelectField("part index").Value
        self.part = next(p for p in parts if p.index == self.part_index)
        self.is_water_subpart = self.index_start in water_indices
        self.is_water_surface = self.part and self.part.water_surface
        
    def remove(self, ob: bpy.types.Object, tris: Face):
        indices = (t.index for t in tris if t.subpart is self)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in indices], context='FACES')
        bm.to_mesh(ob.data)
        bm.free()
        
    def create(self, ob: bpy.types.Object, tris: Face):
        mesh = ob.data
        material = self.part.material
        blend_material = material.blender_material

        for idx, mat in enumerate(mesh.materials):
            if mat == blend_material:
                blend_material_index = idx
                break
        else:
            blend_material_index = len(mesh.materials)
            mesh.materials.append(blend_material)

        indices = [t.index for t in tris if t.subpart is self]
        all_indices = np.zeros(len(mesh.polygons), dtype=np.int8)
        all_indices[indices] = True
        
        for i in indices:
            mesh.polygons[i].material_index = blend_material_index
            
        corinth = utils.is_corinth(bpy.context)
            
        if self.is_water_surface:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            water_layer = bm.faces.layers.bool.get('foundry_water')
            if water_layer is None:
                water_layer = bm.faces.layers.bool.new('foundry_water')
            
            bm.faces.ensure_lookup_table()
            for i in indices:
                bm.faces[i][water_layer] = True
                
            bm.to_mesh(mesh)
            bm.free()

        if self.part.part_type == PartType.transparent:
            utils.add_face_prop(mesh, "transparent", all_indices)
        elif self.part.part_type == PartType.opaque_non_shadowing:
            utils.add_face_prop(mesh, "no_shadow", all_indices)
        elif self.part.part_type == PartType.opaque_shadow_only:
            utils.add_face_prop(mesh, "face_mode", all_indices).face_mode = 'shadow_only'
        elif self.part.part_type == PartType.lightmap_only:
            utils.add_face_prop(mesh, "face_mode", all_indices).face_mode = 'lightmap_only'
        if self.part.draw_distance.value > 0:
            utils.add_face_prop(mesh, "draw_distance", all_indices).draw_distance = self.part.draw_distance.name
        if self.part.tessellation.value > 0:
            utils.add_face_prop(mesh, "mesh_tessellation_density", all_indices).mesh_tessellation_density = self.part.tessellation.name
        
        if self.part.lm_type_per_vertex:
            utils.add_face_prop(mesh, "lightmap_type", all_indices)
            
        # Material Props
        if not corinth and material.lm_res != LIGHTMAP_RESOLUTION_SCALE and material.lm_res != 0.0:
            res = 3
            if material.lm_res < 1:
                res = "1"
            elif material.lm_res > 7:
                res = "7"
            else:
                res = str(material.lm_res)
            utils.add_face_prop(mesh, "lightmap_resolution_scale", all_indices).lightmap_resolution_scale = res
            
        if material.lm_ignore_default_res != LIGHTMAP_IGNORE_DEFAULT_RESOLUTION_SCALE:
            utils.add_face_prop(mesh, "lightmap_ignore_default_resolution_scale", all_indices).lightmap_ignore_default_resolution_scale = material.lm_ignore_default_res
            
        if material.lm_chart_group_index != LIGHTMAP_CHART_GROUP_INDEX:
            utils.add_face_prop(mesh, "lightmap_chart_group", all_indices).lightmap_chart_group = material.lm_chart_group_index
            
        if material.lm_transparency != LIGHTMAP_ADDITIVE_TRANSPARENCY_COLOR:
            utils.add_face_prop(mesh, "lightmap_additive_transparency", all_indices).lightmap_additive_transparency = utils.argb32_to_rgb(material.lm_transparency)
            
        if material.lm_transparency_override != LIGHTMAP_TRANSPARENCY_OVERRIDE:
            utils.add_face_prop(mesh, "lightmap_transparency_override", all_indices).lightmap_transparency_override = material.lm_transparency_override
            
        if material.lm_analytical_absorb != LIGHTMAP_ANALYTICAL_LIGHT_ABSORB and material.lm_analytical_absorb != 1.0:
            utils.add_face_prop(mesh, "lightmap_analytical_bounce_modifier", all_indices).lightmap_analytical_bounce_modifier = material.lm_analytical_absorb
            
        if material.lm_normal_absorb != LIGHTMAP_NORMAL_LIGHT_ABSORD and material.lm_normal_absorb != 1.0:
            utils.add_face_prop(mesh, "lightmap_general_bounce_modifier", all_indices).lightmap_general_bounce_modifier = material.lm_normal_absorb
            
        if material.lm_translucency != LIGHTMAP_TRANSLUCENCY_TINT_COLOR:
            utils.add_face_prop(mesh, "lightmap_translucency_tint_color", all_indices).lightmap_translucency_tint_color = utils.argb32_to_rgb(material.lm_translucency)
            
        if material.lm_both_sides != LIGHTMAP_LIGHTING_FROM_BOTH_SIDES:
            utils.add_face_prop(mesh, "lightmap_lighting_from_both_sides", all_indices).lightmap_lighting_from_both_sides = material.lm_both_sides
            
        if material.emissive is not None:
            prop = utils.add_face_prop(mesh, "emissive", all_indices)
            atten_factor = 1 if utils.is_corinth(bpy.context) else 0.01
            e = material.emissive
            prop.material_lighting_attenuation_cutoff = e.attenuation_cutoff * atten_factor * (1 / WU_SCALAR)
            prop.material_lighting_attenuation_falloff = e.attenuation_falloff * atten_factor * (1 / WU_SCALAR)
            prop.material_lighting_emissive_focus = radians(e.focus * 180)
            prop.material_lighting_emissive_color = e.color
            prop.material_lighting_emissive_per_unit = e.power_per_unit_area
            prop.light_intensity = e.power
            prop.material_lighting_emissive_quality = e.quality
            prop.material_lighting_use_shader_gel = e.use_shader_gel
            prop.material_lighting_bounce_ratio = e.bounce_ratio
        elif material.emissive_invalid:
            prop = utils.add_face_prop(mesh, "emissive", all_indices)
            prop.light_intensity = 0
            prop.debug_emissive_index = material.emissive_index
            utils.print_warning(f"Mesh {ob.data.name} has invalid emissive on material {self.part.material.name} (part {self.part_index})")
            

class Mesh:
    '''All new Halo 3 render geometry definitions!'''
    def __init__(self, element: TagFieldBlockElement, bounds: CompressionBounds = None, permutation=None, materials=[], block_node_map=None, does_not_need_parts=False, from_vert_normals=False):
        self.index = element.ElementIndex
        self.permutation = permutation
        self.rigid_node_index = element.SelectField("rigid node index").Data
        self.index_buffer_type =  element.SelectField("index buffer type").Value
        self.bounds = bounds
        self.parts: list[MeshPart] = []
        self.subparts: list[MeshSubpart] = []
        self.from_vert_normals = from_vert_normals
        
        water_indices = [e.Fields[0].Data for e in element.SelectField("Block:water indices start").Elements]
        
        for part_element in element.SelectField("parts").Elements:
            self.parts.append(MeshPart(part_element, materials))
        for subpart_element in element.SelectField("subparts").Elements:
            self.subparts.append(MeshSubpart(subpart_element, self.parts, water_indices))
            
        self.valid = (bool(self.parts) and bool(self.subparts)) or does_not_need_parts
        
        self.does_not_need_parts = does_not_need_parts
            
        self.is_pca = False
        self.uncompressed = False
        if utils.is_corinth():
            mesh_flags = element.SelectField("mesh flags")
            self.is_pca = mesh_flags.TestBit("mesh is PCA")
            self.uncompressed = mesh_flags.TestBit("use uncompressed vertex format")
            
        self.raw_positions = []
        self.raw_texcoords = []
        self.raw_normals = []
        self.raw_node_indices = []
        self.raw_node_weights = []
        
        self.node_map = []
        if block_node_map is not None and block_node_map.Elements.Count and self.index < block_node_map.Elements.Count:
            map_element = block_node_map.Elements[self.index]
            self.node_map = [utils.unsigned_int8(e.Fields[0].Data) for e in map_element.Fields[0].Elements]
        
        self.vertex_keys = []
        self.mesh_keys = []
        vertex_keys = element.SelectField("Block:vertex keys")
        if vertex_keys is not None:
            self.vertex_keys = [e.Fields[0].Data for e in vertex_keys.Elements]
            self.mesh_keys = [e.Fields[1].Data for e in vertex_keys.Elements]
                
            
    def _true_uvs(self, texcoords):
        return [self._interp_uv(tc) for tc in texcoords]
    
    def _interp_uv(self, texcoord):
        u = np.interp(texcoord[0], (0, 1), (self.bounds.u0, self.bounds.u1))
        v = np.interp(texcoord[1], (0, 1), (self.bounds.v0, self.bounds.v1))
        
        return Vector((u, 1-v)) # 1-v to correct UV for Blender
    
    def create(self, render_model, temp_meshes: TagFieldBlock, nodes=[], parent: bpy.types.Object | None = None, instances: list['InstancePlacement'] = [], name="blam", is_io=False, surface_triangle_mapping=[], section_index=0, real_mesh_index=None):
        if not self.valid:
            return []
        
        raw_mesh_index = self.index if real_mesh_index is None else real_mesh_index
        temp_mesh = temp_meshes.Elements[raw_mesh_index]
            
        raw_vertices = temp_mesh.SelectField("raw vertices")
        raw_indices = temp_mesh.SelectField("raw indices")
        if raw_indices.Elements.Count == 0:
            raw_indices = temp_mesh.SelectField("raw indices32")

        self.raw_positions = list(render_model.GetPositionsFromMesh(temp_meshes, raw_mesh_index))
        self.raw_texcoords = list(render_model.GetTexCoordsFromMesh(temp_meshes, raw_mesh_index))
        self.raw_normals = list(render_model.GetNormalsFromMesh(temp_meshes, raw_mesh_index))
        self.raw_lightmap_texcoords = [e.Fields[5].Data for e in raw_vertices.Elements]
        self.raw_vertex_colors = [e.Fields[8].Data for e in raw_vertices.Elements]
        self.raw_texcoords1 = [e.Fields[9].Data for e in raw_vertices.Elements] if utils.is_corinth() else []
        self.raw_water_texcoords = []

        if not instances and self.rigid_node_index == -1:
            self.raw_node_indices = list(render_model.GetNodeIndiciesFromMesh(temp_meshes, raw_mesh_index))
            self.raw_node_weights = list(render_model.GetNodeWeightsFromMesh(temp_meshes, raw_mesh_index))

        indices = [utils.unsigned_int16(element.Fields[0].Data) for element in raw_indices.Elements]
        buffer = IndexBuffer(self.index_buffer_type, indices)
        self.tris = buffer.get_faces(self)
        if temp_mesh.SelectField("raw water data").Elements.Count > 0:
            water_data = temp_mesh.SelectField("raw water data").Elements[0]

            raw_water_indices = water_data.Fields[0]
            water_indices_local = [utils.unsigned_int16(e.Fields[0].Data) for e in raw_water_indices.Elements]

            raw_water_vertices = water_data.Fields[1]
            self.raw_water_texcoords = [e.Fields[0].Data for e in raw_water_vertices.Elements]

            water_subparts = [sp for sp in self.subparts if sp.is_water_surface]

            water_global_index_stream = []
            for sp in water_subparts:
                s, c = sp.index_start, sp.index_count
                water_global_index_stream.extend(indices[s:s + c])

            if len(water_global_index_stream) != len(water_indices_local):
                print(f"[warn] water index count mismatch: "
                    f"global={len(water_global_index_stream)} local={len(water_indices_local)}")

            local_to_global = {}
            for gi, li in zip(water_global_index_stream, water_indices_local):
                if li not in local_to_global:
                    local_to_global[li] = gi

            vert_count = len(self.raw_positions) // 3
            full = [(0.0, 0.0)] * vert_count
            
            for local_id, uv in enumerate(self.raw_water_texcoords):
                gi = local_to_global.get(local_id)
                if gi is not None:
                    full[gi] = (float(uv[0]), float(uv[1]))

            self.raw_water_texcoords = full

        objects = []

        if instances:
            for instance in instances:
                subpart = self.subparts[instance.index]
                ob = self._create_mesh(instance.name, parent, nodes, subpart, instance.bone, instance.matrix, is_io)
                ob.scale = Vector.Fill(3, instance.scale)
                instance.ob = ob
                objects.append(ob)
        else:
            if self.permutation:
                name = f"{self.permutation.region.name}:{self.permutation.name}"
                
            ob = self._create_mesh(name, parent, nodes, None, surface_triangle_mapping=surface_triangle_mapping, section_index=section_index)
            objects.append(ob)
            
            if ob.data.attributes.get('foundry_water'):
                ob_water = ob.copy()
                ob_water.data = ob.data.copy()

                bm = bmesh.new()
                bm.from_mesh(ob.data)
                layer = bm.faces.layers.bool.get('foundry_water')
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer]], context='FACES')
                bm.faces.layers.bool.remove(layer)
                bm.to_mesh(ob.data)
                bm.free()
                
                bm = bmesh.new()
                bm.from_mesh(ob_water.data)
                layer = bm.faces.layers.bool.get('foundry_water')
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if not f[layer]], context='FACES')
                bm.faces.layers.bool.remove(layer)
                bm.to_mesh(ob_water.data)
                bm.free()
                
                ob_water.data.nwo.mesh_type = '_connected_geometry_mesh_type_water_surface'
                ob_water.nwo.water_volume_depth = 0
                
                if ob_water.data.materials:
                    utils.consolidate_materials(ob_water.data)
                    ob_water.name = ob_water.data.materials[0].name
                else:
                    ob_water.name = "water_surface"
                
                objects.append(ob_water)
        
        return objects

    def _create_mesh(self, name, parent, nodes, subpart: MeshSubpart | None, parent_bone=None, local_matrix=None, is_io=False, surface_triangle_mapping=[], section_index=0):
        matrix = local_matrix or (parent.matrix_world if parent else Matrix.Identity(4))

        indices = [t.indices for t in self.tris if not subpart or t.subpart == subpart]

        vertex_indices = sorted({idx for tri in indices for idx in tri})
        idx_start, idx_end = vertex_indices[0], vertex_indices[-1]
        
        idx_start, idx_end = vertex_indices[0], vertex_indices[-1]

        mesh = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, mesh)

        positions = [self.raw_positions[i:i+3] for i in range(idx_start * 3, (idx_end + 1) * 3, 3)]
        texcoords = [self.raw_texcoords[i:i+2] for i in range(idx_start * 2, (idx_end + 1) * 2, 2)]
        normals = [self.raw_normals[i:i+3] for i in range(idx_start * 3, (idx_end + 1) * 3, 3)]
        lighting_texcoords = [[float(v) for v in self.raw_lightmap_texcoords[n]] for n in range(idx_start, idx_end+1)]
        vertex_colors = [[float(v) for v in self.raw_vertex_colors[n]] for n in range(idx_start, idx_end+1)]
        texcoords1 = [[float(v) for v in self.raw_texcoords1[n]] for n in range(idx_start, idx_end+1)] if self.raw_texcoords1 else []
        water_texcoords = [[float(v) for v in self.raw_water_texcoords[n]] for n in range(idx_start, idx_end+1)] if self.raw_water_texcoords else []

        if idx_start > 0:
            indices = [[i - idx_start for i in tri] for tri in indices]

        mesh.from_pydata(positions, [], indices)

        transform_matrix = self.bounds.co_matrix if self.bounds else Matrix.Scale(100, 4)
        mesh.transform(transform_matrix)

        print(f"--- {name}")

        has_vertex_colors = any(any(v) for v in vertex_colors)
        has_lighting_texcoords = any(any(v) for v in lighting_texcoords)
        has_texcoords1 = bool(texcoords1) and any(any(v) for v in texcoords1)
        has_water_texcoords = bool(water_texcoords) and any(any(v) for v in water_texcoords)
        uvs = self._true_uvs(texcoords) if self.bounds else [Vector((u, 1-v)) for (u, v) in texcoords]
        if has_texcoords1:
            uvs1 = self._true_uvs(texcoords1) if self.bounds else [Vector((u, 1-v)) for (u, v) in texcoords1]
        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        lighting_uv_layer = mesh.uv_layers.new(name="lighting", do_init=False) if has_lighting_texcoords else None
        uvs1_layer = mesh.uv_layers.new(name="UVMap1", do_init=False) if has_texcoords1 else None
        
        if has_water_texcoords:
            if uvs1_layer is None:
                water_uvs_layer = mesh.uv_layers.new(name="UVMap1", do_init=False)
            else:
                water_uvs_layer = mesh.uv_layers.new(name="UVMap2", do_init=False)
                
            water_uvs = self._true_uvs(water_texcoords) if self.bounds else [Vector((u, 1-v)) for (u, v) in water_texcoords]
            

        if uv_layer:
            for face in mesh.polygons:
                for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                    uv_layer.data[loop_idx].uv = uvs[vert_idx]
                    if has_texcoords1:
                        uvs1_layer.data[loop_idx].uv = uvs1[vert_idx]
                    if has_water_texcoords:
                        water_uvs_layer.data[loop_idx].uv = water_uvs[vert_idx]
                    if lighting_uv_layer:
                        lighting_uv_layer.data[loop_idx].uv = lighting_texcoords[vert_idx]

        # normalised_normals = [Vector(n).normalized() for n in normals]
        mesh.normals_split_custom_set_from_vertices(normals)
        if self.is_pca or self.from_vert_normals: # ensures mesh reimports as closely to the original as possible, necessary for re-using PCA animation
            mesh.nwo.from_vert_normals = True

        if has_vertex_colors:
            vcolor_attribute = mesh.color_attributes.new("Color", 'FLOAT_COLOR', 'POINT')
            rgba = np.c_[vertex_colors, np.ones(len(mesh.vertices))]
            vcolor_attribute.data.foreach_set("color", rgba.ravel())   

        if parent:
            ob.parent = parent
            if parent.type == 'ARMATURE':
                if self.rigid_node_index > -1:
                    ob.parent_type = "BONE"
                    ob.parent_bone = parent_bone or nodes[self.rigid_node_index].name
                    ob.matrix_world = matrix
                else:
                    node_indices = [self.raw_node_indices[i:i+4] for i in range(idx_start * 4, (idx_end + 1) * 4, 4)]
                    node_weights = [self.raw_node_weights[i:i+4] for i in range(idx_start * 4, (idx_end + 1) * 4, 4)]
                    vgroups = ob.vertex_groups
                    for idx, (ni, nw) in enumerate(zip(node_indices, node_weights)):
                        for i, w in zip(ni, nw):
                            if 0 <= i <= 254 and w > 0:
                                if self.node_map:
                                    i = self.node_map[i]
                                group = vgroups.get(nodes[i].name) or vgroups.new(name=nodes[i].name)
                                group.add([idx], w, 'REPLACE')
                    ob.modifiers.new(name="Armature", type="ARMATURE").object = parent

        # water_subparts = []
        
        if not self.does_not_need_parts:
            if subpart:
                # if subpart.is_water_subpart:
                #     subpart.create(ob, self.tris)
                #     ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_water_surface'
                #     ob.nwo.water_volume_depth = 0
                #     if ob.data.materials:
                #         ob.name = ob.data.materials[0].name
                #     else:
                #         ob.name = "water_surface"
                # else:
                mesh.materials.append(subpart.part.material.blender_material)
            else:
                for subpart in self.subparts:
                    subpart.create(ob, self.tris)
            
        # for IG figure out what tris are render only
        if surface_triangle_mapping:
            indices = [t.index for t in self.tris]
            collision_face_indices = set()
            face_count = len(mesh.polygons)
            slip_mask = np.zeros(face_count, dtype=np.int8)
            ladder_mask = np.zeros(face_count, dtype=np.int8)
            breakable_mask = np.zeros(face_count, dtype=np.int8)
            
            for mapping in surface_triangle_mapping:
                surf = mapping.surface
                for t in mapping.triangle_indices:
                    if t.section != section_index:
                        continue

                    idx = t.tri
                    collision_face_indices.add(idx)

                    if surf.slip_surface:
                        slip_mask[idx] = 1
                    if surf.ladder:
                        ladder_mask[idx] = 1
                    if surf.breakable:
                        breakable_mask[idx] = 1
                        
            render_only_mask = np.zeros(face_count, dtype=np.int8)
            for f in indices:
                if f not in collision_face_indices:
                    render_only_mask[f] = 1
            
            if slip_mask.any():
                utils.add_face_prop(mesh, "slip_surface", None if slip_mask.all() else slip_mask)
            if ladder_mask.any():
                utils.add_face_prop(mesh, "ladder", None if ladder_mask.all() else ladder_mask)
            if breakable_mask.any():
                utils.add_face_prop(mesh, "face_mode", None if breakable_mask.all() else breakable_mask).face_mode = 'breakable'
            if render_only_mask.any():
                utils.add_face_prop(mesh, "face_mode", None if render_only_mask.all() else render_only_mask).face_mode = 'render_only'


        # for subpart in water_subparts:
        #     subpart.remove(ob, self.tris)

        if not mesh.nwo.from_vert_normals:
            utils.save_loop_normals_mesh(mesh)
            utils.set_two_sided(mesh, is_io)
            utils.apply_loop_normals(mesh)
            # utils.loop_normal_magic(mesh)
            
            if surface_triangle_mapping:
                utils.loop_normal_magic(mesh)
            
        utils.calc_face_prop_counts(mesh)
            
        if self.is_pca:
            mesh.color_attributes.new("tension", 'FLOAT_COLOR', 'POINT')
            
        if self.uncompressed:
            utils.add_face_prop(mesh, "uncompressed")
            
        # if self.mesh_keys:
        #     bm = bmesh.new()
        #     bm.from_mesh(mesh)
        #     layer = bm.verts.layers.int.new("mesh_key")
        #     for idx, vert in enumerate(bm.verts):
        #         vert[layer] = self.mesh_keys[idx]
        #     bm.to_mesh(mesh)
        #     bm.free()
                
        return ob

        
class InstancePlacement:
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node]):
        self.index = element.ElementIndex
        self.name = utils.any_partition(element.SelectField("name").GetStringData(), "__", False)
        self.node_index = element.SelectField("node_index").Value
        self.bone = ""
        if self.node_index > -1:
            self.bone = next((n.name for n in nodes if n.index == self.node_index), None)
        
        self.scale = element.SelectField("scale").Data
        self.forward = Vector([n for n in element.SelectField("forward").Data])
        self.left = Vector([n for n in element.SelectField("left").Data])
        self.up = Vector([n for n in element.SelectField("up").Data])
        self.position = Vector([n for n in element.SelectField("position").Data]) * 100
        
        # self.matrix = Matrix((
        #     (self.forward[0], self.forward[1], self.forward[2], self.position[0]),
        #     (self.left[0], self.left[1], self.left[2], self.position[1]),
        #     (self.up[0], self.up[1], self.up[2], self.position[2]),
        #     (0, 0, 0, 1),
        # ))
        
        self.matrix = Matrix((
            (self.forward[0], self.left[0], self.up[0], self.position[0]),
            (self.forward[1], self.left[1], self.up[1], self.position[1]),
            (self.forward[2], self.left[2], self.up[2], self.position[2]),
            (0, 0, 0, 1),
        ))
        
        self.ob = None
        
        
    
class MarkerType(Enum):
    _connected_geometry_marker_type_model = 0
    _connected_geometry_marker_type_effects = 1
    _connected_geometry_marker_type_garbage = 2
    _connected_geometry_marker_type_hint = 3
    _connected_geometry_marker_type_pathfinding_sphere = 4
    _connected_geometry_marker_type_physics_constraint = 5
    _connected_geometry_marker_type_target = 6

class Marker:
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node], regions: list[Region]):
        self.region = ""
        self.permutation = ""
        self.bone = ""
        self.translation = []
        self.rotation = []
        self.scale = 0.01
        self.direction = []
        self.linked_to = []
        self.uses_regions = False
        region_index = element.SelectField("region index").Data
        permutation_index = element.SelectField("permutation index").Data
        node_index = element.SelectField("node index").Data
        
        if region_index > -1:
            self.uses_regions = True
            self.region = next(r for r in regions if r.index == region_index)
            if permutation_index > -1:
                self.permutation = next(p for p in self.region.permutations if p.index == permutation_index)
                
        if node_index > -1:
            self.bone = next((n.name for n in nodes if n.index == node_index), None)
        
        self.translation = [n * 100 for n in element.SelectField("translation").Data]
        
        self.rotation = utils.ijkw_to_wxyz([n for n in element.SelectField("rotation").Data])
        self.scale = element.SelectField("scale").Data
        self.direction = ([n for n in element.SelectField("direction").Data])

        self.permutation_type = "exclude"
        self.permutations = []
    
class MarkerGroup:
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node], regions: list[Region]):
        self.name = element.SelectField("name").GetStringData()
        self.index = element.ElementIndex
        
        self.type = MarkerType._connected_geometry_marker_type_model
        if self.name.startswith("fx_"):
            self.type = MarkerType._connected_geometry_marker_type_effects
        elif self.name.startswith("target_"):
            self.type = MarkerType._connected_geometry_marker_type_target
        elif self.name.startswith("garbage_"):
            self.type = MarkerType._connected_geometry_marker_type_garbage
        elif self.name.startswith("hint_"):
            self.type = MarkerType._connected_geometry_marker_type_hint
            
        self.markers = []
        for e in element.SelectField("markers").Elements:
            self.markers.append(Marker(e, nodes, regions))
            
    def to_blender(self, armature: bpy.types.Object, collection: bpy.types.Collection, size_factor: float, allowed_region_permutations: set):
        # Find duplicate markers
        objects = []
        skip_markers = []
        for marker in self.markers:
            if marker in skip_markers: continue
            for marker2 in self.markers:
                if marker2 == marker: continue
                if marker.region and marker.region == marker2.region and marker.translation == marker2.translation and marker.rotation == marker2.rotation:
                    marker.linked_to.append(marker2)
                    skip_markers.append(marker2)
                    
        remaining_markers = [m for m in self.markers if m not in skip_markers]
        
        for marker in remaining_markers:
            # print(f"--- {self.name}")
            if marker.region:
                # Check if there is a marker for every permutation
                if marker.linked_to and len(marker.linked_to) + 1 != len(marker.region.permutations):
                    # If not pick if this is include or exclude type depending on whichever means less permutation entries need to be added
                    # If a tie prefer exclude
                    include_permutations = [marker.permutation.name]
                    include_permutations.extend([m.permutation.name for m in marker.linked_to if m.permutation]) 
                    exclude_permutations = [p.name for p in marker.region.permutations if p.name not in include_permutations]
                    if len(include_permutations) < len(exclude_permutations):
                        marker.permutation_type = "include"
                        marker.permutations = include_permutations
                    else:
                        marker.permutations = exclude_permutations
                elif not marker.linked_to:
                    marker.permutation_type = "include"
                    marker.permutations = [marker.permutation.name]
                else:
                    marker.permutations = [marker.permutation.name]
                    
            if allowed_region_permutations:
                skip = False
                if marker.permutation_type == "include":
                    for perm in marker.permutations:
                        region_perm = tuple((marker.region.name, perm))
                        if region_perm in allowed_region_permutations:
                            break
                    else:
                        skip = True
                else: # exclude
                    for perm in marker.permutations:
                        region_perm = tuple((marker.region.name, perm))
                        if region_perm in allowed_region_permutations:
                            skip = True
                            break
            
                if skip:
                    continue
            
            ob = bpy.data.objects.new(name=self.name, object_data=None)
            collection.objects.link(ob)
            ob.parent = armature
            if marker.bone:
                ob.parent_type = "BONE"
                ob.parent_bone = marker.bone
                ob.matrix_world = armature.pose.bones[marker.bone].matrix @ Matrix.LocRotScale(marker.translation, marker.rotation, Vector.Fill(3, 1))

            nwo = ob.nwo
            nwo.marker_type = self.type.name
            
            nwo.marker_uses_regions = marker.uses_regions
            if marker.uses_regions:
                utils.set_region(ob, marker.region.name)
                nwo.marker_permutation_type = marker.permutation_type
                utils.set_marker_permutations(ob, marker.permutations)

            ob.empty_display_type = "ARROWS"
            ob.empty_display_size *= size_factor
            
            if self.type == MarkerType._connected_geometry_marker_type_target:
                ob.empty_display_size = marker.scale * 100
                ob.empty_display_type = "SPHERE"
            elif self.type == MarkerType._connected_geometry_marker_type_garbage:
                ob.nwo.marker_velocity = marker.direction
            
            objects.append(ob)
            
        return objects
    
def get_blender_material(name, shader_path=""):
    mat = bpy.data.materials.get(name)
    if not mat:
        if name == '+sky' or name == '+seamsealer' or name == "+seam":
            add_special_materials('h4' if utils.is_corinth() else 'reach', 'scenario')
            mat = bpy.data.materials.get(name)
        else:
            mat = bpy.data.materials.new(name)
            mat.nwo.shader_path = shader_path
        
    return mat