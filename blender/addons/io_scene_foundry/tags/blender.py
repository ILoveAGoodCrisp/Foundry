"""Blender project context for native blam-tags documents."""
from pathlib import Path
from .. import utils
from .backend import TagPathInput


class BlenderTag:
    """Mix with a TagDocument subclass; importing it never starts ManagedBlam."""
    tag_ext: str = ''

    def __init__(self, path: TagPathInput = '', *, tag_must_exist: bool = True,
                 always_save: bool = False, hide_prints: bool = False,
                 raise_on_error: bool = True) -> None:
        self.scene_nwo = utils.get_scene_props()
        project = utils.get_project(self.scene_nwo.scene_project)
        if project is None:
            raise RuntimeError('Select a Halo project before opening a tag')
        if not path:
            asset = Path(utils.get_asset_path())
            path = asset / (asset.name + '.' + self.tag_ext)
        self.corinth: bool = project.game in {'halo4', 'halo2a'}
        self.tags_dir: str = utils.get_tags_path()
        self.error: Exception | None = None
        try:
            super().__init__(path, tags_root=self.tags_dir, game=project.game,
                             extension=self.tag_ext, must_exist=tag_must_exist,
                             always_save=always_save)
            self.tag_path = self.reference_from_path(self.path)
        except Exception as error:
            self.valid = False
            self._tag = None
            self.tag_has_changes = False
            self.error = error
            if raise_on_error:
                raise
            if not hide_prints:
                utils.print_error(f'Could not open {path}: {error}')
