"""Build Foundry objects from JMS interchange data without the Halo toolset."""
from collections import defaultdict
from math import radians, acos, pi
from pathlib import Path
import numpy as np
import re

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

from .jms_format import JMS
from .coordinates import axis_rotation
from .import_info import BSP_TAG_KINDS, MODEL_TAG_KINDS, FRAME_PREFIXES, main_frame_scope
from .. import utils, marker_axis

class TagBoneMappingError(ValueError):
    """Source geometry cannot be bound unambiguously to the compiled skeleton."""


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
                 parent_collection=None, geometry_only=False, allowed_region_permutations=(), shader_paths=None,
                 import_info_kind='', render_only=False):
        self.owner = owner
        self.path = Path(path)
        self.jms = JMS.from_file(path)
        # if self.jms.invalid_uv_components:
        #     utils.print_warning(f'{self.path.name}: replaced {self.jms.invalid_uv_components} '
        #         f'non-finite UV components with zero (first at line {self.jms.first_invalid_uv_line})')
        self.import_info_kind = import_info_kind
        self.render_only = render_only
        self.source_node_scope = None
        self.used_material_indices = None
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
        if self.import_info_kind in BSP_TAG_KINDS:
            return False
        if self.import_info_kind in MODEL_TAG_KINDS:
            return True
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
                                    if child.name == collection_name
                                    and any(ob.type == 'MESH' and ob.parent == self.tag_armature
                                            and ob.nwo.mesh_lod == shared_lod for ob in child.objects)), None)
        created_collection = self.collection is None
        if created_collection:
            self.collection = bpy.data.collections.new(collection_name)
            parent_collection.children.link(self.collection)
        try:
            if created_collection:
                self.store_metadata()
            self.build_contents()
            if self.import_info_kind:
                self.remove_import_info_frames()
                for mesh in {ob.data for ob in self.objects if ob.type == 'MESH'}:
                    utils.consolidate_materials(mesh)
            if not self.is_model:
                if not self.import_info_kind:
                    self.select_export_root()
                bpy.context.view_layer.update()
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
        """Import records remain transient; authoring data belongs in Blender."""
        pass

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
        self.prepare_import_info()
        self.build_armature()
        self.build_materials()
        self.build_meshes()
        if not self.geometry_only:
            if self.import_info_kind not in {'physics_model', 'collision_model'}:
                if not self.render_only or self.is_model:
                    self.build_markers()
                self.build_extras()
            if not self.render_only and (not self.import_info_kind or self.import_info_kind == 'physics_model'):
                self.build_shapes()
                self.build_constraints()

    def prepare_import_info(self):
        if not self.import_info_kind:
            return
        if not self.is_model:
            self.source_node_scope = main_frame_scope(
                [n.name for n in self.jms.nodes], [n.parent for n in self.jms.nodes],
                list(self.node_world))
        triangles = self.source_triangles()
        self.used_material_indices = {t.material for t in triangles}
        if self.import_info_kind == 'physics_model':
            self.used_material_indices.update(s.material for s in self.jms.shapes)

    def source_triangles(self):
        if self.import_info_kind == 'physics_model' and self.jms.version >= 8206:
            return []
        scope = self.source_node_scope
        if scope is None:
            return self.jms.triangles
        return [t for t in self.jms.triangles if all(
            node == -1 or node in scope or weight <= 0
            for i in t.vertices for node, weight in self.jms.vertices[i].influences)]

    def remove_import_info_frames(self):
        """Flatten authoring frames after source culling, preserving world geometry."""
        bpy.context.view_layer.update()
        frames = {ob for ob in self.objects if ob.type == 'EMPTY' and ob.nwo.is_frame}
        matrices = {ob: ob.matrix_world.copy() for ob in self.objects if ob not in frames}
        changed = []
        for ob, matrix in matrices.items():
            if ob.parent not in frames:
                continue
            parent, parent_type, bone = ob.parent, ob.parent_type, ob.parent_bone
            while parent in frames:
                parent_type, bone, parent = parent.parent_type, parent.parent_bone, parent.parent
            ob.parent, ob.parent_type, ob.parent_bone = parent, parent_type, bone
            ob.matrix_world = matrix
            changed.append(ob)
        self.objects = [ob for ob in self.objects if ob not in frames]
        self.frames = {}
        if hasattr(self, 'anchors'):
            self.anchors = {}
        bpy.data.batch_remove(frames)
        bpy.context.view_layer.update()
        for ob in changed:
            # A rotated, non-uniformly scaled frame can leave shear that an
            # unparented object's TRS channels cannot represent. Bake that
            # residual into a private mesh, retaining the exact final surface.
            if ob.type == 'MESH':
                expected = matrices[ob].to_3x3()
                actual = ob.matrix_world.to_3x3()
                # Translation always fits in the object's channels. Testing an
                # inverse world matrix here amplifies cancellation at distant
                # positions and needlessly makes every ASS instance unique.
                # Only a real change to a basis column requires a geometry bake.
                # Float32 matrix-to-Euler conversion near a vertical axis can
                # introduce a few parts per million without any actual shear.
                if any((actual.col[c] - expected.col[c]).length >
                       1e-5 * max(actual.col[c].length, expected.col[c].length)
                       for c in range(3)):
                    residual = ob.matrix_world.inverted_safe() @ matrices[ob]
                    if ob.data.users > 1:
                        ob.data = ob.data.copy()
                    normals = [(residual.to_3x3().inverted_safe().transposed() @ n.vector).normalized()
                               for n in ob.data.corner_normals] if ob.data.has_custom_normals else None
                    ob.data.transform(residual)
                    if normals:
                        ob.data.normals_split_custom_set(normals)
                    ob.data.update()

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
                # Bone matching uses the current editable Blender names.
                tag_name = bone.name
                by_base_name[canonical_bone_name(tag_name)].append(bone.name)
            used, pending = set(), set()
            for index, node in enumerate(self.jms.nodes):
                exact = bones.get(node.name)
                if exact is None:
                    unprefixed = utils.remove_node_prefix(node.name)
                    literal = bones.get(unprefixed)
                    # A tag may literally name its bone 'frame' (source
                    # 'b_frame'). Prefer that before the bare-frame/unnamed
                    # compatibility alias, but exclude Blender-generated names.
                    if (literal is not None
                            and literal.name == unprefixed):
                        exact = literal
                candidates = by_base_name[canonical_bone_name(node.name)]
                bone_name = (exact.name if exact is not None else
                             candidates[0] if len(candidates) == 1 else None)
                if exact is None and not candidates and self.owner.game in {'halo2', 'halo3', 'halo3odst'}:
                    pending.add(index)
                    continue
                if bone_name is None or bone_name in used:
                    raise TagBoneMappingError(f'{self.path}: JMS node {node.name!r} has no unique render-model bone')
                self.tag_bone_names[index] = bone_name
                used.add(bone_name)
            # Shipped H2/H3/ODST tags shorten names to different lengths and
            # append _dupN when the shortened names collide. Reserve exact
            # matches first, then use parents and rest transforms to resolve
            # collisions. Never use indices: Tool can reorder siblings.
            shortened_names, duplicate_names = {}, set()
            for bone in bones:
                tag_name = bone.name
                name = canonical_bone_name(tag_name)
                # Strip the compiler suffix before collapsing separators. A
                # truncated name can end in '_', producing 'name__dup1'.
                stem = canonical_bone_name(re.sub(r'_dup[1-9]\d*$', '', tag_name, flags=re.I))
                shortened_names[bone.name] = stem if by_base_name.get(stem) else name
                if shortened_names[bone.name] != name:
                    duplicate_names.add(bone.name)

            def same_rest_transform(index, bone_name):
                source_matrix = getattr(self, 'node_world', {}).get(index)
                if source_matrix is None:
                    return False
                source_matrix = self.scene_matrix(source_matrix)
                tag_matrix = bones[bone_name].matrix_local
                # Compare in armature space, independent of its current pose
                # and object placement. Express position tolerance in JMS units.
                return ((source_matrix.translation - tag_matrix.translation).length
                        <= abs(self.scale) * .001
                        and all(abs(source_matrix[r][c] - tag_matrix[r][c]) <= .0001
                                for r in range(3) for c in range(3)))

            while pending:
                options = {}
                for index in pending:
                    node = self.jms.nodes[index]
                    if node.parent >= 0 and node.parent not in self.tag_bone_names:
                        continue
                    expected_parent = self.tag_bone_names.get(node.parent)
                    base = canonical_bone_name(node.name)
                    options[index] = [bone.name for bone in bones if bone.name not in used
                        and (name := shortened_names[bone.name])
                        and len(name) < len(base) and base.startswith(name)
                        and (bone.parent.name if bone.parent else None) == expected_parent
                        and (bone.name not in duplicate_names or same_rest_transform(index, bone.name))]
                counts = defaultdict(int)
                for candidates in options.values():
                    for candidate in candidates:
                        counts[candidate] += 1
                for index, candidates in options.items():
                    if len(candidates) > 1 or any(counts[name] > 1 for name in candidates):
                        options[index] = [name for name in candidates if same_rest_transform(index, name)]
                counts.clear()
                for candidates in options.values():
                    for candidate in candidates:
                        counts[candidate] += 1
                resolved = [(index,candidates[0]) for index,candidates in options.items()
                            if len(candidates) == 1 and counts[candidates[0]] == 1]
                if not resolved:
                    node = self.jms.nodes[min(pending)]
                    raise TagBoneMappingError(f'{self.path}: JMS node {node.name!r} has no unique render-model bone (shortened names must be unambiguous and preserve parents)')
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
            if self.source_node_scope is not None and index not in self.source_node_scope:
                continue
            frame = self.object(node.name)
            frame.empty_display_type = 'ARROWS'
            frame.empty_display_size = max(self.scale, 0.001)
            frame.nwo.is_frame = True
            self.frames[index] = frame
        for index, frame in self.frames.items():
            frame.parent = self.frames.get(self.jms.nodes[index].parent)
            frame.matrix_world = self.scene_matrix(self.node_world[index])

    def build_materials(self):
        from ..tools.importer import JMSMaterialSlot
        for index, material in enumerate(self.jms.materials):
            if self.used_material_indices is not None and index not in self.used_material_indices:
                continue
            self.props[index] = JMSMaterialSlot.from_name(material.name)
            if self.owner.game in {'halo3', 'halo3odst'}:
                self.props[index].emissive_power = self.props[index].emissive_power_scale
            if self.owner.game == 'halo2' and self.props[index].emissive_half_life is not None:
                self.props[index].emissive_half_life *= self.scale
            # Keep property variants in the source table, never in Blender materials.
            shader = re.sub(r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+', '', material.name,
                            flags=re.IGNORECASE).strip()
            name = utils.base_material_name(shader, True).lower() or 'default'
            path = self.source_shader_path(name)
            if Path(path).suffix.lower() in {'.shader_water', '.shader_transparent_water'}:
                self.props[index].water_surface = True
                self.props[index].mesh_type = 'water_surface'
            self.materials[index] = self.material(name, path, name)

    def source_shader_path(self, name):
        """Resolve authoring collection prefixes before basename shader search."""
        def compiled_path(shader_name):
            supplied = self.shader_paths.get(shader_name.casefold(), '')
            if supplied and getattr(self.owner, 'game', '') in {'halo3', 'halo3odst'}:
                path = Path(utils.get_tags_path(), supplied)
                if not path.is_file():
                    # Some shipped BSP palettes retain a stale shader class.
                    # Tool resolves the existing shader by name; use the unique
                    # sibling class instead of exporting the invalid fallback.
                    alternatives = [path.with_suffix(ext) for ext in utils.shader_exts
                                    if path.with_suffix(ext).is_file()]
                    if len(alternatives) == 1:
                        return str(alternatives[0].relative_to(utils.get_tags_path()))
            return supplied

        supplied = compiled_path(name)
        if supplied:
            return supplied
        game = getattr(self.owner, 'game', '')
        if game not in {'halo2', 'halo3', 'halo3odst'}:
            return ''
        if not hasattr(self, 'shader_collections'):
            from ..export.shader_collections import ShaderCollections
            self.shader_collections = ShaderCollections(utils.get_tags_path(), game)
        parts = name.split(maxsplit=1)
        if not parts:
            return ''
        collection = (self.shader_collections.prefix_directories.get(parts[0].casefold())
                      if len(parts) == 2 else None)
        names = [parts[-1]]
        # H2 authoring sources use numeric material-instance suffixes, such as
        # window_high_rise2. Prefer an exact tag before trying the base shader.
        if game == 'halo2' and (base := names[0].rstrip('0123456789')) and base != names[0]:
            names.append(base)
        for shader_name in names:
            # A tag's material table can disambiguate a stale authoring collection.
            supplied = compiled_path(shader_name)
            if supplied:
                return supplied
            if collection is not None:
                directory = Path(utils.get_tags_path(), collection[1])
                for extension in utils.shader_exts:
                    path = directory / (shader_name + extension)
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
            if getattr(material.nwo, 'SpecialMaterial', False):
                utils.material_add_visibility(material)
            return material
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name)
            self.created_materials.append(material)
        if getattr(material.nwo, 'SpecialMaterial', False):
            utils.material_add_visibility(material)
        return material

    def mesh_kind(self, props):
        if self.import_info_kind in {'collision_model', 'physics_model'}:
            return 'collision' if self.import_info_kind == 'collision_model' else 'physics'
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
        if kind == 'water_surface':
            ob.nwo.water_type = 'SURFACE'
        elif kind == 'water_physics':
            ob.nwo.water_type = 'PHYSICS'
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
            if (collision or physics) and self.supports_collision_material_properties():
                mask = np.zeros(len(ob.data.polygons), dtype=np.bool_)
                mask[faces] = True
                if not collision and len(faces) == len(ob.data.polygons):
                    ob.nwo.global_material = self.collision_material_name(index, material)
                elif mask.any():
                    utils.add_face_prop(ob.data, 'global_material', mask).global_material = self.collision_material_name(index, material)
        source_props = next((self.props.get(index) for index in faces_by_material), None)
        if (not self.is_model and ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_portal'
                and self.owner.game in {'halo2', 'halo3', 'halo3odst'}):
            # build_meshes splits portal material groups into consecutive runs.
            # Store the source group before replacing its display material.
            source_index = next(iter(faces_by_material))
            ob.nwo.portal_group_index = self.portal_indices[source_index]
        _, display_material = self.owner.mesh_and_material(self.mesh_kind(source_props), self.is_model)
        if not self.is_model and self.owner.game in {'halo3', 'halo3odst'}:
            if any(material is not None and material.name.casefold().startswith('+seam:')
                   for material in ob.data.materials):
                display_material = None  # Preserve each BSP name and its face assignment.
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
        indexed_portals = not self.is_model and self.owner.game in {'halo2', 'halo3', 'halo3odst'}
        if indexed_portals and not hasattr(self, 'portal_indices'):
            from .portal_groups import portal_material_indices, portal_material_name
            names = {index: j.materials[index].name for index, props in self.props.items()
                     if props.mesh_type == 'portal'}
            indices = portal_material_indices(names.values())
            self.portal_indices = {index: indices[portal_material_name(name) or name.casefold()]
                                   for index, name in names.items()}
        if self.import_info_kind == 'physics_model' and j.version >= 8206:
            return
        if self.is_model and self.mesh_kind(None) == 'physics' and j.shapes:
            # Modern physics sources can retain the render mesh as well as
            # explicit rigid shapes. Tool uses the shapes for the physics tag.
            return
        default_node = -1
        if j.version >= 8205:
            roots = [i for i, node in enumerate(j.nodes) if node.parent == -1]
            if len(roots) == 1:
                # Tool binds positive-weight -1 influences to the model root.
                # Keep their share of a blended weight as well as rigid weights.
                default_node = roots[0]
        object_rotation = not self.is_model and self.owner.game in {'halo2', 'halo3', 'halo3odst'}
        rotation = Matrix.Identity(3) if object_rotation else self.rotation.to_3x3()
        skipped_triangles = 0
        for (region, permutation, lod), triangles in j.triangle_groups().items():
            if self.source_node_scope is not None:
                triangles = [t for t in triangles if all(
                    node == -1 or node in self.source_node_scope or weight <= 0
                    for i in t.vertices for node, weight in j.vertices[i].influences)]
            if (self.allowed_region_permutations
                    and (region, permutation) not in self.allowed_region_permutations):
                continue
            # Object-only portal policies cannot be represented by face layers.
            groups = defaultdict(list)
            preserve_order = not self.is_model and self.owner.game in {'halo2', 'halo3', 'halo3odst'}
            previous_group, run = None, 0
            for triangle in triangles:
                # ASS BSP construction can depend on zero-area faces. Give
                # repeated corners separate editable vertices below so their
                # loops remain valid for Blender's custom-normal calculation.
                if not preserve_order and len(set(triangle.vertices)) != 3:
                    skipped_triangles += 1
                    continue
                props = self.props.get(triangle.material)
                kind = self.mesh_kind(props)
                if self.render_only and (kind in {
                        'collision', 'physics', 'cookie_cutter', 'portal', 'seam', 'fog',
                        'water_physics', 'weather_polyhedron', 'lightmap_region',
                        'soft_ceiling', 'soft_kill', 'slip_surface', 'rain_blocker', 'rain_sheet'}
                        or (props and (props.collision_only or props.sphere_collision_only))):
                    continue
                policy = (tuple(getattr(props, p, False) for p in ('portal_one_way', 'portal_door', 'portal_vis_blocker', 'blocks_sound', 'ai_deafening', 'portal_exact'))
                          if kind == 'portal' else ())
                if indexed_portals and kind == 'portal':
                    policy += (self.portal_indices[triangle.material],)
                group = (kind, policy)
                if preserve_order:
                    # Tool's BSP construction is sensitive to triangle order.
                    # Split mixed surfaces into consecutive runs instead of
                    # moving every portal face to the end of the source mesh.
                    if group != previous_group:
                        run += 1
                        previous_group = group
                    group = (kind, (policy, run))
                groups[group].append(triangle)
            for (kind, _), faces in groups.items():
                remap = {}
                faces_by_material = defaultdict(list)
                local_faces = []
                source_indices = []
                for triangle in faces:
                    local_face = []
                    for i in triangle.vertices:
                        if i not in remap:
                            remap[i] = len(source_indices)
                            source_indices.append(i)
                        local_index = remap[i]
                        if local_index in local_face:
                            local_index = len(source_indices)
                            source_indices.append(i)
                        local_face.append(local_index)
                    local_faces.append(tuple(local_face))
                    faces_by_material[triangle.material].append(len(local_faces) - 1)
                vertices = [j.vertices[i] for i in source_indices]
                if self.geometry_only and self.tag_armature is not None:
                    name = f'{region}:{permutation}' + (f':{lod.upper()}' if lod else '')
                else:
                    name = f'{self.path.stem}:{permutation}:{region}' + (f':{lod}' if lod else '')
                mesh = bpy.data.meshes.new(name)
                ob = self.object(name, mesh)
                if object_rotation:
                    ob.matrix_world = self.rotation
                mesh.from_pydata([rotation @ Vector(tuple(c * self.scale for c in v.position))
                                  for v in vertices], [], local_faces)
                mesh.update()
                # Zero-area faces cannot define a Blender normal space. Smooth
                # fans through them corrupt custom normals on adjacent visible
                # faces. Keep the faces, but isolate their shading fans.
                mesh.polygons.foreach_set('use_smooth', [face.area > 0 for face in mesh.polygons])
                mesh.normals_split_custom_set_from_vertices([(rotation @ Vector(v.normal)).normalized() for v in vertices])
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
                self.mesh_created(ob, source_indices)
                if self.armature:
                    # Mesh coordinates are world-space; preserve them on transformed rigs.
                    ob.parent = self.armature
                    ob.matrix_world = Matrix.Identity(4)
                    weights = defaultdict(list)
                    for i, vertex in enumerate(vertices):
                        combined = defaultdict(float)
                        for node, weight in vertex.influences:
                            if node == -1:
                                node = default_node
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

        # if skipped_triangles:
        #     utils.print_warning(f'{self.path.name}: skipped {skipped_triangles} triangles with repeated vertex indices')

    def place(self, ob, transform, parent=-1, local=True, marker=False):
        matrix = self.transform(transform)
        if self.armature and parent != -1 and local:
            bone_name = self.tag_bone_names.get(parent, self.jms.nodes[parent].name)
            ob.parent, ob.parent_type, ob.parent_bone = self.armature, 'BONE', bone_name
            # Shape/marker frames are bone-local. A reused tag rig can have a
            # different rest basis from the JMS node header, and may be posed.
            matrix.translation *= self.scale
            if marker and self.owner.game in {'halo3', 'halo3odst'}:
                matrix = marker_axis.local_axes(matrix, self.owner.from_x_rot)
            bpy.context.view_layer.update()
            ob.matrix_world = self.armature.matrix_world @ self.armature.pose.bones[bone_name].matrix @ matrix
            return
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
            if (self.source_node_scope is not None and marker.parent != -1
                    and marker.parent not in self.source_node_scope):
                continue
            name = marker.name.lstrip('#')
            match = re.match(r'^\((\S+)\s+(\S+)\)(.*)$', name)
            # The optional (permutation region) prefix is commonly followed
            # by a separator space; it is not part of the marker group name.
            ob = self.object((match[3] if match else name).strip())
            ob.empty_display_type = 'ARROWS'
            radius = marker.radius if marker.radius >= 0 else 1.0
            ob.empty_display_size = max(radius * self.scale, 0.001)
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
                            # JMS places the capsule at its bottom tip; Havok
                            # endpoints are the sphere centres, one radius up.
                            v.co.z += radius
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
            if constraint.kind not in {'hinge', 'ragdoll'}:
                ob.nwo.export_this = False
                utils.print_warning(f'JMS {constraint.kind} constraint {constraint.name}: not exported; Foundry supports hinge and socket constraints')
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
        for position, radius in self.jms.bounding_spheres:
            if self.import_info_kind:
                continue
            ob = self.object('bounding_sphere')
            ob.location = self.rotation.to_3x3() @ (Vector(position) * self.scale)
            ob.empty_display_type = 'SPHERE'
            ob.empty_display_size = radius * self.scale
            ob.nwo.export_this = False
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


def import_jms(owner, path, legacy_type, *, tag_armature=None,
               parent_collection=None, geometry_only=False, allowed_region_permutations=(), shader_paths=None,
               import_info_kind='', render_only=False):
    return JMSImporter(owner, path, legacy_type, tag_armature=tag_armature,
                       parent_collection=parent_collection,
                       geometry_only=geometry_only,
                       allowed_region_permutations=allowed_region_permutations, shader_paths=shader_paths,
                       import_info_kind=import_info_kind, render_only=render_only).build()
