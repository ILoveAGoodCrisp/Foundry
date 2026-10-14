"""Reconstruct editable Foundry objects from detached Granny source data."""
from .. import face_attributes
import ast
from collections import defaultdict
import hashlib
import json
from math import isclose, isfinite, radians
from pathlib import Path
import re
from types import SimpleNamespace

import bpy
from ..uv_channels import store_uv_w
from mathutils import Matrix, Quaternion, Vector
import numpy as np

from .. import import_transform, utils
from ..export import export_info as enums
from ..granny_import import GrannyReader, UnsupportedGrannyFormat
from ..granny_import.native import NativeDecompressor, supported_platform


def properties(props):
    """Flatten the property containers used by the Max/Maya exporters."""
    result = {}
    for key, value in props.items():
        if key.startswith('bungie_') and isinstance(value, dict) and not value:
            # Max also emits empty containers for per-face custom attributes.
            # They must not replace the scalar defaults in bungie_attribs_mesh.
            continue
        if isinstance(value, dict) and (key.startswith('bungie_attribs_') or key in {
                'MaxProperties', 'MayaProperties', 'UserDefinedProperties',
                'bungie_export_enum_tables', 'bungie_export_string_tables',
                'bungie_export_file_header', 'bungie_export_flag', 'materialManager_attrib'}):
            result.update(properties(value))
        else:
            result[key] = value
    return result


def light_attenuation(props):
    """Find usable distance falloff, preferring Halo values over DCC metadata."""
    def normalized(key):
        return re.sub(r'[^a-z0-9]', '', key.casefold())

    def number(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if isfinite(value) and value >= 0 else None

    halo = {normalized(key): value for key, value in props.items() if key.startswith('bungie_light_')}
    for key, value in halo.items():
        if 'inversesquare' in key or key == 'bungielightphysicallycorrect':
            if str(value).strip().casefold() in {'true', 'yes', 'on'} or (number(value) or 0) > 0:
                return None

    def bounds(values, pairs):
        for start_key, end_key in pairs:
            end = number(values.get(end_key))
            if end is not None and end > 0:
                start = number(values.get(start_key)) or 0
                return min(start, end), end
        return None

    result = bounds(halo, [('bungielightfarattenuationstart', 'bungielightfarattenuationend')])
    if result is not None:
        return result

    # Restrict generic names to light-related containers; a mesh's attenuation
    # or camera clipping distances must not become a light's cutoff.
    def containers(values, light_related=False):
        if light_related:
            yield {normalized(key): value for key, value in values.items() if not isinstance(value, dict)}
        for key, value in values.items():
            if isinstance(value, dict):
                yield from containers(value, light_related or 'light' in normalized(key))
    pairs = [('farattenuationstart', 'farattenuationend'),
             ('lightfarattenuationstart', 'lightfarattenuationend'),
             ('distanceattenuationstart', 'distanceattenuationend'),
             ('attenuationstart', 'attenuationend'),
             ('falloffstart', 'falloffend'), ('attenuationnearradius', 'attenuationfarradius')]
    for values in containers(props):
        result = bounds(values, pairs)
        if result is not None:
            return result
    # Some exporters flatten their light-specific fields into ExtendedData.
    return bounds({normalized(key): value for key, value in props.items()
                   if 'light' in normalized(key) and not key.startswith('bungie_')},
                  [('lightfarattenuationstart', 'lightfarattenuationend'),
                   ('lightattenuationstart', 'lightattenuationend')])


def array_literal(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    text = str(value).strip()
    if text.startswith('#(') and text.endswith(')'):
        text = text[2:-1]
    try:
        return list(ast.literal_eval('[' + text + ']'))
    except (SyntaxError, ValueError):
        return []


def numeric(value):
    return float(value) if isinstance(value, str) else value


def has_value(value):
    """Max can emit an unset attribute as an empty or whitespace-only string."""
    return value is not None and not (isinstance(value, str) and not value.strip())


def finite_value(value):
    """Face annotations may hold scalar, vector or nested optional values."""
    if isinstance(value, dict):
        return all(finite_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite_value(item) for item in value)
    return not isinstance(value, (float, np.floating)) or isfinite(value)


def vector_value(value):
    return tuple(float(v) for v in value.replace(',', ' ').split()) if isinstance(value, str) else tuple(value)


def canonical_name(name):
    return utils.remove_node_prefix(name).casefold()


def gr2_scene_settings(owner):
    """Bypass scene units for raw-scale imports without changing scene properties."""
    scene = owner.scene_nwo
    if getattr(owner, 'gr2_convert_scale', True):
        return scene
    return SimpleNamespace(scale='max', forward_direction=scene.forward_direction,
                           asset_type=getattr(scene, 'asset_type', ''))


class GR2Importer:
    def __init__(self, owner, path, data, *, parent_collection=None, tag_armature=None,
                 geometry_only=False, allowed_region_permutations=(), shader_paths=None,
                 default_mesh_type=None, import_markers=True, import_geometry=True, render_only=False,
                 permutation=None, region=None, asset_type=None, regions=(), global_materials=()):
        self.owner, self.path, self.data = owner, Path(path), data
        self.scene_nwo = gr2_scene_settings(owner)
        self.tag_armature = tag_armature
        self.geometry_only = geometry_only
        self.allowed = set(allowed_region_permutations or ())
        self.shader_paths = shader_paths or {}
        self.default_mesh_type = default_mesh_type
        self.render_only = render_only
        self.region = region
        self.is_structure = (default_mesh_type == '_connected_geometry_mesh_type_structure'
                             or (asset_type or getattr(self.scene_nwo, 'asset_type', '')) in {'scenario', 'prefab', 'resource', 'multi_prefab'}
                             or (asset_type is None and re.search(r'(?:^|_)structure(?:_|$)', self.path.stem, re.I)))
        self.import_markers, self.import_geometry = import_markers, import_geometry
        self.collection = bpy.data.collections.new(self.path.stem)
        self.collection.hide_render = default_mesh_type in {'_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics'}
        (parent_collection or owner.scene_collection).children.link(self.collection)
        self.objects, self.materials = [], {}
        self.created_materials = []
        self.images, self.created_images = {}, []
        self.unmapped_enums = {}
        self.unmapped_face_keys = set()
        self.armature = tag_armature
        self.armatures = []
        self.object_roots = set()
        self.export_info = {}
        for skeleton in data['skeletons'].values():
            if skeleton['name'].casefold() == 'bungieexportinfo' and skeleton['bones']:
                self.export_info.update(properties(skeleton['bones'][0]['props']))
        self.enum_tables = {}
        for key, value in self.export_info.items():
            if key.endswith('_enum_names'):
                values = array_literal(self.export_info.get(key.replace('_names', '_values'), ''))
                self.enum_tables[key[:-11]] = dict(zip((int(v) for v in values), array_literal(value)))
        self.regions = self.name_table('connected_geometry_regions_table', regions)
        self.global_materials = self.name_table('connected_geometry_global_material_table', global_materials)
        self.missing_table_entries = {'region': set(), 'global_material': set()}
        match = re.search(r'_(?:render|collision|physics|structure|design)_(.+)$', self.path.stem, re.I)
        self.permutation = permutation if permutation is not None else match[1] if match else 'default'
        self.collection['gr2_source'] = str(self.path)
        if data.get('source_basis'):
            self.collection['gr2_source_basis'] = json.dumps(data['source_basis'])
        self.collection['gr2_export_info'] = json.dumps(self.export_info)
        self.save_name_tables()

    def name_table(self, key, fallback):
        # Sidecar names can fill holes in an incomplete GR2 header. Native
        # tables can also use explicit, non-contiguous IDs rather than offsets.
        table = dict(fallback) if isinstance(fallback, dict) else dict(enumerate(fallback))
        names = array_literal(self.export_info.get(key + '_enum_names', ''))
        values = array_literal(self.export_info.get(key + '_enum_values', ''))
        table.update(zip((int(value) for value in values) if values else range(len(names)), names))
        return table

    def save_name_tables(self):
        self.collection['gr2_name_tables'] = json.dumps({'region': self.regions, 'global_material': self.global_materials})

    def enum(self, kind, value, cls=None, prefix='', *, default=None):
        if not has_value(value):
            return default
        if isinstance(value, str) and value.startswith('_'):
            return value if prefix else value.rsplit(kind + '_', 1)[-1]
        if kind == 'object_type' and value == 'other':
            return 'none'
        try:
            number = int(numeric(value))
        except (TypeError, ValueError, OverflowError):
            return self.unmapped_enum(kind, value, default)
        candidates = [f'e_connected_geometry_{kind}', f'e_connected_material_{kind}', f'e_connected_{kind}']
        for key in candidates:
            name = self.enum_tables.get(key, {}).get(number)
            if name is not None:
                return name if prefix else name.rsplit(kind + '_', 1)[-1]
        if cls is None:
            return str(value)
        try:
            name = cls(number).name
        except ValueError:
            return self.unmapped_enum(kind, value, default)
        return prefix + name if prefix else name

    def unmapped_enum(self, kind, value, default):
        key = json.dumps([kind, value])
        if key not in self.unmapped_enums:
            self.unmapped_enums[key] = dict(kind=kind, value=value)
            self.collection['gr2_unmapped_enums'] = json.dumps(list(self.unmapped_enums.values()))
            utils.print_warning(f'{self.path.name}: unknown GR2 {kind} value {value!r}; retained as metadata')
        return default

    def table_name(self, value, table):
        if isinstance(value, str):
            return value
        index = int(value)
        if index not in table:
            kind = 'region' if table is self.regions else 'global_material'
            name = f'gr2_{kind}_{index}'
            while name in table.values():
                name += '_missing'
            table[index] = name
            self.missing_table_entries[kind].add(index)
            self.save_name_tables()
            utils.print_warning(f'{self.path.name}: missing {kind} name for GR2 ID {index}; using {name}')
        return table[index]

    def object(self, name, data=None):
        ob = bpy.data.objects.new(name, data)
        self.collection.objects.link(ob)
        self.objects.append(ob)
        return ob

    def set_property(self, target, name, value):
        field = target.bl_rna.properties.get(name)
        if field is None or field.is_readonly:
            return
        if field.type != 'STRING' and not has_value(value):
            return
        if field.type == 'BOOLEAN':
            value = bool(numeric(value))
        elif field.type == 'INT':
            value = int(numeric(value))
        elif field.type == 'FLOAT':
            value = vector_value(value) if field.is_array else float(value)
        elif field.type == 'STRING':
            value = str(value)
        elif field.type == 'ENUM':
            value = str(value)
        try:
            setattr(target, name, value)
        except (TypeError, ValueError):
            utils.print_warning(f'{self.path.name}: could not apply GR2 property {name}={value!r}')

    def restore_object_props(self, ob, props):
        props = properties(props)
        ob['gr2_properties'] = json.dumps(props)
        mapping = {
            'mesh_poop_pathfinding': 'poop_pathfinding', 'mesh_poop_lighting': 'poop_lighting',
            'mesh_poop_imposter_policy': 'poop_imposter_policy',
            'mesh_poop_excluded_from_lightprobes': 'poop_excluded_from_lightprobe',
            'mesh_poop_is_render_only': 'poop_render_only',
            'mesh_poop_streamingpriority': 'poop_streaming_priority',
            'mesh_poop_disallow_object_lighting_samples': 'poop_disallow_lighting_samples',
            'marker_game_instance_variant_name': 'marker_game_instance_tag_variant_name',
            'marker_pathfinding_sphere_vehicle_only': 'marker_pathfinding_sphere_vehicle',
            'marker_pathfinding_sphere_remains_when_open': 'pathfinding_sphere_remains_when_open',
            'marker_pathfinding_sphere_with_sectors': 'pathfinding_sphere_with_sectors',
            'mesh_seam_associated_bsp': 'seam_back',
            'face_region': 'region_name', 'marker_region': 'region_name',
            'face_global_material': 'global_material', 'mesh_global_material': 'global_material',
        }
        enum_fields = {
            'mesh_poop_lighting': ('poop_lighting', enums.PoopLighting),
            'mesh_poop_pathfinding': ('poop_instance_pathfinding_policy', enums.PoopInstancePathfindingPolicy),
            'mesh_poop_imposter_policy': ('poop_instance_imposter_policy', enums.PoopInstanceImposterPolicy),
            'mesh_poop_collision_type': ('poop_collision_type', enums.PoopCollisionType),
            'mesh_boundary_surface_type': ('boundary_surface_type', enums.BoundarySurfaceType),
            'mesh_obb_type': ('mesh_obb_volume_type', enums.MeshObbVolumeType),
        }
        for key, value in props.items():
            if not key.startswith('bungie_'):
                continue
            name = key[7:]
            if name in {'object_type', 'mesh_type'}:
                continue
            target = ob.nwo
            dest = mapping.get(name, name.removeprefix('mesh_'))
            if name in enum_fields:
                if ob.type != 'MESH' and name in {'mesh_boundary_surface_type', 'mesh_obb_type'}:
                    continue
                kind, cls = enum_fields[name]
                value = self.enum(kind, value, cls)
                if value is None:
                    continue
                if name == 'mesh_poop_imposter_policy' and value == 'none':
                    value = 'never'
                if name == 'mesh_boundary_surface_type':
                    target, dest, value = ob.data.nwo, 'boundary_surface_type', value.upper()
                elif name == 'mesh_obb_type':
                    target, dest = ob.data.nwo, 'obb_volume_type'
                    value = 'STREAMING_VOLUME' if value == 'streamingvolume' else 'LIGHTMAP_EXCLUSION'
            if name in {'face_region', 'marker_region'}:
                value = self.table_name(value, self.regions)
                utils.add_region(value)
            elif name in {'face_global_material', 'mesh_global_material'}:
                value = self.table_name(value, self.global_materials)
            if name == 'marker_all_regions':
                dest, value = 'marker_uses_regions', not bool(numeric(value))
            if name in {'mesh_water_volume_depth', 'mesh_poop_imposter_transition_distance'}:
                value = float(value) / .3280839895013123
            if name == 'mesh_water_volume_flow_direction':
                value = radians(float(value))
            if hasattr(target, dest):
                self.set_property(target, dest, value)
        if ob.type == 'MESH':
            mesh_type = self.enum('mesh_type', props.get('bungie_mesh_type'), enums.MeshType,
                                  '_connected_geometry_mesh_type_',
                                  default=self.default_mesh_type or '_connected_geometry_mesh_type_default')
            if (mesh_type == '_connected_geometry_mesh_type_default' and self.default_mesh_type in {
                    '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics',
                    '_connected_geometry_mesh_type_decorator'}):
                mesh_type = self.default_mesh_type
            if mesh_type in {'_connected_geometry_mesh_type_poop_collision', '_connected_geometry_mesh_type_poop_physics'}:
                mesh_type = '_connected_geometry_mesh_type_default'
            if self.is_structure:
                # Foundry authors structure as "structure", and instances as
                # "default"; the GR2 enum uses "default" and "poop" respectively.
                mesh_type = {'_connected_geometry_mesh_type_default': '_connected_geometry_mesh_type_structure',
                             '_connected_geometry_mesh_type_poop': '_connected_geometry_mesh_type_default'}.get(mesh_type, mesh_type)
            if mesh_type == '_connected_geometry_mesh_type_poop':
                mesh_type = '_connected_geometry_mesh_type_default'
            self.set_property(ob.data.nwo, 'mesh_type', mesh_type)
        if has_value(props.get('bungie_marker_type')):
            marker_type = self.enum('marker_type', props['bungie_marker_type'], prefix='_connected_geometry_marker_type_')
            if marker_type in {'_connected_geometry_marker_type_physics_hinge_constraint', '_connected_geometry_marker_type_physics_socket_constraint'}:
                self.set_property(ob.nwo, 'physics_constraint_type', marker_type)
                marker_type = '_connected_geometry_marker_type_physics_constraint'
            self.set_property(ob.nwo, 'marker_type', marker_type)
            if props.get('bungie_marker_model_group'):
                ob.name = str(props['bungie_marker_model_group'])
        if 'bungie_mesh_poop_cinema_only' in props or 'bungie_mesh_poop_exclude_from_cinema' in props:
            cinema = 'only' if bool(numeric(props.get('bungie_mesh_poop_cinema_only', 0))) else (
                'exclude' if bool(numeric(props.get('bungie_mesh_poop_exclude_from_cinema', 0))) else 'default')
            self.set_property(ob.nwo, 'poop_cinematic_properties', '_connected_geometry_poop_cinema_' + cinema)
        if hasattr(ob.nwo, 'marker_permutations'):
            for mode in ('include', 'exclude'):
                value = props.get(f'bungie_marker_{mode}_from_permutations')
                if value is None:
                    value = props.get(f'bungie_marker_{mode}_in_permutations')
                if value is not None:
                    if isinstance(value, str):
                        try:
                            names = json.loads(value)
                        except ValueError:
                            names = array_literal(value)
                    else:
                        names = value
                    ob.nwo.marker_permutation_type = mode
                    for name in names:
                        ob.nwo.marker_permutations.add().name = str(name)
        self.set_property(ob.nwo, 'permutation_name', self.permutation)
        utils.add_permutation(self.permutation)

    def face_property(self, mesh, key, value, mask):
        if not has_value(value):
            return True
        simple = {'bungie_ladder': 'ladder', 'bungie_slip_surface': 'slip_surface',
                  'bungie_decal_offset': 'decal_offset', 'bungie_no_shadow': 'no_shadow',
                  'bungie_precise_position': 'precise_position', 'bungie_no_lightmap': 'no_lightmap',
                  'bungie_invisible_to_pvs': 'no_pvs', 'bungie_mesh_use_uncompressed_verts': 'uncompressed'}
        if key in simple:
            name = simple[key]
            self.set_property(utils.add_face_prop(mesh, name, mask), name, bool(numeric(value)))
        elif key == 'bungie_face_sides':
            sides = self.enum('face_sides', value, enums.FaceSides)
            if sides is None:
                self.unmapped_face_keys.add(key)
                return True
            if sides.startswith(('two_sided', 'mirror', 'keep')):
                prop = utils.add_face_prop(mesh, 'face_sides', mask)
                prop.face_sides_type = sides.split('_transparent')[0] if not sides.startswith('two_sided') else 'two_sided'
            if 'transparent' in sides:
                utils.add_face_prop(mesh, 'transparent', mask)
        elif key == 'bungie_face_type':
            name = self.enum('face_type', value, enums.FaceType)
            if name is None:
                self.unmapped_face_keys.add(key)
                return True
            if name in {'normal', 'sky', 'seam_sealer'}:
                attribute = mesh.attributes.get(key) or mesh.attributes.new(name=key, type='INT', domain='FACE')
                values = np.array([item.value for item in attribute.data], dtype=np.int32)
                values[np.ones(len(values), dtype=bool) if mask is None else mask.astype(bool)] = enums.FaceType[name].value
                attribute.data.foreach_set('value', values)
        elif key in {'bungie_face_region', 'bungie_face_global_material', 'bungie_mesh_global_material'}:
            name, table = ('region', self.regions) if key.endswith('region') else ('global_material', self.global_materials)
            value = self.table_name(value, table)
            if value == 'default':
                return True
            self.set_property(utils.add_face_prop(mesh, name, mask), name, value)
            if name == 'region':
                utils.add_region(value)
        else:
            enum_fields = {
                'bungie_face_mode': ('face_mode', 'face_mode', enums.FaceMode),
                'bungie_face_draw_distance': ('draw_distance', 'face_draw_distance', enums.FaceDrawDistance),
                'bungie_mesh_tessellation_density': ('mesh_tessellation_density', 'mesh_tessellation_density', enums.MeshTessellationDensity),
                'bungie_mesh_additional_compression': ('additional_compression', 'mesh_additional_compression', enums.AdditionalCompression),
                'bungie_lightmap_type': ('lightmap_type', 'lightmap_type', enums.LightmapType),
            }
            if key in enum_fields:
                name, kind, cls = enum_fields[key]
                value = self.enum(kind, value, cls)
                if value is None:
                    self.unmapped_face_keys.add(key)
                    return True
                if (name == 'mesh_tessellation_density' and value == 'none'
                        or name == 'additional_compression' and value == 'default'):
                    # Foundry represents these defaults by absence of an override.
                    return True
                if name == 'mesh_tessellation_density' and value in {'4x', '9x', '36x'}:
                    value = '_' + value
                self.set_property(utils.add_face_prop(mesh, name, mask), name, value)
            elif key.startswith('bungie_lightmap_'):
                name = key[7:]
                if name in {'lightmap_additive_transparency', 'lightmap_translucency_tint_color'}:
                    value = tuple(v / 255 for v in vector_value(value))
                elif name == 'lightmap_resolution_scale' and isinstance(value, (float, np.floating)):
                    # Max can store Reach size-class IDs in Real32 annotations,
                    # including small rounding errors around integer values.
                    if isclose(value, round(value), abs_tol=1e-6):
                        value = round(value)
                self.set_property(utils.add_face_prop(mesh, name, mask), name, value)
            else:
                return False
        return True

    def raw_face_annotation(self, mesh, key, records, selected):
        """Keep unmapped numeric annotations in the exporter's native attributes."""
        values = [next(iter(record.values())) if len(record) == 1 else list(record.values()) for record in records]
        try:
            array = np.asarray(values)[selected]
            if array.dtype.kind not in 'fiu':
                return
            # Invalid originals are retained separately by restore_faces.
            # Keep usable components without exporting NaN/Infinity attributes.
            if array.dtype.kind == 'f':
                array[~np.isfinite(array)] = 0
            if array.ndim == 1:
                kind, field = ('FLOAT', 'value') if array.dtype.kind == 'f' else ('INT', 'value')
            elif array.ndim == 2 and array.shape[1] in {3, 4}:
                kind, field = ('FLOAT_VECTOR', 'vector') if array.shape[1] == 3 else ('FLOAT_COLOR', 'color')
                if array.shape[1] == 4:
                    array = array[:, [1, 2, 3, 0]]  # Granny ARGB to Blender RGBA.
            else:
                return
            attribute = mesh.attributes.new(name=key, type=kind, domain='FACE')
            attribute.data.foreach_set(field, array.ravel())
        except (ValueError, TypeError):
            utils.print_warning(f'{self.path.name}: could not restore GR2 face annotation {key}')

    def restore_faces(self, mesh, props, annotations, selected):
        # Maya/343 exports can put whole-mesh face enums in ExtendedData under
        # exporter-specific names. Keep those originals in gr2_properties,
        # while restoring the corresponding native face property here.
        props = dict(props)
        for key, value in list(props.items()):
            match = re.fullmatch(r'face_prop_(bungie_.+)_EnumExportProperty', key)
            if match and not has_value(props.get(match[1])):
                props[match[1]] = value
        annotation_values = {
            key: [next(iter(record.values())) if len(record) == 1 else list(record.values()) for record in records]
            for key, records in annotations.items()}
        invalid_annotations = {}
        for key, values in annotation_values.items():
            invalid = [dict(face=face, source_face=int(source), value=values[source])
                       for face, source in enumerate(selected) if not finite_value(values[source])]
            if invalid:
                invalid_annotations[key] = invalid
                utils.print_warning(f'{self.path.name}: {mesh.name} has {len(invalid)} invalid {key} face values; '
                                    'using defaults and retaining originals as metadata')
        if invalid_annotations:
            mesh['gr2_invalid_face_annotations'] = json.dumps(invalid_annotations)

        def face_value(key, source):
            value = annotation_values[key][source] if key in annotation_values else props.get(key)
            if not finite_value(value):
                value = props.get(key)
            return value if finite_value(value) else None

        # Annotations carry per-face overrides; do not also add a whole-mesh
        # property for the same key (that would defeat the overrides on export).
        for key, value in props.items():
            if key not in annotations and not key.startswith('bungie_lighting_'):
                self.face_property(mesh, key, value, None)
        for key, records in annotations.items():
            if key.startswith('bungie_lighting_'):
                continue
            values = annotation_values[key]
            grouped = defaultdict(list)
            for face, source in enumerate(selected):
                value = face_value(key, source)
                grouped[json.dumps(value)].append(face)
            for serialized, faces in grouped.items():
                mask = np.zeros(len(mesh.polygons), dtype=np.int8)
                mask[faces] = 1
                if not self.face_property(mesh, key, json.loads(serialized), mask):
                    self.raw_face_annotation(mesh, key, records, selected)
                    break
            if key in self.unmapped_face_keys:
                self.raw_face_annotation(mesh, 'gr2_original_' + key, records, selected)
            if key in {'bungie_face_region', 'bungie_face_global_material', 'bungie_mesh_global_material'}:
                kind = 'region' if key.endswith('region') else 'global_material'
                if any(has_value(values[source]) and finite_value(values[source]) and not isinstance(values[source], str)
                       and int(values[source]) in self.missing_table_entries[kind]
                       for source in selected):
                    # Keep the original IDs for recovery without sending an
                    # invalid source index table back to Tool during re-export.
                    self.raw_face_annotation(mesh, 'gr2_original_' + key, records, selected)
        emissive_keys = {key for key in props.keys() | annotations.keys() if key.startswith('bungie_lighting_')}
        if emissive_keys:
            grouped = defaultdict(list)
            for face, source in enumerate(selected):
                values = {key: value for key in sorted(emissive_keys)
                          if has_value(value := face_value(key, source))}
                if not values:
                    continue
                grouped[json.dumps(values)].append(face)
            for serialized, faces in grouped.items():
                values = json.loads(serialized)
                mask = np.zeros(len(mesh.polygons), dtype=np.int8)
                mask[faces] = 1
                prop = utils.add_face_prop(mesh, 'emissive', mask)
                for key, value in values.items():
                    name = 'material_' + key[7:]
                    if key == 'bungie_lighting_emissive_color':
                        color = vector_value(value)
                        color = color[1:] if len(color) == 4 else color
                        value = tuple((v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4) for v in color)
                    elif key == 'bungie_lighting_emissive_focus':
                        value = radians((1 - float(value)) * 180)
                    elif key in {'bungie_lighting_attenuation_cutoff', 'bungie_lighting_attenuation_falloff'}:
                        value = float(value) / (.3280839895013123 * (1 if getattr(self.owner, 'game', 'reach') in {'halo4', 'halo2a'} else 100))
                    self.set_property(prop, name, value)

    def restore_structure_proxy(self, ob, props):
        """Auxiliary BSP geometry must not also be exported as an instance."""
        if not self.is_structure:
            return
        mesh = ob.data
        source_kind = self.enum('mesh_type', props.get('bungie_mesh_type'), enums.MeshType, default='default')
        if source_kind in {'collision', 'physics', 'poop_collision', 'poop_physics'}:
            self.set_property(ob.nwo, 'proxy_instance', False)
            return
        if mesh.nwo.mesh_type != '_connected_geometry_mesh_type_structure':
            if mesh.nwo.mesh_type != '_connected_geometry_mesh_type_default':
                self.set_property(ob.nwo, 'proxy_instance', False)
            return
        auxiliary = np.zeros(len(mesh.polygons), dtype=bool)
        face_type = mesh.attributes.get('bungie_face_type')
        if face_type is not None and face_type.domain == 'FACE' and face_type.data_type == 'INT':
            values = np.empty(len(auxiliary), dtype=np.int32)
            face_type.data.foreach_get('value', values)
            auxiliary |= np.isin(values, [enums.FaceType.sky.value, enums.FaceType.seam_sealer.value])
        for prop in mesh.nwo.face_props:
            if prop.type != 'face_mode' or prop.face_mode not in {
                    'collision_only', 'sphere_collision_only', 'shadow_only', 'lightmap_only'}:
                continue
            auxiliary |= face_attributes.mask(mesh, prop)
        # Foundry's convention materials can carry the same face semantics.
        special_slots = {i for i, material in enumerate(mesh.materials) if material is not None
                         and material.name.startswith(('+sky', '+seamsealer', '+seam'))}
        if special_slots:
            indices = np.empty(len(auxiliary), dtype=np.int32)
            mesh.polygons.foreach_get('material_index', indices)
            auxiliary |= np.isin(indices, list(special_slots))
        if len(auxiliary) and auxiliary.all():
            self.set_property(ob.nwo, 'proxy_instance', False)

    def material(self, address):
        if address in self.materials:
            return self.materials[address]
        source = self.data['materials'].get(address, dict(name='default', props={}))
        props = properties(source['props'])
        name = source['name'] or 'default'
        path = props.get('bungie_shader_path', '')
        kind = props.get('bungie_shader_type', '')
        if path and kind and not Path(path).suffix:
            path += '.' + kind
        path = path or self.shader_paths.get(utils.base_material_name(name, True).lower(), '')
        material = next((m for m in bpy.data.materials if path and m.nwo.shader_path == path), None)
        if material is None:
            material = bpy.data.materials.new(name)
            self.created_materials.append(material)
            material.nwo.shader_path = path
            material['gr2_properties'] = json.dumps(props)
            material['gr2_material_maps'] = json.dumps(source.get('maps', []))
            self.restore_material_textures(material, source)
        self.materials[address] = material
        return material

    def texture_images(self, address):
        if address in self.images:
            return self.images[address]
        source = self.data.get('textures', {}).get(address)
        images = []
        self.images[address] = images
        if source is None:
            return images
        if source.get('error'):
            utils.print_warning(f'{self.path.name}: could not extract GR2 texture {source["name"]}: {source["error"]}')
        for frame in source['images']:
            pixels = frame['pixels']
            digest = hashlib.sha256(pixels.tobytes()).hexdigest()
            # Repeated sidecar/component imports share the same packed pixels.
            image = next((image for image in bpy.data.images if image.get('gr2_pixel_hash') == digest
                          and tuple(image.size) == (source['width'], source['height'])), None)
            if image is None:
                name = Path(source['name'].replace('\\', '/')).stem or 'gr2_texture'
                if len(source['images']) > 1:
                    name += f'_{frame["index"]}'
                image = bpy.data.images.new(name, width=source['width'], height=source['height'], alpha=True)
                self.created_images.append(image)
                image.colorspace_settings.name = 'sRGB'
                image.alpha_mode = 'STRAIGHT'
                image.file_format = 'PNG'
                # Granny's first row is the top; Blender image buffers start at
                # the bottom, matching the V conversion used by imported UVs.
                image.pixels.foreach_set((pixels[::-1].astype(np.float32) / 255).ravel())
                image['gr2_source'] = str(self.path)
                image['gr2_texture_source'] = source['name']
                image['gr2_texture_properties'] = json.dumps(source.get('props', {}))
                image['gr2_texture_encoding'] = source['encoding']
                image['gr2_texture_image_index'] = frame['index']
                image['gr2_texture_mip_levels'] = frame['mip_levels']
                image['gr2_pixel_hash'] = digest
                image.pack()
                image.use_fake_user = True
            images.append(image)
        return images

    def material_texture(self, address, visited=None):
        visited = set() if visited is None else visited
        if not address or address in visited:
            return None
        visited.add(address)
        source = self.data['materials'].get(address, {})
        if source.get('texture'):
            images = self.texture_images(source['texture'])
            if images:
                return images[0]
        for mapping in source.get('maps', []):
            image = self.material_texture(mapping['material'], visited)
            if image is not None:
                return image
        return None

    def restore_material_textures(self, material, source):
        """Restore common diffuse channels through nested Granny material maps."""
        image = None
        if source.get('texture'):
            images = self.texture_images(source['texture'])
            image = images[0] if images else None
        if image is None:
            for mapping in source.get('maps', []):
                channel = re.sub(r'[^a-z0-9]', '', mapping['usage'].casefold())
                if channel in {'color', 'diffuse', 'diffusecolor', 'diffusemap', 'basecolor', 'albedo'}:
                    image = self.material_texture(mapping['material'])
                    if image is not None:
                        break
        if image is None:
            return
        material.use_nodes = True
        nodes = material.node_tree.nodes
        shader = next((node for node in nodes if node.type == 'BSDF_PRINCIPLED'), None)
        if shader is None:
            return
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = image
        texture.label = 'GR2 Diffuse'
        texture.location = (shader.location.x - 300, shader.location.y)
        material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
        material.node_tree.links.new(texture.outputs['Alpha'], shader.inputs['Alpha'])

    def bone_worlds(self, skeleton):
        worlds, visiting = {}, set()
        def world(index):
            if index in worlds:
                return worlds[index]
            if index in visiting or not 0 <= index < len(skeleton['bones']):
                raise ValueError('Invalid GR2 skeleton hierarchy')
            visiting.add(index)
            bone = skeleton['bones'][index]
            matrix = Matrix(bone['matrix'])
            if bone['parent'] != -1:
                matrix = world(bone['parent']) @ matrix
            visiting.remove(index)
            worlds[index] = matrix
            return matrix
        for i in range(len(skeleton['bones'])):
            world(i)
        return worlds

    def bone_name(self, name):
        if self.armature is None:
            return None
        if name in self.armature.data.bones:
            return name
        matches = [b.name for b in self.armature.data.bones if canonical_name(b.name) == canonical_name(name)]
        return matches[0] if len(matches) == 1 else None

    def build_armature(self, skeleton, worlds):
        bone_props = [properties(bone['props']) for bone in skeleton['bones']]
        # Generic Granny exporters have skeletons without Halo object semantics.
        # In that case the skeleton itself defines the bones to reconstruct.
        # A Halo header also identifies otherwise untagged skeleton entries as
        # object transforms. They must not become a generic armature's bones.
        has_object_types = ('e_connected_geometry_object_type' in self.enum_tables
                            or any('bungie_object_type' in props for props in bone_props))
        frames = [i for i, props in enumerate(bone_props)
                  if not has_object_types or self.enum('object_type', props.get('bungie_object_type'),
                                                      enums.ObjectType, default='none') == 'frame']
        root = next((i for i in frames if skeleton['bones'][i]['parent'] == -1 and (
            bone_props[i].get('bungie_frame_world') or canonical_name(skeleton['bones'][i]['name']) == canonical_name(skeleton['name']))), None)
        if root is not None and self.bone_name(skeleton['bones'][root]['name']) is None:
            self.object_roots.add(canonical_name(skeleton['bones'][root]['name']))
        if self.armature is not None or not frames or self.geometry_only:
            return
        arm = self.object(skeleton['name'], bpy.data.armatures.new(skeleton['name']))
        self.armature = arm
        arm['gr2_skeleton_name'] = skeleton['name']
        if root is not None:
            source = skeleton['bones'][root]
            arm.matrix_world = import_transform.object_matrix(worlds[root], self.scene_nwo)
            arm['gr2_object_root'] = source['name']
            arm['gr2_object_root_rest'] = json.dumps(np.asarray(source['matrix']).tolist())
            arm['gr2_properties'] = json.dumps(bone_props[root])
            frames.remove(root)
        inverse = arm.matrix_world.inverted_safe()
        context = self.owner.context
        utils.set_object_mode(context)
        for ob in context.selected_objects:
            ob.select_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bones = {}
            for index in frames:
                source = skeleton['bones'][index]
                bone = arm.data.edit_bones.new(source['name'])
                bone.tail = (0, max(import_transform.scale_factor(self.scene_nwo), .001), 0)
                bone.matrix = inverse @ import_transform.object_matrix(worlds[index], self.scene_nwo)
                bones[index] = bone
            for index, bone in bones.items():
                parent = skeleton['bones'][index]['parent']
                while parent != -1 and parent not in bones:
                    parent = skeleton['bones'][parent]['parent']
                if parent in bones:
                    bone.parent = bones[parent]
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        arm.show_in_front = True
        for index in frames:
            arm.data.bones[skeleton['bones'][index]['name']]['gr2_properties'] = json.dumps(properties(skeleton['bones'][index]['props']))

    def build_light(self, source, world, props):
        kind = self.enum('light_type', props.get('bungie_light_type'), default='omni')
        light_type = {'omni': 'POINT', 'spot': 'SPOT', 'directional': 'SUN'}.get(kind)
        if light_type is None:
            ob = self.object(source['name'])
            self.restore_object_props(ob, props)
            self.set_property(ob.nwo, 'export_this', False)
            utils.print_warning(f'{self.path.name}: unsupported light type {kind!r}; preserved as an empty')
        else:
            light = bpy.data.lights.new(source['name'], light_type)
            ob = self.object(source['name'], light)
            self.restore_object_props(ob, props)
            for key, value in props.items():
                if not key.startswith('bungie_light_') or not has_value(value):
                    continue
                name = key[7:]
                if name.startswith('light_clipping_size_') or name in {'light_far_attenuation_start', 'light_far_attenuation_end'}:
                    value = float(value) * import_transform.scale_factor(self.scene_nwo)
                self.set_property(light.nwo, name, value)
            color = props.get('bungie_light_color')
            if color is not None:
                light.color = [utils.srgb_to_linear(v) for v in vector_value(color)[:3]]
            intensity = float(props.get('bungie_light_intensity', 1))
            light.energy = utils.calc_light_energy(light, intensity, utils.get_import_scale(self.owner.context))
            if light_type == 'SPOT':
                falloff = float(props.get('bungie_light_hotspot_falloff', 60))
                light.spot_size = radians(falloff)
                if falloff > 0:
                    light.spot_blend = max(0, min(1, 1 - float(props.get('bungie_light_hotspot_size', 45)) / falloff))
            attenuation = light_attenuation(props)
            if light_type != 'SUN' and attenuation is not None:
                start, end = attenuation
                scalar = import_transform.scale_factor(self.scene_nwo)
                self.set_property(light.nwo, 'light_far_attenuation_end', end * scalar)
                self.set_property(light.nwo, 'light_far_attenuation_start', start * scalar)
                utils.make_halo_light(light)
        ob.matrix_world = import_transform.object_matrix(world, self.scene_nwo)
        return ob

    def build_mesh_helper(self, source, world, parent_bone, region):
        """Retain exported line/helper nodes which have no drawable geometry."""
        ob = self.object(source['name'])
        ob.empty_display_type = 'PLAIN_AXES'
        self.restore_object_props(ob, source['props'])
        ob.nwo.region_name = utils.add_region(self.region if self.region is not None else region)
        # An empty cannot reproduce this mesh on export; keep it as a helper.
        self.set_property(ob.nwo, 'export_this', False)
        ob['gr2_missing_geometry'] = json.dumps(source['geometry_missing'])
        ob['gr2_mesh_bindings'] = json.dumps(dict(bones=source['bones'], materials=[
            self.data['materials'].get(address, {}).get('name', '') for address in source['materials']]))
        if self.armature is not None:
            name = parent_bone or next((self.bone_name(name) for name in source['bones'] if self.bone_name(name)), None)
            if name:
                ob.parent, ob.parent_type, ob.parent_bone = self.armature, 'BONE', name
            elif any(canonical_name(name) in self.object_roots for name in source['bones']):
                ob.parent = self.armature
        ob.matrix_world = import_transform.object_matrix(world, self.scene_nwo)
        utils.print_warning(f'{self.path.name}: {source["name"]} has no geometry; preserved as an empty')

    def apply_special_material(self, ob, source, props):
        """Use Foundry's display materials after all mesh properties are restored."""
        kind = ob.data.nwo.mesh_type.removeprefix('_connected_geometry_mesh_type_')
        source_kind = self.enum('mesh_type', props.get('bungie_mesh_type'), enums.MeshType)
        if source_kind in {'poop_collision', 'poop_physics'}:
            kind = source_kind
        material_name = {
            'collision': 'Collision', 'poop_collision': 'Collision',
            'physics': 'Physics', 'poop_physics': 'Physics', 'portal': 'Portal',
            'seam': 'Seam', 'cookie_cutter': 'CookieCutter',
            'planar_fog_volume': 'Fog', 'lightmap_region': 'LightmapRegion',
            'water_physics_volume': 'WaterVolume', 'weather_polyhedron': '+weather',
        }.get(kind)
        if kind == 'boundary_surface':
            material_name = {'SOFT_CEILING': 'SoftCeiling', 'SOFT_KILL': 'SoftKill',
                             'SLIP_SURFACE': 'SlipSurface'}.get(ob.data.nwo.boundary_surface_type)
        elif kind == 'obb_volume':
            material_name = {'STREAMING_VOLUME': 'StreamingVolume',
                             'LIGHTMAP_EXCLUSION': 'LightmapExcludeVolume'}.get(ob.data.nwo.obb_volume_type)
        elif kind == 'poop_collision':
            material_name = {'invisible_wall': 'WallCollision', 'play_collision': 'PlayCollision',
                             'bullet_collision': 'BulletCollision'}.get(ob.nwo.poop_collision_type, 'Collision')
        if material_name is None:
            return
        # Retain the source assignments even though the display uses one slot.
        ob.data['gr2_material_groups'] = json.dumps(source['groups'])
        ob.data['gr2_material_bindings'] = json.dumps([
            self.data['materials'].get(address, {}) for address in source['materials']])
        from ..tools.property_apply import apply_props_material
        existed = bpy.data.materials.get(material_name) is not None
        try:
            apply_props_material(ob, material_name)
            ob.data.polygons.foreach_set('material_index', np.zeros(len(ob.data.polygons), dtype=np.int32))
        finally:
            # Include partially created materials in rollback if setup fails.
            material = bpy.data.materials.get(material_name)
            if not existed and material is not None and material not in self.created_materials:
                self.created_materials.append(material)

    def build_mesh(self, source, world, parent_bone=None):
        props = properties(source['props'])
        triangles = source['triangles']
        selected = np.arange(len(triangles), dtype=np.int32)
        if self.render_only:
            mesh_type = self.enum('mesh_type', props.get('bungie_mesh_type'), enums.MeshType, default='default')
            if mesh_type in {'collision', 'physics', 'poop_collision', 'poop_physics', 'cookie_cutter'}:
                return
            records = source['annotations'].get('bungie_face_mode')
            modes = [next(iter(record.values())) for record in records] if records else [props.get('bungie_face_mode')] * len(triangles)
            selected = np.array([i for i, value in enumerate(modes) if self.enum('face_mode', value, enums.FaceMode, default='normal')
                                 not in {'collision_only', 'sphere_collision_only'}], dtype=np.int32)
        region = self.table_name(props.get('bungie_face_region', 'default'), self.regions)
        if source.get('geometry_missing'):
            if not self.allowed or (region, self.permutation) in self.allowed:
                self.build_mesh_helper(source, world, parent_bone, region)
            return
        if self.allowed:
            records = source['annotations'].get('bungie_face_region')
            regions = [self.table_name(next(iter(r.values())), self.regions) for r in records] if records else [region] * len(triangles)
            selected = np.array([i for i in selected if (regions[i], self.permutation) in self.allowed], dtype=np.int32)
        if not len(selected):
            return
        vertices = source['vertices']
        positions = vertices['Position'][:, :3]
        # Exported vertices are in model/world space. Recover an object's local
        # coordinates using its skeleton entry, avoiding a second baked transform.
        inverse = np.array(world.inverted_safe(), dtype=np.float32)
        positions = positions @ inverse[:3, :3].T + inverse[:3, 3]
        mesh = bpy.data.meshes.new(source['name'])
        ob = self.object(source['name'], mesh)
        mesh.from_pydata(positions.tolist(), [], triangles[selected].tolist())
        ob.matrix_world = import_transform.object_matrix(world, self.scene_nwo)
        mesh.transform(Matrix.Scale(import_transform.scale_factor(self.scene_nwo), 4))
        self.restore_object_props(ob, props)
        ob.nwo.region_name = utils.add_region(self.region if self.region is not None else region)
        for address in source['materials']:
            mesh.materials.append(self.material(address))
        material_indices = np.zeros(len(triangles), dtype=np.int32)
        for index, start, count in source['groups']:
            if start < 0 or count < 0 or start + count > len(triangles) or index < 0:
                raise ValueError('Invalid GR2 material group')
            # Material bindings are optional. Max and other Granny exporters can
            # retain topology groups even when no materials were exported.
            if source['materials']:
                if index >= len(source['materials']):
                    raise ValueError('Invalid GR2 material group')
                material_indices[start:start + count] = index
        if not source['materials'] and source['groups']:
            mesh['gr2_material_groups'] = json.dumps(source['groups'])
        mesh.polygons.foreach_set('material_index', material_indices[selected])
        loops = triangles[selected].reshape(-1)
        invalid_uvs = {}
        for name, values in vertices.items():
            layer_name = source.get('component_names', {}).get(name) or name
            # PCA tension is recalculated from deformation at export. Keep
            # authored pca_mask weights, but do not turn sampled tension into
            # a painted Blender color layer.
            if layer_name.casefold() == 'tension' or name.casefold() == 'tension':
                continue
            if name.startswith('TextureCoordinates') or name == 'lighting':
                lighting = 'lighting' in layer_name.lower() or 'lighting' in name.lower()
                uv = mesh.uv_layers.new(name='lighting' if lighting else layer_name)
                invalid = ~np.isfinite(values)
                if invalid.any():
                    invalid_uvs[name] = dict(indices=np.argwhere(invalid).tolist(), values=values[invalid].tolist())
                    values = values.copy()
                    values[invalid] = 0
                    utils.print_warning(f'{self.path.name}: {source["name"]}: replaced {int(invalid.sum())} invalid {layer_name} UV components with zero')
                coordinates = values[loops, :2].copy()
                coordinates[:, 1] = 1 - coordinates[:, 1]
                uv.data.foreach_set('uv', coordinates.ravel())
                if values.shape[1] > 2:
                    store_uv_w(mesh, uv, values[loops, 2])
            elif name.startswith(('DiffuseColor', 'colorSet')) or name.casefold() == 'pca_mask':
                layer = mesh.color_attributes.new(name=layer_name, type='FLOAT_COLOR', domain='CORNER')
                rgba = np.ones((len(loops), 4), dtype=np.float32)
                rgba[:, :min(4, values.shape[1])] = values[loops, :4]
                layer.data.foreach_set('color', rgba.ravel())
        if invalid_uvs:
            mesh['gr2_invalid_uvs'] = json.dumps(invalid_uvs)
        if 'Normal' in vertices:
            normals = vertices['Normal'][loops, :3] @ np.array(world.to_3x3(), dtype=np.float32)
            lengths = np.linalg.norm(normals, axis=1, keepdims=True)
            normals /= np.maximum(lengths, 1e-10)
            mesh.polygons.foreach_set('use_smooth', np.ones(len(selected), dtype=bool))
            mesh.normals_split_custom_set(normals.tolist())
        self.restore_faces(mesh, props, source['annotations'], selected)
        self.apply_special_material(ob, source, props)
        self.restore_structure_proxy(ob, props)
        if self.armature is not None and (source['bones'] or parent_bone or props.get('bungie_parent_object')):
            matrix = ob.matrix_world.copy()
            ob.parent = self.armature
            names = [self.bone_name(name) for name in source['bones']]
            weights, indices = vertices.get('BoneWeights'), vertices.get('BoneIndices')
            if weights is not None and indices is not None:
                object_weights = np.zeros(len(positions), dtype=np.float32)
                bone_weights = np.zeros(len(positions), dtype=np.float32)
                for vertex, (palette, influences) in enumerate(zip(indices, weights)):
                    for index, weight in zip(palette, influences):
                        if weight <= 0:
                            continue
                        if int(index) != index or not 0 <= int(index) < len(names):
                            raise ValueError(f'{self.path}: unresolved GR2 skin bone')
                        name = names[int(index)]
                        if name is None and canonical_name(source['bones'][int(index)]) in self.object_roots:
                            # This influence follows the armature object itself.
                            object_weights[vertex] += weight
                            continue
                        if name is None:
                            raise ValueError(f'{self.path}: unresolved GR2 skin bone')
                        group = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
                        group.add([vertex], float(weight), 'REPLACE')
                        bone_weights[vertex] += weight
                modifier = ob.modifiers.new('Armature', 'ARMATURE')
                modifier.object = self.armature
                if np.any((object_weights > 0) & (bone_weights > 0)):
                    # Blender normalizes the remaining bone weights. Blend its
                    # deformation with the undeformed vertex to retain the
                    # omitted object's share of a mixed skin influence.
                    deform = ob.vertex_groups.new(name='GR2 Deform Weight')
                    for vertex, (object_weight, bone_weight) in enumerate(zip(object_weights, bone_weights)):
                        if bone_weight > 0:
                            deform.add([vertex], float(bone_weight / (bone_weight + object_weight)), 'REPLACE')
                    modifier.vertex_group = deform.name
            else:
                name = parent_bone or next((name for name in names if name), None)
                if name is None:
                    parent_path = props.get('bungie_parent_object', '')
                    components = re.findall(r"'([^']+)'", parent_path)
                    name = self.bone_name(components[-1]) if components else None
                if name:
                    ob.parent_type, ob.parent_bone = 'BONE', name
            ob.matrix_world = matrix
        self.owner.mesh_objects.append(ob)
        return ob

    def restore_instance_proxies(self, model, skeleton, meshes):
        """Recover instance-owned meshes from this model's mesh bindings."""
        kinds = {address: self.enum('mesh_type', properties(self.data['meshes'][address]['props']).get('bungie_mesh_type'),
                                    enums.MeshType, default='default') for address in meshes}
        instances = {self.data['meshes'][address]['name']: ob for address, ob in meshes.items()
                     if kinds[address] in {'poop', 'default'}}
        if not instances:
            return
        bones = skeleton['bones']
        bone_indices = {bone['name']: i for i, bone in enumerate(bones)}
        for address, proxy in meshes.items():
            kind = kinds[address]
            if kind not in {'poop_collision', 'poop_physics', 'cookie_cutter'}:
                continue
            source = self.data['meshes'][address]
            props = properties(source['props'])
            parent_names = re.findall(r"'([^']+)'", str(props.get('bungie_poop_parent', '')))
            parent_name = parent_names[-1] if parent_names else props.get('bungie_poop_parent')
            instance = instances.get(parent_name)
            index = bone_indices.get(source['name'])
            if instance is None and index is not None:
                parent = bones[index]['parent']
                while parent != -1:
                    parent_name = bones[parent]['name']
                    instance = instances.get(parent_name)
                    if instance is not None:
                        break
                    parent = bones[parent]['parent']
            # Some exporters omit the proxy's skeleton entry and parent tag.
            # A model named for its instance still owns its bound proxy meshes.
            if instance is None and not has_value(props.get('bungie_poop_parent')) and index is None:
                parent_name = model['name']
                instance = instances.get(parent_name)
                if instance is None and len(instances) == 1:
                    parent_name, instance = next(iter(instances.items()))
            if instance is None:
                continue
            proxy_type = {'poop_collision': 'collision', 'poop_physics': 'physics',
                          'cookie_cutter': 'cookie_cutter'}[kind]
            # Halo 4/H2A use poop_collision with play_collision for physics.
            if kind == 'poop_collision' and proxy.nwo.poop_collision_type == 'play_collision':
                proxy_type = 'physics'
            if proxy_type == 'physics':
                slot = next((f'proxy_physics{i}' for i in range(200)
                             if getattr(instance.data.nwo, f'proxy_physics{i}') is None), None)
            else:
                slot = f'proxy_{proxy_type}'
                if getattr(instance.data.nwo, slot) is not None:
                    slot = None
            if slot is None:
                utils.print_warning(f'{self.path.name}: no free {proxy_type} proxy slot for {parent_name}; keeping {source["name"]} in the scene')
                continue
            # Proxy edit/export replaces the object's matrix with the owner's.
            # Bake any child offset into its mesh before removing its parenting.
            proxy.data.transform(instance.matrix_world.inverted_safe() @ proxy.matrix_world)
            proxy.parent = None
            proxy.parent_type, proxy.parent_bone = 'OBJECT', ''
            proxy.matrix_parent_inverse = Matrix.Identity(4)
            proxy.matrix_world = instance.matrix_world.copy()
            proxy.nwo.proxy_type = proxy_type
            proxy.data.nwo.mesh_type = '_connected_geometry_mesh_type_' + (
                'cookie_cutter' if proxy_type == 'cookie_cutter' else proxy_type)
            proxy['gr2_proxy_owner'] = parent_name
            # A bound proxy also identifies an instance when its owner lacks
            # mesh-type metadata, as seen in older Max exports.
            instance.data.nwo.mesh_type = '_connected_geometry_mesh_type_default'
            setattr(instance.data.nwo, slot, proxy)
            # The mesh pointer keeps the proxy alive. Foundry links it into the
            # scene temporarily when the user opens instance proxy edit mode.
            for collection in list(proxy.users_collection):
                collection.objects.unlink(proxy)

    def build(self):
        context = self.owner.context
        selected, active = list(context.selected_objects), context.view_layer.objects.active
        try:
            skeleton_armatures = {}
            # Keep every embedded image, including textures not used by a
            # supported shader channel or by the selected mesh components.
            for address in self.data.get('textures', {}):
                self.texture_images(address)
            for model in self.data['models']:
                if model['name'].casefold() == 'bungieexportinfo':
                    continue
                skeleton = self.data['skeletons'].get(model['skeleton'], dict(bones=[]))
                placement = Matrix(model['matrix'])
                worlds = {index: placement @ matrix for index, matrix in self.bone_worlds(skeleton).items()}
                if self.tag_armature is None:
                    self.armature = skeleton_armatures.get(model['skeleton'])
                self.object_roots = set()
                self.build_armature(skeleton, worlds)
                if self.armature is not None:
                    skeleton_armatures[model['skeleton']] = self.armature
                    if self.armature not in self.armatures:
                        self.armatures.append(self.armature)
                by_name = {bone['name']: worlds[i] for i, bone in enumerate(skeleton['bones'])}
                bone_indices = {bone['name']: i for i, bone in enumerate(skeleton['bones'])}
                if self.import_geometry:
                    meshes = {}
                    for address in model['meshes']:
                        source = self.data['meshes'][address]
                        index = bone_indices.get(source['name'])
                        parent = skeleton['bones'][index]['parent'] if index is not None else -1
                        parent_bone = self.bone_name(skeleton['bones'][parent]['name']) if parent != -1 else None
                        ob = self.build_mesh(source, by_name.get(source['name'], placement), parent_bone)
                        if ob is not None:
                            meshes[address] = ob
                    self.restore_instance_proxies(model, skeleton, meshes)
                if (not self.geometry_only and self.import_markers) or self.import_geometry:
                    for index, bone in enumerate(skeleton['bones']):
                        props = properties(bone['props'])
                        kind = self.enum('object_type', props.get('bungie_object_type'), enums.ObjectType, default='none')
                        if kind == 'light' and self.import_geometry and not self.geometry_only:
                            self.build_light(bone, worlds[index], props)
                            continue
                        if props.get('bungie_object_type') == 'other' and self.import_geometry and not self.geometry_only:
                            helper = self.object(bone['name'])
                            self.restore_object_props(helper, props)
                            self.set_property(helper.nwo, 'export_this', False)
                            helper['gr2_object_type'] = 'other'
                            helper.matrix_world = import_transform.object_matrix(worlds[index], self.scene_nwo)
                            continue
                        if kind != 'marker' or self.geometry_only or not self.import_markers:
                            continue
                        marker = self.object(bone['name'])
                        marker.empty_display_type = 'ARROWS'
                        self.restore_object_props(marker, props)
                        matrix = import_transform.marker_matrix(worlds[index], self.scene_nwo)
                        parent = bone['parent']
                        name = self.bone_name(skeleton['bones'][parent]['name']) if parent != -1 else None
                        if name:
                            marker.parent, marker.parent_type, marker.parent_bone = self.armature, 'BONE', name
                        elif parent != -1 and canonical_name(skeleton['bones'][parent]['name']) in self.object_roots:
                            marker.parent = self.armature
                        marker.matrix_world = matrix
                        self.owner.marker_objects.append(marker)
            self.armature = max(self.armatures, key=lambda arm: len(arm.data.bones), default=self.tag_armature)
            if not self.objects and self.armature is None and not any(self.images.values()):
                raise ValueError('GR2 has no supported geometry, skeleton or markers')
            return self.objects
        except Exception:
            for ob in self.objects:
                if ob in self.owner.mesh_objects:
                    self.owner.mesh_objects.remove(ob)
                if ob in self.owner.marker_objects:
                    self.owner.marker_objects.remove(ob)
                data = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if data and data.users == 0:
                    if isinstance(data, bpy.types.Mesh):
                        bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Armature):
                        bpy.data.armatures.remove(data)
                    elif isinstance(data, bpy.types.Light):
                        bpy.data.lights.remove(data)
            bpy.data.collections.remove(self.collection)
            for material in self.created_materials:
                if material.users == 0:
                    bpy.data.materials.remove(material)
            for image in self.created_images:
                bpy.data.images.remove(image)
            raise
        finally:
            utils.set_object_mode(context)
            for ob in context.selected_objects:
                ob.select_set(False)
            for ob in selected:
                if ob.name in context.view_layer.objects:
                    ob.select_set(True)
            context.view_layer.objects.active = active


def resolve_granny_dll(owner):
    """Use the source project's runtime, or an installed Halo editing kit's."""
    project = utils.get_project(owner.scene_nwo.scene_project)
    if project is not None and project.project_path:
        dll_path = Path(project.project_path, 'granny2_x64.dll')
        if dll_path.is_file():
            return dll_path
    projects = [candidate for candidate in utils.get_prefs().projects
                if candidate.game in {'reach', 'halo4', 'halo2a'} and candidate.project_path]
    # Prefer the same game's runtime without changing the import's source game.
    projects.sort(key=lambda candidate: candidate.game != getattr(owner, 'game', None))
    for candidate in projects:
        dll_path = Path(candidate.project_path, 'granny2_x64.dll')
        if dll_path.is_file():
            utils.print_warning(f'Using fallback Granny runtime: {dll_path}')
            return dll_path
    raise RuntimeError(
        'This GR2 compatibility codec requires granny2_x64.dll, but it was not found in the current '
        'project or any configured Halo editing kit. The Halo Reach, Halo 4, and '
        'Halo 2 AMP editing kits contain this DLL. Add one of these editing kits '
        'as a Foundry project to use its DLL as a fallback.')


def read_gr2(owner, path, animations=False):
    # Resolve a kit only for a codec that needs it. Standard geometry, curves,
    # metadata and raw/S3TC images do not require a native runtime.
    codecs = NativeDecompressor(lambda: resolve_granny_dll(owner), on_use=utils.print_warning)
    reader = GrannyReader(decompress=codecs, texture_decoder=codecs.texture)
    options = dict(animations=animations, source_game=getattr(owner, 'game', None),
                   convert_scale=getattr(owner, 'gr2_convert_scale', True))
    try:
        return reader.read(path, **options)
    except UnsupportedGrannyFormat as error:
        if not supported_platform():
            raise RuntimeError(str(error)) from error
        try:
            dll_path = resolve_granny_dll(owner)
        except RuntimeError as missing:
            raise RuntimeError(f'{error}. Native compatibility fallback is unavailable: {missing}') from error
        from .reader import GrannyReader as NativeGrannyReader
        utils.print_warning(f'Using Granny compatibility reader: {error}')
        try:
            return NativeGrannyReader(dll_path).read(path, **options)
        except OSError as exc:
            raise RuntimeError(f'Could not load Granny runtime {dll_path}: {exc}') from exc


def import_gr2(owner, path, **kwargs):
    return GR2Importer(owner, path, read_gr2(owner, path), **kwargs).build()


def import_sidecar(owner, path, *, tag_armature=None, setup_as_asset=True):
    """Assemble the available GR2 components of an asset, in dependency order."""
    from dataclasses import asdict
    from .sidecar import read_sidecar, resolve_gr2_path
    asset = read_sidecar(path)
    project = utils.get_project(owner.scene_nwo.scene_project)
    files = {}
    for source in asset.sources:
        resolved = resolve_gr2_path(asset.path, source.reference, project.data_directory)
        if resolved is None:
            utils.print_warning(f'{asset.path.name}: missing GR2 {source.reference}')
            continue
        # Repeated networks (including shared BSP geometry and LOD declarations)
        # should not duplicate meshes. Different cinematic actors keep their rigs.
        files.setdefault((resolved, 'shared' if source.region == 'shared' else source.rig_key), []).append(source)
    if not files:
        utils.print_warning(f'{asset.path.name}: no referenced GR2 files are available')
        return [], []

    root = bpy.data.collections.new(asset.name)
    owner.scene_collection.children.link(root)
    scenario = asset.asset_type in {'scenario', 'prefab', 'multi_prefab'}
    set_type = utils.SetType.SCENARIO if scenario else utils.SetType.MODEL
    groups, rigs, objects, actions, imported_animations = {}, {}, [], [], []
    for (resolved, _), references in sorted(files.items(), key=lambda item: min(source.priority for source in item[1])):
        source = next((entry for entry in references if entry.object_type != 'skeleton'), references[0])
        group_key = source.region if scenario else source.rig_key
        group = groups.get(group_key)
        if group is None:
            group = bpy.data.collections.new(group_key or asset.name)
            root.children.link(group)
            groups[group_key] = group
            if scenario:
                group.nwo.type = 'region'
                group.nwo.region = utils.add_region(group_key or 'default', set_type)
        rig = rigs.get(source.rig_key)
        if rig is None and not rigs:
            rig = tag_armature
        blocks = (bpy.data.objects, bpy.data.collections, bpy.data.meshes,
                  bpy.data.armatures, bpy.data.materials, bpy.data.actions, bpy.data.images)
        before = [set(block) for block in blocks]
        animation_start = len(owner.scene_nwo.animations)
        kind = source.object_type
        default_type = {'collision_model': 'collision', 'physics_model': 'physics',
                        'scenario_structure_bsp': 'structure', 'render_model': 'default',
                        'decorator_set': 'decorator'}.get(kind)
        if asset.asset_type == 'decorator_set':
            default_type = 'decorator'
        has_marker_file = any(entry.object_type == 'markers' and entry.rig_key == source.rig_key
                              for entries in files.values() for entry in entries)
        try:
            new_objects, new_actions = owner.import_gr2_files(
                [resolved], tag_armature=rig, parent_collection=group, convert_scale=True,
                import_geometry=any(entry.object_type != 'skeleton' for entry in references),
                import_markers=kind == 'markers' or not has_marker_file,
                import_animations=kind == 'model_animation_graph' or not kind,
                animation_name=source.network.get('Name'), animation_metadata=source.network,
                permutation=source.permutation, region=source.region, asset_type=asset.asset_type,
                regions=[name for name, _ in asset.regions], global_materials=asset.global_materials,
                default_mesh_type=f'_connected_geometry_mesh_type_{default_type}' if default_type else None)
            if not new_objects and not new_actions and kind != 'skeleton':
                raise ValueError('GR2 has no supported editable content')
        except (OSError, ValueError, RuntimeError, TypeError, AttributeError, KeyError) as exc:
            # A bad animation can fail after geometry was already built. Roll
            # back this file while keeping successful components from other files.
            for ob in set(bpy.data.objects) - before[0]:
                for owned in (owner.mesh_objects, owner.marker_objects):
                    if ob in owned:
                        owned.remove(ob)
                bpy.data.objects.remove(ob, do_unlink=True)
            for index in reversed(range(animation_start, len(owner.scene_nwo.animations))):
                owner.scene_nwo.animations.remove(index)
            for collection in set(bpy.data.collections) - before[1]:
                bpy.data.collections.remove(collection)
            for block, previous in zip(blocks[2:], before[2:]):
                for item in set(block) - previous:
                    if block == bpy.data.images or item.users == 0:
                        block.remove(item)
            utils.print_warning(f'{asset.path.name}: could not import {resolved.name}: {exc}')
            continue
        objects.extend(new_objects)
        actions.extend(new_actions)
        imported_animations.extend(owner.scene_nwo.animations[animation_start:])
        rig = max((ob for ob in new_objects if ob.type == 'ARMATURE'), key=lambda arm: len(arm.data.bones), default=rig)
        if rig is not None:
            rigs[source.rig_key] = rig
        for collection in set(bpy.data.collections) - before[1]:
            collection.name = f'{kind or "GR2"}: {source.network.get("Name") or resolved.stem}'
            if kind != 'skeleton':
                collection.nwo.type = 'permutation'
                collection.nwo.permutation = utils.add_permutation(source.permutation, set_type)
        if source.lod.isdigit() and 0 <= int(source.lod) < 4:
            for ob in new_objects:
                if ob.type == 'MESH':
                    ob.nwo.decorator_lod = ('high', 'medium', 'low', 'very_low')[int(source.lod)]
        owner.emissive_meshes.update(ob.data for ob in new_objects if ob.type == 'MESH'
                                    and any(prop.type == 'emissive' for prop in ob.data.nwo.face_props))

    for group in groups.values():
        if not group.all_objects:
            for child in reversed(list(group.children_recursive)):
                bpy.data.collections.remove(child)
            bpy.data.collections.remove(group)
    if not objects and not actions:
        bpy.data.collections.remove(root)
        return [], []
    for name, active in asset.regions:
        utils.add_region(name, set_type)
        owner.scene_nwo.regions_table.get(name).active = active
    for name in asset.global_materials:
        table = owner.scene_nwo.global_material_table
        if table.get(name) is None:
            table.add().name = name
    by_name = {item.name.replace(':', ' ').casefold(): item for item in imported_animations}
    for source in asset.aliases:
        attributes = source.network
        reference = attributes.get('NetworkReference', '')
        animation = by_name.get(reference.replace(':', ' ').casefold())
        if animation is None:
            utils.print_warning(f'{asset.path.name}: unresolved animation reference {reference}')
            continue
        if attributes.get('Type', '').lower() == 'rename':
            animation.animation_renames.add().name = attributes.get('Name', '')
        else:
            copy = owner.scene_nwo.animation_copies.add()
            copy.name, copy.source_name = attributes.get('Name', ''), animation.name

    if setup_as_asset:
        supported = {'model', 'sky', 'animation', 'scenario', 'prefab', 'decorator_set', 'particle_model',
                     'polyart', 'cinematic', 'multi_model', 'multi_prefab'}
        if asset.asset_type in supported:
            try:
                owner.scene_nwo.asset_type = asset.asset_type
            except (TypeError, ValueError):
                utils.print_warning(f'{asset.path.name}: asset type {asset.asset_type} is unavailable in this project')
        # An absolute path also works for a sidecar outside the scene's project.
        target = utils.get_project(owner.scene_nwo.scene_project, use_external=False)
        try:
            owner.scene_nwo.sidecar_path = str(asset.path.resolve().relative_to(Path(target.data_directory).resolve()))
        except ValueError:
            owner.scene_nwo.sidecar_path = str(asset.path.resolve())
        if len(rigs) == 1 and not scenario:
            owner.scene_nwo.main_armature = next(iter(rigs.values()))
        for tag_type, reference in asset.output_tags.items():
            field = f'output_{tag_type}'
            if hasattr(owner.scene_nwo, field):
                setattr(owner.scene_nwo, field, True)
    utils.print_tag(f'Imported {asset.name} from {asset.path.name}: {len(objects)} objects, {len(actions)} animations')
    return objects, actions


def animation_action(owner, data, armature, name, frame_start=1):
    """Bake absolute GR2 local transforms into Blender bone basis transforms."""
    scene_nwo = gr2_scene_settings(owner)
    groups = data['groups']
    skeleton_name = canonical_name(armature.get('gr2_skeleton_name', ''))
    matching_groups = [group for group in groups if skeleton_name and canonical_name(group.get('name', '')) == skeleton_name]
    if matching_groups:
        groups = matching_groups
    tracks = {canonical_name(track['name']): track for group in groups for track in group['tracks']}
    mapped = {bone.name: tracks[canonical_name(bone.name)] for bone in armature.data.bones if canonical_name(bone.name) in tracks}
    bone_names = {canonical_name(bone.name) for bone in armature.data.bones}
    object_root = canonical_name(armature.get('gr2_object_root', ''))
    roots = [(track, group.get('root_rest')) for group in groups for track in group['tracks']
             if canonical_name(track['name']) not in bone_names and canonical_name(track['name']) != 'bungieexportinfo'
             and canonical_name(track['name']) in {object_root, canonical_name(group.get('name', ''))}]
    root_track, root_rest = next((item for item in roots if canonical_name(item[0]['name']) == object_root), roots[0] if roots else (None, None))
    if not mapped and root_track is None:
        raise ValueError('GR2 animation has no tracks matching the armature')
    old_action = armature.animation_data.action if armature.animation_data else None
    old_slot = armature.animation_data.action_slot if armature.animation_data else None
    old_basis = {bone.name: bone.matrix_basis.copy() for bone in armature.pose.bones}
    old_object_basis = armature.matrix_basis.copy()
    if root_rest is None:
        root_rest = json.loads(armature.get('gr2_object_root_rest', 'null'))
    root_inverse = import_transform.object_matrix(Matrix(root_rest), scene_nwo, rotate=False).inverted_safe() if root_rest is not None else Matrix.Identity(4)
    action = bpy.data.actions.new(name)
    armature.animation_data_create()
    armature.animation_data.action = action
    count = len((root_track or next(iter(mapped.values())))['positions'])
    from bpy_extras.anim_utils import action_ensure_channelbag_for_slot
    slot = action.slots.new('OBJECT', armature.name)
    armature.animation_data.action_slot = slot
    channelbag = action_ensure_channelbag_for_slot(action, slot)
    times = frame_start + np.arange(count) * data['dt'] * owner.context.scene.render.fps / owner.context.scene.render.fps_base
    scalar = import_transform.scale_factor(scene_nwo)
    def local_transform(track, frame):
        q = track['orientations'][frame]
        matrix = Quaternion((q[3], q[0], q[1], q[2])).to_matrix() @ Matrix(np.array(track['scales'][frame]).reshape(3, 3))
        matrix = matrix.to_4x4()
        matrix.translation = Vector(track['positions'][frame]) * scalar
        return matrix

    def bake_transform(track, prefix, target, group_name):
        # Allocate each curve once instead of repeatedly inserting and updating
        # growing keyframe arrays. Rest transforms are constant across samples.
        samples = np.empty((count, 10), dtype=np.float32)
        previous = None
        for frame in range(count):
            location, rotation, scale = (prefix @ local_transform(track, frame)).decompose()
            if previous is not None:
                rotation.make_compatible(previous)
            previous = rotation
            samples[frame] = (*location, *rotation, *scale)
        group = channelbag.groups.new(group_name)
        coordinates = np.empty((count, 2), dtype=np.float32)
        coordinates[:, 0] = times
        keyframe_rna = bpy.types.Keyframe.bl_rna.properties
        for channel, start, width in (('location', 0, 3), ('rotation_quaternion', 3, 4), ('scale', 7, 3)):
            for index in range(width):
                curve = channelbag.fcurves.new(data_path=target.path_from_id(channel), index=index)
                curve.group = group
                curve.keyframe_points.add(count)
                coordinates[:, 1] = samples[:, start + index]
                curve.keyframe_points.foreach_set('co', coordinates.ravel())
                for prop, identifier in (('interpolation', 'BEZIER'), ('handle_left_type', 'AUTO_CLAMPED'), ('handle_right_type', 'AUTO_CLAMPED')):
                    value = keyframe_rna[prop].enum_items[identifier].value
                    curve.keyframe_points.foreach_set(prop, np.full(count, value, dtype=np.int32))
                curve.update()
    try:
        if root_track is not None:
            armature.rotation_mode = 'QUATERNION'
            bake_transform(root_track, old_object_basis @ root_inverse, armature, 'Armature')
        for bone in armature.pose.bones:
            track = mapped.get(bone.name)
            if track is None:
                continue
            rest = bone.bone.matrix_local
            if bone.parent:
                rest = bone.parent.bone.matrix_local.inverted_safe() @ rest
            prefix = rest.inverted_safe()
            if bone.parent is None and not object_root:
                prefix = prefix @ import_transform.rotation_matrix(scene_nwo)
            bone.rotation_mode = 'QUATERNION'
            bake_transform(track, prefix, bone, bone.name)
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = frame_start
        action.frame_end = frame_start + (count - 1) * data['dt'] * owner.context.scene.render.fps / owner.context.scene.render.fps_base
        return action, count
    except Exception:
        bpy.data.actions.remove(action)
        raise
    finally:
        armature.animation_data.action = old_action
        if old_action is not None and old_slot is not None:
            armature.animation_data.action_slot = old_slot
        armature.matrix_basis = old_object_basis
        for bone in armature.pose.bones:
            bone.matrix_basis = old_basis[bone.name]
