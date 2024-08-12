"""Classes to help with importing geometry from tags"""

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from math import radians
from pathlib import Path
from statistics import mean
from typing import Iterable
import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
import numpy as np

from ..tools.append_foundry_materials import add_special_materials

from ..tools.property_apply import apply_props_material

from .material import MaterialTag
from .shader import ShaderTag
from ..tools import materials as special_materials

from .. import utils
from .Tags import TagFieldBlock, TagFieldBlockElement, TagPath

class PortalType(Enum):
    _connected_geometry_portal_type_no_way = 0
    _connected_geometry_portal_type_one_way = 1
    _connected_geometry_portal_type_two_way = 2
    

class Portal:
    index: int
    vertices: list[Vector]
    type: PortalType
    ai_deafening: bool
    blocks_sounds: bool
    is_door: bool
    
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
    _connected_poop_instance_pathfinding_policy_cutout = 0
    _connected_poop_instance_pathfinding_policy_static = 1
    _connected_poop_instance_pathfinding_policy_none = 2
    
class LightmappingPolicy(Enum):
    _connected_geometry_poop_lighting_per_pixel = 0
    _connected_geometry_poop_lighting_per_vertex = 1
    _connected_geometry_poop_lighting_single_probe = 2
    _connected_geometry_poop_lighting_exclude = 3
    _connected_geometry_poop_lighting_per_pixel_ao = 4
    _connected_geometry_poop_lighting_per_vertex_ao = 5
    
class ImposterPolicy(Enum):
    _connected_poop_instance_imposter_policy_polygon_default = 0
    _connected_poop_instance_imposter_policy_polygon_high = 1
    _connected_poop_instance_imposter_policy_card_default = 2
    _connected_poop_instance_imposter_policy_card_high = 3
    _connected_poop_instance_imposter_policy_none = 4
    _connected_poop_instance_imposter_policy_never = 5

class CinemaType(Enum):
    _connected_geometry_poop_cinema_default = 0
    _connected_geometry_poop_cinema_only = 1
    _connected_geometry_poop_cinema_exclude = 2
    
class StreamingPriority(Enum):
    _connected_geometry_poop_streamingpriority_default = 0
    _connected_geometry_poop_streamingpriority_higher = 1
    _connected_geometry_poop_streamingpriority_highest = 2
    
class Cluster:
    index: int
    mesh_index: int
    mesh: 'Mesh'
    
    def __init__(self, element: TagFieldBlockElement, mesh_block: TagFieldBlock, render_materials: list['Material']):
        self.index = element.ElementIndex
        self.mesh_index = element.SelectField("mesh index").Data
        self.mesh = Mesh(mesh_block.Elements[self.mesh_index], materials=render_materials)
        
    def create(self, render_model, temp_meshes) -> bpy.types.Object:
        return self.mesh.create(render_model, temp_meshes, name=f"cluster:{self.index}")[0]
    
class InstanceDefinition:
    index: int
    collision_info: 'InstanceCollision'
    cookie_info: 'InstanceCollision'
    # cookie_surfaces: list['CollisionSurface']
    # cookie_edges: list['CollisionEdge']
    # cookie_vertices: list['CollisionVertex']
    polyhedra: list['Polyhedron']
    four_vectors: list['PolyhedronFourVectors']
    mesh_index: int
    mesh: 'Mesh'
    compression_index: int
    compression: 'CompressionBounds'
    blender_render: bpy.types.Object
    blender_collision: bpy.types.Object
    blender_cookie: bpy.types.Object
    blender_physics: bpy.types.Object
    
    def __init__(self, element: TagFieldBlockElement, mesh_block: TagFieldBlock, compression_bounds: list['CompressionBounds'], render_materials: list['Material'], collision_materials: list['BSPCollisionMaterial']):
        self.index = element.ElementIndex
        self.mesh_index = element.SelectField("mesh index").Data
        self.compression_index = element.SelectField("compression index").Data
        self.compression = compression_bounds[self.compression_index]
        self.mesh = Mesh(mesh_block.Elements[self.mesh_index], self.compression, materials=render_materials)
        self.has_collision = False
        self.collision_info = None
        self.cookie_info = None
        self.blender_collision = None
        self.blender_cookie = None
        self.blender_render = None
        if not utils.is_corinth():
            self.has_collision = element.SelectField("Struct:collision info[0]/Block:surfaces").Elements.Count > 0
            if self.has_collision:
                self.collision_info = InstanceCollision(element.SelectField("Struct:collision info").Elements[0], f"instance_collision:{self.index}", collision_materials)
            # self.cookie_info = InstanceCollision(element.SelectField("Struct:poopie cutter collision").Elements[0], collision_materials)
    
    def create(self, render_model, temp_meshes) -> list[bpy.types.Object]:
        objects = []
        self.blender_render = self.mesh.create(render_model, temp_meshes, name=f"instance_definition:{self.index}")[0]
        if not utils.is_corinth():
            if self.has_collision:
                self.blender_collision = self.collision_info.to_object()
                if self.blender_render.type == 'MESH':
                    self.blender_collision.name = f"{self.blender_render.name}_proxy_collision"
                    self.blender_collision.nwo.proxy_parent = self.blender_render.data
                    self.blender_collision.nwo.proxy_type = "collision"
                    self.blender_render.data.nwo.proxy_collision = self.blender_collision
                else:
                    self.blender_collision.data.nwo.mesh_type = "_connected_geometry_mesh_type_collision"
            elif self.blender_render.data:
                self.blender_render.data.nwo.render_only = True
            
        if self.blender_render:
            objects.append(self.blender_render)
        if self.blender_collision:
            objects.append(self.blender_collision)
            
        return objects
            
    
class Instance:
    index: int
    matrix: Matrix
    not_in_lightprobes: bool
    render_only: bool
    not_block_aoe: bool
    decal: bool
    remove_from_shadow: bool
    disallow_lighting_samples: bool
    cinema_type: CinemaType
    mesh_index: int
    pathfinding: PathfindingPolicy
    lightmapping: LightmappingPolicy
    imposter: ImposterPolicy
    streaming: StreamingPriority
    lightmap_res: float
    name: str
    imposter_brightness: float
    imposter_transition: float
    definition: InstanceDefinition
    
    def __init__(self, element: TagFieldBlockElement, definitions: list[InstanceDefinition]):
        self.index = element.ElementIndex
        self.mesh_index = element.SelectField("ShortInteger:mesh_index").Data
        self.definition = definitions[self.mesh_index]
        self.scale = element.SelectField("scale").Data
        forward = element.SelectField("forward").Data
        left = element.SelectField("left").Data
        up = element.SelectField("up").Data
        position = element.SelectField("position").Data
        
        # Negative scaling on the diagonal gets the correct facing direction
        self.matrix = Matrix((
            (-forward[0], forward[1], forward[2], position[0] * 100),
            (left[0], -left[1], left[2], position[1] * 100),
            (up[0], up[1], -up[2], position[2] * 100),
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
        
        
    def create(self) -> list[bpy.types.Object]:
        if self.definition.blender_render.type == 'EMPTY' and self.definition.blender_collision:
            ob = self.definition.blender_collision.copy()
        else:
            ob = self.definition.blender_render.copy()
        ob.name = self.name
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
            if self.lightmapping == LightmappingPolicy._connected_geometry_poop_lighting_per_pixel_ao:
                nwo.poop_ao = True
                nwo.poop_lighting = "_connected_geometry_poop_lighting_per_pixel"
            elif self.lightmapping == LightmappingPolicy._connected_geometry_poop_lighting_per_vertex_ao:
                nwo.poop_ao = True
                nwo.poop_lighting = "_connected_geometry_poop_lighting_per_vertex"
        else:
            nwo.poop_lighting = self.lightmapping.name
            
        nwo.poop_pathfinding = self.pathfinding.name
        if self.imposter == ImposterPolicy._connected_poop_instance_imposter_policy_none:
            nwo.poop_imposter_policy = "_connected_poop_instance_imposter_policy_never"
        else:
            nwo.poop_imposter_policy = self.imposter.name
        nwo.poop_streaming_priority = self.streaming.name
        nwo.poop_imposter_brightness = self.imposter_brightness
        nwo.poop_imposter_transition_distance = self.imposter_transition
        nwo.poop_imposter_transition_distance_auto = self.imposter_transition <= 0
        
        nwo.poop_lightmap_resolution_scale = min(max(int(self.lightmap_res), 1), 7)
        
        return ob
        

class BSPMarker:
    index: int
    type: BSPMarkerType
    parameter: str
    rotation: Quaternion
    position: Vector

class EnvironmentObjectPalette:
    definition: str
    model: str
    index: str
    
class EnvironmentObject:
    index: int
    palette_index: int
    palette: EnvironmentObjectPalette
    name: str
    rotation: Quaternion
    translation: Vector
    scale: float
    variant: str

class Face:
    index: int
    indices: list[int]
    subpart: 'MeshPart'
    
    def __init__(self,indices: list[int], subpart: 'MeshSubpart', index: int):
        self.indices = indices
        self.subpart = subpart
        self.index = index

class Node:
    index: int
    name: str
    translation: Vector
    rotation: Quaternion
    inverse_forward: Vector
    inverse_left: Vector
    inverse_up: Vector
    inverse_position: Vector
    inverse_scale: Vector
    transform_matrix: Matrix
    parent = ""
    bone: bpy.types.EditBone
    def __init__(self, name):
        self.name = name

class Permutation:
    region: 'Region'
    index: int
    name: str
    mesh_index: int
    mesh_count: int
    instance_indexes: list[int]
    clone_name: str
    
    def __init__(self, element: TagFieldBlockElement, region: 'Region'):
        self.region = region
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.mesh_index = int(element.SelectField("mesh index").GetStringData())
        self.mesh_count = int(element.SelectField("mesh count").GetStringData())
        self.clone_name = ""
        self.instance_indexes = []
        if utils.is_corinth():
            self.clone_name = element.SelectField("clone name").GetStringData()
        flags_1 = element.SelectField("instance mask 0-31")
        for i in range(31):
            if flags_1.TestBit(str(i)):
                self.instance_indexes.append(i)
        flags_2 = element.SelectField("instance mask 32-63")
        for i in range(31):
            if flags_2.TestBit(str(i)):
                self.instance_indexes.append(i + 32)
        flags_3 = element.SelectField("instance mask 64-95")
        for i in range(31):
            if flags_3.TestBit(str(i)):
                self.instance_indexes.append(i + 64)
    
class Region:
    index: int
    name: str
    permutations_block: TagFieldBlock
    permutations: list[Permutation]
    
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
    index: int
    name: str
    node_a_index: int
    node_b_index: int
    bone_parent: str
    bone_child: str
    matrix_a: Matrix
    matrix_b: Matrix
    
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
    limit_min_angle: float
    limit_max_angle: float
    
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
    min_twist: float
    max_twist: float
    cone: float
    min_plane: float
    max_plane: float
    
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
    type: ConstraintType
    index: int
    constaint_index: int
    constraint_data: Hinge | LimitedHinge | Ragdoll
    
    def to_object(self) -> bpy.types.Object:
        pass
    
class NodeEdge:
    index: int
    node_parent: str
    node_child: str
    constraints: Constraint
    
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
    name: str
    material_index: int
    material: str
    
    def __init__(self, element: TagFieldBlockElement, materials: list[str]):
        base = element.SelectField("Struct:base").Elements[0]
        self.name = base.SelectField("name").Data
        self.material_index = base.SelectField("material").Value
        self.material = materials[self.material_index]
    
    
class Sphere(Shape):
    radius: float
    translation: Vector
    matrix: Matrix
    
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
    radius: float
    bottom: Vector
    top: Vector
    rotation: Quaternion
    translation: Vector
    height: float
    matrix: Matrix
    
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
    translation: Vector
    rotation: Vector
    width: float
    length: float
    height: float
    matrix: Matrix
    ob: bpy.types.Object
    
    def __init__(self, element: TagFieldBlockElement, materials):
        super().__init__(element, materials)
        self.translation = Vector([n for n in element.SelectField("Struct:convex transform shape[0]/RealVector3d:translation").Data]) * 100
        self.width, self.length, self.height = (n * 2 * 100 for n in element.SelectField("RealVector3d:half extents").Data)
        ii, ij, ik = element.SelectField("Struct:convex transform shape[0]/RealVector3d:rotation i").Data
        ji, jj, jk = element.SelectField("Struct:convex transform shape[0]/RealVector3d:rotation j").Data
        ki, kj, kk = element.SelectField("Struct:convex transform shape[0]/RealVector3d:rotation k").Data
        rotation_matrix = Matrix((
            (ii, ij, ik, self.translation[0]),
            (ji, jj, jk, self.translation[1]),
            (ki, kj, kk, self.translation[2]),
            (0, 0, 0, 1)
        ))
        
        rotation = rotation_matrix.to_quaternion()
        self.matrix = Matrix.LocRotScale(self.translation, rotation, Vector((self.width, self.length, self.height)))
        
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
        self.xw, self.yw, self.zw = element.SelectField("havok w four vectors x").Data, element.SelectField("havok w four vectors y").Data, element.SelectField("havok w four vectors z").Data
        
    def to_vectors(self) -> list[Vector]:
        vectors = []
        vectors.append(Vector((self.xi, self.yi, self.zi)) * 100)
        vectors.append(Vector((self.xj, self.yj, self.zj)) * 100)
        vectors.append(Vector((self.xk, self.yk, self.zk)) * 100)
        vectors.append(Vector((self.xw, self.yw, self.zw)) * 100)
        
        return vectors
        
class Polyhedron(Shape):
    four_vectors: PolyhedronFourVectors
    four_vectors_size: int
    vertices: list[Vector]
    offset: int
    matrix: Matrix
    
    def __init__(self, element: TagFieldBlockElement, materials, vectors_block: TagFieldBlockElement, four_vectors_map: list):
        super().__init__(element, materials)
        four_vectors_size = element.SelectField("four vectors size").Data
        self.vertices = []
        self.offset = four_vectors_map[element.ElementIndex] - four_vectors_size
        for i in range(self.offset, self.offset + four_vectors_size):
            four_vectors = PolyhedronFourVectors(vectors_block.Elements[i])
            self.vertices.extend(four_vectors.to_vectors())
            
        self.matrix = Matrix.Identity(4)
            
    def to_object(self) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(vertices=self.vertices, edges=[], faces=[])
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.convex_hull(bm, input=bm.verts)
        bm.to_mesh(mesh)
        bm.free()
        self.ob = bpy.data.objects.new(self.name, mesh)
    
class RigidBody:
    index: int
    node_index: int
    region: str
    shape_type: ShapeType
    shapes: list[Sphere | Pill | Box | Polyhedron]
    four_vectors_offset: int
    valid: bool
    list_shapes_offset: int
    
    def __init__(self, element: TagFieldBlockElement, region, permutation, materials, four_vectors_map, tag, list_shapes_offset):
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
        match self.shape_type:
            case ShapeType.sphere:
                self.shapes.append(Sphere(tag.block_spheres.Elements[shape_index], materials))
            case ShapeType.pill:
                self.shapes.append(Pill(tag.block_pills.Elements[shape_index], materials))
            case ShapeType.box:
                self.shapes.append(Box(tag.block_boxes.Elements[shape_index], materials))
            case ShapeType.polyhedron:
                self.shapes.append(Polyhedron(tag.block_polyhedra.Elements[shape_index], materials, tag.block_polyhedron_four_vectors, four_vectors_map))
                self.four_vectors_offset = self.shapes[-1].offset
            case ShapeType.mopp | ShapeType._list:
                if self.shape_type == ShapeType.mopp:
                    mopp = tag.block_mopps.Elements[shape_index]
                    list_element = tag.block_list_shapes.Elements[mopp.SelectField("list").Value]
                else:
                    list_element = tag.block_list_shapes.Elements[shape_index]
                    
                list_shapes_count = list_element.SelectField("num child shapes").Data
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
                            self.shapes.append(Box(tag.block_boxes.Elements[list_shape_index], materials))
                        case ShapeType.polyhedron:
                            self.shapes.append(Polyhedron(tag.block_polyhedra.Elements[list_shape_index], materials, tag.block_polyhedron_four_vectors, four_vectors_map))
                            self.four_vectors_offset = self.shapes[-1].offset
                        case _:
                            print(f"Unsupported physics shape type: {self.shape_type.name}")
            case _:
                print(f"Unsupported physics shape type: {self.shape_type.name}")
                
        self.valid = True
                
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
    index: int
    name: str
    region: str
    permutation: str

    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.name = element.Fields[0].Data

class BSPCollisionMaterial:
    index: int
    render_method: str
    blender_material: bpy.types.Material
    global_material: str
    tag_shader: TagPath
    name: str
    
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
        
class CollisionVertex:
    index: int
    element: TagFieldBlockElement
    point: tuple[float]
    first_edge: int
    
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.element = element
        self.point = element.Fields[0].Data
        self.first_edge = utils.unsigned_int16(element.Fields[1].Data)
        
    @property
    def position(self) -> Vector:
        return Vector(self.point) * 100
        
class CollisionSurface:
    element: TagFieldBlockElement
    index: int
    first_edge: int
    material: CollisionMaterial
    two_sided: bool
    ladder: bool
    breakable: bool
    slip_surface: bool
    
    def __init__(self, element: TagFieldBlockElement, materials: list[CollisionMaterial] | list[BSPCollisionMaterial]):
        self.index = element.ElementIndex
        self.first_edge = utils.unsigned_int16(element.SelectField("first edge").Data)
        material_index = element.SelectField("material").Data
        if material_index < 0 or material_index >= len(materials):
            self.material = None
        else:
            self.material = materials[material_index]
        flags = element.SelectField("flags")
        self.two_sided = flags.TestBit("two sided")
        self.ladder = flags.TestBit("climbable")
        self.breakable = flags.TestBit("breakable")
        self.slip_surface = flags.TestBit("slip")
        
class CollisionEdge:
    element: TagFieldBlockElement
    index: int
    start_vertex: int
    end_vertex: int
    forward_edge: int
    reverse_edge: int
    left_surface: int
    left_surface: int
    
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
    name: str
    index: int
    node_index: int
    bone: str
    surfaces: list[CollisionSurface]
    edges: list[CollisionEdge]
    vertices: list[CollisionVertex]
    uses_materials: bool
    
    def __init__(self, element: TagFieldBlockElement, name, materials: list[CollisionMaterial]):
        self.name = name
        self.index = element.ElementIndex
        self.uses_materials = False
        self.surfaces = [CollisionSurface(e, materials) for e in element.SelectField("Block:surfaces").Elements]
        self.vertices = [CollisionVertex(e) for e in element.SelectField("Block:vertices").Elements]
        self.edges = [CollisionEdge(e) for e in element.SelectField("Block:edges").Elements]

        
    def to_object(self) -> bpy.types.Object:
        def yield_indices():
            for surface in self.surfaces:
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
                
        indices = yield_indices()
        # Create the bpy mesh
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(vertices=[v.position for v in self.vertices], edges=[], faces=list(indices))
        
        # Check if we need to set any per face properties
        map_material, map_two_sided, map_ladder, map_breakable, map_slip = [], [], [], [], []
        for surface in self.surfaces:
            material = surface.material
            two_sided = surface.two_sided
            ladder = surface.ladder
            breakable = surface.breakable
            slip = surface.slip_surface
            
            map_material.append(material)
            map_two_sided.append(two_sided)
            map_ladder.append(ladder)
            map_breakable.append(breakable)
            map_slip.append(slip)

            
        materials_set = set(map_material)
        two_sided_set = set(map_two_sided)
        ladder_set = set(map_ladder)
        breakable_set = set(map_breakable)
        slip_set = set(map_slip)

        split_material = len(materials_set) > 1
        split_two_sided = len(two_sided_set) > 1
        split_ladder = len(ladder_set) > 1
        split_breakable = len(breakable_set) > 1
        split_slip = len(slip_set) > 1

        blender_materials_map = {}
        layer_materials, layer_two_sided, layer_ladder, layer_breakable, layer_slip = {}, None, None, None, None
        using_layers = split_material or split_two_sided or split_ladder or split_breakable or split_slip
        bm = bmesh.new()
        bm.from_mesh(mesh)
        
        if self.uses_materials:
            if split_material:
                for idx, mat in enumerate(set(map_material)):
                    if mat is None:
                        if isinstance(self, StructureCollision):
                            bmat = get_blender_material("+sky")
                        else:
                            bmat = get_blender_material("+seamsealer")
                            
                        mesh.materials.append(bmat)
                        blender_materials_map[mat] = idx
                    else:
                        mesh.materials.append(mat.blender_material)
                        blender_materials_map[mat] = idx
            elif surface.material:
                mesh.materials.append(surface.material.blender_material)
        else:
            if split_material:
                for material in set(map_material):
                    if material and material.name != 'default':
                        layer_materials[material] = utils.add_face_layer(bm, mesh, "face_global_material", material.name)
            else:
                if surface.material and surface.material.name != "default":
                    mesh.nwo.face_global_material = surface.material.name
                    
                
        if split_two_sided:
            layer_two_sided = utils.add_face_layer(bm, mesh, "two_sided", True)
        else:
            mesh.nwo.face_two_sided = surface.two_sided
            
        if split_ladder:
            layer_ladder = utils.add_face_layer(bm, mesh, "ladder", True)
        else:
            mesh.nwo.ladder = surface.ladder
            
        if split_breakable:
            layer_breakable = utils.add_face_layer(bm, mesh, "breakable", True)
        else:
            mesh.nwo.breakable = surface.breakable
            
        if split_slip:
            layer_slip = utils.add_face_layer(bm, mesh, "slip_surface", True)
        else:
            mesh.nwo.slip_surface = surface.slip_surface
        
        if using_layers:
            if split_material:
                material_indices = [blender_materials_map[mat] for mat in map_material]
            for idx, face in enumerate(bm.faces):
                if split_material:
                    face.material_index = material_indices[idx] if self.uses_materials else face.material_index
                if layer_two_sided:
                    face[layer_two_sided] = map_two_sided[idx]
                if layer_ladder:
                    face[layer_ladder] = map_ladder[idx]
                if layer_breakable:
                    face[layer_breakable] = map_breakable[idx]
                if layer_slip:
                    face[layer_slip] = map_slip[idx]

                    
            for face_layer in mesh.nwo.face_props:
                face_layer.face_count = utils.layer_face_count(bm, bm.faces.layers.int.get(face_layer.layer_name))
        
        # bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
        bm.to_mesh(mesh)
        bm.free()
                                
        mesh.nwo.mesh_type = "_connected_geometry_mesh_type_collision"
        
        ob = bpy.data.objects.new(self.name, mesh)
        if not self.uses_materials:
            apply_props_material(ob, 'Collision')
        return ob
    
class ModelCollision(BSP):
    def __init__(self, element: TagFieldBlockElement, name, collision_materials: list[CollisionMaterial], nodes: list[str] = None):
        super().__init__(element, name, collision_materials)
        self.node_index = element.Fields[0].Data
        self.bone = ""
        if nodes:
            self.bone = nodes[self.node_index]
    
class InstanceCollision(BSP):
    def __init__(self, element: TagFieldBlockElement, name, collision_materials: list[CollisionMaterial]):
        super().__init__(element, name, collision_materials)
        self.uses_materials = True
        
class StructureCollision(BSP):
    def __init__(self, element: TagFieldBlockElement, name, collision_materials: list[CollisionMaterial]):
        super().__init__(element, name, collision_materials)
        self.uses_materials = True
    
class PathfindingSphere:
    bone: str
    index: int
    node_index: int
    when_open: bool
    vehicle: bool
    sectors: bool
    center: float
    radius: float
    
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
    co_matrix: Matrix
    u0: float
    v0: float
    u1: float
    v1: float
    
    def __init__(self, element: TagFieldBlockElement):
        first = element.SelectField("position bounds 0").GetStringData()
        second = element.SelectField("position bounds 1").GetStringData()
        
        self.x0 = float(first[0]) * 100
        self.x1 = float(first[1]) * 100
        self.y0 = float(first[2]) * 100
        self.y1 = float(second[0]) * 100
        self.z0 = float(second[1]) * 100
        self.z1 = float(second[2]) * 100
        
        self.co_matrix = Matrix((
            (self.x1-self.x0, 0, 0, self.x0),
            (0, self.y1-self.y0, 0, self.y0),
            (0, 0, self.z1-self.z0, self.z0),
            (0, 0, 0, 1),
        ))
        
        third = element.SelectField("texcoord bounds 0").GetStringData()
        fourth = element.SelectField("texcoord bounds 1").GetStringData()
        
        self.u0 = float(third[0])
        self.u1 = float(third[1])
        self.v0 = float(fourth[0])
        self.v1 = float(fourth[1])

class Material:
    index: int
    name: str
    new: bool
    shader_path: str
    emissive_index: int
    lm_res: int
    lm_transparency: list[float]
    lm_translucency: list[float]
    lm_both_sides: bool
    breakable_surface_index: int
    blender_material: bpy.types.Material
    
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        render_method_path = element.SelectField("render method").Path
        self.name = render_method_path.ShortName
        self.new = not bool(bpy.data.materials.get(self.name, 0))
        self.shader_path = render_method_path.RelativePathWithExtension
        self.emissive_index = int(element.SelectField("imported material index").GetStringData())
        self.lm_res = int(element.SelectField("imported material index").GetStringData())
        self.lm_transparency = element.SelectField("lightmap additive transparency color").Data
        self.lm_translucency = element.SelectField("lightmap traslucency tint color").Data
        flags = element.SelectField("lightmap flags")
        self.lm_both_sides = flags.TestBit("lighting from both sides")
        self.breakable_surface_index = element.SelectField("breakable surface index").Data
        self.blender_material = get_blender_material(self.name, self.shader_path)
    
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
    index_buffer_type: IndexLayoutType
    indices: list[int]

    def __init__(self, index_buffer_type: int, indices: list[int]):
        self.index_layout = IndexLayoutType(index_buffer_type)
        self.indices = indices

    def get_faces(self, mesh: 'Mesh') -> list[Face]:
        idx = 0
        faces = []
        for subpart in mesh.subparts:
            start = subpart.index_start
            count = subpart.index_count
            list_indices = list(self._get_indices(start, count))
            indices = (list_indices[n:n+3] for n in range(0, len(list_indices), 3))
            for i in indices:
                faces.append(Face(indices=i, subpart=subpart, index=idx))
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
            raise (f"Unsupported Index Layout Type {self.index_layout}")

    def _unpack(self, indices: list[int]) -> list[int]:
        i0, i1, i2 = 0, 0, 0
        for pos, idx in enumerate(indices):
            tri = []
            i0, i1, i2 = i1, i2, idx
            if pos < 2 or i0 == i1 or i0 == i2 or i1 == i2: continue
            yield i0
            if pos % 2 == 0:
                yield i1
                yield i2
            else:
                yield i2
                yield i1
                
class Tessellation(Enum):
    _connected_geometry_mesh_tessellation_density_none = 0
    _connected_geometry_mesh_tessellation_density_4x = 1
    _connected_geometry_mesh_tessellation_density_9x = 2
    _connected_geometry_mesh_tessellation_density_36x = 3
    
class DrawDistance(Enum):
    _connected_geometry_face_draw_distance_normal = 0
    _connected_geometry_face_draw_distance_detail_mid = 1
    _connected_geometry_face_draw_distance_detail_close = 2

class MeshPart:
    index: int
    material_index: int
    material: Material
    transparent: bool
    index_start: int
    index_count: int
    draw_distance: bool
    tessellation: Tessellation
    water_surface: bool
    
    def __init__(self, element: TagFieldBlockElement, materials: list[Material]):
        self.index = element.ElementIndex
        self.material_index = element.SelectField("render method index").Value
        self.transparent = element.SelectField("transparent sorting index").Value > -1
        self.index_start = int(element.SelectField("index start").GetStringData())
        self.index_count = int(element.SelectField("index count").GetStringData())
        
        self.draw_distance = DrawDistance._connected_geometry_face_draw_distance_normal
        flags = element.SelectField("part flags")
        if flags.TestBit("draw cull distance close"):
            self.draw_distance = DrawDistance._connected_geometry_face_draw_distance_detail_close
        elif flags.TestBit("draw cull distance medium"):
            self.draw_distance = DrawDistance._connected_geometry_face_draw_distance_detail_mid
        
        self.water_surface = False
        if flags.TestBit("is water surface"):
            self.water_surface = True
            
        self.tessellation = Tessellation(element.SelectField("tessellation").Value)
        self.material = next(m for m in materials if m.index == self.material_index)
            
class MeshSubpart:
    index: int
    index_start: int
    index_count: int
    part_index: int
    part: MeshPart
    
    def __init__(self, element: TagFieldBlockElement, parts: list[MeshPart]):
        self.index = element.ElementIndex
        self.index_start = int(element.SelectField("index start").GetStringData())
        self.index_count = int(element.SelectField("index count").GetStringData())
        self.part_index = element.SelectField("part index").Value
        self.part = next(p for p in parts if p.index == self.part_index)
        
    def create(self, ob: bpy.types.Object, tris: Face, face_transparent: bool, face_draw_distance: bool, face_tesselation: bool, water_surface_parts: list[MeshPart]):
        mesh = ob.data
        blend_material = self.part.material.blender_material

        if blend_material.name not in mesh.materials:
            mesh.materials.append(blend_material)
        blend_material_index = ob.material_slots.find(blend_material.name)

        indexes = {t.index for t in tris if t.subpart == self}

        for i in indexes:
            mesh.polygons[i].material_index = blend_material_index

        if not (face_transparent or face_draw_distance or face_tesselation or water_surface_parts):
            return

        bm = bmesh.new()
        bm.from_mesh(mesh)
        layer_map = {}
        if face_transparent and self.part.transparent:
            existing_layer = next((prop.layer_name for prop in mesh.nwo.face_props if prop.face_transparent_override), None)
            if existing_layer is None:
                layer_map["face_transparent"] = utils.add_face_layer(bm, mesh, "transparent", True)
            else:
                layer_map["face_transparent"] = bm.faces.layers.int.get(existing_layer)
        if face_draw_distance and self.part.draw_distance.value > 0:
            existing_layer = next((prop.layer_name for prop in mesh.nwo.face_props if prop.face_draw_distance_override), None)
            if existing_layer is None:
                layer_map["face_draw_distance"] = utils.add_face_layer(bm, mesh, "draw_distance", self.part.draw_distance.name)
            else:
                layer_map["face_draw_distance"] = bm.faces.layers.int.get(existing_layer)
        if face_tesselation and self.part.tessellation.value > 0:
            existing_layer = next((prop.layer_name for prop in mesh.nwo.face_props if prop.mesh_tessellation_density_override), None)
            if existing_layer is None:
                layer_map["mesh_tessellation_density"] = utils.add_face_layer(bm, mesh, "tessellation", self.part.tessellation.name)
            else:
                layer_map["mesh_tessellation_density"] = bm.faces.layers.int.get(existing_layer)
                
        if self.part in water_surface_parts:
            layer_map["water_surface"] = bm.faces.layers.int.new("water_surface")

        bm.faces.ensure_lookup_table()
        for i in indexes:
            for layer in layer_map.values():
                bm.faces[i][layer] = 1

        bm.to_mesh(mesh)
        bm.free()
            

class Mesh:
    '''All new Halo 3 render geometry definitions!'''
    index: int
    permutation: Permutation
    parts: list[MeshPart]
    subparts: list[MeshSubpart]
    rigid_node_index: int
    index_buffer_type: int
    bounds: CompressionBounds
    ob: bpy.types.Object
    tris: Iterable[Face]
    raw_positions: list
    raw_texcoords : list
    raw_normals: list
    raw_node_indices: list
    raw_node_weights: list
    node_map: list[int]
    face_transparent: bool
    face_tesselation: bool
    face_draw_distance: bool
    valid: bool
    
    def __init__(self, element: TagFieldBlockElement, bounds: CompressionBounds = None, permutation=None, materials=[], block_node_map=None):
        self.index = element.ElementIndex
        self.permutation = permutation
        self.rigid_node_index = int(element.SelectField("rigid node index").GetStringData())
        self.index_buffer_type =  int(element.SelectField("index buffer type").Value)
        self.bounds = bounds
        self.parts = []
        self.subparts = []
        
        for part_element in element.SelectField("parts").Elements:
            self.parts.append(MeshPart(part_element, materials))
        for subpart_element in element.SelectField("subparts").Elements:
            self.subparts.append(MeshSubpart(subpart_element, self.parts))
            
        self.valid = bool(self.parts) and bool(self.subparts)
            
        self.face_transparent = len({p.transparent for p in self.parts}) > 1
        self.face_tesselation = len({p.tessellation for p in self.parts}) > 1
        self.face_draw_distance = len({p.draw_distance for p in self.parts}) > 1
            
        self.raw_positions = []
        self.raw_texcoords = []
        self.raw_normals = []
        self.raw_node_indices = []
        self.raw_node_weights = []
        
        self.node_map = []
        if block_node_map is not None and block_node_map.Elements.Count and self.index < block_node_map.Elements.Count:
            map_element = block_node_map.Elements[self.index]
            self.node_map = [int(e.Fields[0].GetStringData()) for e in map_element.Fields[0].Elements]
                
            
    def _true_uvs(self, texcoords):
        return [self._interp_uv(tc) for tc in texcoords]
    
    def _interp_uv(self, texcoord):
        u = np.interp(texcoord[0], (0, 1), (self.bounds.u0, self.bounds.u1))
        v = np.interp(texcoord[1], (0, 1), (self.bounds.v0, self.bounds.v1))
        
        return Vector((u, 1-v)) # 1-v to correct UV for Blender
    
    def create(self, render_model, temp_meshes: TagFieldBlock, nodes=[], parent: bpy.types.Object | None = None, instances: list['InstancePlacement'] = [], name="blam"):
        if not self.valid:
            return [bpy.data.objects.new(name, None)]

        temp_mesh = temp_meshes.Elements[self.index]
        raw_vertices = temp_mesh.SelectField("raw vertices")
        raw_indices = temp_mesh.SelectField("raw indices")
        if raw_indices.Elements.Count == 0:
            raw_indices = temp_mesh.SelectField("raw indices32")

        self.raw_positions = list(render_model.GetPositionsFromMesh(temp_meshes, self.index))
        self.raw_texcoords = list(render_model.GetTexCoordsFromMesh(temp_meshes, self.index))
        self.raw_normals = list(render_model.GetNormalsFromMesh(temp_meshes, self.index))
        self.raw_lightmap_texcoords = [e.Fields[5].Data for e in raw_vertices.Elements]
        self.raw_vertex_colors = [e.Fields[8].Data for e in raw_vertices.Elements]
        self.raw_texcoords1 = [e.Fields[9].Data for e in raw_vertices.Elements] if utils.is_corinth() else []

        if not instances and self.rigid_node_index == -1:
            self.raw_node_indices = list(render_model.GetNodeIndiciesFromMesh(temp_meshes, self.index))
            self.raw_node_weights = list(render_model.GetNodeWeightsFromMesh(temp_meshes, self.index))

        indices = [utils.unsigned_int16(int(element.Fields[0].GetStringData())) for element in raw_indices.Elements]
        buffer = IndexBuffer(self.index_buffer_type, indices)
        self.tris = buffer.get_faces(self)

        objects = []

        if instances:
            for instance in instances:
                subpart = self.subparts[instance.index]
                ob = self._create_mesh(instance.name, parent, nodes, subpart, instance.bone, instance.matrix)
                ob.scale = Vector.Fill(3, instance.scale)
                instance.ob = ob
                objects.append(ob)
        else:
            if self.permutation:
                name = f"{self.permutation.region.name}:{self.permutation.name}"
            objects.append(self._create_mesh(name, parent, nodes, None))

        return objects

    def _create_mesh(self, name, parent, nodes, subpart: MeshSubpart | None, parent_bone=None, local_matrix=None):
        matrix = local_matrix or (parent.matrix_world if parent else Matrix.Identity(4))

        indices = [t.indices for t in self.tris if not subpart or t.subpart == subpart]

        vertex_indexes = sorted({idx for tri in indices for idx in tri})
        idx_start, idx_end = vertex_indexes[0], vertex_indexes[-1]

        mesh = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, mesh)

        positions = [self.raw_positions[i:i+3] for i in range(idx_start * 3, (idx_end + 1) * 3, 3)]
        texcoords = [self.raw_texcoords[i:i+2] for i in range(idx_start * 2, (idx_end + 1) * 2, 2)]
        normals = [self.raw_normals[i:i+3] for i in range(idx_start * 3, (idx_end + 1) * 3, 3)]
        lighting_texcoords = [[float(v) for v in self.raw_lightmap_texcoords[n]] for n in range(idx_start, idx_end+1)]
        vertex_colors = [[float(v) for v in self.raw_vertex_colors[n]] for n in range(idx_start, idx_end+1)]
        texcoords1 = [[float(v) for v in self.raw_texcoords1[n]] for n in range(idx_start, idx_end+1)] if self.raw_texcoords1 else []

        if idx_start > 0:
            indices = [[i - idx_start for i in tri] for tri in indices]

        mesh.from_pydata(positions, [], indices)

        transform_matrix = self.bounds.co_matrix if self.bounds else Matrix.Scale(100, 4)
        mesh.transform(transform_matrix)

        print(f"--- {name}")

        has_vertex_colors = any(any(v) for v in vertex_colors)
        has_lighting_texcoords = any(any(v) for v in lighting_texcoords)
        has_texcoords1 = bool(texcoords1) and any(any(v) for v in texcoords1)

        uvs = self._true_uvs(texcoords) if self.bounds else [Vector((u, 1-v)) for (u, v) in texcoords]
        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        lighting_uv_layer = mesh.uv_layers.new(name="lighting", do_init=False) if has_lighting_texcoords else None
        uvs1_layer = mesh.uv_layers.new(name="UVMap1", do_init=False) if has_texcoords1 else None

        if uv_layer:
            for face in mesh.polygons:
                for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                    uv_layer.data[loop_idx].uv = uvs[vert_idx]
                    if uvs1_layer:
                        uvs1_layer.data[loop_idx].uv = texcoords1[vert_idx]
                    if lighting_uv_layer:
                        lighting_uv_layer.data[loop_idx].uv = lighting_texcoords[vert_idx]

        normalised_normals = [Vector(n).normalized() for n in normals]
        mesh.normals_split_custom_set_from_vertices(normalised_normals)

        if has_vertex_colors:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            layer = bm.verts.layers.float_color.new("Color")
            for idx, v in enumerate(bm.verts):
                v[layer] = vertex_colors[idx] + [1.0]
            bm.to_mesh(mesh)
            bm.free()

        if parent:
            ob.parent = parent
            if parent.type == 'ARMATURE':
                if self.rigid_node_index > -1:
                    ob.parent_type = "BONE"
                    ob.parent_bone = parent_bone or nodes[self.rigid_node_index].name
                    ob.matrix_world = matrix
                else:
                    node_indices = self.raw_node_indices[idx_start*4:idx_end*4+4]
                    node_weights = self.raw_node_weights[idx_start*4:idx_end*4+4]
                    vgroups = ob.vertex_groups
                    for idx, (ni, nw) in enumerate(zip(node_indices, node_weights)):
                        for i, w in zip(ni, nw):
                            if 0 <= i <= 254 and w > 0:
                                if self.node_map:
                                    i = self.node_map[i]
                                group = vgroups.get(nodes[i].name) or vgroups.new(name=nodes[i].name)
                                group.add([idx], w, 'REPLACE')
                    ob.modifiers.new(name="Armature", type="ARMATURE").object = parent

        if not self.face_transparent:
            mesh.nwo.face_transparent = self.parts[0].transparent
        if not self.face_draw_distance:
            mesh.nwo.face_draw_distance = self.parts[0].draw_distance.name
        if not self.face_tesselation:
            mesh.nwo.mesh_tessellation_density = self.parts[0].tessellation.name

        water_surface_parts = {p for p in self.parts if p.water_surface}

        if subpart:
            mesh.materials.append(subpart.part.material.blender_material)
        else:
            for subpart in self.subparts:
                subpart.create(ob, self.tris, self.face_transparent, self.face_draw_distance, self.face_tesselation, water_surface_parts)

        self._set_two_sided(mesh)
        utils.loop_normal_magic(mesh)
        
        if mesh.nwo.face_props:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            for face_layer in mesh.nwo.face_props:
                face_layer.face_count = utils.layer_face_count(bm, bm.faces.layers.int.get(face_layer.layer_name))
            bm.free()

        if mean(ob.dimensions.to_tuple()) < 20:
            mesh.nwo.precise_position = True

        return ob

    def _set_two_sided(self, mesh):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        face_dict = {}
        for face in bm.faces:
            vert_set = frozenset(v.co.to_tuple() for v in face.verts)
            face_dict.setdefault(vert_set, []).append(face)

        to_remove = set()
        two_sided = set()
        for faces in face_dict.values():
            for i, f1 in enumerate(faces):
                for f2 in faces[i+1:]:
                    if {v.co.to_tuple() for v in f1.verts} == {v.co.to_tuple() for v in reversed(f2.verts)}:
                        to_remove.add(f2.index)
                        two_sided.add(f1.index)
                        break

        if to_remove:
            if len(bm.faces) == len(to_remove):
                mesh.nwo.face_two_sided = True
            else:
                layer = utils.add_face_layer(bm, mesh, "two_sided", True)
                for face in bm.faces:
                    if face.index in two_sided:
                        face[layer] = 1

            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in to_remove], context='FACES')
            
        bm.to_mesh(mesh)
        bm.free()

        
class InstancePlacement:
    index: int
    name: str
    node_index: int
    bone: str
    scale: float
    forward: Vector
    left: Vector
    up: Vector
    position: Vector
    matrix: Matrix
    ob: bpy.types.Object
    
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node]):
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.node_index = element.SelectField("node_index").Value
        self.bone = ""
        if self.node_index > -1:
            self.bone = next((n.name for n in nodes if n.index == self.node_index), None)
        
        self.scale = float(element.SelectField("scale").GetStringData())
        self.forward = Vector([float(n) for n in element.SelectField("forward").GetStringData()])
        self.left = Vector([float(n) for n in element.SelectField("left").GetStringData()])
        self.up = Vector([float(n) for n in element.SelectField("up").GetStringData()])
        self.position = Vector([float(n) for n in element.SelectField("position").GetStringData()]) * 100
        
        self.matrix = Matrix((
            (self.forward[0], self.forward[1], self.forward[2], self.position[0]),
            (self.left[0], self.left[1], self.left[2], self.position[1]),
            (self.up[0], self.up[1], self.up[2], self.position[2]),
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
    index: int
    region: Region
    permutation: Permutation
    bone: str
    translation: Vector
    rotation: Quaternion
    scale: float
    direction: list[float, float, float]
    linked_to: list['Marker']
    
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node], regions: list[Region]):
        self.region = ""
        self.permutation = ""
        self.bone = ""
        self.translation = []
        self.rotation = []
        self.scale = 0.01
        self.direction = []
        self.linked_to = []
        region_index = int(element.SelectField("region index").GetStringData())
        permutation_index = int(element.SelectField("permutation index").GetStringData())
        node_index = int(element.SelectField("node index").GetStringData())
        if region_index > -1:
            self.region = next(r for r in regions if r.index == region_index)
            if permutation_index > -1:
                self.permutation = next(p for p in self.region.permutations if p.index == permutation_index)
                
        if node_index > -1:
            self.bone = next((n.name for n in nodes if n.index == node_index), None)
        
        self.translation = [float(n) * 100 for n in element.SelectField("translation").GetStringData()]
        
        self.rotation = utils.ijkw_to_wxyz([float(n) for n in element.SelectField("rotation").GetStringData()])
        self.scale = float(element.SelectField("scale").GetStringData())
        self.direction = ([float(n) for n in element.SelectField("direction").GetStringData()])
    
class MarkerGroup:
    name: str
    type: MarkerType
    index: int
    markers: list[Marker]
    
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
            
    def to_blender(self, armature: bpy.types.Object, collection: bpy.types.Collection, size_factor: float):
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
            ob = bpy.data.objects.new(name=self.name, object_data=None)
            collection.objects.link(ob)
            ob.parent = armature
            if marker.bone:
                ob.parent_type = "BONE"
                ob.parent_bone = marker.bone
                ob.matrix_world = armature.pose.bones[marker.bone].matrix @ Matrix.LocRotScale(marker.translation, marker.rotation, Vector.Fill(3, 1))

            nwo = ob.nwo
            nwo.marker_type = self.type.name
            if marker.region:
                nwo.marker_uses_regions = True
                utils.set_region(ob, marker.region.name)
                # Check if there is a marker for every permutation
                if marker.linked_to and len(marker.linked_to) + 1 != len(marker.region.permutations):
                    # If not pick if this is include or exclude type depending on whichever means less permutation entries need to be added
                    # If a tie prefer exclude
                    include_permutations = [m.permutation.name for m in marker.linked_to if m.permutation]
                    exclude_permutations = [p.name for p in marker.region.permutations if p.name not in include_permutations]
                    if len(include_permutations) < len(exclude_permutations):
                        nwo.marker_permutation_type = "include"
                        utils.set_marker_permutations(ob, include_permutations)
                    else:
                        utils.set_marker_permutations(ob, exclude_permutations)
                    
            
            ob.empty_display_type = "ARROWS"
            ob.empty_display_size *= size_factor
            
            if self.type == MarkerType._connected_geometry_marker_type_target:
                ob.empty_display_size = marker.scale * 100
                ob.empty_display_type = "SPHERE"
            elif self.type == MarkerType._connected_geometry_marker_type_garbage:
                ob.nwo.marker_velocity = marker.direction
            elif self.type == MarkerType._connected_geometry_marker_type_hint:
                hint_parts = self.name.split('_')
                if len(hint_parts) > 1:
                    hint_type = hint_parts[1]
                    nwo.marker_hint_type = hint_type
                    if nwo.marker_hint_type != 'bunker' and len(hint_parts) > 2:
                        hint_subtype = hint_parts[2]
                        if hint_subtype in ('right', 'left'):
                            nwo.marker_hint_side = hint_subtype
                        elif hint_subtype in ('step', 'crouch', 'stand'):
                            nwo.marker_hint_height = hint_subtype
            
            objects.append(ob)
            
        return objects
    
def get_blender_material(name, shader_path=""):
    mat = bpy.data.materials.get(name)
    if not mat:
        if name == '+sky' or name == '+seamsealer':
            add_special_materials('h4' if utils.is_corinth() else 'reach', 'scenario')
            mat = bpy.data.materials.get(name)
        else:
            mat = bpy.data.materials.new(name)
            mat.nwo.shader_path = shader_path
        
    return mat