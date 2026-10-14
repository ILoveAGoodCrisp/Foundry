"""Native ASS scene adapter, sharing Foundry geometry/material construction with JMS."""
from collections import defaultdict
from dataclasses import replace
from math import log2, radians
from pathlib import Path, PureWindowsPath
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

from .ass_format import ASS, ASSError
from .coordinates import axis_rotation
from .references import ASS_GAMES, ass_reference_type, ass_reference_name, embedded_game_object_tag
from .jms_format import JMS, Material, Node, Transform, Shape
from .jms_importer import JMSImporter, TagBoneMappingError, is_frame_name, canonical_bone_name
from .import_info import BSP_TAG_KINDS, MODEL_TAG_KINDS, main_frame_scope
from .. import utils, marker_axis
from ..constants import face_prop_game_supported
from ..uv_channels import store_uv_w


class ASSImporter(JMSImporter):
    def __init__(self, owner, path, legacy_type, *, parent_collection=None,
                 tag_armature=None, geometry_only=False, allowed_region_permutations=(), shader_paths=None,
                 import_info_kind='', render_only=False, game_object_paths=()):
        self.owner, self.path = owner, Path(path)
        self.ass = ASS.from_file(path)
        self.import_info_kind = import_info_kind
        self.render_only = render_only
        self.source_node_scope = None
        self.used_material_indices = None
        self.scale = owner.scale_factor
        self.rotation = axis_rotation(owner.from_x_rot)
        self.objects, self.materials, self.created_materials, self.props = [], {}, [], {}
        self.armature, self.node_world = None, {}
        self.tag_armature, self.parent_collection = tag_armature, parent_collection
        self.tag_bone_names, self.geometry_only = {}, geometry_only
        self.allowed_region_permutations = set(allowed_region_permutations)
        self.shader_paths = shader_paths or {}
        self.game_object_paths = frozenset(PureWindowsPath(path) for path in game_object_paths)
        self.source_indices, self.templates, self.anchors = {}, {}, {}
        self.frame_instances = set()
        self.instance_objects = {}
        self.bone_aliases = {}
        weighted = {b for i in self.ass.instances for b in i.bones if b != -1}
        self.is_model = legacy_type == 'model' or (legacy_type == 'auto' and (
            bool(weighted) or self.path.parent.name.lower() in {'render', 'collision', 'physics'}))
        if import_info_kind in BSP_TAG_KINDS:
            self.is_model = False
        elif import_info_kind in MODEL_TAG_KINDS:
            self.is_model = True
        # Power-of-two local units retain every source float exactly. The
        # ordinary frame transform supplies the remaining scene-unit scale.
        self.hierarchy_units = not self.is_model
        self.geometry_scale = 2.0 ** round(log2(self.scale)) if self.hierarchy_units else self.scale
        self.bone_instances = weighted if self.is_model else set()
        if self.is_model:
            self.bone_instances |= {index for index, i in enumerate(self.ass.instances)
                                    if i.name.lower().startswith(('b ', 'b_', 'bone', 'frame', 'bip01')) and i.unique_id != -1}
        if tag_armature is not None:
            # Tool can omit authoring-only roots from the compiled skeleton.
            # Keep their source transforms, but do not recreate them as bones.
            tag_names = {canonical_bone_name(b.name) for b in tag_armature.data.bones}
            matched = {index for index in self.bone_instances
                       if canonical_bone_name(self.ass.instances[index].name) in tag_names}
            for index in weighted - matched:
                ancestor = self.ass.instances[index].parent
                while ancestor != -1 and ancestor not in matched:
                    ancestor = self.ass.instances[ancestor].parent
                if ancestor == -1:
                    # An omitted authoring root can still carry weights. Tool
                    # transfers these to its surviving compiled root child.
                    roots = []
                    for candidate in matched:
                        name = canonical_bone_name(self.ass.instances[candidate].name)
                        bone = next(b for b in tag_armature.data.bones
                                    if canonical_bone_name(b.name) == name)
                        if bone.parent is not None:
                            continue
                        parent = self.ass.instances[candidate].parent
                        while parent != -1 and parent != index:
                            parent = self.ass.instances[parent].parent
                        if parent == index:
                            roots.append(candidate)
                    ancestor = roots[0] if len(roots) == 1 else -1
                if ancestor == -1:
                    raise TagBoneMappingError(f'{self.path}: weighted ASS bone absent from render model: '
                                   f'{self.ass.instances[index].name}')
                self.bone_aliases[index] = ancestor
            self.bone_instances = matched
        self.order = self.ass.instance_order()
        self.world = {}
        for index in self.order:
            i = self.ass.instances[index]
            matrix = self.ass_matrix(i.local)
            self.world[index] = self.world[i.parent] @ matrix if i.parent != -1 else matrix
        if import_info_kind and not self.is_model:
            self.source_node_scope = main_frame_scope(
                [i.name for i in self.ass.instances], [i.parent for i in self.ass.instances],
                self.order, [i.unique_id for i in self.ass.instances])
        if import_info_kind:
            self.used_material_indices = set()
            for index in self.order:
                if not self.includes_instance(index):
                    continue
                instance = self.ass.instances[index]
                if instance.geometry != -1:
                    geometry = self.ass.geometries[instance.geometry]
                    self.used_material_indices.add(geometry.material)
                    self.used_material_indices.update(t.material for t in geometry.triangles)
        materials = []
        for m in self.ass.materials:
            region, permutation = m.region_permutation() if self.is_model else (self.path.stem, 'default')
            materials.append(Material(m.name, m.variant, region, permutation))
        self.jms = JMS(name=self.path.stem, materials=materials)
        self.bone_map = {index: n for n, index in enumerate(i for i in self.order if i in self.bone_instances)}
        for index in self.bone_map:
            instance = self.ass.instances[index]
            parent = instance.parent
            while parent != -1 and parent not in self.bone_map:
                parent = self.ass.instances[parent].parent
            world = self.world[index] @ self.ass_matrix(instance.pivot)
            rotation = world.to_quaternion()
            transform = Transform((rotation.x, rotation.y, rotation.z, rotation.w), tuple(world.translation))
            self.jms.nodes.append(Node(instance.name, self.bone_map.get(parent, -1), transform))
        if len({n.name for n in self.jms.nodes}) != len(self.jms.nodes):
            raise ASSError('ASS skeleton has duplicate bone names')

    @staticmethod
    def ass_matrix(transform):
        x, y, z, w = transform.rotation
        return Matrix.LocRotScale(Vector(transform.translation), Quaternion((w, x, y, z)), Vector(transform.scale))

    def object(self, name, data=None):
        ob = super().object(name, data)
        if not self.is_model:
            self.owner.set_region(ob, self.path.stem)
            self.owner.set_permutation(ob, 'default')
        return ob

    def place_local(self, ob, transform, *, reference=False):
        """Construct source TRS channels without inverting a parent world matrix."""
        x, y, z, w = transform.rotation
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = Quaternion((w, x, y, z))
        ob.location = tuple(value * self.geometry_scale for value in transform.translation)
        ob.scale = transform.scale
        if reference:
            ob.rotation_quaternion = ob.rotation_quaternion @ axis_rotation(-self.owner.from_x_rot).to_quaternion()

    def remove_import_info_frames(self):
        if self.hierarchy_units:
            return  # These editable transforms retain pivots and source precision.
        super().remove_import_info_frames()

    def store_metadata(self):
        # ASS records are import-time data. Blender objects and Foundry
        # properties are the only persisted authoring state.
        pass

    def build_materials(self):
        from ..tools.importer import JMSMaterialSlot
        self.global_materials = {}
        for index, source in enumerate(self.ass.materials):
            if self.used_material_indices is not None and index not in self.used_material_indices:
                continue
            self.props[index] = JMSMaterialSlot.from_name(source.name)
            name = re.sub(r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+', '', source.name,
                          flags=re.IGNORECASE).strip()
            parts = name.split(maxsplit=1)
            if self.is_model and len(parts) > 1:
                self.global_materials[index], name = parts
            name = utils.base_material_name(name, True).lower() or 'default'
            path = self.source_shader_path(name)
            if Path(path).suffix.lower() in {'.shader_water', '.shader_transparent_water'}:
                self.props[index].water_surface = True
            display_name = Path(path).stem if path else name
            self.materials[index] = self.material(display_name, path, name)
            self.props[index].material.name = name
        flags = ('two_sided', 'transparent_one_sided', 'transparent_two_sided', 'render_only',
                 'collision_only', 'sphere_collision_only', 'fog_plane', 'ladder', 'breakable',
                 'ai_deafening', 'no_shadow', 'shadow_only', 'lightmap_only', 'precise',
                 'conveyor', 'portal_one_way', 'portal_door', 'portal_vis_blocker',
                 'ignored_by_lightmaps', 'blocks_sound', 'decal_offset', 'slip_surface')
        for index, material in enumerate(self.ass.materials):
            if self.used_material_indices is not None and index not in self.used_material_indices:
                continue
            p = self.props[index]
            p.emissive_color, p.emissive_quality = (1, 1, 1), 1.0
            p.emissive_per_unit, p.emissive_shader_gel, p.emissive_focus = False, False, 0.0
            p.emissive_attenuation_falloff = p.emissive_attenuation_cutoff = 0.0
            p.emissive_bounce_ratio = 0.0
            p.emissive_attenuation_mode = 'AUTO'
            p.emissive_frustum = False
            p.emissive_basic = any(r.split()[0] == 'BM_LIGHTING_BASIC' for r in material.lighting if r.split())
            if self.owner.game == 'halo2' and p.emissive_half_life is not None:
                p.emissive_half_life *= self.scale
            # Older ASS materials can encode power in the name instead of a
            # BM_LIGHTING_BASIC record. Explicit lighting records take priority.
            if self.owner.game in {'halo3', 'halo3odst'}:
                p.emissive_power = p.emissive_power_scale
                if not self.is_model and p.lightmap_resolution_scale_legacy is None:
                    # Tool defaults to 3 when an ASS material has no lightmap
                    # record. Retain that value as an editable face setting;
                    # an explicit BM_LMRES record below still takes priority.
                    p.lightmap_resolution_scale_legacy = 3.0
                    p.lightmap_resolution_scale = 7
            p.ignore_default_resolution = False
            for record in material.lighting:
                parts = record.split()
                if not parts:
                    continue
                key, values = parts[0], parts[1:]
                try:
                    if key == 'BM_FLAGS':
                        if len(values) != 1 or len(values[0]) < 21 or set(values[0]) - {'0', '1'}:
                            raise ValueError('expected at least 21 binary flags')
                        for flag, bit in zip(flags, values[0]):
                            setattr(p, flag, getattr(p, flag, False) or bit == '1')
                    elif key == 'BM_LMRES':
                        nums = [float(v) for v in values]
                        if len(nums) not in (3, 5, 10, 11):
                            raise ValueError('unexpected lightmap record length')
                        p.lightmap_resolution_scale_legacy = nums[0]
                        p.lightmap_photon_fidelity = int(nums[1])
                        p.lightmap_resolution_scale = utils.clamp(int(nums[0] * 3), 1, 7)
                        tint = (nums[2],) * 3 if len(nums) == 3 else tuple(nums[2:5])
                        p.lightmap_translucency_tint_color = tint if any(tint) else None
                        if len(nums) >= 10:
                            p.lightmap_transparency_override = bool(nums[5])
                            p.lightmap_additive_transparency = tuple(nums[6:9]) if any(nums[6:9]) else None
                            p.emissive_shader_gel = bool(nums[9])
                        if len(nums) == 11:
                            p.ignore_default_resolution = bool(nums[10])
                    elif key == 'BM_LIGHTING_BASIC':
                        nums = [float(v) for v in values]
                        if len(nums) not in (5, 6, 7):
                            raise ValueError('unexpected emissive record length')
                        p.emissive_power, p.emissive_color, p.emissive_quality = nums[0], tuple(nums[1:4]), nums[4]
                        p.emissive_per_unit = bool(nums[5]) if len(nums) >= 6 else False
                        p.emissive_focus = radians(180 * (1 - nums[6])) if len(nums) >= 7 else 0
                    elif key == 'BM_LIGHTING_ATTEN':
                        enabled, falloff, cutoff = map(float, values)
                        p.emissive_attenuation_mode = 'ENABLED' if enabled else 'DISABLED'
                        p.emissive_attenuation_falloff = falloff * self.scale
                        p.emissive_attenuation_cutoff = cutoff * self.scale
                    elif key == 'BM_LIGHTING_FRUS':
                        blend, falloff, cutoff = map(float, values)
                        p.emissive_frustum = True
                        p.emissive_frustum_blend = blend
                        p.emissive_frustum_falloff = radians(falloff)
                        p.emissive_frustum_cutoff = radians(cutoff)
                    # Unknown lighting records remain in collection metadata.
                except (ValueError, IndexError) as error:
                    raise ASSError(f'Material {material.name!r}: invalid {key}: {error}') from error
            if (self.owner.game in {'halo3', 'halo3odst'} and p.emissive_power is None
                    and (p.emissive_shader_gel or p.emissive_frustum or p.emissive_attenuation_mode != 'AUTO')):
                # ASS can author these independently of BM_LIGHTING_BASIC.
                # Preserve them even on a currently non-emitting material.
                p.emissive_power = 0.0
            p.mesh_type = p._mesh_type_from_special_name()

    def apply_materials(self, ob, faces_by_material):
        super().apply_materials(ob, faces_by_material)
        if -1 in faces_by_material:
            slot = len(ob.data.materials)
            ob.data.materials.append(None)
            for face in faces_by_material[-1]:
                ob.data.polygons[face].material_index = slot
        if self.active_kind == 'collision' and not self.is_model:
            if not any(prop.type == 'face_mode' for prop in ob.data.nwo.face_props):
                utils.add_face_prop(ob.data, 'face_mode').face_mode = 'collision_only'
        for index, faces in faces_by_material.items():
            game = getattr(self.owner, 'game', None)
            if (index in self.props and self.props[index].ignore_default_resolution and faces
                    and (not game or face_prop_game_supported('lightmap_ignore_default_resolution_scale', game))):
                mask = [False] * len(ob.data.polygons)
                for face in faces:
                    mask[face] = True
                utils.add_face_prop(ob.data, 'lightmap_ignore_default_resolution_scale', mask)
            if self.supports_collision_material_properties() and index in self.global_materials and faces and not self.uses_collision_material(ob) and ob.data.nwo.mesh_type not in {
                    '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics'}:
                mask = [False] * len(ob.data.polygons)
                for face in faces:
                    mask[face] = True
                utils.add_face_prop(ob.data, 'global_material', mask).global_material = self.global_materials[index]

    def collision_material_name(self, index, material):
        return self.global_materials.get(index, material.name)

    def supports_collision_material_properties(self):
        # ASS targets pre-H4 games; BSP collision materials come from shaders.
        return self.is_model

    def uses_collision_material(self, ob):
        # BSP collision surfaces resolve their physical material through the
        # original shader. A display-only Collision material loses that binding.
        return (self.is_model and self.active_kind == 'collision') or super().uses_collision_material(ob)

    def mesh_kind(self, props):
        if (not self.is_model and props is not None
                and props.material.name.casefold().startswith('+seamsealer')):
            # This is a face-level sealing material, not a separate seam
            # object. Keep it inside its source geometry/instance.
            return self.active_kind or 'default'
        if self.active_kind == 'instance' and props and props.mesh_type != 'default':
            kind = props.mesh_type
            return ('default' if kind == 'weather_polyhedron'
                    and getattr(self.owner, 'game', None) not in {'halo2', 'halo3', 'halo3odst'} else kind)
        if self.active_kind:
            return self.active_kind
        kind = props.mesh_type if props else 'default'
        return ('default' if kind == 'weather_polyhedron'
                and getattr(self.owner, 'game', None) not in {'halo2', 'halo3', 'halo3odst'} else kind)

    def mesh_created(self, ob, source_indices):
        self.source_indices[ob] = source_indices
        geometry = self.active_geometry
        for channel, layer in enumerate(list(ob.data.uv_layers)):
            store_uv_w(ob.data, layer, [geometry.vertices[i].uvs[channel][2]
                if channel < len(geometry.vertices[i].uvs) and len(geometry.vertices[i].uvs[channel]) == 3 else 0
                for i in (source_indices[loop.vertex_index] for loop in ob.data.loops)])

    def role(self, instance, geometry):
        name = instance.name
        if not self.is_model and self.owner.game in {'halo3', 'halo3odst'} and name.startswith('~'):
            return 'water_physics'
        if name.startswith('@'):
            return 'collision'
        if name.startswith('$') or geometry.kind in {'SPHERE', 'BOX', 'PILL'}:
            return 'physics'
        if name.startswith('%'):
            return 'io' if self.is_model else 'instance'
        if self.is_model and self.path.parent.name.lower() in {'collision', 'physics'}:
            return self.path.parent.name.lower()
        return ''

    def geometry_objects(self, index):
        instance = self.ass.instances[index]
        geometry = self.ass.geometries[instance.geometry]
        kind = self.role(instance, geometry)
        # Deform weights live on Mesh data, while group names live on Object.
        # Share skinned geometry only when its instance palette is identical.
        cache_key = (instance.geometry, kind, instance.bones)
        if cache_key in self.templates:
            result = []
            for template in self.templates[cache_key]:
                ob = template.copy()
                self.objects.append(ob)
                self.collection.objects.link(ob)
                if template in self.source_indices:
                    self.source_indices[ob] = self.source_indices[template]
                result.append(ob)
            return result
        self.active_kind, self.active_geometry = kind, geometry
        old_rotation, old_arm, old_scale = self.rotation, self.armature, self.scale
        self.rotation, self.armature = Matrix.Identity(4), None
        self.scale = self.geometry_scale
        before = len(self.objects)
        try:
            if geometry.kind == 'MESH':
                self.jms.vertices = [replace(v, uvs=tuple(uv[:2] for uv in v.uvs)) for v in geometry.vertices]
                self.jms.triangles = geometry.triangles
                super().build_meshes()
            else:
                dimensions = geometry.dimensions
                if geometry.kind == 'BOX':
                    dimensions = tuple(d * 2 for d in dimensions)  # ASS stores half-extents.
                shape = Shape({'SPHERE': 'sphere', 'BOX': 'box', 'PILL': 'pill'}[geometry.kind],
                              instance.name, -1, geometry.material, Transform((0, 0, 0, 1), (0, 0, 0)), dimensions)
                self.jms.shapes = [shape]
                super().build_shapes()
                self.jms.shapes = []
        finally:
            self.rotation, self.armature, self.scale = old_rotation, old_arm, old_scale
        result = self.objects[before:]
        self.templates[cache_key] = result
        return result

    def bind_skin(self, ob, instance, geometry):
        if not instance.bones or ob not in self.source_indices:
            return
        if ob.vertex_groups:
            return  # A copy with the same palette already has groups and weights.
        buckets = defaultdict(list)
        for local, source in enumerate(self.source_indices[ob]):
            combined = defaultdict(float)
            for palette, weight in geometry.vertices[source].influences:
                if palette != -1 and weight > 0:
                    bone = instance.bones[palette]
                    if bone != -1:
                        bone = self.bone_aliases.get(bone, bone)
                        combined[bone] += weight
            total = sum(combined.values())
            for bone, weight in combined.items():
                buckets[(bone, weight / total)].append(local)
        groups = {}
        for (bone, weight), vertices in buckets.items():
            if bone not in groups:
                groups[bone] = ob.vertex_groups.new(name=self.tag_bone_names.get(
                    self.bone_map[bone], self.ass.instances[bone].name))
            groups[bone].add(vertices, weight, 'REPLACE')
        if buckets and self.armature:
            modifier = ob.modifiers.new('Armature', 'ARMATURE')
            modifier.object = self.armature

    def build_contents(self):
        self.node_matrices()
        self.build_armature()
        self.build_materials()
        unit_frame = None
        if self.hierarchy_units:
            unit_frame = self.object('frame units')
            unit_frame.nwo.is_frame = True
            unit_frame.rotation_mode = 'QUATERNION'
            unit_frame.rotation_quaternion = self.rotation.to_quaternion()
            unit_frame.scale = (self.scale / self.geometry_scale,) * 3
        included = {index for index in self.order if self.includes_instance(index)}
        required = set(included)
        if self.hierarchy_units:
            for index in included:
                parent = self.ass.instances[index].parent
                while parent >= 0 and parent not in required:
                    required.add(parent)
                    parent = self.ass.instances[parent].parent
        for index in self.order:
            if index not in required:
                continue
            instance = self.ass.instances[index]
            if index in self.bone_map:
                continue
            anchor = self.object(instance.name + ':frame')
            anchor.nwo.is_frame = True
            # Foundry excludes frame empties themselves. Keep anchors enabled
            # while building; select_export_root disables competing roots once
            # collapse_frames has produced the final hierarchy.
            self.anchors[index] = anchor
            if instance.parent in self.bone_map:
                anchor.parent = self.armature
                anchor.parent_type = 'BONE'
                anchor.parent_bone = self.tag_bone_names.get(
                    self.bone_map[instance.parent], self.ass.instances[instance.parent].name)
            else:
                anchor.parent = self.anchors.get(instance.parent)
            if self.hierarchy_units:
                if anchor.parent is None:
                    anchor.parent = unit_frame
                self.place_local(anchor, instance.local)
            else:
                anchor.rotation_mode = 'QUATERNION'
                anchor.matrix_world = self.scene_matrix(self.world[index])
            if index not in included:
                # A culled wrapper still contributes its editable transform,
                # without bringing its display shape or siblings into the BSP.
                continue
            if is_frame_name(instance.name):
                # Tool treats frames as hierarchy nodes even when Max exports
                # their helper display mesh. Import-info must match direct ASS
                # import and never turn that helper into structure/collision.
                if self.geometry_only:
                    continue
                anchor.name = instance.name
                anchor.empty_display_type = 'ARROWS'
                anchor.empty_display_size = max(self.scale, 0.001)
                self.frame_instances.add(index)
                self.instance_objects[index] = [anchor]
                continue
            if instance.unique_id == -1:
                continue
            geometry = self.ass.geometries[instance.geometry] if instance.geometry != -1 else None
            # Structural XREFs can carry the complete BSP surface. A reference
            # to an existing game-object asset instead carries preview geometry
            # (Flood Voi's floodballs), which must not become static BSP walls.
            reference_type = ass_reference_type(instance.name)
            # The compiled palette records Tool's resolved type. H3 can compile
            # a ?machine? source reference as scenery; preserve that exact path.
            # Without a palette match, an explicit prefix still takes priority
            # over another object type that happens to exist on disk.
            embedded_tag = (self.embedded_game_object_tag(geometry, known_only=bool(reference_type))
                            if geometry is not None and not self.is_model else '')
            if embedded_tag:
                reference_type = Path(embedded_tag).suffix
            reference_only = bool(reference_type or (geometry and geometry.kind == 'MESH' and geometry.xref_path
                                  and not (geometry.vertices and geometry.triangles)))
            if self.geometry_only and (instance.name.startswith('#') or geometry is None
                                       or reference_only or geometry.kind == 'GENERIC_LIGHT'):
                continue
            matrix = self.scene_matrix(self.world[index] @ self.ass_matrix(instance.pivot))
            if reference_only:
                if self.owner.game in ASS_GAMES:
                    # Tool places the referenced object at its node transform.
                    # The object-offset pivot belongs only to the embedded preview
                    # mesh; applying it rotates/offsets devices in the rebuilt BSP.
                    matrix = self.scene_matrix(self.world[index])
                # Referenced models already use the scene's forward axes.
                # Convert the marker's local basis as well as its world basis.
                matrix = marker_axis.local_axes(matrix, self.owner.from_x_rot)
                ob = self.object(ass_reference_name(instance.name) if reference_type else instance.name.lstrip('#'))
                from ..tools.importer import XREF
                path = geometry.xref_path if geometry else ''
                xref_name = geometry.xref_name if geometry else ''
                if embedded_tag:
                    tag, fallback = embedded_tag, ''
                elif reference_type or not self.is_model:
                    reference_type = reference_type or '.scenery'
                    from pathlib import PureWindowsPath
                    asset_name = PureWindowsPath(path.replace('/', '\\')).stem or ass_reference_name(instance.name)
                    xref = XREF(instance.name, path, asset_name)
                    xref.preferred_type = reference_type
                    tag, fallback = self.owner._resolve_xref_tag_path(xref, (reference_type,))
                    fallback = fallback or asset_name + reference_type
                else:
                    tag, fallback = self.owner._resolve_xref_tag_path(XREF(instance.name, path, xref_name))
                ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                ob.nwo.marker_game_instance_tag_name = tag or fallback or ''
                objects = [ob]
            elif instance.name.startswith('#') or geometry is None:
                name = instance.name.lstrip('#')
                match = re.match(r'^\((\S+)\s+(\S+)\)(.*)$', name)
                ob = self.object((match[3] if match else name).strip())
                ob.empty_display_type = 'ARROWS'
                ob.empty_display_size = self.scale * (geometry.dimensions[0] if geometry and geometry.kind == 'SPHERE' else 1)
                ob.nwo.is_frame = not instance.name.startswith('#')
                if self.is_model and match:
                    self.owner.set_region(ob, match[2])
                    self.owner.set_permutation(ob, match[1])
                    ob.nwo.marker_uses_regions = True
                    ob.nwo.marker_permutation_type = 'include'
                    ob.nwo.marker_permutations.add().name = match[1]
                elif self.is_model and geometry and geometry.material != -1:
                    region, permutation = self.ass.materials[geometry.material].region_permutation()
                    self.owner.set_region(ob, region)
                    self.owner.set_permutation(ob, permutation)
                for prefix, kind in (('fx', 'effects'), ('target', 'target'), ('garbage', 'garbage'), ('hint', 'hint')):
                    if ob.name.startswith(prefix):
                        ob.nwo.marker_type = '_connected_geometry_marker_type_' + kind
                        break
                objects = [ob]
            elif geometry.kind == 'GENERIC_LIGHT':
                objects = [self.light_object(instance, geometry.light)]
            else:
                objects = self.geometry_objects(index)
                for ob in objects:
                    ob.name = f'{instance.name}:{ob.nwo.permutation_name}:{ob.nwo.region_name}'
                    if instance.name.startswith('%'):
                        self.owner.set_poop_policies(ob)
                        if self.is_model:
                            ob.nwo.marker_uses_regions = ob.nwo.region_name != 'default'
                            ob.nwo.marker_permutation_type = 'include'
                            ob.nwo.marker_permutations.clear()
                            ob.nwo.marker_permutations.add().name = ob.nwo.permutation_name
                    self.bind_skin(ob, instance, geometry)
            for ob in objects:
                # Skinning already applies the bones' motion. Inheriting that
                # motion through a bone-parented anchor applies it twice.
                skinned = any(mod.type == 'ARMATURE' and mod.object == self.armature
                              for mod in ob.modifiers)
                ob.parent = self.armature if skinned else anchor
                ob.parent_type = 'OBJECT'
                if not self.is_model:
                    pivot = instance.pivot
                    if reference_only and self.owner.game in ASS_GAMES:
                        pivot = replace(pivot, rotation=(0, 0, 0, 1), translation=(0, 0, 0), scale=(1, 1, 1))
                    self.place_local(ob, pivot, reference=reference_only)
                    if reference_only or ob.type == 'LIGHT':
                        # Referenced previews and light data already use scene units.
                        ob.scale *= self.geometry_scale / self.scale
                else:
                    ob.matrix_world = matrix
            self.instance_objects[index] = objects
        if not self.import_info_kind and not self.hierarchy_units:
            self.collapse_frames()
        self.link_collision_proxies()
        bpy.context.view_layer.update()

    def embedded_game_object_tag(self, geometry, *, known_only=False):
        return embedded_game_object_tag(geometry.xref_path, geometry.xref_name,
                                        utils.get_tags_path(), utils.get_data_path(), self.game_object_paths,
                                        known_only=known_only)

    def includes_instance(self, index):
        instance = self.ass.instances[index]
        geometry = self.ass.geometries[instance.geometry] if instance.geometry != -1 else None
        reference = ass_reference_type(instance.name) or (
            not self.is_model and geometry is not None and self.embedded_game_object_tag(geometry))
        if self.render_only:
            if (instance.name.startswith(('@', '$'))
                    or (not reference and geometry is not None and not instance.name.startswith('#')
                        and self.role(instance, geometry) in {'collision', 'physics'})
                    or (not self.is_model and instance.name.startswith('#'))):
                return False
        if not self.import_info_kind:
            return True
        if self.source_node_scope is not None and index not in self.source_node_scope:
            return False
        if not self.is_model and is_frame_name(instance.name):
            return True  # Primitive frame display shapes are not physics meshes.
        physics = not reference and (instance.name.startswith('$') or (not instance.name.startswith('#') and geometry is not None
                  and geometry.kind in {'SPHERE', 'BOX', 'PILL'}))
        if self.import_info_kind == 'physics_model':
            return index in self.bone_instances or physics
        if self.import_info_kind in {'render_model', 'model', 'gbxmodel', 'sky', 'particle_model', 'decorator_set'}:
            return not physics and not instance.name.startswith('@')
        if not self.is_model:
            return not physics
        return True

    def collapse_frames(self):
        """Use the imported object as the hierarchy anchor wherever possible.

        A split instance with descendants still needs an independent anchor:
        none of its material parts alone represents the source parent.
        Preserve world transforms, including pivots and bone parenting.
        """
        bpy.context.view_layer.update()
        # Reparenting preserves these evaluated transforms. Snapshot once so
        # large scenario imports do not rebuild the dependency graph per anchor.
        world_matrices = {ob: ob.matrix_world.copy() for ob in self.objects}
        removed = set()
        parents = {i.parent for i in self.ass.instances}
        for index in reversed(self.order):
            anchor = self.anchors.get(index)
            if anchor is None:
                continue
            if index in self.frame_instances:
                continue
            instance = self.ass.instances[index]
            if (instance.unique_id == -1 and instance.parent == -1
                    and any(self.ass.instances[i].parent == index for i in self.frame_instances)):
                # The Max scene root also owns authoring guides outside the
                # actual export frame. Keep their exclusion after collapsing
                # helper frames instead of exporting them as BSP surfaces.
                for child in list(anchor.children):
                    if child in (self.anchors[i] for i in self.frame_instances):
                        child.parent = None
                        child.matrix_world = world_matrices[child]
                continue
            objects = self.instance_objects.get(index, [])
            if len(objects) > 1 and index in parents:
                continue
            replacement = objects[0] if len(objects) == 1 else None
            children = list(anchor.children)
            for ob in children:
                if replacement is not None and ob != replacement:
                    ob.parent = replacement
                    ob.parent_type = 'OBJECT'
                else:
                    ob.parent = anchor.parent
                    ob.parent_type = anchor.parent_type
                    ob.parent_bone = anchor.parent_bone
                ob.matrix_world = world_matrices[ob]
            removed.add(anchor)
            del self.anchors[index]
        self.objects = [ob for ob in self.objects if ob not in removed]
        bpy.data.batch_remove(removed)
        bpy.context.view_layer.update()

    def link_collision_proxies(self):
        if self.is_model:
            return
        proxies = defaultdict(list)
        for index, instance in enumerate(self.ass.instances):
            if not instance.name.startswith('@') or instance.parent == -1:
                continue
            if not self.ass.instances[instance.parent].name.startswith('%'):
                continue
            parents = { (o.nwo.region_name, o.nwo.permutation_name): o
                       for o in self.instance_objects.get(instance.parent, []) if o.type == 'MESH'}
            for child in self.instance_objects.get(index, []):
                if child.type != 'MESH':
                    continue
                parent = parents.get((child.nwo.region_name, child.nwo.permutation_name))
                if parent is None:
                    continue
                # Foundry proxies use the render mesh's local coordinates.
                # ASS collision children have independent transforms/pivots.
                # Bake those here and retain every child of an instance.
                if child.data.users > 1:
                    child.data = child.data.copy()
                relative = (self.ass_matrix(self.ass.instances[instance.parent].pivot).inverted()
                            @ self.ass_matrix(instance.local) @ self.ass_matrix(instance.pivot))
                normals = [(relative.to_3x3().inverted().transposed() @ n.vector).normalized()
                           for n in child.data.corner_normals]
                # Convert the translation to Blender units before baking the
                # child's current local geometry into the render instance.
                relative.translation *= self.geometry_scale
                points = [relative @ vertex.co for vertex in child.data.vertices]
                for vertex, point in zip(child.data.vertices, points):
                    vertex.co = point
                child.data.normals_split_custom_set(normals)
                child.parent = parent
                child.matrix_parent_inverse = Matrix.Identity(4)
                child.matrix_basis = Matrix.Identity(4)
                proxies[parent].append(child)
        bpy.context.view_layer.update()
        for parent, children in proxies.items():
            if parent.data.users > 1:
                parent.data = parent.data.copy()
            if len(children) > 1:
                self.objects = [ob for ob in self.objects if ob not in children[1:]]
                child = utils.join_objects(children, cleanup_geometry=False)
            else:
                child = children[0]
            parent.data.nwo.proxy_collision = child
            child.nwo.proxy_type = 'collision'
            utils.unlink(child)

    def light_object(self, instance, light):
        kind = {'SPOT_LGT': 'SPOT', 'DIRECT_LGT': 'AREA', 'OMNI_LGT': 'POINT', 'AMBIENT_LGT': 'SUN'}.get(light.kind)
        if kind is None:
            raise ASSError(f'Unsupported ASS light type {light.kind}')
        data = bpy.data.lights.new(instance.name, kind)
        ob = self.object(instance.name, data)
        data.color, data.energy = light.color, max(0, light.intensity)
        if kind == 'SPOT':
            data.spot_size = radians(max(0, light.falloff))
            data.spot_blend = max(0, min(1, (light.falloff - light.hotspot) / light.falloff)) if light.falloff > 0 else 0
        if kind == 'AREA':
            data.shape = 'RECTANGLE' if light.shape else 'DISK'
            data.size = max(self.scale, abs(light.hotspot) * self.scale)
            if light.shape:
                data.size_y = data.size / max(light.aspect, 0.001)
        for suffix, value in (('near_attenuation_start', light.near_start if light.near_enabled else 0),
                              ('near_attenuation_end', light.near_end if light.near_enabled else 0),
                              ('far_attenuation_start', light.far_start if light.far_enabled else 0),
                              ('far_attenuation_end', light.far_end if light.far_enabled else 0)):
            setattr(data.nwo, 'light_' + suffix, value * self.scale)
        if self.owner.game in {'halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'} and kind != 'SUN':
            data.nwo.light_intensity = max(0, light.intensity)
            utils.make_halo_light(data)
        return ob


def import_ass(owner, path, legacy_type, *, parent_collection=None, tag_armature=None,
               geometry_only=False, allowed_region_permutations=(), shader_paths=None, import_info_kind='',
               render_only=False, game_object_paths=()):
    return ASSImporter(owner, path, legacy_type, parent_collection=parent_collection,
                       tag_armature=tag_armature, geometry_only=geometry_only,
                       allowed_region_permutations=allowed_region_permutations, shader_paths=shader_paths,
                       import_info_kind=import_info_kind, render_only=render_only,
                       game_object_paths=game_object_paths).build()
