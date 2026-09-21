from pathlib import Path
import addon_utils
from bpy.app.handlers import persistent
import bpy

from .tools.light_exporter import export_lights
from .tools.prefab_exporter import export_prefabs
from .tools.decorator_exporter import export_decorators
from .tools.airprobe_exporter import export_airprobes

from . import utils

# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------

load_handler_complete = False
_subscription_owner = None  # prevent msgbus GC


# -----------------------------------------------------------------------------
# MsgBus
# -----------------------------------------------------------------------------

def msgbus_callback(context):
    try:
        ob = context.object
        if ob and context.mode == "EDIT_MESH":
            highlight = ob.data.nwo.highlight
            if highlight:
                bpy.ops.nwo.face_attribute_color_all(enable_highlight=highlight)
    except Exception:
        pass


def subscribe(owner):
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.Object, "mode"),
        owner=owner,
        args=(bpy.context,),
        notify=msgbus_callback,
        options={"PERSISTENT"},
    )


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------

def load_projects():
    """Reload persisted projects and ensure the current scene selects one."""
    projects = utils.setup_projects_list()
    if not getattr(bpy.context, "scene", None):
        return projects

    nwo = utils.get_scene_props()
    blend_path = bpy.data.filepath
    project_names = [p.name for p in projects]

    if projects and (not nwo.scene_project or nwo.scene_project not in project_names):
        if blend_path:
            for project in projects:
                if Path(blend_path).is_relative_to(project.project_path):
                    nwo.scene_project = project.name
                    break
            else:
                nwo.scene_project = projects[0].name
        else:
            nwo.scene_project = projects[0].name

    return projects

@persistent
def load_set_output_state(dummy):
    utils.get_export_props().show_output = utils.foundry_output_state


@persistent
def import_handler(import_context):
    """Handles adding region / permutations and instance proxies"""

    proxies = []

    for item in import_context.import_items:
        id = item.id
        if id is None or id.id_type is None:
            continue

        match id.id_type:
            case 'OBJECT':
                if id.nwo.region_name:
                    utils.add_region(id.nwo.region_name)
                if id.nwo.permutation_name:
                    utils.add_permutation(id.nwo.permutation_name)

                if id.type == 'MESH':
                    for prop in id.data.nwo.face_props:
                        if prop.type == 'region' and prop.region_name:
                            utils.add_region(prop.region_name)

                    if id.nwo.proxy_type:
                        proxies.append(id)

            case 'COLLECTION':
                match id.nwo.type:
                    case 'region':
                        if id.nwo.region:
                            utils.add_region(id.nwo.region)
                    case 'permutation':
                        if id.nwo.permutation:
                            utils.add_permutation(id.nwo.permutation)

    if proxies:
        for ob in proxies:
            utils.unlink(ob)


@persistent
def load_handler(dummy):
    """Main scene initialization on file load"""

    global load_handler_complete, _subscription_owner

    context = bpy.context
    nwo = utils.get_scene_props()

    if not nwo.is_main_scene:
        nwo.is_main_scene = True

    nwo.export_in_progress = False
    nwo.camera_sync_active = False

    load_projects()

    # -------------------------------------------------------------------------
    # Resolve module reference
    # -------------------------------------------------------------------------

    module_name = bpy.context.preferences.addons[__package__].module
    for m in addon_utils.modules():
        if m.__name__ == module_name:
            utils.module = m
            break

    # -------------------------------------------------------------------------
    # Ensure default tables
    # -------------------------------------------------------------------------

    if not nwo.regions_table:
        r = nwo.regions_table.add()
        r.old = "default"
        r.name = "default"

    if not nwo.permutations_table:
        p = nwo.permutations_table.add()
        p.old = "default"
        p.name = "default"

    if not nwo.cinematic_scenes:
        c = nwo.cinematic_scenes.add()
        c.name = "default"
        c.scene = nwo.id_data

    # -------------------------------------------------------------------------
    # Runtime-only logic (skip in background)
    # -------------------------------------------------------------------------

    if not bpy.app.background:

        # Cleanup proxy leftovers
        if nwo.instance_proxy_running:
            for ob in context.view_layer.objects:
                if ob.nwo.proxy_type:
                    utils.unlink(ob)

        nwo.instance_proxy_running = False

        # Msgbus subscription (persistent owner)
        if _subscription_owner is None:
            _subscription_owner = object()
            subscribe(_subscription_owner)

    load_handler_complete = True


@persistent
def save_object_positions_to_tags(dummy):
    if not bpy.context or not bpy.context.scene:
        return

    nwo = utils.get_scene_props()
    if not utils.valid_nwo_asset():
        return

    asset_type = nwo.asset_type

    if nwo.prefabs_export_on_save and asset_type == 'scenario' and utils.is_corinth():
        print("Exporting Prefabs")
        export_prefabs()

    if nwo.lights_export_on_save and asset_type == 'scenario':
        print("Exporting Lights")
        export_lights(*utils.get_asset_info())

    if (
        nwo.decorators_export_on_save
        and asset_type == 'scenario'
        and nwo.decorators_from_blender
    ):
        print("Exporting Decorators")
        export_decorators(utils.is_corinth(bpy.context))

    if (
        nwo.airprobes_export_on_save
        and asset_type == 'scenario'
        and nwo.airprobes_from_blender
        and not utils.is_corinth()
    ):
        print("Exporting Airprobes")
        export_airprobes()
