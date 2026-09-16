"""Blender object metadata backed by blam-tags."""
from ..tags.blender import BlenderTag
from ..tags.object import ObjectDocument


class ObjectTag(BlenderTag, ObjectDocument):
    def __init__(self, path='', *, tag_must_exist=False, **kwargs):
        super().__init__(path, tag_must_exist=tag_must_exist, **kwargs)

    def functions_to_blender(self):
        from .connected_material import game_functions
        candidates = [e for e in self.block(self.object_struct(), 'functions')
                      if self.value(e, 'export name').strip()
                      and self.value(e, 'export name') != self.value(e, 'import name')
                      and self.value(e, 'export name') not in game_functions]
        if not candidates:
            return {}
        # Custom function editors have no Python binding yet.
        from .object_legacy import LegacyObjectTag
        with LegacyObjectTag(path=self.system_path, tag_must_exist=True) as legacy:
            return legacy.functions_to_blender()

    def attachments_to_blender(self, armature, markers, parent_collection):
        if not len(self.block(self.object_struct(), 'attachments')):
            return []
        # Light conversion still needs the legacy custom function editor.
        from .object_legacy import LegacyObjectTag
        with LegacyObjectTag(path=self.system_path, tag_must_exist=True) as legacy:
            return legacy.attachments_to_blender(armature, markers, parent_collection)
