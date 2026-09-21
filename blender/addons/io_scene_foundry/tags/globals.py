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
        block = self.block(self.tag.root(), '@player representation')
        index = character_type.value - 1
        if index >= len(block):
            return
        element = block[index]
        allowed_fp_region_perms = "default"
        fp_path = None
        if self.corinth:
            model_path = self.reference(element, 'first person hands model')
            variant = self.value(element, 'first person multiplayer hands variant')
            if model_path is None or not Path(model_path.Filename).is_file():
                return
            with ModelTag(path=model_path.RelativePathWithExtension) as model:
                fp_path = model.reference_render_model.Path
                if fp_path is not None and variant:
                    allowed_fp_region_perms = model.get_variant_regions_and_permutations(variant, -1)
        else:
            fp_path = self.reference(element, 'first person hands')
        tp_path = self.reference(element, 'third person unit')
        if fp_path is not None and tp_path is not None:
            return fp_path.Filename, tp_path.Filename, allowed_fp_region_perms
