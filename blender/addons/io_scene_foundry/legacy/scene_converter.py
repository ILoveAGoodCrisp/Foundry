"""Convert existing Halo Blender Toolset objects without an interchange round trip.

The toolset remains optional: access its registered RNA properties only when the
scene-conversion operator is used. Optional transforms convert Halo coordinates
to the current Foundry scene scale and forward before interpreting source properties.
"""
from collections import defaultdict
from pathlib import Path
import re

import bmesh
import bpy
import numpy as np

from .. import utils
from ..constants import face_prop_game_supported


CONVERTED = 'foundry_converted_from_toolset'
PORTAL_POLICIES = ('portal_one_way', 'portal_door', 'portal_vis_blocker',
                   'blocks_sound', 'ai_deafening', 'portal_exact')


def region_definition(name):
    """Toolset face regions contain [LOD] [permutation] region."""
    words = name.split()
    lod = next((w.upper() for w in words if re.fullmatch(r'l[1-6]', w, re.I)), 'L5')
    words = [w for w in words if not re.fullmatch(r'l[1-6]|\(\d+\)', w, re.I)]
    return (words[-1] if words else 'default', words[-2] if len(words) > 1 else 'default', lod)


class HaloSceneConverter:
    def __init__(self, importer, is_model, *, bsp_name="", top_level_bsps=False):
        self.owner = importer
        self.is_model = is_model
        self.top_level_bsps = top_level_bsps and not is_model
        self.bsp_name = '' if self.top_level_bsps else re.sub(r"\.(?:jms|ass)$", "", bsp_name.strip(), flags=re.I)
        # Conversion is always for the current project, never an import-source override.
        self.game = importer.target_game
        self.owner.game = self.game
        self.warnings = set()
        self.material_props = {}
        self.converted_materials = {}

    def props(self, material):
        if material is None:
            return None
        if material not in self.material_props:
            from ..tools.importer import JMSMaterialSlot
            self.material_props[material] = JMSMaterialSlot.from_material(
                material, self.game, self.owner.scale_factor)
            source = material.ass_jms
            # These toolset fields currently have no Foundry export equivalent.
            unsupported = [name for name in (
                'conveyor', 'dislike_photons', 'group_transparents_by_plane',
                'lightmap_half_life', 'lightmap_diffuse_scale',
            ) if getattr(source, name, False)]
            if source.photon_fidelity != 1:
                unsupported.append('photon_fidelity')
            if source.frustum_blend or source.frustum_falloff != 25 or source.frustum_cutoff != 45:
                unsupported.append('frustum lighting')
            if source.emissive_focus > 1:
                unsupported.append('emissive_focus above 1 (clamped)')
            if unsupported:
                self.warnings.add(f'{material.name}: no Foundry equivalent for {", ".join(unsupported)}; source properties retained')
        return self.material_props[material]

    def bsp_sources(self, objects):
        """Resolve source collections before marker replacement or mesh splitting."""
        scene = self.owner.context.scene
        inherited = {}

        def visit(collection, bsp=None):
            if collection.nwo.type == 'region':
                bsp = collection
            inherited[collection] = bsp
            for child in collection.children:
                visit(child, bsp)

        visit(scene.collection)
        result = {}
        for ob in objects:
            if self.bsp_name:
                result[ob] = self.bsp_name, None
                continue
            sources = sorted((c for c in ob.users_collection if c in inherited),
                             key=lambda c: (c != self.owner.context.collection, c.name))
            bsp = next((inherited[c] for c in sources if inherited[c] is not None), None)
            if bsp is not None:
                result[ob] = bsp.nwo.region or bsp.name, bsp
                continue
            source = next((c for c in sources if c != scene.collection), None)
            # Toolset imports do not retain their source filepath. Named source
            # collections are the best available identity; callers can override it.
            name = source.name if source else Path(bpy.data.filepath).stem or 'default'
            name = re.sub(r'\.(?:jms|ass)$', '', name, flags=re.I)
            result[ob] = name, source
        return result

    def prepare_top_level_bsps(self):
        """Classify scene roots, independently of visibility or conversion history."""
        roots = list(self.owner.context.scene.collection.children)
        for collection in roots:
            if collection.library:
                self.warnings.add(f'{collection.name}: linked collection cannot be made a BSP; make it local first')
                continue
            name = collection.name
            bsp = self.owner._ensure_region_entry(name, utils.SetType.SCENARIO)
            collection.nwo.type = 'region'
            collection.nwo.region = bsp
            # A nested BSP would override the requested top-level assignment.
            # Keep other child categories (permutations/exclusions) intact.
            for child in collection.children_recursive:
                if child not in roots and not child.library and child.nwo.type == 'region':
                    child.nwo.type = 'none'

    def assign_bsps(self, converted, sources):
        scene = self.owner.context.scene
        destinations = {}
        converted_set = set(converted)
        for ob in converted:
            name, source = sources[ob]
            destination = destinations.get(name)
            if destination is None:
                destination = next((c for c in scene.collection.children_recursive
                                    if c.nwo.type == 'region' and c.nwo.region == name), None)
                # Do not change the export identity of unconverted/unselected
                # objects sharing a source collection.
                if (destination is None and source is not None and source.library is None
                        and source.nwo.type in {'none', 'region'}
                        and set(source.all_objects).issubset(converted_set)):
                    destination = source
                if destination is None:
                    destination = bpy.data.collections.new(name)
                    scene.collection.children.link(destination)
                bsp = self.owner._ensure_region_entry(name, utils.SetType.SCENARIO)
                destination.nwo.type = 'region'
                destination.nwo.region = bsp
                destinations[name] = destination
            if ob.name not in destination.all_objects:
                destination.objects.link(ob)
            descendants = set(destination.children_recursive)
            for collection in tuple(ob.users_collection):
                if collection != destination and collection not in descendants:
                    collection.objects.unlink(ob)
            ob.nwo.region_name = destination.nwo.region

    def convert(self, objects, *, convert_scale=False, convert_forward=False):
        objects = [ob for ob in objects if not ob.get(CONVERTED)]
        if any(ob.library or (ob.data and ob.data.library) for ob in objects):
            raise RuntimeError('Make linked objects and their data local before converting the scene')
        if self.top_level_bsps:
            self.prepare_top_level_bsps()
        if objects and (convert_scale or convert_forward):
            self.transform_geometry(objects, convert_scale, convert_forward)
        source_bsps = self.bsp_sources(objects) if not self.is_model else {}
        converted_bsps = {}
        parents = {ob.parent for ob in objects if ob.parent is not None}
        converted = []
        constraints = []
        for ob in objects:
            start = len(converted)
            bsp = source_bsps.get(ob)
            if ob.type == 'ARMATURE':
                if ob.data.users > 1:
                    ob.data = ob.data.copy()
                for bone in ob.data.bones:
                    if bone.ass_jms.name_override.strip():
                        bone.name = bone.ass_jms.name_override.strip()
                converted.append(ob)
            elif ob.rigid_body_constraint and ob.name.startswith('$'):
                constraints.append((ob, bsp))
            elif ob.type == 'MESH' and ob.data.ass_jms.XREF_path:
                from ..tools.importer import XREF
                source = ob.data.ass_jms
                xref = XREF(ob.name, source.XREF_path, source.XREF_name)
                marker = self.marker(ob)
                marker.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                path, fallback = self.owner._resolve_xref_tag_path(xref)
                marker.nwo.marker_game_instance_tag_name = path or fallback
                converted.append(marker)
            elif ob.name.lower().startswith(('frame_', 'frame ', 'bip_', 'bip ', 'b_', 'b ')):
                frame = self.marker(ob)
                frame.nwo.is_frame = True
                converted.append(frame)
            elif ob.name.startswith('#'):
                converted.append(self.marker(ob))
            elif ob.type == 'MESH':
                converted.extend(self.mesh(ob))
            elif ob.type == 'EMPTY':
                ob.nwo.is_frame = ob in parents
                if ob.ass_jms.name_override.strip():
                    ob.name = ob.ass_jms.name_override.strip()
                converted.append(ob)
            elif ob.type == 'LIGHT':
                self.light(ob)
                converted.append(ob)
            if not self.is_model:
                for result in converted[start:]:
                    converted_bsps[result] = bsp
        for ob, bsp in constraints:
            self.constraint(ob)
            converted.append(ob)
            if not self.is_model:
                converted_bsps[ob] = bsp
        if not self.is_model:
            self.assign_bsps(converted, converted_bsps)
        # Resolve proxies after the parent's data has been split/copied.
        for ob in converted:
            if (not self.is_model and ob.type == 'MESH' and ob.name.startswith('@')
                    and ob.parent and ob.parent.type == 'MESH' and ob.parent.name.startswith('%')
                    and ob.parent in converted):
                ob.nwo.proxy_type = 'collision'
                ob.parent.data.nwo.proxy_collision = ob
                # Keep the object in the scene and editable, but export via its parent.
                ob.nwo.export_this = False
            ob[CONVERTED] = True
        # Type prefixes belong to the source names; name overrides affect export
        # names only, and must not turn a #marker into an ordinary render mesh.
        for ob in converted:
            if ob.type != 'EMPTY' and ob.ass_jms.name_override.strip():
                ob.name = ob.ass_jms.name_override.strip().lstrip('#')
        return len(converted)

    def transform_geometry(self, objects, convert_scale, convert_forward):
        context = self.owner.context
        scene_nwo = self.owner.scene_nwo
        factor = 0.03048 if convert_scale and scene_nwo.scale == 'blender' else 1.0
        forward = scene_nwo.forward_direction if convert_forward else 'x'
        rotation = utils.rotation_diff_from_forward('x', forward)
        # Source property distances, like the geometry, are always Halo units.
        if convert_scale:
            self.owner.scale_factor = factor
        if factor == 1.0 and not rotation:
            return
        targets = set(objects)
        # Transforming shared data must not resize unselected objects or objects
        # in other scenes. Preserve sharing within this conversion batch.
        copies = {}
        for ob in objects:
            if ob.data and ob.data.users > 1:
                source = ob.data
                if source not in copies:
                    copies[source] = source.copy()
                ob.data = copies[source]
        context.view_layer.update()
        outside_children = {ob: ob.matrix_world.copy() for ob in bpy.data.objects
                            if ob not in targets and ob.parent in targets}
        selection = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            utils.transform_scene(context, factor, rotation, 'x', forward,
                                  keep_marker_axis=False, objects=objects, actions=[])
        finally:
            context.view_layer.update()
            for ob, matrix in outside_children.items():
                ob.matrix_world = matrix
            utils.deselect_all_objects()
            for ob in selection:
                ob.select_set(True)
            context.view_layer.objects.active = active

    def marker(self, ob):
        name = (ob.ass_jms.name_override.strip() or ob.name).lstrip('#')
        region = ob.ass_jms.marker_region
        permutation = None
        match = re.match(r'^\(([^)]+)\)(.*)', name)
        if match:
            region, permutation, _ = region_definition(match[1])
            name = match[2]
        if ob.type == 'MESH':
            active = ob.data.active_region
            if 0 <= active < len(ob.data.region_list):
                region, permutation, _ = region_definition(ob.data.region_list[active].name)
            from ..tools.mesh_to_marker import convert_to_marker
            original = ob
            ob = convert_to_marker(original)
            utils.copy_bl_props(original.ass_jms, ob.ass_jms)
            bpy.data.objects.remove(original, do_unlink=True)
        ob.name = name
        ob.empty_display_type = 'ARROWS'
        if self.is_model and region:
            self.owner._ensure_region_entry(region, utils.SetType.MODEL)
            ob.nwo.region_name = region
            ob.nwo.marker_uses_regions = True
        if self.is_model and permutation:
            self.owner._ensure_permutation_entry(permutation, utils.SetType.MODEL)
            ob.nwo.marker_permutation_type = 'include'
            ob.nwo.marker_permutations.clear()
            ob.nwo.marker_permutations.add().name = permutation
        for prefix, kind in (('fx', 'effects'), ('target', 'target'), ('garbage', 'garbage'), ('hint', 'hint')):
            if name.startswith(prefix):
                ob.nwo.marker_type = '_connected_geometry_marker_type_' + kind
                break
        if name.startswith('target'):
            ob.empty_display_type = 'SPHERE'
        return ob

    def kind(self, ob, props):
        if ob.name.startswith('@'):
            return 'collision'
        if ob.name.startswith('$'):
            return 'physics'
        if ob.name.startswith('~') and not self.is_model:
            return 'water_physics'
        if ob.name.startswith('%') and self.is_model:
            return 'io'
        if props and props.mesh_type != 'default':
            return props.mesh_type
        return 'instance' if ob.name.startswith('%') else 'default'

    def mesh(self, ob):
        source = ob.data
        materials = [slot.material for slot in ob.material_slots]
        props = [self.props(material) for material in materials]
        regions = getattr(source, 'region_list', ())
        region_attr = source.attributes.get('Region Assignment')
        groups = defaultdict(list)
        for face in source.polygons:
            prop = props[face.material_index] if face.material_index < len(props) else None
            kind = self.kind(ob, prop)
            definition = ('default', 'default', 'L5')
            if self.is_model and regions:
                index = region_attr.data[face.index].value - 1 if region_attr else 0
                if 0 <= index < len(regions):
                    definition = region_definition(regions[index].name)
            policy = tuple(getattr(prop, name, False) for name in PORTAL_POLICIES) if kind == 'portal' else ()
            groups[(kind, definition, policy)].append(face.index)
        if not groups:
            groups[(self.kind(ob, None), ('default', 'default', 'L5'), ())] = []

        # Work on private meshes even for Selected Only. Copies also preserve UVs,
        # weights, source region attributes, and existing Foundry face properties.
        results = [ob]
        for _ in range(len(groups) - 1):
            copy = ob.copy()
            for collection in ob.users_collection:
                collection.objects.link(copy)
            results.append(copy)
        for result, ((kind, definition, _), faces) in zip(results, groups.items()):
            result.data = source.copy()
            if len(groups) > 1:
                self.keep_faces(result.data, set(faces))
            mesh_type, _ = self.owner.mesh_and_material(kind, self.is_model)
            result.data.nwo.mesh_type = mesh_type
            if self.is_model:
                region, permutation, lod = definition
                self.owner._ensure_region_entry(region, utils.SetType.MODEL)
                self.owner._ensure_permutation_entry(permutation, utils.SetType.MODEL)
                result.nwo.region_name, result.nwo.permutation_name = region, permutation
                result.nwo.mesh_lod = lod
            if result.name.startswith('%'):
                self.owner.set_poop_policies(result)
            if kind == 'io':
                result.nwo.marker_uses_regions = True
                result.nwo.marker_permutation_type = 'include'
                result.nwo.marker_permutations.clear()
                result.nwo.marker_permutations.add().name = result.nwo.permutation_name
            elif kind == 'physics':
                primitive = {'CAPSULES': 'pill', 'SPHERE': 'sphere', 'BOX': 'box'}.get(source.ass_jms.Object_Type, 'none')
                result.nwo.mesh_primitive_type = '_connected_geometry_primitive_type_' + primitive
            elif kind == 'seam':
                result.nwo.seam_back_manual = True
            if mesh_type == '_connected_geometry_mesh_type_structure':
                result.nwo.proxy_instance = True
            if kind in {'soft_ceiling', 'soft_kill', 'slip_surface'}:
                result.data.nwo['boundary_surface_type'] = ('soft_ceiling', 'soft_kill', 'slip_surface').index(kind)
            indices = np.empty(len(result.data.polygons), dtype=np.int32)
            result.data.polygons.foreach_get('material_index', indices)
            for index, prop in enumerate(props):
                mask = indices == index
                if prop is None or not mask.any():
                    continue
                self.owner._apply_jms_material_props(result.data, result.nwo, prop, mask,
                                                     apply_object_props=kind == 'portal')
                if prop.ignore_default_resolution and face_prop_game_supported('lightmap_ignore_default_resolution_scale', self.game):
                    utils.add_face_prop(result.data, 'lightmap_ignore_default_resolution_scale', mask)
                if self.is_model and kind in {'collision', 'physics'}:
                    utils.add_face_prop(result.data, 'global_material', mask).global_material = utils.base_material_name(prop.material.name, True)
                material = self.material(materials[index], prop)
                result.material_slots[index].link = 'DATA'
                result.material_slots[index].material = material
            if kind == 'collision' and not self.is_model:
                # Object-level @ geometry is collision-only even if its shader
                # has no suffix. Existing sphere-only masks retain precedence.
                utils.add_face_prop(result.data, 'face_mode').face_mode = 'collision_only'
            utils.consolidate_face_attributes(result.data, preserve_special_faces=self.game == 'halo1')
        return results

    @staticmethod
    def keep_faces(mesh, keep):
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            utils.save_loop_normals(bm, mesh)
            bmesh.ops.delete(bm, geom=[face for face in bm.faces if face.index not in keep], context='FACES')
            bm.to_mesh(mesh)
        finally:
            bm.free()
        utils.apply_loop_normals(mesh)

    def material(self, source, props):
        if source in self.converted_materials:
            return self.converted_materials[source]
        material = source
        # Face flags belong to Foundry properties, not the exported shader name.
        name = utils.base_material_name(props.material.name, True).lower() or 'default'
        if props.portal_exact:
            name = '+exactportal'
        shader_emissive = self.game in {'halo1', 'halo2'} and props.emissive_power
        if name != source.name or props.portal_exact or shader_emissive:
            material = source.copy()
            material.name = name
            # A private copy may acquire Blender's .001 suffix. Keep the source
            # shader identity without editing materials used by unselected objects.
            material['foundry_legacy_shader_name'] = name
            if props.portal_exact:
                material.nwo['shader_path'] = ''
            if shader_emissive:
                # H1/H2 power and color belong to the shader. H2 additionally
                # has a per-face power multiplier, applied above.
                prop = material.nwo.material_props.add()
                prop.type = 'emissive'
                prop.material_lighting_emissive_power = props.emissive_power
                prop.material_lighting_emissive_color = props.emissive_color
                prop.material_lighting_emissive_quality = props.emissive_quality
                prop.material_lighting_emissive_per_unit = props.emissive_per_unit
                prop.material_lighting_emissive_focus = props.emissive_focus
                prop.material_lighting_attenuation_falloff = props.emissive_attenuation_falloff
                prop.material_lighting_attenuation_cutoff = props.emissive_attenuation_cutoff
        self.converted_materials[source] = material
        return material

    def light(self, ob):
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        data = ob.data
        source = data.halo_light
        data.nwo.light_intensity = data.energy
        data.nwo.light_shape = '_connected_geometry_light_shape_' + ('rectangle' if source.light_cone_shape == '0' else 'circle')
        data.nwo.light_aspect = source.aspect_ratio
        if data.type == 'SPOT':
            data.spot_size, data.spot_blend = source.spot_size, source.spot_blend
        elif data.type == 'AREA':
            data.shape = 'RECTANGLE' if source.light_cone_shape == '0' else 'DISK'
            if data.shape == 'RECTANGLE':
                data.size_y = data.size / source.aspect_ratio
        # ASS distances are Max units; Foundry stores distances in scene units.
        if source.use_near_atten:
            data.shadow_soft_size = source.near_atten_end * self.owner.scale_factor
            self.warnings.add(f'{ob.name}: near attenuation is represented by light radius; Foundry has no near-attenuation export fields')
        data.nwo.light_far_attenuation_start = source.far_atten_start * self.owner.scale_factor if source.use_far_atten else 0
        data.nwo.light_far_attenuation_end = source.far_atten_end * self.owner.scale_factor if source.use_far_atten else 0

    def constraint(self, ob):
        source = ob.rigid_body_constraint
        nwo = ob.nwo
        if source.type not in {'HINGE', 'GENERIC'}:
            nwo.export_this = False
            self.warnings.add(f'{ob.name}: unsupported {source.type} constraint retained and excluded from export')
            return
        nwo.marker_type = '_connected_geometry_marker_type_physics_constraint'
        nwo.physics_constraint_parent, nwo.physics_constraint_child = source.object1, source.object2
        if source.type == 'HINGE':
            nwo.physics_constraint_type = '_connected_geometry_marker_type_physics_hinge_constraint'
            nwo.physics_constraint_uses_limits = source.use_limit_ang_z
            nwo.hinge_constraint_minimum, nwo.hinge_constraint_maximum = source.limit_ang_z_lower, source.limit_ang_z_upper
        elif source.type == 'GENERIC':
            nwo.physics_constraint_type = '_connected_geometry_marker_type_physics_socket_constraint'
            nwo.physics_constraint_uses_limits = source.use_limit_ang_x or source.use_limit_ang_y or source.use_limit_ang_z
            if source.use_limit_ang_x:
                nwo.twist_constraint_start, nwo.twist_constraint_end = source.limit_ang_x_lower, source.limit_ang_x_upper
            if source.use_limit_ang_y:
                nwo.cone_angle = source.limit_ang_y_upper
            if source.use_limit_ang_z:
                nwo.plane_constraint_minimum, nwo.plane_constraint_maximum = source.limit_ang_z_lower, source.limit_ang_z_upper
