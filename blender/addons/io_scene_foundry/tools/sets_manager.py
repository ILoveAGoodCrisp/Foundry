

'''Handles bpy operators and functions for the Sets Manager panel'''

import random
from pathlib import Path

import bpy

from ..constants import VALID_MESHES
from ..icons import get_icon_id
from ..managed_blam.model import ModelTag
from ..managed_blam.object import ObjectTag
from ..managed_blam.render_model import RenderModelTag
from ..managed_blam.scenario import ScenarioTag
from ..tools.collection_manager import get_full_name

from ..utils import create_parent_mapping, get_asset_tag, get_asset_tags, get_rig_prioritize_active, get_tags_path, get_scene_props, is_corinth, is_frame, is_marker, is_mesh, poll_ui, set_type_from_asset, update_tables_from_objects, valid_nwo_asset

def has_region_or_perm(ob):
    if is_mesh(ob) and (ob.nwo.mesh_type != '_connected_geometry_mesh_type_object_instance' or ob.nwo.marker_uses_regions):
        return True
    elif is_marker(ob) and ob.nwo.marker_uses_regions:
        return True
    elif ob.type == 'LIGHT':
        return True
    
    return False

MODEL_VARIANT_VIEWER_NONE = "__none__"
MODEL_VARIANT_VIEWER_CUSTOM = "__custom__"
MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS = "all"
MODEL_VARIANT_CHANGE_COLOR_PROPS = ("Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color")
MODEL_VARIANT_CHANGE_COLOR_PRIORITY_EXTS = (".biped", ".vehicle", ".crate", ".scenery")
MODEL_VARIANT_CHANGE_COLOR_OBJECT_TAGS = (
    (".biped", "output_biped", "template_biped"),
    (".vehicle", "output_vehicle", "template_vehicle"),
    (".crate", "output_crate", "template_crate"),
    (".scenery", "output_scenery", "template_scenery"),
    (".creature", "output_creature", "template_creature"),
    (".giant", "output_giant", "template_giant"),
    (".weapon", "output_weapon", "template_weapon"),
    (".equipment", "output_equipment", "template_equipment"),
    (".effect_scenery", "output_effect_scenery", "template_effect_scenery"),
    (".device_control", "output_device_control", "template_device_control"),
    (".device_machine", "output_device_machine", "template_device_machine"),
    (".device_terminal", "output_device_terminal", "template_device_terminal"),
    (".device_dispenser", "output_device_dispenser", "template_device_dispenser"),
)
last_model_variant_viewer_variant = MODEL_VARIANT_VIEWER_NONE
model_variant_viewer_data_cache = {}

def _dedupe_names(names):
    deduped = []
    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(name)

    return deduped

def _enum_items_from_names(names):
    items = []
    for name in _dedupe_names(names):
        items.append((name, name, ""))

    return items

def _collection_names(collection):
    return [item.name for item in collection if item.name]

def _set_collection_names(collection, names):
    collection.clear()
    for name in _dedupe_names(names):
        item = collection.add()
        item.name = name

def _model_variant_region_permutation_items(self, context):
    items = _enum_items_from_names(_collection_names(self.permutations))
    if not items:
        items.append((MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS, MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS, ""))

    return items

class NWO_ModelVariantViewerNameItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", options=set())

class NWO_ModelVariantViewerRegion(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Region", options=set())
    enabled: bpy.props.BoolProperty(name="Enabled", default=True, options=set())
    permutations: bpy.props.CollectionProperty(type=NWO_ModelVariantViewerNameItem, options=set())
    render_permutations: bpy.props.CollectionProperty(type=NWO_ModelVariantViewerNameItem, options=set())
    permutation: bpy.props.EnumProperty(
        name="Permutation",
        items=_model_variant_region_permutation_items,
        options=set(),
    )

def _model_variant_items(self, context):
    cache = model_variant_viewer_data_cache.get(getattr(self, "cache_key", ""), {})
    variants = cache.get("variants", [])
    items = [(MODEL_VARIANT_VIEWER_NONE, "none", "Show all regions and permutations")]
    items.extend(_enum_items_from_names(variants))

    return items

def _permutations_with_all(permutations):
    return _dedupe_names([MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS] + list(permutations))

def _set_model_variant_viewer_row(row, enabled, permutation):
    row.enabled = enabled
    if not permutation:
        return

    permutations = _collection_names(row.permutations)
    if permutation not in permutations:
        permutations.insert(0, permutation)
        _set_collection_names(row.permutations, permutations)
    row.permutation = permutation

def _apply_model_variant_selection(operator):
    variant = getattr(operator, "variant", MODEL_VARIANT_VIEWER_NONE)
    if variant == MODEL_VARIANT_VIEWER_NONE:
        for row in operator.regions:
            _set_model_variant_viewer_row(row, True, MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS)
        return

    if variant == MODEL_VARIANT_VIEWER_CUSTOM:
        return

    cache = model_variant_viewer_data_cache.get(getattr(operator, "cache_key", ""), {})
    variant_regions = cache.get("variant_regions", {})
    scoped_regions = variant_regions.get(variant, {})
    for row in operator.regions:
        scoped_permutations = scoped_regions.get(row.name, [])
        if scoped_permutations:
            _set_model_variant_viewer_row(row, True, random.choice(scoped_permutations))
        else:
            _set_model_variant_viewer_row(row, False, row.permutation)

def _update_model_variant_selection(self, context):
    _apply_model_variant_selection(self)

def _get_render_model_region_data(render_model_path):
    region_permutations = {}
    with RenderModelTag(path=render_model_path) as render:
        for region in render.get_regions():
            permutations = render.get_permutations(region)
            region_permutations[region] = permutations or ["default"]

    if "default" in region_permutations:
        default_region = "default"
    elif region_permutations:
        default_region = next(iter(region_permutations))
    else:
        default_region = "default"

    region_default_permutations = {}
    for region, permutations in region_permutations.items():
        if "default" in permutations:
            region_default_permutations[region] = "default"

    return region_permutations, default_region, region_default_permutations

def _variant_region_permutations(variant_element, region_permutations, default_region, region_default_permutations):
    scoped_regions = {}
    variant_regions = set()
    for region_element in variant_element.SelectField("regions").Elements:
        region = region_element.Fields[0].GetStringData()
        if region == "default":
            region = default_region

        variant_regions.add(region)
        permutations = []
        permutation_elements = region_element.SelectField("permutations").Elements
        if permutation_elements.Count == 0:
            permutations.append(region_default_permutations.get(region, "default"))
        else:
            for permutation_element in permutation_elements:
                permutation = permutation_element.Fields[0].GetStringData()
                if not permutation:
                    continue
                if permutation == "default":
                    permutation = region_default_permutations.get(region, "default")

                permutations.append(permutation)
                for state_element in permutation_element.SelectField("states").Elements:
                    state_name = state_element.Fields[0].GetStringData()
                    if state_name == "default":
                        state_name = region_default_permutations.get(region, "default")
                    if state_name:
                        permutations.append(state_name)

        scoped_regions[region] = _dedupe_names(permutations)

    for region, permutations in region_permutations.items():
        if region not in variant_regions:
            scoped_regions[region] = list(permutations)

    return scoped_regions

def _model_variant_viewer_data(model_tag_path):
    variants = []
    region_permutations = {}
    variant_regions = {}
    render_model_path = ""
    with ModelTag(path=model_tag_path) as model:
        variants = model.get_model_variants()
        render_model_path = model.get_render_model()
        default_region = "default"
        region_default_permutations = {}
        if render_model_path and Path(get_tags_path(), render_model_path).exists():
            region_permutations, default_region, region_default_permutations = _get_render_model_region_data(render_model_path)

        for variant_element in model.block_variants.Elements:
            variant_name = variant_element.Fields[0].GetStringData()
            if not variant_name:
                continue
            variant_regions[variant_name] = _variant_region_permutations(
                variant_element,
                region_permutations,
                default_region,
                region_default_permutations,
            )

    return variants, region_permutations, variant_regions, render_model_path

def _resolved_tag_path(tag_path):
    path = Path(str(tag_path).strip('"'))
    if path.is_absolute():
        return path

    return Path(get_tags_path(), path)

def _safe_mtime(path):
    if not path:
        return None

    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None

def _model_variant_viewer_cache_key(model_tag_path):
    return str(_resolved_tag_path(model_tag_path))

def _cached_model_variant_viewer_data(model_tag_path):
    cache_key = _model_variant_viewer_cache_key(model_tag_path)
    model_path = Path(cache_key)
    model_mtime = _safe_mtime(model_path)
    cached = model_variant_viewer_data_cache.get(cache_key)
    if cached and cached.get("model_mtime") == model_mtime and cached.get("render_mtime") == _safe_mtime(cached.get("render_path")):
        return cache_key, cached["variants"], cached["region_permutations"], cached["variant_regions"]

    variants, region_permutations, variant_regions, render_model_path = _model_variant_viewer_data(model_tag_path)
    resolved_render_path = _resolved_tag_path(render_model_path) if render_model_path else None
    model_variant_viewer_data_cache[cache_key] = {
        "model_mtime": model_mtime,
        "render_path": resolved_render_path,
        "render_mtime": _safe_mtime(resolved_render_path),
        "variants": variants,
        "region_permutations": region_permutations,
        "variant_regions": variant_regions,
    }

    return cache_key, variants, region_permutations, variant_regions

def _object_type_visible_for_variant(ob, nwo):
    if ob.type == 'LIGHT':
        return nwo.connected_geometry_object_type_light_visible
    elif is_frame(ob):
        return nwo.connected_geometry_object_type_frame_visible
    elif is_marker(ob):
        return getattr(nwo, f"{ob.nwo.marker_type[1:]}_visible", True)
    elif is_mesh(ob):
        mesh_type = getattr(ob.data.nwo, "mesh_type", ob.nwo.mesh_type)
        return getattr(nwo, f"{mesh_type[1:]}_visible", True)

    return True

def _is_object_instance(ob):
    return is_mesh(ob) and ob.nwo.mesh_type == '_connected_geometry_mesh_type_object_instance'

def _marker_permutation_matches(nwo, permutation):
    marker_permutations = {item.name for item in nwo.marker_permutations if item.name}
    if not marker_permutations:
        return True

    if nwo.marker_permutation_type == "include":
        return permutation in marker_permutations
    elif nwo.marker_permutation_type == "exclude":
        return permutation not in marker_permutations

    return True

def _marker_matches_any_permutation(nwo, permutations):
    marker_permutations = {item.name for item in nwo.marker_permutations if item.name}
    if not marker_permutations:
        return True

    permutations = {permutation for permutation in permutations if permutation and permutation != MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS}
    if not permutations:
        return False

    if nwo.marker_permutation_type == "include":
        return bool(marker_permutations & permutations)
    elif nwo.marker_permutation_type == "exclude":
        return bool(permutations - marker_permutations)

    return True

def _model_variant_clone_map(scene_nwo):
    clone_map = {}
    for permutation in scene_nwo.permutations_table:
        for clone in permutation.clones:
            if clone.name:
                clone_map[clone.name] = (permutation.name, clone)

    return clone_map

def _is_default_permutation_sentinel(region, permutation, render_region_permutations):
    if permutation != "default":
        return False

    return "default" not in render_region_permutations.get(region, set())

def _variant_viewer_object_matches(ob, region, permutation, render_region_permutations, collection_map, clone_map):
    if _is_object_instance(ob):
        if not ob.nwo.marker_uses_regions:
            return True

        if not true_table_entry(ob, "region_name", region, collection_map):
            return False

        if permutation == MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS:
            return _marker_matches_any_permutation(ob.nwo, render_region_permutations.get(region, set()))

        if _is_default_permutation_sentinel(region, permutation, render_region_permutations):
            return False

        return _marker_permutation_matches(ob.nwo, permutation)

    if is_marker(ob) and ob.nwo.marker_uses_regions:
        if not true_table_entry(ob, "region_name", region, collection_map):
            return False

        if permutation == MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS:
            return _marker_matches_any_permutation(ob.nwo, render_region_permutations.get(region, set()))

        if _is_default_permutation_sentinel(region, permutation, render_region_permutations):
            return False

        return _marker_permutation_matches(ob.nwo, permutation)

    if not true_table_entry(ob, "region_name", region, collection_map):
        return False

    if permutation == MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS:
        permutations = render_region_permutations.get(region, set())
        if not permutations:
            return True

        return any(true_table_entry(ob, "permutation_name", perm, collection_map) for perm in permutations)

    if _is_default_permutation_sentinel(region, permutation, render_region_permutations):
        return False

    if true_table_entry(ob, "permutation_name", permutation, collection_map):
        return True

    clone = clone_map.get(permutation)
    return clone is not None and true_table_entry(ob, "permutation_name", clone[0], collection_map)

def _iter_clone_material_overrides(clone, enabled_only=True):
    if enabled_only and not clone.enabled:
        return

    for override in clone.material_overrides:
        if enabled_only and not override.enabled:
            continue
        if override.source_material is None or override.destination_material is None:
            continue

        yield override

def _reset_model_variant_clone_materials(context, collection_map, clone_map):
    source_permutations = {source for source, _ in clone_map.values()}
    if not source_permutations:
        return

    for ob in context.view_layer.objects:
        if ob.type not in VALID_MESHES or _is_object_instance(ob):
            continue
        for source_permutation in source_permutations:
            if not true_table_entry(ob, "permutation_name", source_permutation, collection_map):
                continue
            for other_source, clone in clone_map.values():
                if other_source != source_permutation:
                    continue
                for override in _iter_clone_material_overrides(clone, enabled_only=False):
                    for slot in ob.material_slots:
                        if slot.material is override.destination_material:
                            slot.material = override.source_material

def _apply_model_variant_clone_materials(context, selected_regions, collection_map, clone_map):
    applied = set()
    selected_clone_regions = [
        (region, permutation, clone_map[permutation][0], clone_map[permutation][1])
        for region, permutation in selected_regions
        if permutation in clone_map
    ]
    if not selected_clone_regions:
        return applied

    for ob in context.view_layer.objects:
        if ob.type not in VALID_MESHES or _is_object_instance(ob):
            continue
        for region, clone_name, source_permutation, clone in selected_clone_regions:
            if not true_table_entry(ob, "region_name", region, collection_map):
                continue
            if not true_table_entry(ob, "permutation_name", source_permutation, collection_map):
                continue
            for override in _iter_clone_material_overrides(clone):
                for slot in ob.material_slots:
                    if slot.material is override.source_material:
                        slot.material = override.destination_material
                        applied.add(clone_name)

    return applied

def _tag_path_exists(tag_path):
    if not tag_path:
        return False

    path = Path(str(tag_path).strip('"'))
    if path.is_absolute():
        return path.exists()

    return Path(get_tags_path(), path).exists()

def _append_change_color_candidate(candidates, tag_path):
    if not tag_path:
        return

    tag_path = str(tag_path).strip('"')
    if not tag_path or tag_path in candidates:
        return

    if _tag_path_exists(tag_path):
        candidates.append(tag_path)

def _append_scene_object_tag_candidates(candidates, scene_nwo, extensions, require_enabled):
    by_extension = {extension: (output_prop, template_prop) for extension, output_prop, template_prop in MODEL_VARIANT_CHANGE_COLOR_OBJECT_TAGS}
    for extension in extensions:
        output_prop, template_prop = by_extension[extension]
        if require_enabled and not getattr(scene_nwo, output_prop, False):
            continue

        _append_change_color_candidate(candidates, get_asset_tag(extension))
        _append_change_color_candidate(candidates, getattr(scene_nwo, template_prop, ""))
        for tag_path in get_asset_tags(extension):
            _append_change_color_candidate(candidates, tag_path)

def _model_variant_change_color_candidates(context):
    candidates = []
    armature = get_rig_prioritize_active(context)
    if armature:
        _append_change_color_candidate(candidates, armature.nwo.cinematic_object)

    scene_nwo = get_scene_props()
    priority_extensions = MODEL_VARIANT_CHANGE_COLOR_PRIORITY_EXTS
    other_extensions = tuple(extension for extension, _, _ in MODEL_VARIANT_CHANGE_COLOR_OBJECT_TAGS if extension not in priority_extensions)
    _append_scene_object_tag_candidates(candidates, scene_nwo, priority_extensions, True)
    _append_scene_object_tag_candidates(candidates, scene_nwo, priority_extensions, False)
    _append_scene_object_tag_candidates(candidates, scene_nwo, other_extensions, True)
    _append_scene_object_tag_candidates(candidates, scene_nwo, other_extensions, False)

    return armature, candidates

def _set_color_id_property(ob, name, value):
    ob[name] = value
    ob.id_properties_ui(name).update(subtype="COLOR", min=0, max=1)
    ob.update_tag(refresh={'DATA'})

def _apply_model_variant_change_colors(context, variant):
    armature, candidates = _model_variant_change_color_candidates(context)
    if not armature or not candidates:
        return ""

    if variant in {MODEL_VARIANT_VIEWER_NONE, MODEL_VARIANT_VIEWER_CUSTOM}:
        variant = ""

    for tag_path in candidates:
        with ObjectTag(path=tag_path) as object_tag:
            change_colors = object_tag.get_change_colors(variant)

        if change_colors is None:
            continue

        for name, value in zip(MODEL_VARIANT_CHANGE_COLOR_PROPS, change_colors):
            _set_color_id_property(armature, name, value)

        return tag_path

    return ""

class NWO_OT_ModelVariantViewer(bpy.types.Operator):
    bl_idname = "nwo.model_variant_viewer"
    bl_label = "Model Variant Viewer"
    bl_description = "Preview a model variant by hiding objects outside the selected region/permutation choices"
    bl_options = {"UNDO"}

    cache_key: bpy.props.StringProperty(options={'HIDDEN'})
    variant: bpy.props.EnumProperty(
        name="Variant",
        items=_model_variant_items,
        update=_update_model_variant_selection,
        options=set(),
    )
    regions: bpy.props.CollectionProperty(type=NWO_ModelVariantViewerRegion, options=set())

    @classmethod
    def poll(cls, context):
        nwo = get_scene_props()
        return poll_ui(('model', 'sky')) and nwo.regions_table and nwo.permutations_table

    def _populate(self, context):
        global last_model_variant_viewer_variant

        scene_nwo = get_scene_props()
        model_tag_path = get_asset_tag(".model")
        if not model_tag_path:
            model_tag_path = scene_nwo.template_model
            if not model_tag_path:
                arm = get_rig_prioritize_active(context)
                if arm:
                    render_model = arm.nwo.node_order_source
                    if render_model:
                        model_tag_path = str(Path(render_model).with_suffix(".model"))

                if not model_tag_path:
                    self.report({'WARNING'}, "No model tag found. Export the asset before opening the variant viewer")
                    return False

        try:
            cache_key, variants, region_permutations, variant_regions = _cached_model_variant_viewer_data(model_tag_path)
        except Exception as error:
            self.report({'WARNING'}, f"Failed to read model variants: {error}")
            return False

        scene_nwo = get_scene_props()
        scene_regions = [item.name for item in scene_nwo.regions_table]
        scene_permutations = [item.name for item in scene_nwo.permutations_table] or ["default"]
        region_names = _dedupe_names(scene_regions + list(region_permutations))

        self.cache_key = cache_key
        self.regions.clear()
        for region in region_names:
            row = self.regions.add()
            row.name = region
            render_permutations = _dedupe_names(region_permutations.get(region) or scene_permutations)
            _set_collection_names(row.permutations, _permutations_with_all(render_permutations))
            _set_collection_names(row.render_permutations, render_permutations)
            row.permutation = MODEL_VARIANT_VIEWER_ALL_PERMUTATIONS
            row.enabled = True

        self.variant = last_model_variant_viewer_variant if last_model_variant_viewer_variant in variants else MODEL_VARIANT_VIEWER_NONE
        _apply_model_variant_selection(self)
        return True

    def invoke(self, context, event):
        if not self._populate(context):
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text="Variant")
        row.prop(self, "variant", text="")
        layout.separator()

        for item in self.regions:
            row = layout.row(align=True)
            row.prop(item, "enabled", text=item.name)
            perm_row = row.row(align=True)
            perm_row.enabled = item.enabled
            perm_row.prop(item, "permutation", text="")

    def execute(self, context):
        global last_model_variant_viewer_variant

        selected_region_items = [(item.name, item.permutation) for item in self.regions if item.enabled and item.permutation]
        if not selected_region_items:
            self.report({'WARNING'}, "No regions selected")
            return {'CANCELLED'}

        render_region_permutations = {
            item.name: set(_collection_names(item.render_permutations))
            for item in self.regions
        }
        change_color_source = _apply_model_variant_change_colors(context, self.variant)
        collection_map = create_parent_mapping(context)
        scene_nwo = get_scene_props()
        clone_map = _model_variant_clone_map(scene_nwo)
        _reset_model_variant_clone_materials(context, collection_map, clone_map)
        applied_clones = _apply_model_variant_clone_materials(context, selected_region_items, collection_map, clone_map)
        visible_count = 0
        hidden_count = 0
        for ob in context.view_layer.objects:
            if not has_region_or_perm(ob) and not _is_object_instance(ob):
                continue

            visible = False
            for region, permutation in selected_region_items:
                if _variant_viewer_object_matches(ob, region, permutation, render_region_permutations, collection_map, clone_map):
                    visible = _object_type_visible_for_variant(ob, scene_nwo)
                    break

            ob.hide_set(not visible)
            ob.hide_render = (not visible)
            if visible:
                visible_count += 1
            else:
                hidden_count += 1

        if hasattr(context.area, 'tag_redraw'):
            context.area.tag_redraw()

        message = f"Showing {visible_count} objects. Hid {hidden_count}"
        if change_color_source:
            message += f". Applied change colors from {Path(change_color_source).name}"
        if applied_clones:
            message += f". Applied clone materials for {', '.join(sorted(applied_clones))}"
        self.report({'INFO'}, message)
        last_model_variant_viewer_variant = self.variant
        return {'FINISHED'}

class NWO_UpdateSets(bpy.types.Operator):
    bl_idname = "nwo.update_sets"
    bl_label = "Sync"
    bl_description = "Ensures object hidden and hide select states match what is defined in the sets manager.\n\nThis also updates the regions and permutations table entires from scene objects. Useful if you have a mismatch between object regions/permutations and the sets manager tables"
    bl_options = {"UNDO"}

    def execute(self, context):
        scene_nwo = get_scene_props()
        update_tables_from_objects(context)
        for item in scene_nwo.regions_table:
            bpy.ops.nwo.region_hide(entry_name=item.name)
            bpy.ops.nwo.region_hide_select(entry_name=item.name)
        for item in scene_nwo.permutations_table:
            bpy.ops.nwo.permutation_hide(entry_name=item.name)
            bpy.ops.nwo.permutation_hide_select(entry_name=item.name)
            
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_default')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_collision')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_physics')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_object_instance')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_structure')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_seam')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_portal')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_water_surface')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_poop_vertical_rain_sheet')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_planar_fog_volume')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_lightmap_region')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_boundary_surface')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_obb_volume')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_cookie_cutter')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_poop_rain_blocker')
        
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_model')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_effects')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_garbage')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_hint')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_pathfinding_sphere')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_physics_constraint')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_target')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_game_instance')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_airprobe')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_envfx')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_lightCone')
        
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_object_type_frame')
        bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_object_type_light')
            
        self.report({'INFO'}, "Sync Complete")
        return {"FINISHED"}
            

# Parent Classes
class TableEntryAdd(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}

    set_object_prop: bpy.props.IntProperty()
    name: bpy.props.StringProperty(name="Name")

    def execute(self, context):
        name = self.name.lower()
        nwo = get_scene_props()
        table = getattr(nwo, self.table_str)
        all_names = [entry.name for entry in table]

        if not name:
            self.report({'WARNING'}, f"{self.type_str} name cannot be empty")
            return {'CANCELLED'}
        elif len(name) > 128:
            self.report({'WARNING'}, f"{self.type_str} name has a maximum of 128 characters")
            return {'CANCELLED'}
        elif name in all_names:
            self.report({'WARNING'}, f"{self.type_str} name already exists")
            return {'CANCELLED'}
    
        entry = table.add()
        entry.old = name
        entry.name = name
        entry.set_type = set_type_from_asset(nwo)
        setattr(nwo, f"{self.table_str}_active_index", len(table) - 1)
        if self.set_object_prop == 1:
            ob = context.object
            if ob: setattr(ob.nwo, self.ob_prop_str, name)
        elif self.set_object_prop == 2:
            [setattr(ob.nwo, self.ob_prop_str, name) for ob in context.selected_objects]

        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.activate_init = True
        layout.prop(self, "name", text="Name")

class TableEntryRemove(bpy.types.Operator):
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = get_scene_props()
        table = getattr(nwo, self.table_str)
        
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        entry = table[table_active_index]
        scene_objects = context.scene.objects
        old_entry_name = entry.name
        entry_objects = [ob for ob in scene_objects if getattr(ob.nwo, self.ob_prop_str) == entry.name]
        table.remove(table_active_index)
        if table_active_index > len(table) - 1:
            setattr(nwo, table_active_index_str, table_active_index - 1)
        new_entry_name = table[0].name
        for ob in entry_objects:
            setattr(ob.nwo, self.ob_prop_str, new_entry_name)
        if self.ob_prop_str == 'permutation_name':
            for ob in scene_objects:
                perms_list = ob.nwo.marker_permutations
                perms_to_remove = []
                for idx, perm in enumerate(perms_list):
                    if perm.name == old_entry_name:
                        perms_to_remove.append(idx)
                        
                while perms_to_remove:
                    perms_list.remove(perms_to_remove[0])
                    perms_to_remove.pop(0)
                    perms_to_remove = [idx - 1 for idx in perms_to_remove]
                
                if ob.nwo.marker_permutations_index >= len(perms_list):
                    ob.nwo.marker_permutations_index = 0
                    
        for coll in bpy.data.collections:
            if coll.library:
                continue
            if self.ob_prop_str == 'region_name':
                if coll.nwo.type == 'region' and coll.nwo.region == old_entry_name:
                    coll.nwo.region = new_entry_name
                    coll.name = get_full_name(coll.nwo.type, new_entry_name)
            elif self.ob_prop_str == 'permutation_name':
                if coll.nwo.type == 'permutation' and coll.nwo.permutation == old_entry_name:
                    coll.nwo.permutation = new_entry_name 
                    coll.name = get_full_name(coll.nwo.type, new_entry_name)
                        
        context.area.tag_redraw()
        return {'FINISHED'}
    
class TableEntryMove(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = get_scene_props()
        table = getattr(nwo, self.table_str)
            
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = table_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        setattr(nwo, table_active_index_str, to_index)
            
        context.area.tag_redraw()
        return {'FINISHED'}

class TableEntryAssignSingle(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    def execute(self, context):
        nwo = context.object.nwo
        old_name = getattr(nwo, self.ob_prop_str)
        setattr(nwo, self.ob_prop_str, self.name)
        if self.ob_prop_str == "region_name" and nwo.seam_back == self.name:
            nwo.seam_back = old_name
        return {'FINISHED'}
    
class TableEntryAssign(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    def execute(self, context):
        sel_obs = context.selected_objects
        for ob in sel_obs:
            old_name = getattr(ob.nwo, self.ob_prop_str)
            setattr(ob.nwo, self.ob_prop_str, self.name)
            if self.ob_prop_str == "region_name" and ob.nwo.seam_back == self.name:
                ob.nwo.seam_back = old_name
        return {'FINISHED'}
    
class TableEntrySelect(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    select: bpy.props.BoolProperty()
    
    def execute(self, context):
        nwo = get_scene_props()
        table = getattr(nwo, self.table_str)
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        entry = table[table_active_index]
        available_objects = [ob for ob in context.view_layer.objects if has_region_or_perm(ob)]
        collection_map = create_parent_mapping(context)
        entry_objects = [ob for ob in available_objects if true_table_entry(ob, self.ob_prop_str, entry.name, collection_map)]
        [ob.select_set(self.select) for ob in entry_objects]
        return {'FINISHED'}
    
class TableEntryRename(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    
    new_name: bpy.props.StringProperty(
        name="New Name",
    )

    index: bpy.props.IntProperty()
    
    def execute(self, context):
        nwo = get_scene_props()
        new_name = self.new_name.lower()
        table = getattr(nwo, self.table_str)
        table_active_index = self.index
        all_names = [entry.name for entry in table]
        all_names.pop(table_active_index)
        entry = table[table_active_index]

        if not entry.old:
            entry.old = 'default'
        if not new_name:
            self.report({'WARNING'}, f"{self.type_str} name cannot be empty")
            entry.name = entry.old
            return {'CANCELLED'}
        elif len(new_name) > 128:
            self.report({'WARNING'}, f"{self.type_str} name has a maximum of 128 characters")
            entry.name = entry.old
            return {'CANCELLED'}
        elif new_name in all_names:
            self.report({'WARNING'}, f"{self.type_str} name already exists")
            entry.name = entry.old
            return {'CANCELLED'}
        
        scene_objects = context.scene.objects
        entry_objects = [ob for ob in scene_objects if getattr(ob.nwo, self.ob_prop_str) == entry.old]
        seam_objects = []
        if self.ob_prop_str == "region_name":
            seam_objects = [ob for ob in scene_objects if ob.nwo.seam_back == entry.old]
        entry_collections = []
        if self.ob_prop_str == 'region_name':
            entry_collections = [coll for coll in bpy.data.collections if coll.nwo.region == entry.old]
        elif self.ob_prop_str == 'permutation_name':
            entry_collections = [coll for coll in bpy.data.collections if coll.nwo.permutation == entry.old]
        old_name = str(entry.old)
        entry.old = new_name
        entry.name = new_name
        for ob in entry_objects:
            setattr(ob.nwo, self.ob_prop_str, new_name)
        for ob in seam_objects:
            ob.nwo.seam_back = new_name
            
        if self.ob_prop_str == 'permutation_name':
            for ob in scene_objects:
                perms_list = ob.nwo.marker_permutations
                for perm in perms_list:
                    if perm.name == old_name:
                        perm.name = new_name
                    
        for coll in entry_collections:
            if self.ob_prop_str == 'region_name':
                coll.nwo.region = new_name
            elif self.ob_prop_str == 'permutation_name':
                coll.nwo.permutation = new_name
                
            coll.name = get_full_name(coll.nwo.type, new_name)

        if hasattr(context.area, 'tag_redraw'):
            context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.activate_init = True
        layout.prop(self, "new_name", text="New Name")

class TableEntryHide(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    entry_name: bpy.props.StringProperty()
    
    def execute(self, context):
        collection_map = create_parent_mapping(context)
        nwo = get_scene_props()
        table = getattr(nwo, self.table_str)
        entry = get_entry(table, self.entry_name)
        should_hide = entry.hidden
        available_objects = [ob for ob in context.view_layer.objects if has_region_or_perm(ob) and not ob.nwo.ignore_for_export]
        entry_objects = [ob for ob in available_objects if true_table_entry(ob, self.ob_prop_str, entry.name, collection_map)]
        if should_hide:
            for ob in entry_objects:
                ob.hide_set(True)
        else:
            unhide_objects(entry_objects, nwo, collection_map)

        return {'FINISHED'}
    
class TableEntryHideSelect(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    entry_name: bpy.props.StringProperty()
    
    def execute(self, context):
        collection_map = create_parent_mapping(context)
        nwo = get_scene_props()
        table = getattr(nwo, self.table_str)
        entry = get_entry(table, self.entry_name)
        should_hide_select = entry.hide_select
        available_objects = [ob for ob in context.view_layer.objects if has_region_or_perm(ob) and not ob.nwo.ignore_for_export]
        entry_objects = [ob for ob in available_objects if true_table_entry(ob, self.ob_prop_str, entry.name, collection_map)]
        regions_table = getattr(nwo, 'regions_table')
        permutations_table = getattr(nwo, 'permutations_table')
        for ob in entry_objects:
            if should_hide_select == False:
                region = None
                permutation = None
                ecoll = collection_map.get(ob.nwo.export_collection)
                if ecoll:
                    region = ecoll.region
                    permutation = ecoll.permutation
                if region is None:
                    region = ob.nwo.region_name
                if permutation is None:
                    permutation = ob.nwo.permutation_name    
                
                if get_entry(regions_table, region).hide_select or get_entry(permutations_table, permutation).hide_select:
                    continue
                
            ob.hide_select = should_hide_select
        return {'FINISHED'}

# REGIONS
class NWO_RegionAdd(TableEntryAdd):
    bl_label = ""
    bl_idname = "nwo.region_add"
    bl_description = "Add a new Region"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type_str = "Region"
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Add a new BSP"
        else:
            return "Add a new Region"

class NWO_FaceRegionAdd(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.face_region_add"
    bl_description = "Add a new Region"
    bl_options = {'UNDO'}

    set_object_prop: bpy.props.BoolProperty()
    name: bpy.props.StringProperty()

    def execute(self, context):
        name = self.name.lower()
        nwo = get_scene_props()
        table = getattr(nwo, "regions_table")
        all_names = [entry.name for entry in table]

        if not name:
            self.report({'WARNING'}, f"Region name cannot be empty")
            return {'CANCELLED'}
        elif len(name) > 128:
            self.report({'WARNING'}, f"Region name has a maximum of 128 characters")
            return {'CANCELLED'}
        elif name in all_names:
            self.report({'WARNING'}, f"Region name already exists")
            return {'CANCELLED'}
    
        entry = table.add()
        entry.old = name
        entry.name = name
        entry.set_type = set_type_from_asset(nwo)
        setattr(nwo, f"regions_table_active_index", len(table) - 1)
        if self.set_object_prop:
            ob = context.object
            if ob and ob.type == 'MESH':
                face_attribute = ob.data.nwo.face_props[ob.data.nwo.face_props_active_index]
                face_attribute.region = name

        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.activate_init = True
        layout.prop(self, "name", text="Name")

class NWO_RegionRemove(TableEntryRemove):
    bl_label = ""
    bl_idname = "nwo.region_remove"
    bl_description = "Removes the active Region"

    @classmethod
    def poll(cls, context):
        return len(get_scene_props().regions_table) > 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Removes the active BSP"
        else:
            return "Removes the active Region"
    
class NWO_RegionMove(TableEntryMove):
    bl_label = ""
    bl_idname = "nwo.region_move"
    bl_description = "Moves the active Region"

    @classmethod
    def poll(cls, context):
        return len(get_scene_props().regions_table) > 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Moves the active BSP"
        else:
            return "Moves the active Region"
    
class NWO_RegionAssignSingle(TableEntryAssignSingle):
    bl_label = ""
    bl_idname = "nwo.region_assign_single"
    bl_description = "Assigns the active Region to the active Object"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table and context.object

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Assigns the selected BSP to the active Object"
        else:
            return "Assigns the selected Region to the active Object"
        
class NWO_FaceRegionAssignSingle(bpy.types.Operator):
    bl_options = {'UNDO'}
    bl_label = ''
    bl_idname = 'nwo.face_region_assign_single'
    bl_description = "Assigns the active Region to the active face property"
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in VALID_MESHES
    
    def execute(self, context):
        mesh = context.object.data
        face_attribute = mesh.nwo.face_props[mesh.nwo.face_props_active_index]
        face_attribute.region = self.name
        return {'FINISHED'}
    
class NWO_MaterialRegionAssignSingle(bpy.types.Operator):
    bl_options = {'UNDO'}
    bl_label = ''
    bl_idname = 'nwo.material_region_assign_single'
    bl_description = "Assigns the active Region to the active material"
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type in VALID_MESHES
    
    
    def execute(self, context):
        mat = context.object.active_material
        material_attribute = mat.nwo.material_props[mat.nwo.material_props_active_index]
        material_attribute.region = self.name
        return {'FINISHED'}
    
class NWO_RegionAssign(TableEntryAssign):
    bl_label = ""
    bl_idname = "nwo.region_assign"
    bl_description = "Assigns the active Region to selected Objects"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table and context.selected_objects

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Assigns the active BSP to selected Objects"
        else:
            return "Assigns the active Region to selected Objects"
    
class NWO_RegionSelect(TableEntrySelect):
    bl_label = ""
    bl_idname = "nwo.region_select"
    bl_description = "Selects/Deselects the active Region"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            if properties.select:
                return "Selects the active BSP"
            else:
                return "Deselects the active BSP"
        else:
            if properties.select:
                return "Selects the active Region"
            else:
                return "Deselects the active Region"
    
class NWO_RegionRename(TableEntryRename):
    bl_label = ""
    bl_idname = "nwo.region_rename"
    bl_description = "Renames the active Region and updates scene objects"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type_str = "Region"
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Renames the active BSP and updates scene objects"
        else:
            return "Renames the active Region and updates scene objects"
    
class NWO_RegionHide(TableEntryHide):
    bl_label = ""
    bl_idname = "nwo.region_hide"
    bl_description = "Hides/Unhides the active Region"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            if properties.hidden:
                return "Unhides the active BSP"
            else:
                return "Hides the active BSP"
        else:
            if properties.select:
                return "Unhides the active Region"
            else:
                return "Hides the active Region"

class NWO_RegionHideSelect(TableEntryHideSelect):
    bl_label = ""
    bl_idname = "nwo.region_hide_select"
    bl_description = "Disables selection of the active Region objects"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            if properties.hide_select:
                return "Enables selection of the active BSP objects"
            else:
                return "Disables selection of the active BSP objects"
        else:
            if properties.select:
                return "Enables selection of the active Region objects"
            else:
                return "Disables selection of the active Region objects"

# PERMUTATIONS
class NWO_PermutationAdd(TableEntryAdd):
    bl_label = ""
    bl_idname = "nwo.permutation_add"
    bl_description = "Add a new Permutation"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type_str = "Permutation"
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Add a new Layer"
        else:
            return "Add a new Permutation"

class NWO_PermutationRemove(TableEntryRemove):
    bl_label = ""
    bl_idname = "nwo.permutation_remove"
    bl_description = "Removes the active Permutation"

    @classmethod
    def poll(cls, context):
        return len(get_scene_props().permutations_table) > 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Removes the active Layer"
        else:
            return "Removes the active Permutation"
    
class NWO_PermutationMove(TableEntryMove):
    bl_label = ""
    bl_idname = "nwo.permutation_move"
    bl_description = "Moves the active Permutation"

    @classmethod
    def poll(cls, context):
        return len(get_scene_props().permutations_table) > 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Moves the active Layer"
        else:
            return "Moves the active Permutation"
    
class NWO_PermutationAssignSingle(TableEntryAssignSingle):
    bl_label = ""
    bl_idname = "nwo.permutation_assign_single"
    bl_description = "Assigns the selected Permutation to the active Object"

    @classmethod
    def poll(cls, context):
        return get_scene_props().permutations_table and context.object
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Assigns the selected Layer to the active Object"
        else:
            return "Assigns the selected Permutation to the active Object"
    
class NWO_PermutationAssign(TableEntryAssign):
    bl_label = ""
    bl_idname = "nwo.permutation_assign"
    bl_description = "Assigns the active Permutation to selected Objects"

    @classmethod
    def poll(cls, context):
        return get_scene_props().permutations_table and context.selected_objects

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Assigns the active Layer to selected Objects"
        else:
            return "Assigns the active Permutation to selected Objects"
    
class NWO_PermutationSelect(TableEntrySelect):
    bl_label = ""
    bl_idname = "nwo.permutation_select"
    bl_description = "Selects/Deselects the active Permutation"

    @classmethod
    def poll(cls, context):
        return get_scene_props().permutations_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            if properties.select:
                return "Selects the active Layer"
            else:
                return "Deselects the active Layer"
        else:
            if properties.select:
                return "Selects the active Permutation"
            else:
                return "Deselects the active Permutation"
    
class NWO_PermutationRename(TableEntryRename):
    bl_label = ""
    bl_idname = "nwo.permutation_rename"
    bl_description = "Renames the active Permutation and updates scene objects"

    @classmethod
    def poll(cls, context):
        return get_scene_props().permutations_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type_str = "Permutation"
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            return "Renames the active Layer and updates scene objects"
        else:
            return "Renames the active Permutation and updates scene objects"
    
class NWO_PermutationHide(TableEntryHide):
    bl_label = ""
    bl_idname = "nwo.permutation_hide"
    bl_description = "Hides/Unhides the active Permutation"

    @classmethod
    def poll(cls, context):
        return get_scene_props().permutations_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            if properties.hide_select:
                return "Enables selection of the active Layer objects"
            else:
                return "Disables selection of the active Layer objects"
        else:
            if properties.select:
                return "Enables selection of the active Permutation objects"
            else:
                return "Disables selection of the active Permutation objects"

class NWO_PermutationHideSelect(TableEntryHideSelect):
    bl_label = ""
    bl_idname = "nwo.permutation_hide_select"
    bl_description = "Disable selection of the active Permutation objects"

    @classmethod
    def poll(cls, context):
        return get_scene_props().permutations_table

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = get_scene_props().asset_type == 'scenario'
        if is_scenario:
            if properties.hide_select:
                return "Enables selection of the active Layer objects"
            else:
                return "Disables selection of the active Layer objects"
        else:
            if properties.select:
                return "Enables selection of the active Permutation objects"
            else:
                return "Disables selection of the active Permutation objects"


class NWO_SeamAssignSingle(TableEntryAssignSingle):
    bl_label = ""
    bl_idname = "nwo.seam_backface_assign_single"
    bl_description = "Sets the selected BSP as this seam's backfacing BSP reference"

    @classmethod
    def poll(cls, context):
        return get_scene_props().regions_table and context.object

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_str = "regions_table"
        self.ob_prop_str = "seam_back"

# HELPER FUNCTIONS

def get_entry(table, entry_name):
    for entry in table:
        if entry.name == entry_name:
            return entry
        
def true_table_entry(ob, ob_prop_str, entry_name, collection_map) -> bool:
    region = None
    permutation = None
    ecoll = collection_map.get(ob.nwo.export_collection)
    if ecoll:
        region = ecoll.region
        permutation = ecoll.permutation
    if region is None:
        region = ob.nwo.region_name
    if permutation is None:
        permutation = ob.nwo.permutation_name    
    
    if ob_prop_str == "region_name":
        return region == entry_name
    elif ob_prop_str == "permutation_name":
        if is_marker(ob) or ob.nwo.mesh_type == '_connected_geometry_mesh_type_object_instance':
            perms = [perm.name for perm in ob.nwo.marker_permutations]
            if ob.nwo.marker_permutation_type == 'exclude':
                return entry_name not in perms
            elif ob.nwo.marker_permutation_type == 'include':
                return entry_name in perms
            
        return permutation == entry_name
    
    
# COOL TOOLS MENU
class NWO_BSPContextMenu(bpy.types.Menu):
    bl_idname = "NWO_MT_BSPContextMenu"
    bl_label = "BSP Context Menu"
        
    def draw(self, context):
        layout = self.layout
        layout.operator("nwo.print_bsp_info", text="Show BSP Info", icon='INFO')
        layout.operator("nwo.set_bsp_lightmap_res", text="Set BSP Lightmap Resolution", icon='OUTLINER_DATA_LIGHTPROBE')
        if is_corinth(context):
            layout.operator("nwo.set_default_sky", text="Set BSP Sky", icon_value=get_icon_id("sky"))
        
        
class NWO_BSPInfo(bpy.types.Operator):
    bl_idname = "nwo.print_bsp_info"
    bl_label = "Show BSP Info"
    bl_description = "Outputs information about the selected BSP"
    
    @classmethod
    def poll(cls, context):
        return poll_ui(('scenario',)) and valid_nwo_asset(context)
        
    def execute(self, context):
        self.info = None
        nwo = get_scene_props()
        bsp = nwo.regions_table[nwo.regions_table_active_index].name
        with ScenarioTag() as scenario:
            self.info = scenario.get_bsp_info(bsp)
        
        if self.info is None:
            self.report({'WARNING'}, f"BSP {bsp} does not exist in scenario tag. You may need to export this scene")
            return {'CANCELLED'}
        return context.window_manager.invoke_popup(self)
    
    def draw(self, context):
        layout = self.layout
        for k, v in self.info.items():
            layout.label(text=f'{k}: {v}')
            
class NWO_BSPSetLightmapRes(bpy.types.Operator):
    bl_idname = "nwo.set_bsp_lightmap_res"
    bl_label = "Set BSP Lightmap Resolution"
    bl_description = "Sets the lightmap resolution (size class) for this BSP. If this is a H4+ project, then it also allows you set the refinement size class"
    
    def size_class_items(self, context):
        items = []
        if is_corinth(context):
            items.append(("0", "32x32", ""))
            items.append(("1", "64x64", ""))
            items.append(("2", "128x128", ""))
            items.append(("3", "256x256", ""))
            items.append(("4", "512x512", ""))
            items.append(("5", "768x768", ""))
            items.append(("6", "1024x1024", ""))
            items.append(("7", "1280x1280", ""))
            items.append(("8", "1536x1536", ""))
            items.append(("9", "1792x1792", ""))
            items.append(("10", "2048x2048", ""))
            items.append(("11", "2304x2304", ""))
            items.append(("12", "2560x2560", ""))
            items.append(("13", "2816x2816", ""))
            items.append(("14", "3072x3072", ""))
        else:
            items.append(("0", "256x256", ""))
            items.append(("1", "512x512", ""))
            items.append(("2", "768x768", ""))
            items.append(("3", "1024x1024", ""))
            items.append(("4", "1280x1280", ""))
            items.append(("5", "1536x1536", ""))
            items.append(("6", "1792x1792", ""))
            
        return items
    
    size_class: bpy.props.EnumProperty(
        name="Lightmap Resolution",
        items=size_class_items
    )
    
    def refinement_size_class_items(self, context):
        items=[
            ("0", "4096x1024", ""),
            ("1", "1024x1024", ""),
            ("2", "2048x1024", ""),
            ("3", "6144x1024", ""),
        ]
        
        return items
    
    refinement_size_class: bpy.props.EnumProperty(
        name="Lightmap Refinement",
        items=refinement_size_class_items,
    )
    
    @classmethod
    def poll(cls, context):
        return poll_ui(('scenario',)) and valid_nwo_asset(context)
        
    def execute(self, context):
        self.info = None
        nwo = get_scene_props()
        bsp = nwo.regions_table[nwo.regions_table_active_index].name
        with ScenarioTag() as scenario:
            success = scenario.set_bsp_lightmap_res(bsp, int(self.size_class), int(self.refinement_size_class))
            if not success:
                self.report({'WARNING'}, f"BSP {bsp} does not exist in scenario tag. You may need to export this scene")
                return {'CANCELLED'}
        
        if is_corinth(context):
            self.report({'INFO'}, f"Set lightmap resolution of {self.size_class_items(context)[int(self.size_class)][1]} and refinement class of {self.refinement_size_class_items(context)[int(self.refinement_size_class)][1]}")
        else:
            self.report({'INFO'}, f"Set lightmap resolution of {self.size_class}")
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "size_class", text="Resolution")
        if is_corinth(context):
            layout.prop(self, "refinement_size_class", text="Refinement")
            
def unhide_objects(objects, nwo, collection_map):
    regions_table = nwo.regions_table
    permutations_table = nwo.permutations_table

    # Only unhide objects if both region and permutation are set to unhidden
    for ob in objects:
        region = None
        permutation = None
        ecoll = collection_map.get(ob.nwo.export_collection)
        if ecoll:
            region = ecoll.region
            permutation = ecoll.permutation
        if not region:
            region = ob.nwo.region_name
        if not permutation:
            permutation = ob.nwo.permutation_name  

        if get_entry(regions_table, region).hidden or get_entry(permutations_table, permutation).hidden:
            continue
        if ob.type == 'LIGHT' and not nwo.connected_geometry_object_type_light_visible:
            continue
        elif is_frame(ob) and not nwo.connected_geometry_object_type_frame_visible:
            continue
        elif is_marker(ob) and not getattr(nwo, f"{ob.nwo.marker_type[1:]}_visible"):
            continue
        elif is_mesh(ob) and not getattr(nwo, f"{ob.data.nwo.mesh_type[1:]}_visible"):
            continue
        
        ob.hide_set(False)
            
class NWO_OT_HideObjectType(bpy.types.Operator):
    bl_idname = "nwo.hide_object_type"
    bl_label = "Hide Object Type"
    bl_description = "Hides/Unhides an object type"
    bl_options = {"UNDO", "INTERNAL"}
    
    object_type: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        collection_map = create_parent_mapping(context)
        nwo = get_scene_props()
        visible_str = f"{self.object_type[1:]}_visible"
        valid_objects = objects_by_type(context, self.object_type)
        if valid_objects:
            if getattr(nwo, visible_str):
                unhide_objects(valid_objects, nwo, collection_map)
            else:
                for ob in valid_objects:
                    ob.hide_set(True)
            
        return {"FINISHED"}
    
def objects_by_type(context: bpy.types.Context, object_type: str) -> list[bpy.types.Object]:
    if object_type == '_connected_geometry_object_type_light':
        return [ob for ob in context.view_layer.objects if ob.type == 'LIGHT']
    elif object_type == '_connected_geometry_object_type_frame':
        return [ob for ob in context.view_layer.objects if is_frame(ob)]
    elif object_type.startswith("_connected_geometry_marker_type"):
        return [ob for ob in context.view_layer.objects if is_marker(ob) and ob.nwo.marker_type == object_type]
    elif object_type.startswith("_connected_geometry_mesh_type"):
        return [ob for ob in context.view_layer.objects if is_mesh(ob) and ob.data.nwo.mesh_type == object_type]
