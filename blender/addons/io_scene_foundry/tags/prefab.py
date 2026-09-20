"""Native prefab metadata."""
from pathlib import Path

from .backend import TagDocument
from .blender import BlenderTag


class PrefabTag(BlenderTag, TagDocument):
    tag_ext = 'prefab'

    def bsp_path(self):
        reference = self.reference(self.tag.root(), 'bsp reference')
        if reference is None:
            return None
        path = Path(reference.Filename)
        return path if path.is_file() else None

