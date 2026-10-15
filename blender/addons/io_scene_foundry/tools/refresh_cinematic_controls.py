from pathlib import Path
import bpy

from .. import utils

from ..tags.cinematic_root import NativeCinematicTag
from ..tags.cinematic_debug import LOOP_VARIABLE, h3_debug_commands

REACH_LOOP_IT_WORKS = False

def new_command(command_name: str, command: str):
    return f'<item type = command name = "{command_name}" variable = "{command}">\n'

def add_controls_to_debug_menu(corinth: bool, cinematic_path: Path, scene_name, shot_index) -> bool:
    # All controls use existing engine globals; no mission source is installed.
    menu_commands = []
    cin_name = cinematic_path.with_suffix("").name
    h3 = utils.get_game() in {'halo3', 'halo3odst'}
    playback_suffix = ' (fade_in 0 0 0 0) (cinematic_show_letterbox_immediate 0)' if h3 else ''
    scene_index = -1
    with NativeCinematicTag(path=cinematic_path) as cinematic:
        for index, (scene, _) in enumerate(cinematic.scene_references()):
            if scene is not None and scene_name == scene.ShortName:
                scene_index = index
                break
                
        if scene_index == -1:
            return False

        if h3:
            # current_shot_index is already one-based; 0 means no active marker.
            shot_index = max(1, shot_index)
            try:
                h3_commands = h3_debug_commands(cinematic, scene_name, shot_index)
                # Quote loop_it strings inside the debug menu's variable attribute.
                h3_commands = {kind: command.replace('"', '\\"')
                               for kind, command in h3_commands.items()}
            except (OSError, ValueError, RuntimeError) as error:
                utils.print_warning(f'Failed to update H3/ODST cinematic controls: {error}')
                return False

        if corinth:
            bsp_zone_flags = cinematic.playback_bsp_zone_flags()
        
        # PLAY CINEMATIC
        command_name = f"Foundry: Start {cin_name}"
        if h3:
            command = h3_commands['cinematic']
        elif corinth:
            command = f'cinematic_debug_play \\"{cin_name}\\" \\"\\" cache_file_builder_unshare_unique_map_locations {bsp_zone_flags}'
        else:
            body = f'({cin_name}_debug){playback_suffix}'
            if REACH_LOOP_IT_WORKS:
                command = f'(loop_clear) (if cache_file_builder_unshare_unique_map_locations (loop_it {{{body}}}) {body})'
            else:
                command = f'(loop_clear) {body}'
        menu_commands.append(new_command(command_name, command))
        
        if scene_name:
            # PLAY SCENE
            command_name = f"Foundry: Start Scene {scene_name}"
            if h3:
                command = h3_commands['scene']
            elif corinth:
                command = f'cinematic_debug_play \\"{cin_name}\\" \\"1 {scene_index} 0\\" cache_file_builder_unshare_unique_map_locations {bsp_zone_flags}'
            else:
                body = f'(begin_{cin_name}_debug) (!{scene_name}) (end_{cin_name}_debug){playback_suffix}'
                if REACH_LOOP_IT_WORKS:
                    command = f"(loop_clear) (if cache_file_builder_unshare_unique_map_locations (loop_it {{(begin {body})}}) (begin {body}))"
                else:
                    command = f'(loop_clear) {body}'
            
            menu_commands.append(new_command(command_name, command))
            
            # PLAY SHOT
            command_name = f"Foundry: Start Scene {scene_name} Shot {shot_index}"
            if h3:
                command = h3_commands['shot']
            elif corinth:
                command = f'cinematic_debug_play \\"{cin_name}\\" \\"1 {scene_index} 1 {shot_index}\\" cache_file_builder_unshare_unique_map_locations {bsp_zone_flags}'
            else:
                body = f'(begin_{cin_name}_debug) (cinematic_print \\"beginning scene {scene_index + 1}\\") (cinematic_scripting_create_scene {scene_index}) ({scene_name}_sh{shot_index}) (cinematic_scripting_destroy_scene {scene_index}) (end_{cin_name}_debug){playback_suffix}'
                if REACH_LOOP_IT_WORKS:
                    command  = f'(loop_clear) (if cache_file_builder_unshare_unique_map_locations (loop_it {{(begin {body})}}) (begin {body}))'
                else:
                    command = f'(loop_clear) {body}'
            menu_commands.append(new_command(command_name, command))
            
        # PAUSE
        if corinth:
            command_name = "Foundry: Play/Pause"
            command = "cinematic_pause"
            menu_commands.append(new_command(command_name, command))
        
        # STOP
        command_name = f"Foundry: Stop"
        if h3:
            command = h3_commands['stop']
        elif corinth:
            command = "cinematic_debug_stop"
        else:
            command = f"(loop_clear) (end_{cin_name}_debug)"
        menu_commands.append(new_command(command_name, command))
        
        # STEP
        if corinth:
            command_name = "Foundry: Step One Frame"
            command = "cinematic_step_one_frame"
            menu_commands.append(new_command(command_name, command))

        # LOOP
        if h3 or corinth or REACH_LOOP_IT_WORKS:
            if h3:
                loop_command = f'<item type = global name = "Foundry: Loop (0 Off / 1 On)" inc = 1 min = 0 max = 1 variable = "{LOOP_VARIABLE}">\n'
            else:
                loop_command = '<item type = global name = "Foundry: Loop" variable = "cache_file_builder_unshare_unique_map_locations">\n'
            menu_commands.append(loop_command)
            
            
    menu_path = Path(utils.get_project_path(), 'bin', 'debug_menu_user_init.txt')
    valid_lines = None
    # Read first so we can keep the users existing commands
    if menu_path.exists():
        with open(menu_path, 'r') as menu:
            existing_menu = menu.readlines()
            # Strip out Cinematic commands. These get rebuilt in the next step
            valid_lines = [line for line in existing_menu if not '"Foundry: ' in line]
            
    with open(menu_path, 'w') as menu:
        if valid_lines is not None:
            menu.writelines(valid_lines)
            
        menu.writelines([str(cmd) for cmd in menu_commands])
        
    return True
        
class NWO_OT_RefreshCinematicControls(bpy.types.Operator):
    bl_idname = "nwo.refresh_cinematic_controls"
    bl_label = "Refresh Cinematic Controls"
    bl_description = "Rewrites the current set of cinematic controls using the current scene state (current cinematic, current cinematic scene, current shot). Reparse the debug menu [debug_menu_rebuild] to see changes in game"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_scene_props().asset_type == 'cinematic' and utils.valid_nwo_asset(context)

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.is_child_asset:
            asset_path = scene_nwo.parent_asset
        else:
            asset_path = utils.get_asset_path()
            
        asset_name = Path(asset_path).name
        
        scene_name = f"{asset_name}_{utils.get_asset_name()}" if scene_nwo.is_child_asset else f"{asset_name}_000"
        shot_index = utils.current_shot_index(context)
        if add_controls_to_debug_menu(utils.is_corinth(context), Path(asset_path, asset_name).with_suffix(".cinematic"), scene_name, shot_index):
            if utils.get_game() in {'halo3', 'halo3odst'}:
                self.report({'INFO'}, f"Updated cinematic controls: [Cinematic: {asset_name}], [Scene: {scene_name}], [Shot: {max(1, shot_index)}]. Run debug_menu_rebuild to refresh the menu",)
            else:
                self.report({'INFO'}, f"Updated debug menu with cinematic controls: [Cinematic: {asset_name}], [Scene: {scene_name}], [Shot: {shot_index + 1}]",)
            return {"FINISHED"}
        else:
            self.report({'WARNING'}, "Failed to update debug menu",)
            return {"CANCELLED"}
