"""Cache compilation formats and output locations for the MCC editing kits."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CacheProfile:
    output_folder: str
    arguments: tuple[str, ...]
    separate_sound_banks: bool = False

CACHE_PROFILES = {
    'halo1': CacheProfile('maps', ()),
    'halo2': CacheProfile('h2_maps_win64_dx11', ()),
    'halo3': CacheProfile('maps', ('pc',)),
    'halo3odst': CacheProfile('maps', ('pc',)),
    'reach': CacheProfile('maps', ('pc',), True),
    'halo4': CacheProfile('maps', ('pc',), True),
    'halo2a': CacheProfile('maps', ('pc',), True),
}

def cache_build_command(game, scenario, halo1_mode='classic'):
    profile = CACHE_PROFILES[game]
    if game == 'halo1':
        if halo1_mode not in {'classic', 'remastered'}:
            raise ValueError('Select Classic or Remastered for Halo 1 cache compilation')
        return ['build-cache-file', str(scenario), halo1_mode]
    return ['build-cache-file', str(scenario), *profile.arguments]
