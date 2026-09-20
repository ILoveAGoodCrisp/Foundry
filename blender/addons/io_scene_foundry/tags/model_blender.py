"""Blender-facing model metadata wrapper."""
from pathlib import Path

from .. import utils
from .blender import BlenderTag
from .model import ModelDocument


class ModelTag(BlenderTag, ModelDocument):
    tag_ext = 'model'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        self.asset_dir = utils.get_asset_path()
        self.asset_name = Path(self.asset_dir).name
