from enum import Enum
import bpy
from .. import icons
from .. import utils
from ..project import GAME_INFO

class NWOAsset:
    def __init__(self, internal_name: str, display_name: str, icon: str, corinth_only: bool, description="") -> None:
        self.internal_name = internal_name
        self.display_name = display_name
        self.icon_name = icon
        self.corinth_only = corinth_only
        self.description = description
        
    @property
    def icon(self):
        if self.icon_name.upper() == self.icon_name:
            return self.icon_name
        return icons.get_icon_id(self.icon_name)
    
model_description = "Models are objects that can be placed down in scenarios.\n\nThey must always have a render model, but can optionally have collision and physics models, as well as animation graphs.\n\nModels may be generated as a variety of high level tags, such as scenery, vehicles, weapons etc"
scenario_description = "Scenarios are playable levels. They are made up of BSPs which make up the level geometry for the scenario"
sky_description = "Skies are used for scenarios as a skybox.\n\nThey may contain lights which can be used when lightmapping a scenario. Skies contain only render geometry"
decorator_set_description = "Decorator sets are used as paint brushes in scenarios.\n\nThey are made up of a set of render geometry that can then be painted onto scenario geometry"
particle_model_description = "Particle models are used for particle emitters in effect tags"
polyart_description = "Polyart is lightweight UI and effects geometry for Halo 4 and Halo 2 Anniversary Multiplayer. Each Foundry region exports to its own polyart_asset tag"
animation_description = "Animation graphs enable animations to play on objects.\n\nUnlike the model asset type, this type only generates an animation graph.\n\nUse this if you are creating first person animations or standalone animations"
camera_track_set_description = "Camera tracks represent the position of a third person camera on a unit (such as a vehicle) at different look angles"
resource_description = "Resource assets cannot be exported but offer access to all object/mesh/marker types and tools.\n\nThey are designed to contain data (such as materials of meshes) that can then be referenced in other scenes"
cinematic_description = "Create cinematic scenes with camera shots and animated actors"
prefab_description = "Prefabs act like standalone bits of instanced geometry that can be referenced in BSPs.\n\nTo reference a prefab in a Scenario asset, add a Game Object Marker and add the relative tag path to your the tag path field"
single_animation_description = "Exports a single gr2 with the same name as this blend file. Animation properties can be found in the asset editor panel. Does not use the animation action track system to load actions, just exports animations as is. What you see is what you get"
multi_model_description = "Exports a crate tag for each collection that is a direct child of the scene collection (excluding collections that have been set to a halo collection type). The name of the asset created will match the name of collection, with any '.' characters replaced by '_'\nThis asset type does not support lights"
multi_prefab_description = "Exports a prefab tag for each collection that is a direct child of the scene collection (excluding collections that have been set to a halo collection type). The name of the asset created will match the name of collection, with any '.' characters replaced by '_'\nThis asset type does not support lights"
  
model = NWOAsset("model", "Model", "model", False, model_description)
scenario = NWOAsset("scenario", "Scenario", "scenario", False, scenario_description)
sky = NWOAsset("sky", "Sky", "sky", False, sky_description)
decorator_set = NWOAsset("decorator_set", "Decorator Set", "decorator", False, decorator_set_description)
particle_model = NWOAsset("particle_model", "Particle Model", "particle_model", False, particle_model_description)
polyart = NWOAsset("polyart", "Polyart", "MESH_DATA", True, polyart_description)
animation = NWOAsset("animation", "Animation Graph", "animation", False, animation_description)
camera_track_set = NWOAsset("camera_track_set", "Camera Track Set", 'CON_CAMERASOLVER', False, camera_track_set_description)
resource = NWOAsset("resource", "Resource", "LINKED", False, resource_description)
cinematic = NWOAsset("cinematic", "Cinematic", "VIEW_CAMERA_UNSELECTED", False, cinematic_description)
prefab = NWOAsset("prefab", "Prefab", "prefab", True, prefab_description)
single_animation = NWOAsset("single_animation", "Single Animation", "ACTION", False, single_animation_description)
multi_model = NWOAsset("multi_model", "Crates", "crate", False, multi_model_description)
multi_prefab = NWOAsset("multi_prefab", "Multiple Prefabs", "prefab", True, multi_prefab_description)

asset_types = [model, scenario, sky, decorator_set, particle_model, animation, camera_track_set, resource, cinematic, prefab, single_animation, multi_model, multi_prefab, polyart]

OBJECT_TYPE_DESCRIPTIONS = {
    'scenery': 'Decorative objects placed in a level, such as rocks, trees, and buildings',
    'crate': 'Physical props that can move and react to collisions, such as boxes and barrels',
    'biped': 'Characters used by players or AI, such as soldiers and other walking units',
    'creature': 'Ambient creatures, such as small animals',
    'device_control': 'Interactive controls, such as switches and buttons that operate other devices',
    'device_machine': 'Moving level machinery, such as doors, elevators, and platforms',
    'device_terminal': 'Interactive terminals and displays',
    'device_dispenser': 'Devices that dispense items',
    'effect_scenery': 'Objects used to place effects in a level',
    'equipment': 'Equipment items that can be picked up or used',
    'giant': 'Large animated units, such as a Scarab',
    'vehicle': 'Vehicles that characters can drive, ride, or occupy',
    'weapon': 'Weapons that characters can carry and use',
    'custom': 'Choose the output tag types yourself in Optional setup. A model can generate more than one object tag type',
}

# Support means a usable Foundry asset workflow, not merely existence of a
# similarly named engine tag. Keep in sync with export/legacy.py:write_tags.
# Camera tracks bypass that writer; resources intentionally do not export.
_COMMON_ASSETS = frozenset({
    'model', 'sky', 'animation', 'single_animation', 'camera_track_set', 'resource',
})
_HALO3_ASSETS = _COMMON_ASSETS | {
    'scenario', 'decorator_set', 'particle_model', 'cinematic', 'multi_model',
}
_REACH_ASSETS = frozenset(a.internal_name for a in asset_types if not a.corinth_only)
_ALL_ASSETS = frozenset(a.internal_name for a in asset_types)
SUPPORTED_ASSETS = {
    'halo1': _COMMON_ASSETS | {'scenario'},
    'halo2': _COMMON_ASSETS | {'scenario', 'particle_model', 'decorator_set'},
    'halo3': _HALO3_ASSETS,
    'halo3odst': _HALO3_ASSETS,
    'reach': _REACH_ASSETS,
    'halo4': _ALL_ASSETS,
    'halo2a': _ALL_ASSETS,
}

# Blender requires callback enum strings to remain alive after the callback.
_asset_type_item_cache = {}


def _asset_type_items_for_game(game):
    supported = SUPPORTED_ASSETS.get(game, _ALL_ASSETS)
    game_name = GAME_INFO[game][1] if game in GAME_INFO else game
    items = []
    for i, asset in enumerate(asset_types):
        unsupported = asset.internal_name not in supported
        suffix = f' (NOT SUPPORTED FOR {game_name})' if unsupported else ''
        description = asset.description
        if unsupported:
            description += f'\n\nFoundry does not currently support this asset workflow for {game_name}.'
        items.append((asset.internal_name, asset.display_name + suffix,
                      description, asset.icon, i))
    key = (game, tuple(item[3] for item in items))
    return _asset_type_item_cache.setdefault(key, items)


def asset_type_items(self, context):
    project = utils.get_project(use_external=False)
    return _asset_type_items_for_game(project.game if project else 'reach')

def asset_type_items_creator(self, context):
    project = utils.get_project(self.project, use_external=False)
    if project is None:
        return asset_type_items(self, context)
    return _asset_type_items_for_game(project.game)


def _asset_type_game(target):
    project = utils.get_project(getattr(target, 'project', None), use_external=False)
    return project.game if project else 'reach'


def draw_asset_type_menu(layout, target):
    # Keep the full enum for saved files; only filter the choices in the UI.
    # The pointer also targets the pending New Asset operator in the file browser.
    row = layout.row()
    row.context_pointer_set('nwo_asset_type_target', target)
    item = next((item for item in _asset_type_items_for_game(_asset_type_game(target))
                 if item[0] == target.asset_type), None)
    if item is None:
        row.menu('NWO_MT_AssetType', text='Asset Type')
    elif isinstance(item[3], str):
        row.menu('NWO_MT_AssetType', text=item[1], icon=item[3])
    else:
        row.menu('NWO_MT_AssetType', text=item[1], icon_value=item[3])


class NWO_OT_SetAssetType(bpy.types.Operator):
    bl_idname = 'nwo.set_asset_type'
    bl_label = 'Set Asset Type'
    bl_options = {'UNDO', 'INTERNAL'}

    asset_type: bpy.props.StringProperty(options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        return next((asset.description for asset in asset_types
                     if asset.internal_name == properties.asset_type), '')

    def execute(self, context):
        target = getattr(context, 'nwo_asset_type_target', None)
        if target is None:
            return {'CANCELLED'}
        supported = SUPPORTED_ASSETS.get(_asset_type_game(target), _ALL_ASSETS)
        if self.asset_type not in supported:
            return {'CANCELLED'}
        target.asset_type = self.asset_type
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class NWO_MT_AssetType(bpy.types.Menu):
    bl_label = 'Asset Type'

    def draw(self, context):
        target = getattr(context, 'nwo_asset_type_target', None)
        if target is None:
            return
        supported = SUPPORTED_ASSETS.get(_asset_type_game(target), _ALL_ASSETS)
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        for asset in asset_types:
            if asset.internal_name not in supported:
                continue
            icon = asset.icon
            icon_args = {'icon': icon} if isinstance(icon, str) else {'icon_value': icon}
            props = layout.operator('nwo.set_asset_type', text=asset.display_name,
                                    **icon_args)
            props.asset_type = asset.internal_name

class AssetType(Enum):
    MODEL = 0
    SCENARIO = 1
    SKY = 2
    DECORATOR_SET = 3
    PARTICLE_MODEL = 4
    ANIMATION = 5
    CAMERA_TRACK_SET = 6
    RESOURCE = 7
    CINEMATIC = 8
    PREFAB = 9
    SINGLE_ANIMATION = 10
    MULTI_MODEL = 11
    MULTI_PREFAB = 12
    POLYART = 13
    
    @property
    def supports_permutations(self):
        return self.value in {0, 1, 2, 9, 11, 12}
    
    @property
    def supports_animations(self):
        return self.value in {0, 5, 8}
    
    @property
    def supports_bsp(self):
        return self.value in {1, 9, 12}
    
    @property
    def supports_global_materials(self):
        return self.value in {0, 1, 9, 11, 12}
    
    @property
    def supports_regions(self):
        return self.value in {0, 2, 11, 13}
