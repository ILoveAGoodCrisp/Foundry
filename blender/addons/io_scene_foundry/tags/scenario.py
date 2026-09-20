"""Native scenario metadata and lightweight editor operations."""
from pathlib import Path
import shutil

from .backend import TagDocument
from .blender import BlenderTag


class ScenarioMetadataTag(BlenderTag, TagDocument):
    tag_ext = 'scenario'

    def _set_value(self, struct, name, value):
        self.required_field(struct, name).set(value)
        self.tag_has_changes = True

    def _blocks(self):
        root = self.tag.root()
        designs_field = root.field('structure designs')
        designs = designs_field.as_block() if designs_field is not None else None
        return root, self.block(root, 'structure bsps'), designs

    def _bsp(self, name):
        _, bsps, _ = self._blocks()
        for index in range(len(bsps)):
            reference = self.reference(bsps[index], 'structure bsp')
            if reference is not None and Path(reference.RelativePath).name == name:
                return bsps[index]

    def _sky_name(self, element):
        root = self.tag.root()
        object_names = self.block(root, 'object names')
        index = self.value(element, 'name')
        if isinstance(index, int) and 0 <= index < len(object_names):
            name = self.value(object_names[index], 'name')
            if name:
                return name
        reference = self.reference(element, 'sky')
        return reference.ShortName if reference is not None else None

    @staticmethod
    def _active_indices(mask, count):
        return {index for index in range(min(count, 32)) if int(mask) & (1 << index)}

    def scenario_type(self):
        return self.value(self.tag.root(), 'type')

    read_scenario_type = scenario_type

    def set_scenario_type(self, value):
        self._set_value(self.tag.root(), 'type', value)

    def create_default_profile(self):
        root = self.tag.root()
        locations = self.block(root, 'player starting locations')
        locations.add()

        profiles = self.block(root, 'player starting profile')
        profile_index = profiles.add()
        profiles = self.block(root, 'player starting profile')
        profile = profiles[profile_index]
        self._set_value(profile, 'name', 'default_single')

        defaults = {}
        object_types_path = self.tags_root / 'multiplayer/globals.multiplayer_object_type_list'
        if object_types_path.is_file():
            with TagDocument(object_types_path, tags_root=self.tags_root,
                             game=self.game, must_exist=True) as object_types:
                block = object_types.block(object_types.tag.root(), 'object types')
                wanted = {
                    'assault_rifle': 'primary weapon',
                    'magnum': 'secondary weapon',
                    'sprint_equipment': 'starting equipment',
                }
                for element in block:
                    field = wanted.get(object_types.value(element, 'name'))
                    if field is not None:
                        reference = object_types.reference(element, 'object')
                        if reference is not None:
                            defaults[field] = reference

        for name in ('primary weapon', 'secondary weapon'):
            reference = defaults.get(name)
            if reference is None:
                continue
            self.set_reference(profile, name, reference)
            prefix = 'primary' if name.startswith('primary') else 'secondary'
            self._set_value(profile, f'{prefix}rounds loaded', -1)
            self._set_value(profile, f'{prefix}rounds total', -1)
        equipment = profile.field('starting equipment')
        if equipment is not None and defaults.get('starting equipment') is not None:
            self.set_reference(profile, 'starting equipment', defaults['starting equipment'])
        self.tag_has_changes = True

    def survival_mode(self):
        return self.scenario_type() == 0 and self.required_field(self.tag.root(), 'flags').get_flag('survival')

    def get_bsp_names(self):
        _, bsps, _ = self._blocks()
        names = []
        for element in bsps:
            reference = self.reference(element, 'structure bsp')
            if reference is not None:
                names.append(reference.ShortName)
        return names

    def get_sky_indices(self):
        _, bsps, _ = self._blocks()
        return [self.value(element, 'default sky') for element in bsps]

    def _zone_mask(self, zone_set, name):
        if not zone_set:
            return None
        root = self.tag.root()
        for element in self.block(root, 'zone sets'):
            if self.value(element, 'name') == zone_set:
                return int(self.value(element, name))
        return None

    def get_bsp_paths(self, zone_set=''):
        _, bsps, _ = self._blocks()
        mask = self._zone_mask(zone_set, 'bsp zone flags')
        active = self._active_indices(mask, len(bsps)) if mask else None
        paths = []
        for index, element in enumerate(bsps):
            if active is not None and index not in active:
                continue
            reference = self.reference(element, 'structure bsp')
            if self.path_exists(reference):
                paths.append(reference.Filename)
        return paths

    def get_design_paths(self, zone_set=''):
        _, _, designs = self._blocks()
        if designs is None:
            return []
        mask = self._zone_mask(zone_set, 'structure design zone flags')
        active = self._active_indices(mask, len(designs)) if mask else None
        paths = []
        for index, element in enumerate(designs):
            if active is not None and index not in active:
                continue
            reference = self.reference(element, 'structure design')
            if self.path_exists(reference):
                paths.append(reference.Filename)
        return paths

    def zone_set_names(self):
        root = self.tag.root()
        return [self.value(element, 'name') for element in self.block(root, 'zone sets')]

    def get_zone_sets_dict(self):
        root, bsps, _ = self._blocks()
        bsp_names = []
        for element in bsps:
            reference = self.reference(element, 'structure bsp')
            bsp_names.append(reference.ShortName if reference is not None else '')
        result = {}
        for element in self.block(root, 'zone sets'):
            mask = self.value(element, 'bsp zone flags')
            result[self.value(element, 'name')] = [
                bsp_names[index] for index in self._active_indices(mask, len(bsps))
                if bsp_names[index]
            ]
        return result

    def write_foundry_zone_set(self):
        root, bsps, designs = self._blocks()
        zone_sets = self.block(root, 'zone sets')
        index = None
        for candidate in range(len(zone_sets)):
            if self.value(zone_sets[candidate], 'name') == 'foundry_debug_zone_set':
                index = candidate
                break
        if index is None:
            index = zone_sets.add()
            zone_sets = self.block(root, 'zone sets')
            self._set_value(zone_sets[index], 'name', 'foundry_debug_zone_set')
        element = zone_sets[index]
        bsp_count = len(bsps)
        design_count = len(designs) if designs is not None else 0
        if bsp_count > 32 or design_count > 32:
            raise ValueError(f'{self.path}: debug zone set block flags support at most 32 entries')
        self._set_value(element, 'bsp zone flags', (1 << bsp_count) - 1)
        if element.field('structure design zone flags') is not None:
            self._set_value(element, 'structure design zone flags', (1 << design_count) - 1)

    def get_skies_mapping(self):
        root = self.tag.root()
        return [name for element in self.block(root, 'skies')
                if (name := self._sky_name(element)) is not None]

    def get_sky_paths(self):
        root = self.tag.root()
        return [reference.RelativePathWithExtension for element in self.block(root, 'skies')
                if (reference := self.reference(element, 'sky')) is not None
                and self.path_exists(reference)]

    @staticmethod
    def _set_point(field, point):
        field.set(type(field.value)(*point))

    def cubemap_positions(self):
        root = self.tag.root()
        positions = []
        for element in self.block(root, 'cubemaps'):
            point = self.value(element, 'cubemap position')
            positions.append((point.x, point.y, point.z))
        return positions

    def ensure_default_cubemap(self, point=(0.0, 0.0, 0.6)):
        root = self.tag.root()
        cubemaps = self.block(root, 'cubemaps')
        if len(cubemaps):
            return False
        index = cubemaps.add()
        cubemaps = self.block(root, 'cubemaps')
        self._set_point(self.required_field(cubemaps[index], 'cubemap position'), point)
        self.tag_has_changes = True

        resources = self.block(root, 'scenario resources')
        if not len(resources):
            return True
        split_resources = self.block(resources[0], 'new split resources')
        if not len(split_resources):
            return True
        reference = self.reference(split_resources[0], 'cubemap reference resource')
        if not self.path_exists(reference):
            return True
        with TagDocument(reference, tags_root=self.tags_root, game=self.game,
                         must_exist=True) as resource:
            resource_root = resource.tag.root()
            resource_cubemaps = resource.block(resource_root, 'cubemaps')
            resource_index = resource_cubemaps.add()
            resource_cubemaps = resource.block(resource_root, 'cubemaps')
            self._set_point(resource.required_field(
                resource_cubemaps[resource_index], 'cubemap position'), point)
            resource.tag_has_changes = True
        return True

    def set_cubemap_bitmap_references(self):
        root, bsps, _ = self._blocks()
        scenario_name = self.tag_path.ShortName
        scenario_dir = Path(self.tag_path.RelativePath).parent
        field_name = 'bsp specific cubemap' if self.corinth else 'cubemap bitmap group reference'
        records = []
        for index in range(len(bsps)):
            element = bsps[index]
            bsp = self.reference(element, 'structure bsp')
            if bsp is None:
                continue
            bitmap = scenario_dir / f'{scenario_name}_{bsp.ShortName}_cubemaps.bitmap'
            self.set_reference(element, field_name, bitmap)
            records.append((index, bsp.ShortName, self.reference(element, field_name)))
        return records

    def cutscene_anchor(self, name):
        root = self.tag.root()
        for element in self.block(root, 'cutscene flags'):
            if self.value(element, 'name') != name:
                continue
            point = self.value(element, 'position')
            angles = self.value(element, 'facing')
            return ((point.x, point.y, point.z),
                    (angles.yaw, angles.pitch, getattr(angles, 'roll', 0.0)))

    def add_new_sky(self, path):
        root = self.tag.root()
        skies = self.block(root, 'skies')
        sky_index = skies.add()
        skies = self.block(root, 'skies')
        self.set_reference(skies[sky_index], 'sky', path)

        object_names = self.block(root, 'object names')
        name_index = object_names.add()
        object_names = self.block(root, 'object names')
        sky_name = Path(path).stem
        self._set_value(object_names[name_index], 'name', sky_name)
        skies = self.block(root, 'skies')
        self._set_value(skies[sky_index], 'name', name_index)

        if self.corinth and sky_index == 0:
            bsps = self.block(root, 'structure bsps')
            for element in bsps:
                if self.value(element, 'default sky') == -1:
                    self._set_value(element, 'default sky', sky_index)
        return sky_name, sky_index

    def set_bsp_default_sky(self, bsp_name, sky_index):
        element = self._bsp(bsp_name)
        if element is None:
            return None
        self._set_value(element, 'default sky', sky_index)
        root = self.tag.root()
        skies = self.block(root, 'skies')
        return self._sky_name(skies[sky_index]) if 0 <= sky_index < len(skies) else 'None'

    def set_bsp_lightmap_res(self, bsp_name, size_class, refinement_class):
        element = self._bsp(bsp_name)
        if element is None:
            return False
        self._set_value(element, 'size class', size_class)
        if self.corinth:
            self._set_value(element, 'refinement size class', refinement_class)
        options = self.required_field(element, 'size class').options()
        return options.current_name if options is not None else str(size_class)

    def get_bsp_info(self, bsp_name):
        element = self._bsp(bsp_name)
        if element is None:
            return None
        size = self.required_field(element, 'size class').options()
        result = {'Lightmapper Size Class': size.current_name if size else str(self.value(element, 'size class'))}
        if self.corinth:
            refinement = self.required_field(element, 'refinement size class').options()
            result['Lightmapper Refinement Class'] = refinement.current_name if refinement else str(self.value(element, 'refinement size class'))
        sky_index = self.value(element, 'default sky')
        if sky_index < 0:
            result['Default Sky'] = 'None'
        else:
            skies = self.block(self.tag.root(), 'skies')
            result['Default Sky'] = self._sky_name(skies[sky_index]) if sky_index < len(skies) else 'None'
        return result

    def get_info(self, bsp_index):
        if self.corinth:
            return None
        _, bsps, _ = self._blocks()
        if not 0 <= bsp_index < len(bsps):
            return None
        reference = self.reference(bsps[bsp_index], 'structure lighting_info')
        return Path(reference.Filename) if self.path_exists(reference) else None

    def collect_cutscene_titles(self):
        root = self.tag.root()
        titles = [(text, text, '') for element in self.block(root, 'cutscene titles')
                  if (text := self.value(element, 'name'))]
        if not self.corinth:
            return titles
        for element in self.block(root, 'child scenarios'):
            reference = self.reference(element, 'tag')
            if not self.path_exists(reference):
                continue
            with ScenarioMetadataTag(reference) as child:
                child_titles = child.collect_cutscene_titles()
            if child_titles:
                titles.append(('', reference.ShortName, ''))
                titles.extend(child_titles)
        return titles

    def save_copy_as_solo(self, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.system_path, destination)
        with ScenarioMetadataTag(destination) as copy:
            copy.set_scenario_type(0)
