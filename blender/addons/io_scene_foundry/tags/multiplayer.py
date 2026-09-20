"""Native multiplayer tag metadata."""
from .backend import TagDocument
from .blender import BlenderTag


class MultiplayerObjectTypeListTag(BlenderTag, TagDocument):
    tag_ext = 'multiplayer_object_type_list'

    def weapon_references(self):
        root = self.tag.root()
        object_types = self.block(root, 'object types')
        references = []
        for weapon in self.block(root, 'weapons'):
            index = self.value(weapon, 'object type')
            if not isinstance(index, int) or not 0 <= index < len(object_types):
                continue
            reference = self.reference(object_types[index], 'object')
            if self.path_exists(reference):
                references.append(reference)
        return references

