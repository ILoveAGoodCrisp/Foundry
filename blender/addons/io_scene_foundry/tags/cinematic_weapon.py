"""Weapon-bearing cinematic attachments for Halo 3 and ODST."""
from pathlib import Path

from .backend import TagDocument


CINEMATIC_BIPED = Path('objects/cinematics/cinematic_biped/cinematic_biped.biped')
TEMPLATES = Path(__file__).parent / 'templates' / 'cinematic_biped'


def cinematic_weapon_attachment(weapon, *, tags_root, game, definitions=None):
    """Reuse a biped with exactly the selected weapon in its primary slot."""
    if game not in {'halo3', 'halo3odst'}:
        return weapon
    weapon = Path(getattr(weapon, 'RelativePathWithExtension', weapon))
    if weapon.suffix.lower() != '.weapon':
        return weapon
    path = CINEMATIC_BIPED.with_name(f'cinematic_biped_{weapon.stem}.biped')
    with TagDocument(path, tags_root=tags_root, game=game, definitions=definitions) as biped:
        if biped.read_only:
            raise RuntimeError('Cannot create cinematic weapon attachments during a read-only operation')
        if biped.tag_is_new:
            template = biped.tags_root / CINEMATIC_BIPED
            if not template.is_file():
                template = TEMPLATES / CINEMATIC_BIPED.name
            biped._tag = biped.api.TagFile.read(template)

        unit = biped.required_field(biped.tag.root(), 'unit').as_struct()
        weapons = biped.block(unit, 'weapons')
        selected = biped.reference_from_path(weapon)
        if len(weapons) != 1 or biped.reference(weapons[0], 'weapon') != selected:
            weapons.clear()
            biped.set_reference(weapons[weapons.add()], 'weapon', selected)
            biped.tag_has_changes = True

        # The supplied template uses these shared model files. Keep project edits
        # and custom templates; install only missing dependencies of this model.
        obj = biped.required_field(unit, 'object').as_struct()
        model = biped.reference(obj, 'model')
        if model == biped.reference_from_path(CINEMATIC_BIPED.with_suffix('.model')):
            for extension in ('.model', '.render_model', '.model_animation_graph'):
                destination = biped.tags_root / CINEMATIC_BIPED.with_suffix(extension)
                if not destination.is_file():
                    source = TEMPLATES / destination.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    biped.api.TagFile.read(source).write_atomic(destination)
    return path
