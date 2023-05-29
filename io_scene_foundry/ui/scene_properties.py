# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

import os
from bpy.props import IntProperty, BoolProperty, EnumProperty, StringProperty, CollectionProperty
from bpy.types import PropertyGroup
import bpy

from . import poll_ui
from ..icons import get_icon_id
from ..utils.nwo_utils import get_ek_path, not_bungie_game

def game_version_warning(self, context):
    self.layout.label(text=f"Please set your editing kit path for {context.scene.nwo.game_version.upper()} in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset]")

def prefab_warning(self, context):
    self.layout.label(text=f"Halo Reach does not support prefab assets")

class NWO_Asset_ListItems(PropertyGroup):
    def GetSharedAssetName(self):
        name = self.shared_asset_path
        name = name.rpartition('\\')[2]
        name = name.rpartition('.sidecar.xml')[0]

        return name

    shared_asset_name: StringProperty(
        get=GetSharedAssetName,
    )

    shared_asset_path: StringProperty()

    shared_asset_types = [
            ('BipedAsset', 'Biped', ''),
            ('CrateAsset', 'Crate', ''),
            ('CreatureAsset', 'Creature', ''),
            ('Device_ControlAsset', 'Device Control', ''),
            ('Device_MachineAsset', 'Device Machine', ''),
            ('Device_TerminalAsset', 'Device Terminal', ''),
            ('Effect_SceneryAsset', 'Effect Scenery', ''),
            ('EquipmentAsset', 'Equipment', ''),
            ('GiantAsset', 'Giant', ''),
            ('SceneryAsset', 'Scenery', ''),
            ('VehicleAsset', 'Vehicle', ''),
            ('WeaponAsset', 'Weapon', ''),
            ('ScenarioAsset', 'Scenario', ''),
            ('Decorator_SetAsset', 'Decorator Set', ''),
            ('Particle_ModelAsset', 'Particle Model', ''),
        ]

    shared_asset_type: EnumProperty(
        name='Type',
        default='BipedAsset',
        options=set(),
        items=shared_asset_types
    )

class NWO_ScenePropertiesGroup(PropertyGroup):
    def check_paths_update_scene(self, context):
        ek_path = get_ek_path()
        if ek_path is None or ek_path == '':
            context.window_manager.popup_menu(game_version_warning, title="Warning", icon='ERROR')

        # store this value in a txt file so we can retrive it when changing scene
        temp_file_path = os.path.join(bpy.app.tempdir, 'game_version.txt')
        with open(temp_file_path, 'w') as temp_file:
            temp_file.write(f'{self.game_version}')

        scene = context.scene
        nwo_asset = scene.nwo
        if nwo_asset.asset_type == '' and self.game_version == 'reach':
            nwo_asset.asset_type = 'SCENARIO'

    def game_version_items(self, context):
        items = []   
        items.append(('reach', "Halo Reach", "Halo Reach", get_icon_id("halo_reach"), 0))
        items.append(('h4', "Halo 4", "Halo 4", get_icon_id("halo_4"), 1))
        items.append(('h2a', "Halo 2AMP", "Halo 2 Anniversary Multiplayer", get_icon_id("halo_2amp"), 2))
        return items
                
    game_version: EnumProperty(
        name="Game",
        options=set(),
        default=0,
        update=check_paths_update_scene,
        items=game_version_items,
    )
    
    mb_startup: BoolProperty(
        name="Run ManagedBlam on Startup",
        description="Runs ManagedBlam.dll on Blender startup, this will lock the selected game on startup. Disable and and restart blender if you wish to change the selected game.",
        )
    
    def get_temp_settings(self):
        scene = bpy.context.scene
        temp_file_path = os.path.join(bpy.app.tempdir, 'nwo_scene_settings.txt')
        if os.path.exists(temp_file_path):
            with open(temp_file_path, 'r') as temp_file:
                settings = temp_file.readlines()

            settings = [line.strip() for line in settings]
            scene.nwo_halo_launcher.sidecar_path = settings[0]
            scene.nwo.game_version = settings[1]
            scene.nwo.asset_type = settings[2]
            scene.nwo.output_biped = True if settings[3] == 'True' else False
            scene.nwo.output_crate = True if settings[4] == 'True' else False
            scene.nwo.output_creature = True if settings[5] == 'True' else False
            scene.nwo.output_device_control = True if settings[6] == 'True' else False
            scene.nwo.output_device_dispenser = True if settings[7] == 'True' else False
            scene.nwo.output_device_machine = True if settings[8] == 'True' else False
            scene.nwo.output_device_terminal = True if settings[9] == 'True' else False
            scene.nwo.output_effect_scenery = True if settings[10] == 'True' else False
            scene.nwo.output_equipment = True if settings[11] == 'True' else False
            scene.nwo.output_giant = True if settings[12] == 'True' else False
            scene.nwo.output_scenery = True if settings[13] == 'True' else False
            scene.nwo.output_vehicle = True if settings[14] == 'True' else False
            scene.nwo.output_weapon = True if settings[15] == 'True' else False
            scene.nwo_export.show_output = True if settings[16] == 'True' else False

            os.remove(temp_file_path)

        return False

    temp_file_watcher: BoolProperty(
        name = "",
        default = False,
        get=get_temp_settings,
        )
    shared_assets: CollectionProperty(
        type=NWO_Asset_ListItems,
    )

    shared_assets_index: IntProperty(
        name='Index for Shared Asset',
        default=0,
        min=0,
    )

    def items_mesh_type_ui(self, context):
        """Function to handle context for mesh enum lists"""
        h4 = not_bungie_game()
        items = []

        if poll_ui('DECORATOR SET'):
            items.append(('_connected_geometry_mesh_type_decorator', 'Decorator', 'Decorator mesh type. Supports up to 4 level of detail variants', get_icon_id("decorator"), 0))
        elif poll_ui(('MODEL', 'SKY', 'PARTICLE MODEL')):
            items.append(('_connected_geometry_mesh_type_render', 'Render', 'Render only geometry', get_icon_id("render_geometry"), 0))
            if poll_ui('MODEL'):
                items.append(('_connected_geometry_mesh_type_collision', 'Collision', 'Collision only geometry. Acts as bullet collision and for scenery also provides player collision', get_icon_id("collider"), 1))
                items.append(('_connected_geometry_mesh_type_physics', 'Physics', 'Physics only geometry. Uses havok physics to interact with static and dynamic meshes', get_icon_id("physics"), 2))
                # if not h4: NOTE removing these for now until I figure out how they work
                #     items.append(('_connected_geometry_mesh_type_object_instance', 'Flair', 'Instanced mesh for models. Can be instanced across mutliple permutations', get_icon_id("flair"), 3))
        elif poll_ui('SCENARIO'):
            items.append(('_connected_geometry_mesh_type_structure', 'Structure', 'Structure bsp geometry. By default provides render and bullet/player collision', get_icon_id("structure"), 0))
            items.append(('_connected_geometry_mesh_type_poop', 'Instance', 'Instanced geometry. Geometry capable of cutting through structure mesh', get_icon_id("instance"), 1))
            items.append(('_connected_geometry_mesh_type_poop_collision', 'Collision', 'Non rendered geometry which provides collision only', get_icon_id("collider"), 2))
            items.append(('_connected_geometry_mesh_type_plane', 'Plane', 'Non rendered geometry which provides various utility functions in a bsp. The planes can cut through bsp geometry. Supports portals, fog planes, and water surfaces', get_icon_id("surface"), 3))
            items.append(('_connected_geometry_mesh_type_volume', 'Volume', 'Non rendered geometry which defines regions for special properties', get_icon_id("volume"), 4))
        elif poll_ui('PREFAB'):
            items.append(('_connected_geometry_mesh_type_poop', 'Instance', 'Instanced geometry. Geometry capable of cutting through structure mesh', get_icon_id("instance"), 0))
            items.append(('_connected_geometry_mesh_type_poop_collision', 'Collision', 'Non rendered geometry which provides collision only', get_icon_id("collider"), 1))
            items.append(('_connected_geometry_mesh_type_cookie_cutter', 'Cookie Cutter', 'Non rendered geometry which cuts out the region it defines from the pathfinding grid', get_icon_id("cookie_cutter"), 2))
    
        return items
    
    default_mesh_type_ui: EnumProperty(
        name="Default Mesh Type",
        options=set(),
        description="Set the default Halo mesh type for new objects",
        items=items_mesh_type_ui,
        )
    
    def apply_props(self, context):
        for ob in context.scene.objects:
            ob_nwo = ob.nwo

            if ob_nwo.mesh_type_ui == '':
                if self.asset_type == 'DECORATOR SET':
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_decorator'
                elif self.asset_type == 'SCENARIO':
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_structure'
                elif self.asset_type == 'PREFAB':
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_poop'
                else:
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_render'

    def asset_type_items(self, context):
        items = []
        items.append(('MODEL', "Model", "", get_icon_id("model"), 0))
        items.append(('SCENARIO', "Scenario", "", get_icon_id("scenario"), 1))
        items.append(('SKY', 'Sky', '', get_icon_id("sky"), 2))
        items.append(('DECORATOR SET', 'Decorator Set', '', get_icon_id("decorator"), 3))
        items.append(('PARTICLE MODEL', 'Particle Model', '', get_icon_id("particle_model"), 4))
        items.append(('FP ANIMATION', 'First Person Animation', '', get_icon_id("animation"), 5))
        if context.scene.nwo.game_version != 'reach':
            items.append(('PREFAB', 'Prefab', '', get_icon_id("prefab"), 6))

        return items
    
    asset_type: EnumProperty(
        name="Asset Type",
        options=set(),
        description="Define the type of asset you are creating",
        items=asset_type_items,
        )
    
    forward_direction: EnumProperty(
        name="Model Forward",
        options=set(),
        description="Define the forward direction you are using for this model. By default Halo uses X forward. If you model is not x positive select the correct forward directiom.",
        default = 'x',
        items=[ ('x', "X Postive", ""), ('x-', "X Negative", ""), ('y', 'Y Postive', ''), ('y-', 'Y Negative', '')]
    )

    output_biped: BoolProperty(
        name='Biped',
        description='',
        default=False,
        options=set(),
    )
    output_crate: BoolProperty(
        name='Crate',
        description='',
        default=False,
        options=set(),
    )
    output_creature: BoolProperty(
        name='Creature',
        description='',
        default=False,
        options=set(),
    )
    output_device_control: BoolProperty(
        name='Device Control',
        description='',
        default=False,
        options=set(),
    )
    output_device_dispenser: BoolProperty(
        name='Device Dispenser',
        description='',
        default=False,
        options=set(),
    )
    output_device_machine: BoolProperty(
        name='Device Machine',
        description='',
        default=False,
        options=set(),
    )
    output_device_terminal: BoolProperty(
        name='Device Terminal',
        description='',
        default=False,
        options=set(),
    )
    output_effect_scenery: BoolProperty(
        name='Effect Scenery',
        description='',
        default=False,
        options=set(),
    )
    output_equipment: BoolProperty(
        name='Equipment',
        description='',
        default=False,
        options=set(),
    )
    output_giant: BoolProperty(
        name='Giant',
        description='',
        default=False,
        options=set(),
    )
    output_scenery: BoolProperty(
        name='Scenery',
        description='',
        default=True,
        options=set(),
    )
    output_vehicle: BoolProperty(
        name='Vehicle',
        description='',
        default=False,
        options=set(),
    )
    output_weapon: BoolProperty(
        name='Weapon',
        description='',
        default=False,
        options=set(),
    )