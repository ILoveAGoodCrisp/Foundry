"""Read-only cinematic environment resolution and actor animation matching."""
from dataclasses import dataclass
from pathlib import Path
import re

from .backend import TagDocument


def tag_path_key(path):
    return '/'.join(part for part in str(path).replace('\\', '/').split('/') if part).casefold()


def cinematic_animation_shots(animations, identifier, active_shots):
    """Match the actor identifier, not just the numeric suffix of a shared graph."""
    expected = {f'{identifier}_{shot + 1}'.casefold(): shot + 1 for shot in active_shots}
    matches = {}
    for index, name in animations:
        name = re.sub(r'\.\d{3,}$', '', name).casefold()
        shot = expected.get(name)
        if shot is not None:
            matches[shot] = index
    return matches


@dataclass(frozen=True)
class CinematicEnvironment:
    scenario: str | None
    zone_set: str = ''
    bsp_mask: int | None = None
    warning: str = ''


class CinematicImportDocument(TagDocument):
    def cinematic_indices(self, cinematic):
        root = self.tag.root()
        field = root.field('cinematics')
        target = tag_path_key(cinematic)
        return [i for i, entry in enumerate(field.as_block() if field is not None else ())
                if (ref := self.reference(entry, 'name')) is not None
                and tag_path_key(ref.RelativePathWithExtension) == target]

    def cinematic_environment(self, cinematic, requested_index=-1, recovered=False):
        root = self.tag.root()
        field = root.field('zone sets')
        zones = field.as_block() if field is not None else ()
        indices = self.cinematic_indices(cinematic)
        cinematic_mask = sum(1 << i for i in indices)
        matching = [i for i, zone in enumerate(zones)
                    if zone.field('cinematic zones') is not None
                    and int(self.value(zone, 'cinematic zones')) & cinematic_mask]
        # An index in a missing scenario cannot be assumed to index its replacement.
        if 0 <= requested_index < len(zones) and (not recovered or requested_index in matching):
            selected = [requested_index]
        else:
            selected = matching
        if not selected:
            return CinematicEnvironment(str(self.system_path), bsp_mask=0,
                warning=f'{self.path}: no zone set could be resolved for {cinematic}; skipping BSP import')
        mask = 0
        for index in selected:
            mask |= int(self.value(zones[index], 'bsp zone flags')) & 0xffffffff
        name = self.value(zones[selected[0]], 'name') if len(selected) == 1 else ''
        return CinematicEnvironment(str(self.system_path), name, mask)

    def resolve_environment(self, scenario_reference, zone_index):
        if self.path_exists(scenario_reference):
            with CinematicImportDocument(scenario_reference, tags_root=self.tags_root,
                    game=self.game, definitions=self.definitions, must_exist=True) as scenario:
                return scenario.cinematic_environment(self.path, zone_index)
        if scenario_reference is None:
            return CinematicEnvironment(None, warning=f'{self.path}: no scenario reference to resolve')
        directory = Path(scenario_reference.Filename).parent
        candidates = sorted(directory.glob('*.scenario'),
            key=lambda p: (p.stem.casefold() != directory.name.casefold(), p.name.casefold()))
        failures = []
        for candidate in candidates:
            try:
                with CinematicImportDocument(candidate, tags_root=self.tags_root,
                        game=self.game, definitions=self.definitions, must_exist=True) as scenario:
                    if scenario.cinematic_indices(self.path):
                        return scenario.cinematic_environment(self.path, zone_index, recovered=True)
            except (OSError, ValueError, RuntimeError) as error:
                failures.append(f'{candidate.name}: {error}')
        detail = '; '.join(failures)
        return CinematicEnvironment(None, warning=(
            f'{self.path}: no scenario in {directory} references this cinematic'
            + (f' ({detail})' if detail else '')))
