"""Model metadata and reference edits backed by blam-tags."""
from types import SimpleNamespace
from pathlib import Path
from .. import utils
from ..tags.blender import BlenderTag
from ..tags.model import ModelDocument, RenderModelOverrideType

ChildObject = SimpleNamespace


def _variant_default_permutation(region, region_default_perms):
    return region_default_perms.get(region, 'default')


class ModelTag(BlenderTag, ModelDocument):
    tag_ext = 'model'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        self.asset_dir = utils.get_asset_path()
        self.asset_name = Path(self.asset_dir).name
