

from collections import defaultdict
from enum import Enum
from math import radians
import os
from pathlib import Path, PureWindowsPath
import re
from tempfile import TemporaryDirectory
import time
import traceback
import zlib
from uuid import uuid4
import bmesh
import bpy
import bpy.props
from mathutils import Color, Quaternion, Vector, Matrix, Euler

import numpy as np

from ..tags import connected_geometry
from .. import import_transform

from ..tags.cinematic_root import NativeCinematicTag
from ..tags.animation_graph import AnimationGraphTag

from ..tags.decorator_set import DecoratorSetTag
from ..tags.decal_system import DecalSystemCorinthTag, DecalSystemTag

from ..tags.polyart import PolyArtTag

from ..tags.structure_lighting import ScenarioStructureLightingInfoTag

from ..tags.structure_design_blender import StructureDesignTag

from ..tags.globals import FPARMS, GlobalsTag

from ..tags.backend import ImportInfoSource, TagDocument
from ..tags.prefab import PrefabTag
from ..tags.scenario import ScenarioMetadataTag
from ..tags.sky_blender import SkyTag

from .animation.generate_frames import FrameGenerator

from ..legacy.jma import JMA
from ..ui.panel.cinematic import bake_vis_to_keyframes

from ..tags.object_blender import ObjectTag
from ..tags.particle_model import ParticleModelTag
from ..tags.scenario_structure_bsp import ScenarioStructureBspTag
from ..tags.animation import AnimationTag
from ..tags.animation_names import convert_animation_name_for_project, LEGACY_GAMES, REACH_PLUS_GAMES
from ..tags.pca_blender import PCAAnimationTag
from ..tags.render_model_blender import RenderModelTag
from ..tags.physics_blender import PhysicsTag
from ..tags.model import ChildObject, RenderModelOverrideType
from ..tags.model_blender import ModelTag
from ..tools.mesh_to_marker import convert_to_marker
from ..tags.bitmap import bitmap_to_image, clear_path_cache
from ..tags.camera_track import CameraTrackTag
from ..tags.collision_blender import CollisionTag
from ..tools.clear_duplicate_materials import clear_duplicate_materials
from ..tools.property_apply import apply_props_material, apply_prefix_bulk
from ..tools.rigging import HaloRig, aim_pitch_name, aim_yaw_name, needs_reach_fp_ik_fix, pedestal_name
from ..tools.rigging.create_rig import bake_imported_actions_to_control_rig
from ..tools.shader_finder import find_shaders
from ..tools.shader_reader import tag_to_nodes
from ..constants import (
    IDENTITY_MATRIX,
    IMPORT_TEMPLATE_DEFAULT,
    IMPORT_TEMPLATE_EVERYTHING,
    IMPORT_TEMPLATE_ITEMS,
    IMPORT_TEMPLATE_REIMPORT,
    IMPORT_TEMPLATE_VIEWING,
    OBJECT_TAG_EXTS,
    VALID_MESHES,
    WU_SCALAR,
    face_prop_game_supported,
)
from ..tags.connected_material import GameFunctionType, game_functions
from .. import utils
from .model_to_instance import ModelInstance
from functools import partial

legacy_model_formats = '.jms', '.ass'
IMPORT_SHADER_EXTENSIONS = utils.shader_exts + (
    '.shader_model', '.shader_environment', '.shader_transparent_chicago',
    '.shader_transparent_chicago_extended', '.shader_transparent_generic',
    '.shader_transparent_glass', '.shader_transparent_meter',
    '.shader_transparent_plasma', '.shader_transparent_water',
)
legacy_animation_formats = '.jmm', '.jma', '.jmt', '.jmz', '.jmv', '.jmw', '.jmo', '.jmr', '.jmrx'
legacy_poop_prefixes = '%', '+', '-', '?', '!', '>', '*', '&', '^', '<', '|',
legacy_frame_prefixes = "frame_", "frame ", "bip_", "bip ", "b_", "b "
DECORATOR_INSTANCER_GROUP = "Instanced Decorators"
DECORATOR_CLOUD_PROP = "nwo_decorator_placement_cloud"
DECORATOR_INSTANCE_SOURCE_PROP = "nwo_decorator_instance_source"
DECORATOR_TAG_PROP = "nwo_decorator_tag"
DECORATOR_VARIANT_PROP = "nwo_decorator_variant"
DECORATOR_ATTR_NORMAL = "normal"
DECORATOR_ATTR_INFO = "decorator_info"
DECORATOR_ATTR_SCALE = "decorator_scale"
DECORATOR_ATTR_TINT = "decorator_tint"

IMPORT_TEMPLATE_VALUES = {
    IMPORT_TEMPLATE_EVERYTHING: {
        "tag_render": True,
        "tag_markers": True,
        "tag_collision": True,
        "tag_physics": True,
        "tag_animation": True,
        "tag_import_lights": True,
        "tag_import_attachments": True,
        "build_blender_materials": True,
        "setup_as_asset": True,
        "from_vert_normals": False,
        "import_variant_children": True,
        "import_biped_weapon": True,
        "tag_bsp_import_geometry": True,
        "tag_bsp_skip_structure_merge": False,
        "tag_bsp_merge_render_collision": True,
        "tag_bsp_render_only": False,
        "tag_bsp_import_havok": True,
        "tag_import_design": True,
        "tag_scenario_import_objects": True,
        "tag_scenario_import_decals": True,
        "tag_scenario_import_decorators": True,
    },
    IMPORT_TEMPLATE_REIMPORT: {
        "tag_render": True,
        "tag_markers": True,
        "tag_collision": True,
        "tag_physics": True,
        "tag_animation": True,
        "tag_import_lights": True,
        "tag_import_attachments": False,
        "build_blender_materials": False,
        "setup_as_asset": True,
        "from_vert_normals": False,
        "import_variant_children": True,
        "import_biped_weapon": False,
        "tag_bsp_import_geometry": True,
        "tag_bsp_skip_structure_merge": False,
        "tag_bsp_merge_render_collision": True,
        "tag_bsp_render_only": False,
        "tag_bsp_import_havok": True,
        "tag_import_design": True,
        "tag_scenario_import_objects": False,
        "tag_scenario_import_decals": False,
        "tag_scenario_import_decorators": False,
    },
    IMPORT_TEMPLATE_VIEWING: {
        "tag_render": True,
        "tag_markers": True,
        "tag_collision": False,
        "tag_physics": False,
        "tag_animation": False,
        "tag_import_lights": True,
        "tag_import_attachments": True,
        "build_blender_materials": True,
        "setup_as_asset": False,
        "from_vert_normals": False,
        "import_variant_children": True,
        "import_biped_weapon": False,
        "tag_bsp_import_geometry": True,
        "tag_bsp_skip_structure_merge": False,
        "tag_bsp_merge_render_collision": True,
        "tag_bsp_render_only": True,
        "tag_bsp_import_havok": False,
        "tag_import_design": False,
        "tag_scenario_import_objects": True,
        "tag_scenario_import_decals": True,
        "tag_scenario_import_decorators": True,
    },
}

MODEL_IMPORT_TYPES = {
    "model",
    "biped",
    "crate",
    "creature",
    "device_control",
    "device_dispenser",
    "effect_scenery",
    "equipment",
    "giant",
    "device_machine",
    "projectile",
    "scenery",
    "spawner",
    "sound_scenery",
    "device_terminal",
    "vehicle",
    "weapon",
}

TEMPLATED_IMPORT_TYPES = MODEL_IMPORT_TYPES | {
    "render_model",
    "gbxmodel",
    "sky",
    "scenario",
    "scenario_structure_bsp",
    "prefab",
}

TEMPLATED_IMPORT_SCOPES = {
    "model",
    "object",
    "render_model",
    "sky",
    "scenario",
    "scenario_structure_bsp",
    "prefab",
}

def apply_import_template(operator, template):
    values = IMPORT_TEMPLATE_VALUES.get(template)
    if values is None:
        return

    for prop_name, value in values.items():
        if prop_name == "tag_bsp_import_havok" and not utils.is_corinth():
            continue
        if hasattr(operator, prop_name):
            setattr(operator, prop_name, value)

def import_template_update(self, context):
    apply_import_template(self, self.import_template)

def import_template_applies(operator):
    import_type = getattr(operator, "import_type", "")
    if import_type:
        return import_type in TEMPLATED_IMPORT_TYPES

    scope = getattr(operator, "scope", "")
    if not scope:
        return True

    return any(item in scope for item in TEMPLATED_IMPORT_SCOPES)

def set_default_import_template(operator):
    if not import_template_applies(operator):
        return

    template = getattr(utils.get_prefs(), "default_import_template", IMPORT_TEMPLATE_DEFAULT)
    if template != IMPORT_TEMPLATE_DEFAULT and template not in IMPORT_TEMPLATE_VALUES:
        template = IMPORT_TEMPLATE_DEFAULT
    operator.import_template = template
    apply_import_template(operator, template)

def draw_import_template(operator, layout):
    row = layout.row()
    row.prop(operator, "import_template", text="Template")

def draw_animation_conversions(operator, layout):
    row = layout.row()
    row.enabled = operator.graph_import_animations
    row.prop(operator, "convert_animations")


def draw_animation_graph_import_options(operator, layout, corinth, include_generate_frames=False):
    box = layout.box()
    box.prop(operator, "tag_animation")
    col = box.column(align=True)
    col.enabled = operator.tag_animation
    col.prop(operator, "tag_animation_filter")
    col.prop(operator, "graph_import_animations")
    draw_animation_conversions(operator, col)
    row = col.row()
    row.enabled = operator.tag_animation and operator.graph_import_animations
    row.prop(operator, "graph_bake_to_control_rig")
    row = col.row()
    row.enabled = operator.tag_animation and operator.graph_import_animations
    row.prop(operator, "graph_scale_animations_to_skeleton")
    if corinth:
        row = col.row()
        row.enabled = operator.tag_animation and operator.graph_import_animations
        row.prop(operator, "graph_import_pca_data")
    col.prop(operator, "graph_generate_renames")
    col.prop(operator, "graph_import_events")
    col.prop(operator, "graph_import_ik_chains")
    if include_generate_frames:
        col.prop(operator, "generate_frames")

def draw_graph_import_options(operator, layout, corinth):
    layout.prop(operator, "tag_animation_filter")
    layout.prop(operator, "graph_import_animations")
    draw_animation_conversions(operator, layout)
    row = layout.row()
    row.enabled = operator.graph_import_animations
    row.prop(operator, "graph_bake_to_control_rig")
    row = layout.row()
    row.enabled = operator.graph_import_animations
    row.prop(operator, "graph_scale_animations_to_skeleton")
    if corinth:
        row = layout.row()
        row.enabled = operator.graph_import_animations
        row.prop(operator, "graph_import_pca_data")
    layout.prop(operator, "graph_generate_renames")
    layout.prop(operator, "graph_import_events")
    layout.prop(operator, "graph_import_ik_chains")

def draw_model_source_options(operator, layout, corinth, show_model_override, show_variant, show_state=True, show_permutation=False):
    if not show_model_override and not show_variant and not show_permutation:
        return

    box = layout.box()
    box.label(text="Selection")
    if show_model_override and corinth:
        box.prop(operator, "tag_model_override_type")
    if show_permutation:
        box.prop(operator, "tag_permutation")
    if show_variant:
        box.prop(operator, "tag_variant")
        if show_state and getattr(operator, "tag_variant", "") != "all_variants":
            box.prop(operator, "tag_state")
            if getattr(operator, "tag_markers", False):
                box.prop(operator, "import_variant_children")

def render_lod_source_project(operator):
    # The tag dialog establishes a source-project override before drawing.
    # In the file browser, resolve the selection without changing that context.
    project = utils.get_project()
    filepath = getattr(operator, 'filepath', '')
    if filepath:
        path = Path(filepath).resolve()
        for source_project in utils.get_prefs().projects:
            try:
                path.relative_to(Path(source_project.tags_directory).resolve())
            except ValueError:
                continue
            project = source_project
            break
    return project


def draw_halo2_lod(operator, layout):
    project = render_lod_source_project(operator)
    if project is not None and project.game in {'halo1', 'halo2'}:
        layout.prop(operator, "render_lod", text="Halo 1 LOD" if project.game == 'halo1' else "Halo 2 LOD")


def draw_material_project_option(operator, layout):
    if not hasattr(operator, "build_materials_for_project"):
        return
    project = utils.get_project(use_external=False)
    if project is None or project.game == 'halo2':
        return
    row = layout.row()
    row.enabled = operator.build_blender_materials
    row.prop(operator, "build_materials_for_project")


def draw_model_tag_import_sections(operator, layout, corinth, show_template=True, show_source=True, has_variants=True, has_permutations=False, show_fp_arms=True, show_biped_weapon=True, include_generate_frames=False, show_material_options=True):
    if show_template:
        draw_import_template(operator, layout)

    if show_source:
        draw_model_source_options(operator, layout, corinth, has_variants, has_variants,
                                  show_permutation=has_permutations)

    rig_box = layout.box()
    rig_box.label(text="Rigging")
    rig_box.prop(operator, "reuse_armature")
    rig_box.prop(operator, "build_control_rig")

    core_box = layout.box()
    core_box.label(text="Core Model")
    core_box.prop(operator, "tag_render")
    draw_halo2_lod(operator, core_box)
    core_box.prop(operator, "tag_markers")

    reimport_box = layout.box()
    reimport_box.label(text="Game Reimport")
    reimport_box.prop(operator, "setup_as_asset")
    reimport_box.prop(operator, "tag_collision")
    reimport_box.prop(operator, "tag_physics")
    # reimport_box.prop(operator, "from_vert_normals")

    draw_animation_graph_import_options(operator, layout, corinth, include_generate_frames)

    view_box = layout.box()
    view_box.label(text="Blender Viewing")
    if corinth:
        view_box.prop(operator, "tag_import_lights")
    view_box.prop(operator, "tag_import_attachments")
    if show_fp_arms:
        view_box.prop(operator, "import_fp_arms", text="FP Arms (Weapon Only)")
    if show_biped_weapon:
        view_box.prop(operator, "import_biped_weapon")
    if show_biped_weapon and getattr(operator, "import_biped_weapon", False):
        view_box.prop(operator, "biped_weapon_source")
    if show_material_options:
        view_box.prop(operator, "build_blender_materials")
        draw_material_project_option(operator, view_box)
        view_box.prop(operator, "always_extract_bitmaps")

def draw_scenario_import_sections(operator, layout, corinth, show_template=True, show_zone_set=False, show_sky=False, show_scenario_content=False, show_setup_as_asset=True):
    project = render_lod_source_project(operator)
    game = project.game if project is not None else None
    classic = game in {'halo1', 'halo2'}
    corinth = project.corinth if project is not None else corinth
    if show_template:
        draw_import_template(operator, layout)

    if show_zone_set:
        source_box = layout.box()
        source_box.label(text="Selection")
        source_box.prop(operator, "tag_bsp" if classic else "tag_zone_set")

    core_box = layout.box()
    core_box.label(text="Core")
    core_box.prop(operator, "tag_bsp_import_geometry")
    if game == 'halo1':
        merge_row = core_box.row()
        merge_row.enabled = operator.tag_bsp_import_geometry
        merge_row.prop(operator, "tag_bsp_merge_render_collision")
    if not classic:
        core_box.prop(operator, "tag_import_lights")

    reimport_box = layout.box()
    reimport_box.label(text="Game Reimport")
    if show_setup_as_asset:
        setup_as_asset_row = reimport_box.row()
        setup_as_asset_row.enabled = not getattr(operator, "force_no_setup_as_asset", False)
        setup_as_asset_row.prop(operator, "setup_as_asset")
    reimport_col = reimport_box.column(align=True)
    reimport_col.enabled = not operator.tag_bsp_render_only
    reimport_col.prop(operator, "tag_bsp_skip_structure_merge")
    if corinth:
        reimport_col.prop(operator, "tag_bsp_import_havok")
    if not classic:
        reimport_col.prop(operator, "tag_import_design")

    view_box = layout.box()
    view_box.label(text="Blender Viewing")
    view_box.prop(operator, "tag_bsp_render_only")
    if show_sky:
        view_box.prop(operator, "tag_sky")
    if show_scenario_content:
        view_box.prop(operator, "tag_scenario_import_objects")
        view_box.prop(operator, "tag_scenario_import_decals")
        if game != 'halo1':
            view_box.prop(operator, "tag_scenario_import_decorators")
            row = view_box.row()
            row.enabled = operator.tag_scenario_import_decorators
            row.prop(operator, "decorator_lod")
    view_box.prop(operator, "build_blender_materials")
    draw_material_project_option(operator, view_box)
    view_box.prop(operator, "always_extract_bitmaps")

def _set_vector_point_attribute(mesh, name, values):
    attribute = mesh.attributes.new(name, 'FLOAT_VECTOR', 'POINT')
    attribute.data.foreach_set('vector', np.ascontiguousarray(values, dtype=np.float32).reshape(-1))


def _set_color_point_attribute(mesh, name, values):
    attribute = mesh.attributes.new(name, 'FLOAT_COLOR', 'POINT')
    attribute.data.foreach_set('color', np.ascontiguousarray(values, dtype=np.float32).reshape(-1))


def _decorator_up_vectors(rotations):
    x, y, z, w = (rotations[:, index] for index in range(4))
    up = np.empty((len(rotations), 3), dtype=np.float32)
    up[:, 0] = 2.0 * (x * z + w * y)
    up[:, 1] = 2.0 * (y * z - w * x)
    up[:, 2] = 1.0 - 2.0 * (x * x + y * y)
    lengths = np.linalg.norm(up, axis=1)
    valid = lengths > 0.000001
    up[valid] /= lengths[valid, None]
    up[~valid] = (0.0, 0.0, 1.0)
    return up


def _decorator_rotation_values(rotations, up):
    x, y, z, w = (rotations[:, index] for index in range(4))
    original_x = np.empty((len(rotations), 3), dtype=np.float32)
    original_x[:, 0] = 1.0 - 2.0 * (y * y + z * z)
    original_x[:, 1] = 2.0 * (x * y + z * w)
    original_x[:, 2] = 2.0 * (x * z - y * w)

    align = np.empty((len(rotations), 4), dtype=np.float32)
    align[:, 0] = 1.0 + up[:, 2]
    align[:, 1] = -up[:, 1]
    align[:, 2] = up[:, 0]
    align[:, 3] = 0.0
    align[align[:, 0] < 0.000001] = (0.0, 1.0, 0.0, 0.0)
    align /= np.linalg.norm(align, axis=1)[:, None]

    aw, ax, ay, az = (align[:, index] for index in range(4))
    base_x = np.empty_like(up)
    base_x[:, 0] = 1.0 - 2.0 * (ay * ay + az * az)
    base_x[:, 1] = 2.0 * (ax * ay + az * aw)
    base_x[:, 2] = 2.0 * (ax * az - ay * aw)
    cross = np.cross(base_x, original_x)
    sin = np.einsum('ij,ij->i', up, cross)
    cos = np.einsum('ij,ij->i', base_x, original_x)
    return np.mod(np.arctan2(sin, cos), 2.0 * np.pi) / (2.0 * np.pi)


def _decorator_records_to_clouds(placements, path, name, types, collection, bvh=None):
    grouped = defaultdict(list)
    for placement in placements:
        decorator_type = types.get(placement.type_index)
        if decorator_type is None:
            continue
        position = Vector(tuple(value * 100 for value in placement.position))
        if bvh and not utils.test_point_bvh(bvh, position):
            continue
        grouped[placement.type_index].append(placement)

    clouds = []
    placement_count = 0
    for type_index, records in grouped.items():
        decorator_type = types[type_index]
        placement_count += len(records)
        cloud_name = f'{name}_{decorator_type.decorator_type_name}_decorator_cloud'
        positions = np.asarray([record.position for record in records], dtype=np.float32) * 100.0
        rotations = np.asarray([record.rotation for record in records], dtype=np.float32)
        mesh = bpy.data.meshes.new(cloud_name)
        mesh.vertices.add(len(records))
        mesh.vertices.foreach_set('co', positions.reshape(-1))
        up = _decorator_up_vectors(rotations)
        _set_vector_point_attribute(mesh, DECORATOR_ATTR_NORMAL, up)
        info = np.ones((len(records), 4), dtype=np.float32)
        info[:, 0] = _decorator_rotation_values(rotations, up)
        info[:, 1] = np.asarray([record.ground_tint for record in records], dtype=np.float32) / 255.0
        info[:, 2] = np.asarray([record.motion_scale for record in records], dtype=np.float32) / 255.0
        _set_color_point_attribute(mesh, DECORATOR_ATTR_INFO, info)
        scale = np.ones((len(records), 4), dtype=np.float32)
        scale[:, :3] = np.asarray([record.scale for record in records], dtype=np.float32)[:, None]
        _set_color_point_attribute(mesh, DECORATOR_ATTR_SCALE, scale)
        tint = np.ones((len(records), 4), dtype=np.float32)
        tint[:, :3] = np.asarray([record.tint for record in records], dtype=np.float32) ** 2.2
        _set_color_point_attribute(mesh, DECORATOR_ATTR_TINT, tint)
        mesh.transform(import_transform.mesh_matrix())
        mesh.update()

        ob = bpy.data.objects.new(name=cloud_name, object_data=mesh)
        ob.matrix_world = import_transform.rotation_matrix()
        ob[DECORATOR_CLOUD_PROP] = True
        ob[DECORATOR_TAG_PROP] = path
        ob[DECORATOR_VARIANT_PROP] = decorator_type.decorator_type_name
        ob.nwo.export_this = False
        collection.objects.link(ob)
        clouds.append(ob)
    return clouds, placement_count


def _decorator_cloud_marker_data(cloud: bpy.types.Object):
    tag_path = cloud.get(DECORATOR_TAG_PROP) or cloud.nwo.marker_game_instance_tag_name
    variant = cloud.get(DECORATOR_VARIANT_PROP) or cloud.nwo.marker_game_instance_tag_variant_name
    return tag_path, variant

def _decorator_instance_source_empty(cloud: bpy.types.Object, game_object_collection: bpy.types.Collection=None):
    name = f"{cloud.name}_instance_source"
    source = bpy.data.objects.get(name)
    if source is None:
        source = bpy.data.objects.new(name, None)
    
    for collection in tuple(source.users_collection):
        collection.objects.unlink(source)
    
    source[DECORATOR_INSTANCE_SOURCE_PROP] = True
    cloud[DECORATOR_INSTANCE_SOURCE_PROP] = source.name
    source.empty_display_type = 'PLAIN_AXES'
    source.empty_display_size = 0.01
    source.hide_select = False
    source.hide_viewport = False
    source.hide_render = False
    source.instance_type = 'COLLECTION'
    source.instance_collection = game_object_collection
    source.matrix_world = Matrix.Identity(4)
    tag_path, variant = _decorator_cloud_marker_data(cloud)
    source.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
    source.nwo.marker_game_instance_tag_name = tag_path
    source.nwo.marker_game_instance_tag_variant_name = variant
    source.nwo.marker_instance = True
    source.nwo.export_this = True
    return source

def _modifier_input_identifier(node_group: bpy.types.NodeTree, socket_name: str):
    search_name = socket_name.casefold()
    if hasattr(node_group, "interface"):
        for item in node_group.interface.items_tree:
            if getattr(item, "item_type", None) != 'SOCKET':
                continue
            if getattr(item, "in_out", None) != 'INPUT':
                continue
            if getattr(item, "name", "").casefold() == search_name:
                return getattr(item, "identifier", None)
    
    for socket in getattr(node_group, "inputs", []):
        if socket.name.casefold() == search_name:
            return socket.identifier
    
    return None

def _modifier_property_input(mod: bpy.types.NodesModifier, identifier: str):
    properties = getattr(mod, "properties", None)
    inputs = getattr(properties, "inputs", None) if properties is not None else None
    if inputs is not None:
        modifier_input = getattr(inputs, identifier, None)
        if modifier_input is not None:
            return modifier_input
    
    view_layer = getattr(bpy.context, "view_layer", None)
    if view_layer is not None:
        view_layer.update()
        properties = getattr(mod, "properties", None)
        inputs = getattr(properties, "inputs", None) if properties is not None else None
        if inputs is None:
            return None
        modifier_input = getattr(inputs, identifier, None)
        if modifier_input is not None:
            return modifier_input
    
    try:
        return inputs[identifier]
    except (KeyError, TypeError):
        return None

def _set_modifier_input(mod: bpy.types.NodesModifier, node_group: bpy.types.NodeTree, socket_name: str, value):
    identifier = _modifier_input_identifier(node_group, socket_name)
    if identifier is None:
        return False
    
    modifier_input = _modifier_property_input(mod, identifier)
    if modifier_input is None:
        return False
    modifier_input.value = value
    return True

def _set_modifier_attribute_input(mod: bpy.types.NodesModifier, node_group: bpy.types.NodeTree, socket_name: str, attribute_name: str):
    identifier = _modifier_input_identifier(node_group, socket_name)
    if identifier is None:
        return False
    
    use_attribute_key = f"{identifier}_use_attribute"
    attribute_name_key = f"{identifier}_attribute_name"
    
    modifier_input = _modifier_property_input(mod, identifier)
    if modifier_input is None:
        return False
    if hasattr(modifier_input, "type"):
        modifier_input.type = "ATTRIBUTE"
    modifier_input.attribute_name = attribute_name
    return True

def _add_decorator_cloud_instance_nodes(cloud: bpy.types.Object, source: bpy.types.Object):
    modifier_name = DECORATOR_INSTANCER_GROUP
    mod = cloud.modifiers.get(modifier_name) or cloud.modifiers.new(modifier_name, 'NODES')
    group = utils.add_node_from_resources("geometry_nodes", DECORATOR_INSTANCER_GROUP)
    if group is None:
        return mod
    
    mod.node_group = group
    _set_modifier_input(mod, group, "Instance On", "Points")
    _set_modifier_input(mod, group, "Input Type", "Data-Block")
    _set_modifier_input(mod, group, "Instance Type", "Object")
    _set_modifier_input(mod, group, "Object", source)
    _set_modifier_input(mod, group, "Keep Surface", True)
    _set_modifier_input(mod, group, "Align Rotation", True)
    _set_modifier_attribute_input(mod, group, "Scale", DECORATOR_ATTR_SCALE)
    return mod

def add_decorator_cloud_instancer(cloud: bpy.types.Object, game_object_collection: bpy.types.Collection):
    source = _decorator_instance_source_empty(cloud, game_object_collection)
    return _add_decorator_cloud_instance_nodes(cloud, source)

def _armature_pose_bones_in_node_order(armature: bpy.types.Object, node_count: int) -> list[bpy.types.PoseBone]:
    pose_bones = armature.pose.bones
    return [
        pose_bones[bone.name]
        for bone in armature.data.bones[:node_count]
        if bone.name in pose_bones
    ]

def _pose_bone_rest_local_matrix(bone: bpy.types.PoseBone) -> Matrix:
    matrix = bone.bone.matrix_local.copy()
    if bone.parent is not None:
        return bone.parent.bone.matrix_local.inverted_safe() @ matrix

    return matrix

def _apply_scenario_node_orientations(armature: bpy.types.Object, node_mask: list[bool], orientations) -> int:
    if armature is None or armature.type != 'ARMATURE' or not node_mask or not orientations:
        return 0

    orientation_iter = iter(orientations)
    pose_bones = _armature_pose_bones_in_node_order(armature, len(node_mask))
    applied_count = 0

    for idx, bone in enumerate(pose_bones):
        if not node_mask[idx]:
            continue

        try:
            orientation = next(orientation_iter)
        except StopIteration:
            break

        orientation = orientation.copy() if isinstance(orientation, Quaternion) else Quaternion(orientation)
        if orientation.magnitude <= 1e-6:
            orientation = Quaternion((1.0, 0.0, 0.0, 0.0))
        else:
            orientation.normalize()

        base_matrix = _pose_bone_rest_local_matrix(bone)

        translation, _, scale = base_matrix.decompose()
        if bone.parent is None:
            orientation = import_transform.quaternion(orientation)

        target_matrix = Matrix.LocRotScale(translation, orientation, scale)
        pose_matrix = base_matrix.inverted_safe() @ target_matrix

        bone.rotation_mode = 'QUATERNION'
        bone.matrix_basis = pose_matrix
        applied_count += 1

    return applied_count

variant_items = []
last_used_variant = ""

permutation_items = []

decorator_type_items = []
last_used_decorator_type = ""

sky_items = []
cinematic_scene_items = []
BIPED_WEAPON_SOURCE_BIPED_TAG = "biped_tag_weapons"
biped_weapon_source_item_cache = {}

zone_set_items = {"blah": "blah"}
bsp_items = []

ammo_names = "primary_ammunition", "airstrike_launch_count", "secondary_ammunition"
tether_name = "tether_distance"

checked_asset_once = False

def biped_weapon_source_items(_self, _context):
    tags_dir = utils.get_tags_path()
    cache_key = os.path.normcase(os.path.abspath(tags_dir)) if tags_dir else None
    if cache_key in biped_weapon_source_item_cache:
        return biped_weapon_source_item_cache[cache_key]
    items = [
        (BIPED_WEAPON_SOURCE_BIPED_TAG, "Default", "Import the weapons referenced by the biped tag"),
    ]
    weapon_paths = set()

    if tags_dir:
        tags_root = Path(tags_dir)
        for directory, _, filenames in os.walk(tags_root):
            for filename in filenames:
                if Path(filename).suffix.lower() != '.weapon':
                    continue
                path = (Path(directory) / filename).relative_to(tags_root)
                with ObjectTag(path=path, tag_must_exist=True, raise_on_error=False, hide_prints=True) as weapon:
                    if not weapon.valid:
                        continue
                    model_path = weapon.get_model_tag_path_full()
                    model_extension = '.gbxmodel' if weapon.game == 'halo1' else '.model'
                    if not model_path or Path(model_path).suffix.lower() != model_extension or not Path(model_path).is_file():
                        continue
                weapon_paths.add(str(path))

    # A flat enum lets Blender wrap long menus into columns instead of measuring
    # the full folder headings and collapsing the menu to a scrolling column.
    for path in sorted(weapon_paths, key=lambda p: (Path(p).stem.casefold(), p.casefold(), p)):
        items.append((path, Path(path).stem, path))

    biped_weapon_source_item_cache[cache_key] = items
    return items

IMPORT_OPERATOR_ENUM_DEFAULTS = {
    "extracted_bitmap_format": "tiff",
    "biped_weapon_source": BIPED_WEAPON_SOURCE_BIPED_TAG,
    "tag_state": "default",
    "tag_model_override_type": "none",
    "decorator_lod": "1",
    "render_lod": "ALL",
    "import_fp_arms": "NONE",
    "legacy_type": "auto",
}

RENDER_LOD_ITEMS = [
    ("ALL", "All", "Import every available level of detail"),
    ("L1", "L1", "Import the super-low detail geometry"),
    ("L2", "L2", "Import the low detail geometry"),
    ("L3", "L3", "Import the medium detail geometry"),
    ("L4", "L4", "Import the high detail geometry"),
    ("L5", "L5", "Import the default super-high detail geometry"),
    ("L6", "L6", "Import the cinematic geometry"),
]

HALO1_RENDER_LOD_ITEMS = [
    ("ALL", "All", "Import every available level of detail"),
    ("L1", "Super Low", "Import the super-low detail geometry"),
    ("L2", "Low", "Import the low detail geometry"),
    ("L3", "Medium", "Import the medium detail geometry"),
    ("L4", "High", "Import the high detail geometry"),
    ("L5", "Super High", "Import the super-high detail geometry"),
]


def render_lod_items(operator, _context):
    project = render_lod_source_project(operator)
    return HALO1_RENDER_LOD_ITEMS if project is not None and project.game == 'halo1' else RENDER_LOD_ITEMS


def ensure_import_operator_enum_defaults(keywords):
    for prop_name, default in IMPORT_OPERATOR_ENUM_DEFAULTS.items():
        if keywords.get(prop_name) == "":
            keywords[prop_name] = default


FP_ARMS_ITEMS = (
    ('NONE', "None", "Don't import first person arms", 0),
    ('SPARTAN', "Spartan", "Import Spartan first person arms", 1),
    ('ELITE', "Elite", "Import Elite first person arms", 2),
)
H1_FP_ARMS_ITEMS = (
    FP_ARMS_ITEMS[0], ('SPARTAN', "Cyborg", "Import Cyborg first person hands", 1),
)
ODST_FP_ARMS_ITEMS = (
    FP_ARMS_ITEMS[0],
    ('SPARTAN', "ODST", "Import ODST first person arms", 1),
    ('ELITE', "Dare", "Import ONI operative first person arms", 2),
)


def fp_arms_items(operator, context):
    project = render_lod_source_project(operator)
    game = project.game if project is not None else None
    if game == 'halo1':
        return H1_FP_ARMS_ITEMS
    if game == 'halo3odst':
        return ODST_FP_ARMS_ITEMS
    return FP_ARMS_ITEMS

### Steps for adding a new file type ###
########################################
# 1. Add the name of the file extension to formats
# 2. Add this to a file handler's bl_file_extensions (keep each string below 512 bytes)
# 3. Add NWO_Import.invoke condition for type and add to the filter glob
# 4. Add elif for type to NWOImporter.group_filetypes
# 5. Add import function to NWOImporter
# 6. Add an if with conditions for handling this import under NWO_Import.execute
# 7. Update scope variable to importer calls in other python files where appropriate

formats = "jms", "jma", "wrl", "bitmap", "camera_track", "model", "render_model", "collision_model", "physics_model", "sky", "scenario", "scenario_structure_bsp", "scenario_structure_lighting_info", "particle_model", "object", "animation", "prefab", "structure_design", "polyart_asset", "decorator_set", "cinematic"

xref_tag_types = (
    ".crate",
    ".scenery",
    ".device_machine"
)

object_tag_types = (
    ".biped",
    ".crate",
    ".creature",
    ".device_control",
    ".device_dispenser",
    ".effect_scenery",
    ".equipment",
    ".giant",
    ".device_machine",
    ".projectile",
    ".scenery",
    ".spawner",
    ".sound_scenery",
    ".device_terminal",
    ".vehicle",
    ".weapon",
)

filetype_suffixes = (
    ("jms", legacy_model_formats),
    ("jma", legacy_animation_formats),
    ("wrl", (".wrl",)),
    ("bitmap", (".bitmap",)),
    ("camera_track", (".camera_track",)),
    ("render_model", (".render_model", ".gbxmodel")),
    ("collision_model", (".collision_model", ".model_collision_geometry")),
    ("physics_model", (".physics_model", ".physics")),
    ("model", (".model",)),
    ("sky", (".sky",)),
    ("scenario", (".scenario",)),
    ("scenario_structure_bsp", (".scenario_structure_bsp",)),
    ("scenario_structure_lighting_info", (".scenario_structure_lighting_info",)),
    ("particle_model", (".particle_model",)),
    ("object", object_tag_types),
    ("animation", (".model_animation_graph", ".model_animations")),
    ("prefab", (".prefab",)),
    ("structure_design", (".structure_design",)),
    ("polyart_asset", (".polyart_asset",)),
    ("decorator_set", (".decorator_set",)),
    ("cinematic", (".cinematic",)),
)

tag_files_cache = set()
tag_files_by_name_cache = {}
objects_cache = {}

deferred_ops = []

def asset_tag_paths(tag_root: str | Path, *paths: str) -> dict[str, str]:
    """Keep the tag references used for import, independent of extracted sources."""
    root = Path(tag_root)
    return {
        Path(path).suffix: str(Path(path).relative_to(root))
        for path in paths if path
    }

def set_asset(tag_ext: str, ob: bpy.types.Object=None, is_sky=False,
              tag_paths: dict[str, str] | None = None, tag_root: str | Path | None = None):
    scene_nwo = utils.get_scene_props()
    project = utils.get_project()
    halo1 = project is not None and project.game == 'halo1'
    is_model = tag_ext == ".model" or (halo1 and tag_ext == ".gbxmodel")
    if is_sky or is_model or tag_ext in object_tag_types:
        tags_dir = utils.get_tags_path()
        scene_nwo.asset_type = 'sky' if is_sky else 'model'
        if ob is None or ob.type != 'ARMATURE':
            name = ob.name if ob is not None else 'imported tag'
            return utils.print_warning(f"Tried to setup {name} as an asset but it is not an armature")
        render_extension = '.gbxmodel' if halo1 else '.render_model'
        render_path = (tag_paths.get(render_extension, '') if tag_paths is not None
                       else ob.nwo.node_order_source)
        if not render_path.strip():
            return utils.print_warning(f"Tried to setup {ob.name} as an asset but it has no render model tag path")
        if tag_paths is not None and not halo1:
            ob.nwo.node_order_source = render_path
        
        path = Path(render_path).with_suffix("")
        paths = tag_paths or {}
        tag_directory = Path(tag_root) if tag_root is not None else Path(tags_dir)
        def existing_tag(extension: str) -> str:
            relative = (paths.get(extension, '') if tag_paths is not None
                        else str(path.with_suffix(extension)))
            return relative if (tag_directory / relative).exists() else ''
    
        scene_nwo.main_armature = ob
        if not is_sky and not is_model:
            def enable_output_tag(tag_type: str):
                relative = existing_tag(tag_type) if tag_paths is None else paths.get(tag_type, '')
                if relative and (tag_directory / relative).exists():
                    tag_type_no_period = tag_type[1:]
                    setattr(scene_nwo, f"output_{tag_type_no_period}", True)
                    setattr(scene_nwo, f"template_{tag_type_no_period}", relative)
                    
            for tag_type in object_tag_types:
                enable_output_tag(tag_type)
                
        if halo1:
            scene_nwo.template_model = ""
            scene_nwo.template_render_model = render_path
            scene_nwo.template_collision_model = ""
            scene_nwo.template_model_animation_graph = ""
            collision_extension = ".model_collision_geometry"
            animation_extension = ".model_animations"
            physics_extension = ".physics"
        else:
            scene_nwo.template_model = paths.get('.model', str(path.with_suffix('.model')))
            scene_nwo.template_render_model = render_path
            collision_extension = ".collision_model"
            animation_extension = ".model_animation_graph"
            physics_extension = ".physics_model"

        scene_nwo.template_collision_model = existing_tag(collision_extension)
        scene_nwo.template_model_animation_graph = existing_tag(animation_extension)
        if scene_nwo.template_model_animation_graph:
            with AnimationGraphTag(path=tag_directory / scene_nwo.template_model_animation_graph) as animation:
                skeleton_node_names = animation.get_nodes()
                for usage_name, node_index in animation.node_usages().items():
                    usage = usage_name.replace(" ", "_")
                    if 0 <= node_index < len(skeleton_node_names):
                        node = skeleton_node_names[node_index]
                        setattr(scene_nwo, f"node_usage_{usage}", node)
                    
        scene_nwo.template_physics_model = existing_tag(physics_extension)
             
    else:
        match tag_ext:
            case '.scenario' | '.scenario_structure_bsp':
                scene_nwo.asset_type = 'scenario'
            case '.prefab':
                scene_nwo.asset_type = 'prefab'
            case '.particle_model':
                scene_nwo.asset_type = 'particle_model'
            case '.polyart_asset':
                scene_nwo.asset_type = 'polyart'
            case '.decorator_set':
                scene_nwo.asset_type = 'decorator_set'
            case '.camera_track':
                scene_nwo.asset_type = 'camera_track_set'
            case '.cinematic':
                scene_nwo.asset_type = 'cinematic'

def add_function(scene: bpy.types.Scene, name: str, rename: str, ob: bpy.types.Object, armature: bpy.types.Object=None) -> bool:
    func = game_functions.get(name)
    ammo = name.startswith(ammo_names)
    tether = name.startswith(tether_name)
    has_armature = armature is not None # because we handle these differently
    needs_id_prop = False
    id = None
    value_comes_from_scene = False
    value_is_bool = False
    
    if ammo or tether:
        ob[name] = 0.0
        ob.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
        return value_is_bool
    
    if func is None:
        if has_armature:
            id = armature
            needs_id_prop = armature.get(rename) is None
        if needs_id_prop:
            id[rename if id == armature else name] = 0.0
            id.id_properties_ui(rename if id == armature else name).update(min=0, max=1, subtype='FACTOR')
        ob[name] = 0.0
        ob.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
    else:
        if func.function_type == GameFunctionType.CONSTANT:
            return value_is_bool
        value_is_bool = isinstance(func.default_value, bool)
        value_comes_from_scene = func.attribute_type == 'VIEW_LAYER'
        if value_comes_from_scene:
            id = scene
            needs_id_prop = scene.get(name) is None
        elif has_armature:
            id = armature
            needs_id_prop = armature.get(rename) is None
        
        if value_is_bool:
            if needs_id_prop:
                id[rename if id == armature else name] = func.default_value
            ob[name] = func.default_value
        else:
            if needs_id_prop:
                id[rename if id == armature else name] = float(func.default_value)
                id.id_properties_ui(rename if id == armature else name).update(min=0, max=1, subtype='FACTOR')
            ob[name] = float(func.default_value)
            ob.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
    
    if id is not None:
        result = ob.driver_add(f'["{name}"]')
        driver = result.driver
        driver.type = 'SCRIPTED'
        var = driver.variables.new()
        var.name = "var"
        var.type = 'SINGLE_PROP'
        if value_comes_from_scene:
            var.targets[0].id_type = 'SCENE'
        else:
            id.update_tag(refresh={'DATA'})
        var.targets[0].id = id
        var.targets[0].data_path = f'["{rename}"]'
        driver.expression = var.name
        
    return value_is_bool


def set_variant_property(armature, model, selection):
    if armature is None:
        return
    armature['variant'] = model.get_variant_value(selection)
    armature.id_properties_ui('variant').update(min=0, max=1, subtype='FACTOR')


def add_object_functions(scene, ob, armature, functions):
    """Evaluate imported mappings on the armature, then expose them on meshes."""
    from ..tags.function_driver import set_scalar_driver_expression
    decoded = getattr(functions, 'decoded', {})
    owner = armature if armature is not None else ob
    for name, function in decoded.items():
        if name not in owner:
            owner[name] = 0.0
            owner.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
        curve = owner.driver_add(f'["{bpy.utils.escape_identifier(name)}"]')
        driver = curve.driver
        driver.type = 'SCRIPTED'
        while driver.variables:
            driver.variables.remove(driver.variables[0])
        variables = {}

        def variable(source):
            if source in {'one', 'zero', 'none', ''}:
                return '1.0' if source == 'one' else '0.0'
            if source not in variables:
                if source not in decoded:
                    add_function(scene, source, source, ob, armature)
                var = driver.variables.new()
                var.name = f'v{len(variables)}'
                var.type = 'SINGLE_PROP'
                func = game_functions.get(source)
                from_scene = func is not None and func.attribute_type == 'VIEW_LAYER'
                var.targets[0].id_type = 'SCENE' if from_scene else 'OBJECT'
                var.targets[0].id = scene if from_scene else owner
                var.targets[0].data_path = f'["{bpy.utils.escape_identifier(source)}"]'
                variables[source] = var.name
            return variables[source]

        fps = scene.render.fps / scene.render.fps_base
        expression = function.driver_expression(variable, f'frame/{fps:.9g}')
        set_scalar_driver_expression(owner, curve, expression)
        if ob != owner:
            add_function(scene, name, name, ob, armature)
    owner.update_tag(refresh={'DATA'})


def bind_sequence_drivers(scene, ob, slot_index):
    """Bind every sequence texture, including copied and reused materials."""
    import ast
    material = ob.material_slots[slot_index].material
    tree = material.node_tree
    if tree is None or tree.animation_data is None:
        return material
    curves = [curve for curve in tree.animation_data.drivers
              if curve.data_path.endswith('.image_user.frame_offset')
              or curve.data_path.startswith('["_foundry_driver_')]
    owner = ob.parent if ob.parent is not None else ob
    if any(var.targets[0].id_type != 'NODETREE' and var.targets[0].id is not None
           and var.targets[0].id not in {owner, ob, scene}
           for curve in curves for var in curve.driver.variables):
        material = material.copy()
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        ob.material_slots[slot_index].material = material
        curves = [curve for curve in material.node_tree.animation_data.drivers
                  if curve.data_path.endswith('.image_user.frame_offset')
                  or curve.data_path.startswith('["_foundry_driver_')]
    for curve in curves:
        for var in curve.driver.variables:
            if var.targets[0].id_type == 'NODETREE':
                var.targets[0].id = material.node_tree
                continue
            name = ast.literal_eval(var.targets[0].data_path[1:-1])
            add_function(scene, name, name, ob, ob.parent)
            func = game_functions.get(name)
            from_scene = func is not None and func.attribute_type == 'VIEW_LAYER'
            var.targets[0].id_type = 'SCENE' if from_scene else 'OBJECT'
            var.targets[0].id = scene if from_scene else owner
            ammo = name.startswith(ammo_names)
            tether = name.startswith(tether_name)
            if ammo or tether:
                var.targets[0].id = ob
                digit_driver = ob.driver_add(f'["{name}"]').driver
                digit_driver.type = 'SCRIPTED'
                while digit_driver.variables:
                    digit_driver.variables.remove(digit_driver.variables[0])
                digit = digit_driver.variables.new()
                digit.name = 'var'
                digit.type = 'SINGLE_PROP'
                digit.targets[0].id = owner
                digit.targets[0].data_path = '["Tether Distance"]' if tether else '["Ammo"]'
                place = {'ones': 1, 'tens': 10, 'hundreds': 100}.get(name.rpartition('_')[2], 1)
                length = material.node_tree.path_resolve(curve.data_path.removesuffix('.frame_offset')).frame_duration
                digit_driver.expression = f'(floor(var/{place})%10)/{max(length-1, 1)}'
    return material
        

class State(Enum):
    all_states = -1
    default = 0
    minor = 1
    medium = 2
    major = 3
    destroyed = 4

state_items = [
    ("all_states", "All Damage States", "Includes all damage stages"),
    ("default", "Default", "State before any damage has been taken"),
    ("minor", "Minor", "Minor Damage"),
    ("medium", "Medium", "Medium Damage"),
    ("major", "Major", "Major Damage"),
    ("destroyed", "Destroyed", "Object's destroyed state"),
]

class XREF:
    def __init__(self, object_name: str, xref_path: str, xref_name: str):
        self.preferred_type = ".crate"
        self.preferred_dir = None
        if object_name.lower().startswith("?"):
            self.preferred_type = ".device_machine"
        if xref_path:
            source_path = PureWindowsPath(xref_path.replace('/', '\\'))
            parts = source_path.parts
            data_index = next((i for i, part in enumerate(parts)
                               if part.casefold() == 'data'), None)
            tags_index = next((i for i, part in enumerate(parts)
                               if part.casefold() == 'tags'), None)
            start = ((data_index + 1) if data_index is not None else
                     (tags_index + 1) if tags_index is not None else
                     0 if not source_path.is_absolute() else None)
            if start is not None:
                relative_parts = list(parts[start:-1])
                if relative_parts and relative_parts[-1].casefold() in {'render', 'collision', 'physics'}:
                    relative_parts.pop()
                if not any(part in {'.', '..'} for part in relative_parts):
                    self.preferred_dir = Path(utils.get_tags_path(), *relative_parts)
        
        self.name = xref_name or PureWindowsPath(xref_path.replace('/', '\\')).stem


class NWO_OT_ConvertScene(bpy.types.Operator):
    bl_label = "Convert Toolset Scene"
    bl_idname = "nwo.convert_scene"
    bl_description = "Convert an io_scene_halo JMS/ASS scene to Foundry export properties"
    bl_options = {'REGISTER', 'UNDO'}

    selected_only: bpy.props.BoolProperty(
        name="Selected Only", description="Convert only selected objects")
    include_disabled_collections: bpy.props.BoolProperty(
        name="Include Disabled Collections", default=True,
        description="Include objects in collections excluded from the current view layer or disabled in the viewport; Selected Only still limits conversion to selected objects")
    convert_scale: bpy.props.BoolProperty(
        name="Convert Scale", default=True,
        description="Convert geometry from Halo scale to the current Foundry scene scale; ignored when the scene uses Halo scale")
    convert_forward: bpy.props.BoolProperty(
        name="Convert Forward", default=True,
        description="Rotate geometry from Halo +X forward to the current Foundry scene forward; ignored when the scene uses +X forward")
    jms_type: bpy.props.EnumProperty(
        name="Scene Type", default='auto',
        items=[('auto', "Auto", "Use the current asset type"),
               ('model', "Model", ""), ('scenario', "Scenario", "")])
    bsp_name: bpy.props.StringProperty(
        name="BSP Name",
        description="Optional BSP name for scenario conversion; otherwise preserve BSP assignments or use source collection names")
    top_level_bsps: bpy.props.BoolProperty(
        name="Use Top-Level Collections as BSPs",
        description="Use each direct child of Scene Collection as a BSP named after that collection, including hidden and empty collections; collection assignments apply even with Selected Only enabled",
        default=False)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and utils.current_project_valid()

    def invoke(self, context, event):
        self.jms_type = 'scenario' if utils.get_scene_props().asset_type in {'scenario', 'prefab'} else 'model'
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        scene_nwo = utils.get_scene_props()
        self.layout.prop(self, 'selected_only')
        self.layout.prop(self, 'include_disabled_collections')
        self.layout.label(text="Source: Halo Scale, +X Forward")
        scale = 'Blender Scale' if scene_nwo.scale == 'blender' else 'Halo Scale'
        forward = {'x': '+X', 'x-': '-X', 'y': '+Y', 'y-': '-Y'}[scene_nwo.forward_direction]
        self.layout.label(text=f"Scene: {scale}, {forward} Forward")
        row = self.layout.row()
        row.enabled = scene_nwo.scale != 'max'
        row.prop(self, 'convert_scale')
        row = self.layout.row()
        row.enabled = scene_nwo.forward_direction != 'x'
        row.prop(self, 'convert_forward')
        self.layout.prop(self, 'jms_type', expand=True)
        if self.jms_type == 'scenario' or (self.jms_type == 'auto' and
                utils.get_scene_props().asset_type in {'scenario', 'prefab'}):
            self.layout.prop(self, 'top_level_bsps')
            row = self.layout.row()
            row.enabled = not self.top_level_bsps
            row.prop(self, 'bsp_name')

    def execute(self, context):
        if not hasattr(bpy.types.Material, 'ass_jms') or not hasattr(bpy.types.Mesh, 'ass_jms'):
            self.report({'WARNING'}, "Enable the Halo Blender Toolset (io_scene_halo) before converting")
            return {'CANCELLED'}
        from ..legacy.scene_converter import HaloSceneConverter
        objects = list(context.selected_objects if self.selected_only else context.scene.objects)
        if not self.include_disabled_collections:
            enabled_objects = set()

            def collect_enabled(layer):
                if layer.exclude or layer.collection.hide_viewport:
                    return
                enabled_objects.update(layer.collection.objects)
                for child in layer.children:
                    collect_enabled(child)

            collect_enabled(context.view_layer.layer_collection)
            objects = [ob for ob in objects if ob in enabled_objects]
        if any(not ob.get('foundry_converted_from_toolset') and
               (ob.library or (ob.data and ob.data.library)) for ob in objects):
            self.report({'WARNING'}, "Make linked objects and their data local before converting")
            return {'CANCELLED'}
        is_model = self.jms_type == 'model' or (self.jms_type == 'auto' and
                    utils.get_scene_props().asset_type not in {'scenario', 'prefab'})
        converter = HaloSceneConverter(NWOImporter(context, existing_scene=True), is_model,
                                       bsp_name=self.bsp_name, top_level_bsps=self.top_level_bsps)
        converted = converter.convert(objects, convert_scale=self.convert_scale,
                                      convert_forward=self.convert_forward)
        if converter.warnings:
            for warning in sorted(converter.warnings):
                utils.print_warning(warning)
            self.report({'WARNING'}, f"Converted {converted} objects; see output for unsupported source properties")
        else:
            self.report({'INFO'}, f"Converted {converted} objects to Foundry")
        return {'FINISHED'}


class NWO_Import(bpy.types.Operator):
    bl_label = "Foundry Import"
    bl_idname = "nwo.foundry_import"
    bl_description = "Imports a variety of filetypes and sets them up for Foundry. Currently supports: JMA, JMS, ASS, WRL diagnostics, bitmap tags, camera_track tags, model tags (collision & skeleton only)"
    
    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()
    
    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'SKIP_SAVE', 'HIDDEN'})
    
    filepath: bpy.props.StringProperty(
        name='Filepath',
        subtype='FILE_PATH',
        options={"HIDDEN"},
    )

    import_template: bpy.props.EnumProperty(
        name="Template",
        description="Preset for common import goals",
        items=IMPORT_TEMPLATE_ITEMS,
        options={'SKIP_SAVE'},
        default=IMPORT_TEMPLATE_DEFAULT,
        update=import_template_update,
    )
    
    # find_shader_paths: bpy.props.BoolProperty(
    #     name="Find Shader Paths",
    #     description="Searches the tags folder after import and tries to find shader/material tags which match the name of importer materials",
    #     default=True,
    # )
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )

    build_materials_for_project: bpy.props.BoolProperty(
        name="Build Materials for Current Project",
        description="Convert imported materials to the current project's game nodes and convert packed bitmap channels where possible. Unsupported effects are approximated. Halo 2 is supported as a source only",
        default=False,
    )
    
    import_images_to_blender: bpy.props.BoolProperty(
        name="Import to Blend",
        description="Imports images into the blender after extracting bitmaps from the game",
        default=True,
    )
    images_fake_user: bpy.props.BoolProperty(
        name="Set Fake User",
        description="Sets the fake user property on imported images",
        default=True,
    )
    extracted_bitmap_format: bpy.props.EnumProperty(
        name="Image Format",
        description="Sets format to save the extracted bitmap as",
        items=[
            ("tiff", "TIFF", ""),
            ("png", "PNG", ""),
            ("jped", "JPEG", ""),
            ("bmp", "BMP", ""),
        ]
    )
    
    camera_track_animation_scale: bpy.props.FloatProperty(
        name='Animation Scale',
        default=1,
        min=1,
    )
    
    legacy_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    scope: bpy.props.StringProperty(
        name="Scope",
        options={"HIDDEN", "SKIP_SAVE"}
    )
    
    reuse_armature: bpy.props.BoolProperty(
        name="Reuse Scene Armature",
        description="Will reuse the main blend scene armature for this model instead of importing a new one",
        default=False,
    )
    tag_render: bpy.props.BoolProperty(
        name="Import Render Geometry",
        default=True,
    )
    render_lod: bpy.props.EnumProperty(
        name="LOD",
        description="Level of detail to import from Halo 1 or Halo 2 models",
        items=render_lod_items,
        default=0,
        options={'SKIP_SAVE'},
    )
    tag_markers: bpy.props.BoolProperty(
        name="Import Markers",
        default=True,
    )
    tag_collision: bpy.props.BoolProperty(
        name="Import Collision",
        default=False,
    )
    tag_physics: bpy.props.BoolProperty(
        name="Import Physics",
        default=False,
    )
    tag_animation: bpy.props.BoolProperty(
        name="Import Animation Graph",
        description="Imports animations, renames, and animation events. This importer is work in progress and additional functionaility is still to be added",
        options={'SKIP_SAVE'},
        default=False,
    )
    
    tag_variant: bpy.props.StringProperty(
        name="Variant",
        options={'SKIP_SAVE'},
        description="Optional field to declare a variant to import. If this field is left blank, all variants will be imported (except if this is for a cinematic, in which case the first variant will be used)"
    )

    tag_permutation: bpy.props.StringProperty(
        name="Permutation",
        options={'SKIP_SAVE'},
        description="Optional Halo 1 model permutation to import. Leave blank to import all permutations",
    )
    
    import_variant_children: bpy.props.BoolProperty(
        name="Import Variant Child Objects",
        description="Imports the child objects associated with this model variant",
        options={'SKIP_SAVE'},
    )
    
    import_biped_weapon: bpy.props.BoolProperty(
        name="Import Biped Weapons",
        description="Imports all the biped's weapons if it has any",
    )

    biped_weapon_source: bpy.props.EnumProperty(
        name="Biped Weapon",
        description="Weapon source to import when importing biped weapons",
        items=biped_weapon_source_items,
    )
    
    tag_state: bpy.props.EnumProperty(
        name="Model State",
        description="The damage state to import. Only valid when a variant is set",
        default=1,
        items=state_items,
    )
    
    tag_model_override_type: bpy.props.EnumProperty(
        name="Model Override",
        description="The render model type to read from the model override block",
        items=[
            ('none', "None", ""),
            ('campaign', "Campaign", ""),
            ('multiplayer', "Multiplayer", ""),
            ('firefight', "Firefight", ""),
            ('mainmenu', "Main Menu", ""),
        ]
    )
    
    tag_import_attachments: bpy.props.BoolProperty(
        name="Attachments",
        description="Import object tag attachments. Currently supports lights and cheap lights"
    )
    
    setup_as_asset: bpy.props.BoolProperty(
        name="Setup as Asset",
        default=False,
        description="Updates the scene asset settings so that this object can be immediately reimported into the game"
    )
    
    tag_zone_set: bpy.props.StringProperty(
        name="Zone Set",
        options={'SKIP_SAVE'},
        description="Optional field to declare a zone set to import. This will limit the scope of imported BSPs to those within the zone set. If this field is left blank, all BSPs will be imported"
    )
    
    tag_bsp: bpy.props.StringProperty(
        name="BSP",
        options={'SKIP_SAVE'},
        description="Halo 1 or Halo 2 BSP name to import. Leave blank to import all BSPs",
    )

    tag_bsp_render_only: bpy.props.BoolProperty(
        name="Render Geometry Only",
        description="Skips importing bsp data like collision and portals. Use this if you aren't importing the BSP back into the game"
    )
    
    tag_bsp_import_havok: bpy.props.BoolProperty(
        name="Import Havok Collision (WIP)",
        description="Imports serialized Havok collision from scenario_structure_bsp tags as standalone collision meshes. Experimental.",
        default=False,
    )

    tag_bsp_import_geometry: bpy.props.BoolProperty(
        name="Import BSP Geometry",
        description="Imports the all geometry data within bsp tags",
        default=True,
    )

    tag_bsp_skip_structure_merge: bpy.props.BoolProperty(
        name="Skip Structure Merge",
        description="Keeps imported BSP clusters as separate objects instead of joining them into one structure mesh",
        default=False,
    )

    tag_bsp_merge_render_collision: bpy.props.BoolProperty(
        name="Merge Render and Collision",
        description="Reconstructs shared render and collision surfaces for Halo 1 BSPs. Disable to import the original render and collision meshes separately",
        default=True,
    )
    
    tag_import_design: bpy.props.BoolProperty(
        name="Import Structure Design",
        description="Imports geometry from scenario structure design tags. Ignored if render only is set",
        default=True,
    )
    
    tag_sky: bpy.props.StringProperty(
        name="Sky",
        description="Enter the tag relative path to the sky to import with this Scenario",
    )
    
    tag_cinematic_import_scenario: bpy.props.BoolProperty(
        name="Import Scenario",
        default=True,
    )
    
    tag_cinematic_import_actors: bpy.props.BoolProperty(
        name="Import Actors",
        default=True,
    )
    
    tag_cinematic_scene: bpy.props.StringProperty(
        name="Scene",
        options={'SKIP_SAVE'},
        description="Select a specific cinematic scene to import, or all (default)",
    )
    
    tag_scenario_import_objects: bpy.props.BoolProperty(
        name="Import Scenario Objects",
        description="Imports scenario objects. Added to an exclude collection by default",
        default=False,
    )
    
    tag_scenario_import_decals: bpy.props.BoolProperty(
        name="Import Scenario Decals",
        description="Imports scenario decals. Added to an exclude collection by default",
        default=False,
    )
    
    tag_scenario_import_decorators: bpy.props.BoolProperty(
        name="Import Scenario Decorators",
        description="Imports scenario decorators. These won't export by default unless you enable the option in the asset editor panel to control decorators from Blender",
        default=False,
    )
    
    decorator_single_lod: bpy.props.BoolProperty(
        name="Only single LOD",
        description="Import only a single level of detail for this decorator"
    )
    
    decorator_lod: bpy.props.EnumProperty(
        name="Decorator LOD",
        description="Level of detail for imported decorators",
        items=[
            ("1", "Highest", ""),
            ("2", "Medium", ""),
            ("3", "Low", ""),
            ("4", "Lowest", ""),
        ]
    )
    
    decorator_type: bpy.props.StringProperty(
        name="Decorator Type",
        options={'SKIP_SAVE'},
        description="Optional field to declare a decorator type to import. If this field is left blank, all types will be imported"
    )
    
    tag_import_lights: bpy.props.BoolProperty(
        name="Import Lights",
        description="Imports the all lights found in scenario_structure_lighting_info tags",
        default=True,
    )
    
    tag_animation_filter: bpy.props.StringProperty(
        name="Animation Filter",
        options={'SKIP_SAVE'},
        description="Filter for the animations to import. Animations that don't contain the specified strings (space or colon delimited) will be skipped"
    )
    
    graph_import_animations: bpy.props.BoolProperty(
        name="Import Animations",
        default=True,
        description="Imports animations from the graph"
    )
    graph_bake_to_control_rig: bpy.props.BoolProperty(
        name="Bake to Control Rig",
        default=True,
        description="Bakes imported animations to an existing or newly built control rig",
    )
    graph_scale_animations_to_skeleton: bpy.props.BoolProperty(
        name="Root Translation / Scale Only",
        default=False,
        description="Applies translation and scale to root/pedestal bones and their direct children; tagged animations always use this, and the option applies it globally with idle-based foot height correction"
    )
    graph_import_pca_data: bpy.props.BoolProperty(
        name="Import PCA Data",
        default=True,
        description="Imports animations with their PCA (face animation) data"
    )
    graph_generate_renames: bpy.props.BoolProperty(
        name="Generate Animation Renames and Copies",
        default=True,
        description="Reads graph paths to add complete hierarchy copies and individual animation renames"
    )
    graph_import_events: bpy.props.BoolProperty(
        name="Import Animation Events",
        default=True,
        description="Imports frame events from the graph tag and frame event list"
    )
    graph_import_ik_chains: bpy.props.BoolProperty(
        name="Import IK Chains",
        default=True,
        description="Sets up the IK chains graph tag block in blender"
    )
    
    import_fp_arms: bpy.props.EnumProperty(
        name="FP Arms",
        description="Imports the First person arms along with the weapon and joins the skeletons",
        items=fp_arms_items,
        default=0,
    )
    
    legacy_type: bpy.props.EnumProperty(
        name="JMS/ASS Type",
        description="Whether the importer should try to import a JMS/ASS file as a model, or bsp. Auto will determine this based on current asset type and contents of the JMS/ASS file",
        items=[
            ("auto", "Auto", ""),
            ("model", "Model", ""),
            ("bsp", "BSP", ""),
        ]
    )
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not",
        options=set(),
    )
    
    import_as_instanced_collection: bpy.props.BoolProperty(
        name="Import as Game Marker",
        description="Imports the object as a game marker with an instanced collection",
        default=True
    )
    
    from_vert_normals: bpy.props.BoolProperty(
        name="Store Model Vertex Normals",
        description="Stores a models vertex normals so that it can be reimported in game with the exact same vertex order. This is done automatically for PCA meshes, this option just applies the same to everything. Any edits to meshes with this setting will probably break normals on export"
    )
    
    place_at_mouse: bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    mouse_x: bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    mouse_y: bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    convert_to_instance: bpy.props.BoolProperty(
        name="Convert to Instance Geometry",
        description="Converts a model to instanced geometry",
    )
    
    generate_frames: bpy.props.BoolProperty(
        name="Generate Missing Frames",
        description="Generates frames where possible for JMA imported animations. This is needed because base animations are missing a final frame, and replacement animations their first frame, which would have been present in their source file. If the missing frames have already been corrected, disable this option",
    )
    
    build_control_rig: bpy.props.BoolProperty(
        name="Build Control Rig",
        description="Builds an FK & IK control rig for imported models",
        default=False,
    )

    convert_animations: bpy.props.BoolProperty(
        name="Convert Animations for Project",
        description="Convert animation names, turn poses, aim/look overlays, and Halo 4 / H2AMP locomote composites to the current project game",
        default=True,
    )

    use_import_info: bpy.props.BoolProperty(
        name="Use Import Info",
        description="Imports embedded JMS, ASS, and JMA source data instead of compiled tag data when available. GR2 source data is currently ignored",
        default=True,
    )
    
    def execute(self, context):
        global deferred_ops
        deferred_ops = []
        scene_nwo = utils.get_scene_props()
        scene_nwo_export = utils.get_export_props()
        failed = False
        filepaths = [self.directory + f.name for f in self.files]
        if self.filepath and self.filepath not in filepaths:
            filepaths.append(self.filepath)
            
        if not filepaths:
            self.report({"WARNING"}, "No files to import")
            return {'CANCELLED'}
        
        start = time.perf_counter()
        imported_objects = []
        imported_actions = []
        armature = None
        starting_materials = set(bpy.data.materials)
        for_cinematic = scene_nwo.asset_type == 'cinematic'
        self.anchor = None
        self.nothing_imported = False
        self.user_cancelled = False
        utils.set_object_mode(context)
        global last_used_variant
        last_used_variant = self.tag_variant
        if self.tag_variant == "all_variants":
            self.tag_variant = ""
        if self.tag_permutation == "all_permutations":
            self.tag_permutation = ""
        if self.tag_zone_set == "all_zone_sets":
            self.tag_zone_set = ""
        if self.decorator_type == "all_types":
            self.decorator_type = ""
        if self.tag_sky == "none":
            self.tag_sky = ""
        if self.tag_cinematic_scene == "all":
            self.tag_cinematic_scene = ""
            
        if self.always_extract_bitmaps:
            clear_path_cache()
            
        set_animation_index = scene_nwo.asset_type in {'model', 'animation'}
        scene_collection_map = defaultdict(set)
        scene_datas = []

        with TemporaryDirectory(prefix="foundry_import_info_") as import_info_directory, utils.ExportManager():
            utils.clear_output()
            
            if not self.place_at_mouse and scene_nwo_export.show_output:
                utils.show_output()  # open Foundry Output so users can see progress
                scene_nwo_export.show_output = False
            try:
                utils.print_section("FOUNDRY IMPORTER")
                
                # Read tags using their source kit without changing the scene project.
                # Only checking the last file for speed (last file is always self.filepath if there was one).
                # If another file is a tag, too bad, we won't try to identify its source project
                utils.set_import_context_from_filepath(Path(filepaths[-1]))

                scope_list = []
                if self.scope:
                    scope_list = self.scope.split(',')
                    
                importer = NWOImporter(context, filepaths, scope_list)
                importer.build_materials_for_project = self.build_materials_for_project
                importer.render_lod = self.render_lod
                if self.use_import_info:
                    importer.configure_import_info(Path(import_info_directory))
                    importer.add_import_info_sources(filepaths)
                importer.graph_bake_to_control_rig = self.graph_bake_to_control_rig
                importer.convert_animations = self.convert_animations
                switch_blender_scene = None
                
                mouse_matrix = utils.matrix_from_mouse(self.mouse_x, self.mouse_y)
                
                imported_animations = []
                current_animations = set(scene_nwo.animations[:])
                
                if self.place_at_mouse and not self.convert_to_instance:
                    tag_path = filepaths[0]
                    marker = bpy.data.objects.new(name=Path(tag_path).with_suffix("").name, object_data=None)
                    marker.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                    marker.nwo.marker_game_instance_tag_name = utils.relative_path(tag_path)
                    if 'decorator_set' in importer.extensions:
                        marker.nwo.marker_game_instance_tag_variant_name = self.decorator_type
                    else:
                        marker.nwo.marker_game_instance_tag_variant_name = self.tag_variant
                    
                    marker.matrix_world = mouse_matrix
                
                
                if 'jms' in importer.extensions:
                    imported_objects.extend(importer.import_jms_files(importer.sorted_filepaths["jms"], self.legacy_type))

                if 'wrl' in importer.extensions:
                    importer.import_wrl_files(importer.sorted_filepaths["wrl"])


                            
                if 'jma' in importer.extensions:
                    jma_files = importer.sorted_filepaths["jma"]
                    arm = None
                    arm = utils.get_rig_prioritize_active(context)
                        
                    if arm is None:
                        utils.print_warning("No armature in scene, cannot import JMA files")
                    else:
                        if importer.needs_scaling:
                            utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, scene_nwo.forward_direction, 'x', objects=[arm], actions=[])
                        imported_animations = importer.import_jma_files(jma_files, arm)
                        if imported_animations:
                            imported_actions.extend(imported_animations)
                            
                        if importer.needs_scaling:
                            utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', scene_nwo.forward_direction, objects=[arm], actions=imported_animations)
                            
                        if imported_animations and set_animation_index:
                            scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
                        
                if 'model' in importer.extensions:
                    importer.tag_render = self.tag_render
                    importer.tag_markers = self.tag_markers
                    importer.tag_collision = self.tag_collision
                    importer.tag_physics = self.tag_physics
                    importer.tag_animation = self.tag_animation
                    importer.tag_variant = self.tag_variant.lower()
                    importer.tag_permutation = self.tag_permutation.lower()
                    importer.tag_state = State[self.tag_state].value
                    importer.tag_model_override_type = RenderModelOverrideType(self.tag_model_override_type) if self.tag_model_override_type != 'none' else None
                    importer.tag_animation_filter = self.tag_animation_filter
                    importer.graph_import_animations = self.graph_import_animations
                    importer.graph_import_pca_data = self.graph_import_pca_data
                    importer.graph_generate_renames = self.graph_generate_renames
                    importer.graph_import_events = self.graph_import_events
                    importer.graph_scale_animations_to_skeleton = self.graph_scale_animations_to_skeleton
                    importer.graph_import_ik_chains = self.graph_import_ik_chains
                    importer.import_variant_children = self.import_variant_children
                    importer.setup_as_asset = self.setup_as_asset
                    importer.tag_import_lights = self.tag_import_lights
                    importer.build_control_rig = self.build_control_rig
                    model_files = importer.sorted_filepaths["model"]
                    existing_armature = None
                    if self.reuse_armature:
                        existing_armature = utils.get_rig_prioritize_active(context)
                        if existing_armature is not None:
                            arm_pose = existing_armature.data.pose_position
                            existing_armature.data.pose_position = 'REST'
                            context.view_layer.update()
                            
                    imported_model_objects, imported_animations = importer.import_models(model_files, existing_armature)
                        
                    if existing_armature is not None:
                        existing_armature.data.pose_position = arm_pose
                    
                    if imported_animations and set_animation_index:
                        scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
                        
                    imported_objects.extend(imported_model_objects)
                    
                    
                elif 'object' in importer.extensions:
                    if self.place_at_mouse:
                        if self.convert_to_instance:
                            object_files = [importer.sorted_filepaths["object"][0]]
                            model_objects, variant = importer.import_object(object_files, None, for_instance_conversion=True)
                            if model_objects:
                                converter = ModelInstance(object_files[0], variant, utils.is_corinth(context))
                                converter.from_objects(model_objects)
                                to_instance_objects = converter.to_instance(context.collection if context.collection else context.scene.collection)
                                imported_objects.extend(to_instance_objects)
                                converter.clean_up()
                                
                                if scene_nwo.maintain_marker_axis:
                                    converter.instance.matrix_world = mouse_matrix @ Matrix.Rotation(importer.from_x_rot, 4, 'Z')
                                else:
                                    converter.instance.matrix_world = mouse_matrix
                                
                        else:
                            key = marker.nwo.marker_game_instance_tag_name, marker.nwo.marker_game_instance_tag_variant_name
                            game_object_collection = importer.get_cached_game_object_collection(*key)
                            imported_object_objects = []
                            if game_object_collection is None:
                                game_object_collection = importer.import_object(marker, None)
                                if game_object_collection is not None:
                                    merged_collection = merge_collection(game_object_collection)
                                    imported_object_objects = game_object_collection.all_objects
                                    context.scene.collection.children.unlink(game_object_collection)
                                    game_object_collection = importer.cache_game_object_collection(merged_collection, *key)
                            if game_object_collection is not None:
                                marker.instance_type = 'COLLECTION'
                                marker.instance_collection = game_object_collection
                                marker.nwo.marker_instance = True
                                imported_objects.append(marker)
                                context.collection.objects.link(marker)
                                marker.select_set(True)
                                context.view_layer.objects.active = marker
                        
                    else:
                        importer.tag_model_override_type = RenderModelOverrideType(self.tag_model_override_type) if self.tag_model_override_type != 'none' else None
                        importer.tag_render = self.tag_render
                        importer.tag_markers = self.tag_markers
                        importer.tag_collision = self.tag_collision
                        importer.tag_physics = self.tag_physics
                        importer.tag_animation = self.tag_animation
                        importer.tag_variant = self.tag_variant.lower()
                        importer.tag_permutation = self.tag_permutation.lower()
                        importer.tag_state = State[self.tag_state].value
                        importer.tag_animation_filter = self.tag_animation_filter
                        importer.graph_import_animations = self.graph_import_animations
                        importer.graph_import_pca_data = self.graph_import_pca_data
                        importer.graph_generate_renames = self.graph_generate_renames
                        importer.graph_import_events = self.graph_import_events
                        importer.graph_scale_animations_to_skeleton = self.graph_scale_animations_to_skeleton
                        importer.graph_import_ik_chains = self.graph_import_ik_chains
                        importer.import_variant_children = self.import_variant_children
                        importer.import_biped_weapon = self.import_biped_weapon
                        importer.biped_weapon_source = self.biped_weapon_source
                        importer.setup_as_asset = self.setup_as_asset
                        importer.import_fp_arms = FPARMS[self.import_fp_arms]
                        # importer.from_vert_normals = self.from_vert_normals
                        importer.tag_import_lights = self.tag_import_lights
                        importer.build_control_rig = self.build_control_rig
                        importer.tag_import_attachments = self.tag_import_attachments
                        object_files = importer.sorted_filepaths["object"]
                        existing_armature = None
                        if self.reuse_armature:
                            existing_armature = utils.get_rig_prioritize_active(context)
                            if existing_armature is not None:
                                arm_pose = existing_armature.data.pose_position
                                existing_armature.data.pose_position = 'REST'
                                context.view_layer.update()
                        
                        imported_object_objects, imported_animations = importer.import_object(object_files, existing_armature)
                            
                        if existing_armature is not None:
                            existing_armature.data.pose_position = arm_pose
                            
                        imported_objects.extend(imported_object_objects)
                        
                        if imported_animations and set_animation_index:
                            scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
                    
                elif 'render_model' in importer.extensions:
                    importer.tag_render = self.tag_render
                    importer.tag_markers = self.tag_markers
                    # importer.from_vert_normals = self.from_vert_normals
                    importer.build_control_rig = self.build_control_rig
                    render_model_files = importer.sorted_filepaths["render_model"]
                    existing_armature = None
                    if self.reuse_armature:
                        existing_armature = utils.get_rig_prioritize_active(context)
                    
                    imported_render_objects = []
                    for file in render_model_files:
                        print(f'Importing Render Model Tag: {Path(file).with_suffix("").name} ')
                        render_model_objects, armature = importer.import_render_model(file, context.scene.collection, existing_armature, set(), skip_print=True)
                        imported_render_objects.extend(render_model_objects)
                        
                    imported_objects.extend(imported_render_objects)

                elif {'collision_model', 'physics_model'}.intersection(importer.extensions):
                    # Capture the selection before importing a fallback skeleton.
                    selected_armature = next((ob for ob in context.selected_objects
                                              if ob == context.object and ob.type == 'ARMATURE'), None)
                    if selected_armature is None:
                        selected_armature = next((ob for ob in context.selected_objects
                                                  if ob.type == 'ARMATURE'), None)
                    for kind in ('collision_model', 'physics_model'):
                        for file in importer.sorted_filepaths.get(kind, ()):
                            utils.print_section(f'Importing {kind.replace("_", " ").title()} Tag: {Path(file).name}')
                            imported_objects.extend(importer.import_standalone_model_geometry(
                                file, kind, selected_armature))

                elif 'sky' in importer.extensions:
                    importer.tag_render = self.tag_render
                    importer.tag_markers = self.tag_markers
                    importer.tag_animation = self.tag_animation
                    importer.tag_animation_filter = self.tag_animation_filter
                    importer.graph_import_animations = self.graph_import_animations
                    importer.graph_import_pca_data = self.graph_import_pca_data
                    importer.graph_generate_renames = self.graph_generate_renames
                    importer.graph_import_events = self.graph_import_events
                    importer.graph_scale_animations_to_skeleton = self.graph_scale_animations_to_skeleton
                    importer.graph_import_ik_chains = self.graph_import_ik_chains
                    importer.setup_as_asset = self.setup_as_asset
                    importer.build_control_rig = self.build_control_rig
                    existing_armature = utils.get_rig_prioritize_active(context) if self.reuse_armature else None
                    sky_objects, sky_animations = importer.import_skies(
                        importer.sorted_filepaths["sky"], existing_armature)
                    imported_objects.extend(sky_objects)
                    if sky_animations and set_animation_index:
                        scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
                    
                elif 'animation' in importer.extensions:
                    importer.tag_animation_filter = self.tag_animation_filter
                    importer.graph_import_animations = self.graph_import_animations
                    importer.graph_import_pca_data = self.graph_import_pca_data
                    importer.graph_generate_renames = self.graph_generate_renames
                    importer.graph_import_events = self.graph_import_events
                    importer.graph_scale_animations_to_skeleton = self.graph_scale_animations_to_skeleton
                    importer.graph_import_ik_chains = self.graph_import_ik_chains
                    animation_files = importer.sorted_filepaths['animation']
                    imported_animations = []
                    if context.object and context.object.type == 'ARMATURE':
                        existing_armature = context.object
                    else:
                        existing_armature = utils.get_rig_prioritize_active(context)
                    if existing_armature is None:
                        utils.print_warning("No armature found, cannot import animations. Ensure you have the appropriate armature for this animation graph import and selected")
                    else:
                        arm_pose = existing_armature.data.pose_position
                        existing_armature.data.pose_position = 'REST'
                        context.view_layer.update()
                        good_to_go = True
                        render_model = existing_armature.nwo.node_order_source
                        if not render_model.strip():
                            # try own asset
                            render_model = utils.get_asset_render_model()
                            if render_model is None:
                                utils.print_warning(f"Armature [{existing_armature.name}] has no render model set. Set this in Foundry object properties")
                                good_to_go = False
                                
                        if good_to_go:
                            full_render_path = Path(utils.get_tags_path(), utils.relative_path(render_model))
                            # if not full_render_path.exists():
                            #     utils.print_warning(f"Armature [{existing_armature.name}] has invalid render model set (it does not exist) [{full_render_path}]")
                            #     good_to_go = False
                        
                        if good_to_go:
                            for file in animation_files:
                                print(f'Importing Animation Tag: {Path(file).with_suffix("").name} ')
                                imported_animations.extend(importer.import_animation_graph(file, existing_armature, full_render_path))
                            
                        if imported_animations and set_animation_index:
                            scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
                                    
                        existing_armature.data.pose_position = arm_pose
                    
                if 'scenario' in importer.extensions:
                    importer.tag_zone_set = self.tag_zone_set
                    importer.tag_bsp = self.tag_bsp if self.tag_bsp != 'all_bsps' else ''
                    importer.tag_bsp_render_only = self.tag_bsp_render_only
                    importer.tag_bsp_import_geometry = self.tag_bsp_import_geometry
                    importer.tag_bsp_skip_structure_merge = self.tag_bsp_skip_structure_merge
                    importer.tag_bsp_merge_render_collision = self.tag_bsp_merge_render_collision
                    importer.tag_bsp_import_havok = self.tag_bsp_import_havok
                    importer.tag_import_lights = self.tag_import_lights
                    importer.tag_import_design = self.tag_import_design
                    importer.tag_scenario_import_objects = self.tag_scenario_import_objects
                    importer.tag_scenario_import_decals = self.tag_scenario_import_decals
                    importer.tag_scenario_import_decorators = self.tag_scenario_import_decorators
                    importer.decorator_lod = int(self.decorator_lod)
                    importer.setup_as_asset = self.setup_as_asset
                    importer.tag_sky = self.tag_sky
                    scenario_files = importer.sorted_filepaths["scenario"]
                    imported_scenario_objects = importer.import_scenarios(scenario_files, self.build_blender_materials, self.always_extract_bitmaps)
                        
                    imported_objects.extend(imported_scenario_objects)
                    
                    if for_cinematic:
                        if not scene_nwo.cinematic_scenario and scenario_files:
                            scene_nwo.cinematic_scenario = scenario_files[0]
                            if self.tag_zone_set:
                                scene_nwo.cinematic_zone_set = self.tag_zone_set
                        self.link_anchor(context, imported_scenario_objects)
                    
                elif 'scenario_structure_bsp' in importer.extensions:
                    importer.tag_bsp_render_only = self.tag_bsp_render_only
                    importer.tag_bsp_import_geometry = self.tag_bsp_import_geometry
                    importer.tag_bsp_skip_structure_merge = self.tag_bsp_skip_structure_merge
                    importer.tag_bsp_merge_render_collision = self.tag_bsp_merge_render_collision
                    importer.tag_bsp_import_havok = self.tag_bsp_import_havok
                    importer.tag_import_lights = self.tag_import_lights
                    importer.setup_as_asset = self.setup_as_asset
                    bsp_files = importer.sorted_filepaths["scenario_structure_bsp"]
                    imported_bsp_objects = []
                    for bsp in bsp_files:
                        bsp_objects, _ = importer.import_bsp(bsp)
                        imported_bsp_objects.extend(bsp_objects)
                        set_asset(Path(bsp).suffix)
                        
                    imported_objects.extend(imported_bsp_objects)
                    
                    if for_cinematic:
                        self.link_anchor(context, imported_bsp_objects)    
                        
                elif 'scenario_structure_lighting_info' in importer.extensions:
                    info_files = importer.sorted_filepaths["scenario_structure_lighting_info"]
                    imported_info_objects = []
                    for info in info_files:
                        info_objects, info_collection, _ = importer.import_scenario_structure_lighting_info(info)
                        imported_info_objects.extend(info_objects)
                        
                    imported_objects.extend(imported_info_objects)
                    
                elif 'structure_design' in importer.extensions:
                    importer.setup_as_asset = self.setup_as_asset
                    
                    design_files = importer.sorted_filepaths["structure_design"]
                    imported_design_objects = []
                    for design in design_files:
                        design_objects = importer.import_structure_design(design)
                        imported_design_objects.extend(design_objects)
                        
                    imported_objects.extend(imported_design_objects)
                        
                elif 'prefab' in importer.extensions:
                    importer.tag_bsp_render_only = self.tag_bsp_render_only
                    importer.tag_bsp_import_geometry = self.tag_bsp_import_geometry
                    importer.tag_bsp_skip_structure_merge = self.tag_bsp_skip_structure_merge
                    importer.tag_bsp_merge_render_collision = self.tag_bsp_merge_render_collision
                    importer.tag_bsp_import_havok = self.tag_bsp_import_havok
                    importer.tag_import_lights = self.tag_import_lights
                    importer.setup_as_asset = self.setup_as_asset
                    if self.place_at_mouse:
                        key = marker.nwo.marker_game_instance_tag_name
                        game_object_collection = importer.get_cached_game_object_collection(key)
                        imported_object_objects = []
                        if game_object_collection is None:
                            game_object_collection = importer.import_prefab(marker)
                            merged_collection = merge_collection(game_object_collection, suffix="Prefab") 
                            imported_object_objects = game_object_collection.all_objects
                            context.scene.collection.children.unlink(game_object_collection)
                            game_object_collection = importer.cache_game_object_collection(merged_collection, key)
                            # bpy.data.collections.link(game_object_collection)
                            
                        marker.instance_type = 'COLLECTION'
                        marker.instance_collection = game_object_collection
                        marker.nwo.marker_instance = True
                        imported_objects.append(marker)
                        context.collection.objects.link(marker)
                        
                        marker.select_set(True)
                        context.view_layer.objects.active = marker
                    else:
                        imported_prefab_objects = []
                        prefab_files = importer.sorted_filepaths["prefab"]
                        for file in prefab_files:
                            imported_prefab_objects.extend(importer.import_prefab(file))
                            
                        imported_objects.extend(imported_prefab_objects)
                        
                if 'polyart_asset' in importer.extensions:
                    polyart_files = importer.sorted_filepaths["polyart_asset"]
                    imported_polyart_objects = []
                    for file in polyart_files:
                        imported_polyart_objects.extend(importer.import_polyart(file))
                        
                    imported_objects.extend(imported_polyart_objects)
                    
                if 'decorator_set' in importer.extensions:
                    importer.setup_as_asset = self.setup_as_asset
                    if self.place_at_mouse:
                        key = marker.nwo.marker_game_instance_tag_name, marker.nwo.marker_game_instance_tag_variant_name
                        game_object_collection = importer.get_cached_game_object_collection(*key)
                        imported_object_objects = []
                        if game_object_collection is None:
                            game_object_collection = importer.import_decorator_set(marker, self.build_blender_materials, self.always_extract_bitmaps, self.decorator_type.lower() if self.decorator_type.strip() else None, int(self.decorator_lod), True)
                            merged_collection = merge_collection(game_object_collection, suffix="Decorator") 
                            imported_object_objects = game_object_collection.all_objects
                            context.scene.collection.children.unlink(game_object_collection)
                            game_object_collection = importer.cache_game_object_collection(merged_collection, *key)
                            # bpy.data.collections.link(game_object_collection)
                            
                        marker.instance_type = 'COLLECTION'
                        marker.instance_collection = game_object_collection
                        marker.nwo.marker_instance = True
                        imported_objects.append(marker)
                        context.collection.objects.link(marker)
                        
                        marker.select_set(True)
                        context.view_layer.objects.active = marker
                    else:
                        decorator_files = importer.sorted_filepaths["decorator_set"]
                        imported_decorator_objects = []
                        lod = int(self.decorator_lod) if self.decorator_single_lod else 0
                        for file in decorator_files:
                            imported_decorator_objects.extend(importer.import_decorator_set(file, self.build_blender_materials, self.always_extract_bitmaps, self.decorator_type.lower() if self.decorator_type.strip() else None, lod))
                        
                        imported_objects.extend(imported_decorator_objects)
                    
                if 'particle_model' in importer.extensions:
                    particle_model_files = importer.sorted_filepaths["particle_model"]
                    imported_particle_model_objects = []
                    for file in particle_model_files:
                        particle_objects = importer.import_particle_model(file)
                        imported_particle_model_objects.extend(particle_objects)
                        
                    imported_objects.extend(imported_particle_model_objects)
                    
                # for ob in importer.to_cursor_objects:
                #     ob.matrix_world = context.scene.cursor.matrix
                do_vis_bake = False
                
                if 'cinematic' in importer.extensions:
                    scenario_collection = None
                    cinematic_files = importer.sorted_filepaths["cinematic"]
                    imported_cinematic_objects = []
                    imported_cinematic_actions = []
                    importer.tag_cinematic_import_scenario = self.tag_cinematic_import_scenario
                    importer.tag_cinematic_scene = self.tag_cinematic_scene
                    importer.build_control_rig = self.build_control_rig
                    importer.tag_model_override_type = RenderModelOverrideType.campaign
                    importer.graph_import_pca_data = self.graph_import_pca_data
                    importer.tag_import_attachments = self.tag_import_attachments
                    anchor_objects = {}
                    imported_cinematic_scenario_objects = []
                    
                    if utils.is_corinth(context):
                        film_aperture = 22.5
                    else:
                        film_aperture = 45
                        
                    globals_path = Path(utils.get_tags_path(), "globals\\globals.globals")
                    if globals_path.exists():
                        with GlobalsTag(path=globals_path) as tag_globals:
                            tag_film_aperture = tag_globals.cinematic_film_aperture()
                            if tag_film_aperture is not None:
                                film_aperture = tag_film_aperture
                            else:
                                utils.print_warning(f"Failed to read globals tag. Using default cinematic film aperture of {film_aperture}")
                    else:
                        utils.print_warning(f"Failed to read globals tag. Using default cinematic film aperture of {film_aperture}")
                    
                    importer.tag_render = True
                    importer.tag_markers = True
                    importer.graph_scale_animations_to_skeleton = self.graph_scale_animations_to_skeleton
                    importer.tag_state = State["default"].value
                    importer.import_variant_children = True
                    importer.graph_import_animations = True
                    
                    for file in cinematic_files:
                        scene_datas, scenario, zone_set = importer.import_cinematic(file, film_aperture)
                        
                        if scenario and zone_set:
                            importer.tag_zone_set = zone_set
                            importer.tag_bsp_import_geometry = True
                            importer.tag_bsp_skip_structure_merge = self.tag_bsp_skip_structure_merge
                            importer.tag_bsp_merge_render_collision = self.tag_bsp_merge_render_collision
                            importer.tag_bsp_render_only = True
                            importer.tag_import_lights = self.tag_import_lights
                            importer.tag_scenario_import_objects = self.tag_scenario_import_objects
                            importer.tag_scenario_import_decals = self.tag_scenario_import_decals
                            importer.tag_scenario_import_decorators = self.tag_scenario_import_decorators
                            importer.tag_sky = self.tag_sky
                            imported_cinematic_scenario_objects, scenario_collection = importer.import_scenarios([scenario], self.build_blender_materials, self.always_extract_bitmaps, return_collection=True, merge_sky_to_scenario_collection=True)
                            
                            imported_cinematic_objects.extend(imported_cinematic_scenario_objects)
                            
                            scene_nwo.cinematic_scenario = scenario
                            scene_nwo.cinematic_zone_set = zone_set
                        
                        first_scene = True
                        for sdata in scene_datas:
                            if first_scene:
                                # if scenario_collection is not None:
                                #     scene_collection_map[sdata.blender_scene].add(scenario_collection)
                                # if sdata.blender_scene:
                                #     context.window.scene = sdata.blender_scene
                                switch_blender_scene = sdata.blender_scene
                            
                            context.window.scene = sdata.blender_scene
                            camera_collection = bpy.data.collections.new(sdata.name)
                            context.scene.collection.children.link(camera_collection)
                            scene_imported_objects = []
                            scene_imported_actions = []
                            for ob in sdata.camera_objects:
                                camera_collection.objects.link(ob)
                                
                            # scene_collection_map[sdata.blender_scene].add(camera_collection)
                                
                            imported_cinematic_objects.extend(sdata.camera_objects)
                            imported_cinematic_actions.extend(sdata.actions)
                            scene_imported_objects.extend(sdata.camera_objects)
                            scene_imported_actions.extend(sdata.actions)
                            
                            camera_light_mask = {cam: set() for cam in sdata.camera_objects}
                            light_objects_all = []
                            light_objects_corinth = []
                            cinematic_objects_collection = bpy.data.collections.new(f"objects_{sdata.name}")
                            context.scene.collection.children.link(cinematic_objects_collection)
                            # scene_collection_map[sdata.blender_scene].add(cinematic_objects_collection)
                            object_lighting_collection = bpy.data.collections.new(f"object_lighting_{sdata.name}")
                            context.scene.collection.children.link(object_lighting_collection)
                            # scene_collection_map[sdata.blender_scene].add(object_lighting_collection)

                            def setup_light(light_ob, camera_shot, receiver_collection, lighting_shot=None):
                                object_lighting_coll.objects.link(light_ob)
                                camera_light_mask[camera_shot].add(light_ob)
                                light_objects_all.append(light_ob)
                                imported_cinematic_objects.append(light_ob)
                                scene_imported_objects.append(light_ob)
                                if lighting_shot is not None:
                                    light_ob["cinematic_light_marker"] = lighting_shot.marker
                                    light_ob["cinematic_light_persist"] = lighting_shot.persist
                                    light_ob["cinematic_light_shot"] = lighting_shot.shot_index + 1
                                if receiver_collection is not None:
                                    light_ob.light_linking.receiver_collection = model_collection
                            
                            if self.tag_cinematic_import_actors:
                                camera_actor_mask = {cam: set() for cam in sdata.camera_objects}
                                do_vis_bake = True
                                all_actors = set()
                                actor_event_links = []
                                for cin_object in sdata.object_animations:
                                    importer.tag_variant = cin_object.variant
                                    imported_cinematic_object_objects, armature, render_path, model_collection = importer.import_object([cin_object.object_path], None, return_cin_stuff=True, parent_collection=cinematic_objects_collection)
                                    imported_cinematic_objects.extend(imported_cinematic_object_objects)
                                    scene_imported_objects.extend(imported_cinematic_object_objects)
                                    cin_object.armature = armature
                                    armature.name = cin_object.name

                                    for event_index in cin_object.events:
                                        actor_event_links.append((event_index, armature))

                                    model_collection.name = cin_object.name
                                    animation_start = len(scene_nwo.animations)
                                    cin_actions = importer.import_animation_graph(cin_object.graph_path, armature, render_path)
                                    
                                    # Scenes reuse names, and Blender can invalidate RNA
                                    # references as this collection grows. Keep stable indices.
                                    cin_object.animations = {
                                        utils.action_shot_index(scene_nwo.animations[i].name): i
                                        for i in range(animation_start, len(scene_nwo.animations))
                                    }
                                    imported_cinematic_actions.extend(cin_actions)
                                    scene_imported_actions.extend(cin_actions)
                                    all_actors.add(armature)
                                    for cam in cin_object.cameras.values():
                                        camera_actor_mask[cam].add(armature)
                                        
                                    # Lighting
                                    if not self.tag_import_lights or cin_object.cinematic_lighting is None:
                                        continue
                                    
                                    utils.print_bullet(f"Adding cinematic lighting for {cin_object.name}")
                                    markers = {m.name: m for m in imported_cinematic_object_objects if m.type == 'EMPTY'}
                                    object_lighting_coll = bpy.data.collections.new(f"{armature.name}_lighting")
                                    object_lighting_collection.children.link(object_lighting_coll)
                                    
                                    for lighting_shot in cin_object.cinematic_lighting:
                                        marker = markers.get(lighting_shot.marker)
                                        for idx, vmf_light in enumerate(lighting_shot.vmf_lights):
                                            c = cin_object.cameras.get(lighting_shot.shot_index)
                                            if c is None:
                                                continue
                                            light_name = f"{armature.name}_light_2_shot_{lighting_shot.shot_index + 1}" if idx == 1 else f"{armature.name}_light_1_shot_{lighting_shot.shot_index + 1}"
                                            setup_light(vmf_light.to_blender(armature, marker, light_name), c, model_collection, lighting_shot)
                                            
                                        for idx, dynamic_light in enumerate(lighting_shot.dynamic_lights):
                                            c = cin_object.cameras.get(lighting_shot.shot_index)
                                            if c is None:
                                                continue
                                            light_name = f"{armature.name}_dynamic_light_{lighting_shot.marker}_shot_{lighting_shot.shot_index + 1}" if (lighting_shot.marker and dynamic_light.use_marker) else f"{armature.name}_dynamic_light_shot_{lighting_shot.shot_index + 1}"
                                            l_ob = dynamic_light.to_blender(armature, marker, light_name)
                                            setup_light(l_ob, c, None, lighting_shot)
                                
                                for cam, actors in camera_actor_mask.items():
                                    cam_actors = cam.nwo.actors
                                    if len(actors) >= len(all_actors):
                                        exclude_actors = all_actors.difference(actors)
                                        cam.nwo.actors_type = 'exclude'
                                        for a in exclude_actors:
                                            cam_actors.add().actor = a
                                    else:
                                        cam.nwo.actors_type = 'include'
                                        for a in actors:
                                            cam_actors.add().actor = a
                            
                            if self.tag_import_lights:
                                do_vis_bake = True
                                
                                for lighting_info in sdata.lighting_infos:
                                    light_objects, light_collection, camera_lights = importer.import_scenario_structure_lighting_info(lighting_info, cinematic_cameras=sdata.camera_objects)
                                    for cam, lights in camera_lights.items():
                                        camera_light_mask[cam].update(lights)
                                    light_objects_all.extend(light_objects)
                                    light_objects_corinth.extend(light_objects)
                                    # scene_collection_map[sdata.blender_scene].add(light_collection)
                                    imported_cinematic_objects.extend(light_objects)
                                    scene_imported_objects.extend(light_objects)
                                    
                                for cam, lights in camera_light_mask.items():
                                    cam_lights = cam.nwo.cinematic_lights
                                    if len(lights) >= len(light_objects_all):
                                        exclude_lights = set(light_objects_all).difference(lights)
                                        cam.nwo.cinematic_lights_type = 'exclude'
                                        for l in exclude_lights:
                                            cam_lights.add().light = l
                                    else:
                                        cam.nwo.cinematic_lights_type = 'include'
                                        for l in lights:
                                            cam_lights.add().light = l

                            if imported_cinematic_scenario_objects:
                                anchor_position = Vector.Fill(3, 0)
                                anchor_facing = Vector.Fill(3, 0)
                                with ScenarioMetadataTag(path=scenario) as scenario_tag:
                                    anchor = scenario_tag.cutscene_anchor(sdata.anchor_name)
                                    if anchor is not None:
                                        anchor_position = Vector(anchor[0]) * 100
                                        anchor_facing = Vector(anchor[1])
                                
                                anchor_euler = Euler((anchor_facing[2], -anchor_facing[1], anchor_facing[0]), 'ZYX')
                                anchor_matrix = Matrix.LocRotScale(anchor_position, anchor_euler, Vector.Fill(3, 1))
                                
                                scenario_instance_empty = bpy.data.objects.new(scenario_collection.name, object_data=None)
                                context.scene.collection.objects.link(scenario_instance_empty)
                                # scene_collection_map[sdata.blender_scene].add(scenario_instance_empty)
                                scenario_instance_empty.instance_type = 'COLLECTION'
                                scenario_instance_empty.instance_collection = scenario_collection
                                imported_cinematic_objects.append(scenario_instance_empty)
                                scene_imported_objects.append(scenario_instance_empty)
                                
                                anchor = bpy.data.objects.new(name=sdata.anchor_name, object_data=None)
                                anchor.nwo.is_frame = True
                                anchor.empty_display_size = (1 / 0.03048) * import_transform.scale_factor()
                                anchor.matrix_world = import_transform.object_matrix(anchor_matrix.inverted_safe())
                                context.scene.collection.objects.link(anchor)
                                sdata.blender_scene.nwo.cinematic_anchor = anchor
                                imported_cinematic_objects.append(anchor)
                                scene_imported_objects.append(anchor)
                                anchor_objects[anchor] = imported_cinematic_scenario_objects
                                anchor.nwo.export_this = False
                                scenario_instance_empty.parent = anchor
                                scenario_instance_empty.parent_type = 'OBJECT'
                                scenario_instance_empty.matrix_parent_inverse = Matrix.Identity(4)
                                if scene_nwo.maintain_marker_axis:
                                    scenario_instance_empty.matrix_local = Matrix.Rotation(
                                        -import_transform.rotation(scene_nwo), 4, 'Z'
                                    )
                                else:
                                    scenario_instance_empty.matrix_local = Matrix.Identity(4)
                            else:
                                anchor = bpy.data.objects.new(name=sdata.anchor_name, object_data=None)
                                anchor.nwo.is_frame = True
                                anchor.nwo.export_this = False
                                0
                                scene_imported_objects.append(anchor)
                            
                            for ob in light_objects_corinth:
                                ob.parent = anchor
                                ob.parent_type = 'OBJECT'

                            if self.tag_cinematic_import_actors:
                                cinematic_events = sdata.blender_scene.nwo.cinematic_events
                                for event_index, actor in actor_event_links:
                                    if event_index < len(cinematic_events):
                                        e = cinematic_events[event_index]
                                        if e.type == 'EFFECT':
                                            e.marker = actor
                                        else:
                                            e.actor = actor

                            # scene_collection_map[sdata.blender_scene].add(anchor)
                            first_scene = False
                            
                    imported_objects.extend(imported_cinematic_objects)

                    # for anchor, scen_objects in anchor_objects.items():
                    #     for ob in scen_objects:
                    #         if not ob.parent:
                    #             ob.parent = anchor
                    #             ob.parent_type = 'OBJECT'

                if importer.pca_info:
                    print(f"Importing PCA Animations from {len(importer.pca_info)} tag{'' if len(importer.pca_info) == 1 else 's'}")
                    shape_key_actions = {}
                    for info in importer.pca_info:
                        with PCAAnimationTag(path=info.pca_path) as pca:
                            shape_key_actions.update(pca.to_blender(info.pca_animations, info.pca_groups, info.objects))
                            
                    for (action, slot), shape_keys in shape_key_actions.items():
                        
                        fcurves = utils.get_fcurves(action, slot)
                        existing_paths = {fcu.data_path for fcu in fcurves}

                        for kb in shape_keys.key_blocks:
                            if kb.name == "Basis":
                                continue

                            data_path = f'key_blocks["{kb.name}"].value'

                            if data_path not in existing_paths:
                                fcu = fcurves.new(data_path=data_path)
                                kp = fcu.keyframe_points.insert(frame=1, value=0.0, options={'FAST'})
                                kp.interpolation = 'LINEAR'
                
                if scene_datas and self.tag_cinematic_import_actors:
                    print("--- Creating NLA tracks for cinematic")
                    for sdata in scene_datas:
                        add_scene_data_to_nla(sdata, scene_nwo)
                
                setup_materials(context, importer, starting_materials, imported_objects, self.build_blender_materials, self.always_extract_bitmaps, importer.emissive_meshes)
                        
                if 'bitmap' in importer.extensions:
                    bitmap_files = importer.sorted_filepaths["bitmap"]
                    if not bitmap_files:
                        self.nothing_imported = True
                    else:
                        extracted_bitmaps = importer.extract_bitmaps(bitmap_files, self.extracted_bitmap_format)
                        if self.import_images_to_blender:
                            importer.load_bitmaps(extracted_bitmaps, self.images_fake_user)
                                    
                        self.report({'INFO'}, f"Extracted {'and imported' if self.import_images_to_blender else ''} {len(bitmap_files)} bitmaps")
                        
                if 'camera_track' in importer.extensions:
                    camera_track_files = importer.sorted_filepaths["camera_track"]
                    cameras, actions = importer.import_camera_tracks(camera_track_files, self.camera_track_animation_scale)
                    
                    if scene_nwo.animations:
                        scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
                        
                if self.generate_frames and imported_animations and 'jma' in importer.extensions:
                    generator = FrameGenerator(a for a in scene_nwo.animations if a not in current_animations)
                    generator.generate()

                importer.bake_imported_control_rig_actions()
                    
                # if importer.deferred_parenting:
                #     for ob, parent in importer.deferred_parenting.items():
                #         if ob.name in bpy.data.objects and parent.name in bpy.data.objects:
                #             ob.parent = parent
                
                # for bscene, v in scene_collection_map.items():
                #     for ob_or_collection in v:
                #         if isinstance(ob_or_collection, bpy.types.Object):
                #             utils.unlink(ob_or_collection)
                #             bscene.collection.objects.link(ob_or_collection)
                #         else:
                #             context.scene.collection.children.unlink(ob_or_collection)
                #             bscene.collection.children.link(ob_or_collection)
                
                if do_vis_bake:
                    for sdata in scene_datas:
                        context.window.scene = sdata.blender_scene
                        utils.print_step(f"Baking object visibility to keyframes for {sdata.blender_scene.name}")
                        bake_vis_to_keyframes(context)

                if switch_blender_scene is not None and context.window.scene != switch_blender_scene:
                    context.window.scene = switch_blender_scene
                    
                apply_prefix_bulk(imported_objects)
                
                for op in deferred_ops:
                    op()
                    
                # # Clamp lights
                # utils.print_tag("Clamping Lights")
                # lights = {l.data for l in imported_objects if l.type == 'LIGHT' and l.data.type != 'SUN' and l.data.nwo.light_far_attenuation_end > 0.0 and l.data.energy > 30}
                # for l in lights:
                #     l.energy = max(min(l.energy, utils.calc_max_intensity(l.nwo.light_far_attenuation_end, 0.05)), 30)
                #     # l.nwo.light_far_attenuation_end = 0
                        
            except KeyboardInterrupt:
                utils.print_warning("\nIMPORT CANCELLED BY USER")
                self.user_cancelled = True
                failed = True
            except Exception as e:
                failed = True
                if isinstance(e, RuntimeError):
                    utils.print_warning(traceback.format_exception_only(e)[0][14:])
                else:
                    utils.print_error("\n\nException hit. Please include in report\n")
                    traceback.print_exc()
                    print("FOUNDRY VERSION: ", utils.get_version_string())
                    utils.print_warning(
                        "Import failed spectacularly. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry/issues\n"
                    )
                    utils.print_error(
                        "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                    )
                    failed = True

        
        end = time.perf_counter()
        if self.user_cancelled:
            self.report({'WARNING'}, "Import cancelled by user")
        elif failed:
            utils.print_error("IMPORT FAILED")
            self.report({'WARNING'}, "Import failed")
        elif self.nothing_imported:
            print("No Folders/Filepaths supplied")
            self.report({'WARNING'}, "Nothing imported. No filepaths/folders supplied")
        else:
            print(
                "\n-----------------------------------------------------------------------"
            )
            print(f"Import Completed in {utils.human_time(end - start)}")

            print(
                "-----------------------------------------------------------------------\n"
            )
        
        if failed:
            bpy.ops.ed.undo_push()
            bpy.ops.ed.undo()
        
        clear_cache()
        utils.clear_external_project()
        return {'FINISHED'}
    
    def link_anchor(self, context, objects):
        scene_nwo = utils.get_scene_props()
        if self.anchor is None:
            if scene_nwo.cinematic_anchor is None:
                self.anchor = bpy.data.objects.new(name="Anchor", object_data=None)
                context.scene.collection.objects.link(self.anchor)
                scene_nwo.cinematic_anchor = self.anchor
            else:
                self.anchor = scene_nwo.cinematic_anchor
        for ob in objects:
            if not ob.parent:
                ob.parent = self.anchor
                ob.parent_type = 'OBJECT'
    
    def invoke(self, context, event):
        # skip_fileselect = False
        # if self.directory or self.files or self.filepath:
        #     skip_fileselect = True
        #     self.filter_glob = "*.bitmap;*.camera_track;*.model;*.scenario;*.scen*_bsp;*.render_model"
        # else:
        
        global checked_asset_once
        if not self.setup_as_asset and not utils.valid_nwo_asset(context) and not checked_asset_once:
            checked_asset_once = True
            self.setup_as_asset = True
        set_default_import_template(self)
        
        if 'bitmap' in self.scope:
            self.directory = utils.get_tags_path()
        elif 'camera_track' in self.scope:
            cameras_dir = Path(utils.get_tags_path(), 'camera')
            if cameras_dir.exists():
                self.directory = str(cameras_dir)
            else:
                self.directory = utils.get_tags_path()
        else:
            self.directory = ''
            self.filepath = ''
            
        self.filename = ''
        if not self.scope:
            self.filter_glob = "*"
        else:
            if 'bitmap' in self.scope:
                self.directory = utils.get_tags_path()
                self.filter_glob += "*.bitmap;"
            if 'camera_track' in self.scope:
                self.filter_glob += '*.camera_track;'
            if 'model' in self.scope:
                self.filter_glob += '*.model;'
            if 'render_model' in self.scope:
                self.filter_glob += '*.render_model;*.gbxmodel;'
            if 'physics_model' in self.scope:
                self.filter_glob += '*.physics_model;*.physics;'
            if 'collision_model' in self.scope:
                self.filter_glob += '*.collision_model;*.model_collision_geometry;'
            if 'sky' in self.scope:
                self.filter_glob += '*.sky;'
            if 'scenario' in self.scope:
                self.filter_glob += '*.scenario;'
            if 'scenario_structure_bsp' in self.scope:
                self.filter_glob += '*.scen*_bsp;'
            if 'scenario_structure_lighting_info' in self.scope:
                self.filter_glob += '*.scen*_info;'
            if 'particle_model' in self.scope:
                self.filter_glob += '*.particle_model;'
            if 'object' in self.scope:
                self.filter_glob += '*.biped;*.crate;*.creature;*.d*_control;*.d*_dispenser;*.e*_scenery;*.equipment;*.giant;*.d*_machine;*.projectile;*.scenery;*.spawner;*.sound_scenery;*.d*_terminal;*.vehicle;*.weapon;'
            if 'animation' in self.scope:
                self.filter_glob += '*.mod*_*_graph;'
            if 'prefab' in self.scope:
                self.filter_glob += '*.prefab;'
            if 'structure_design' in self.scope:
                self.filter_glob += '*.stru*_design;'
            if 'polyart_asset' in self.scope:
                self.filter_glob += '*.polyart_a*;'
            if 'decorator_set' in self.scope:
                self.filter_glob += '*.decor*_set;'
            if 'cinematic' in self.scope:
                self.filter_glob += '*.cinematic;'
                    
            if 'jms' in self.scope:
                self.legacy_okay = True
                self.filter_glob += '*.jms;*.ass;'
            if 'wrl' in self.scope:
                self.filter_glob += '*.wrl;'
            if 'jma' in self.scope:
                self.legacy_okay = True
                self.filter_glob += '*.jmm;*.jma;*.jmt;*.jmz;*.jmv;*.jmw;*.jmo;*.jmr;*.jmrx;'
            
        # if skip_fileselect:
        #     return self.execute(context)
        
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.25
        corinth = utils.is_corinth(context)
        project = render_lod_source_project(self)
        game = project.game if project is not None else None
        scope_items = set(self.scope.split(',')) if self.scope else set()
        corinth = project.corinth if project is not None else corinth
        if (utils.get_scene_props().asset_type != 'cinematic' and 'cinematic' not in scope_items
                and (not scope_items or any(item not in {'jms', 'jma', 'wrl'} for item in scope_items))):
            box = layout.box()
            box.label(text="Tag Source Data")
            box.prop(self, "use_import_info")
        if not self.scope or ('jms' in self.scope or 'model' in self.scope or 'object' in self.scope or 'render_model' in self.scope or 'collision_model' in self.scope or 'physics_model' in self.scope or 'sky' in self.scope):
            box = layout.box()
            box.label(text="Model Settings")
            tag_type = 'material' if utils.is_corinth(context) else 'shader'
            # box.prop(self, 'find_shader_paths', text=f"Find {tag_type.capitalize()} Tag Paths")
            box.prop(self, 'build_blender_materials', text=f"Blender Materials from {tag_type.capitalize()} Tags")
            draw_material_project_option(self, box)
            box.prop(self, 'always_extract_bitmaps')
            
        if not self.scope or ('model' in self.scope) or ('object' in self.scope):
            layout.label(text='Model Tag Settings')
            draw_model_tag_import_sections(
                self,
                layout,
                corinth,
                show_template=True,
                show_source=True,
                has_variants=game != 'halo1',
                has_permutations=game == 'halo1',
                include_generate_frames=True,
                show_material_options=False,
            )

        if ('render_model' in scope_items or 'sky' in scope_items) and 'model' not in scope_items and 'object' not in scope_items:
            box = layout.box()
            box.label(text='Sky Settings' if 'sky' in scope_items else 'Render Model Settings')
            box.prop(self, 'reuse_armature')
            box.prop(self, 'build_control_rig')
            box.prop(self, 'tag_render')
            draw_halo2_lod(self, box)
            box.prop(self, 'tag_markers')
            if 'sky' in scope_items:
                box.prop(self, 'tag_animation')
                box.prop(self, 'setup_as_asset')

        if {'collision_model', 'physics_model'}.intersection(scope_items) and 'model' not in scope_items and 'object' not in scope_items:
            box = layout.box()
            box.label(text='Collision & Physics Settings')
            box.label(text='Uses selected armature or a skeleton from this tag folder')
            
        if not self.scope or ('scenario' in scope_items) or ('scenario_structure_bsp' in scope_items):
            layout.label(text='Scenario Tag Settings')
            draw_scenario_import_sections(
                self,
                layout,
                corinth,
                show_template=True,
                show_zone_set=not self.scope or ('scenario' in scope_items),
                show_sky=not self.scope or ('scenario' in scope_items),
                show_scenario_content=not self.scope or ('scenario' in scope_items),
                show_setup_as_asset=not self.scope or ('scenario' in scope_items) or ('scenario_structure_bsp' in scope_items),
            )
        
        if not self.scope or 'jms' in self.scope:
            box = layout.box()
            box.label(text="JMS/ASS Settings")
            box.prop(self, "legacy_type")

        if 'jma' in scope_items and not ({'model', 'object'} & scope_items):
            box = layout.box()
            box.label(text="Animation Settings")
            box.prop(self, "generate_frames")
            box.prop(self, "convert_animations")
        
        if not self.scope or ('bitmap' in self.scope):
            box = layout.box()
            box.label(text="Bitmap Settings")
            box.use_property_split = True
            box.prop(self, 'extracted_bitmap_format')
            box.prop(self, 'import_images_to_blender')
            if self.import_images_to_blender:
                box.prop(self, 'images_fake_user')
                
        if not self.scope or ('camera_track' in self.scope):
            box = layout.box()
            box.label(text='Camera Track Settings')
            box.prop(self, 'camera_track_animation_scale')
            box.prop(self, "setup_as_asset")
            
        if game != 'halo1' and (not self.scope or 'decorator_set' in scope_items):
            box = layout.box()
            box.label(text='Decorator Set Settings')
            box.prop(self, "decorator_type")
            box.prop(self, "decorator_single_lod")
            if self.decorator_single_lod:
                box.prop(self, "decorator_lod")
            box.prop(self, 'build_blender_materials', text="Build Blender Material")
            draw_material_project_option(self, box)
            box.prop(self, 'always_extract_bitmaps')
            box.prop(self, "setup_as_asset")
            
        if game not in {'halo1', 'halo2'} and (not self.scope or 'cinematic' in scope_items):
            box = layout.box()
            box.label(text='Cinematic Settings')
            box.prop(self, "tag_cinematic_import_scenario")
            box.prop(self, "tag_cinematic_import_actors")
            if corinth:
                box.prop(self, "graph_import_pca_data")
            box.prop(self, "tag_cinematic_scene")
            box.prop(self, "build_control_rig")
            box.prop(self, "tag_import_attachments")
            box.prop(self, "tag_import_lights")
            box.prop(self, "tag_sky")
            box.prop(self, "tag_scenario_import_objects")
            box.prop(self, "tag_scenario_import_decals")
            box.prop(self, "tag_scenario_import_decorators")
            box.prop(self, "setup_as_asset")
            box.prop(self, "build_blender_materials")
            draw_material_project_option(self, box)
            box.prop(self, "always_extract_bitmaps")
            
class JMSMaterialSlot:
    @classmethod
    def from_material(cls, material, game, scale=1):
        """Read toolset properties without renaming or editing the source material."""
        props = material.ass_jms
        result = cls.from_name(props.name_override.strip() or material.name)
        for target, source in (
            ('two_sided', 'two_sided'), ('transparent_one_sided', 'transparent_1_sided'),
            ('transparent_two_sided', 'transparent_2_sided'), ('render_only', 'render_only'),
            ('collision_only', 'collision_only'), ('sphere_collision_only', 'sphere_collision_only'),
            ('fog_plane', 'fog_plane'), ('ladder', 'ladder'), ('breakable', 'breakable'),
            ('ai_deafening', 'ai_deafening'), ('no_shadow', 'no_shadow'), ('shadow_only', 'shadow_only'),
            ('lightmap_only', 'lightmap_only'), ('precise', 'precise'), ('portal_one_way', 'portal_1_way'),
            ('portal_door', 'portal_door'), ('portal_vis_blocker', 'portal_vis_blocker'),
            ('ignored_by_lightmaps', 'ignored_by_lightmaps'), ('blocks_sound', 'blocks_sound'),
            ('decal_offset', 'decal_offset'), ('water_surface', 'water_surface'), ('slip_surface', 'slip_surface'),
        ):
            setattr(result, target, getattr(result, target) or getattr(props, source))
        result.portal_exact = game == 'halo1' and (
            props.portal_exact or result.name.startswith('+exactportal'))
        # A period is an H1 exact-portal / H2 shadow-only suffix, but Blender
        # also appends .001 to duplicate material names.
        symbol_name = re.sub(r'\.\d{3}$', '', result.material.name).rstrip()
        if symbol_name.endswith('.'):
            if game == 'halo1':
                result.portal_exact = True
            elif game == 'halo2':
                result.shadow_only = True
        jms_resolution = game == 'halo2' and props.lightmap_resolution_scale > 0
        resolution = props.lightmap_resolution_scale if jms_resolution else props.lightmap_res
        if jms_resolution or resolution != 1:
            result.lightmap_resolution_scale_legacy = resolution
            result.lightmap_resolution_scale = utils.clamp(int(resolution * 3), 1, 7)
        result.ignore_default_resolution = props.ignore_default_res_scale
        result.lightmap_additive_transparency = tuple(props.additive_transparency) if any(props.additive_transparency) else None
        result.lightmap_translucency_tint_color = tuple(props.two_sided_transparent_tint) if any(props.two_sided_transparent_tint) else None
        result.lightmap_transparency_override = props.override_lightmap_transparency
        if game == 'halo2' and props.lightmap_power_scale > 0:
            result.emissive_power_scale = props.lightmap_power_scale
        result.emissive_power = props.power
        result.emissive_color = tuple(props.color)
        result.emissive_quality = props.quality
        result.emissive_per_unit = props.power_per_unit_area
        result.emissive_shader_gel = props.use_shader_gel
        result.emissive_focus = radians(180 * (1 - min(props.emissive_focus, 1)))
        result.emissive_attenuation = props.attenuation_enabled
        result.emissive_attenuation_falloff = props.falloff_distance * scale if props.attenuation_enabled else 0
        result.emissive_attenuation_cutoff = props.cutoff_distance * scale if props.attenuation_enabled else 0
        result.mesh_type = 'portal' if result.portal_exact else result._mesh_type_from_special_name()
        return result

    @classmethod
    def from_name(cls, name):
        """Read file material flags without creating Blender materials."""
        from types import SimpleNamespace
        result = cls.__new__(cls)
        result.material = SimpleNamespace(name=name)
        result.name = name
        result._material_props_from_name()
        result.slip_surface = ']' in name
        result.emissive_power = None
        result.material.name = re.sub(r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+', '', name).strip()
        result.mesh_type = result._mesh_type_from_special_name()
        return result

        
    def _mesh_type_from_special_name(self):
        name = self.material.name
        if name.startswith('+weather'):
            return 'weather_polyhedron'
        elif name.startswith(('+portal', '+exactportal')) or self.portal_one_way or self.portal_vis_blocker:
            return 'portal'
        elif name.startswith('+seam') and not name.startswith('+seams'):
            return 'seam'
        elif name.startswith('+soft_ceiling'):
            return 'soft_ceiling'
        elif name.startswith('+soft_kill'):
            return 'soft_kill'
        elif name.startswith('+slip_surface'):
            return 'slip_surface'
        elif self.fog_plane:
            return 'fog'
        elif self.water_surface:
            return 'water_surface'
        
        return 'default'
            
        
    def _material_props_from_name(self):
        name = self.material.name
        self.two_sided = '%' in name
        self.transparent_one_sided = '#' in name
        self.transparent_two_sided = '?' in name
        self.render_only = '!' in name
        self.collision_only = '@' in name
        self.sphere_collision_only = '*' in name
        self.fog_plane = '$' in name
        self.ladder = '^' in name
        self.breakable = '-' in name
        self.ai_deafening = '&' in name
        self.no_shadow = '=' in name
        self.lightmap_only = ';' in name
        self.shadow_only = False
        self.precise = ')' in name
        self.portal_exact = name.startswith('+exactportal')
        self.portal_one_way = '<' in name
        self.portal_door = '|' in name
        self.portal_vis_blocker = '~' in name
        self.ignored_by_lightmaps = '{' in name
        self.blocks_sound = '}' in name
        self.decal_offset = '[' in name
        self.water_surface = "'" in name
        self.slip_surface = False
        
        self.emissive_power_scale = None

        # lighting props
        self.lightmap_resolution_scale = None
        self.lightmap_resolution_scale_legacy = None
        self.lightmap_translucency_tint_color = None
        self.lightmap_additive_transparency = None
        self.lightmap_transparency_override = None
        
        parts = name.split()
        if len(parts) > 1 and (parts[0].startswith(utils.legacy_lightmap_prefixes) or parts[-1].startswith(utils.legacy_lightmap_prefixes)):
            pattern = r'(' + '|'.join(utils.legacy_lightmap_prefixes) + r')((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
            matches = re.findall(pattern, name)
            for match_groups in matches:
                if len(match_groups) <= 1:
                    continue
                match match_groups[0]:
                    case 'lp:':
                        self.emissive_power_scale = float(match_groups[1])
                    case 'lm:':
                        value = float(match_groups[1])
                        self.lightmap_resolution_scale_legacy = value
                        self.lightmap_resolution_scale = utils.clamp(int(value * 3), 1, 7)
        
    def __eq__(self, __value: 'JMSMaterialSlot') -> bool:
        if not isinstance(__value, self.__class__):
            return False
        if self.two_sided != __value.two_sided:
            return False
        if self.transparent_one_sided != __value.transparent_one_sided:
            return False
        if self.transparent_two_sided != __value.transparent_two_sided:
            return False
        if self.render_only != __value.render_only:
            return False
        if self.collision_only != __value.collision_only:
            return False
        if self.sphere_collision_only != __value.sphere_collision_only:
            return False
        if self.fog_plane != __value.fog_plane:
            return False
        if self.ladder != __value.ladder:
            return False
        if self.breakable != __value.breakable:
            return False
        if self.ai_deafening != __value.ai_deafening:
            return False
        if self.no_shadow != __value.no_shadow:
            return False
        if self.shadow_only != __value.shadow_only:
            return False
        if self.lightmap_only != __value.lightmap_only:
            return False
        if self.precise != __value.precise:
            return False
        if self.portal_one_way != __value.portal_one_way:
            return False
        if self.portal_door != __value.portal_door:
            return False
        if self.portal_vis_blocker != __value.portal_vis_blocker:
            return False
        if self.ignored_by_lightmaps != __value.ignored_by_lightmaps:
            return False
        if self.blocks_sound != __value.blocks_sound:
            return False
        if self.decal_offset != __value.decal_offset:
            return False
        if self.water_surface != __value.water_surface:
            return False
        if self.slip_surface != __value.slip_surface:
            return False
        
        if self.lightmap_resolution_scale != __value.lightmap_resolution_scale: return False
        if self.lightmap_resolution_scale_legacy != __value.lightmap_resolution_scale_legacy: return False
        if self.lightmap_translucency_tint_color != __value.lightmap_translucency_tint_color: return False
        if self.lightmap_additive_transparency != __value.lightmap_additive_transparency: return False
        if self.lightmap_transparency_override != __value.lightmap_transparency_override: return False
        
        if getattr(self, 'emissive_power_scale', None) != getattr(__value, 'emissive_power_scale', None): return False
        if self.emissive_power != __value.emissive_power: return False
        if self.emissive_color != __value.emissive_color: return False
        if self.emissive_quality != __value.emissive_quality: return False
        if self.emissive_per_unit != __value.emissive_per_unit: return False
        if self.emissive_shader_gel != __value.emissive_shader_gel: return False
        if self.emissive_focus != __value.emissive_focus: return False
        if self.emissive_attenuation != __value.emissive_attenuation: return False
        if self.emissive_attenuation_falloff != __value.emissive_attenuation_falloff: return False
        if self.emissive_attenuation_cutoff != __value.emissive_attenuation_cutoff: return False
        if self.emissive_frustum_blend != __value.emissive_frustum_blend: return False
        if self.emissive_frustum_falloff != __value.emissive_frustum_falloff: return False
        if self.emissive_frustum_cutoff != __value.emissive_frustum_cutoff: return False
        
        return True

class PCAInfo:
    def __init__(self):
        self.start_frame = 1
        self.objects = []
        self.pca_animations = {}
        self.pca_groups = {}
        self.pca_path = None

class NWOImporter:
    def __init__(self, context, filepaths=None, scope=None, existing_scene=False):
        self.scene_nwo = utils.get_scene_props()
        self.scene_nwo_export = utils.get_export_props()
        self.game = utils.get_project(self.scene_nwo.scene_project).game
        self.target_game = utils.get_project(
            self.scene_nwo.scene_project, use_external=False).game
        self.build_materials_for_project = False
        self.filepaths = list(filepaths) if filepaths else []
        self.context = context
        self.scene = context.scene
        self.scene_collection = self.scene.collection
        self.tags_dir = utils.get_project(self.scene_nwo.scene_project).tags_directory
        self.tags_path = Path(self.tags_dir)
        self.mesh_objects = []
        self.marker_objects = []
        self.extensions = set()
        self.existing_scene = existing_scene
        self.apply_materials = utils.get_prefs().apply_materials
        self.prefix_setting = utils.get_prefs().apply_prefix
        self.corinth = utils.is_corinth(context)
        self.tag_render = False
        self.render_lod = 'ALL'
        self.tag_markers = False
        self.tag_collision = False
        self.tag_physics = False
        self.graph_scale_animations_to_skeleton = False
        self.tag_animation = False
        self.convert_animations = True
        self.graph_import_animations = False
        self.graph_bake_to_control_rig = True
        self.graph_import_pca_data = False
        self.graph_generate_renames = False
        self.graph_import_events = False
        self.graph_import_ik_chains = False
        self.import_fp_arms = FPARMS.NONE
        # self.to_cursor_objects = set()
        self.tag_variant = ""
        self.tag_permutation = ""
        self.tag_state = -1
        self.tag_zone_set = ""
        self.tag_bsp = ""
        self.tag_bsp_render_only = False
        self.tag_bsp_import_geometry = False
        self.tag_bsp_skip_structure_merge = False
        self.tag_bsp_merge_render_collision = True
        self.tag_bsp_import_havok = False
        self.tag_import_lights = False
        self.tag_import_design = False
        self.tag_scenario_import_objects = False
        self.tag_scenario_import_decals = False
        self.tag_scenario_import_decorators = False
        self.decorator_lod = 0
        self.tag_animation_filter = ""
        self.import_variant_children = False
        self.import_biped_weapon = False
        self.biped_weapon_source = BIPED_WEAPON_SOURCE_BIPED_TAG
        self.import_biped_weapon_non_export = True
        self.setup_as_asset = False
        self.tag_sky = ""
        self.for_cinematic = self.scene_nwo.asset_type == "cinematic"
        self.obs_for_props = {}
        self.attachments = []
        self.fp_arms_imported = False
        self.deferred_parenting = {}
        self.game_object_collection_cache = None
        self.region_names = {entry.name for entry in self.scene_nwo.regions_table}
        self.permutation_names = {entry.name for entry in self.scene_nwo.permutations_table}
        if self.filepaths:
            self.sorted_filepaths = self.group_filetypes(scope)
        else:
            self.sorted_filepaths = []
        
        self.scale_factor = 0.03048 if self.scene_nwo.scale == 'blender' else 1
        self.to_x_rot = utils.rotation_diff_from_forward(self.scene_nwo.forward_direction, 'x')
        self.from_x_rot = utils.rotation_diff_from_forward('x', self.scene_nwo.forward_direction)
        self.needs_scaling = self.scale_factor != 1 or self.to_x_rot
        self.from_vert_normals = False
        
        self.emissive_meshes = set()
        
        self.pca_info = []
        
        self.tag_cinematic_import_scenario = False
        self.tag_cinematic_import_actors = False
        self.tag_cinematic_scene = ""
        self.build_control_rig = False
        self.tag_import_attachments = False
        self.control_rig_action_batches = []
        
        self.tag_model_override_type = None
        self.use_import_info = False
        self.import_info_output_root = None
        self.import_info_source_cache = {}
        self.import_info_source_index = 0
        
        clear_cache()
        
    def group_filetypes(self, scope):
        if scope:
            filetype_dict = {ext: {} for ext in scope}
        else:
            filetype_dict = {ext: {} for ext in formats}
        expanded_paths = []
        for path in self.filepaths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    expanded_paths.extend(os.path.join(root, file) for file in files)
            else:
                expanded_paths.append(path)

        self.filepaths = expanded_paths
        valid_exts = set(filetype_dict)

        for path in expanded_paths:
            path_lower = path.lower()
            for filetype, suffixes in filetype_suffixes:
                if filetype in valid_exts and path_lower.endswith(suffixes):
                    self.extensions.add(filetype)
                    filetype_dict[filetype][path] = None
                    break
            
        # First stored as dict then converted to list. Avoids duplicate files
        for k, v in filetype_dict.items():
            filetype_dict[k] = list(v)
                
        return filetype_dict

    @staticmethod
    def _import_info_output_path(root: Path, source: ImportInfoSource, index: int) -> Path:
        parts = [
            part for part in PureWindowsPath(source.path).parts
            if part not in {'\\', '/', '.', '..'} and ':' not in part
        ]
        data_index = next(
            (i for i, part in enumerate(parts) if part.casefold() == 'data'), None)
        relative_parts = parts[data_index + 1:] if data_index is not None else parts[-1:]
        if not relative_parts:
            relative_parts = [f"source_{index}{source.suffix}"]
        return root.joinpath(*relative_parts)

    def configure_import_info(self, output_root: Path):
        self.use_import_info = not (self.for_cinematic or 'cinematic' in self.extensions)
        self.import_info_output_root = output_root

    def import_info_sources_for_tag(self, tag_path) -> list[str]:
        # Embedded model sources can contain multiple LODs and omit cinematic
        # geometry. Use compiled geometry when a specific LOD is requested.
        if (self.game in {'halo1', 'halo2'} and self.render_lod != 'ALL'
                and Path(tag_path).suffix.lower() in {'.render_model', '.model', '.gbxmodel'}):
            return []
        if not self.use_import_info or self.import_info_output_root is None:
            return []
        key = os.path.normcase(os.path.abspath(tag_path))
        cached = self.import_info_source_cache.get(key)
        if cached is not None:
            return cached
        self.import_info_source_cache[key] = []
        if Path(tag_path).suffix.lower() in legacy_model_formats + legacy_animation_formats + ('.wrl',):
            return []
        try:
            with utils.TagImportMover(self.tags_dir, tag_path) as mover:
                with TagDocument(
                    mover.tag_path,
                    tags_root=self.tags_dir,
                    game=self.game,
                    must_exist=True,
                ) as document:
                    sources = document.import_info_sources()
        except Exception as exc:
            utils.print_warning(f"Could not read import info from {tag_path}: {exc}")
            return []

        tag_output = self.import_info_output_root / f"tag_{self.import_info_source_index:04d}"
        self.import_info_source_index += 1
        extracted = []
        extraction_failed = False
        for source_index, source in enumerate(sources):
            try:
                output_path = self._import_info_output_path(tag_output, source, source_index)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.exists():
                    output_path = output_path.with_name(
                        f"{output_path.stem}_{source_index}{output_path.suffix}")
                output_path.write_bytes(source.decompressed_data())
            except (OSError, ValueError, zlib.error) as exc:
                utils.print_warning(
                    f"Could not extract import-info source {source.path}: {exc}")
                extraction_failed = True
                continue
            extracted.append(str(output_path))

        if extraction_failed:
            utils.print_warning(
                f"Falling back to compiled tag data for {Path(tag_path).name}")
            return []

        self.import_info_source_cache[key] = extracted
        if extracted:
            utils.print_tag(
                f"Using {len(extracted)} import-info source file"
                f"{'' if len(extracted) == 1 else 's'} from {Path(tag_path).name}")
        return extracted

    def add_import_info_sources(self, tag_paths):
        """Substitute import-info sources for selected compiled tags."""
        replacements = set()
        extracted = []
        for tag_path in tag_paths:
            tag_sources = self.import_info_sources_for_tag(tag_path)
            if tag_sources:
                replacements.add(os.path.normcase(os.path.abspath(tag_path)))
                extracted.extend(tag_sources)

        if not extracted:
            return

        for filetype, paths in self.sorted_filepaths.items():
            self.sorted_filepaths[filetype] = [
                path for path in paths
                if os.path.normcase(os.path.abspath(path)) not in replacements
            ]

        for path in extracted:
            suffix = Path(path).suffix.lower()
            filetype = 'jms' if suffix in legacy_model_formats else 'jma'
            self.sorted_filepaths.setdefault(filetype, []).append(path)
            self.extensions.add(filetype)
        
    # Utility functions

    def _ensure_game_object_collection_cache(self):
        if self.game_object_collection_cache is not None:
            return self.game_object_collection_cache

        self.game_object_collection_cache = {
            (collection.nwo.game_object_path, collection.nwo.game_object_variant): collection
            for collection in bpy.data.collections
            if collection.nwo.game_object_path
        }
        return self.game_object_collection_cache

    def get_cached_game_object_collection(self, tag_path: str, variant: str=""):
        return self._ensure_game_object_collection_cache().get((tag_path, variant))

    def cache_game_object_collection(self, collection: bpy.types.Collection, tag_path: str, variant: str=""):
        collection.nwo.game_object_path = tag_path
        collection.nwo.game_object_variant = variant
        self._ensure_game_object_collection_cache()[(tag_path, variant)] = collection
        return collection

    def register_control_rig_actions(self, armature: bpy.types.Object, actions):
        if armature is not None and actions:
            self.control_rig_action_batches.append((armature, list(actions)))

    def _create_fp_game_camera(self, collection: bpy.types.Collection, armature: bpy.types.Object, camera_control_bone: bpy.types.PoseBone, fov: float = None):
        if fov is None:
            fov = 78.0

        camera_name = "FP Game Camera"
        camera_data = bpy.data.cameras.new(camera_name)
        camera_data.lens_unit = 'FOV'
        camera_data.sensor_fit = 'HORIZONTAL'
        camera_data.angle = radians(fov)
        camera_data.display_size = 50 * import_transform.scale_factor(self.scene_nwo)
        camera_data.clip_end = 1000

        camera = bpy.data.objects.new(camera_name, camera_data)
        camera.nwo.export_this = False
        collection.objects.link(camera)

        right = Vector((0.0, -1.0, 0.0))
        up = Vector((0.0, 0.0, 1.0))
        back = Vector((-1.0, 0.0, 0.0))
        matrix = Matrix((
            (right.x, up.x, back.x, 0.0),
            (right.y, up.y, back.y, 0.0),
            (right.z, up.z, back.z, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ))
        camera.matrix_world = import_transform.object_matrix(matrix, self.scene_nwo)
        
        if armature and camera_control_bone:
            con = camera.constraints.new('COPY_LOCATION')
            con.target = armature
            con.subtarget = camera_control_bone.name
            
            # con = camera.constraints.new('COPY_ROTATION')
            # con.target = armature
            # con.subtarget = camera_control_bone.name
            # con.target_space = 'LOCAL_OWNER_ORIENT'
            # con.owner_space = 'LOCAL'

        self.context.scene.camera = camera
        return camera

    def bake_imported_control_rig_actions(self):
        if not self.graph_bake_to_control_rig:
            return 0

        baked_count = 0
        for armature, actions in self.control_rig_action_batches:
            if armature.name not in bpy.data.objects:
                continue

            baked_count += bake_imported_actions_to_control_rig(self.context, armature, actions)

        if baked_count:
            utils.print_bullet(f"Baked {baked_count} imported animations to control rig FK bones")

        return baked_count

    def _should_cache_object_import(self, existing_armature, pose, make_non_export, for_instance_conversion, return_cin_stuff):
        return (
            return_cin_stuff
            and existing_armature is None
            and pose is None
            and not make_non_export
            and not for_instance_conversion
            and not self.tag_import_attachments
            and not getattr(self.import_fp_arms, "value", False)
        )

    def _get_object_import_cache_key(self, file: str, variant: str):
        return (
            str(file).lower(),
            variant,
            self.tag_permutation,
            self.tag_render,
            self.tag_markers,
            self.tag_state,
            self.import_variant_children,
            self.tag_import_attachments,
            self.build_control_rig,
            bool(self.tag_import_lights and self.corinth),
            getattr(self.import_fp_arms, "value", None),
        )

    def get_cached_object_import(self, cache_key, parent_collection: bpy.types.Collection):
        cache_entry = objects_cache.get(cache_key)
        if cache_entry is None:
            return None

        imported_objects, armature, render, model_collection, object_map = duplicate_cached_collection(
            cache_entry["collection"],
            cache_entry["render"],
            parent_collection,
            copy_object_data=cache_entry.get("copy_object_data", False),
        )
        for template_object, functions in cache_entry.get("prop_object_map", {}).items():
            new_object = object_map.get(template_object)
            if new_object is not None:
                self.obs_for_props[new_object] = functions

        return imported_objects, armature, render, model_collection

    def cache_object_import(self, cache_key, collection: bpy.types.Collection, render: str, copy_object_data=False):
        if cache_key in objects_cache:
            return objects_cache[cache_key]

        template_collection, object_map = clone_collection_hierarchy(
            collection,
            copy_object_data=copy_object_data,
            collection_name=f"{collection.name}_cache",
        )
        cache_entry = {
            "collection": template_collection,
            "render": render,
            "copy_object_data": copy_object_data,
            "prop_object_map": {
                object_map[source_object]: self.obs_for_props[source_object]
                for source_object in collection.all_objects
                if source_object in self.obs_for_props and source_object in object_map
            },
        }
        objects_cache[cache_key] = cache_entry
        return cache_entry

    def _ensure_region_entry(self, region: str, set_type: utils.SetType | None = None):
        if not region:
            return

        entry = self.scene_nwo.regions_table.get(region, 0)
        if not entry:
            entry = self.scene_nwo.regions_table.add()
            entry.old = region
            entry.name = region
        if set_type is not None:
            entry.set_type = set_type.name
        self.region_names.add(region)
        return entry.name

    def _ensure_permutation_entry(self, permutation: str, set_type: utils.SetType | None = None):
        if not permutation:
            return

        entry = self.scene_nwo.permutations_table.get(permutation, 0)
        if not entry:
            entry = self.scene_nwo.permutations_table.add()
            entry.old = permutation
            entry.name = permutation
        if set_type is not None:
            entry.set_type = set_type.name
        self.permutation_names.add(permutation)
        return entry.name

    def set_region(self, ob, region):
        self._ensure_region_entry(region)
        ob.nwo.region_name = region

    def set_permutation(self, ob, permutation):
        self._ensure_permutation_entry(permutation)
        ob.nwo.permutation_name = permutation

    def _ensure_tag_files_cache(self):
        global tag_files_cache
        global tag_files_by_name_cache
        if tag_files_by_name_cache:
            return tag_files_by_name_cache

        if not tag_files_cache:
            for root, _, files in os.walk(self.tags_dir):
                for file in files:
                    tag_files_cache.add(Path(root, file).with_suffix(""))

        tag_files_by_name_cache = {}
        for path_no_ext in tag_files_cache:
            tag_files_by_name_cache.setdefault(path_no_ext.name, []).append(path_no_ext)

        return tag_files_by_name_cache

    def _resolve_xref_tag_path(self, xref: 'XREF'):
        tag_path = ""
        fallback_tag_path = ""
        if xref.preferred_dir is not None:
            asset_dir = (xref.preferred_dir if xref.preferred_dir.name.casefold() == xref.name.casefold()
                         else xref.preferred_dir / xref.name)
            candidates = (asset_dir / xref.name, xref.preferred_dir / xref.name)
            fallback_tag_path = utils.relative_path(
                candidates[0].with_name(xref.name + xref.preferred_type))
            for base in candidates:
                for extension in (xref.preferred_type, *xref_tag_types):
                    path = base.with_name(xref.name + extension)
                    if path.is_file():
                        return utils.relative_path(path), fallback_tag_path

        tag_files_by_name = self._ensure_tag_files_cache()
        for path_no_ext in tag_files_by_name.get(xref.name, ()):
            path = path_no_ext.with_suffix(xref.preferred_type)
            if path.exists():
                tag_path = utils.relative_path(path)
                break

            for xtype in xref_tag_types:
                path = path_no_ext.with_suffix(xtype)
                if path.exists():
                    tag_path = utils.relative_path(path)
                    break

            if tag_path:
                break

        return tag_path, fallback_tag_path

    def _set_color_id_property(self, ob: bpy.types.Object, name: str, value):
        ob[name] = value
        ob.id_properties_ui(name).update(subtype="COLOR", min=0, max=1)


    def _apply_change_color_properties(self, ob: bpy.types.Object, change_colors):
        if change_colors is None:
            return

        for name, value in zip(("Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color"), change_colors):
            self._set_color_id_property(ob, name, value)

    def _add_id_prop_driver(self, ob: bpy.types.Object, armature: bpy.types.Object, prop: str):
        result = ob.driver_add(f'["{prop}"]')
        if isinstance(result, list):
            for idx, fcurve in enumerate(result):
                driver = fcurve.driver
                driver.type = 'SCRIPTED'
                var = driver.variables.new()
                var.name = "var"
                var.type = 'SINGLE_PROP'
                var.targets[0].id = armature
                var.targets[0].data_path = f'["{prop}"][{idx}]'
                driver.expression = var.name
            return

        driver = result.driver
        driver.type = 'SCRIPTED'
        var = driver.variables.new()
        var.name = "var"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = armature
        var.targets[0].data_path = f'["{prop}"]'
        driver.expression = var.name

    def _apply_jms_material_props(self, mesh: bpy.types.Mesh, nwo, jms_mat: 'JMSMaterialSlot', indices=None, apply_object_props=True):
        game = getattr(self, 'game', None)
        supports = lambda prop_type, face_mode=None: not game or face_prop_game_supported(prop_type, game, face_mode)

        if (jms_mat.two_sided or jms_mat.transparent_two_sided) and supports('face_sides'):
            utils.add_face_prop(mesh, "face_sides", indices)

        if (jms_mat.transparent_one_sided or jms_mat.transparent_two_sided) and supports('transparent'):
            utils.add_face_prop(mesh, "transparent", indices)
        if jms_mat.render_only and not mesh.nwo.proxy_collision and supports('face_mode', 'render_only'):
            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'render_only'
        if jms_mat.collision_only and supports('face_mode', 'collision_only'):
            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'collision_only'
        if jms_mat.sphere_collision_only and supports('face_mode', 'sphere_collision_only'):
            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'sphere_collision_only'

        if jms_mat.ladder and supports('ladder'):
            utils.add_face_prop(mesh, "ladder", indices)
        if jms_mat.breakable and supports('face_mode', 'breakable'):
            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'breakable'

        if apply_object_props:
            nwo.portal_exact = jms_mat.portal_exact
            nwo.portal_ai_deafening = jms_mat.ai_deafening

        if jms_mat.no_shadow and supports('no_shadow'):
            utils.add_face_prop(mesh, "no_shadow", indices)

        if jms_mat.lightmap_only and supports('face_mode', 'lightmap_only'):
            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'lightmap_only'
        if jms_mat.shadow_only and supports('face_mode', 'shadow_only'):
            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'shadow_only'
        if jms_mat.precise and supports('precise_position'):
            utils.add_face_prop(mesh, "precise_position", indices)

        if apply_object_props:
            if jms_mat.portal_one_way:
                nwo.portal_type = '_connected_geometry_portal_type_one_way'
            nwo.portal_is_door = jms_mat.portal_door
            if jms_mat.portal_vis_blocker:
                nwo.portal_type = '_connected_geometry_portal_type_no_way'
            nwo.portal_blocks_sounds = jms_mat.blocks_sound

        if jms_mat.ignored_by_lightmaps and supports('no_lightmap'):
            utils.add_face_prop(mesh, "no_lightmap", indices)

        if jms_mat.decal_offset and supports('decal_offset'):
            utils.add_face_prop(mesh, "decal_offset", indices)

        if jms_mat.slip_surface and supports('slip_surface'):
            utils.add_face_prop(mesh, "slip_surface", indices)

        # Legacy games store a multiplier (default 1); Reach stores a size-class
        # enum (default 3). Preserve both interpretations on the same face prop.
        legacy_resolution = getattr(jms_mat, 'lightmap_resolution_scale_legacy', None)
        if legacy_resolution is not None and legacy_resolution != 1 and supports('lightmap_resolution_scale'):
            prop = utils.add_face_prop(mesh, "lightmap_resolution_scale", indices)
            prop.lightmap_resolution_scale_legacy = legacy_resolution
            prop.lightmap_resolution_scale = str(jms_mat.lightmap_resolution_scale)
        if jms_mat.lightmap_additive_transparency and supports('lightmap_additive_transparency'):
            utils.add_face_prop(mesh, "lightmap_additive_transparency", indices).lightmap_additive_transparency = jms_mat.lightmap_additive_transparency
        if jms_mat.lightmap_translucency_tint_color and supports('lightmap_translucency_tint_color'):
            utils.add_face_prop(mesh, "lightmap_translucency_tint_color", indices).lightmap_translucency_tint_color = jms_mat.lightmap_translucency_tint_color
        if jms_mat.lightmap_transparency_override and supports('lightmap_transparency_override'):
            utils.add_face_prop(mesh, "lightmap_transparency_override", indices)

        if self.game == 'halo2' and getattr(jms_mat, 'emissive_power_scale', None) is not None and supports('emissive'):
            prop = utils.add_face_prop(mesh, "emissive", indices)
            prop.material_lighting_emissive_power_scale = jms_mat.emissive_power_scale
            prop.material_lighting_attenuation_falloff = 0.0
            prop.material_lighting_attenuation_cutoff = 0.0
        elif self.game != 'halo2' and jms_mat.emissive_power and supports('emissive'):
            prop = utils.add_face_prop(mesh, "emissive", indices)
            prop.material_lighting_emissive_power = jms_mat.emissive_power
            prop.material_lighting_emissive_color = jms_mat.emissive_color
            prop.material_lighting_emissive_quality = jms_mat.emissive_quality
            prop.material_lighting_emissive_per_unit = jms_mat.emissive_per_unit
            prop.material_lighting_use_shader_gel = jms_mat.emissive_shader_gel
            prop.material_lighting_emissive_focus = jms_mat.emissive_focus
            prop.material_lighting_attenuation_falloff = 0.0 if self.game == 'halo1' else jms_mat.emissive_attenuation_falloff
            prop.material_lighting_attenuation_cutoff = 0.0 if self.game == 'halo1' else jms_mat.emissive_attenuation_cutoff
        
    # Camera track import
    def import_camera_tracks(self, paths, animation_scale):
        cameras = []
        actions = []
        for file in paths:
            camera, action = self.import_camera_track(file, animation_scale)
            cameras.append(camera)
            actions.append(action)
        
        return cameras, actions
            
    def import_camera_track(self, file, animation_scale):
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with CameraTrackTag(path=mover.tag_path, tag_must_exist=True) as camera_track:
                camera, action = camera_track.to_blender_animation(self.context, animation_scale)
            
        return camera, action
    
    # Model Import

    def import_skies(self, paths, existing_armature, parent_collection=None, make_non_export=False):
        imported_objects = []
        imported_animations = []
        scene_collection = parent_collection or self.scene_collection
        for file in paths:
            utils.print_section(f'Importing Sky Tag: {Path(file).name}')
            with utils.TagImportMover(self.tags_dir, file) as mover:
                with SkyTag(path=mover.tag_path, raise_on_error=False) as sky:
                    if not sky.valid:
                        continue
                    source_tag_root = mover.potential_source_tag_dir if mover.needs_to_move else self.tags_dir
                    render = sky.get_model_path(source_tag_root)
                    animation = sky.get_animation_path(source_tag_root)
                    model_collection = bpy.data.collections.new(sky.tag_path.ShortName)
                    scene_collection.children.link(model_collection)
                    if make_non_export:
                        model_collection.nwo.type = 'exclude'
                    sky_lights = sky.lights_to_blender(model_collection)
                    for ob in sky_lights:
                        ob.visible_shadow = False
                    imported_objects.extend(sky_lights)
                    if not render or not Path(render).is_file():
                        utils.print_warning(f'Sky tag [{Path(file).name}] has no valid model reference')
                        continue
                    render_objects, armature = self.import_render_model(
                        render, model_collection, existing_armature, set())
                    for ob in render_objects:
                        ob.visible_shadow = False
                    imported_objects.extend(render_objects)

                    if animation and self.tag_animation and armature is not None and Path(animation).is_file():
                        print('Importing Animations')
                        imported_animations.extend(self.import_animation_graph(animation, armature, render))

                    if self.setup_as_asset:
                        set_asset(Path(render).suffix, armature, is_sky=True,
                                  tag_paths=asset_tag_paths(source_tag_root, render, animation),
                                  tag_root=source_tag_root)

        return imported_objects, imported_animations
    
    def import_models(self, paths, existing_armature):
        imported_objects = []
        imported_animations = []
        for file in paths:
            selection = self.tag_variant or self.tag_permutation
            if selection:
                print(f'Importing Model Tag: {Path(file).with_suffix("").name} [{selection}] ')
            else:
                print(f'Importing Model Tag: {Path(file).with_suffix("").name} ')
            with utils.TagImportMover(self.tags_dir, file) as mover:
                with ModelTag(path=mover.tag_path, raise_on_error=False) as model:
                    if not model.valid: continue
                    if mover.needs_to_move:
                        source_tag_root = mover.potential_source_tag_dir
                    else:
                        source_tag_root = self.tags_dir
                        
                    render, collision, animation, physics = model.get_model_paths(optional_tag_root=source_tag_root, override_type=self.tag_model_override_type)
                    
                    allowed_region_permutations = (model.get_halo1_region_permutations(self.tag_permutation) if model.game == 'halo1'
                                                   else model.get_variant_regions_and_permutations(self.tag_variant, self.tag_state))
                    selection = self.tag_variant or self.tag_permutation
                    if selection:
                        model_collection = bpy.data.collections.new(f"{model.tag_path.ShortName} [{selection}]")
                    else:
                        model_collection = bpy.data.collections.new(model.tag_path.ShortName)
                    self.scene_collection.children.link(model_collection)
                    if render:
                        render_objects, armature = self.import_render_model(render, model_collection, existing_armature, allowed_region_permutations)
                        set_variant_property(armature, model, selection)
                        imported_objects.extend(render_objects)
                    if collision and self.tag_collision:
                        imported_objects.extend(self.import_collision_model(collision, armature, model_collection, allowed_region_permutations))
                    if physics and self.tag_physics:
                        imported_objects.extend(self.import_physics_model(physics, armature, model_collection, allowed_region_permutations))
                    if animation and self.tag_animation:
                        print("Importing Animations")
                        imported_animations.extend(self.import_animation_graph(animation, armature, render))
                        
                    if self.tag_import_lights and self.corinth:
                        path = model.get_lighting_info()
                        if path is not None:
                            lighting_info_path = Path(path.Filename)
                            if lighting_info_path.exists():
                                with ScenarioStructureLightingInfoTag(path=str(lighting_info_path)) as info:
                                    light_objects = info.to_blender(model_collection)
                                    if light_objects:
                                        print(f"Imported {len(light_objects)} lights from {info.tag_path.RelativePathWithExtension}")
                                        imported_objects.extend(light_objects)
                                        for ob in light_objects:
                                            ob.parent = armature
                        
                    if self.setup_as_asset:
                        paths = asset_tag_paths(source_tag_root, render, collision, animation, physics)
                        paths['.model'] = model.tag_path.RelativePathWithExtension
                        set_asset(Path(file).suffix, armature, model.is_sky(),
                                  tag_paths=paths, tag_root=source_tag_root)
        
        return imported_objects, imported_animations

    def build_imported_control_rig(self, armature: bpy.types.Object):
        if not self.build_control_rig or armature is None or armature.type != 'ARMATURE':
            return

        if any(bone.name.startswith(("FK_", "IK_", "PT_", "CTRL_")) for bone in armature.data.bones):
            return

        pedestal = None
        pitch = None
        yaw = None
        uses_pedestal = False
        for bone in armature.data.bones:
            node_name = utils.remove_node_prefix(bone.name).lower()
            if node_name == pedestal_name and pedestal is None:
                pedestal = bone.name
                uses_pedestal = True
            elif node_name == aim_pitch_name and pitch is None:
                pitch = bone.name
            elif node_name == aim_yaw_name and yaw is None:
                yaw = bone.name

        uses_aim_bones = pitch is not None or yaw is not None
        reach_fp_fix = needs_reach_fp_ik_fix(armature.nwo.node_order_source)

        utils.deselect_all_objects()
        armature.select_set(True)
        utils.set_active_object(armature)
        if armature.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        rig = HaloRig(
            self.context,
            import_transform.scale_factor(),
            self.scene_nwo.forward_direction,
            uses_aim_bones,
            False,
        )
        rig.rig_ob = armature
        rig.rig_data = armature.data
        rig.rig_pose = armature.pose
        rig.build_bones(pedestal=pedestal, pitch=pitch, yaw=yaw)
        if uses_pedestal or uses_aim_bones:
            rig.build_and_apply_control_shapes(reach_fp_fix=reach_fp_fix, reverse_control=False)
        rig.apply_halo_bone_shape()
        rig.build_fk_ik_rig(reverse_controls=False, reach_fp_ik_fix=reach_fp_fix)
        rig.generate_bone_collections()
    
    def _merge_fp_armatures(self, armature, fp_armature, fp_objects, graph_nodes):
        # Shared roots (for example pedestal) must remain a single bone so the
        # animation graph and mesh vertex groups agree after Blender's join.
        utils.deselect_all_objects()
        armature.select_set(True)
        utils.set_active_object(armature)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        shared_names = {utils.remove_node_prefix(bone.name) for bone in fp_armature.data.bones}
        for bone in list(armature.data.edit_bones):
            if utils.remove_node_prefix(bone.name) in shared_names:
                armature.data.edit_bones.remove(bone)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        fp_armature.select_set(True)
        bpy.ops.object.join()

        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bones = {utils.remove_node_prefix(bone.name): bone for bone in armature.data.edit_bones}
        # Tool adds camera_control to FP graphs without adding it to either
        # render model. Its default local transform is identity.
        for node in graph_nodes:
            name = utils.remove_node_prefix(node.name)
            if name == 'camera_control' and name not in bones:
                bone = armature.data.edit_bones.new(node.name)
                bone.tail = (0, import_transform.scale_factor(self.scene_nwo), 0)
                if 0 <= node.parent_index < len(graph_nodes):
                    parent = bones.get(utils.remove_node_prefix(graph_nodes[node.parent_index].name))
                    if parent is not None:
                        bone.matrix = parent.matrix.copy()
                bones[name] = bone
        for index, node in enumerate(graph_nodes):
            bone = bones.get(utils.remove_node_prefix(node.name))
            if bone is None:
                continue
            if 0 <= node.parent_index < len(graph_nodes) and node.parent_index != index:
                parent = bones.get(utils.remove_node_prefix(graph_nodes[node.parent_index].name))
                if parent is not None and parent != bone:
                    bone.parent = parent
            else:
                bone.parent = None
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        for ob in fp_objects:
            world = ob.matrix_world.copy()
            ob.parent = armature
            ob.matrix_world = world
            if ob.type == 'MESH':
                for modifier in ob.modifiers:
                    if modifier.type == 'ARMATURE':
                        modifier.object = armature

    def _import_fp_arms(self, armature, animation, scene_collection, source_tag_root):
        globals_path = Path(source_tag_root) / "globals" / "globals.globals"
        if not globals_path.is_file():
            utils.print_warning(f"Couldn't find globals tag [{globals_path}], cannot import FP arms")
            return [], None, None
        with utils.TagImportMover(self.tags_dir, globals_path) as mover:
            with GlobalsTag(path=mover.tag_path) as globals:
                fp_camera_fov = globals.get_camera_fov()
                result = globals.get_fp_arms_path(self.import_fp_arms)
        if result is None:
            utils.print_warning("Failed to get FP arms reference for the selected character")
            return [], None, None
        fp_arms_path, tp_unit_path, allowed_fp_region_permutations = result
        if not Path(fp_arms_path).is_file():
            utils.print_warning(f"FP arms tag does not exist: {fp_arms_path}")
            return [], None, None
        fp_collection = bpy.data.collections.new(f"FP Arms - {self.import_fp_arms.name.title()}")
        scene_collection.children.link(fp_collection)
        # Compiled arms preserve the globals representation's permutations.
        # Embedded JMS sources can use different region/permutation names.
        with utils.TagImportMover(self.tags_dir, fp_arms_path) as mover:
            with RenderModelTag(path=mover.tag_path) as render_model:
                fp_objects, fp_armature = render_model.to_blend_objects(
                    fp_collection, True, self.tag_markers, scene_collection, None,
                    allowed_fp_region_permutations, no_io=True,
                    build_control_rig=False, selected_lod=self.render_lod)
        if fp_armature is None:
            utils.print_warning("FP arms tag has no skeleton")
            return fp_objects, None, None
        fp_objects.remove(fp_armature)
        fp_arm_name = fp_armature.name
        fp_arm_props = {name: getattr(fp_armature.nwo, name) for name in (
            "control_aim", "invert_control_aim", "invert_control_rig", "node_order_source")}
        graph_nodes = []
        if animation:
            with utils.TagImportMover(self.tags_dir, animation) as mover:
                with AnimationGraphTag(path=mover.tag_path) as graph:
                    graph_nodes = graph.nodes()
        self._merge_fp_armatures(armature, fp_armature, fp_objects, graph_nodes)
        armature.name = fp_arm_name
        utils.unlink(armature)
        fp_collection.objects.link(armature)
        for name, value in fp_arm_props.items():
            setattr(armature.nwo, name, value)
        change_colors = None
        if tp_unit_path and Path(tp_unit_path).is_file():
            with ObjectTag(path=tp_unit_path) as unit:
                change_colors = unit.get_change_colors()
        self.build_imported_control_rig(armature)
        self._create_fp_game_camera(fp_collection, armature, utils.get_pose_bone(armature, "camera_control"), fp_camera_fov)
        return fp_objects, fp_arms_path, change_colors

    def import_object(self, paths, existing_armature, pose=None, make_non_export=False, for_instance_conversion=False, return_cin_stuff=False, blender_scene=None, parent_collection=None) -> tuple[list[bpy.types.Object], list] | bpy.types.Collection:
        imported_objects = []
        imported_animations = []
        armature = None
        model_collection = None
        if parent_collection is not None:
            scene_collection = parent_collection
        elif blender_scene is None:
            scene_collection = self.scene_collection
        else:
            scene_collection = blender_scene.collection
            
        is_game_object = isinstance(paths, bpy.types.Object)
        if is_game_object:
            paths = [paths]
            self.tag_render = True
            self.tag_markers = True
            self.tag_state = 0
            self.import_variant_children = True
            
        elif for_instance_conversion:
            self.tag_render = True
            self.tag_collision = True
            self.tag_physics = True
            self.tag_state = 0
            self.import_variant_children = True
            
        for file in paths:
            imported_file_objects = []
            fp_default_models = ()
            if is_game_object:
                game_object = file
                file = str(Path(utils.get_tags_path(), game_object.nwo.marker_game_instance_tag_name))
                if not Path(file).is_file():
                    utils.print_warning(f"Game object tag does not exist: {game_object.nwo.marker_game_instance_tag_name}")
                    continue
            
            # cache_key = file, self.tag_variant
            # cached = objects_cache.get(cache_key)
            # need_to_cache = cached is None
            
            # if not need_to_cache and not self.tag_animation:
            #     print()
            #     if self.tag_variant:
            #         utils.print_tag(f'Using Cached Object Tag: {Path(file).name} [{self.tag_variant}]')
            #     else:
            #         utils.print_tag(f'Using Cached Object Tag: {Path(file).name} ')
            #     imported_file_objects, armature, render, model_collection = duplicate_cached_import(*cached, scene_collection)
            #     imported_objects.extend(imported_file_objects)
            #     continue
            
            selection = self.tag_variant or self.tag_permutation
            if selection:
                utils.print_section(f'Importing Object Tag: {Path(file).name} [{selection}]')
            else:
                utils.print_section(f'Importing Object Tag: {Path(file).name} ')
                
            with utils.TagImportMover(self.tags_dir, file) as mover:
                with ObjectTag(path=mover.tag_path, raise_on_error=False) as obj:
                    if not obj.valid:
                        continue
                    if is_game_object:
                        if game_object.nwo.marker_game_instance_tag_variant_name.strip():
                            self.tag_variant = game_object.nwo.marker_game_instance_tag_variant_name
                        elif obj.get_default_variant():
                            self.tag_variant = obj.get_default_variant()
                        else:
                            self.tag_variant = ""
                            
                    if for_instance_conversion or return_cin_stuff:
                        if not self.tag_variant:
                            if obj.get_default_variant():
                                self.tag_variant = obj.get_default_variant()
                            
                    model_path = obj.get_model_tag_path_full()
                    if not model_path or not Path(model_path).exists():
                        if is_game_object:
                            utils.print_warning(f"No model tag for game object {obj.tag_path.RelativePathWithExtension}")
                        continue
                    change_colors = obj.get_change_colors(self.tag_variant)
                    magazine_size = obj.get_magazine_size(find_weapon=True)
                    has_ammo = magazine_size > 0
                    if has_ammo:
                        print(f"--- Weapon has magazine size: {magazine_size}")
                    uses_tether = obj.get_uses_tether(find_weapon=True)
                    functions = obj.functions_to_blender()
                    # if functions:
                    #     print(f"--- Created Blender node groups for {len(functions)} object functions")
                    
                    prop_names = []
                    with utils.TagImportMover(self.tags_dir, model_path) as model_mover:
                        with ModelTag(path=model_mover.tag_path, raise_on_error=False) as model:
                            if not model.valid: continue
                            if model_mover.needs_to_move:
                                source_tag_root = mover.potential_source_tag_dir
                            else:
                                source_tag_root = self.tags_dir
                                
                            if obj.game == 'halo1':
                                render, collision, animation, physics = obj.get_halo1_model_paths(source_tag_root)
                            else:
                                render, collision, animation, physics = model.get_model_paths(optional_tag_root=source_tag_root)
                            
                            temp_variant = self.tag_variant

                            if not temp_variant and (for_instance_conversion or is_game_object or self.scene_nwo.asset_type == 'cinematic'):
                                if model.get_model_variants():
                                    temp_variant = model.get_model_variants()[0]

                            cache_key = None
                            if self._should_cache_object_import(existing_armature, pose, make_non_export, for_instance_conversion, return_cin_stuff):
                                cache_key = self._get_object_import_cache_key(file, temp_variant)
                                cached = self.get_cached_object_import(cache_key, scene_collection)
                                if cached is not None:
                                    imported_file_objects, armature, render, model_collection = cached
                                    imported_objects.extend(imported_file_objects)
                                    continue
                            
                            allowed_region_permutations = (model.get_halo1_region_permutations(self.tag_permutation) if obj.game == 'halo1'
                                                           else model.get_variant_regions_and_permutations(temp_variant, self.tag_state))
                            selection = temp_variant or self.tag_permutation
                            if selection:
                                model_collection = bpy.data.collections.new(f"{model.tag_path.ShortName} [{selection}]")
                            else:
                                model_collection = bpy.data.collections.new(model.tag_path.ShortName)
                            scene_collection.children.link(model_collection)
                            
                            if make_non_export:
                                model_collection.nwo.type = 'exclude'
                                
                            uses_fp_arms = not (is_game_object or for_instance_conversion) and self.import_fp_arms.value and obj.tag_path.Extension == "weapon"
                            if uses_fp_arms:
                                fp_index = self.import_fp_arms.value - 1
                                fp_model = obj.get_fp_model(fp_index)
                                fp_graph = obj.get_fp_animation(fp_index)
                                if fp_model is not None and Path(fp_model.Filename).is_file():
                                    render = fp_model.Filename
                                    animation = fp_graph.Filename if fp_graph is not None and Path(fp_graph.Filename).is_file() else ''
                                    allowed_region_permutations = set()
                                    # Third-person collision and physics use another skeleton.
                                    collision = physics = ''
                                    if not animation:
                                        utils.print_warning("Weapon has no first-person animation graph for the selected character")
                                else:
                                    utils.print_warning("Weapon has no first-person model for the selected character")
                                    uses_fp_arms = False
                                
                            # possible compass driver = abs(var/pi / (2*pi))
                            if render:
                                render_objects, armature = self.import_render_model(render, model_collection, existing_armature, allowed_region_permutations, allow_control_rig=(not uses_fp_arms))
                                set_variant_property(armature, model, selection)
                                
                                if pose:
                                    print(f"--- Posing {obj.tag_path.ShortName}")
                                    self.context.view_layer.update()
                                    node_mask, orientations = pose
                                    _apply_scenario_node_orientations(armature, node_mask, orientations)
                                    self.context.view_layer.update()
                                
                                if self.tag_import_attachments:
                                    attachments = obj.attachments_to_blender(armature, [m for m in render_objects if m.type == 'EMPTY'], model_collection)
                                    self.attachments.extend(attachments)
                                    imported_file_objects.extend([ao for a in attachments for ao in a.objects])
                                
                                if uses_fp_arms and armature is not None:
                                    fp_objects, fp_arms_path, fp_change_colors = self._import_fp_arms(
                                        armature, animation, scene_collection, source_tag_root)
                                    render_objects.extend(fp_objects)
                                    if fp_change_colors is not None:
                                        change_colors = fp_change_colors
                                    if fp_arms_path:
                                        fp_default_models = (fp_arms_path,)
                                        self.fp_arms_imported = True
                                    else:
                                        self.build_imported_control_rig(armature)

                                imported_file_objects.extend(render_objects)
                                
                                has_change_colors = change_colors is not None
                                
                                if has_change_colors:
                                    prop_names.extend(("Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color"))
                                
                                for ob in render_objects:
                                    if ob.type != 'EMPTY':
                                        if has_change_colors:
                                            self._apply_change_color_properties(ob, change_colors)

                                        if ob.type == 'MESH':
                                            self.obs_for_props[ob] = functions
                                            if obj.game in {'halo1', 'halo2'}:
                                                add_object_functions(self.context.scene, ob, armature, functions)
                                    
                                    if not is_game_object:    
                                        if ob.type == 'ARMATURE':
                                            # self.to_cursor_objects.add(ob)
                                            ob.nwo.cinematic_object = obj.tag_path.RelativePathWithExtension
                                            if temp_variant == self.tag_variant:
                                                ob.nwo.cinematic_variant = temp_variant
                                                
                                            if has_ammo:
                                                ob["Ammo"] = magazine_size
                                                ob.id_properties_ui("Ammo").update(min=0, max=int('9' * len(str(magazine_size))))
                                            if uses_tether:
                                                ob["Tether Distance"] = 0
                                                ob.id_properties_ui("Tether Distance").update(min=0, max=999)
                                                
                                        elif ob.type == 'MESH':
                                            for prop in prop_names:
                                                self._add_id_prop_driver(ob, armature, prop)
                                                                                
                            if not is_game_object and collision and self.tag_collision:
                                imported_file_objects.extend(self.import_collision_model(collision, armature, model_collection, allowed_region_permutations))
                            if not is_game_object and physics and self.tag_physics:
                                imported_file_objects.extend(self.import_physics_model(physics, armature, model_collection, allowed_region_permutations))
                            if not is_game_object and animation and self.tag_animation:
                                print("Importing Animation Graph")
                                imported_animations.extend(self.import_animation_graph(animation, armature, render, additional_render_models=fp_default_models))
                                
                            if self.tag_import_lights and self.corinth:
                                path = model.get_lighting_info()
                                if path is not None:
                                    lighting_info_path = Path(path.Filename)
                                    if lighting_info_path.exists():
                                        with ScenarioStructureLightingInfoTag(path=str(lighting_info_path)) as info:
                                            light_objects = info.to_blender(model_collection)
                                            if light_objects:
                                                print(f"Imported {len(light_objects)} lights from {info.tag_path.RelativePathWithExtension}")
                                                imported_file_objects.extend(light_objects)
                                                for ob in light_objects:
                                                    ob.parent = armature
                                
                            if self.import_variant_children and temp_variant:
                                child_collection = bpy.data.collections.new(name=f"{model.tag_path.ShortName}_child_objects")
                                model_collection.children.link(child_collection)
                                child_objects = model.get_variant_children(temp_variant)
                                if child_objects:
                                    utils.print_bullet("Importing Child Objects")
                                    for child in child_objects:
                                        if child.child_object is None:
                                            continue
                                        utils.print_step(f"--- {child.child_object.ShortNameWithExtension}")
                                        imported_file_objects.extend(self.import_child_object(child, armature, {ob: ob.nwo.marker_model_group for ob in render_objects if ob.type == 'EMPTY'}, child_collection, is_game_object))
                                    self.context.view_layer.update()
                                    
                            if self.import_biped_weapon and obj.tag_path.Extension == "biped":
                                weapon_paths = []
                                if self.biped_weapon_source and self.biped_weapon_source != BIPED_WEAPON_SOURCE_BIPED_TAG:
                                    weapon_paths.append(self.biped_weapon_source)
                                else:
                                    weapon_paths.extend(obj.get_unit_weapons())

                                if weapon_paths:
                                    weapon_collection = bpy.data.collections.new(name=f"{model.tag_path.ShortName}_weapon")
                                    model_collection.children.link(weapon_collection)
                                    for weapon in weapon_paths:
                                        weapon_name = Path(weapon.RelativePathWithExtension).name if hasattr(weapon, "RelativePathWithExtension") else PureWindowsPath(weapon).name
                                        utils.print_section(f"Importing Weapon: {weapon_name}")
                                        child = ChildObject(child_variant_name="")
                                        parent_marker, child_marker = obj.get_weapon_markers()
                                        child.parent_marker = parent_marker if parent_marker else "primary_weapon"
                                        child.child_marker = child_marker if obj.game == 'halo1' else (child_marker or "right_hand")
                                        child.child_object = weapon
                                        imported_file_objects.extend(self.import_child_object(
                                            child,
                                            armature,
                                            {ob: ob.nwo.marker_model_group for ob in render_objects if ob.type == 'EMPTY'},
                                            weapon_collection,
                                            is_game_object,
                                            make_armature_non_export=self.import_biped_weapon_non_export and self.scene_nwo.asset_type != 'cinematic',
                                            export_attach_point=not (self.import_biped_weapon_non_export and self.scene_nwo.asset_type != 'cinematic'),
                                        ))
                                    self.context.view_layer.update()
                                    
                            if not is_game_object and self.setup_as_asset:
                                paths = asset_tag_paths(source_tag_root, render, collision, animation, physics)
                                paths['.model'] = model.tag_path.RelativePathWithExtension
                                paths[Path(file).suffix] = obj.tag_path.RelativePathWithExtension
                                set_asset(Path(file).suffix, armature, model.is_sky(),
                                          tag_paths=paths, tag_root=source_tag_root)
                                
                            # if need_to_cache:
                            #     objects_cache[cache_key] = imported_file_objects, render, model_collection.name

                            if cache_key is not None and render and imported_file_objects:
                                self.cache_object_import(cache_key, model_collection, render, copy_object_data=True)
                                
                            imported_objects.extend(imported_file_objects)

        if is_game_object:
            return model_collection
        elif for_instance_conversion:
            return imported_objects, self.tag_variant
        elif return_cin_stuff:
            return imported_objects, armature, render, model_collection
        elif return_cin_stuff:
            return imported_objects, armature, render, model_collection
        else:
            return imported_objects, imported_animations
    
    def import_child_object(self, child_object: ChildObject, parent_armature: bpy.types.Object, markers: dict[bpy.types.Object: str], child_collection, is_game_object, make_armature_non_export=True, export_attach_point=False):
        imported_objects = []
        armature = None
        if child_object.child_object is None:
            return imported_objects

        def _copy_marker_transform(target: bpy.types.Object, marker: bpy.types.Object):
            target.constraints.clear()
            target.matrix_world = marker.matrix_world.copy()
            constraint = target.constraints.new(type='COPY_TRANSFORMS')
            constraint.target = marker
            return constraint
        
        def defer_copy_marker_transform(target: bpy.types.Object, marker: bpy.types.Object):
            deferred_ops.append(partial(_copy_marker_transform, target, marker))
        
        # cache_key = child_object.child_object, child_object.child_variant_name
        # cached = objects_cache.get(cache_key)
        # need_to_cache = cached is None
        # if not need_to_cache:
        #     imported_file_objects, armature, render, model_collection = duplicate_cached_import(*cached, child_collection)
        #     imported_objects.extend(imported_file_objects)
        #     return imported_objects
        
        with ObjectTag(path=child_object.child_object, raise_on_error=False) as obj:
            model_path = obj.get_model_tag_path_full()
            if not model_path or not Path(model_path).exists():
                return imported_objects
            change_colors = obj.get_change_colors(self.tag_variant)
            has_change_colors = change_colors is not None
            magazine_size = obj.get_magazine_size(find_weapon=True)
            has_ammo = magazine_size > 0
            if has_ammo:
                print(f"--- Weapon has magazine size: {magazine_size}")
            uses_tether = obj.get_uses_tether(find_weapon=True)
            functions = obj.functions_to_blender()
            if functions:
                print(f"--- Created Blender node groups for {len(functions)} object functions")
            
            default_variant = obj.get_default_variant()
            prop_names = []
            with ModelTag(path=model_path, raise_on_error=False) as model:
                if not model.valid: return

                if obj.game == 'halo1':
                    render, collision, animation, physics = obj.get_halo1_model_paths()
                else:
                    render, collision, animation, physics = model.get_model_paths(override_type=self.tag_model_override_type)
                temp_variant = child_object.child_variant_name

                if not temp_variant:
                    if default_variant:
                        temp_variant = default_variant
                    elif model.get_model_variants():
                        temp_variant = model.get_model_variants()[0]

                allowed_region_permutations = (model.get_halo1_region_permutations(temp_variant) if obj.game == 'halo1'
                                               else model.get_variant_regions_and_permutations(temp_variant, self.tag_state))
                if temp_variant:
                    model_collection = bpy.data.collections.new(f"{model.tag_path.ShortName} [{temp_variant}]")
                else:
                    model_collection = bpy.data.collections.new(model.tag_path.ShortName)
                child_collection.children.link(model_collection)

                if has_change_colors:
                    prop_names.extend(("Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color"))
                
                if render:
                    render_objects, armature = self.import_render_model(render, model_collection, None, allowed_region_permutations)
                    set_variant_property(armature, model, temp_variant)
                    imported_objects.extend(render_objects)
                    for ob in render_objects:
                        if ob.type != 'EMPTY':
                            if has_change_colors:
                                self._apply_change_color_properties(ob, change_colors)

                            if ob.type == 'MESH':
                                self.obs_for_props[ob] = functions
                                if obj.game in {'halo1', 'halo2'}:
                                    add_object_functions(self.context.scene, ob, armature, functions)
                                
                        if ob.type == 'ARMATURE':
                            if make_armature_non_export:
                                ob.nwo.export_this = False
                            ob.nwo.cinematic_object = obj.tag_path.RelativePathWithExtension
                            if temp_variant == self.tag_variant:
                                ob.nwo.cinematic_variant = temp_variant
                                
                            if has_ammo:
                                ob["Ammo"] = magazine_size
                                ob.id_properties_ui("Ammo").update(min=0, max=int('9' * len(str(magazine_size))))
                            if uses_tether:
                                ob["Tether Distance"] = 0
                                ob.id_properties_ui("Tether Distance").update(min=0, max=999)
                                
                        elif ob.type == 'MESH':
                            for prop in prop_names:
                                self._add_id_prop_driver(ob, armature, prop)
                                    
                    if not is_game_object and collision and self.tag_collision:
                        imported_objects.extend(self.import_collision_model(collision, armature, model_collection, allowed_region_permutations))
                    if not is_game_object and physics and self.tag_physics:
                        imported_objects.extend(self.import_physics_model(physics, armature, model_collection, allowed_region_permutations))
                        
                    if self.tag_import_lights and self.corinth:
                        path = model.get_lighting_info()
                        if path is not None:
                            lighting_info_path = Path(path.Filename)
                            if lighting_info_path.exists():
                                with ScenarioStructureLightingInfoTag(path=str(lighting_info_path)) as info:
                                    light_objects = info.to_blender(model_collection)
                                    if light_objects:
                                        print(f"Imported {len(light_objects)} lights from {info.tag_path.RelativePathWithExtension}")
                                        imported_objects.extend(light_objects)
                                        for ob in light_objects:
                                            ob.parent = armature
                        
                    marker_children = []
                        
                    if child_object.child_marker:
                        for marker_ob, group_name in {ob: ob.nwo.marker_model_group for ob in render_objects if ob.type == 'EMPTY'}.items():
                            if group_name == child_object.child_marker:
                                marker_children.append(marker_ob)
                                
                    if marker_children:
                        attach_point = marker_children[0].copy()
                        attach_point.name = f"{obj.tag_path.ShortName}_attach"
                        attach_point_matrix = attach_point.matrix_world.copy()
                        attach_point.parent = None
                        attach_point.matrix_world = attach_point_matrix
                        attach_point.nwo.export_this = export_attach_point
                        child_collection.objects.link(attach_point)
                        imported_objects.append(attach_point)
                        arm_matrix = armature.matrix_world.copy()
                        armature.parent = attach_point
                        armature.matrix_world = arm_matrix
                        
                    marker_parents = []
                    
                    if child_object.parent_marker:
                        for marker_ob, group_name in markers.items():
                            if group_name == child_object.parent_marker:
                                marker_parents.append(marker_ob)

                    if marker_parents:
                        if marker_children:
                            _copy_marker_transform(attach_point, marker_parents[0])
                        else:
                            defer_copy_marker_transform(armature, marker_parents[0])
                    else:
                        if marker_children:
                            attach_point.parent = parent_armature
                            attach_point.matrix_world = parent_armature.matrix_world
                        else:
                            armature.parent = parent_armature
                            
                    # if need_to_cache:
                    #     objects_cache[cache_key] = imported_objects, render, model_collection.name
 
        return imported_objects
            
    def import_render_model(self, file, model_collection, existing_armature, allowed_region_permutations, skip_print=False, allow_control_rig=True):
        # Attachments need their model markers even when standalone marker
        # import is disabled. Otherwise light tags convert but produce no objects.
        import_markers = self.tag_markers or self.tag_import_attachments
        if not skip_print:
            utils.print_tag("Importing Render Model")
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        use_tag_skeleton = source_files and self.game in {'halo2', 'halo3', 'halo3odst'}
        if use_tag_skeleton:
            collection = bpy.data.collections.new(Path(file).stem + '_render')
            model_collection.children.link(collection)
            with utils.TagImportMover(self.tags_dir, file) as mover:
                with RenderModelTag(path=mover.tag_path) as render_model:
                    tag_objects, armature = render_model.to_blend_objects(
                        collection, False, import_markers, model_collection,
                        existing_armature, allowed_region_permutations,
                        build_control_rig=self.build_control_rig and allow_control_rig)
                    tag_objects.extend(render_model.skylights_to_blender(collection))
                    shader_paths = {}
                    for record in render_model.render_materials():
                        reference = record.render_method
                        name = reference.ShortName.lower()
                        path = reference.RelativePathWithExtension
                        # A basename shared inside this tag is ambiguous; leave
                        # it unresolved rather than assigning an arbitrary shader.
                        shader_paths[name] = path if shader_paths.get(name, path) == path else ''
                    source_objects = self.import_jms_files(
                        source_files, 'model', tag_armature=armature,
                        parent_collection=collection, geometry_only=True,
                        allowed_region_permutations=render_model._resolve_region_permutations(
                            allowed_region_permutations), shader_paths=shader_paths)
                    if self.build_control_rig and allow_control_rig:
                        render_model._apply_control_rig_deform_shapes_after_geometry()
                    sky_data = render_model.sky_data()
                    if sky_data.is_sky or sky_data.lights:
                        for ob in tag_objects + source_objects:
                            ob.visible_shadow = False
            return tag_objects + source_objects, armature
        if source_files:
            objects = self.import_jms_files(source_files, 'model', parent_collection=model_collection)
            armature = next((ob for ob in objects if ob.type == 'ARMATURE'), existing_armature)
            if armature is not None and self.game != 'halo1':
                armature.nwo.node_order_source = utils.relative_path(file)
            with utils.TagImportMover(self.tags_dir, file) as mover:
                with RenderModelTag(path=mover.tag_path) as render_model:
                    sky_data = render_model.sky_data()
                    if sky_data.is_sky or sky_data.lights:
                        for ob in objects:
                            ob.visible_shadow = False
            return objects, armature
        render_model_objects = []
        armature = None
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name) + "_render")
        model_collection.children.link(collection)
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with RenderModelTag(path=mover.tag_path) as render_model:
                render_model_objects, armature = render_model.to_blend_objects(collection, self.tag_render, import_markers, model_collection, existing_armature, allowed_region_permutations, self.from_vert_normals, build_control_rig=self.build_control_rig and allow_control_rig, selected_lod=self.render_lod)
                render_model_objects.extend(render_model.skylights_to_blender(collection))
                sky_data = render_model.sky_data()
                if sky_data.is_sky or sky_data.lights:
                    for ob in render_model_objects:
                        ob.visible_shadow = False
            
        return render_model_objects, armature
    
    def import_standalone_model_geometry(self, file, kind, armature=None):
        model_collection = bpy.data.collections.new(Path(file).stem)
        self.scene_collection.children.link(model_collection)
        objects = []
        if armature is None:
            path = Path(file)
            extensions = ('.gbxmodel', '.model') if self.game == 'halo1' else ('.render_model',)
            candidates = sorted((candidate for candidate in path.parent.iterdir()
                                 if candidate.is_file() and candidate.suffix.lower() in extensions),
                                key=lambda candidate: (candidate.stem.casefold() != path.stem.casefold(),
                                                       extensions.index(candidate.suffix.lower()),
                                                       candidate.name.casefold()))
            if candidates:
                if not hasattr(self, '_standalone_model_armatures'):
                    self._standalone_model_armatures = {}
                render_path = candidates[0].resolve()
                armature = self._standalone_model_armatures.get(render_path)
                if armature is None:
                    with utils.TagImportMover(self.tags_dir, render_path) as mover:
                        with RenderModelTag(path=mover.tag_path) as render_model:
                            skeleton_objects, armature = render_model.to_blend_objects(
                                model_collection, False, False, model_collection,
                                build_control_rig=False)
                            objects.extend(skeleton_objects)
                    self._standalone_model_armatures[render_path] = armature
        import_geometry = self.import_collision_model if kind == 'collision_model' else self.import_physics_model
        objects.extend(import_geometry(file, armature, model_collection, set()))
        return objects

    def import_collision_model(self, file, armature, model_collection,allowed_region_permutations):
        print("Importing Collision Model")
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files and armature is not None:
            collection = bpy.data.collections.new(Path(file).stem + '_collision')
            collection.hide_render = True
            model_collection.children.link(collection)
            return self.import_jms_files(source_files, 'model',
                                         tag_armature=armature,
                                         parent_collection=collection,
                                         allowed_region_permutations=allowed_region_permutations)
        collision_model_objects = []
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name) + "_collision")
        collection.hide_render = True
        model_collection.children.link(collection)
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with CollisionTag(path=mover.tag_path) as collision_model:
                collision_model_objects = collision_model.to_blend_objects(collection, armature, allowed_region_permutations)
            
        return collision_model_objects
    
    def import_physics_model(self, file, armature, model_collection, allowed_region_permutations):
        print("Importing Physics Model")
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files and armature is not None:
            collection = bpy.data.collections.new(Path(file).stem + '_physics')
            collection.hide_render = True
            model_collection.children.link(collection)
            return self.import_jms_files(source_files, 'model',
                                         tag_armature=armature,
                                         parent_collection=collection,
                                         allowed_region_permutations=allowed_region_permutations)
        physics_model_objects = []
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name) + "_physics")
        collection.hide_render = True
        model_collection.children.link(collection)
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with PhysicsTag(path=mover.tag_path) as physics_model:
                physics_model_objects = physics_model.to_blend_objects(collection, armature, allowed_region_permutations)
            
        return physics_model_objects
    
    def import_animation_graph(self, file, armature, render, return_animations=False, additional_render_models=()):
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_animation_formats
        ]
        convert_locomotes = (self.convert_animations and self.target_game in {'halo4', 'halo2a'}
                             and self.game in LEGACY_GAMES | {'reach'})
        convert_style = self.convert_animations and (
            self.game in LEGACY_GAMES and self.target_game in REACH_PLUS_GAMES
            or self.game in REACH_PLUS_GAMES and self.target_game in LEGACY_GAMES
            or convert_locomotes)
        # Style conversion needs the graph's blend-screen coordinates, even when
        # an import-info JMA is available for this graph.
        if source_files and not convert_style:
            blend_screen_choices = {}
            if self.game in LEGACY_GAMES:
                with utils.TagImportMover(self.tags_dir, file) as mover:
                    with AnimationGraphTag(path=mover.tag_path) as graph:
                        blend_screen_choices = graph.blend_screens_to_blender()
            imported_animation_start = len(self.scene_nwo.animations)
            actions = self.import_jma_files(source_files, armature)
            animations = list(self.scene_nwo.animations[imported_animation_start:])
            choices_by_name = {
                name.replace(':', ' ').casefold(): screen
                for name, screen in blend_screen_choices.items()
            }
            for animation in animations:
                if animation.animation_type == 'overlay':
                    animation.blend_screen = choices_by_name.get(
                        animation.name.replace(':', ' ').casefold(), '')
            return (actions, animations) if return_animations else actions
        actions = []
        animations = []
        legacy_frame_maps = {}
        reach_duplicate_frames = {}
        imported_animation_start = len(self.scene_nwo.animations)
        filter = self.tag_animation_filter.replace(" ", ":")
        self.context.scene.render.fps = 30
        self.context.scene.render.fps_base = 1
        with utils.TagImportMover(self.tags_dir, file) as mover:
            forced_compression_value = 0
            graph_metadata = None
            blend_screen_choices = {}
            with AnimationGraphTag(path=mover.tag_path) as graph:
                forced_compression_value = graph.forced_compression()
                graph_metadata = graph.import_metadata()
                convert_to_reach = (self.convert_animations and graph.game in LEGACY_GAMES
                                    and self.target_game in REACH_PLUS_GAMES)
                convert_to_legacy = (self.convert_animations and graph.game in REACH_PLUS_GAMES
                                     and self.target_game in LEGACY_GAMES)
                legacy_blend_screens = graph.blend_screens() if convert_to_reach else {}
                if graph.game in LEGACY_GAMES:
                    blend_screen_choices = graph.blend_screens_to_blender()
                if self.graph_import_ik_chains:
                    if armature == self.scene_nwo.main_armature or self.scene_nwo.main_armature is None:
                        self.scene_nwo.main_armature = armature
                        utils.print_bullet("Importing IK Chains")
                        count = graph.ik_chains_to_blender(armature)
                        utils.print_bullet(f"Added / Updated {count} IK Chains")
                match forced_compression_value:
                    case 0:
                        self.scene_nwo.forced_animation_compression = 'none'
                    case 3:
                        self.scene_nwo.forced_animation_compression = 'uncompressed'
                    case 1:
                        self.scene_nwo.forced_animation_compression = 'medium'
                    case 2:
                        self.scene_nwo.forced_animation_compression = 'rough'
                        
            with AnimationTag(path=mover.tag_path) as graph:
                utils.print_section(f"Importing Animation Graph: {graph.tag_path.ShortNameWithExtension}")
                if self.graph_import_animations:
                    utils.print_bullet("Importing Animations")
                    if self.corinth and self.graph_import_pca_data:
                        result = graph.to_blender(
                            render,
                            armature,
                            filter,
                            import_pca=True,
                            scale_animations_to_skeleton=self.graph_scale_animations_to_skeleton,
                            metadata=graph_metadata,
                            additional_render_models=additional_render_models,
                            convert_to_reach=convert_to_reach,
                            convert_to_legacy=convert_to_legacy,
                            legacy_blend_screens=legacy_blend_screens,
                            blend_screen_choices=blend_screen_choices,
                            convert_animation_names=self.convert_animations,
                            target_game=self.target_game,
                        )
                        if result is not None:
                            actions, animations, pca_animations, pca_groups, pca_path = result
                            if pca_animations and pca_groups and pca_path is not None:
                                pca_info = PCAInfo()
                                pca_info.objects = [ob for ob in armature.children if ob.type == 'MESH']
                                pca_info.pca_animations = pca_animations
                                pca_info.pca_groups = pca_groups
                                pca_info.pca_path = pca_path
                                self.pca_info.append(pca_info)
                    else:
                        result = graph.to_blender(
                            render,
                            armature,
                            filter,
                            import_pca=False,
                            scale_animations_to_skeleton=self.graph_scale_animations_to_skeleton,
                            metadata=graph_metadata,
                            additional_render_models=additional_render_models,
                            convert_to_reach=convert_to_reach,
                            convert_to_legacy=convert_to_legacy,
                            legacy_blend_screens=legacy_blend_screens,
                            blend_screen_choices=blend_screen_choices,
                            convert_animation_names=self.convert_animations,
                            target_game=self.target_game,
                        )
                        if result is not None:
                            actions, animations = result
                    if convert_to_legacy:
                        legacy_frame_maps = graph.legacy_frame_maps
                    if convert_to_reach:
                        reach_duplicate_frames = graph.reach_duplicate_frames

            if self.graph_generate_renames:
                utils.print_bullet("Generating Animation Renames and Copies")
                with AnimationGraphTag(path=mover.tag_path) as graph:
                    graph.generate_renames(
                        filter, self.convert_animations, self.target_game)
            if self.graph_import_events:
                utils.print_bullet("Importing Frame Events")
                imported_animations = self.scene_nwo.animations[imported_animation_start:]
                with AnimationGraphTag(path=mover.tag_path) as graph:
                    count = graph.events_to_blender(
                        imported_animations, self.convert_animations,
                        self.target_game)
                utils.print_bullet(f"Imported {count} frame events")

        if convert_to_legacy and self.graph_import_animations:
            from .animation.reach_import import remap_legacy_screen_events
            remap_legacy_screen_events(self.scene_nwo.animations[imported_animation_start:], legacy_frame_maps)

        if convert_to_reach and self.graph_import_animations:
            from .animation.legacy_import import (
                combine_reach_acc_overlays, strip_reach_blend_screen_duplicates,
            )
            strip_reach_blend_screen_duplicates(
                armature, self.scene_nwo.animations[imported_animation_start:],
                reach_duplicate_frames,
            )
            combined = combine_reach_acc_overlays(
                self.scene_nwo, armature,
                self.scene_nwo.animations[imported_animation_start:],
            )
            if combined:
                animations = [item.name for item in self.scene_nwo.animations[imported_animation_start:]]
                actions = list(dict.fromkeys(track.action
                               for item in self.scene_nwo.animations[imported_animation_start:]
                               for track in item.action_tracks if track.action is not None))
                utils.print_bullet(f'Combined {len(combined)} acceleration overlays')

        if (convert_to_reach or convert_locomotes) and self.graph_import_animations:
            from .animation.legacy_import import generate_reach_aim_look_overlays
            from .animation.legacy_turns import convert_reach_turn_poses
            converted_turns = []
            if convert_to_reach:
                utils.print_bullet("Converting Turn Poses")
                converted_turns = convert_reach_turn_poses(
                    self.scene_nwo, armature,
                    self.scene_nwo.animations[imported_animation_start:],
                )
                utils.print_bullet(f"Converted {len(converted_turns)} turn poses")
            utils.print_bullet("Generating Aim / Look Overlays")
            generated = generate_reach_aim_look_overlays(
                self.scene_nwo, armature,
                self.scene_nwo.animations[imported_animation_start:],
                turns_with_aim_pose=converted_turns,
                prefer_move=convert_locomotes,
            )
            for animation in generated:
                animations.append(animation.name)
                actions.extend(track.action for track in animation.action_tracks
                               if track.action is not None)
            utils.print_bullet(f"Generated {len(generated)} aim/look overlays")

        if convert_locomotes and self.graph_import_animations:
            from .animation.locomote_import import convert_locomotion
            utils.print_bullet("Generating Locomote Composites")
            generated = convert_locomotion(self.scene_nwo, armature, imported_animation_start)
            animations = [animation.name for animation in self.scene_nwo.animations[imported_animation_start:]]
            actions = list(dict.fromkeys(track.action
                           for animation in self.scene_nwo.animations[imported_animation_start:]
                           for track in animation.action_tracks if track.action is not None))
            utils.print_bullet(f"Generated {len(generated)} locomotion animations / composites")

        self.register_control_rig_actions(armature, actions)

        if return_animations:
            return actions, animations
        
        return actions
    
    def _scenario_objects_to_blender(self, scenario, parent_collection=None, bvh=None, bsp_indices=None):
        object_name_count, folder_records, placements = scenario.object_placements()
        objects = []
        child_objects = {}
        skeleton_poses = []

        objects_collection = bpy.data.collections.new(name=f"{scenario.tag_path.ShortName}_objects")
        objects_collection.nwo.type = 'exclude'
        if parent_collection is None:
            bpy.context.scene.collection.children.link(objects_collection)
        else:
            parent_collection.children.link(objects_collection)

        folders = []
        for record in folder_records:
            folder = bpy.data.collections.new(record.name)
            folders.append(folder)
        for folder, record in zip(folders, folder_records):
            if 0 <= record.parent_index < len(folders):
                folders[record.parent_index].children.link(folder)
            else:
                objects_collection.children.link(folder)

        named_objects = [None] * object_name_count
        used_folders = set()
        for block_name, _ in scenario.OBJECT_BLOCKS:
            block_placements = [placement for placement in placements
                                if placement.block_name == block_name]
            if not block_placements:
                continue
            print(f"Creating Scenario {block_name.capitalize()} Objects")
            collection = bpy.data.collections.new(name=block_name)
            objects_collection.children.link(collection)
            used_collection = False
            for placement in block_placements:
                if placement.definition is None:
                    continue
                if bsp_indices is not None and placement.bsps:
                    if not placement.bsps.intersection(bsp_indices):
                        continue
                elif bvh:
                    point = Vector(tuple(value * 100 for value in placement.position))
                    if not utils.test_point_bvh(bvh, point):
                        continue

                position = Vector(tuple(value * 100 for value in placement.position))
                yaw, pitch, roll = placement.rotation
                rotation = Euler((roll, -pitch, yaw), 'ZYX')
                ob = bpy.data.objects.new(name=placement.name, object_data=None)
                ob.empty_display_type = "ARROWS"
                ob.matrix_world = import_transform.marker_matrix(Matrix.LocRotScale(
                    position, rotation, Vector.Fill(3, placement.scale)))
                ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                ob.nwo.marker_game_instance_tag_name = placement.definition
                ob.nwo.marker_game_instance_tag_variant_name = placement.variant

                if 0 <= placement.name_index < len(named_objects):
                    named_objects[placement.name_index] = ob
                if placement.parent_index >= 0:
                    child_objects[ob] = placement.parent_index
                if 0 <= placement.folder_index < len(folders):
                    folder = folders[placement.folder_index]
                    folder.objects.link(ob)
                    used_folders.add(folder)
                else:
                    collection.objects.link(ob)
                    used_collection = True
                objects.append(ob)
                skeleton_poses.append(None)

            if not used_collection:
                bpy.data.collections.remove(collection)

        for ob, parent_index in child_objects.items():
            if 0 <= parent_index < len(named_objects):
                parent = named_objects[parent_index]
                if parent is not None:
                    ob.parent = parent

        for folder in folders:
            if folder in used_folders:
                continue
            if not any(child in used_folders for child in folder.children_recursive):
                bpy.data.collections.remove(folder)

        return objects, skeleton_poses

    def _scenario_decals_to_blender(self, scenario, parent_collection=None, bvh=None, bsp_indices=None):
        placements = scenario.decal_placements()
        if not placements:
            return []
        print("Creating Scenario Decals")
        collection = bpy.data.collections.new(name=f"{scenario.tag_path.ShortName}_decals")
        collection.nwo.type = 'exclude'
        if parent_collection is None:
            bpy.context.scene.collection.children.link(collection)
        else:
            parent_collection.children.link(collection)

        material_cache = {}
        objects = []
        for placement in placements:
            if placement.definition is None:
                continue
            has_bsp_filter = bsp_indices is not None and placement.bsps
            if has_bsp_filter:
                if not placement.bsps.intersection(bsp_indices):
                    continue
            position = Vector(tuple(value * 100 for value in placement.position))
            if not has_bsp_filter and bvh and not utils.test_point_bvh(bvh, position):
                continue

            material = material_cache.get(placement.definition)
            if placement.definition not in material_cache:
                material = None
                if scenario.game in {'halo1', 'halo2'}:
                    from ..tags.shader_converter import ShaderTag
                    decal_name = Path(placement.definition).stem
                    material = bpy.data.materials.get(decal_name)
                    if material is None:
                        material = bpy.data.materials.new(decal_name)
                        material.nwo.shader_path = placement.definition
                        with ShaderTag(path=placement.definition) as decal:
                            decal.to_nodes(material, generated_uvs=True)
                else:
                    tag_type = DecalSystemCorinthTag if scenario.corinth else DecalSystemTag
                    with tag_type(path=placement.definition) as decal:
                        for element in decal.tag.SelectField("Block:decals").Elements:
                            decal_name = f'{decal.tag_path.ShortName}_{element.SelectField("StringId:decal name").GetStringData()}'
                            material = bpy.data.materials.get(decal_name)
                            if material is None:
                                decal.reread_fields(element.ElementIndex)
                                material = bpy.data.materials.new(decal_name)
                                decal.to_nodes(material, generated_uvs=True)
                material_cache[placement.definition] = material

            scale_x, scale_y = (value * 100 for value in placement.scale)
            mesh = bpy.data.meshes.new(placement.name)
            mesh.from_pydata((
                (-scale_x / 2, -scale_y / 2, 0),
                (scale_x / 2, -scale_y / 2, 0),
                (scale_x / 2, scale_y / 2, 0),
                (-scale_x / 2, scale_y / 2, 0),
            ), [], ((0, 1, 2, 3),))
            mesh.transform(import_transform.mesh_matrix())
            ob = bpy.data.objects.new(name=placement.name, object_data=mesh)
            rotation = utils.ijkw_to_wxyz(placement.rotation)
            matrix = Matrix.LocRotScale(position, rotation, Vector.Fill(3, 1))
            normal = matrix.to_3x3() @ Vector((0, 0, 1))
            matrix.translation += normal.normalized() * 0.1
            ob.matrix_world = import_transform.object_matrix(matrix)
            if material is not None:
                mesh.materials.append(material)
            collection.objects.link(ob)
            objects.append(ob)
        return objects

    def _scenario_decorators_to_blender(self, scenario, parent_collection=None, bvh=None):
        start_time = time.perf_counter()
        decorator_sets = scenario.decorator_sets()
        if not decorator_sets:
            return []
        print("Creating Scenario Decorators")
        collection = bpy.data.collections.new(name=f"{scenario.tag_path.ShortName}_decorators")
        if parent_collection is None:
            bpy.context.scene.collection.children.link(collection)
        else:
            parent_collection.children.link(collection)

        objects = []
        placement_count = 0
        for record in decorator_sets:
            with DecoratorSetTag(path=record.definition) as decorator_set:
                types = {item.decorator_type_index: item
                         for item in decorator_set.get_decorator_types()}
            print(f"  Processing {record.definition} - {len(record.placements)} placed in scenario")
            clouds, accepted = _decorator_records_to_clouds(
                record.placements, record.definition, record.name, types, collection, bvh)
            objects.extend(clouds)
            placement_count += accepted

        elapsed = time.perf_counter() - start_time
        if placement_count != len(objects):
            print(f"Finished creating {placement_count} decorator placements in {len(objects)} cloud objects in {elapsed:.3f}s total")
        else:
            print(f"Finished creating {len(objects)} decorators in {elapsed:.3f}s total")
        return objects
    
    def import_scenarios(self, paths, build_blender_materials, always_extract_bitmaps, return_collection=False, merge_sky_to_scenario_collection=False):
        imported_objects = []
        scene_nwo = utils.get_scene_props()
        scene_skies = scene_nwo.scenario_skies
        for file in paths:
            if self.tag_zone_set:
                utils.print_section(f'Importing Scenario Tag: {Path(file).with_suffix("").name} with Zone Set {self.tag_zone_set}')
            else:
                utils.print_section(f'Importing Scenario Tag: {Path(file).with_suffix("").name}')
            structure_collision = []
            with utils.TagImportMover(self.tags_dir, file) as mover:
                with ScenarioMetadataTag(path=mover.tag_path, raise_on_error=False) as scenario:
                    if not scenario.valid: continue
                    scene_skies.clear()
                    scene_nwo.skies_authored_from_blender = True
                    for sky_path in scenario.get_sky_references():
                        scene_skies.add().path = sky_path
                    bsps = scenario.get_bsp_paths(self.tag_zone_set)
                    if scenario.game in {'halo1', 'halo2'} and self.tag_bsp:
                        bsps = [bsp for bsp in bsps if Path(bsp).stem.casefold() == self.tag_bsp.casefold()]
                        if not bsps:
                            raise ValueError(f"BSP '{self.tag_bsp}' was not found in {file}")
                    all_bsps = scenario.get_bsp_paths()
                    bsp_sky_indices = scenario.get_sky_indices()
                    index_map = {b: i for i, b in enumerate(all_bsps)}
                    sky_index_map = {i: b for i, b in enumerate(bsp_sky_indices)}
                    bsp_indices_list = [index_map[b] for b in bsps]
                    bsp_indices = set(bsp_indices_list)
                    sky_indices = [sky_index_map[b] for b in bsp_indices_list]
                    
                    match scenario.read_scenario_type():
                        case 0:
                            if scenario.survival_mode():
                                self.tag_model_override_type = RenderModelOverrideType.firefight
                            else:
                                self.tag_model_override_type = RenderModelOverrideType.campaign
                        case 1:
                            self.tag_model_override_type = RenderModelOverrideType.multiplayer
                        case 2:
                            self.tag_model_override_type = RenderModelOverrideType.mainmenu
                    
                    do_raycasting = len(bsps) != len(all_bsps) and (self.tag_scenario_import_decals or self.tag_scenario_import_decorators or self.tag_scenario_import_objects)
                    scenario_name = f"scenario_{scenario.tag_path.ShortName}"
                    scenario_collection = bpy.data.collections.get(scenario_name)
                    if scenario_collection is None:
                        scenario_collection = bpy.data.collections.new(scenario_name)
                        self.scene_collection.children.link(scenario_collection)
                    for bsp, sky_index in zip(bsps, sky_indices):
                        bsp_objects, bvh = self.import_bsp(bsp, scenario_collection, None if self.corinth else scenario.get_info(all_bsps.index(bsp)), do_raycasting, sky_index)
                        imported_objects.extend(bsp_objects)
                        if bvh:
                            structure_collision.append(bvh)
                    
                    if self.tag_import_design and not self.tag_bsp_render_only:
                        designs = scenario.get_design_paths(self.tag_zone_set)
                        for idx, design in enumerate(designs):
                            design_objects = self.import_structure_design(design, scenario_collection)
                            imported_objects.extend(design_objects)
                            
                    if self.tag_sky:
                        sky_name = Path(self.tag_sky).with_suffix("").name
                        print(f"Importing Sky - {sky_name}")
                        self.tag_render = True
                        sky_path = str(Path(utils.get_tags_path(), self.tag_sky))
                        if Path(sky_path).suffix.lower() == '.sky':
                            sky_objects, _ = self.import_skies(
                                [sky_path], None,
                                parent_collection=scenario_collection if merge_sky_to_scenario_collection else None,
                                make_non_export=True)
                        else:
                            sky_objects, _ = self.import_object(
                                [sky_path], None, make_non_export=True,
                                parent_collection=scenario_collection if merge_sky_to_scenario_collection else None)
                        imported_objects.extend(sky_objects)
                            
                        factor = 1
                        if self.scene_nwo.scale == 'max':
                            factor = 1 / 0.03048
                        
                        sky_view = 100_000 * factor
                        
                        for area in bpy.context.screen.areas:
                            if area.type == "VIEW_3D":
                                for space in area.spaces:
                                    if space.type == "VIEW_3D":
                                        if space.clip_end < sky_view:
                                            space.clip_start = 1 * factor
                                            space.clip_end = sky_view
                                            
                    def import_scenario_data(child_scenario, child_collection):
                        if self.tag_scenario_import_objects:
                            game_objects, skeleton_poses = self._scenario_objects_to_blender(
                                child_scenario, child_collection, structure_collision, bsp_indices)
                            if game_objects:
                                print("Importing Game Object Geometry")
                                imported_objects.extend(game_objects)
                                for ob, skeleton_pose in zip(game_objects, skeleton_poses):
                                    has_skeleton_pose = bool(skeleton_pose)

                                    if has_skeleton_pose:
                                        game_object_collection = None
                                    else:
                                        key = ob.nwo.marker_game_instance_tag_name, ob.nwo.marker_game_instance_tag_variant_name
                                        game_object_collection = self.get_cached_game_object_collection(*key)
                                    
                                    if game_object_collection is None:
                                        if ob.nwo.marker_game_instance_tag_name.endswith(".prefab"):
                                            game_object_collection = self.import_prefab(ob)
                                        else:
                                            game_object_collection = self.import_object(ob, None, skeleton_pose)
                                        if game_object_collection is None:
                                            continue
                                        
                                        merged_collection = merge_collection(game_object_collection, has_skeleton_pose) 
                                        imported_objects.extend(game_object_collection.all_objects)
                                        self.scene_collection.children.unlink(game_object_collection)
                                        # bpy.data.collections.link(game_object_collection)
                                        game_object_collection = merged_collection
                                        if not has_skeleton_pose:
                                            game_object_collection = self.cache_game_object_collection(game_object_collection, *key)
                                        
                                    ob.instance_type = 'COLLECTION'
                                    ob.instance_collection = game_object_collection
                                    ob.nwo.marker_instance = True
                                    
                        if self.tag_scenario_import_decals:
                            imported_objects.extend(self._scenario_decals_to_blender(
                                child_scenario,
                                child_collection, structure_collision, bsp_indices))
                            
                        if self.tag_scenario_import_decorators:
                            decorator_objects = self._scenario_decorators_to_blender(
                                child_scenario,
                                child_collection, structure_collision)
                            if decorator_objects:
                                print("Importing Decorator Set Geometry")
                                imported_objects.extend(decorator_objects)
                                for ob in decorator_objects:
                                    is_decorator_cloud = ob.get(DECORATOR_CLOUD_PROP)
                                    if is_decorator_cloud:
                                        tag_path, variant = _decorator_cloud_marker_data(ob)
                                    else:
                                        tag_path = ob.nwo.marker_game_instance_tag_name
                                        variant = ob.nwo.marker_game_instance_tag_variant_name
                                    
                                    key = tag_path, variant
                                    game_object_collection = self.get_cached_game_object_collection(*key)
                                    
                                    if game_object_collection is None:
                                        decorator_source = _decorator_instance_source_empty(ob) if is_decorator_cloud else ob
                                        game_object_collection = self.import_decorator_set(decorator_source, build_blender_materials, always_extract_bitmaps, single_type=variant, lod=self.decorator_lod, only_single_type=True)
                                        merged_collection = merge_collection(game_object_collection, suffix="Decorator")
                                        imported_objects.extend(game_object_collection.all_objects)
                                        self.scene_collection.children.unlink(game_object_collection)
                                        # bpy.data.collections.link(game_object_collection)
                                        game_object_collection = self.cache_game_object_collection(merged_collection, *key)
                                    
                                    if is_decorator_cloud:
                                        add_decorator_cloud_instancer(ob, game_object_collection)
                                        continue
                                        
                                    ob.instance_type = 'COLLECTION'
                                    ob.instance_collection = game_object_collection
                                    ob.nwo.marker_instance = True
                                            
                    import_content = (
                        self.tag_scenario_import_objects
                        or self.tag_scenario_import_decals
                        or self.tag_scenario_import_decorators
                    )
                    if import_content:
                        import_scenario_data(scenario, scenario_collection)
                    
                    if self.corinth:
                        for child_path in scenario.child_scenario_paths():
                            print(f"--- Importing data from child scenario: {child_path.ShortName}")
                            child_coll = bpy.data.collections.new(child_path.ShortName)
                            scenario_collection.children.link(child_coll)
                            if import_content:
                                with ScenarioMetadataTag(path=child_path) as child_scenario:
                                    import_scenario_data(child_scenario, child_coll)

                            if not child_coll.all_objects:
                                bpy.data.collections.remove(child_coll)

                    if self.setup_as_asset:
                        set_asset(Path(file).suffix)
                        self.scene_nwo_export.create_debug_zone_set = False
                        # scenario.zone_sets_to_blender(self.tag_zone_set)
        
        if return_collection:
            return imported_objects, scenario_collection
        else:
            return imported_objects
    
    def import_bsp(self, file, scenario_collection=None, info_path=None, always_get_structure_collision=False, sky_index=-1):
        bsp_name = Path(file).with_suffix("").name
        bvh = None
        utils.print_tag(f"Importing BSP {bsp_name}")
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files:
            bsp_objects = self.import_jms_files(source_files, 'bsp', parent_collection=scenario_collection)
            game_objects = [ob for ob in bsp_objects if ob.type == 'EMPTY'
                            and ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance']
            self._import_bsp_game_objects(bsp_objects, game_objects)
            return bsp_objects, None
        bsp_objects = []
        collection = bpy.data.collections.get(bsp_name)
        if collection is not None and collection.nwo.type != 'region':
            collection = None
        if collection is None:
            collection = bpy.data.collections.new(bsp_name)
            if scenario_collection is None:
                self.scene_collection.children.link(collection)
            else:
                scenario_collection.children.link(collection)
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with ScenarioStructureBspTag(path=mover.tag_path) as bsp:
                bsp_objects, game_objects, bvh = bsp.to_blend_objects(collection, self.tag_bsp_render_only, info_path, self.tag_bsp_import_geometry, self.tag_import_lights, always_get_structure_collision, sky_index, self.tag_bsp_import_havok, self.tag_bsp_skip_structure_merge, merge_render_collision=self.tag_bsp_merge_render_collision)
                
                meshes = {ob.data for ob in bsp_objects if ob.type == 'MESH'}
                self.emissive_meshes.update({me for me in meshes if any(p.type == 'emissive' for p in me.nwo.face_props)})
                
                self._import_bsp_game_objects(bsp_objects, game_objects)
                # seams = bsp.get_seams(bsp_name, seams)
        
        bsp_name = utils.add_region(bsp_name, utils.SetType.SCENARIO)
        collection.name = bsp_name
        collection.nwo.type = "region"
        collection.nwo.region = bsp_name
        
        return bsp_objects, bvh

    def _import_bsp_game_objects(self, bsp_objects, game_objects):
        if not game_objects:
            return
        print("Importing Game Object Geometry")
        for ob in game_objects:
            tag_path = ob.nwo.marker_game_instance_tag_name
            if not tag_path:
                continue
            key = tag_path, ob.nwo.marker_game_instance_tag_variant_name
            game_object_collection = self.get_cached_game_object_collection(*key)
            if game_object_collection is None:
                suffix = "Marker"
                if tag_path.endswith(".prefab"):
                    game_object_collection = self.import_prefab(ob)
                    suffix = "Prefab"
                else:
                    game_object_collection = self.import_object(ob, None)
                if game_object_collection is None:
                    continue
                merged_collection = merge_collection(game_object_collection, suffix=suffix)
                bsp_objects.extend(game_object_collection.all_objects)
                self.scene_collection.children.unlink(game_object_collection)
                game_object_collection = self.cache_game_object_collection(merged_collection, *key)
            ob.instance_type = 'COLLECTION'
            ob.instance_collection = game_object_collection
            ob.nwo.marker_instance = True
    
    def import_scenario_structure_lighting_info(self, file, parent_collection=None, cinematic_cameras=[]):
        info_name = Path(file).with_suffix("").name
        print(f"\nImporting Structure Structure Lighting Info {info_name}")
        info_objects = []
        coll_name = f"{info_name}_lighting_info"
        collection = bpy.data.collections.new(coll_name)
        if parent_collection is None:
            self.scene_collection.children.link(collection)
        else:
            collection.children.link(parent_collection)
            
        camera_lights = None

        with utils.TagImportMover(self.tags_dir, file) as mover:
            with ScenarioStructureLightingInfoTag(path=mover.tag_path) as info:
                info_objects = info.to_blender(collection, cinematic_cameras)
                camera_lights = info.camera_lights
        
        return info_objects, collection, camera_lights
    
    def import_structure_design(self, file, scenario_collection=None):
        design_name = Path(file).with_suffix("").name
        print(f"\nImporting Structure Design {design_name}")
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files:
            return self.import_jms_files(source_files, 'bsp')
        design_objects = []
        collection = bpy.data.collections.get(design_name)
        if collection is None:
            collection = bpy.data.collections.new(design_name)
            if scenario_collection is None:
                self.scene_collection.children.link(collection)
            else:
                scenario_collection.children.link(collection)
        collection.hide_render = True
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with StructureDesignTag(path=mover.tag_path) as design:
                design_objects = design.to_blender(collection)
        
        design_name = utils.add_region(design_name, utils.SetType.SCENARIO)
        collection.name = design_name
        collection.nwo.type = "region"
        collection.nwo.region = design_name
        
        return design_objects
    
    def import_prefab(self, file, bsp_collection=None):
        imported_objects = []
        is_game_object = isinstance(file, bpy.types.Object)
        
        if is_game_object:
            game_object = file
            file = str(Path(utils.get_tags_path(), game_object.nwo.marker_game_instance_tag_name))
            
        prefab_name = Path(file).with_suffix("").name
        print(f"Importing Prefab {prefab_name}")
        
        collection = bpy.data.collections.new(prefab_name)
        if bsp_collection is None:
            self.scene_collection.children.link(collection)
        else:
            bsp_collection.children.link(collection)
            
        with PrefabTag(path=file) as prefab:
            bsp_ref = prefab.bsp_path()
            if bsp_ref is None:
                return

        source_files = [
            path for path in self.import_info_sources_for_tag(bsp_ref.Filename)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files:
            objects = self.import_jms_files(source_files, 'bsp')
            bpy.data.collections.remove(collection)
            if is_game_object:
                return objects[0].users_collection[0] if objects else None
            return objects
            
        with ScenarioStructureBspTag(path=bsp_ref) as bsp:
            bsp_objects, _, _ = bsp.to_blend_objects(collection, self.tag_bsp_render_only, import_geometry=self.tag_bsp_import_geometry, import_lights=self.tag_import_lights, import_havok=self.tag_bsp_import_havok, skip_structure_merge=self.tag_bsp_skip_structure_merge)
            imported_objects.extend(bsp_objects)
            meshes = {ob.data for ob in bsp_objects if ob.type == 'MESH'}
            self.emissive_meshes.update({me for me in meshes if any(p.type == 'emissive' for p in me.nwo.face_props)})

        if is_game_object:
            return collection
        else:
            if self.setup_as_asset:
                set_asset(Path(file).suffix)
            return imported_objects

    def import_polyart(self, file):
        filename = Path(file).with_suffix("").name
        print(f"Importing Polyart: {filename}")
        main_collection = bpy.data.collections.get("polyart")
        if main_collection is None:
            main_collection = bpy.data.collections.new("polyart")
            self.scene_collection.children.link(main_collection)
            
        collection = bpy.data.collections.new(f"{filename}_polyart")
        collection.nwo.type = "region"
        collection.nwo.region = utils.add_region(filename)
        main_collection.children.link(collection)
        
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with PolyArtTag(path=mover.tag_path) as polyart:
                return polyart.to_blender(collection)
    
    def import_particle_model(self, file):
        filename = Path(file).with_suffix("").name
        print(f"Importing Particle Model: {filename}")
        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files:
            return self.import_jms_files(source_files, 'model')
        particle_model_objects = []
        collection = bpy.data.collections.new(f"{filename}_particle")
        self.scene_collection.children.link(collection)
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with ParticleModelTag(path=mover.tag_path) as particle_model:
                particle_model_objects = particle_model.to_blend_objects(collection, filename)
                
        if self.setup_as_asset:
            set_asset(Path(file).suffix)
            
        return particle_model_objects
    
    def import_decorator_set(self, file, build_materials, extract_bitmaps, single_type=None, lod=0, only_single_type=False):
        print("Importing Decorator Set")
        
        is_game_object = isinstance(file, bpy.types.Object)
        decorator_objects = []
        
        if is_game_object:
            game_object = file
            file = str(Path(utils.get_tags_path(), game_object.nwo.marker_game_instance_tag_name))
            if only_single_type is not None:
                global last_used_decorator_type
                last_used_decorator_type = single_type

        source_files = [
            path for path in self.import_info_sources_for_tag(file)
            if Path(path).suffix.lower() in legacy_model_formats
        ]
        if source_files:
            objects = self.import_jms_files(source_files, 'model')
            if is_game_object:
                return objects[0].users_collection[0] if objects else None
            return objects
            
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name))
        self.scene_collection.children.link(collection)
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with DecoratorSetTag(path=mover.tag_path) as decorator:
                decorator_objects = decorator.to_blender(collection, build_materials, extract_bitmaps, single_type, lod, only_single_type)

        if is_game_object:
            return collection
        else:
            if self.setup_as_asset:
                set_asset(Path(file).suffix)
            
        return decorator_objects
    
    def import_cinematic(self, file, film_aperture: float):
        # Cinematic actors and scenery must use compiled tag geometry throughout.
        self.use_import_info = False
        filename = Path(file).with_suffix("").name
        utils.print_section(f"Importing Cinematic: {filename}")
        with utils.TagImportMover(self.tags_dir, file) as mover:
            with NativeCinematicTag(path=mover.tag_path) as cinematic:
                scene_datas, scenario_path, zone_set = cinematic.to_blender(film_aperture, self.tag_cinematic_import_scenario, specific_scene=self.tag_cinematic_scene)
                
        if self.setup_as_asset:
            set_asset(Path(file).suffix)
        
        return scene_datas, scenario_path, zone_set
        
    # Bitmap Import
    def extract_bitmaps(self, bitmap_files, image_format):
        print("\nExtracting Bitmaps")
        print(
            "-----------------------------------------------------------------------\n"
        )
        extracted_bitmaps = {}
        job = "Progress"
        bitmap_count = len(bitmap_files)
        for idx, fp in enumerate(bitmap_files):
            utils.update_progress(job, idx / bitmap_count)
            # bitmap_name = utils.dot_partition(os.path.basename(fp))
            # if 'lp_array' in bitmap_name or 'global_render_texture' in bitmap_name: continue
            with utils.TagImportMover(self.tags_dir, fp) as mover:
                info = bitmap_to_image(mover.tag_path, True)
                if info.image:
                    extracted_bitmaps[info.image_path] = info.for_normal
        utils.update_progress(job, 1)
        print(f"\nExtracted {len(extracted_bitmaps)} bitmaps")
        
        return extracted_bitmaps
    
    def load_bitmaps(self, image_paths, fake_user):
        print("\nLoading Bitmaps")
        print(
            "-----------------------------------------------------------------------\n"
        )
        images = []
        job = "Progress"
        image_paths_count = len(image_paths)
        for idx, (path, is_non_color) in enumerate(image_paths.items()):
            utils.update_progress(job, idx / image_paths_count)
            if Path(path).exists():
                image = bpy.data.images.load(filepath=path, check_existing=True)
                images.append(image)
                image.use_fake_user = fake_user
                image.nwo.filepath = utils.relative_path(path)
                if is_non_color:
                    image.colorspace_settings.name = 'Non-Color'
                else:
                    image.alpha_mode = 'CHANNEL_PACKED'
            else:
                utils.print_warning(f"Failed to extract bitmap: {path}")
            
        utils.update_progress(job, 1)
        
        return images


# JMS/ASS importer
######################################################################

    def import_wrl_files(self, wrl_files):
        from ..legacy.wrl import import_errors

        rotation = utils.blender_halo_rotation_diff(self.scene_nwo.forward_direction)
        scale = 1 / import_transform.scale_factor(self.scene_nwo)
        for path in wrl_files:
            import_errors(Path(path), self.context.scene, rotation, scale)

    def import_jms_files(self, jms_files, legacy_type, *, tag_armature=None,
                         parent_collection=None, geometry_only=False, allowed_region_permutations=(), shader_paths=None):
        """Import JMS and ASS natively, with conversion inside each adapter."""
        from ..legacy.jms_importer import import_jms
        from ..legacy.ass_importer import import_ass
        objects = []
        for path in reversed(jms_files):
            reader = import_ass if Path(path).suffix.lower() == '.ass' else import_jms
            if tag_armature is not None:
                objects.extend(reader(self, path, legacy_type,
                                      tag_armature=tag_armature,
                                      parent_collection=parent_collection,
                                      geometry_only=geometry_only,
                                      allowed_region_permutations=allowed_region_permutations, shader_paths=shader_paths))
            else:
                objects.extend(reader(self, path, legacy_type, parent_collection=parent_collection,
                                      allowed_region_permutations=allowed_region_permutations, shader_paths=shader_paths))
        return objects


    def set_poop_policies(self, ob):
        for char in ob.name[1:]:
            match char:
                case '+':
                    ob.nwo.poop_pathfinding = 'static'
                case '-':
                    ob.nwo.poop_pathfinding = 'none'
                case '?':
                    ob.nwo.poop_lighting = 'per_vertex'
                case '!':
                    ob.nwo.poop_lighting = 'per_pixel'
                case '>':
                    ob.nwo.poop_lighting = 'single_probe'
                case '*':
                    ob.nwo.poop_render_only = True
                case '&':
                    ob.nwo.poop_chops_portals = True
                case '^':
                    ob.nwo.poop_does_not_block_aoe = True
                case '<':
                    ob.nwo.poop_excluded_from_lightprobe = True
                case '|':
                    ob.nwo.poop_decal_spacing = True
                case _:
                    return


    def mesh_and_material(self, mesh_type, is_model):
        material = ""
        match mesh_type:
            case "collision":
                if is_model:
                    mesh_type = "_connected_geometry_mesh_type_collision"
                    material = "Collision"
                else:
                    mesh_type = "_connected_geometry_mesh_type_structure"
            case "physics":
                mesh_type = "_connected_geometry_mesh_type_physics"
                material = "Physics"
            case "default":
                if is_model:
                    mesh_type = "_connected_geometry_mesh_type_default"
                else:
                    mesh_type = "_connected_geometry_mesh_type_structure"
            case "io":
                mesh_type = "_connected_geometry_mesh_type_object_instance"
            case "instance":
                mesh_type = "_connected_geometry_mesh_type_default"
            case "seam":
                mesh_type = "_connected_geometry_mesh_type_seam"
                material = "Seam"
            case "portal":
                mesh_type = "_connected_geometry_mesh_type_portal"
                material = "Portal"
            case "water_surface":
                mesh_type = "_connected_geometry_mesh_type_water_surface"
            case "rain_sheet":
                mesh_type = "_connected_geometry_mesh_type_poop_vertical_rain_sheet"
                material = "RainSheet"
            case "fog":
                mesh_type = "_connected_geometry_mesh_type_planar_fog_volume"
                material = "Fog"
            case "lightmap_region":
                mesh_type = "_connected_geometry_mesh_type_lightmap_region"
                material = "LightmapRegion"
            case "soft_ceiling":
                mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                material = "SoftCeiling"
            case "soft_kill":
                mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                material = "SoftKill"
            case "slip_surface":
                mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                material = "SlipSurface"
            case "water_physics":
                mesh_type = "_connected_geometry_mesh_type_water_surface"
                material = "WaterVolume"
            case "cookie_cutter":
                mesh_type = "_connected_geometry_mesh_type_cookie_cutter"
                material = "CookieCutter"
            case "rain_blocker":
                mesh_type = "_connected_geometry_mesh_type_poop_rain_blocker"
                material = "RainBlocker"
            case "weather_polyhedron":
                mesh_type = "_connected_geometry_mesh_type_weather_polyhedron"
                material = "+weather"
            case "decorator":
                mesh_type = "_connected_geometry_mesh_type_decorator"
                
        return mesh_type, material
            

# Legacy Animation importer
######################################################################
    def import_jma_files(self, jma_files, arm):
        """Imports all legacy animation files supplied"""
        if not jma_files:
            return []
        self.actions = []
        self.objects = []
        if jma_files:
            muted_armature_deforms = utils.mute_armature_mods()
            print("Importing Animations")
            print(
                "-----------------------------------------------------------------------\n"
            )
            try:
                for bone in arm.pose.bones:
                    bone.matrix_basis = IDENTITY_MATRIX
                self.context.view_layer.update()
                for path in jma_files:
                    self.import_legacy_animation(path, arm)
            finally:
                utils.unmute_armature_mods(muted_armature_deforms)
                
            if self.scene_nwo.asset_type in {'model', 'animation'}:
                self.scene_nwo.active_animation_index = len(self.scene_nwo.animations) - 1

            self.register_control_rig_actions(arm, self.actions)
            return self.actions
            
    def import_legacy_animation(self, path, arm):
        path = Path(path)
        # existing_animations = bpy.data.actions[:]
        extension = path.suffix.strip('.')
        anim_name = path.with_suffix("").name
        if self.convert_animations:
            anim_name = convert_animation_name_for_project(
                anim_name, 'halo1', self.target_game)
        print(f"--- {anim_name}")
        jma = JMA()
        jma.from_file(path)
        action = jma.to_armature_action(arm)
        if action is not None:
            action.name = anim_name
            self.actions.append(action)
            animation = self.scene_nwo.animations.add()
            animation.name = anim_name
            # action.use_fake_user = True
            action.use_frame_range = True
            animation.frame_start = 1
            animation.frame_end = jma.frame_count
            track = animation.action_tracks.add()
            track.object = arm
            track.action = action
            match extension.lower():
                case 'jmm':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'none'
                case 'jma':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'xy'
                case 'jmt':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'xyyaw'
                case 'jmz':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'xyzyaw'
                case 'jmv':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'full'
                case 'jmw':
                    animation.animation_type = 'world'
                case 'jmo':
                    animation.animation_type = 'overlay'
                    # animation.animation_is_pose = any(hint in anim_name.lower() for hint in pose_hints)
                    # if animation.animation_is_pose:
                    #     pass
                case 'jmr':
                    animation.animation_type = 'replacement'
                case 'jmrx':
                    animation.animation_type = 'replacement'
                    animation.animation_space = 'local'
                        
class NWO_OT_ImportFromDrop(bpy.types.Operator):
    bl_idname = "nwo.import_from_drop"
    bl_label = "Foundry Importer"
    bl_description = "Imports from drag n drop"
    bl_options = {'REGISTER', 'UNDO'}
    
    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'SKIP_SAVE', 'HIDDEN'})
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    import_template: bpy.props.EnumProperty(
        name="Template",
        description="Preset for common import goals",
        items=IMPORT_TEMPLATE_ITEMS,
        options={'SKIP_SAVE'},
        default=IMPORT_TEMPLATE_DEFAULT,
        update=import_template_update,
    )
    # filename: bpy.props.StringProperty(options={'SKIP_SAVE'})
    # filter_glob: bpy.props.StringProperty(
    #     default=".jms;.ass;.bitmap;.model;.render_model;.scenario;.scenario_structure_bsp;.jmm;.jma;.jmt;.jmz;.jmv;.jmw;.jmo;.jmr;.jmrx;.camera_track;.particle_model;.scenery;.biped;.model_animation_graph",
    #     options={"HIDDEN"},
    # )
    
    # find_shader_paths: bpy.props.BoolProperty(
    #     name="Find Shader Paths",
    #     description="Searches the tags folder after import and tries to find shader/material tags which match the name of importer materials",
    #     default=True,
    # )
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )

    build_materials_for_project: bpy.props.BoolProperty(
        name="Build Materials for Current Project",
        description="Convert imported materials to the current project's game nodes and convert packed bitmap channels where possible. Unsupported effects are approximated. Halo 2 is supported as a source only",
        default=False,
    )
    
    import_images_to_blender: bpy.props.BoolProperty(
        name="Import to Blend",
        description="Imports images into the blender after extracting bitmaps from the game",
        default=True,
    )
    images_fake_user: bpy.props.BoolProperty(
        name="Set Fake User",
        description="Sets the fake user property on imported images",
        default=True,
    )
    extracted_bitmap_format: bpy.props.EnumProperty(
        name="Image Format",
        description="Sets format to save the extracted bitmap as",
        items=[
            ("tiff", "TIFF", ""),
            ("png", "PNG", ""),
            ("jped", "JPEG", ""),
            ("bmp", "BMP", ""),
        ]
    )
    
    camera_track_animation_scale: bpy.props.FloatProperty(
        name='Animation Scale',
        default=1,
        min=1,
    )
    
    reuse_armature: bpy.props.BoolProperty(
        name="Reuse Scene Armature",
        description="Will reuse the main blend scene armature for this model instead of importing a new one",
        default=False,
    )
    tag_render: bpy.props.BoolProperty(
        name="Import Render Geometry",
        default=True,
    )
    render_lod: bpy.props.EnumProperty(
        name="LOD",
        description="Level of detail to import from Halo 1 or Halo 2 models",
        items=render_lod_items,
        default=0,
        options={'SKIP_SAVE'},
    )
    tag_markers: bpy.props.BoolProperty(
        name="Import Markers",
        default=True,
    )
    tag_collision: bpy.props.BoolProperty(
        name="Import Collision",
        default=False,
    )
    tag_physics: bpy.props.BoolProperty(
        name="Import Physics",
        default=False,
    )
    tag_animation: bpy.props.BoolProperty(
        name="Import Animation Graph",
        description="Imports animations, renames, and animation events. This importer is work in progress and additional functionaility is still to be added",
        options={'SKIP_SAVE'},
        default=False,
    )
    
    def items_tag_variant(self, context):
        var_match = False
        if utils.get_scene_props().asset_type in {"cinematic", "scenario"}:
            items = []
        else:
            items = [("all_variants", "All Variants", "Includes the full model geometry")]
        for var in variant_items:
            if var == last_used_variant:
                var_match = True
            else:
                items.append((var, var, ""))
                
        if var_match:
            items.insert(0, (last_used_variant, last_used_variant, ""))
            
        if not items:
            return [("all_variants", "All Variants", "Includes the full model geometry")]
            
        return items

    def items_tag_permutation(self, context):
        return [("all_permutations", "All Permutations", "Import every model permutation"), *(
            (permutation, permutation, "") for permutation in permutation_items
        )]
    
    def items_decorator_type(self, context):
        dec_match = False
        if utils.get_scene_props().asset_type in {"cinematic", "scenario"}:
            items = []
        else:
            items = [("all_types", "All Types", "Includes the full model geometry")]
        for dec in decorator_type_items:
            if dec.decorator_type_name == last_used_decorator_type:
                dec_match = True
            else:
                items.append((dec.decorator_type_name, dec.decorator_type_name, ""))
                
        if dec_match:
            items.insert(0, (last_used_decorator_type, last_used_decorator_type, ""))
            
        if not items:
            return [("all_types", "All Types", "Includes the full model geometry")]
            
        return items
    
    def items_sky(self, context):
        items = [("none", "None", "")]
        for sky in sky_items:
            items.append((sky, Path(sky).with_suffix("").name, ""))
            
        return items
    
    def items_cinematic_scene(self, context):
        items = [("all", "All", "")]
        for cin_scene in cinematic_scene_items:
            items.append((cin_scene, Path(cin_scene).with_suffix("").name, ""))
            
        return items
        
    
    tag_variant: bpy.props.EnumProperty(
        name="Variant",
        options={'SKIP_SAVE'},
        description="Model variant to import, or all",
        items=items_tag_variant,
    )

    tag_permutation: bpy.props.EnumProperty(
        name="Permutation",
        options={'SKIP_SAVE'},
        description="Halo 1 model permutation to import, or all",
        items=items_tag_permutation,
    )
    
    setup_as_asset: bpy.props.BoolProperty(
        name="Setup as Asset",
        default=False,
        description="Updates the scene asset settings so that this object can be immediately reimported into the game"
    )

    force_no_setup_as_asset: bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    def items_tag_bsp(self, context):
        return bsp_items or [("all_bsps", "All BSPs", "Import all scenario BSPs")]

    tag_bsp: bpy.props.EnumProperty(
        name="BSP",
        options={'SKIP_SAVE'},
        description="Select the Halo 1 or Halo 2 BSP to import",
        items=items_tag_bsp,
    )

    def items_tag_zone_set(self, context):
        items = [("all_zone_sets", "All Zone Sets", "All scenario bsps will be imported")]
        for zs, bsps in zone_set_items.items():
            bsps_str = "\n".join(bsps)
            items.append((zs, zs, f"Includes BSPs:\n{bsps_str}"))
            
        return items
    
    tag_zone_set: bpy.props.EnumProperty(
        name="Zone Set",
        options={'SKIP_SAVE'},
        description="Limits the bsps to import to those present in the specified zoneset",
        items=items_tag_zone_set,
    )
    
    tag_bsp_render_only: bpy.props.BoolProperty(
        name="Render Geometry Only",
        description="Skips importing bsp data like collision and portals. Use this if you aren't importing the BSP back into the game",
    )
    
    tag_bsp_import_havok: bpy.props.BoolProperty(
        name="Import Havok Collision (WIP)",
        description="Imports serialized Havok collision from scenario_structure_bsp tags as standalone collision meshes. Experimental.",
        default=False,
    )

    tag_bsp_import_geometry: bpy.props.BoolProperty(
        name="Import BSP Geometry",
        description="Imports the all geometry data within bsp tags",
        default=True,
    )

    tag_bsp_skip_structure_merge: bpy.props.BoolProperty(
        name="Skip Structure Merge",
        description="Keeps imported BSP clusters as separate objects instead of joining them into one structure mesh",
        default=False,
    )

    tag_bsp_merge_render_collision: bpy.props.BoolProperty(
        name="Merge Render and Collision",
        description="Reconstructs shared render and collision surfaces for Halo 1 BSPs. Disable to import the original render and collision meshes separately",
        default=True,
    )
    
    tag_import_design: bpy.props.BoolProperty(
        name="Import Structure Design",
        description="Imports geometry from scenario structure design tags. Ignored if render only is set",
        default=True,
    )
    
    tag_sky: bpy.props.EnumProperty(
        name="Sky",
        description="Select the sky to import with this scenario",
        items=items_sky
    )
    
    tag_cinematic_import_scenario: bpy.props.BoolProperty(
        name="Import Scenario",
        default=True,
    )
    
    tag_cinematic_import_actors: bpy.props.BoolProperty(
        name="Import Actors",
        default=True,
    )
    
    tag_cinematic_scene: bpy.props.EnumProperty(
        name="Scene",
        options={'SKIP_SAVE'},
        description="Select a specific cinematic scene to import, or all (default)",
        items=items_cinematic_scene,
    )
    
    tag_scenario_import_objects: bpy.props.BoolProperty(
        name="Import Objects",
        description="Imports scenario objects. Added to an exclude collection by default",
        default=False,
    )
    
    tag_scenario_import_decals: bpy.props.BoolProperty(
        name="Import Decals",
        description="Imports scenario decals. Added to an exclude collection by default",
        default=False,
    )
    
    tag_scenario_import_decorators: bpy.props.BoolProperty(
        name="Import Decorators",
        description="Imports scenario decorators. These won't export by default unless you enable the option in the asset editor panel to control decorators from Blender",
        default=False,
    )
    
    decorator_single_lod: bpy.props.BoolProperty(
        name="Only single LOD",
        description="Import only a single level of detail for this decorator"
    )
    
    decorator_lod: bpy.props.EnumProperty(
        name="Decorator LOD",
        description="Level of detail for imported decorators",
        items=[
            ("1", "Highest", ""),
            ("2", "Medium", ""),
            ("3", "Low", ""),
            ("4", "Lowest", ""),
        ]
    )
    
    decorator_type: bpy.props.EnumProperty(
        name="Decorator Type",
        options={'SKIP_SAVE'},
        description="Decorator Type to import, or all",
        items=items_decorator_type,
    )
    
    tag_import_lights: bpy.props.BoolProperty(
        name="Import Lights",
        description="Imports the all lights found in scenario_structure_lighting_info tags",
        default=True,
    )
    
    tag_animation_filter: bpy.props.StringProperty(
        name="Animation Filter",
        description="Filter for the animations to import. Animation names that do not contain the specified string will be skipped"
    )
    
    tag_state: bpy.props.EnumProperty(
        name="Model State",
        description="The damage state to import. Only valid when a variant is set",
        default=1,
        items=state_items,
    )
    
    tag_model_override_type: bpy.props.EnumProperty(
        name="Model Override",
        description="The render model type to read from the model override block",
        items=[
            ('none', "None", ""),
            ('campaign', "Campaign", ""),
            ('multiplayer', "Multiplayer", ""),
            ('firefight', "Firefight", ""),
            ('mainmenu', "Main Menu", ""),
        ]
    )
    
    tag_import_attachments: bpy.props.BoolProperty(
        name="Attachments",
        description="Import object tag attachments. Currently supports lights and cheap lights"
    )
    
    graph_import_animations: bpy.props.BoolProperty(
        name="Import Animations",
        default=True,
        description="Imports animations from the graph"
    )
    graph_bake_to_control_rig: bpy.props.BoolProperty(
        name="Bake to Control Rig",
        default=True,
        description="Bakes imported animations to an existing or newly built control rig",
    )
    graph_scale_animations_to_skeleton: bpy.props.BoolProperty(
        name="Root Translation / Scale Only",
        default=False,
        description="Applies translation and scale to root/pedestal bones and their direct children; tagged animations always use this, and the option applies it globally with idle-based foot height correction"
    )
    graph_import_pca_data: bpy.props.BoolProperty(
        name="Import PCA Data",
        description="Imports animations with their PCA (face animation) data",
        default=True,
    )
    graph_generate_renames: bpy.props.BoolProperty(
        name="Generate Renames and Copies",
        default=True,
        description="Reads graph paths to add complete hierarchy copies and individual animation renames"
    )
    graph_import_events: bpy.props.BoolProperty(
        name="Import Animation Events",
        default=True,
        description="Imports frame events from the graph tag and frame event list"
    )
    graph_import_ik_chains: bpy.props.BoolProperty(
        name="Import IK Chains",
        default=True,
        description="Sets up the IK chains graph tag block in blender"
    )
    
    import_fp_arms: bpy.props.EnumProperty(
        name="FP Arms",
        description="Imports the First person arms along with the weapon and joins the skeletons",
        items=fp_arms_items,
        default=0,
    )
    
    legacy_type: bpy.props.EnumProperty(
        name="JMS/ASS Type",
        description="Whether the importer should try to import a JMS/ASS file as a model, or bsp. Auto will determine this based on current asset type and contents of the JMS/ASS file",
        items=[
            ("auto", "Auto", ""),
            ("model", "Model", ""),
            ("bsp", "BSP", ""),
        ]
    )
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not",
        options=set(),
    )
    
    import_variant_children: bpy.props.BoolProperty(
        name="Import Child Objects",
        description="Imports the child objects associated with this model variant",
        default=True,
        options={'SKIP_SAVE'},
    )
    
    import_biped_weapon: bpy.props.BoolProperty(
        name="Import Biped Weapons",
        description="Imports all the biped's weapons if it has any",
    )

    biped_weapon_source: bpy.props.EnumProperty(
        name="Biped Weapon",
        description="Weapon source to import when importing biped weapons",
        items=biped_weapon_source_items,
    )
    
    legacy_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    place_at_mouse : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    convert_to_instance: bpy.props.BoolProperty(
        name="Convert to Instance Geometry",
        description="Converts a model to instanced geometry",
    )
    
    import_as_instanced_collection: bpy.props.BoolProperty(
        name="Import as Game Marker",
        description="Imports the object as a game marker with an instanced collection",
        default=True
    )
    
    from_vert_normals: bpy.props.BoolProperty(
        name="Store Model Vertex Normals",
        description="Stores a models vertex normals so that it can be reimported in game with the exact same vertex order. This is done automatically for PCA meshes, this option just applies the same to everything. Any edits to meshes with this setting will probably break normals on export"
    )
    
    mouse_x : bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    mouse_y : bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    generate_frames: bpy.props.BoolProperty(
        name="Generate Missing Frames",
        description="Generates frames where possible for tag imported animations. This is needed because base and replacement animations are missing a final frame which would have been present in their source file",
    )
    
    build_control_rig: bpy.props.BoolProperty(
        name="Build Control Rig",
        description="Builds an FK and IK control rig for imported models",
        default=False,
    )

    convert_animations: bpy.props.BoolProperty(
        name="Convert Animations for Project",
        description="Convert animation names, turn poses, aim/look overlays, and Halo 4 / H2AMP locomote composites to the current project game",
        default=True,
    )

    use_import_info: bpy.props.BoolProperty(
        name="Use Import Info",
        description="Imports embedded JMS, ASS, and JMA source data instead of compiled tag data when available. GR2 source data is currently ignored",
        default=True,
    )
    
    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()
    
    def execute(self, context):
        keywords = self.as_keywords()
        keywords.pop("import_template", None)
        force_no_setup_as_asset = keywords.pop("force_no_setup_as_asset", False)
        if force_no_setup_as_asset:
            keywords["setup_as_asset"] = False
        keywords['files'] = [{'name': f.name} for f in self.files]
        ensure_import_operator_enum_defaults(keywords)
        try:
            bpy.ops.nwo.foundry_import(**keywords)
        finally:
            utils.clear_external_project()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        utils.set_import_context_from_filepath(Path(self.filepath))
        try:
            return self._invoke_with_source_project(context, event)
        except Exception:
            utils.clear_external_project()
            raise

    def _invoke_with_source_project(self, context, event):
        scene_nwo = utils.get_scene_props()
        global checked_asset_once
        if not self.force_no_setup_as_asset and not self.setup_as_asset and not utils.valid_nwo_asset(context) and not checked_asset_once:
            checked_asset_once = True
            self.setup_as_asset = True
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        suffix = Path(self.filepath).suffix.lower()
        self.place_at_mouse = scene_nwo.asset_type == 'scenario' and (suffix == '.prefab' or suffix == '.decorator_set' or suffix in OBJECT_TAG_EXTS)
        self.has_variants = False
        self.has_permutations = False
        self.has_zone_sets = False
        self.import_type = Path(self.filepath).suffix[1:].lower()
        set_default_import_template(self)
        if self.force_no_setup_as_asset:
            self.setup_as_asset = False
        if scene_nwo.asset_type == "cinematic":
            self.tag_bsp_render_only = True
            self.tag_collision = False
            self.tag_physics = False
            # self.tag_animation = False
            self.tag_state = "default"
            
        if self.import_type in {"jms", "ass", "jmm", "jma", "jmt", "jmz", "jmv", "jmw", "jmo", "jmr", "jmrx"}:
            self.legacy_okay = True

        if self.import_type in {"camera_track", "jms", "ass", "model", "render_model", "gbxmodel", "collision_model", "model_collision_geometry", "physics_model", "physics", "sky", "scenario", "scenario_structure_bsp", "model_animation_graph", "model_animations", "biped", "crate", "creature", "device_control", "device_dispenser", "effect_scenery", "equipment", "giant", "device_machine", "projectile", "scenery", "spawner", "sound_scenery", "device_terminal", "vehicle", "weapon", "prefab", "decorator_set", "jmm", "jma", "jmt", "jmz", "jmv", "jmw", "jmo", "jmr", "jmrx", "cinematic"}:
            if self.import_type == "scenario":
                global zone_set_items
                global bsp_items
                global sky_items
                with ScenarioMetadataTag(path=self.filepath) as scenario:
                    bsp_items = [("all_bsps", "All BSPs", "Import all scenario BSPs")]
                    if scenario.game in {'halo1', 'halo2'}:
                        bsp_items.extend((Path(path).stem, Path(path).stem, path)
                                         for path in scenario.get_bsp_paths())
                        self.tag_bsp = "all_bsps"
                    zone_set_items = scenario.get_zone_sets_dict()
                    if zone_set_items:
                        self.has_zone_sets = True
                    sky_items = scenario.get_sky_paths()
                            
            elif self.import_type == 'cinematic':
                global cinematic_scene_items
                with NativeCinematicTag(path=self.filepath) as cinematic:
                    cinematic_scene_items = []
                    scenario_path, _ = cinematic.scenario_reference()
                    for cin_scene_path, _ in cinematic.scene_references():
                        if cinematic.path_exists(cin_scene_path):
                            cinematic_scene_items.append(cin_scene_path.RelativePathWithExtension)
                    
                    if cinematic.path_exists(scenario_path):
                        with TagDocument(scenario_path.Filename, tags_root=cinematic.tags_root,
                                         game=cinematic.game, must_exist=True) as scenario:
                            sky_items = []
                            for element in scenario.block(scenario.tag.root(), 'skies'):
                                sky = scenario.reference(element, 'sky')
                                if sky and Path(sky.Filename).exists():
                                    sky_items.append(sky.RelativePathWithExtension)
                        
            elif self.import_type == 'decorator_set':
                global decorator_type_items
                with DecoratorSetTag(path=self.filepath) as decorator_Set:
                    decorator_type_items = decorator_Set.get_decorator_types()
                        
            elif self.import_type in {"model", "biped", "crate", "creature", "device_control", "device_dispenser", "effect_scenery", "equipment", "giant", "device_machine", "projectile", "scenery", "spawner", "sound_scenery", "device_terminal", "vehicle", "weapon"}:
                global variant_items
                global permutation_items
                variant_items = []
                permutation_items = []
                if self.import_type == "model":
                    with ModelTag(path=self.filepath) as model:
                        if model.game == 'halo1':
                            permutation_items = model.get_model_permutations()
                            self.has_permutations = True
                            self.tag_permutation = "all_permutations"
                        else:
                            variant_items = model.get_model_variants()
                else:
                    with ObjectTag(path=self.filepath) as object_tag:
                        if object_tag.game == 'halo1':
                            permutation_items = object_tag.get_model_permutations()
                            self.has_permutations = True
                            self.tag_permutation = "all_permutations"
                        else:
                            variant_items = object_tag.get_variants()
                if variant_items:
                    self.has_variants = True
            if self.place_at_mouse:
                return self.execute(context)
            else:
                return context.window_manager.invoke_props_dialog(self, width=500)
        else:
            return self.execute(context)

    def cancel(self, context):
        utils.clear_external_project()
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.label(text=f"Importing: {Path(self.filepath).name}")
        corinth = utils.is_corinth(context)
        if self.import_type not in {"cinematic", "jms", "ass", "jmm", "jma", "jmt", "jmz", "jmv", "jmw", "jmo", "jmr", "jmrx"} and utils.get_scene_props().asset_type != 'cinematic':
            layout.prop(self, "use_import_info")
        match self.import_type:
            case "model" | "biped" | "crate" | "creature" | "device_control" | "device_dispenser" | "effect_scenery" | "equipment" | "giant" | "device_machine" | "projectile" | "scenery" | "spawner" | "sound_scenery" | "device_terminal" | "vehicle" | "weapon":
                if self.place_at_mouse:
                    if self.has_variants or self.has_permutations:
                        draw_model_source_options(
                            self, layout, corinth, self.has_variants, self.has_variants,
                            show_permutation=self.has_permutations)
                    layout.prop(self, "convert_to_instance")
                else:
                    draw_model_tag_import_sections(
                        self,
                        layout,
                        corinth,
                        show_template=True,
                        show_source=self.has_variants or self.has_permutations,
                        has_variants=self.has_variants,
                        has_permutations=self.has_permutations,
                        show_fp_arms=self.import_type == "weapon",
                        show_biped_weapon=self.import_type == "biped",
                    )
            case 'decorator_set':
                layout.prop(self, "decorator_type")
                if self.place_at_mouse:
                    layout.prop(self, "decorator_lod")
                else:
                    layout.prop(self, "decorator_single_lod")
                    if self.decorator_single_lod:
                        layout.prop(self, "decorator_lod")
                    layout.prop(self, "setup_as_asset")
                layout.prop(self, "build_blender_materials")
                draw_material_project_option(self, layout)
                layout.prop(self, "always_extract_bitmaps")
            case "render_model" | "gbxmodel" | "sky":
                draw_import_template(self, layout)
                layout.prop(self, "build_control_rig")
                draw_halo2_lod(self, layout)
                if self.has_variants:
                    layout.prop(self, "tag_variant")
                layout.prop(self, "tag_markers")
                if self.import_type == 'sky':
                    layout.prop(self, "tag_animation")
                    layout.prop(self, "setup_as_asset")
                # layout.prop(self, "from_vert_normals")
                layout.prop(self, "build_blender_materials")
                draw_material_project_option(self, layout)
                layout.prop(self, "always_extract_bitmaps")
            case "collision_model" | "model_collision_geometry" | "physics_model" | "physics":
                layout.label(text="Uses selected armature or a skeleton from this tag folder")
            case "scenario":
                draw_scenario_import_sections(
                    self,
                    layout,
                    corinth,
                    show_template=True,
                    show_zone_set=True,
                    show_sky=True,
                    show_scenario_content=True,
                    show_setup_as_asset=True,
                )
            case "scenario_structure_bsp" | "prefab":
                draw_scenario_import_sections(
                    self,
                    layout,
                    corinth,
                    show_template=True,
                    show_zone_set=False,
                    show_sky=False,
                    show_scenario_content=False,
                    show_setup_as_asset=True,
                )
            case "model_animation_graph" | "model_animations":
                draw_graph_import_options(self, layout, corinth)
            case "camera_track":
                layout.prop(self, "camera_track_animation_scale")
                layout.prop(self, "setup_as_asset")
            case 'cinematic':
                layout.prop(self, "tag_cinematic_import_scenario")
                layout.prop(self, "tag_cinematic_import_actors")
                if corinth:
                    layout.prop(self, "graph_import_pca_data")
                layout.prop(self, "tag_cinematic_scene")
                layout.prop(self, "build_control_rig")
                layout.prop(self, "tag_import_attachments")
                layout.prop(self, "tag_import_lights")
                layout.prop(self, "tag_sky")
                layout.prop(self, "tag_scenario_import_objects")
                layout.prop(self, "tag_scenario_import_decals")
                layout.prop(self, "tag_scenario_import_decorators")
                layout.prop(self, "setup_as_asset")
                layout.prop(self, "build_blender_materials")
                draw_material_project_option(self, layout)
                layout.prop(self, "always_extract_bitmaps")
            case "ass" | "jms":
                layout.prop(self, "legacy_type", expand=True)
            case "jmm" | "jma" | "jmt" | "jmz" | "jmv" | "jmw" | "jmo" | "jmr" | "jmrx":
                layout.prop(self, "generate_frames")
                layout.prop(self, "convert_animations")
            

class NWO_FH_Import(bpy.types.FileHandler):
    bl_idname = "NWO_FH_Import"
    bl_label = "File handler Foundry Importer"
    bl_import_operator = "nwo.import_from_drop"
    bl_file_extensions = ".wrl;.jms;.ass;.bitmap;.model;.gbxmodel;.render_model;.physics_model;.physics;.sky;.scenario;.scenario_structure_bsp;.scenario_structure_lighting_info;.jmm;.jma;.jmt;.jmz;.jmv;.jmw;.jmo;.jmr;.jmrx;.camera_track;.particle_model;.biped;.crate;.creature;.device_control;.device_dispenser;.effect_scenery;.equipment;.giant;.device_machine;.projectile;.scenery;.spawner;.sound_scenery;.device_terminal;.vehicle;.weapon;.model_animation_graph;.model_animations;.prefab;.structure_design;.polyart_asset;.decorator_set"

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')

class NWO_FH_ImportCollision(bpy.types.FileHandler):
    # Keep the general handler below Blender's 512-byte extension limit.
    bl_idname = "NWO_FH_ImportCollision"
    bl_label = "File handler Foundry Collision Importer"
    bl_import_operator = "nwo.import_from_drop"
    bl_file_extensions = ".collision_model;.model_collision_geometry"

    @classmethod
    def poll_drop(cls, context):
        return NWO_FH_Import.poll_drop(context)

class NWO_FH_ImportCinematic(bpy.types.FileHandler):
    # Blender stores each extension list in a 512-byte buffer, including the
    # terminator. Appending .cinematic to the general handler truncates it.
    bl_idname = "NWO_FH_ImportCinematic"
    bl_label = "File handler Foundry Cinematic Importer"
    bl_import_operator = "nwo.import_from_drop"
    bl_file_extensions = ".cinematic"

    @classmethod
    def poll_drop(cls, context):
        return NWO_FH_Import.poll_drop(context)

class NWO_OT_ImportBitmap(bpy.types.Operator):
    bl_idname = "nwo.import_bitmap"
    bl_label = "Bitmap Importer"
    bl_description = "Imports an image and loads it as the active image in the image editor or as a texture node depending on area context"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filename: bpy.props.StringProperty(options={'SKIP_SAVE'}, subtype='FILE_NAME')
    filter_glob: bpy.props.StringProperty(
        default="*.bitmap",
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        if Path(self.filepath).suffix != '.bitmap':
            return {'CANCELLED'}

        utils.set_import_context_from_filepath(Path(self.filepath))
        try:
            clear_path_cache()
            importer = NWOImporter(context, [self.filepath], ['bitmap'])
            extracted_bitmaps = importer.extract_bitmaps([self.filepath], 'tiff')
            images = importer.load_bitmaps(extracted_bitmaps, False)
            if images:
                if context.area.type == 'IMAGE_EDITOR':
                    context.area.spaces.active.image = images[0]
                elif context.area.type == 'NODE_EDITOR' and context.material:
                    tree = context.material.node_tree
                    node = tree.nodes.new("ShaderNodeTexImage")
                    node.image = images[0]
                    for n in tree.nodes: n.select = False
                    node.select = True
                    node.location = context.region.view2d.region_to_view(self.mouse_x, self.mouse_y)
        finally:
            utils.clear_external_project()
                    
        return {"FINISHED"}
    
    def invoke(self, context, event):
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        return self.execute(context)
    
class NWO_FH_ImportBitmapAsImage(bpy.types.FileHandler):
    bl_idname = "NWO_FH_ImportBitmapAsImage"
    bl_label = "File handler Foundry Bitmap Importer"
    bl_import_operator = "nwo.import_bitmap"
    bl_file_extensions = ".bitmap"
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'IMAGE_EDITOR')

    
class NWO_FH_ImportBitmapAsNode(bpy.types.FileHandler):
    bl_idname = "NWO_FH_ImportBitmapAsNode"
    bl_label = "File handler Foundry Bitmap Importer"
    bl_import_operator = "nwo.import_bitmap"
    bl_file_extensions = ".bitmap"
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'NODE_EDITOR')
    
class NWO_OT_ImportShader(bpy.types.Operator):
    bl_idname = "nwo.import_shader"
    bl_label = "Shader Importer"
    bl_description = "Imports a shader/material tag"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filename: bpy.props.StringProperty(options={'SKIP_SAVE'}, subtype='FILE_NAME')
    filter_glob: bpy.props.StringProperty(
        default=';'.join('*' + extension for extension in IMPORT_SHADER_EXTENSIONS),
        options={"HIDDEN"},
    )

    build_materials_for_project: bpy.props.BoolProperty(
        name="Build Materials for Current Project",
        description="Use the current project's game nodes and convert packed bitmap channels where possible",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        if Path(self.filepath).suffix.lower() not in IMPORT_SHADER_EXTENSIONS:
            return {'CANCELLED'}
        
        mat = bpy.data.materials.new(str(Path(self.filepath).with_suffix("").name))
        project = utils.get_project(use_external=False)
        utils.set_import_context_from_filepath(Path(self.filepath))
        try:
            shader_path = utils.relative_path(self.filepath)
            mat.name = utils.imported_material_name(mat.name)
            mat.nwo['shader_path'] = shader_path
            tag_to_nodes(utils.is_corinth(context), mat, shader_path,
                         target_game=project.game if self.build_materials_for_project and project else None)
        finally:
            utils.clear_external_project()
        
        if not hasattr(self, "area"):
            self.area = None
            self.mouse_x = 0
            self.mouse_y = 0
        
        match self.area:
            case 'VIEW_3D':
                hit, face_location, face_normal, face_index, face_object, face_matrix = utils.ray_cast_mouse(context, (self.mouse_x, self.mouse_y))
                if hit and face_object.type in VALID_MESHES:
                    mesh = face_object.data
                    if mesh.materials and face_object.type == 'MESH':
                        mat_index = mesh.polygons[face_index].material_index
                        mesh.materials[mat_index] = mat
                    else:
                        mesh.materials.append(mat)
            case 'PROPERTIES' | 'NODE_EDITOR':
                if context.object and context.object.type in VALID_MESHES:
                    mesh = context.object.data
                    if context.material:
                        mat_index = mesh.materials.find(context.material.name)
                        mesh.materials[mat_index] = mat
                    else:
                        mesh.materials.append(mat)
                        
        
        self.report({'INFO'}, f"Imported {mat.name}")
                    
        return {"FINISHED"}
    
    def invoke(self, context, event):
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        self.area = context.area.type
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout.row()
        project = utils.get_project(use_external=False)
        row.enabled = project is not None and project.game != 'halo2'
        row.prop(self, 'build_materials_for_project')
    
class NWO_FH_ImportShaderAsMaterial(bpy.types.FileHandler):
    bl_idname = "NWO_FH_ImportShaderAsMaterial"
    bl_label = "File handler Foundry Bitmap Importer"
    bl_import_operator = "nwo.import_shader"
    bl_file_extensions = ';'.join(IMPORT_SHADER_EXTENSIONS)
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type in {'NODE_EDITOR', 'VIEW_3D', 'PROPERTIES'})
    
def merge_collection(collection: bpy.types.Collection, suffix="Marker"):
    """Reduces a collection down to just the meshes. Clearing markers and armatures"""
    # utils.deselect_all_objects()
    # any_parents = False
    # to_remove_objects = []
    # to_remove_data = []
    allowed_types = {'MESH', 'LIGHT'}
    merged_collection = bpy.data.collections.new(f"{collection.name} {suffix}")
    # if keep_armature:
    #     allowed_types.add('ARMATURE')
    for ob in collection.all_objects:
        if ob.type in allowed_types:
            merged_collection.objects.link(ob)
            # has_parent = ob.parent is not None
            # if has_parent:
            #     any_parents = True
            #     ob.select_set(True)
            #     bpy.context.view_layer.objects.active = ob
        # else:
        #     to_remove_objects.append(ob)
        #     if ob.data is not None:
        #         to_remove_data.append(ob.data)
    
    # if any_parents:
    #     bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    # if to_remove_objects:
    #     bpy.data.batch_remove(to_remove_objects)
    #     if to_remove_data:
    #         bpy.data.batch_remove(to_remove_data)
    
    return merged_collection
    
    for ob in list(collection.all_objects):
        utils.unlink(ob)
        collection.objects.link(ob)
    
    for child in collection.children_recursive:
        bpy.data.collections.remove(child)
        
def setup_materials(context: bpy.types.Context, importer: NWOImporter, starting_materials, imported_objects: list[bpy.types.Object], build_materials: bool, always_extract_bitmaps=False, emissive_meshes=None):
    starting_materials = starting_materials if isinstance(starting_materials, set) else set(starting_materials)
    new_materials = [mat for mat in bpy.data.materials if mat not in starting_materials]
    source_project = utils.get_project(importer.scene_nwo.scene_project)
    for mat in new_materials:
        mat.name = utils.imported_material_name(mat.name, source_project)
    # Clear duplicate materials
    missing_some_shader_paths = False
    if new_materials:
        new_materials = clear_duplicate_materials(True, new_materials)
        for m in new_materials:
            if not m.nwo.shader_path and utils.has_shader_path(m):
                missing_some_shader_paths = True
                break
    
    if missing_some_shader_paths:
        if utils.is_corinth(context):
            print('Updating material tag paths for imported objects')
        else:
            print('Updating shader tag paths for imported objects')
        imported_meshes = {ob.data for ob in imported_objects if ob.type in VALID_MESHES}
        if imported_meshes:
            find_shaders(new_materials)
                
    if build_materials:
        validated_funcs = set()
        if utils.is_corinth(context):
            print('Building Blender materials from material tags')
        else:
            print('Building Blender materials from shader tags')

        processed_shader_paths = {}
        
        for mat in new_materials:
            if not mat.users:
                bpy.data.materials.remove(mat)
                continue
            shader_path = mat.nwo.shader_path
            if shader_path:
                existing_mat = processed_shader_paths.get(shader_path)
                if existing_mat is None:
                    result = tag_to_nodes(
                        importer.corinth, mat, shader_path, always_extract_bitmaps,
                        target_game=importer.target_game if importer.build_materials_for_project else None)
                    processed_shader_paths[shader_path] = mat
                else:
                    utils.copy_material_nodes(existing_mat, mat)
                    mat.nwo.game_functions = existing_mat.nwo.game_functions
                    mat.nwo.object_functions = existing_mat.nwo.object_functions
                    if existing_mat.get('foundry_material_target_game'):
                        for key in ('foundry_material_source_game', 'foundry_material_target_game',
                                    'foundry_material_source_shader', 'foundry_material_conversion_notes'):
                            if key in existing_mat:
                                mat[key] = existing_mat[key]
                        mat.nwo['shader_path'] = existing_mat.nwo.shader_path
                        mat.nwo.prev_shader_path = existing_mat.nwo.prev_shader_path
                        mat.nwo.material_shader = existing_mat.nwo.material_shader
                        mat.nwo.shader_type = existing_mat.nwo.shader_type
                        mat.nwo.uses_blender_nodes = existing_mat.nwo.uses_blender_nodes
                        mat.nwo.game_functions = existing_mat.nwo.game_functions
                        mat.nwo.object_functions = existing_mat.nwo.object_functions
                        mat.surface_render_method = existing_mat.surface_render_method
                    
                # TODO Add emissive node
            elif importer.build_materials_for_project and mat.node_tree is not None:
                # Some decal-system materials are built while reading their
                # owning tag and have no standalone shader path to rebuild.
                from .material_game_mapping import convert_material_game
                from .node_tree_arrange import arrange
                if convert_material_game(mat, importer.game, importer.target_game):
                    mat.nwo.uses_blender_nodes = True
                    mat.nwo.material_shader = ''
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree is not None:
                            family = node.node_tree.name.partition('.')[2]
                            if family in {'shader', 'shader_custom', 'shader_decal', 'shader_foliage',
                                          'shader_glass', 'shader_halogram', 'shader_terrain'}:
                                mat.nwo.shader_type = '.' + family
                                break
                    arrange(mat.node_tree)
        
        for ob in imported_objects:
            for slot_index, slot in enumerate(ob.material_slots):
                if slot.material:
                    bind_sequence_drivers(context.scene, ob, slot_index)
                    functions = slot.material.nwo.game_functions.split(",") if slot.material.nwo.game_functions.strip(" ,") else []
                    if slot.material.nwo.object_functions.strip(" ,"):
                        validated_funcs.update(slot.material.nwo.object_functions.split(","))
                    if functions:
                        for func in functions:
                            if not func.startswith(ammo_names) and not func.startswith(tether_name):
                                add_function(context.scene, func, func, ob, ob.parent)
        
        for ob, func_dict in importer.obs_for_props.items():
            if importer.game in {'halo1', 'halo2'}:
                continue
            for export_name, funcs in func_dict.items():
                if export_name in validated_funcs:
                    for idx, func in enumerate(funcs):
                        if idx == 0:
                            add_function(context.scene, func, export_name, ob, ob.parent)
                        else:
                            add_function(context.scene, func, func, ob, ob.parent)
                            
        for attachment in importer.attachments:
            attach_arm = attachment.armature
            for func in attachment.function_names:
                for ao in attachment.objects:
                    add_function(context.scene, func, func, ao, attach_arm)
                        
    if build_materials:
        # Apply emissives even when an import reuses existing materials.
        emissive_meshes = set(emissive_meshes or ())
        if importer.game in {'halo1', 'halo2'}:
            emissive_meshes.update(ob.data for ob in imported_objects
                                   if ob.type == 'MESH' and (
                                       any(p.type == 'emissive' for p in ob.data.nwo.face_props) or
                                       any(mat and any(p.type == 'emissive' for p in mat.nwo.material_props)
                                           for mat in ob.data.materials)))
        if emissive_meshes:
            print("Setting up emissive materials")
            for mesh in emissive_meshes:
                utils.setup_emissive_attributes(mesh, importer.game)

        # NOTE Commented out until foundry node is ready
        # for mesh in {ob.data for ob in imported_objects if ob.type == 'MESH'}:
        #     if any((p.type == 'face_sides' and p.two_sided) or
        #            (p.type == 'face_mode' and p.face_mode in utils.INVISIBLE_FACE_MODES)
        #            for p in mesh.nwo.face_props):
        #         utils.setup_two_sided_preview(mesh)


class NWO_ImportGameInstanceTag(bpy.types.Operator):
    bl_idname = "nwo.import_game_instance_tag"
    bl_label = "Import Game Tag"
    bl_description = "Imports the tag referenced by this game instance marker and sets as the visual representation for the marker"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None or ob.type != 'EMPTY':
            return False
        
        if not ob.nwo.marker_game_instance_tag_name.strip():
            return False
        
        suffix = Path(ob.nwo.marker_game_instance_tag_name).suffix.lower()
        
        return suffix == ".prefab" or suffix or '.decorator_set' in suffix in OBJECT_TAG_EXTS
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not",
        options=set(),
    )
    
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )
    
    decorator_lod: bpy.props.EnumProperty(
        name="Decorator LOD",
        description="Level of detail for imported decorators",
        items=[
            ("1", "Highest", ""),
            ("2", "Medium", ""),
            ("3", "Low", ""),
            ("4", "Lowest", ""),
        ]
    )

    def execute(self, context):
        ob = context.object
        scene_nwo = utils.get_scene_props()
        tag_path = ob.nwo.marker_game_instance_tag_name
        variant = ob.nwo.marker_game_instance_tag_variant_name.lower()
        
        tag_path_rel = utils.relative_path(tag_path)
        tag_path_full = Path(utils.get_tags_path(), tag_path_rel)
        
        if not tag_path_full.exists():
            self.report({'WARNING'}, f"Tag does not exist: {tag_path_full}")
            return {'CANCELLED'}
        
        collection = next(
            (
                c for c in bpy.data.collections
                if c.nwo.game_object_path == tag_path_rel and c.nwo.game_object_variant == variant
            ),
            None,
        )
        if collection is None:
            importer = NWOImporter(context)
            starting_materials = set(bpy.data.materials)
            
            suffix = "Marker"
            if tag_path_full.suffix.lower() == ".prefab":
                suffix = "Prefab"
                collection = importer.import_prefab(ob)
            elif tag_path_full.suffix.lower() == ".decorator_set":
                suffix = "Decorator"
                collection = importer.import_decorator_set(ob, self.build_blender_materials, self.always_extract_bitmaps, single_type=variant, lod=int(self.decorator_lod), only_single_type=True)
            else:
                collection = importer.import_object(ob, None)
            if collection is None:
                self.report({'WARNING'}, f"No model tag for game object: {tag_path_rel}")
                return {'CANCELLED'}
            
            merged_collection = merge_collection(collection, suffix=suffix)
            context.scene.collection.children.unlink(collection)
            collection = importer.cache_game_object_collection(merged_collection, tag_path_rel, variant)
            
            setup_materials(context, importer, starting_materials, collection.all_objects, self.build_blender_materials, self.always_extract_bitmaps)
            
        ob.instance_type = 'COLLECTION'
        ob.instance_collection = collection
        ob.nwo.marker_instance = True
        
        ob.select_set(True)
        context.view_layer.objects.active = ob
        
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "build_blender_materials")
        layout.prop(self, "always_extract_bitmaps")
        if context.object.nwo.marker_game_instance_tag_name.lower().endswith(".decorator_set"):
            layout.prop(self, "decorator_lod")
            
class NWO_OT_InstancerToInstance(bpy.types.Operator):
    bl_idname = "nwo.instancer_to_instance"
    bl_label = "Convert Game Object to Instance Geometry"
    bl_description = "Converts the referenced object tags of selected marker instances into instanced geometry. Collision and physics are made into proxies"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'EMPTY' and context.object.nwo.marker_type == '_connected_geometry_marker_type_game_instance' and context.object.nwo.marker_game_instance_tag_name.strip()

    def execute(self, context):
        cache = {}
        corinth = utils.is_corinth(context)
        collection = context.scene.collection
        count = 0
        rotation_matrix = Matrix.Identity(4)
        scene_nwo = utils.get_scene_props()
        
        for ob in context.selected_objects:
            if not (ob.type == 'EMPTY' and ob.nwo.marker_type == '_connected_geometry_marker_type_game_instance' and ob.nwo.marker_game_instance_tag_name.strip()):
                continue
            
            if not ob.nwo.marker_game_instance_tag_name.lower().endswith(utils.object_exts):
                continue
            
            linked_instance = cache.get((ob.nwo.marker_game_instance_tag_name, ob.nwo.marker_game_instance_tag_variant_name))
            if linked_instance is None:
                object_tag = utils.relative_path(ob.nwo.marker_game_instance_tag_name)
                
                full_object_tag = Path(utils.get_tags_path(), object_tag)
                if not full_object_tag.exists():
                    continue
                
                importer = NWOImporter(context, [str(full_object_tag)])
                importer.tag_variant = ob.nwo.marker_game_instance_tag_variant_name
                imported_objects, variant = importer.import_object([str(full_object_tag)], None, for_instance_conversion=True)
                
                collection = ob.users_collection[0] if ob.users_collection else collection
                converter = ModelInstance(object_tag, variant, corinth)
                converter.from_objects(imported_objects)
                new_objects = converter.to_instance(collection)
                cache[(ob.nwo.marker_game_instance_tag_name, ob.nwo.marker_game_instance_tag_variant_name)] = converter.instance
                
                if scene_nwo.maintain_marker_axis:
                    rotation_matrix = Matrix.Rotation(importer.from_x_rot, 4, 'Z')
                
                converter.instance.matrix_world = ob.matrix_world @ rotation_matrix
                
                # For Mjolnir Tool
                if hasattr(ob, "forge"):
                    utils.copy_bl_props(ob.forge, converter.instance.forge)
                    
                converter.clean_up()
                
            else:
                new_instance = linked_instance.copy()
                collection.objects.link(new_instance)
                new_instance.matrix_world = ob.matrix_world @ rotation_matrix
                # For Mjolnir Tool
                if hasattr(ob, "forge"):
                    utils.copy_bl_props(ob.forge, new_instance.forge)

            count += 1 
            bpy.data.objects.remove(ob)
        
        self.report({'INFO'}, f"Created {count} instanced geometries")
        return {"FINISHED"}
    
def find_or_create_free_track(ad, start, end):
    for track in ad.nla_tracks:
        conflict = False
        for st in track.strips:
            if not (end <= st.frame_start or start >= st.frame_end):
                conflict = True
                break
        if not conflict:
            return track

    track = ad.nla_tracks.new()
    track.name = f"Track {len(ad.nla_tracks)}"
    return track

def add_scene_data_to_nla(sdata, scene_nwo):
    for idx, shot_frame in enumerate(sdata.shot_frames):
        shot_idx = idx + 1
        
        for cin_object in sdata.object_animations:
            if not cin_object.animations:
                continue
            animation_index = cin_object.animations.get(shot_idx)
            if animation_index is None:
                continue
            animation = scene_nwo.animations[animation_index]
            
            animation_start, animation_end = animation.frame_start, animation.frame_end
            start = shot_frame
            end = shot_frame + (animation_end - animation_start)
            
            for track in animation.action_tracks:
                if track.is_shape_key_action:
                    ob = track.object
                    shape_keys = ob.data.shape_keys
                    action = track.action
                    track = find_or_create_free_track(shape_keys.animation_data, start, end)
                    base_name = f"{ob.name}_shot{shot_idx}"
                    strip_name = base_name
                    existing = {s.name for s in track.strips}
                    if strip_name in existing:
                        i = 1
                        while f"{base_name}_{i}" in existing:
                            i += 1
                        strip_name = f"{base_name}_{i}"

                    strip = track.strips.new(strip_name, start, action)

                    strip.frame_start = start
                    strip.frame_end = end
                    strip.action_frame_start = animation_start
                    strip.action_frame_end = animation_end
                    shape_keys.animation_data.action = None
                else:
                    arm = track.object
                    action = track.action
                    track = find_or_create_free_track(arm.animation_data, start, end)
                    base_name = f"{arm.name}_shot{shot_idx}"
                    strip_name = base_name
                    existing = {s.name for s in track.strips}
                    if strip_name in existing:
                        i = 1
                        while f"{base_name}_{i}" in existing:
                            i += 1
                        strip_name = f"{base_name}_{i}"

                    strip = track.strips.new(strip_name, start, action)

                    strip.frame_start = start
                    strip.frame_end = end
                    strip.action_frame_start = animation_start
                    strip.action_frame_end = animation_end

                    arm.animation_data.action = None

            # print(f"Added {action.name} to {arm.name} at frame {shot_frame}")

def _remap_driver_targets(id_block, object_map):
    animation_data = getattr(id_block, "animation_data", None)
    if animation_data is None:
        return

    for fcurve in animation_data.drivers:
        for variable in fcurve.driver.variables:
            for target in variable.targets:
                if target.id in object_map:
                    target.id = object_map[target.id]

def _copy_collection_object(source_object: bpy.types.Object, copy_object_data=False):
    new_object = source_object.copy()
    if copy_object_data and source_object.data is not None and hasattr(source_object.data, "copy"):
        new_object.data = source_object.data.copy()
    return new_object

def clone_collection_hierarchy(source_collection: bpy.types.Collection, parent_collection=None, copy_object_data=False, collection_name=None):
    object_map = {}

    def clone_collection(source: bpy.types.Collection, target_parent=None, target_name=None):
        new_collection = bpy.data.collections.new(target_name or source.name)
        new_collection.hide_render = source.hide_render
        new_collection.hide_viewport = source.hide_viewport
        if hasattr(source, "color_tag"):
            new_collection.color_tag = source.color_tag

        if target_parent is not None:
            target_parent.children.link(new_collection)

        for source_object in source.objects:
            new_object = _copy_collection_object(source_object, copy_object_data=copy_object_data)
            new_collection.objects.link(new_object)
            object_map[source_object] = new_object

        for child in source.children:
            clone_collection(child, new_collection)

        return new_collection

    new_root = clone_collection(source_collection, parent_collection, collection_name)

    for source_object, new_object in object_map.items():
        if source_object.parent in object_map:
            new_object.parent = object_map[source_object.parent]
        else:
            new_object.parent = None

        new_object.parent_type = source_object.parent_type
        new_object.parent_bone = source_object.parent_bone

        for modifier in new_object.modifiers:
            target_object = getattr(modifier, "object", None)
            if target_object in object_map:
                modifier.object = object_map[target_object]

        for constraint in new_object.constraints:
            target_object = getattr(constraint, "target", None)
            if target_object in object_map:
                constraint.target = object_map[target_object]

        _remap_driver_targets(new_object, object_map)
        if new_object.data is not None:
            _remap_driver_targets(new_object.data, object_map)

    return new_root, object_map

def duplicate_cached_collection(template_collection: bpy.types.Collection, render_ref, parent_collection: bpy.types.Collection, copy_object_data=False):
    new_collection, object_map = clone_collection_hierarchy(
        template_collection,
        parent_collection,
        copy_object_data=copy_object_data,
    )
    new_objects = list(new_collection.all_objects)
    armature = next((obj for obj in new_objects if obj.type == 'ARMATURE' and obj.parent is None), None)
    return new_objects, armature, render_ref, new_collection, object_map

def duplicate_cached_import(template_objects, render_ref, collection_name, parent_collection):
    new_collection = bpy.data.collections.new(collection_name)
    parent_collection.children.link(new_collection)
    armature = None
    template_objects = set(template_objects)

    obj_map = {}

    for src in template_objects:
        obj = src.copy()
        if armature is None and obj.type == 'ARMATURE' and obj.parent is None:
            armature = obj

        new_collection.objects.link(obj)
        obj_map[src] = obj

    for src, obj in obj_map.items():
        if src.parent in obj_map:
            obj.parent = obj_map[src.parent]

        obj.parent_type = src.parent_type
        obj.parent_bone = src.parent_bone

    if armature is not None:
        for obj in obj_map.values():
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE':
                        mod.object = armature

    return list(obj_map.values()), armature, render_ref, new_collection

def remove_orphan_object_data(data):
    if data.users != 0:
        return

    for data_type, data_collection in (
        (bpy.types.Mesh, bpy.data.meshes),
        (bpy.types.Armature, bpy.data.armatures),
        (bpy.types.Light, bpy.data.lights),
        (bpy.types.Camera, bpy.data.cameras),
        (bpy.types.Curve, bpy.data.curves),
        (bpy.types.Lattice, bpy.data.lattices),
        (bpy.types.MetaBall, bpy.data.metaballs),
    ):
        if isinstance(data, data_type):
            data_collection.remove(data, do_unlink=True)
            return

def remove_collection_hierarchy(collection: bpy.types.Collection):
    if collection not in frozenset(bpy.data.collections):
        return

    data_to_remove = []
    for obj in list(collection.all_objects):
        data = getattr(obj, "data", None)
        if data is not None:
            data_to_remove.append(data)
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except TypeError:
            return

    for data in dict.fromkeys(data_to_remove):
        remove_orphan_object_data(data)

    for child_collection in reversed(list(collection.children_recursive)):
        if child_collection in frozenset(bpy.data.collections):
            bpy.data.collections.remove(child_collection, do_unlink=True)

    if collection in frozenset(bpy.data.collections):
        bpy.data.collections.remove(collection, do_unlink=True)

def clear_cache():
    global objects_cache
    global tag_files_by_name_cache
    for cache_entry in objects_cache.values():
        if isinstance(cache_entry, dict):
            collection = cache_entry.get("collection")
            if collection is not None:
                try:
                    remove_collection_hierarchy(collection)
                except Exception as e:
                    utils.print_warning(f"Could not clear import cache collection '{collection.name}': {e}")
    objects_cache = {}
    tag_files_by_name_cache = {}
    connected_geometry.clear_cache()
