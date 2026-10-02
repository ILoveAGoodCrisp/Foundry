"""Global material and player metadata, backed by blam-tags."""
from enum import Enum
from pathlib import Path
from .model_blender import ModelTag
from .blender import BlenderTag
from .metadata import GlobalsDocument


class FPARMS(Enum):
    NONE = 0
    SPARTAN = 1
    ELITE = 2


class GlobalsTag(BlenderTag, GlobalsDocument):
    tag_ext = 'globals'

    def cinematic_film_aperture(self) -> float | None:
        field = self.tag.root().field('cinematics globals')
        block = None if field is None else field.as_block()
        if block is None or not len(block):
            return None
        aperture = block[0].field('cinematic film aperture')
        return None if aperture is None else float(aperture.value)

    def get_fp_arms_path(self, character_type: FPARMS):
        if character_type not in (FPARMS.SPARTAN, FPARMS.ELITE):
            return
        index = character_type.value - 1
        references = self.get_fp_arms_references(index)
        if references is None:
            return
        fp_path, tp_path = references
        allowed_fp_region_perms = "default"
        if self.corinth:
            element = self.fp_player_representation(index)
            model_path = fp_path
            variant = self.value(element, 'first person multiplayer hands variant')
            if model_path is None or not Path(model_path.Filename).is_file():
                return
            with ModelTag(path=model_path.RelativePathWithExtension) as model:
                fp_path = model.reference_render_model.Path
                if fp_path is not None and variant:
                    allowed_fp_region_perms = model.get_variant_regions_and_permutations(variant, -1)
        if fp_path is not None:
            return fp_path.Filename, tp_path.Filename if tp_path else None, allowed_fp_region_perms
