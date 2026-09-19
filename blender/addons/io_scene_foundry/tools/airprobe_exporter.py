import time
import types

import bpy

from .. import utils
from ..tags.scenario import ScenarioMetadataTag


AIRPROBE_MARKER_TYPE = "_connected_geometry_marker_type_airprobe"


class NWO_OT_ExportAirprobes(bpy.types.Operator):
    bl_idname = "nwo.export_airprobes"
    bl_label = "Export Airprobes"
    bl_description = "Exports all airprobes"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context) and not utils.is_corinth(context)

    def execute(self, context):
        current_selection = context.selected_objects[:]
        current_object = context.object
        export_airprobes()
        for ob in current_selection:
            ob.select_set(True)
        context.view_layer.objects.active = current_object
        return {"FINISHED"}


def gather_airprobes(context):
    print("--- Start airprobe gather")
    start = time.perf_counter()

    collection_map = utils.create_parent_mapping(context)
    proxies = []
    with utils.DepsgraphRead():
        depsgraph = context.evaluated_depsgraph_get()

        for inst in depsgraph.object_instances:
            obj = inst.object
            original = obj.original
            nwo = original.nwo
            parent = original

            if inst.is_instance:
                obj = inst.instance_object
                original = obj.original
                nwo = original.nwo
                parent = inst.parent

            if not (original.type == "EMPTY" and nwo.marker_type == AIRPROBE_MARKER_TYPE):
                continue

            if utils.ignore_for_export_fast(original, collection_map, parent):
                continue

            proxy = types.SimpleNamespace()
            proxy.name = original.name
            proxy.type = "EMPTY"
            proxy.nwo = nwo
            proxy.matrix_world = inst.matrix_world.copy()
            proxies.append(proxy)

    print(len(proxies), "airprobes found")
    print("--- Gathered airprobes in: {:.3f}s".format(time.perf_counter() - start))

    return proxies


def _airprobe_items(airprobe_objects):
    if hasattr(airprobe_objects, "items"):
        return airprobe_objects.items()

    return [(ob, ob.name) for ob in airprobe_objects]


def _write_airprobes(scenario, airprobe_objects):
    root = scenario.tag.root()
    airprobes = scenario.block(root, 'airprobes')
    airprobes.clear()
    items = list(_airprobe_items(airprobe_objects))
    if len(items) > 512:
        utils.print_warning(f"More than 512 airprobes found [Total {len(items)}]. Exported first 512 only")
    for ob, name in items[:512]:
        index = airprobes.add()
        airprobes = scenario.block(root, 'airprobes')
        element = airprobes[index]
        matrix = utils.halo_transforms_matrix(ob.matrix_world)
        position = scenario.required_field(element, 'airprobe position')
        position.set(type(position.value)(*matrix.translation))
        scenario.required_field(element, 'airprobe name').set(utils.clean_text(name))
        scenario.tag_has_changes = True


def export_airprobes(airprobe_objects=None):
    scenario_path = utils.get_asset_tag(".scenario", True)
    if airprobe_objects is None:
        airprobe_objects = gather_airprobes(bpy.context)

    print("--- Writing airprobes to Tag")
    start = time.perf_counter()
    with ScenarioMetadataTag(path=scenario_path) as scenario:
        _write_airprobes(scenario, airprobe_objects)

    print("--- Completed airprobes tag write in", utils.human_time(time.perf_counter() - start, True))
