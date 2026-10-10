"""Build Foundry objects from JMS interchange data without the Halo toolset."""
from collections import defaultdict
from dataclasses import asdict
from math import radians, acos, pi
from pathlib import Path
import json
import numpy as np
import re

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

from .jms_format import JMS
from .coordinates import axis_rotation
from .. import utils, marker_axis

FRAME_PREFIXES = ('frame_', 'frame ', 'bip_', 'bip ', 'b_', 'b ')


def is_frame_name(name):
    return name.casefold().startswith(FRAME_PREFIXES)


def canonical_bone_name(name):
    # Classic JMS exporters may spell a tag bone's word separators as spaces.
    # Halo 2's compiler strips the bare frame prefix to an empty node name.
    if name.casefold() == 'frame':
        return ''
    return re.sub(r'[\s_]+', '_', utils.remove_node_prefix(name).casefold())


class JMSImporter:
    def __init__(self, owner, path, legacy_type, *, tag_armature=None,
                 parent_collection=None, geometry_only=False, allowed_region_permutations=(), shader_paths=None):
        self.owner = owner
        self.path = Path(path)
        self.jms = JMS.from_file(path)
        self.scale = owner.scale_factor
        self.rotation = axis_rotation(owner.from_x_rot)
        self.is_model = self.model_import(legacy_type, tag_armature)
        self.objects = []
        self.materials = {}
        self.created_materials = []
        self.props = {}
        self.armature = None
        self.frames = {}
        self.node_world = {}
        self.tag_armature = tag_armature
        self.parent_collection = parent_collection
        self.tag_bone_names = {}
        self.geometry_only = geometry_only
        self.allowed_region_permutations = set(allowed_region_permutations)
        self.shader_paths = shader_paths or {}

    def model_import(self, legacy_type, tag_armature):
        if legacy_type != 'auto':
            return legacy_type == 'model'
        if tag_armature is not None:
            return True
        # BSP exports also contain a root node. Special BSP surfaces and the
        # destination scenario are stronger evidence than node presence.
        from ..tools.importer import JMSMaterialSlot
        if any(JMSMaterialSlot.from_name(m.name).mesh_type != 'default'
               or m.name.startswith(('+sky', '+seamsealer')) for m in self.jms.materials):
            return False
        if self.path.parent.name.lower() in {'render', 'collision', 'physics'}:
            return True
        asset_type = getattr(getattr(self.owner, 'scene_nwo', None), 'asset_type', '')
        if asset_type in {'scenario', 'prefab'}:
            return False
        return bool(self.jms.nodes)

    def transform(self, transform):
        x, y, z, w = transform.rotation
        q = Quaternion((w, x, y, z))
        q.normalize()
        if self.jms.version < 8205:
            q.invert()
        return Matrix.Translation(Vector(transform.translation)) @ q.to_matrix().to_4x4()

    def scene_matrix(self, matrix):
        matrix = matrix.copy()
        matrix.translation *= self.scale
        return self.rotation @ matrix

    def node_matrices(self):
        for start in range(len(self.jms.nodes)):
            chain, index = [], start
            while index != -1 and index not in self.node_world:
                chain.append(index)
                index = self.jms.nodes[index].parent if self.jms.version < 8205 else -1
            for index in reversed(chain):
                node = self.jms.nodes[index]
                matrix = self.transform(node.transform)
                if self.jms.version < 8205 and node.parent != -1:
                    matrix = self.node_world[node.parent] @ matrix
                self.node_world[index] = matrix

    def object(self, name, data=None):
        ob = bpy.data.objects.new(name, data)
        self.objects.append(ob)
        self.collection.objects.link(ob)
        if getattr(self, 'jms_source_key', None):
            ob['jms_source_key'] = self.jms_source_key
        return ob

    def build(self):
        context = bpy.context
        selected, active = list(context.selected_objects), context.view_layer.objects.active
        collection_name = self.path.stem
        shared_lod = None
        if self.tag_armature is not None:
            lods = {lod.upper() for _, _, lod in self.jms.triangle_groups() if lod}
            kind = next(iter(lods)) if self.geometry_only and len(lods) == 1 else self.path.parent.name
            collection_name = f'{self.tag_armature.name}_{kind}'
            if self.geometry_only and kind in {'L1', 'L2', 'L3', 'L4', 'L5', 'L6'}:
                shared_lod = kind
        parent_collection = self.parent_collection or context.scene.collection
        self.collection = None
        if shared_lod:
            self.collection = next((child for child in parent_collection.children
                                    if child.get('foundry_import_lod') == shared_lod
                                    and child.get('foundry_import_armature') == self.tag_armature), None)
        created_collection = self.collection is None
        if created_collection:
            self.collection = bpy.data.collections.new(collection_name)
            parent_collection.children.link(self.collection)
            if shared_lod:
                self.collection['foundry_import_lod'] = shared_lod
                self.collection['foundry_import_armature'] = self.tag_armature
        try:
            if created_collection:
                self.store_metadata()
            else:
                # Render-only sources share the tag skeleton and LOD folder.
                # Keep its metadata and object source key consistent on reuse.
                self.jms_source_key = self.collection['jms_source_key']
            self.build_contents()
            if (self.armature is not None and self.jms.version >= 8205
                    and (self.tag_armature is not None or self.armature in self.objects)):
                self.armature['legacy_import_matrix'] = json.dumps([list(row) for row in self.armature.matrix_world])
                for index, node in enumerate(self.jms.nodes):
                    name = self.tag_bone_names.get(index, node.name)
                    bone = self.armature.data.bones.get(name)
                    if bone is not None and 'legacy_source_node' not in bone:
                        bone['legacy_source_node'] = json.dumps(asdict(node))
                        bone['legacy_source_node_index'] = index
                        bone['legacy_import_name'] = bone.name
                        bone['legacy_import_matrix'] = json.dumps([list(row) for row in bone.matrix_local])
            if not self.is_model:
                self.select_export_root()
                bpy.context.view_layer.update()
                for ob in self.objects:
                    if ob.type == 'MESH' and 'ass_source_matrix' not in ob:
                        # JMS BSP points are in world space. Their Blender
                        # object carries only the import-axis correction.
                        ob['ass_source_matrix'] = json.dumps([list(row) for row in Matrix.Identity(4)])
                        ob['ass_import_matrix'] = json.dumps([list(row) for row in ob.matrix_world])
                # JMS regions describe model parts, not separate BSPs. ASS
                # instances share this path, including copied mesh instances.
                bsp = self.owner._ensure_region_entry(self.path.stem, utils.SetType.SCENARIO)
                self.collection.nwo.type = 'region'
                self.collection.nwo.region = bsp
                for ob in self.objects:
                    ob.nwo.region_name = bsp
            if shared_lod and created_collection and not self.objects:
                bpy.data.collections.remove(self.collection)
            return self.objects
        except Exception:
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for ob in reversed(self.objects):
                data = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if data and data.users == 0:
                    if isinstance(data, bpy.types.Mesh):
                        bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Armature):
                        bpy.data.armatures.remove(data)
                    elif isinstance(data, bpy.types.Light):
                        bpy.data.lights.remove(data)
            if created_collection:
                bpy.data.collections.remove(self.collection)
            for material in self.created_materials:
                if material.users == 0:
                    bpy.data.materials.remove(material)
            raise
        finally:
            for ob in context.selected_objects:
                ob.select_set(False)
            for ob in selected:
                if ob.name in context.view_layer.objects:
                    ob.select_set(True)
            context.view_layer.objects.active = active

    def store_metadata(self):
        from uuid import uuid4
        self.jms_source_key = str(uuid4())
        self.collection['jms_source_key'] = self.jms_source_key
        self.collection['jms_nodes'] = json.dumps([asdict(node) for node in self.jms.nodes])
        self.collection['jms_version'] = self.jms.version
        self.collection['jms_materials'] = json.dumps([asdict(m) for m in self.jms.materials])
        self.collection['jms_checksum'] = str(self.jms.checksum)

    def select_export_root(self):
        """Keep one authoring root enabled for non-model geometry export."""
        roots = [ob for ob in self.objects
                 if ob.parent is None and ob.type == 'EMPTY' and ob.nwo.is_frame]
        if not roots:
            return
        root = next((ob for ob in roots if ob.name.casefold().startswith('frame')), roots[0])
        for ob in roots:
            # Export exclusion propagates through the hierarchy, so leave the
            # selected root's children enabled and disable only competing roots.
            ob.nwo.export_this = ob is root

    def build_contents(self):
        self.node_matrices()
        self.build_armature()
        self.build_materials()
        self.build_meshes()
        if not self.geometry_only:
            self.build_markers()
            self.build_shapes()
            self.build_constraints()
            self.build_extras()

    def mesh_created(self, ob, source_indices):
        """Adapter hook for formats with instance-local skin and UV bindings."""

    def build_armature(self):
        if not self.jms.nodes:
            return
        if not self.is_model:
            self.build_frames()
            return
        if self.tag_armature is not None:
            bones = self.tag_armature.data.bones
            by_base_name = defaultdict(list)
            for bone in bones:
                # Blender assigns a default name to unnamed tag nodes. Use the
                # original name when available, including an empty string.
                tag_name = bone.get('foundry_tag_node_name', bone.name)
                by_base_name[canonical_bone_name(tag_name)].append(bone.name)
            used, pending = set(), set()
            for index, node in enumerate(self.jms.nodes):
                exact = bones.get(node.name)
                candidates = by_base_name[canonical_bone_name(node.name)]
                bone_name = (exact.name if exact is not None else
                             candidates[0] if len(candidates) == 1 else None)
                if exact is None and not candidates and self.owner.game in {'halo2', 'halo3', 'halo3odst'}:
                    pending.add(index)
                    continue
                if bone_name is None or bone_name in used:
                    raise ValueError(f'{self.path}: JMS node {node.name!r} has no unique render-model bone')
                self.tag_bone_names[index] = bone_name
                used.add(bone_name)
            # Shipped H2/H3/ODST tags shorten names to different lengths. Reserve all
            # exact matches first, then resolve a shortened name only when it
            # is unique in both directions and its parent has been matched.
            # Never use source/tag indices: Tool can reorder siblings.
            while pending:
                options = {}
                for index in pending:
                    node = self.jms.nodes[index]
                    if node.parent >= 0 and node.parent not in self.tag_bone_names:
                        continue
                    expected_parent = self.tag_bone_names.get(node.parent)
                    base = canonical_bone_name(node.name)
                    options[index] = [bone.name for bone in bones if bone.name not in used
                        and (name := canonical_bone_name(bone.get('foundry_tag_node_name', bone.name)))
                        and len(name) < len(base) and base.startswith(name)
                        and (bone.parent.name if bone.parent else None) == expected_parent]
                counts = defaultdict(int)
                for candidates in options.values():
                    for candidate in candidates:
                        counts[candidate] += 1
                resolved = [(index,candidates[0]) for index,candidates in options.items()
                            if len(candidates) == 1 and counts[candidates[0]] == 1]
                if not resolved:
                    node = self.jms.nodes[min(pending)]
                    raise ValueError(f'{self.path}: JMS node {node.name!r} has no unique render-model bone (shortened names must be unambiguous and preserve parents)')
                for index,bone_name in resolved:
                    self.tag_bone_names[index] = bone_name
                    used.add(bone_name)
                    pending.remove(index)
            self.armature = self.tag_armature
            return
        context = bpy.context
        candidate = context.scene.nwo.main_armature or utils.get_rig_prioritize_active(context)
        candidates = ([candidate] if candidate else []) + [o for o in context.scene.objects if o.type == 'ARMATURE' and o != candidate]
        names = {n.name for n in self.jms.nodes}
        for arm in candidates:
            if names.issubset(arm.data.bones.keys()):
                self.armature = arm
                return
        arm = self.object(self.path.stem, bpy.data.armatures.new(self.path.stem))
        self.armature = arm
        for ob in context.selected_objects:
            ob.select_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bones = []
            for index, node in enumerate(self.jms.nodes):
                bone = arm.data.edit_bones.new(node.name)
                bone.tail = (0, max(self.scale * 5, 0.001), 0)
                bone.matrix = self.scene_matrix(self.node_world[index])
                bones.append(bone)
            for index, node in enumerate(self.jms.nodes):
                if node.parent != -1:
                    bones[index].parent = bones[node.parent]
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        arm.show_in_front = True

    def build_frames(self):
        """Represent non-model JMS nodes as Foundry frame empties."""
        self.frames = {}
        for index, node in enumerate(self.jms.nodes):
            frame = self.object(node.name)
            frame.empty_display_type = 'ARROWS'
            frame.empty_display_size = max(self.scale, 0.001)
            frame.nwo.is_frame = True
            if node.parent != -1:
                frame.parent = self.frames[node.parent]
                frame.parent_type = 'OBJECT'
            frame.matrix_world = self.scene_matrix(self.node_world[index])
            self.frames[index] = frame

    def build_materials(self):
        from ..tools.importer import JMSMaterialSlot
        for index, material in enumerate(self.jms.materials):
            self.props[index] = JMSMaterialSlot.from_name(material.name)
            if self.owner.game in {'halo3', 'halo3odst'}:
                self.props[index].emissive_power = self.props[index].emissive_power_scale
            if self.owner.game == 'halo2' and self.props[index].emissive_half_life is not None:
                self.props[index].emissive_half_life *= self.scale
            # Keep property variants in the source table, never in Blender materials.
            shader = re.sub(r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+', '', material.name).strip()
            name = utils.base_material_name(shader, True).lower() or 'default'
            self.materials[index] = self.material(name, self.source_shader_path(name), name)

    def source_shader_path(self, name):
        """Resolve authoring collection prefixes before basename shader search."""
        supplied = self.shader_paths.get(name.casefold(), '')
        if supplied:
            return supplied
        game = getattr(self.owner, 'game', '')
        if game not in {'halo2', 'halo3', 'halo3odst'}:
            return ''
        if not hasattr(self, 'shader_collections'):
            from ..export.shader_collections import ShaderCollections
            self.shader_collections = ShaderCollections(utils.get_tags_path(), game)
        parts = name.split(maxsplit=1)
        if len(parts) != 2:
            return ''
        # A tag's material table can disambiguate a stale authoring collection.
        supplied = self.shader_paths.get(parts[1].casefold(), '')
        if supplied:
            return supplied
        collection = self.shader_collections.prefix_directories.get(parts[0].casefold())
        if collection is None:
            return ''
        directory = Path(utils.get_tags_path(), collection[1])
        for extension in utils.shader_exts:
            path = directory / (parts[1] + extension)
            if path.is_file():
                return str(path.relative_to(utils.get_tags_path()))
        return ''

    def material(self, name, shader_path='', source_name=''):
        if shader_path:
            material = next((mat for mat in bpy.data.materials
                             if mat.nwo.shader_path == shader_path), None)
            if material is None:
                material = bpy.data.materials.new(name)
                material.nwo.shader_path = shader_path
                self.created_materials.append(material)
            if source_name and 'foundry_legacy_shader_name' not in material:
                material['foundry_legacy_shader_name'] = source_name
            if getattr(material.nwo, 'SpecialMaterial', False):
                utils.material_add_visibility(material)
            return material
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name)
            self.created_materials.append(material)
        if source_name and 'foundry_legacy_shader_name' not in material:
            material['foundry_legacy_shader_name'] = source_name
        if getattr(material.nwo, 'SpecialMaterial', False):
            utils.material_add_visibility(material)
        return material

    def mesh_kind(self, props):
        folder = self.path.parent.name.lower()
        if self.is_model and folder in {'collision', 'physics'}:
            return folder
        return props.mesh_type if props else 'default'

    def configure_mesh(self, ob, kind, region='default', permutation='default'):
        mesh_type, _ = self.owner.mesh_and_material(kind, self.is_model)
        ob.data.nwo.mesh_type = mesh_type
        self.owner.set_region(ob, region if self.is_model else self.path.stem)
        self.owner.set_permutation(ob, permutation)
        if mesh_type == '_connected_geometry_mesh_type_structure':
            ob.nwo.proxy_instance = True
        if kind == 'seam':
            ob.nwo.seam_back_manual = True
        if kind in {'soft_ceiling', 'soft_kill', 'slip_surface'}:
            # Apply the display material after reading the source face properties.
            ob.data.nwo['boundary_surface_type'] = ('soft_ceiling', 'soft_kill', 'slip_surface').index(kind)

    def apply_materials(self, ob, faces_by_material):
        collision = self.uses_collision_material(ob)
        physics = ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_physics'
        slots = {}
        for index, faces in faces_by_material.items():
            material = self.materials.get(index)
            if material is None:
                material = self.material('default')
            if material.name not in slots:
                slots[material.name] = len(ob.data.materials)
                ob.data.materials.append(material)
            for face in faces:
                ob.data.polygons[face].material_index = slots[material.name]
            props = self.props.get(index)
            if props:
                indices = None
                if len(faces) != len(ob.data.polygons):
                    indices = np.zeros(len(ob.data.polygons), dtype=np.bool_)
                    indices[faces] = True
                self.owner._apply_jms_material_props(ob.data, ob.nwo, props, indices)
                if self.is_model and self.owner.game in {'halo2', 'halo3', 'halo3odst'} and not props.precise:
                    # An unflagged source material explicitly uses the default
                    # compiler precision. Do not let Auto Precise change it.
                    utils.add_face_prop(ob.data, 'precise_position', indices).precise_position = False
            if (collision or physics) and self.supports_collision_material_properties():
                mask = np.zeros(len(ob.data.polygons), dtype=np.bool_)
                mask[faces] = True
                if not collision and len(faces) == len(ob.data.polygons):
                    ob.nwo.global_material = self.collision_material_name(index, material)
                elif mask.any():
                    utils.add_face_prop(ob.data, 'global_material', mask).global_material = self.collision_material_name(index, material)
        source_props = next((self.props.get(index) for index in faces_by_material), None)
        _, display_material = self.owner.mesh_and_material(self.mesh_kind(source_props), self.is_model)
        if collision:
            display_material = 'Collision'
        elif physics:
            display_material = 'Physics'
        if display_material:
            from ..tools.property_apply import apply_props_material
            existed = bpy.data.materials.get(display_material) is not None
            apply_props_material(ob, display_material)
            ob.data.polygons.foreach_set('material_index', [0] * len(ob.data.polygons))
            if not existed:
                self.created_materials.append(ob.data.materials[0])
        utils.consolidate_face_attributes(ob.data, preserve_special_faces=self.jms.version <= 8200)

    def collision_material_name(self, index, material):
        return material.name

    def supports_collision_material_properties(self):
        return self.is_model or self.owner.corinth

    def uses_collision_material(self, ob):
        return ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_collision'

    def build_meshes(self):
        j = self.jms
        object_rotation = not self.is_model and self.owner.game in {'halo2', 'halo3', 'halo3odst'}
        rotation = Matrix.Identity(3) if object_rotation else self.rotation.to_3x3()
        skipped_triangles = 0
        for (region, permutation, lod), triangles in j.triangle_groups().items():
            if (self.allowed_region_permutations
                    and (region, permutation) not in self.allowed_region_permutations):
                continue
            # Object-only portal policies cannot be represented by face layers.
            groups = defaultdict(list)
            for triangle in triangles:
                # Repeated vertex indices create invalid loops that can crash
                # Blender's custom-normal calculation. Keep them in source data.
                if len(set(triangle.vertices)) != 3:
                    skipped_triangles += 1
                    continue
                props = self.props.get(triangle.material)
                kind = self.mesh_kind(props)
                policy = (tuple(getattr(props, p, False) for p in ('portal_one_way', 'portal_door', 'portal_vis_blocker', 'blocks_sound', 'ai_deafening', 'portal_exact'))
                          if kind == 'portal' else ())
                groups[(kind, policy)].append(triangle)
            for (kind, _), faces in groups.items():
                remap = {}
                faces_by_material = defaultdict(list)
                local_faces = []
                for triangle in faces:
                    local_faces.append(tuple(remap.setdefault(i, len(remap)) for i in triangle.vertices))
                    faces_by_material[triangle.material].append(len(local_faces) - 1)
                vertices = [j.vertices[i] for i in remap]
                if self.geometry_only and self.tag_armature is not None:
                    name = f'{region}:{permutation}' + (f':{lod.upper()}' if lod else '')
                else:
                    name = f'{self.path.stem}:{permutation}:{region}' + (f':{lod}' if lod else '')
                mesh = bpy.data.meshes.new(name)
                ob = self.object(name, mesh)
                if object_rotation:
                    ob.matrix_world = self.rotation
                mesh.from_pydata([rotation @ (Vector(v.position) * self.scale) for v in vertices], [], local_faces)
                mesh.update()
                mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
                mesh.normals_split_custom_set_from_vertices([(rotation @ Vector(v.normal)).normalized() for v in vertices])
                mesh['foundry_legacy_normals'] = True
                loop_vertices = [loop.vertex_index for loop in mesh.loops]
                for uv_index in range(max((len(v.uvs) for v in vertices), default=0)):
                    uv = mesh.uv_layers.new(name='UVMap' if uv_index == 0 else f'UVMap.{uv_index:03}')
                    uv.data.foreach_set('uv', [c for i in loop_vertices for c in (vertices[i].uvs[uv_index] if uv_index < len(vertices[i].uvs) else (0, 0))])
                if any(v.color is not None for v in vertices):
                    colors = mesh.color_attributes.new(name='Color', type='FLOAT_COLOR', domain='CORNER')
                    colors.data.foreach_set('color', [c for i in loop_vertices for c in (*(vertices[i].color or (1, 1, 1)), 1)])
                self.configure_mesh(ob, kind, region, permutation)
                lod_label = lod.upper()
                if lod_label in {'L1', 'L2', 'L3', 'L4', 'L5', 'L6'}:
                    ob.nwo.mesh_lod = lod_label
                self.apply_materials(ob, faces_by_material)
                self.mesh_created(ob, list(remap))
                if self.armature:
                    # Mesh coordinates are world-space; preserve them on transformed rigs.
                    ob.parent = self.armature
                    ob.matrix_world = Matrix.Identity(4)
                    weights = defaultdict(list)
                    for i, vertex in enumerate(vertices):
                        combined = defaultdict(float)
                        for node, weight in vertex.influences:
                            if node != -1 and weight > 0:
                                combined[node] += weight
                        total = sum(combined.values())
                        for node, weight in combined.items():
                            weights[(node, weight / total)].append(i)
                    vertex_groups = {}
                    for (node, weight), indices in weights.items():
                        if node not in vertex_groups:
                            vertex_groups[node] = ob.vertex_groups.new(
                                name=self.tag_bone_names.get(node, j.nodes[node].name))
                        vertex_groups[node].add(indices, weight, 'REPLACE')
                    if weights:
                        modifier = ob.modifiers.new('Armature', 'ARMATURE')
                        modifier.object = self.armature
                ob['legacy_import_matrix'] = json.dumps([list(row) for row in ob.matrix_world])

        # if skipped_triangles:
        #     utils.print_warning(f'{self.path.name}: skipped {skipped_triangles} triangles with repeated vertex indices')

    def place(self, ob, transform, parent=-1, local=True, marker=False):
        matrix = self.transform(transform)
        if local and parent != -1:
            matrix = self.node_world[parent] @ matrix
        if marker and self.owner.game in {'halo3', 'halo3odst'}:
            matrix = marker_axis.local_axes(matrix, self.owner.from_x_rot)
        if self.armature:
            ob.parent = self.armature
            if parent != -1:
                ob.parent_type = 'BONE'
                ob.parent_bone = self.tag_bone_names.get(parent, self.jms.nodes[parent].name)
        elif parent in getattr(self, 'frames', {}):
            ob.parent = self.frames[parent]
            ob.parent_type = 'OBJECT'
        ob.matrix_world = self.scene_matrix(matrix)

    def build_markers(self):
        for marker in self.jms.markers:
            name = marker.name.lstrip('#')
            match = re.match(r'^\((\S+)\s+(\S+)\)(.*)$', name)
            # The optional (permutation region) prefix is commonly followed
            # by a separator space; it is not part of the marker group name.
            ob = self.object((match[3] if match else name).strip())
            ob.empty_display_type = 'ARROWS'
            radius = marker.radius if marker.radius >= 0 else 1.0
            ob.empty_display_size = max(radius * self.scale, 0.001)
            if marker.radius < 0:
                ob['jms_marker_radius'] = marker.radius
            transform = marker.transform
            if self.jms.version <= 8200:
                # CE marker rotations are not inverted like CE node rotations.
                from .jms_format import Transform
                x, y, z, w = transform.rotation
                transform = Transform((-x, -y, -z, w), transform.translation)
            self.place(ob, transform, marker.parent, marker=True)
            if self.is_model and marker.region != -1:
                self.owner.set_region(ob, self.jms.regions[marker.region])
                ob.nwo.marker_uses_regions = True
            if self.is_model and match:
                self.owner.set_region(ob, match[2])
                self.owner.set_permutation(ob, match[1])
                ob.nwo.marker_uses_regions = True
                ob.nwo.marker_permutation_type = 'include'
                ob.nwo.marker_permutations.add().name = match[1]
            for prefix, kind in (('fx', 'effects'), ('target', 'target'), ('garbage', 'garbage'), ('hint', 'hint')):
                if ob.name.startswith(prefix):
                    ob.nwo.marker_type = '_connected_geometry_marker_type_' + kind
                    break

    def build_shapes(self):
        for shape in self.jms.shapes:
            mesh = bpy.data.meshes.new(shape.name)
            ob = self.object(shape.name, mesh)
            bm = bmesh.new()
            try:
                if shape.kind in {'sphere', 'pill'}:
                    radius = shape.dimensions[-1]
                    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius)
                    if shape.kind == 'pill':
                        height = shape.dimensions[0]
                        for v in bm.verts:
                            if v.co.z > 0:
                                v.co.z += height
                elif shape.kind == 'box':
                    bmesh.ops.create_cube(bm, size=1)
                    for v in bm.verts:
                        v.co = Vector(tuple(v.co[i] * shape.dimensions[i] for i in range(3)))
                else:
                    verts = [bm.verts.new(v) for v in shape.vertices]
                    if len(verts) >= 4:
                        bmesh.ops.convex_hull(bm, input=verts, use_existing_faces=False)
                for v in bm.verts:
                    v.co *= self.scale
                bm.to_mesh(mesh)
            finally:
                bm.free()
            material = self.jms.materials[shape.material] if shape.material != -1 else None
            self.configure_mesh(ob, 'physics', material.region if material else 'default', material.permutation if material else 'default')
            ob.nwo.mesh_primitive_type = '_connected_geometry_primitive_type_' + ('none' if shape.kind == 'convex' else shape.kind)
            self.apply_materials(ob, {shape.material: list(range(len(mesh.polygons)))})
            self.place(ob, shape.transform, shape.parent)

    def build_constraints(self):
        for constraint in self.jms.constraints:
            ob = self.object(constraint.name.lstrip('$'))
            ob.empty_display_type = 'ARROWS'
            ob.empty_display_size = self.scale * 5
            self.place(ob, constraint.parent_transform, constraint.parent)
            # Preserve both frames and unsupported constraint types for later export.
            ob['jms_constraint'] = json.dumps(asdict(constraint))
            parent_world = self.transform(constraint.parent_transform)
            child_world = self.transform(constraint.child_transform)
            if constraint.parent != -1:
                parent_world = self.node_world[constraint.parent] @ parent_world
            if constraint.child != -1:
                child_world = self.node_world[constraint.child] @ child_world
            relative = parent_world.inverted() @ child_world
            relative.translation *= self.scale
            ob['jms_constraint_child_relative'] = json.dumps([list(row) for row in relative])
            if constraint.kind not in {'hinge', 'ragdoll'}:
                ob.nwo.export_this = False
                utils.print_warning(f'JMS {constraint.kind} constraint {constraint.name}: preserved as metadata; Foundry supports hinge and socket constraints')
                continue
            ob.nwo.marker_type = '_connected_geometry_marker_type_physics_constraint'
            ob.nwo.physics_constraint_type = '_connected_geometry_marker_type_physics_' + ('hinge_constraint' if constraint.kind == 'hinge' else 'socket_constraint')
            for side, index in (('parent', constraint.parent), ('child', constraint.child)):
                if index != -1:
                    setattr(ob.nwo, 'physics_constraint_' + side, self.armature)
                    setattr(ob.nwo, 'physics_constraint_' + side + '_bone',
                            self.tag_bone_names.get(index, self.jms.nodes[index].name))
            limits = constraint.limits
            if constraint.kind == 'hinge':
                ob.nwo.physics_constraint_uses_limits = bool(limits[0])
                ob.nwo.hinge_constraint_minimum = radians(limits[2])
                ob.nwo.hinge_constraint_maximum = radians(limits[3])
            else:
                ob.nwo.physics_constraint_uses_limits = True
                for prop, value in zip(('twist_constraint_start', 'twist_constraint_end', 'cone_angle', 'plane_constraint_minimum', 'plane_constraint_maximum'), (limits[0], limits[1], limits[3], limits[4], limits[5])):
                    setattr(ob.nwo, prop, radians(value))

    def build_extras(self):
        from ..tools.importer import XREF
        for name, uid, index, transform in self.jms.instances:
            path, xref_name = self.jms.xrefs[index]
            ob = self.object(name)
            self.place(ob, transform)
            # Collection geometry has already been converted to scene axes.
            ob.matrix_world = marker_axis.local_axes(ob.matrix_world, self.owner.from_x_rot)
            ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
            tag, fallback = self.owner._resolve_xref_tag_path(XREF(name, path, xref_name))
            ob.nwo.marker_game_instance_tag_name = tag or fallback or ''
            ob['jms_xref_path'], ob['jms_xref_name'], ob['jms_identifier'] = path, xref_name, str(uid)
        for position, radius in self.jms.bounding_spheres:
            ob = self.object('bounding_sphere')
            ob.location = self.rotation.to_3x3() @ (Vector(position) * self.scale)
            ob.empty_display_type = 'SPHERE'
            ob.empty_display_size = radius * self.scale
            ob.nwo.export_this = False
            ob['jms_bounding_sphere'] = True
        for direction, intensity, angle in self.jms.skylights:
            light = bpy.data.lights.new('skylight', 'SUN')
            ob = self.object('skylight', light)
            vector = self.rotation.to_3x3() @ Vector(direction)
            if vector.length:
                ob.rotation_euler = vector.to_track_quat('-Z', 'Y').to_euler()
            peak = max(intensity)
            light.energy = peak
            light.color = tuple(c / peak for c in intensity) if peak > 0 else (0, 0, 0)
            # JMS stores solid angle (steradians); Blender expects angular diameter.
            light.angle = 2 * acos(max(-1, min(1, 1 - angle / (2 * pi))))
            ob['jms_skylight'] = json.dumps((direction, intensity, angle))


def import_jms(owner, path, legacy_type, *, tag_armature=None,
               parent_collection=None, geometry_only=False, allowed_region_permutations=(), shader_paths=None):
    return JMSImporter(owner, path, legacy_type, tag_armature=tag_armature,
                       parent_collection=parent_collection,
                       geometry_only=geometry_only,
                       allowed_region_permutations=allowed_region_permutations, shader_paths=shader_paths).build()
