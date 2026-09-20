"""Native sound metadata used by Foundry UI lists."""
from .backend import TagDocument
from .blender import BlenderTag


class SoundEffectCollectionTag(BlenderTag, TagDocument):
    tag_ext = 'sound_effect_collection'

    def usable_effect_names(self):
        names = []
        for element in self.block(self.tag.root(), 'sound effects'):
            name = self.value(element, 'name')
            if not name:
                continue
            playback = self.required_field(element, 'playback').as_struct()
            if playback is None:
                raise TypeError(f'{self.path}: sound effect playback is not a struct')
            radio_effect = playback.field('radio effect')
            has_radio_effect = radio_effect is not None and radio_effect.value is not None
            components = playback.field('sound components')
            has_components = components is not None and bool(components.as_block())
            if components is None:
                # H3/ODST store components inside a nested sound-effect block.
                sound_effect = playback.field('sound effect')
                for effect in sound_effect.as_block() if sound_effect is not None else ():
                    nested = self.required_field(effect, 'sound effect struct').as_struct()
                    if nested is not None and self.block(nested, 'components'):
                        has_components = True
                        break
            if has_radio_effect or has_components:
                names.append(name)
        return names
