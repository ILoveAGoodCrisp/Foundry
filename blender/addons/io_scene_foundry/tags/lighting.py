"""Lightmapper region settings without the ManagedBlam field interface."""
import math
from .backend import TagDocument


class LightmapperGlobalsDocument(TagDocument):
    tag_ext = 'lightmapper_globals'

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
