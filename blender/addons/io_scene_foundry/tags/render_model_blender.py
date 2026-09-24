

from collections import defaultdict
import math
from mathutils import Color, Matrix, Vector

from ..tools.rigging import HaloRig, needs_reach_fp_ik_fix

from ..constants import HALO_FACTOR

from .connected_geometry import CompressionBounds, InstancePlacement, MarkerGroup, Material, Mesh, Node, Region, RenderArmature
from .. import import_transform

from .. import utils
from .render_model import RenderModelMetadataTag
import bpy
    
class RenderModelTag(RenderModelMetadataTag):
    tag_ext = 'render_model'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = bpy.context

    def _resolve_region_permutations(self, selection: set | str) -> set:
        if not isinstance(selection, str):
            return set(selection) if selection else set()
        if selection == 'all_permutations':
            return set()

        resolved = set()
        for region in self.regions:
            if not region.permutations:
                continue
            permutation = next(
                (entry for entry in region.permutations if entry.name == selection),
                region.permutations[0],
            )
            resolved.add((region.name, permutation.name))
        return resolved
        
    def to_blend_objects(self, collection, render: bool, markers: bool, model_collection: bpy.types.Collection, existing_armature=None, allowed_region_permutations=set(), from_vert_normals=False, no_io=False, no_armature=False, specific_io_index=None, build_control_rig=False, selected_lod: str = 'ALL'):
        self.collection = collection
        self.model_collection = model_collection
        self._native_nodes = RenderModelMetadataTag.nodes(self)
        self._native_regions = RenderModelMetadataTag.regions(self)
        self._native_instance_placements = self.instance_placements()
        self._native_marker_groups = self.marker_groups()
        self._native_instance_mesh_index = self.instance_mesh_index()
        self._native_compression_bounds = self.compression_bounds()
        self._native_render_materials = self.render_materials() if render else []
        self._native_render_meshes = self.render_meshes() if render else []
        objects = []
        self.armature = self._create_armature(existing_armature, build_control_rig)
        objects.append(self.armature)
        
        self.regions: list[Region] = [Region.from_native(record)
                                      for record in self._native_regions]
        allowed_region_permutations = self._resolve_region_permutations(
            allowed_region_permutations)
        
        if render:
            # print("Creating Render Geometry")
            result = self._create_render_geometry(allowed_region_permutations, from_vert_normals, no_io, specific_io_index, selected_lod)
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

        if build_control_rig and render:
            self._apply_control_rig_deform_shapes_after_geometry()
        
        if no_armature:
            objects.pop(0)
            data = self.armature.data
            bpy.data.objects.remove(self.armature)
            bpy.data.armatures.remove(data)
            return objects
        
        return objects, self.armature

    def _apply_control_rig_deform_shapes_after_geometry(self):
        if self.armature is None or self.armature.type != 'ARMATURE':
            return

        rig = HaloRig(
            self.context,
            import_transform.scale_factor(),
            self.scene_nwo.forward_direction,
            any(bone.name.endswith(("_pitch", "_yaw")) for bone in self.armature.pose.bones),
            False,
        )
        rig.rig_ob = self.armature
        rig.rig_data = self.armature.data
        rig.rig_pose = self.armature.pose
        rig.apply_halo_bone_shape()
        if any(bone.name.startswith(("FK_", "IK_", "PT_")) for bone in self.armature.data.bones):
            rig.build_fk_ik_rig(
                reverse_controls=self.armature.nwo.invert_control_rig,
                constraints_only=True,
                reach_fp_ik_fix=needs_reach_fp_ik_fix(self.tag_path.RelativePathWithExtension),
            )
    
    def _create_armature(self, existing_armature=None, build_control_rig=False):
        # print("Creating Armature")
        arm = RenderArmature(f"{self.tag_path.ShortName}", existing_armature, tag_path=self.tag_path.RelativePathWithExtension)
        if arm.data.bones:
            return arm.ob
        self.nodes: list[Node] = []
        uses_aim_bones = False
        uses_pedestal = False
        root = None
        reach_fp_fix = False
        reach_fp_ik_fix = False
        pedestal = None
        pitch = None
        yaw = None
        nodes_dict = {}
        for record in self._native_nodes:
            # Halo 1 stores model-node default rotations in the inverse
            # convention used by later games. Convert them before composing
            # each local transform into the Blender rest pose.
            node = Node.from_native(record, invert_rotation=self.game == 'halo1')
            rotation = record.rotation
            parent_index = record.parent_index
            if parent_index > -1:
                if parent_index >= len(self._native_nodes):
                    raise ValueError(
                        f"Node {record.index} parent index {parent_index} is out of range")
                node.parent_name = self._native_nodes[parent_index].name
                
            if record.index == 0:
                root = node
                pedestal = node.name
                if node.name.endswith(('pedestal')):
                    uses_pedestal = True
                    
                if rotation[1] == 0.5:
                    reach_fp_fix = True
                    
            elif node.parent_name == root.name and node.name.endswith(('aim_pitch', 'aim_yaw')):
                uses_aim_bones = True
                if node.name.endswith('aim_pitch'):
                    pitch = node.name
                elif node.name.endswith('aim_yaw'):
                    yaw = node.name
                
            self.nodes.append(node)
            nodes_dict[node.name] = node

        reach_fp_ik_fix = reach_fp_fix and needs_reach_fp_ik_fix(self.tag_path.RelativePathWithExtension)
            
        for node in self.nodes:
            if node.parent_name and node.parent is None:
                node.parent = nodes_dict[node.parent_name]
        
        self.model_collection.objects.link(arm.ob)
        arm.ob.select_set(True)
        utils.set_active_object(arm.ob)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        for node in self.nodes: arm.create_bone(node)
        for node in self.nodes: arm.parent_bone(node)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        # Set render_model ref for node order
        arm.ob.nwo.node_order_source = self.tag_path.RelativePathWithExtension
        
        if build_control_rig:
        # make the rig not terrible
            rig = HaloRig(self.context, import_transform.scale_factor(), self.scene_nwo.forward_direction, uses_aim_bones, False)
            rig.rig_ob = arm.ob
            rig.rig_data = arm.data
            rig.rig_pose = arm.ob.pose
            rig.build_bones(pedestal=pedestal, pitch=pitch, yaw=yaw)
            if uses_pedestal or uses_aim_bones:
                rig.build_and_apply_control_shapes(reach_fp_fix=reach_fp_fix, reverse_control=False)
            rig.apply_halo_bone_shape()
            rig.build_fk_ik_rig(reverse_controls=False, reach_fp_ik_fix=reach_fp_ik_fix)
            rig.generate_bone_collections()

        return arm.ob
        

    def _create_render_geometry(self, allowed_region_permutations: set | str, from_vert_normals=False, no_io=False, specific_io_index=None, selected_lod: str = 'ALL'):
        objects = []
        if not self._native_compression_bounds:
            utils.print_warning("Render Model has no compression info. Cannot import render model mesh")
            return []
        self.bounds = CompressionBounds.from_native(
            self._native_compression_bounds[0])
        native_render_meshes = self._native_render_meshes
        
        materials = [Material.from_native(record)
                     for record in self._native_render_materials]
        materials_by_index = {material.index: material for material in materials}

        clone_meshes: list[Mesh] = []
        original_meshes_by_perm_name = {}
        regions_by_name = {region.name: region for region in self.regions}
        selected_lod = selected_lod.upper()
        if selected_lod not in {'ALL', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6'}:
            selected_lod = 'ALL'
        lod_collections: dict[str, bpy.types.Collection] = {}

        def collection_for_lod(lod: str) -> bpy.types.Collection:
            if not lod:
                return self.collection
            collection = lod_collections.get(lod)
            if collection is None:
                collection = bpy.data.collections.new(f'{self.tag_path.ShortName}_{lod}')
                self.collection.children.link(collection)
                lod_collections[lod] = collection
            return collection

        allowed_region_permutations = self._resolve_region_permutations(
            allowed_region_permutations)

        valid_instance_indexes = set() if allowed_region_permutations else None
        ob_region_perms = {}
        instance_region_permutations = defaultdict(lambda: defaultdict(list))
        region_perm_raw_mesh: dict[tuple[str, str, int]: int] = {}
        for region in self.regions:
            for permutation in region.permutations:
                region_perm = (region.name, permutation.name)
                if allowed_region_permutations and region_perm in allowed_region_permutations:
                    valid_instance_indexes.update(permutation.instance_indices)

                for instance_index in permutation.instance_indices:
                    instance_region_permutations[instance_index][region.name].append(permutation.name)

                if self.corinth and allowed_region_permutations and permutation.mesh_index > -1:
                    for i in range(permutation.mesh_count):
                        region_perm_raw_mesh[(region.name, permutation.name, i)] = permutation.mesh_index

        if valid_instance_indexes is not None:
            for record in self._native_instance_placements:
                if record.index not in instance_region_permutations:
                    valid_instance_indexes.add(record.index)
        
        for region in self.regions:
            for permutation in region.permutations:
                region_perm = (region.name, permutation.name)
                if allowed_region_permutations and region_perm not in allowed_region_permutations:
                    continue
                    
                meshes = (permutation.lod_mesh_indices if self.game == 'halo2'
                          else tuple(('', permutation.mesh_index + i)
                                     for i in range(permutation.mesh_count)))
                if self.game == 'halo2' and selected_lod != 'ALL':
                    meshes = tuple(mesh for mesh in meshes if mesh[0] == selected_lod)
                for i, (lod, mesh_index) in enumerate(meshes):
                    real_mesh_idx = None
                    geometry_record = native_render_meshes[mesh_index]
                    if permutation.clone_name:
                        if not allowed_region_permutations or (region.name, permutation.clone_name) in allowed_region_permutations:
                            mesh = Mesh.from_native(
                                native_render_meshes[mesh_index],
                                materials_by_index, self.corinth)
                            mesh.permutation = permutation
                            clone_meshes.append(mesh)
                            continue
                        
                        real_mesh_idx = region_perm_raw_mesh[(region.name, permutation.clone_name, i)]
                        geometry_record = native_render_meshes[real_mesh_idx]

                    mesh = Mesh.from_native(
                        native_render_meshes[mesh_index], materials_by_index,
                        self.corinth, geometry_record)
                    mesh.permutation = permutation
                    mesh.from_vert_normals = from_vert_normals
                    mesh.tag_path = self.tag_path.RelativePathWithExtension
                    
                    obs = mesh.create(None, None, self.nodes, self.armature,
                                      real_mesh_index=real_mesh_idx)
                    for ob in obs:
                        ob_region_perms[ob] = (*region_perm, lod)
                        if lod:
                            ob.name = f'{ob.name}:{lod}'
                        
                    original_meshes_by_perm_name.setdefault(mesh.permutation.name, mesh)
                    objects.extend(obs)
                    target_collection = collection_for_lod(lod)
                    for ob in obs:
                        target_collection.objects.link(ob)
                
        # Instances
        self.instances = []
        if not no_io:
            if specific_io_index is not None:
                valid_instance_indexes = {specific_io_index}
            self.instance_mesh_index = self._native_instance_mesh_index
            if self.instance_mesh_index > -1:
                if valid_instance_indexes is None:
                    for record in self._native_instance_placements:
                        self.instances.append(
                            InstancePlacement.from_native(record, self.nodes))
                else:
                    for record in self._native_instance_placements:
                        if record.index in valid_instance_indexes:
                            self.instances.append(
                                InstancePlacement.from_native(record, self.nodes))

        for ob, region_perm in ob_region_perms.items():
            region, permutation, lod = region_perm
            utils.set_region(ob, region, utils.SetType.MODEL)
            utils.set_permutation(ob, permutation, utils.SetType.MODEL)
            if lod:
                ob.nwo.mesh_lod = lod
            
        if self.instances:
            instance_mesh = Mesh.from_native(
                native_render_meshes[self.instance_mesh_index],
                materials_by_index, self.corinth)
            instance_mesh.from_vert_normals = from_vert_normals
            instance_mesh.tag_path = self.tag_path.RelativePathWithExtension
            ios = instance_mesh.create(
                None, None, self.nodes, self.armature, self.instances,
                is_io=True)
            for ob in ios:
                ob.data.nwo.mesh_type = "_connected_geometry_mesh_type_object_instance"
                self.collection.objects.link(ob)
                
            for instance in self.instances:
                ob = instance.ob
                if not ob:
                    continue

                region_permutations = instance_region_permutations.get(instance.index)
                if not region_permutations:
                    ob.nwo.marker_uses_regions = False
                    continue

                region_names = list(region_permutations)
                if len(region_names) != 1:
                    ob.nwo.marker_uses_regions = False
                    continue

                region_name = region_names[0]
                permutations = region_permutations[region_name]
                region = regions_by_name.get(region_name)
                if region is None:
                    continue

                ob.nwo.marker_uses_regions = True
                utils.set_region(ob, region_name, utils.SetType.MODEL)
                if len(region.permutations) == 1:
                    # Keep the sole real region permutation explicit rather than
                    # representing it as an empty exclude list.
                    ob.nwo.marker_permutation_type = "include"
                    utils.set_marker_permutations(ob, permutations)
                elif len(permutations) != len(region.permutations):
                    # Pick if this is include or exclude type depending on whichever means less permutation entries need to be added
                    # If a tie prefer exclude
                    exclude_permutations = [p.name for p in region.permutations if p.name not in permutations]
                    if len(permutations) < len(exclude_permutations):
                        ob.nwo.marker_permutation_type = "include"
                        utils.set_marker_permutations(ob, permutations)
                    else:
                        utils.set_marker_permutations(ob, exclude_permutations)
                        
                
            objects.extend(ios)
            
        for cmesh in clone_meshes:
            tmesh = original_meshes_by_perm_name.get(cmesh.permutation.clone_name)
            if tmesh is None:
                continue

            permutation = self.scene_nwo.permutations_table.get(tmesh.permutation.name)
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
        for record in self._native_marker_groups:
            marker_group = MarkerGroup.from_native(record, self.nodes, self.regions)
            objects.extend(marker_group.to_blender(self.armature, markers_collection, marker_size_factor, allowed_region_permutations))
            
        return objects
    
    
    def skylights_to_blender(self, parent_collection: bpy.types.Collection = None) -> list:
        objects = []
        if self.corinth:
            return [] # H4+ no longer uses skylights, instead using a model scenario_structure_lighting_info tag

        sky = self.sky_data()

        if not sky.is_sky:
            return []

        sun_index = len(sky.lights) - 1
        
        if sun_index < 0:
            return []
        
        sun_as_vmf_light = sky.sun_as_vmf_light
        
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
            
            obj.matrix_world = import_transform.transform_matrix(Matrix.LocRotScale(loc, rot, sca))
            
        for index, record in enumerate(sky.lights):
            direction = Vector(record.direction).normalized()
            color = Color(record.intensity)
            power = record.solid_angle
            
            if not sun_as_vmf_light and index == sun_index:
                two_pi = 2.0 * math.pi
                cos_theta = 1.0 - (power / two_pi)
                cos_theta = max(-1.0, min(1.0, cos_theta))
                half_angle_radians = math.acos(cos_theta)
                self.scene_nwo.sun_size = 2.0 * half_angle_radians * 180.0 / math.pi
                continue
            
            data = bpy.data.lights.new(f"skylight:{index}", 'SUN')
                
            ob = bpy.data.objects.new(data.name, data)
            
            scale_by_direction(ob, direction)
            
            data.energy = power
            data.color = color
            
            collection.objects.link(ob)
            objects.append(ob)
        
        if not sun_as_vmf_light:
            if len(sky.sun) < 6:
                raise ValueError(
                    f"{self.tag_path.RelativePathWithExtension} sky sun array "
                    f"has {len(sky.sun)} of 6 values")
            sun_dx, sun_dy, sun_dz, sun_ir, sun_ib, sun_ig = sky.sun[:6]
            
            data = bpy.data.lights.new("Sun", 'SUN')
            ob = bpy.data.objects.new(data.name, data)

            direction = Vector((sun_dx, sun_dy, sun_dz))
            scale_by_direction(ob, direction, 150)
            
            normalized_color = Vector((sun_ir, sun_ib, sun_ig)).normalized()
            
            data.color = normalized_color
            data.energy = sun_ir / normalized_color[0] / 2
            
            collection.objects.link(ob)
            objects.append(ob)
            
        self.scene_nwo.sun_bounce_scale = sky.sun_bounce_scale
        self.scene_nwo.skylight_bounce_scale = sky.skylight_bounce_scale
        self.scene_nwo.sun_as_vmf_light = sun_as_vmf_light
        
        return objects
            
            
    def get_bounds(self):
        bounds = self.compression_bounds()
        if not bounds:
            raise ValueError(f"{self.tag_path.RelativePathWithExtension} has no compression bounds")
        return CompressionBounds.from_native(bounds[0])
    
    def insert_empty_region_perms(self, empty_region_perms: dict[str, set]):
        super().insert_empty_region_perms(empty_region_perms)
                
