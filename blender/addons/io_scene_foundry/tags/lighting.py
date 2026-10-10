"""Lightmapper region settings without the ManagedBlam field interface."""
import math
from pathlib import Path
import shutil
from .backend import TagDocument
from dataclasses import dataclass
from .backend import TagReference


@dataclass(frozen=True)
class CinematicDynamicLight:
    reference: TagReference
    follow_object: bool
    use_marker: bool
    direction: float
    front_back: float
    distance: float


class CinematicLightingDocument(TagDocument):
    tag_ext = 'new_cinematic_lighting'

    def seed_from_template(self, template):
        """Initialize a missing lighting tag and local light copies, never overwrite edits."""
        if not self.tag_is_new or not template:
            return
        if self.read_only:
            raise RuntimeError('Cannot create lighting templates during a read-only operation')
        with TagDocument(template, tags_root=self.tags_root, game=self.game,
                         extension=self.tag_ext, must_exist=True) as source:
            self._tag = self.api.TagFile.read(source.system_path)
        references = []
        block = self.tag.root().field('dynamic lights')
        for element in block.as_block() if block is not None else ():
            reference = self.reference(element, 'light')
            if reference is not None:
                references.append((element, reference))
        # Resolve every source before creating any dependencies, so a missing
        # template never silently produces a partially populated lighting tag.
        copies = {}
        for _, reference in references:
            if reference.RelativePathWithExtension in copies:
                continue
            name = f'{self.system_path.stem}_light{len(copies) + 1}.light'
            destination = self.system_path.with_name(name)
            source = Path(reference.Filename)
            if not destination.is_file() and not source.is_file():
                raise FileNotFoundError(f'Missing cinematic template light: {source}')
            copies[reference.RelativePathWithExtension] = (source, destination)
        for source, destination in copies.values():
            if destination.is_file():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                with source.open('rb') as original, destination.open('xb') as output:
                    shutil.copyfileobj(original, output)
            except FileExistsError:
                pass
        for element, reference in references:
            self.set_reference(element, 'light', copies[reference.RelativePathWithExtension][1])
        self.tag_has_changes = True

    def dynamic_lights(self):
        # H4/H2AMP use authored probes; their Blender conversion is not implemented yet.
        if self.game in {'halo4', 'halo2a'}:
            return []
        result = []
        for element in self.block(self.tag.root(), 'dynamic lights'):
            reference = self.reference(element, 'light')
            if not self.path_exists(reference):
                continue
            flags = self.required_field(element, 'Flags')
            result.append(CinematicDynamicLight(reference, flags.get_flag('follow object'),
                          flags.get_flag('position at marker'), self.value(element, 'Direction'),
                          self.value(element, 'Front-Back'), self.value(element, 'Distance')))
        return result


class LightmapperGlobalsDocument(TagDocument):
    tag_ext = 'lightmapper_globals'

    def quality_names(self):
        return [self.value(element, 'name') for element in self.block(self.tag.root(), 'quality settings')]

    def settings(self, name):
        field = self.required_field(self.tag.root(), name)
        result = field.as_struct()
        if result is None:
            raise TypeError(f'{self.path}: {name!r} is not a settings struct')
        return result

    def restrict_to_region(self, minimum, maximum):
        minimum, maximum = tuple(minimum), tuple(maximum)
        if len(minimum) != 3 or len(maximum) != 3:
            raise ValueError('A lightmap region needs three minimum and maximum coordinates')
        if any(not math.isfinite(v) for v in minimum + maximum) or any(a > b for a, b in zip(minimum, maximum)):
            raise ValueError('Invalid lightmap region bounds')
        global_settings = self.settings('Global lightmapper settings')
        local_settings = self.settings('Local lightmapper settings')
        for name, value in (('Indirect Restrict AABB Min', minimum), ('Indirect Restrict AABB Max', maximum)):
            field = self.required_field(global_settings, name)
            field.set(type(field.value)(*value))
        self.required_field(global_settings, 'Global flags').set_flag('Restrict lightmap samples to Maya regions', True)
        self.required_field(local_settings, 'Local flags').set_flag('Enable AO', True)
        mode = self.required_field(global_settings, 'Mode')
        if mode.value == 'Direct only' or (isinstance(mode.value, int) and mode.value < 1):
            mode.set(1)
        self.tag_has_changes = True

    def clear_region_restriction(self):
        settings = self.settings('Global lightmapper settings')
        self.required_field(settings, 'Global flags').set_flag('Restrict lightmap samples to Maya regions', False)
        self.tag_has_changes = True
