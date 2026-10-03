from pathlib import Path

from .cinematic_script import script_from_text

from .cinematic import CinematicSceneDataTag

from .cinematic_scene import NativeCinematicSceneTag
from .backend import TagDocument
from .cinematic_import import CinematicImportDocument
from .blender import BlenderTag

from .. import utils

CINEMATIC_TAG_NAME_MAX_LENGTH = 25


class CinematicScenarioDocument(TagDocument):
    """The scenario fields changed as part of a cinematic export."""

    def _set_value(self, element, name, value):
        self.required_field(element, name).set(value)
        self.tag_has_changes = True

    def _set_indexed_flag(self, element, name, index, enabled=True):
        field = self.required_field(element, name)
        if not 0 <= index < 32:
            raise IndexError(f'{self.path}: {name!r} cannot represent bit {index}')
        value = int(field.value)
        field.set(value | (1 << index) if enabled else value & ~(1 << index))
        self.tag_has_changes = True

    def _enable_all_flags(self, element, name, count):
        if not 0 <= count <= 32:
            raise ValueError(f'{self.path}: {name!r} cannot represent {count} entries')
        field = self.required_field(element, name)
        field.set((1 << count) - 1)
        self.tag_has_changes = True

    def link_cinematic(self, cinematic, zone_set):
        root = self.tag.root()
        cinematics = self.block(root, 'cinematics')
        cinematic_index = None
        target = cinematic.RelativePathWithExtension.casefold()
        for index in range(len(cinematics)):
            reference = self.reference(cinematics[index], 'name')
            if reference is not None and reference.RelativePathWithExtension.casefold() == target:
                cinematic_index = index
                break
        if cinematic_index is None:
            cinematic_index = cinematics.add()
            cinematics = self.block(root, 'cinematics')
            self.set_reference(cinematics[cinematic_index], 'name', cinematic)

        if not zone_set:
            return
        zone_sets = self.block(root, 'zone sets')
        zone_set_index = None
        for index in range(len(zone_sets)):
            if self.value(zone_sets[index], 'name') == zone_set:
                zone_set_index = index
                break
        if zone_set_index is None:
            zone_set_index = zone_sets.add()
            zone_sets = self.block(root, 'zone sets')
            element = zone_sets[zone_set_index]
            self._set_value(element, 'name', zone_set)
            self._enable_all_flags(element, 'bsp zone flags', len(self.block(root, 'structure bsps')))
            if element.field('structure design zone flags') is not None:
                self._enable_all_flags(element, 'structure design zone flags', len(self.block(root, 'structure designs')))
        self._set_indexed_flag(zone_sets[zone_set_index], 'cinematic zones', cinematic_index)
        return zone_set_index

    def update_anchors(self, cinematic_scenes, corinth):
        root = self.tag.root()
        flags = self.block(root, 'cutscene flags')
        by_name = {scene.anchor_name: scene for scene in cinematic_scenes}
        indices = {}
        for index in range(len(flags)):
            name = self.value(flags[index], 'name')
            if name in by_name:
                indices[name] = index
        for name, scene in by_name.items():
            index = indices.get(name)
            if index is None:
                index = flags.add()
                flags = self.block(root, 'cutscene flags')
            element = flags[index]
            self._set_value(element, 'name', name)
            position = self.required_field(element, 'position')
            position.set(type(position.value)(*scene.anchor_location))
            facing = self.required_field(element, 'facing')
            angles = scene.anchor_ypr if corinth else scene.anchor_ypr[:2]
            facing.set(type(facing.value)(*angles))
            self.tag_has_changes = True

    def remove_generated_script(self):
        root = self.tag.root()
        source_files = self.block(root, 'source files')
        for index in range(len(source_files)):
            if self.value(source_files[index], 'name') == 'auto_generated_cinematic_script':
                source_files.delete(index)
                self.tag_has_changes = True
                return

    def update_cinematic_resource(self):
        root = self.tag.root()
        resources = self.block(root, 'scenario resources')
        if not len(resources):
            return
        split_resources = self.block(resources[0], 'new split resources')
        if not len(split_resources):
            return
        reference = self.reference(split_resources[0], 'cutscene data resource')
        if not self.path_exists(reference):
            return
        with TagDocument(reference, tags_root=self.tags_root, game=self.game,
                         must_exist=True) as resource:
            destination = resource.tag.root()
            # Older H3/ODST resources contain only flags, camera points and
            # recorded animations. Their flags also use fixed strings instead
            # of string IDs and omit editor folders. Copy values into the
            # resource's own layout rather than assuming identical blocks.
            for target_name, source_name in (('cinematics', 'cinematics'),
                                             ('flags', 'cutscene flags')):
                if target_name == 'cinematics' and destination.field(target_name) is None:
                    continue
                target = resource.block(destination, target_name)
                source = self.block(root, source_name)
                target.clear()
                for entry in source:
                    element = target[target.add()]
                    for field in element.fields():
                        source_field = entry.field(field.name) if field.name else None
                        if source_field is not None:
                            if field.type_name in {'byte flags', 'word flags', 'long flags'}:
                                source_names = source_field.options().names
                                for name in field.options().names:
                                    field.set_flag(name, name in source_names and source_field.get_flag(name))
                            else:
                                field.set(source_field.value)
            resource.tag_has_changes = True

    def scenario_type(self):
        return self.value(self.tag.root(), 'type')


class CinematicTag(BlenderTag, TagDocument):
    tag_ext = 'cinematic'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def _set_value(self, element, name, value):
        self.required_field(element, name).set(value)
        self.tag_has_changes = True

    def _set_script(self, root, name, text):
        script_struct = self.required_field(root, name).as_struct()
        if script_struct is None:
            raise ValueError(f'{self.path}: {name!r} is not a structure')
        self._set_value(script_struct, 'script', text.encode('utf-8'))
    
    def create(self, name: str, cinematic_scenes, scenario_path: Path | None = None, zone_set: str = "cinematic", scene_nwo=None):
        scene_nwo = scene_nwo or self.scene_nwo
        root = self.tag.root()
        settings = self.required_field(root, 'scenario and zone set').as_struct()
        if settings is None:
            raise ValueError(f'{self.path}: scenario and zone set is not a structure')
        self._set_value(root, 'name', name[:CINEMATIC_TAG_NAME_MAX_LENGTH])
        
        # Add Cinematic Settings
        channel_type_value = int(scene_nwo.cinematic_channel_type)
        if not self.corinth:
            channel_type_value = min(4, channel_type_value)
        self._set_value(root, 'channel type', channel_type_value)
        self._set_value(root, 'easing in time', scene_nwo.cinematic_easing_in_time)
        self._set_value(root, 'easing out time', scene_nwo.cinematic_easing_out_time)
        if self.game in {'halo3', 'halo3odst'}:
            for direction in ('in', 'out'):
                color = self.required_field(root, f'fade {direction} color')
                color.set(type(color.value)(*getattr(scene_nwo, f'cinematic_fade_{direction}_color')))
                self._set_value(root, f'fade {direction} time', getattr(scene_nwo, f'cinematic_fade_{direction}_time'))
        else:
            if scene_nwo.cinematic_transition_settings.strip():
                transition = Path(utils.relative_path(scene_nwo.cinematic_transition_settings)).with_suffix(".cinematic_transition")
            else:
                transition = Path(self.tag_path.RelativePath).with_suffix(".cinematic_transition")
            with TagDocument(transition, tags_root=self.tags_dir, game=self.game,
                             extension='cinematic_transition', must_exist=False) as trans:
                transition_reference = trans.reference_from_path(trans.path)
                self.set_reference(root, 'transition settings', transition_reference)
                if not scene_nwo.cinematic_transition_settings.strip():
                    scene_nwo.cinematic_transition_settings = transition_reference.RelativePathWithExtension
            
        if scene_nwo.cinematic_bink_movie.strip():
            b_path = Path(utils.relative_path(scene_nwo.cinematic_bink_movie)).with_suffix(".bink")
            self.set_reference(root, 'bink movie', b_path)
            
        flags = root.field('flags')
        if flags is not None:
            flags.set_flag("Outro", scene_nwo.cinematic_outro)
        elif scene_nwo.cinematic_outro:
            raise ValueError(f'{self.path}: outro is unavailable in this tag layout')
        if self.corinth:
            flags.set_flag("Extra Memory Bink", scene_nwo.cinematic_extra_memory_bink)
            flags.set_flag("Opaque Bink", scene_nwo.cinematic_opaque_bink)
            flags.set_flag("Don't Stretch Bink", scene_nwo.cinematic_dont_stretch_bink)
            flags.set_flag("Don't Force Hologram Render", scene_nwo.cinematic_dont_force_hologram_render)
            self._set_value(root, 'bink movie on disc', scene_nwo.cinematic_bink_movie_on_disc)

        self._set_script(root, 'header', script_from_text(
            self.corinth, scene_nwo.cinematic_header, scene_nwo.cinematic_header_text,
            scene_nwo.cinematic_header_use_text))
        self._set_script(root, 'footer', script_from_text(
            self.corinth, scene_nwo.cinematic_footer, scene_nwo.cinematic_footer_text,
            scene_nwo.cinematic_footer_use_text))
        self._set_script(root, 'early exit', script_from_text(
            self.corinth, scene_nwo.cinematic_skip_footer, scene_nwo.cinematic_skip_footer_text,
            scene_nwo.cinematic_skip_footer_use_text))

        # Add scenes to cinematic
        scene_paths = [cs.name for cs in cinematic_scenes]
        if scene_paths:
            scenes = self.block(root, 'scenes')
            scenes.clear()
            for sp in scene_paths:
                element = scenes[scenes.add()]
                scene_path = Path(Path(self.tag_path.RelativePath).parent, sp)
                self.set_reference(element, 'scene', scene_path.with_suffix(".cinematic_scene"))
                if self.corinth:
                    self.set_reference(element, 'data', scene_path.with_suffix(".cinematic_scene_data"))
        
        needs_cinematic_scenario_update = True
        if scenario_path is None:
            tag_path = self.reference(settings, 'scenario')
            if tag_path is not None:
                path = Path(tag_path.Filename)
                if path.exists():
                    scenario_path = path
                    needs_cinematic_scenario_update = False
        
        if scenario_path is not None:
            with CinematicScenarioDocument(scenario_path, tags_root=self.tags_dir,
                                           game=self.game, must_exist=True) as scenario:
                # Set link to scenario in cinematic tag
                if needs_cinematic_scenario_update:
                    self.set_reference(settings, 'scenario', scenario.path)
                    zone_set_index = scenario.link_cinematic(self.tag_path, zone_set)
                    if zone_set_index is not None:
                        self._set_value(settings, 'zone set', zone_set_index)

                scenario.update_anchors(cinematic_scenes, self.corinth)
                if not self.corinth:
                    scenario.update_cinematic_resource()
                    scenario.remove_generated_script()

                if scenario.scenario_type() == 1:
                    utils.print_warning(f"{scenario.path} is set to Multiplayer. Cinematics will crash if you attempt to run them\nSwitch the scenario type to Solo before playing cinematic")


class NativeCinematicTag(CinematicTag):
    """Native cinematic scene discovery and import, without playback initialization."""
    tag_ext = 'cinematic'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', True)
        super().__init__(path, **kwargs)

    def scene_references(self):
        return [(self.reference(element, 'scene'),
                 self.reference(element, 'data') if self.corinth else None)
                for element in self.block(self.tag.root(), 'scenes')]

    def scenario_reference(self):
        settings = self.required_field(self.tag.root(), 'scenario and zone set').as_struct()
        return self.reference(settings, 'scenario'), self.value(settings, 'zone set')

    def playback_bsp_zone_flags(self):
        playback = self.required_field(self.tag.root(), 'cinematic playback').as_struct()
        if playback is None:
            raise ValueError(f'{self.path}: cinematic playback is not a structure')
        field = playback.field('bsp zone flags')
        return field.value if field is not None else None

    def to_blender(self, film_aperture, import_scenario=False, specific_scene=''):
        scenario_path, zone_set = None, ''
        self.scenario_bsp_mask = None
        if import_scenario:
            reference, index = self.scenario_reference()
            with CinematicImportDocument(self.path, tags_root=self.tags_root,
                    game=self.game, definitions=self.definitions, must_exist=True) as document:
                environment = document.resolve_environment(reference, index)
            scenario_path, zone_set = environment.scenario, environment.zone_set
            self.scenario_bsp_mask = environment.bsp_mask
            if environment.warning:
                utils.print_warning(environment.warning)
            if scenario_path and not self.path_exists(reference):
                utils.print_step(f'Resolved cinematic scenario: {scenario_path}')
        scenes = []
        for scene, data in self.scene_references():
            if not self.path_exists(scene) or (self.corinth and not self.path_exists(data)):
                continue
            if specific_scene and scene.RelativePathWithExtension != specific_scene:
                continue
            result = SceneData(film_aperture, self.tag_path.ShortName)
            if self.corinth:
                result.from_scene_corinth(scene, data)
            else:
                result.from_scene(scene)
            scenes.append(result)
        return scenes, scenario_path, zone_set


class SceneData:
    def __init__(self, film_aperture, cinematic_name):
        self.name = ""
        self.blender_scene = None
        self.camera_objects = []
        self.object_animations = []
        self.anchor_name = ""
        self.actions = []
        self.shot_frames = []
        self.lighting_infos = []
        
        self.film_aperture = film_aperture
        self.cinematic_name = cinematic_name
        
    def from_scene(self, scene_tagpath):
        with NativeCinematicSceneTag(path=scene_tagpath) as scene:
            self.name, self.blender_scene, self.camera_objects, self.object_animations, self.anchor_name, self.actions, self.shot_frames, self.lighting_infos = scene.to_blender(self.film_aperture, self.cinematic_name, scene)
    
    def from_scene_corinth(self, scene_tagpath, scene_data_tagpath):
        with NativeCinematicSceneTag(path=scene_tagpath) as scene:
            with CinematicSceneDataTag(path=scene_data_tagpath) as data:
                self.name, self.blender_scene, self.camera_objects, self.object_animations, self.anchor_name, self.actions, self.shot_frames, self.lighting_infos = scene.to_blender(self.film_aperture, self.cinematic_name, data)
