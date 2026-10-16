"""File-menu interchange exports, independent of asset paths and tag processing.

Reuse Foundry's evaluated geometry and format adapters, but never run the asset
coordinator, create sidecars, prune intermediates or invoke editing-kit tools.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import traceback

import bpy
from mathutils import Matrix
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from .. import utils
from ..coordinate_system import CoordinateSystem
from ..exceptions import ExportCancelled
from ..granny_export import ExportBackend, build_export_file, write_minimal_file
from ..granny_export.adapter import numeric_buffer
from ..granny_export.model import Animation, SampledCurve, TrackGroup, TransformTrack
from ..legacy.writers import VERSIONS, legacy_bone_order
from ..tools.asset_types import AssetType
from .legacy import LegacyExportScene, write_outputs
from .export_info import ObjectType, MeshType
from .virtual_geometry import VirtualAnimation, VirtualScene
from .pointcloud import is_decorator_geometry, prepare_pointcloud_proxy
from ..constants import GENERAL_OBJECTS


ANIMATION_FORMATS = (
    ('jma', 'JMA — XY movement', 'Base animation with XY root movement'),
    ('jmm', 'JMM — No movement', 'Base animation without root movement'),
    ('jmt', 'JMT — XY and yaw', 'Base animation with XY movement and yaw'),
    ('jmz', 'JMZ — XYZ and yaw', 'Base animation with XYZ movement and yaw'),
    ('jmo', 'JMO — Overlay', 'Overlay animation'),
    ('jmr', 'JMR — Replacement', 'Replacement animation'),
    ('jmw', 'JMW — World', 'World-space animation'),
    ('jmv', 'JMV — Vehicle', 'Vehicle animation'),
    ('jmh', 'JMH — World relative', 'World-relative animation'),
)


class SettingsView:
    """Local overrides keep export options out of the saved asset settings."""
    def __init__(self, source, **overrides):
        self._source = source
        self.__dict__.update(overrides)

    def __getattr__(self, name):
        return getattr(self._source, name)


def project_versions(context):
    project = utils.get_project(context.scene.nwo.scene_project)
    versions = VERSIONS.get(project.game if project else '', (8213, 7, 16395))
    return versions[0], versions[1] or 7, versions[2]


def export_objects(context, options):
    """Intersect the file-browser scope filters before preparation unhides objects."""
    collection = context.view_layer.active_layer_collection.collection
    collection_objects = set(collection.all_objects) if options.use_active_collection else None
    return {
        ob for ob in context.view_layer.objects
        if (not options.use_selection or ob.select_get())
        and (not options.use_visible or ob.visible_get(view_layer=context.view_layer))
        and (collection_objects is None or ob in collection_objects)
        and ob.type in GENERAL_OBJECTS | {'ARMATURE'}
    }


class StandaloneScene(LegacyExportScene):
    def __init__(self, context, filepath, options, objects):
        # Deliberately do not call either asset-export constructor: those require
        # a project, change the working directory and initialize asset sidecars.
        self.context = context
        self.asset_name = filepath.stem
        self.asset_path = filepath.parent
        self.asset_path_relative = ''
        self.sidecar = None
        self.sidecar_path = ''
        project = utils.get_project(context.scene.nwo.scene_project)
        self.project_game = project.game if project else 'reach'
        self.corinth = self.project_game in {'halo4', 'halo2a'}
        self.game_version = 'corinth' if self.corinth else 'reach'
        self.legacy_export = options.format != 'gr2'
        self.export_backend = ExportBackend.LEGACY if self.legacy_export else ExportBackend.PYTHON
        self.granny = None
        self.tags_dir = Path(utils.get_tags_path() or filepath.parent)
        self.data_dir = Path(utils.get_data_path() or filepath.parent)
        self.halo_metadata = options.format != 'gr2' or options.halo_metadata
        scene_nwo = context.scene.nwo
        regions = list(scene_nwo.regions_table) or [SimpleNamespace(name='default')]
        permutations = list(scene_nwo.permutations_table) or [SimpleNamespace(name='default')]
        self.scene_settings = SettingsView(scene_nwo, regions_table=regions,
            permutations_table=permutations, animations=(), active_animation_index=-1,
            is_child_asset=False)
        self.export_settings = SettingsView(context.scene.nwo_export,
            export_render=True, export_collision=True, export_physics=True,
            export_markers=True, export_skeleton=True, export_structure=True,
            export_design=True, export_all_permutations=True, lightmap_all_bsps=True,
            granny_mirror=False, disable_automatic_suspension_computation=True)
        self.asset_type = (AssetType.SCENARIO if scene_nwo.asset_type in {'scenario', 'prefab', 'multi_prefab'}
                           and options.format in {'jms', 'ass'} else AssetType.MODEL)
        self.supports_bsp = self.asset_type.supports_bsp
        self.is_model = not self.supports_bsp
        self.uses_main_armature = True
        self.type_is_relevant = self.halo_metadata
        self.default_region = regions[0].name
        self.default_permutation = permutations[0].name
        self.reg_name = 'BSP' if self.supports_bsp else 'region'
        self.perm_name = 'layer' if self.supports_bsp else 'permutation'
        self.export_tag_types = {'render', 'collision', 'physics', 'markers', 'skeleton', 'structure', 'design', 'animation'}
        self.limit_perms_to_selection = self.limit_bsps_to_selection = False
        self.selected_cinematic_objects_only = False
        self.granny_textures = self.granny_open = self.granny_animations_mesh = False
        self.forward = scene_nwo.forward_direction
        convention = CoordinateSystem.from_scene(scene_nwo)
        self.to_halo_scale = convention.to_halo_scale if options.convert_scale else 1.
        self.from_halo_scale = 1 / self.to_halo_scale
        self.to_maya_scale = self.to_halo_scale / 10 if self.corinth else self.to_halo_scale
        self.rotation_correction = convention.to_halo_rotation if options.convert_forward else 0.
        self.halo_transform_scale = convention.to_world_scale if options.convert_scale else 1.
        self.unit_factor = convention.meters_per_unit
        self.atten_scalar = 1 if self.corinth else 100
        self.mirror = False
        self.has_animations = False
        self.objects = objects
        self.jms_version, self.ass_version, self.jma_version = project_versions(context)
        if self.legacy_export:
            setattr(self, options.format + '_version', options.version)
        self.target_game = ('halo1' if (options.format == 'jms' and self.jms_version < 8205)
                            or (options.format == 'jma' and self.jma_version < 16394)
                            else 'halo2' if (options.format == 'jms' and self.jms_version < 8211)
                            or (options.format == 'ass' and self.ass_version < 3) else 'halo3')
        if self.legacy_export:
            self.project_game = self.target_game
            self.corinth = False
            self.game_version = 'reach'
            self.to_maya_scale = self.to_halo_scale
        self.warned_shader_paths = set()
        self.shader_name_cache = {}
        self.halo1_two_sided_shaders = set()
        self.new_scene('standalone')
        self.original_subframe = context.scene.frame_subframe
        self.collection_properties = {}

    def ready_scene(self):
        utils.set_object_mode(self.context)
        # Only unhide included objects and their skeleton dependencies.
        dependencies = set(self.objects)
        for ob in self.objects:
            parent = ob.parent
            while parent is not None:
                if parent.type in {'ARMATURE', 'EMPTY'}:
                    dependencies.add(parent)
                parent = parent.parent
            for modifier in ob.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object is not None:
                    dependencies.add(modifier.object)
        self.objects = dependencies
        rigs = [ob for ob in dependencies if ob.type == 'ARMATURE']
        active = self.context.view_layer.objects.active
        self.main_armature = (active if active in rigs else
            self.scene_settings.main_armature if self.scene_settings.main_armature in rigs else
            next(iter(sorted(rigs, key=lambda ob: ob.name)), None))
        self.scene_settings.main_armature = self.main_armature
        for ob in dependencies:
            self.collection_properties[ob] = (ob.nwo.collection_region, ob.nwo.collection_permutation)
            hidden, viewport_hidden = ob.hide_get(), ob.hide_viewport
            if hidden or viewport_hidden:
                self.hidden_objects[ob] = hidden, viewport_hidden
                ob.hide_set(False)
                ob.hide_viewport = False
            if ob.type == 'ARMATURE':
                self.armature_poses[ob.data] = ob.data.pose_position
                ob.data.pose_position = 'REST'
            for modifier in ob.modifiers:
                if modifier.type == 'ARMATURE' and modifier.show_viewport:
                    self.legacy_armature_modifiers.append(modifier)
                    modifier.show_viewport = False
        self.context.view_layer.update()

    def get_initial_export_objects(self):
        self.collection_map = utils.create_parent_mapping(self.context)
        self.depsgraph = self.context.evaluated_depsgraph_get()
        self.export_objects = []
        pointcloud_meshes = {}
        preview_sources = utils.decorator_preview_sources()
        for inst in self.depsgraph.object_instances:
            original = inst.object.original
            scope_object = inst.parent.original if inst.is_instance else original
            if scope_object not in self.objects:
                continue
            if is_decorator_geometry(inst, preview_sources):
                continue
            if inst.is_instance:
                original = inst.instance_object.original
            if original.type == 'ARMATURE':
                if original not in self.export_objects:
                    self.export_objects.append(original)
                continue
            if original.type not in GENERAL_OBJECTS:
                continue
            if original.is_instancer and original.instance_collection and not original.nwo.marker_instance:
                continue
            proxy = utils.ExportObject()
            for name in ('name', 'type', 'nwo', 'data', 'parent', 'parent_type', 'parent_bone',
                         'material_slots', 'vertex_groups', 'empty_display_type', 'pose', 'empty_display_size'):
                setattr(proxy, name, getattr(original, name))
            proxy.ob = original
            proxy.matrix_world = inst.matrix_world.copy()
            proxy.eval_ob = inst.instance_object if inst.is_instance else inst.object
            proxy.modifiers = tuple(proxy.eval_ob.modifiers)
            if original.type == 'POINTCLOUD' and not prepare_pointcloud_proxy(
                    proxy, inst.object, pointcloud_meshes, self.temp_meshes):
                continue
            self.collection_properties.setdefault(original,
                (original.nwo.collection_region, original.nwo.collection_permutation))
            original.nwo.collection_region = ''
            original.nwo.collection_permutation = ''
            collection = self.collection_map.get(original.nwo.export_collection)
            if collection is not None:
                original.nwo.collection_region = collection.region or ''
                original.nwo.collection_permutation = collection.permutation or ''
                proxy.collection_region = collection.region or ''
            self.export_objects.append(proxy)
        self.virtual_scene = VirtualScene(self.asset_type, self.depsgraph, self.corinth,
            self.tags_dir, None, self.export_settings, utils.time_step(), self.rotation_correction,
            False, SimpleNamespace(game=self.project_game), self.to_halo_scale, self.unit_factor,
            self.atten_scalar, self.context, self.halo_transform_scale, self.scene_settings,
            export_backend=self.export_backend)
        self.virtual_scene.halo_metadata = self.halo_metadata
        self.has_no_virtual_scene = False

    def get_halo_props(self, ob):
        if self.halo_metadata:
            return super().get_halo_props(ob)
        # Internal classification is needed by VirtualScene, but is never
        # serialized when halo_metadata is disabled in the GR2 adapter.
        kind = ObjectType.frame.value if ob.type == 'ARMATURE' or (ob.type == 'EMPTY' and ob.nwo.is_frame) else ObjectType.marker.value if ob.type == 'EMPTY' else ObjectType.mesh.value
        props = {'bungie_object_type': kind}
        mesh_props = {'bungie_mesh_type': MeshType.default.value} if kind == ObjectType.mesh.value else {}
        return props, self.default_region, self.default_permutation, mesh_props, None, False, False

    def create_virtual_tree(self):
        # Resolve wrapper parents so an excluded mesh cannot bring in its children.
        # Keep the hierarchy for independent armatures instead of attaching every
        # object to the scene's main rig.
        wrappers = {getattr(ob, 'ob', ob): ob for ob in self.ob_halo_data}
        parents = {}
        for ob in self.ob_halo_data:
            parent = wrappers.get(ob.parent)
            if parent is None and self.main_armature in wrappers and ob.type != 'ARMATURE':
                parent = self.main_armature
            if parent is not None:
                parents[ob] = parent
        self.virtual_scene.object_parent_dict = parents
        for ob in self.ob_halo_data:
            if ob not in parents:
                self.virtual_scene.add_model(ob)
        if not self.halo_metadata:
            for model in self.virtual_scene.models.values():
                if model.ob.type == 'ARMATURE':
                    model.name = model.node.name = model.skeleton.name = model.ob.name
                    model.skeleton.bones[0].name = model.ob.name
        if self.corinth and self.halo_metadata:
            self.virtual_scene.build_corinth_physics_subshapes()
        skeleton = self.virtual_scene.skeleton_model
        self.bones = [b for b in skeleton.skeleton.bones if isinstance(b.bone, bpy.types.PoseBone)] if skeleton else []
        parents_by_name = {b.name: skeleton.skeleton.bones[b.parent_index].name if b.parent_index >= 0 else None
                           for b in self.bones}
        by_name = {b.name: b for b in self.bones}
        self.bones = [by_name[name] for name in legacy_bone_order(parents_by_name)]
        self.bone_index = {b.name: i for i, b in enumerate(self.bones)}
        self.bone_parents = {name: self.bone_index.get(parent, -1) for name, parent in parents_by_name.items()}
        self.bone_world = {b.name: b.matrix_world for b in self.bones}

    def legacy_shader_name(self, material):
        # File exports do not require a tags directory or modify shader collections.
        name = getattr(material, 'legacy_shader_name', '') or material.name
        path = getattr(material, 'shader_path', '')
        if (self.target_game == 'halo1' and not name.startswith('+')
                and (not path.strip() or path in {'override', 'shaders\\invalid'})):
            return 'invalid'
        return name

    def sample_loaded_animation(self, options):
        if not self.virtual_scene.skeleton_model or not self.bones:
            raise ExportCancelled('Animation export requires an included armature with exportable bones')
        for armature in self.armature_poses:
            armature.pose_position = 'POSE'
        self.context.view_layer.update()
        extension = getattr(options, 'animation_format', 'jma')
        animation = SimpleNamespace(name=self.asset_name, frame_start=self.context.scene.frame_start,
            frame_end=self.context.scene.frame_end, compression='Medium',
            animation_type='overlay' if extension == 'jmo' else 'replacement' if extension == 'jmr' else 'base',
            animation_movement_data={'jmm': 'none', 'jmt': 'xyyaw', 'jmz': 'xyzyaw'}.get(extension, 'xy'),
            animation_space='world' if extension in {'jmw', 'jmh'} else 'object',
            animation_events=(), animation_nodes=(), pose_overlay=False)
        return VirtualAnimation(animation, self.virtual_scene, True)

    def sample_gr2_animation(self):
        """Sample the assigned actions together, including object transforms.

        Each model gets a track group, so independent rigs may reuse bone names.
        Object models animate relative to their initial model placement; skeletal
        models retain the identity wrapper used by Foundry's GR2 representation.
        """
        for armature in self.armature_poses:
            armature.pose_position = 'POSE'
        start, end = self.context.scene.frame_start, self.context.scene.frame_end
        frame_count = utils.game_frame(end - start + 1)
        groups = []
        for model in self.virtual_scene.models.values():
            bones = model.skeleton.bones
            tracks = {bone.name: ([], [], []) for bone in bones}
            base = model.node.matrix_local.inverted_safe() if model.ob.type != 'ARMATURE' else Matrix.Identity(4)
            for index in range(frame_count):
                frame = start + (end - start) * index / max(1, frame_count - 1)
                self.context.scene.frame_set(int(frame), subframe=frame - int(frame))
                depsgraph = self.context.evaluated_depsgraph_get()
                world = []
                for bone in bones:
                    source = bone.bone
                    if bone is bones[0] and model.ob.type == 'ARMATURE':
                        matrix = Matrix.Identity(4)
                    elif isinstance(source, bpy.types.PoseBone):
                        armature = source.id_data.evaluated_get(depsgraph)
                        matrix = self.virtual_scene.rotation_matrix @ armature.matrix_world @ armature.pose.bones[source.name].matrix
                    else:
                        raw = getattr(source, 'ob', source)
                        matrix = base @ self.virtual_scene.rotation_matrix @ raw.evaluated_get(depsgraph).matrix_world
                    world.append(matrix)
                for bone, matrix in zip(bones, world):
                    if bone.parent_index != -1:
                        matrix = world[bone.parent_index].inverted_safe() @ matrix
                    loc, rot, scale = matrix.decompose()
                    positions, rotations, scales = tracks[bone.name]
                    positions.extend(loc)
                    rotations.extend((rot.x, rot.y, rot.z, rot.w))
                    scales.extend((scale.x, 0., 0., 0., scale.y, 0., 0., 0., scale.z))
            transforms = tuple(TransformTrack(name, *(SampledCurve(numeric_buffer(values, width=width))
                for values, width in zip(tracks[name], (3, 4, 9)))) for name in sorted(tracks))
            groups.append(TrackGroup(model.node.name, transforms))
        dt = self.virtual_scene.time_step
        return Animation(self.asset_name, dt * (frame_count - 1) + .00001, dt, tuple(groups))

    def write_file(self, filepath, options):
        nodes = list(self.virtual_scene.nodes.values())
        geometry = [node for node in nodes if node.mesh is not None]
        markers = [node for node in nodes if node.tag_type == 'markers']
        ass_regions = (self.lightmap_regions if self.target_game in {'halo3', 'halo3odst'} else ())
        if not nodes and not (options.format == 'ass' and (self.lights or ass_regions)):
            raise ExportCancelled('No exportable objects in the chosen scope')
        if options.format == 'jms':
            asset = self.jms_asset(filepath.stem, geometry, markers,
                'structure' if self.supports_bsp else 'render', include_physics=True, filter_markers=False)
        elif options.format == 'ass':
            asset = self.ass_asset(filepath.stem, geometry, markers, self.lights,
                                   lightmap_regions=ass_regions,
                                   filter_region=False, filter_markers=False)
        elif options.format == 'jma':
            asset = self.jma_text(self.sample_loaded_animation(options))
        else:
            data = build_export_file(self.virtual_scene, self.virtual_scene.nodes,
                export_info=self.export_info, file_name=str(filepath), art_tool_version=bpy.app.version,
                exporter_version=utils.get_version(), scale=self.from_halo_scale,
                halo_metadata=self.halo_metadata)
            if options.include_animation:
                sampled = self.sample_gr2_animation()
                data = replace(data, animations=(sampled,), track_groups=sampled.track_groups)
            # VirtualScene applies scene forward rotation; the writer finishes
            # the format's unit and basis conversion.
            conversion = data.conversion
            if not options.convert_scale:
                conversion = replace(conversion, target_units_per_meter=data.art_tool.units_per_meter)
            if not options.convert_forward:
                conversion = replace(conversion, right=data.art_tool.right,
                                     up=data.art_tool.up, back=data.art_tool.back)
            data = replace(data, conversion=conversion)
            write_minimal_file(data, filepath)
            return
        write_outputs([(filepath, asset)], maya_order=self.export_settings.legacy_maya_order)

    def restore_scene(self):
        try:
            super().restore_scene()
        finally:
            for ob, (region, permutation) in self.collection_properties.items():
                ob.nwo.collection_region = region
                ob.nwo.collection_permutation = permutation
            self.context.scene.frame_set(self.current_frame, subframe=self.original_subframe)


class StandaloneExport:
    bl_options = {'PRESET'}
    use_selection: BoolProperty(name='Selected Objects', description='Export only selected objects', default=False)
    use_visible: BoolProperty(name='Visible Objects', description='Export only objects visible in the current view layer', default=False)
    use_active_collection: BoolProperty(name='Active Collection', description='Export the active collection and its child collections', default=False)
    convert_scale: BoolProperty(name='Convert Scale', description='Convert scene units to Halo export units', default=True)
    convert_forward: BoolProperty(name='Convert Forward', description='Convert the scene forward direction to the export convention', default=True)

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def invoke(self, context, event):
        if self.format != 'gr2' and not self.properties.is_property_set('version'):
            self.version = project_versions(context)[{'jms': 0, 'ass': 1, 'jma': 2}[self.format]]
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        include = layout.box()
        include.label(text='Include')
        include.prop(self, 'use_selection')
        include.prop(self, 'use_visible')
        include.prop(self, 'use_active_collection')
        if self.format == 'gr2':
            include.prop(self, 'include_animation')
            include.prop(self, 'halo_metadata')
        transform = layout.box()
        transform.label(text='Transform')
        transform.prop(self, 'convert_scale')
        transform.prop(self, 'convert_forward')
        if self.format != 'gr2':
            format_box = layout.box()
            format_box.label(text='Format')
            format_box.prop(self, 'version')
            if self.format == 'jma':
                format_box.prop(self, 'animation_format')

    def execute(self, context):
        export = None
        try:
            if self.format != 'gr2' and not self.properties.is_property_set('version'):
                self.version = project_versions(context)[{'jms': 0, 'ass': 1, 'jma': 2}[self.format]]
            filepath = Path(bpy.path.abspath(self.filepath))
            if self.format == 'jma':
                filepath = filepath.with_suffix('.' + self.animation_format)
            objects = export_objects(context, self)
            if not objects:
                raise ExportCancelled('No objects match the export filters')
            export = StandaloneScene(context, filepath, self, objects)
            try:
                export.ready_scene()
                export.get_initial_export_objects()
                export.map_halo_properties()
                export.create_virtual_tree()
                export.write_file(filepath, self)
            finally:
                export.restore_scene()
            for warning in dict.fromkeys(export.warnings + export.virtual_scene.warnings):
                self.report({'WARNING'}, warning)
            self.report({'INFO'}, f'Exported {filepath.name}')
            return {'FINISHED'}
        except Exception as error:
            if not isinstance(error, (ExportCancelled, ValueError, OSError)):
                traceback.print_exc()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class NWO_ExportJMS(StandaloneExport, bpy.types.Operator, ExportHelper):
    bl_idname = 'export_scene.foundry_jms'
    bl_label = 'Export JMS'
    bl_description = 'Export a standalone JMS file to the chosen location'
    format = 'jms'
    filename_ext = '.jms'
    filter_glob: StringProperty(default='*.jms', options={'HIDDEN'})
    version: IntProperty(name='Version', description='JMS file version; initialized from the project default', default=8213, min=8197, max=8213)


class NWO_ExportASS(StandaloneExport, bpy.types.Operator, ExportHelper):
    bl_idname = 'export_scene.foundry_ass'
    bl_label = 'Export ASS'
    bl_description = 'Export a standalone ASS file to the chosen location'
    format = 'ass'
    filename_ext = '.ass'
    filter_glob: StringProperty(default='*.ass', options={'HIDDEN'})
    version: IntProperty(name='Version', description='ASS file version; initialized from the project default', default=7, min=1, max=7)


def update_animation_format(self, context):
    if self.filepath:
        self.filepath = str(Path(self.filepath).with_suffix('.' + self.animation_format))


class NWO_ExportJMA(StandaloneExport, bpy.types.Operator, ExportHelper):
    bl_idname = 'export_scene.foundry_jma'
    bl_label = 'Export Halo Animation'
    bl_description = 'Export the currently assigned actions over the scene frame range as a standalone Halo animation'
    format = 'jma'
    filename_ext = '.jma'
    filter_glob: StringProperty(default='*.jma;*.jmm;*.jmt;*.jmz;*.jmo;*.jmr;*.jmw;*.jmv;*.jmh', options={'HIDDEN'})
    version: IntProperty(name='Version', description='Animation file version; initialized from the project default', default=16395, min=16392, max=16395)
    animation_format: EnumProperty(name='Animation Format', items=ANIMATION_FORMATS, default='jma', update=update_animation_format)

    def check(self, context):
        if self.filepath:
            filepath = str(Path(self.filepath).with_suffix('.' + self.animation_format))
            if filepath != self.filepath:
                self.filepath = filepath
                return True
        return False


class NWO_ExportGR2(StandaloneExport, bpy.types.Operator, ExportHelper):
    bl_idname = 'export_scene.foundry_gr2'
    bl_label = 'Export GR2'
    bl_description = 'Export a standalone Granny file to the chosen location'
    format = 'gr2'
    filename_ext = '.gr2'
    filter_glob: StringProperty(default='*.gr2', options={'HIDDEN'})
    halo_metadata: BoolProperty(name='Halo Properties', description='Write BungieExportInfo and Halo properties; disable for use outside Halo', default=True)
    include_animation: BoolProperty(name='Include Animation', description='Include the currently assigned actions over the scene frame range', default=False)


classes = (NWO_ExportJMS, NWO_ExportASS, NWO_ExportJMA, NWO_ExportGR2)


def menu_func_export(self, context):
    for cls, label in zip(classes, ('Halo JMS (.jms)', 'Halo ASS (.ass)', 'Halo Animation (.jma/.jmm/…)', 'Granny (.gr2)')):
        self.layout.operator(cls.bl_idname, text=label)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
