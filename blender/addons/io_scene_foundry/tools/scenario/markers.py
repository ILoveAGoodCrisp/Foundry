"""Blender transforms and native options for authored scenario markers."""
from ... import utils
from ...tags.scenario import ScenarioDocument, ScenarioMarkerPlacement
from ...tags.scenario_markers import PLAYER_FIELDS, block_fields, MARKER_PREFIX
from .targets import scenario_targets


def gather_camera_points(context):
    from types import SimpleNamespace
    cameras = []
    collection_map = utils.create_parent_mapping(context)
    with utils.DepsgraphRead():
        for instance in context.evaluated_depsgraph_get().object_instances:
            evaluated = instance.instance_object if instance.is_instance else instance.object
            original = evaluated.original
            parent = instance.parent if instance.is_instance else original
            if original.type != 'CAMERA' or utils.ignore_for_export_fast(original, collection_map, parent):
                continue
            cameras.append(SimpleNamespace(name=original.name, nwo=original.nwo, data=evaluated.data,
                matrix_world=instance.matrix_world.copy()))
    return cameras


def camera_point_placement(camera):
    from ...tags.camera_track import camera_correction_matrix
    from ...tags.scenario import ScenarioCameraPoint
    matrix = utils.halo_transforms_matrix(camera.matrix_world)
    position, rotation, _ = matrix.decompose()
    # Match CameraTrackTag.to_tag: Blender looks down local -Z, with +Y up.
    orientation = (rotation.to_matrix() @ camera_correction_matrix.inverted_safe()).to_euler('ZYX')
    nwo = camera.nwo
    return ScenarioCameraPoint(nwo.camera_point_name.strip() or camera.name, tuple(position),
        (orientation.z, -orientation.y, orientation.x), camera.data.angle,
        int(nwo.camera_point_type), nwo.camera_point_edit_as_relative, nwo.camera_point_zone_set)


def export_camera_points(camera_objects=None, *, context=None, scenario_path=None, tags_root=None, game=None):
    import bpy
    settings = utils.get_scene_props()
    if not settings.camera_points_from_blender:
        return 0
    if camera_objects is None:
        camera_objects = gather_camera_points(context or bpy.context)
    game = game or utils.get_project(settings.scene_project).game
    count = 0
    with scenario_targets(camera_objects, scenario_path=scenario_path or utils.get_asset_tag('.scenario', True),
            tags_root=tags_root or utils.get_tags_path(), game=game, include_existing_children=True) as targets:
        for scenario, cameras in targets:
            points = [camera_point_placement(camera) for camera in cameras]
            scenario.replace_camera_points(points)
            count += len(points)
    return count


def marker_placement(ob, game):
    matrix = utils.halo_transforms_matrix(ob.matrix_world, marker=True)
    euler = matrix.to_euler('ZYX')
    rotation = (euler.z, -euler.y, euler.x)
    nwo = ob.nwo
    if nwo.marker_type == MARKER_PREFIX + 'player_start':
        fields = block_fields(game, 'player starting locations')
        options = {field: getattr(nwo, prop) if field == 'editor folder' else int(getattr(nwo, prop))
                   for prop, field in PLAYER_FIELDS.items() if field in fields}
        if 'flags' in fields:
            options['flags'] = int(nwo.player_start_survival) | (int(nwo.player_start_survival_elite) << 1 if game != 'halo3odst' else 0)
        name = ob.name
    else:
        fields = block_fields(game, 'cutscene flags')
        options = {field: getattr(nwo, prop) for prop, field in
                   (('scenario_editor_folder', 'editor folder'), ('cutscene_flag_source_bsp', 'source bsp')) if field in fields}
        name = nwo.cutscene_flag_name.strip() or ob.name
    return ScenarioMarkerPlacement(name, tuple(matrix.translation), rotation, options)


def export_scenario_markers(objects, *, scenario_path, tags_root, game, clear_player_starts=False):
    starts = [marker_placement(ob, game) for ob in objects if ob.nwo.marker_type == MARKER_PREFIX + 'player_start']
    flags = [marker_placement(ob, game) for ob in objects if ob.nwo.marker_type == MARKER_PREFIX + 'cutscene_flag']
    if not starts and not flags and not clear_player_starts:
        return
    with scenario_targets(objects, scenario_path=scenario_path, tags_root=tags_root, game=game,
            include_existing_children=True) as targets:
        for scenario, objects_ in targets:
            starts_ = [marker_placement(ob, game) for ob in objects_ if ob.nwo.marker_type == MARKER_PREFIX + 'player_start']
            flags_ = [marker_placement(ob, game) for ob in objects_ if ob.nwo.marker_type == MARKER_PREFIX + 'cutscene_flag']
            if starts or clear_player_starts:
                scenario.write_marker_placements('player starting locations', starts_)
            if flags_:
                scenario.write_marker_placements('cutscene flags', flags_)


def markers_to_blender(scenario, collection, bvh=None, bsp_indices=None):
    import bpy
    from mathutils import Euler, Matrix, Vector
    from ... import import_transform

    objects = []
    for block, kind in (('player starting locations', 'player_start'), ('cutscene flags', 'cutscene_flag')):
        for placement in scenario.marker_placements(block):
            bsp = placement.options.get('bsp index', placement.options.get('source bsp', -1))
            if bsp_indices is not None and bsp >= 0 and bsp not in bsp_indices:
                continue
            position = Vector(placement.position) * 100
            if bsp < 0 and bvh and not utils.test_point_bvh(bvh, position):
                continue
            ob = bpy.data.objects.new(placement.name, None)
            ob.empty_display_type = 'ARROWS'
            yaw, pitch, roll = placement.rotation
            ob.matrix_world = import_transform.marker_matrix(Matrix.LocRotScale(
                position, Euler((roll, -pitch, yaw), 'ZYX'), Vector.Fill(3, 1)))
            ob.nwo.marker_type = MARKER_PREFIX + kind
            for prop, field in PLAYER_FIELDS.items():
                if field in placement.options:
                    value = placement.options[field]
                    if 'enum' in block_fields(scenario.game, block)[field]['type']:
                        value = str(value)
                    setattr(ob.nwo, prop, value)
            if kind == 'cutscene_flag':
                ob.nwo.cutscene_flag_name = placement.name
                ob.nwo.cutscene_flag_source_bsp = placement.options.get('source bsp', -1)
            else:
                flags = placement.options.get('flags', 0)
                ob.nwo.player_start_survival = bool(flags & 1)
                ob.nwo.player_start_survival_elite = bool(flags & 2)
            collection.objects.link(ob)
            objects.append(ob)
    return objects


def camera_points_to_blender(scenario, collection):
    import bpy
    from math import pi
    from mathutils import Euler, Matrix, Vector
    from ... import import_transform
    from ...tags.camera_track import camera_correction_matrix

    objects = []
    for point in scenario.camera_points():
        data = bpy.data.cameras.new(point.name)
        data.sensor_fit = 'HORIZONTAL'
        if 0 < point.field_of_view < pi:
            data.angle = point.field_of_view
        camera = bpy.data.objects.new(point.name, data)
        yaw, pitch, roll = point.orientation
        rotation = Euler((roll, -pitch, yaw), 'ZYX').to_matrix() @ camera_correction_matrix
        camera.matrix_world = import_transform.object_matrix(Matrix.LocRotScale(
            Vector(point.position) * 100, rotation.to_quaternion(), Vector.Fill(3, 1)))
        camera.nwo.camera_point_name = point.name
        camera.nwo.camera_point_type = str(point.camera_type)
        camera.nwo.camera_point_edit_as_relative = point.edit_as_relative
        camera.nwo.camera_point_zone_set = point.zone_set_index
        collection.objects.link(camera)
        objects.append(camera)
    return objects


def airprobes_to_blender(scenario, collection):
    import bpy
    from mathutils import Matrix, Vector
    from ... import import_transform

    field = scenario.tag.root().field('airprobes')
    if field is None:
        return []
    objects = []
    for row in field.as_block():
        ob = bpy.data.objects.new(str(scenario.value(row, 'airprobe name')), None)
        ob.empty_display_type = 'SPHERE'
        ob.empty_display_size = import_transform.distance(.1)
        ob.nwo.marker_type = MARKER_PREFIX + 'airprobe'
        position = Vector(scenario.value(row, 'airprobe position').to_array()) * 100
        ob.matrix_world = import_transform.marker_matrix(Matrix.Translation(position))
        collection.objects.link(ob)
        objects.append(ob)
    return objects
