"""Sky tag references for the legacy games."""
from __future__ import annotations

from pathlib import Path

from .backend import TagDocument, TagReference


class SkyDocument(TagDocument):
    tag_ext = 'sky'

    def _reference_filename(self, field_name: str,
                            optional_tag_root: str | Path | None = None) -> str:
        reference = self.reference(self.tag.root(), field_name)
        if reference is None:
            return ''

        root = Path(optional_tag_root) if optional_tag_root is not None else reference.root
        resolved = TagReference(root, reference.RelativePath, reference.Extension)
        if self.game == 'halo1' and field_name == 'model' and reference.Extension == 'model':
            model_path = Path(resolved.Filename)
            gbxmodel_path = model_path.with_suffix('.gbxmodel')
            if not model_path.is_file() and gbxmodel_path.is_file():
                resolved = TagReference(root, reference.RelativePath, 'gbxmodel')
        return resolved.Filename

    def get_model_path(self, optional_tag_root: str | Path | None = None) -> str:
        field_name = 'model' if self.game == 'halo1' else 'render model'
        return self._reference_filename(field_name, optional_tag_root)

    def get_animation_path(self, optional_tag_root: str | Path | None = None) -> str:
        return self._reference_filename('animation graph', optional_tag_root)

