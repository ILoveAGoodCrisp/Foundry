

from collections import defaultdict
import math
import bmesh
from mathutils import Color, Euler, Matrix, Quaternion, Vector

from ..tools.rigging import HaloRig

from ..constants import HALO_FACTOR

from .connected_geometry import CompressionBounds, InstancePlacement, MarkerGroup, Material, Mesh, Node, Region, RenderArmature
from .Tags import *

from .. import utils
from ..managed_blam import Tag
import bpy
    
class RenderModelTag(Tag):
    tag_ext = 'render_model'
    
    def _read_fields(self):
        self.reference_structure_meta_data = self.tag.SelectField("Reference:structure meta data") if self.corinth else None
        self.block_nodes = self.tag.SelectField("Block:nodes")
        self.struct_render_geometry = self.tag.SelectField("Struct:render geometry")
        self.block_compression_info = self.tag.SelectField("Struct:render geometry[0]/Block:compression info")
        self.block_per_mesh_temporary = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh temporary")
        self.block_regions = self.tag.SelectField("Block:regions")
        self.block_meshes = self.tag.SelectField("Struct:render geometry[0]/Block:meshes")
        self.block_materials = self.tag.SelectField("Block:materials")
        self.block_marker_groups = self.tag.SelectField("Block:marker groups")
        
    def set_structure_meta_ref(self, meta_path):
        if self._tag_exists(meta_path):
            self.reference_structure_meta_data.Path = self._TagPath_from_string(meta_path)
            self.tag_has_changes = True
        else:
            print("Failed to add structure meta reference. Structure meta tag does not exist")
            
    def get_nodes(self):
        return [e.SelectField('name').GetStringData() for e in self.block_nodes.Elements]
    
    def get_regions(self) -> list[str]:
        return [e.Fields[0].GetStringData() for e in self.block_regions.Elements]
    
    def get_permutations(self, region: str = "") -> list[str]:
        '''Returns a list of render model permutations. A region name can be passed in to only return permutations from that region'''
        if region:
            for element in self.block_regions.Elements:
                if element.Fields[0].GetStringData() == region:
                    return [e.Fields[0].GetStringData() for e in element.Fields[1].Elements]
            else:
                return []
        else:
            permutations = {}
            for element in self.block_regions.Elements:
                permutations.update({e.Fields[0].GetStringData(): None for e in element.Fields[1].Elements}) # using dict instead of set to maintain insertion order
            return list(permutations)
    
    def read_render_geometry(self):
        render_geo = self._GameRenderGeometry()
        mesh_info = render_geo.GetMeshInfo(self.struct_render_geometry)
        print("index_bytes", mesh_info.index_bytes)
        print("index_count", mesh_info.index_count)
        print("parts", mesh_info.parts)
        print("subparts", mesh_info.subparts)
        print("triangle_count", mesh_info.triangle_count)
        print("vertex_bytes", mesh_info.vertex_bytes)
        print("vertex_count", mesh_info.vertex_count)
        print("vertex_type", mesh_info.vertex_type)
        
    def read_render_model(self):
        data_block = self.struct_render_geometry.Elements[0].SelectField('per mesh temporary')
        render_model = self._GameRenderModel()
        node_indices = render_model.GetNodeIndiciesFromMesh(data_block, 0)
        node_weights = render_model.GetNodeWeightsFromMesh(data_block, 0)
        normals = render_model.GetNormalsFromMesh(data_block, 0)
        positions = render_model.GetPositionsFromMesh(data_block, 0)
        tex_coords = render_model.GetTexCoordsFromMesh(data_block, 0)
        print("\nnode_indices")
        print("#"*50 + '\n')
        print([i for i in node_indices])
        print("\nnode_weights")
        print("#"*50 + '\n')
        print([i for i in node_weights])
        print("\nnormals")
        print("#"*50 + '\n')
        print([i for i in normals])
        print("\npositions")
        print("#"*50 + '\n')
        print([i for i in positions])
        print("\ntex_coords")
        print("#"*50 + '\n')
        print([i for i in tex_coords])
        
    def to_blend_objects(self, collection, render: bool, markers: bool, model_collection: bpy.types.Collection, existing_armature=None, allowed_region_permutations=set(), from_vert_normals=False, no_io=False, no_armature=False, specific_io_index=None):
        self.collection = collection
        self.model_collection = model_collection
        objects = []
        self.armature = self._create_armature(existing_armature)
        objects.append(self.armature)
        
        self.regions: list[Region] = []
        for element in self.block_regions.Elements:
            self.regions.append(Region(element))
        
        if render:
            # print("Creating Render Geometry")
            result = self._create_render_geometry(allowed_region_permutations, from_vert_normals, no_io, specific_io_index)
            if result:
                objects.extend(result)
            else:
                if no_armature:
                    objects.pop(0)
                    data = self.armature.data
                    bpy.data.objects.remove(self.armature)
                    bpy.data.armatures.remove(data)
                    return objects
                else:
                    return objects, self.armature
        if markers:
            # print("Creating Markers")
            objects.extend(self._create_markers(allowed_region_permutations))
            
        meshes = {ob.data for ob in objects if ob.data is not None and ob.type == 'MESH'}
        for me in meshes:
            utils.consolidate_face_attributes(me)
        
        if no_armature:
            objects.pop(0)
            data = self.armature.data
            bpy.data.objects.remove(self.armature)
            bpy.data.armatures.remove(data)
            return objects
        
        return objects, self.armature
    
    def _create_armature(self, existing_armature=None):
        # print("Creating Armature")
        arm = RenderArmature(f"{self.tag.Path.ShortName}", existing_armature)
        self.nodes: list[Node] = []
        uses_aim_bones = False
        uses_pedestal = False
        root = None
        reach_fp_fix = False
        pedestal = None
        pitch = None
        yaw = None
        for element in self.block_nodes.Elements:
            node = Node(element.SelectField("name").GetStringData(), )
            
            node.index = element.ElementIndex
            translation = element.SelectField("default translation").Data
            node.translation = Vector([n for n in translation]) * 100
            rotation = element.SelectField("default rotation").Data
            node.rotation = Quaternion([rotation[3], rotation[0], rotation[1], rotation[2]])
            inverse_forward = element.SelectField("inverse forward").Data
            node.inverse_forward = Vector([n for n in inverse_forward])
            inverse_left = element.SelectField("inverse left").Data
            node.inverse_left = Vector([n for n in inverse_left])
            inverse_up = element.SelectField("inverse up").Data
            node.inverse_up = Vector([n for n in inverse_up])
            inverse_position = element.SelectField("inverse position").Data
            node.inverse_position = Vector([n for n in inverse_position]) * 100
            inverse_scale = element.SelectField("inverse scale").Data
            node.inverse_scale = float(inverse_scale)
            
            parent_index = element.SelectField("parent node").Value
            if parent_index > -1:
                node.parent = self.block_nodes.Elements[parent_index].SelectField("name").GetStringData()
                
            if element.ElementIndex == 0:
                root = node
                pedestal = node.name
                if node.name.endswith(('pedestal')):
                    uses_pedestal = True
                    
                if rotation[1] == 0.5:
                    reach_fp_fix = True
                    
            elif node.parent == root.name and node.name.endswith(('aim_pitch', 'aim_yaw')):
                uses_aim_bones = True
                if node.name.endswith('aim_pitch'):
                    pitch = node.name
                elif node.name.endswith('aim_yaw'):
                    yaw = node.name
                
            self.nodes.append(node)
        
        if existing_armature is None:
            self.model_collection.objects.link(arm.ob)
            arm.ob.select_set(True)
            utils.set_active_object(arm.ob)
            bpy.ops.object.editmode_toggle()
            for node in self.nodes: arm.create_bone(node)
            for node in self.nodes: arm.parent_bone(node)
            bpy.ops.object.editmode_toggle()
            # Set render_model ref for node order
            arm.ob.nwo.node_order_source = self.tag_path.RelativePathWithExtension
            
            # make the rig not terrible
            scale = 1 / 0.03048
            rig = HaloRig(self.context, scale, 'x', uses_aim_bones, False)
            rig.rig_ob = arm.ob
            rig.rig_data = arm.data
            rig.rig_pose = arm.ob.pose
            rig.build_bones(pedestal=pedestal, pitch=pitch, yaw=yaw)
            if uses_pedestal or uses_aim_bones:
                rig.build_and_apply_control_shapes(wireframe=True, reach_fp_fix=reach_fp_fix, reverse_control=True)
            rig.apply_halo_bone_shape()
            rig.build_fk_ik_rig(reverse_controls=True)
            rig.generate_bone_collections()
        else:
            for node in self.nodes:
                node.bone = next((b for b in arm.ob.data.bones if b.name == node.name), None)
        
        return arm.ob
        

    def _create_render_geometry(self, allowed_region_permutations: set | str, from_vert_normals=False, no_io=False, specific_io_index=None):
        objects = []
        if not self.block_compression_info.Elements.Count:
            utils.print_warning("Render Model has no compression info. Cannot import render model mesh")
            return []
        self.bounds = CompressionBounds(self.block_compression_info.Elements[0])
        render_model = self._GameRenderModel()
        
        materials = [Material(e) for e in self.block_materials.Elements]
    
        
        original_meshes: list[Mesh] = []
        clone_meshes: list[Mesh] = []
        mesh_node_map = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh node map")
        
        valid_instance_indexes = set() if allowed_region_permutations else None
        
        if isinstance(allowed_region_permutations, str): # if str use all regions but only the given perm
            allowed_region_permutations = {(r.name, allowed_region_permutations) for r in self.regions}
            
        ob_region_perms = {}
        region_perm_raw_mesh: dict[tuple[str, str, int]: int] = {}
        if self.corinth and allowed_region_permutations: # need to create real raw mesh indices for clones
            for r in self.regions:
                for p in r.permutations:
                    for i in range(p.mesh_count):
                        region_perm_raw_mesh[tuple((r.name, p.name, i))] = p.mesh_index
        
        for region in self.regions:
            for permutation in region.permutations:
                if allowed_region_permutations:
                    region_perm = tuple((region.name, permutation.name))
                    if region_perm not in allowed_region_permutations:
                        continue
                    valid_instance_indexes.update(permutation.instance_indices)
                    
                if permutation.mesh_index < 0: continue
                for i in range(permutation.mesh_count):
                    real_mesh_idx = None
                    mesh = Mesh(self.block_meshes.Elements[permutation.mesh_index + i], self.bounds, permutation, materials, mesh_node_map, from_vert_normals=from_vert_normals)
                    for part in mesh.parts:
                        part.material = materials[part.material_index]
                    
                    if mesh.permutation.clone_name:
                        if not allowed_region_permutations or tuple((region.name, mesh.permutation.clone_name)) in allowed_region_permutations:
                            clone_meshes.append(mesh)
                            continue
                        
                        real_mesh_idx = region_perm_raw_mesh[tuple((region.name, mesh.permutation.clone_name, i))]

                    obs = mesh.create(render_model, self.block_per_mesh_temporary, self.nodes, self.armature, real_mesh_index=real_mesh_idx)
                    # NOTE This code doesn't work correctly
                    if False and mesh.mesh_keys:
                        shape_names = {e.Fields[0].Data: utils.any_partition(e.Fields[1].GetStringData(), ":", True) for e in self.tag.SelectField("Struct:render geometry[0]/Block:shapeNames").Elements}
                        new_obs = []
                        for ob in obs:
                            face_groups = defaultdict(list)
                            bm = bmesh.new()
                            bm.from_mesh(ob.data)
                            for face in bm.faces:
                                keys = [mesh.mesh_keys[v.index] for v in face.verts]
                                uniq = set(keys)
                                if len(uniq) == 1:
                                    face_groups[keys[0]].append(face.index)
                                else:
                                    for k in uniq:
                                        face_groups[k].append(face.index)
                                        
                            bm.free()
                                
                            for key, poly_indices in face_groups.items():
                                new_mesh = ob.data.copy()
                                new_ob = ob.copy()
                                new_ob.data = new_mesh
                                name = shape_names[key]
                                new_ob.name = name
                                new_mesh.name = name

                                bm = bmesh.new()
                                bm.from_mesh(new_mesh)
                                
                                to_delete_faces = [f for f in bm.faces if f.index not in poly_indices]
                                bmesh.ops.delete(bm, geom=to_delete_faces, context='FACES')
                                
                                bm.to_mesh(new_mesh)
                                bm.free()
                                new_obs.append(new_ob)
                                ob_region_perms[new_ob] = utils.dot_partition(ob.name).split(":")
                            
                        obs = new_obs
                    else:
                        for ob in obs:
                            ob_region_perms[ob] = utils.dot_partition(ob.name).split(":")
                        
                    original_meshes.append(mesh)
                    objects.extend(obs)
                    for ob in obs:
                        self.collection.objects.link(ob)
                
        # Instances
        self.instances = []
        if not no_io:
            if specific_io_index is not None:
                valid_instance_indexes = [specific_io_index]
            self.instance_mesh_index = self.tag.SelectField("LongBlockIndex:instance mesh index").Value
            if self.instance_mesh_index > -1:
                if valid_instance_indexes is None:
                    for element in self.tag.SelectField("Block:instance placements").Elements:
                        self.instances.append(InstancePlacement(element, self.nodes))
                else:
                    for element in self.tag.SelectField("Block:instance placements").Elements:
                        if element.ElementIndex in valid_instance_indexes:
                            self.instances.append(InstancePlacement(element, self.nodes))

        for ob, region_perm in ob_region_perms.items():
            region, permutation = region_perm
            utils.set_region(ob, region)
            utils.set_permutation(ob, permutation)
            
        if self.instances:
            instance_mesh = Mesh(self.block_meshes.Elements[self.instance_mesh_index], self.bounds, None, materials, mesh_node_map, from_vert_normals=from_vert_normals)
            ios = instance_mesh.create(render_model, self.block_per_mesh_temporary, self.nodes, self.armature, self.instances, is_io=True)
            for ob in ios:
                ob.data.nwo.mesh_type = "_connected_geometry_mesh_type_object_instance"
                self.collection.objects.link(ob)
                
            for instance in self.instances:
                i_permutations = []
                ob = instance.ob
                if not ob: continue
                for region in self.regions:
                    for perm in region.permutations:
                        for instance_index in perm.instance_indices:
                            if instance_index == instance.index:
                                if not ob.nwo.marker_uses_regions:
                                    ob.nwo.marker_uses_regions = True
                                    utils.set_region(ob, region.name)
                                i_permutations.append(perm.name)
                                break
                    
                    if ob.nwo.marker_uses_regions:
                        if len(i_permutations) != len(region.permutations):
                            # Pick if this is include or exclude type depending on whichever means less permutation entries need to be added
                            # If a tie prefer exclude
                            exclude_permutations = [p.name for p in region.permutations if p.name not in i_permutations]
                            if len(i_permutations) < len(exclude_permutations):
                                ob.nwo.marker_permutation_type = "include"
                                utils.set_marker_permutations(ob, i_permutations)
                            else:
                                utils.set_marker_permutations(ob, exclude_permutations)
                        break
                
            objects.extend(ios)
            
        for cmesh in clone_meshes:
            for tmesh in original_meshes:
                if tmesh.permutation.name == cmesh.permutation.clone_name:
                    permutation = self.context.scene.nwo.permutations_table.get(tmesh.permutation.name)
                    if permutation is None:
                        continue
                    clone = permutation.clones.get(cmesh.permutation.name)
                    if clone is None:
                        clone = permutation.clones.add()
                        clone.name = cmesh.permutation.name
                        print(f"\n--- Added permutation clone: {permutation.name} --> {clone.name}")
                    for true_part, clone_part in zip(tmesh.parts, cmesh.parts):
                        source_material = true_part.material
                        destination_material = clone_part.material
                        if source_material is None or destination_material is None or source_material.blender_material is None or destination_material.blender_material is None or source_material.blender_material is destination_material.blender_material:
                            continue
                        # check existing
                        for override in clone.material_overrides:
                            if source_material.blender_material is override.source_material:
                                break
                        else:
                            override = clone.material_overrides.add()
                            override.source_material = source_material.blender_material
                            override.destination_material = destination_material.blender_material
                            print(f"--- Material Override added for clone {clone.name}: {override.source_material.name} --> {override.destination_material.name}")
                    break
                
        if "sky" in self.tag_path.ShortName:
            for ob in objects:
                utils.hide_from_rays(ob)
        
        return objects
    
    def _create_markers(self, allowed_region_permutations: set):
        # Model Markers
        objects = []
        markers_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_markers")
        self.collection.children.link(markers_collection)
        marker_size_factor = max(self.bounds.x1 - self.bounds.x0, self.bounds.y1 - self.bounds.y0, self.bounds.z1 - self.bounds.z0) * 0.025
        for element in self.block_marker_groups.Elements:
            marker_group = MarkerGroup(element, self.nodes, self.regions)
            objects.extend(marker_group.to_blender(self.armature, markers_collection, marker_size_factor, allowed_region_permutations))
            
        return objects
    
    
    def skylights_to_blender(self, parent_collection: bpy.types.Collection = None) -> list:
        objects = []
        if self.corinth:
            return [] # H4+ no longer uses skylights, instead using a model scenario_structure_lighting_info tag
        
        flags = self.tag.SelectField("WordFlags:flags")
        
        if not flags.TestBit("this is supposed to be a sky"):
            return []
        
        block_sky_lights = self.tag.SelectField("Block:sky lights")
        sun_index = block_sky_lights.Elements.Count - 1
        
        if sun_index < 0:
            return []
        
        sun_as_vmf_light = flags.TestBit("sun as vmf light")
        
        collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_skylights")
        
        if parent_collection is None:
            self.context.scene.collection.children.link(collection)
        else:
            parent_collection.children.link(collection)
            
        def scale_by_direction(obj: bpy.types.Object, dir: Vector, scale=100):
            radius = scale * HALO_FACTOR
            rot = dir.to_track_quat('Z', 'Y')
            loc = dir * radius
            sca = Vector.Fill(3, HALO_FACTOR)
            
            obj.matrix_world = Matrix.LocRotScale(loc, rot, sca)
            
        for element in block_sky_lights.Elements:
            direction = Vector((*element.Fields[0].Data,)).normalized()
            color = Color((*element.Fields[1].Data,)) # intensity
            power = element.Fields[2].Data # solid angle
            
            if not sun_as_vmf_light and element.ElementIndex == sun_index:
                two_pi = 2.0 * math.pi
                cos_theta = 1.0 - (power / two_pi)
                cos_theta = max(-1.0, min(1.0, cos_theta))
                half_angle_radians = math.acos(cos_theta)
                self.context.scene.nwo.sun_size = 2.0 * half_angle_radians * 180.0 / math.pi
            
            data = bpy.data.lights.new(f"skylight:{element.ElementIndex}", 'SUN')
                
            ob = bpy.data.objects.new(data.name, data)
            
            scale_by_direction(ob, direction)
            
            data.energy = power
            data.color = color
            
            collection.objects.link(ob)
            objects.append(ob)
        
        if not sun_as_vmf_light:
            sun_array = self.tag.SelectField("Array:sun")
            # direction
            sun_dx = sun_array.Elements[0].Fields[0].Data
            sun_dy = sun_array.Elements[1].Fields[0].Data
            sun_dz = sun_array.Elements[2].Fields[0].Data
            # RGB intensity
            sun_ir = sun_array.Elements[3].Fields[0].Data
            sun_ib = sun_array.Elements[4].Fields[0].Data
            sun_ig = sun_array.Elements[5].Fields[0].Data
            
            data = bpy.data.lights.new("Sun", 'SUN')
            ob = bpy.data.objects.new(data.name, data)
            
            direction = Vector((sun_dx, sun_dy, sun_dz))
            scale_by_direction(ob, direction, 150)
            
            normalized_color = Vector((sun_ir, sun_ib, sun_ig)).normalized()
            
            data.color = normalized_color
            data.energy = sun_ir / normalized_color[0]
            
            collection.objects.link(ob)
            objects.append(ob)
            
        # sunlight_mutliplier = self.tag.SelectField("Real:direct sun light multiplier").Data
        # skylight_multiplier = self.tag.SelectField("Real:sky dome and all bounce light multiplier").Data
        self.context.scene.nwo.sun_bounce_scale = self.tag.SelectField("Real:sun 1st bounce scaler").Data
        self.context.scene.nwo.skylight_bounce_scale = self.tag.SelectField("Real:sky light 1st bounce scaler").Data
        self.context.scene.nwo.sun_as_vmf_light = sun_as_vmf_light
        
        return objects
            
            
    def get_bounds(self):
        return CompressionBounds(self.block_compression_info.Elements[0])
    
    def insert_empty_region_perms(self, empty_region_perms: dict[str, set]):
        print("\nAdding Empty Region Permutations")
        for region_element in self.block_regions.Elements:
            region = region_element.Fields[0].GetStringData()
            perms = empty_region_perms.get(region)
            if perms is None:
                continue
            
            permutations_block = region_element.SelectField("Block:permutations")
            # Getting all existing perms to ensure we don't duplicate any, for example those created by clones
            existing_perms = {e.Fields[0].GetStringData() for e in permutations_block.Elements}
            remaining_perms = perms.difference(existing_perms)
            print(f"\n--- Adding empty permutations to existing region {region}")
            for perm in sorted(remaining_perms): # Sorting this to ensure a consistent order in multiple exports
                perm_element = permutations_block.AddElement()
                perm_element.Fields[0].SetStringData(perm)
                perm_element.Fields[1].Data = -1 # mesh index
                print(f"\tAdded permutation {perm}")
                self.tag_has_changes = True
            
            empty_region_perms.pop(region)
        
        # This now contains only the completely empty regions
        if empty_region_perms:
            self.tag_has_changes = True
        
        for region, perms in empty_region_perms.items():
            region_element = self.block_regions.AddElement()
            region_element.Fields[0].SetStringData(region)
            print(f"\n--- Created new empty region {region}")
            
            permutations_block = region_element.SelectField("Block:permutations")
            for perm in sorted(perms):
                perm_element = permutations_block.AddElement()
                perm_element.Fields[0].SetStringData(perm)
                perm_element.Fields[1].Data = -1 # mesh index
                print(f"\tAdded permutation {perm}")
                