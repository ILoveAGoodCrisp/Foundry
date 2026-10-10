"""Expected renderer limitations stay in group documentation, not warnings."""


def engine_only_limit(game, family, category, option):
    """Suppress unavailable engine-buffer/simulation effects, not missing work."""
    if game == 'reach' and category == 'wetness':
        return True
    if category == 'specular' and option == 'modulate':
        return True  # Writes specular into the engine G-buffer.
    if category == 'blend_mode' and option in {'maximum', 'add_src_times_dstalpha'}:
        return True  # Needs destination framebuffer color/alpha.
    if game == 'reach':
        if family == 'shader_fur_stencil':
            return True  # Writes engine stencil bits rather than surface color.
        if family == 'shader_screen' and category == 'base' and option == 'normal_map_edge_stencil':
            return True
        if category == 'subsurface_scattering' and option == 'subsurface_scattering_prt':
            return True  # Requires the engine's precomputed transfer data.
        if family == 'shader_water':
            return option in {
                'waveshape': {'default'},
                'foam': {'auto', 'both'},
                'detail': {'repeat'},
                'global_shape': {'paint'},
            }.get(category, ())
    return False
