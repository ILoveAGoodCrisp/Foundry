"""Native ASS scene adapter, sharing Foundry geometry/material construction with JMS."""
from collections import defaultdict
from dataclasses import asdict, replace
from math import radians
from pathlib import Path
import json
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

from .ass_format import ASS, ASSError
from .jms_format import JMS, Material, Node, Transform, Shape
from .jms_importer import JMSImporter
from .. import utils


class ASSImporter(JMSImporter):
    def __init__(self, owner, path, legacy_type):
        self.owner, self.path = owner, Path(path)
        self.ass = ASS.from_file(path)
        self.scale = owner.scale_factor
        self.rotation = Matrix.Rotation(owner.from_x_rot, 4, 'Z')
        self.objects, self.materials, self.created_materials, self.props = [], {}, [], {}
        self.armature, self.node_world = None, {}
        self.source_indices, self.templates, self.anchors = {}, {}, {}
        self.instance_objects = {}
        weighted = {b for i in self.ass.instances for b in i.bones if b != -1}
        self.is_model = legacy_type == 'model' or (legacy_type == 'auto' and (
            bool(weighted) or self.path.parent.name.lower() in {'render', 'collision', 'physics'}))
        self.bone_instances = weighted if self.is_model else set()
        if self.is_model:
            self.bone_instances |= {index for index, i in enumerate(self.ass.instances)
                                    if i.name.lower().startswith(('b ', 'b_', 'bone', 'frame', 'bip01')) and i.unique_id != -1}
        self.order = self.ass.instance_order()
        self.world = {}
        for index in self.order:
            i = self.ass.instances[index]
            matrix = self.ass_matrix(i.local)
            self.world[index] = self.world[i.parent] @ matrix if i.parent != -1 else matrix
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

    def store_metadata(self):
        self.collection['ass_version'] = self.ass.version
        self.collection['ass_header'] = json.dumps(self.ass.header)
        self.collection['ass_materials'] = json.dumps([asdict(m) for m in self.ass.materials])
        if self.ass.invalid_uv_components:
            self.collection['ass_repaired_uv_components'] = self.ass.invalid_uv_components
            utils.print_warning(f'{self.path.name}: replaced {self.ass.invalid_uv_components} non-finite UV components with zero (first at line {self.ass.first_invalid_uv_line})')

    def build_materials(self):
        from ..tools.importer import JMSMaterialSlot
        self.global_materials = {}
        for index, source in enumerate(self.ass.materials):
            self.props[index] = JMSMaterialSlot.from_name(source.name)
            name = re.sub(r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+', '', source.name).strip()
            parts = name.split(maxsplit=1)
            if len(parts) > 1:
                self.global_materials[index], name = parts
            name = utils.base_material_name(name, True).lower() or 'default'
            self.materials[index] = self.material(name)
            self.props[index].material.name = name
        flags = ('two_sided', 'transparent_one_sided', 'transparent_two_sided', 'render_only',
                 'collision_only', 'sphere_collision_only', 'fog_plane', 'ladder', 'breakable',
                 'ai_deafening', 'no_shadow', 'shadow_only', 'lightmap_only', 'precise',
                 'conveyor', 'portal_one_way', 'portal_door', 'portal_vis_blocker',
                 'ignored_by_lightmaps', 'blocks_sound', 'decal_offset', 'slip_surface')
        for index, material in enumerate(self.ass.materials):
            p = self.props[index]
            p.emissive_color, p.emissive_quality = (1, 1, 1), 1.0
            p.emissive_per_unit, p.emissive_shader_gel, p.emissive_focus = False, False, 0.0
            p.emissive_attenuation_falloff = p.emissive_attenuation_cutoff = 0.0
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
                        if enabled:
                            p.emissive_attenuation_falloff = falloff * self.scale
                            p.emissive_attenuation_cutoff = cutoff * self.scale
                    # Frustum and other unsupported records remain in collection metadata.
                except (ValueError, IndexError) as error:
                    raise ASSError(f'Material {material.name!r}: invalid {key}: {error}') from error
            p.mesh_type = p._mesh_type_from_special_name()

    def apply_materials(self, ob, faces_by_material):
        super().apply_materials(ob, faces_by_material)
        if self.active_kind == 'collision' and not self.is_model:
            utils.add_face_prop(ob.data, 'face_mode').face_mode = 'collision_only'
        for index, faces in faces_by_material.items():
            if index in self.props and self.props[index].ignore_default_resolution and faces:
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
        return self.active_kind == 'collision' or super().uses_collision_material(ob)

    def mesh_kind(self, props):
        if self.active_kind == 'instance' and props and props.mesh_type != 'default':
            kind = props.mesh_type
            return ('default' if kind == 'weather_polyhedron'
                    and getattr(self.owner, 'game', None) != 'halo2' else kind)
        if self.active_kind:
            return self.active_kind
        kind = props.mesh_type if props else 'default'
        return ('default' if kind == 'weather_polyhedron'
                and getattr(self.owner, 'game', None) != 'halo2' else kind)

    def mesh_created(self, ob, source_indices):
        self.source_indices[ob] = source_indices
        # Blender UV layers only hold XY. Preserve ASS's third UV component.
        geometry = self.active_geometry
        for channel in range(max((len(v.uvs) for v in geometry.vertices), default=0)):
            if any(len(v.uvs[channel]) == 3 for v in geometry.vertices if channel < len(v.uvs)):
                attribute = ob.data.attributes.new(f'ass_uv_w_{channel}', 'FLOAT', 'POINT')
                attribute.data.foreach_set('value', [geometry.vertices[i].uvs[channel][2]
                    if channel < len(geometry.vertices[i].uvs) and len(geometry.vertices[i].uvs[channel]) == 3 else 0 for i in source_indices])

    def role(self, instance, geometry):
        name = instance.name
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
        old_rotation, old_arm = self.rotation, self.armature
        self.rotation, self.armature = Matrix.Identity(4), None
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
            self.rotation, self.armature = old_rotation, old_arm
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
                        combined[bone] += weight
            total = sum(combined.values())
            for bone, weight in combined.items():
                buckets[(bone, weight / total)].append(local)
        groups = {}
        for (bone, weight), vertices in buckets.items():
            if bone not in groups:
                groups[bone] = ob.vertex_groups.new(name=self.ass.instances[bone].name)
            groups[bone].add(vertices, weight, 'REPLACE')
        if buckets and self.armature:
            modifier = ob.modifiers.new('Armature', 'ARMATURE')
            modifier.object = self.armature

    def build_contents(self):
        self.node_matrices()
        self.build_armature()
        self.build_materials()
        for index in self.order:
            instance = self.ass.instances[index]
            if index in self.bone_map:
                continue
            anchor = self.object(instance.name + ':frame')
            anchor.nwo.is_frame = True
            # Foundry excludes frame empties themselves. Keep export_this enabled:
            # disabling a root object also excludes all its descendants.
            self.anchors[index] = anchor
            if instance.parent in self.bone_map:
                anchor.parent = self.armature
                anchor.parent_type = 'BONE'
                anchor.parent_bone = self.ass.instances[instance.parent].name
            else:
                anchor.parent = self.anchors.get(instance.parent)
            anchor.matrix_world = self.scene_matrix(self.world[index])
            anchor['ass_instance'] = json.dumps(asdict(instance))
            if instance.unique_id == -1:
                continue
            geometry = self.ass.geometries[instance.geometry] if instance.geometry != -1 else None
            matrix = self.scene_matrix(self.world[index] @ self.ass_matrix(instance.pivot))
            if geometry and geometry.xref_path:
                ob = self.object(instance.name.lstrip('#'))
                from ..tools.importer import XREF
                tag, fallback = self.owner._resolve_xref_tag_path(XREF(instance.name, geometry.xref_path, geometry.xref_name))
                ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                ob.nwo.marker_game_instance_tag_name = tag or fallback or ''
                ob['ass_xref_path'], ob['ass_xref_name'] = geometry.xref_path, geometry.xref_name
                objects = [ob]
            elif instance.name.startswith('#') or geometry is None:
                name = instance.name.lstrip('#')
                match = re.match(r'^\((\S+)\s+(\S+)\)(.*)$', name)
                ob = self.object(match[3] if match else name)
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
                ob.parent = anchor
                ob.parent_type = 'OBJECT'
                ob.matrix_world = matrix
                ob['ass_geometry'] = instance.geometry
                ob['ass_identifier'] = str(instance.unique_id)
            self.instance_objects[index] = objects
        self.collapse_frames()
        self.link_collision_proxies()

    def collapse_frames(self):
        """Use the imported object as the hierarchy anchor wherever possible.

        A split instance with descendants still needs an independent anchor:
        none of its material parts alone represents the source parent.
        Preserve world transforms, including pivots and bone parenting.
        """
        bpy.context.view_layer.update()
        parents = {i.parent for i in self.ass.instances}
        for index in reversed(self.order):
            anchor = self.anchors.get(index)
            if anchor is None:
                continue
            objects = self.instance_objects.get(index, [])
            if len(objects) > 1 and index in parents:
                continue
            replacement = objects[0] if len(objects) == 1 else None
            children = list(anchor.children)
            matrices = {ob: ob.matrix_world.copy() for ob in children}
            for ob in children:
                if replacement is not None and ob != replacement:
                    ob.parent = replacement
                    ob.parent_type = 'OBJECT'
                else:
                    ob.parent = anchor.parent
                    ob.parent_type = anchor.parent_type
                    ob.parent_bone = anchor.parent_bone
                ob.matrix_world = matrices[ob]
            for ob in objects:
                ob['ass_instance'] = anchor['ass_instance']
            self.objects.remove(anchor)
            del self.anchors[index]
            bpy.data.objects.remove(anchor, do_unlink=True)
            bpy.context.view_layer.update()

    def link_collision_proxies(self):
        if self.is_model:
            return
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
                if parent.data.users > 1:
                    parent.data = parent.data.copy()
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
        ob['ass_light'] = json.dumps(asdict(light))
        return ob


def import_ass(owner, path, legacy_type):
    return ASSImporter(owner, path, legacy_type).build()
