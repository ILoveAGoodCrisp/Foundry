from pathlib import Path
import bpy

from ..managed_blam.cinematic_scene import CinematicSceneTag

from .. import utils

from ..managed_blam.cinematic import CinematicTag

REACH_LOOP_IT_WORKS = False

def new_command(command_name: str, command: str):
    return f'<item type = command name = "{command_name}" variable = "{command}">\n'

def add_controls_to_debug_menu(context: bpy.types.Context, corinth: bool, cinematic_path: Path, scene_index, shot_index):
    # using cache_file_builder_unshare_unique_map_locations as a variable for looping. It is enabled by default in reach+
    menu_commands = []
    cin_name = cinematic_path.with_suffix("").name
    scene_name = ""
    scene_path = ""
    with CinematicTag(path=cinematic_path) as cinematic:
        if cinematic.scenes.Elements.Count > scene_index:
            element = cinematic.scenes.Elements[scene_index]
            path = element.Fields[0].Path
            if path is not None:
                scene_name = path.ShortName
                scene_path = path.RelativePathWithExtension
        
        if corinth:
            bsp_zone_flags = cinematic.tag.SelectField("Struct:cinematic playback[0]/LongInteger:bsp zone flags").Data
        # LOOP
        if corinth or REACH_LOOP_IT_WORKS:
            loop_command = '<item type = global name = "Cinematic: Loop" variable = "cache_file_builder_unshare_unique_map_locations">\n'
            menu_commands.append(loop_command)
        
        # PLAY CINEMATIC
        command_name = f"Cinematic: Start {cin_name}"
        if corinth:
            command = f'cinematic_debug_play \\"{cin_name}\\" \\"\\" cache_file_builder_unshare_unique_map_locations {bsp_zone_flags}'
        else:
            body = f'({cin_name}_debug)'
            if REACH_LOOP_IT_WORKS:
                command = f'(loop_clear) (if cache_file_builder_unshare_unique_map_locations (loop_it {{{body}}}) {body})'
            else:
                command = f'(loop_clear) {body}'
        menu_commands.append(new_command(command_name, command))
        
        if scene_name:
            # PLAY SCENE
            command_name = f"Cinematic: Start Scene {scene_name}"
            if corinth:
                command = f'cinematic_debug_play \\"{cin_name}\\" \\"1 {scene_index} 0\\" cache_file_builder_unshare_unique_map_locations {bsp_zone_flags}'
            else:
                body = f'(begin_{cin_name}_debug) (!{scene_name}) (end_{cin_name}_debug)'
                if REACH_LOOP_IT_WORKS:
                    command = f"(loop_clear) (if cache_file_builder_unshare_unique_map_locations (loop_it {{(begin {body})}}) (begin {body}))"
                else:
                    command = f'(loop_clear) {body}'
            
            menu_commands.append(new_command(command_name, command))
            
            # PLAY SHOT
            command_name = f"Cinematic: Start Scene {scene_name} Shot {shot_index + 1}"
            if corinth:
                command = f'cinematic_debug_play \\"{cin_name}\\" \\"1 {scene_index} 1 {shot_index}\\" cache_file_builder_unshare_unique_map_locations {bsp_zone_flags}'
            else:
                body = f'(begin_{cin_name}_debug) (cinematic_print \\"beginning scene {scene_index + 1}\\") (cinematic_scripting_create_scene {scene_index}) ({scene_name}_sh{shot_index + 1}) (cinematic_scripting_destroy_scene {scene_index}) (end_{cin_name}_debug)'
                if REACH_LOOP_IT_WORKS:
                    command  = f'(loop_clear) (if cache_file_builder_unshare_unique_map_locations (loop_it {{(begin {body})}}) (begin {body}))'
                else:
                    command = f'(loop_clear) {body}'
            menu_commands.append(new_command(command_name, command))
            
        # PAUSE
        if corinth:
            command_name = "Cinematic: Play/Pause"
            command = "cinematic_pause"
            menu_commands.append(new_command(command_name, command))
        
        # STOP
        command_name = f"Cinematic: Stop"
        if corinth:
            command = "cinematic_debug_stop"
        else:
            command = f"(loop_clear) (end_{cin_name}_debug)"
        menu_commands.append(new_command(command_name, command))
        
        # STEP
        if corinth:
            command_name = "Cinematic: Step One Frame"
            command = "cinematic_step_one_frame"
            menu_commands.append(new_command(command_name, command))
            
            
    menu_path = Path(utils.get_project_path(), 'bin', 'debug_menu_user_init.txt')
    valid_lines = None
    # Read first so we can keep the users existing commands
    if menu_path.exists():
        with open(menu_path, 'r') as menu:
            existing_menu = menu.readlines()
            # Strip out Cinematic commands. These get rebuilt in the next step
            valid_lines = [line for line in existing_menu if not '"Cinematic: ' in line]
            
    with open(menu_path, 'w') as menu:
        if valid_lines is not None:
            menu.writelines(valid_lines)
            
        menu.writelines([str(cmd) for cmd in menu_commands])
        
    return scene_name
        
class NWO_OT_RefreshCinematicControls(bpy.types.Operator):
    bl_idname = "nwo.refresh_cinematic_controls"
    bl_label = "Refresh Cinematic Controls"
    bl_description = "Rewrites the current set of cinematic controls using the current scene state (current cinematic, current cinematic scene, current shot). Remember to reparse the debug menu [debug_menu_rebuild] to see the changes in game"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.asset_type == 'cinematic' and utils.valid_nwo_asset(context)

    def execute(self, context):
        asset_path = utils.get_asset_path()
        asset_name = Path(asset_path).name
        scene_index = 0
        shot_index = utils.current_shot_index(context)
        scene_name = add_controls_to_debug_menu(context, utils.is_corinth(context), Path(asset_path, asset_name).with_suffix(".cinematic"), scene_index, shot_index)
        self.report({'INFO'}, f"Updated debug menu with cinematic controls: [Cinematic: {asset_name}], [Scene: {scene_name}], [Shot: {shot_index + 1}]",)
        return {"FINISHED"}
