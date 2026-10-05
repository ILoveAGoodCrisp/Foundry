"""Legacy launcher capabilities from the editing kits' hs_doc.txt files.

Keep the menu and init.txt writer in agreement, including when settings saved
for a newer game are still enabled after switching projects.
"""

HALO3_PRUNING_COMMANDS = {
    "prune_globals": "prune_global",
    "prune_globals_keep_playable": "prune_global_keep_playable",
    "prune_globals_use_empty": "prune_global_use_empty",
    "prune_scenario_all_lightmaps": "prune_scenario_lightmaps",
    "prune_all_material_effects": "prune_scenario_material_effects",
    "prune_all_dialog_sounds": "prune_global_dialog_sounds",
    "prune_all_error_geometry": "prune_error_geometry",
}

LEGACY_PRUNING_COMMANDS = {
    "Halo1": {},
    "Halo2": {},
    "Halo3": HALO3_PRUNING_COMMANDS,
    "Halo3ODST": {
        **HALO3_PRUNING_COMMANDS,
        "prune_all_materials_use_gray_shader": "prune_scenario_use_gray_shader",
        "prune_scenario_force_solo_mode": "prune_scenario_force_solo_mode",
        "prune_scenario_force_single_bsp_zone_set": "prune_scenario_force_single_bsp_zone_set",
        "prune_scenario_force_single_bsp_zones": "prune_scenario_add_single_bsp_zones",
        "prune_scenario_for_environment_editing": "prune_scenario_for_environment_editing",
        "prune_scenario_for_environment_editing_keep_cinematics": "prune_scenario_for_environment_editing_keep_cinematics",
    },
}

LEGACY_SETTINGS = {
    "Halo1": frozenset({"custom_functions", "show_debugging", "run_game_scripts"}),
    "Halo2": frozenset({"custom_functions", "show_debugging", "run_game_scripts"}),
    "Halo3": frozenset({"use_play", "insertion_point_index", "initial_zone_set",
                        "custom_functions", "show_debugging", "run_game_scripts", "forge"}),
    "Halo3ODST": frozenset({"use_play", "insertion_point_index", "initial_zone_set",
                            "custom_functions", "show_debugging", "run_game_scripts"}),
}

LEGACY_DEBUG_COMMANDS = {
    "Halo1": ("events_enabled 0", "terminal_render 0"),
    "Halo2": ("error_geometry_hide_all", "ai_hide_actor_errors 1",
              "terminal_render 0", "console_status_string_render 0"),
    "Halo3": ("error_geometry_hide_all", "events_enabled 0", "ai_hide_actor_errors 1",
              "terminal_render 0", "console_status_string_render 0", "events_debug_spam_render 0"),
    "Halo3ODST": ("error_geometry_hide_all", "events_enabled 0", "ai_hide_actor_errors 1",
                  "terminal_render 0", "console_status_string_render 0", "events_debug_spam_render 0"),
}


def legacy_init_commands(game, settings, *, is_sapien, zone_set_index=None,
                         multiplayer=False, firefight=False):
    """Return only built-in commands supported by this legacy game."""
    commands = []
    for prop, command in LEGACY_PRUNING_COMMANDS[game].items():
        if prop == "prune_scenario_for_environment_editing_keep_cinematics":
            if not settings.prune_scenario_for_environment_editing:
                continue
        if getattr(settings, prop):
            commands.append(f"{command} 1")
    if not is_sapien:
        if game == "Halo3" and multiplayer and settings.forge:
            commands.append("game_multiplayer sandbox")
        elif game == "Halo3ODST" and firefight:
            commands.append("game_survival")
        commands.append(f"run_game_scripts {int(settings.run_game_scripts)}")
    if not settings.show_debugging:
        commands.extend(LEGACY_DEBUG_COMMANDS[game])
    if "initial_zone_set" in LEGACY_SETTINGS[game]:
        if zone_set_index is not None:
            commands.append(f"game_initial_zone_set {zone_set_index}")
        if settings.insertion_point_index > -1:
            commands.append(f"game_insertion_point_set {settings.insertion_point_index}")
    return commands
