"""UI that exists in the 3d viewport"""

import bpy

from ..icons import get_icon_id

from ..tools.property_apply import apply_prefix, apply_props_material
from .. import utils

from ..constants import VALID_MESHES 

class NWO_MT_PIE_ApplyTypeMesh(bpy.types.Menu):
    bl_label = "Mesh Type"
    bl_idname = "NWO_MT_PIE_ApplyTypeMesh"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        pie.operator_enum("nwo.apply_type_mesh", "m_type")


class NWO_PIE_ApplyTypeMesh(bpy.types.Operator):
    bl_label = "Apply Mesh Type"
    bl_idname = "nwo.apply_types_mesh_pie"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(self, context):
        asset_type = context.scene.nwo.asset_type
        return asset_type in ("model", "scenario", "prefab")

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="NWO_MT_PIE_ApplyTypeMesh")

        return {"FINISHED"}


class NWO_OT_ApplyTypeMesh(bpy.types.Operator):
    bl_label = "Apply Mesh Type"
    bl_idname = "nwo.apply_type_mesh"
    bl_description = "Applies the specified mesh type to the selected objects"
    bl_options = {"REGISTER", "UNDO"}
    
    convert_mesh: bpy.props.EnumProperty(
        options={'SKIP_SAVE'},
        name="Convert Mesh",
        description="Converts a mesh to a bounding box or convex hull",
        items=[
            ("keep", "Keep", "Keeps the current mesh"),
            ("convex_hull", "Convex Hull", "Convert mesh to a convex hull"),
            ("bounding_box", "Bounding Box", "Convert mesh to its bounding box"),
        ]
    )

    def m_type_items(self, context):
        items = []
        nwo = context.scene.nwo
        asset_type = nwo.asset_type
        h4 = utils.is_corinth(context)
        index = 0
        if asset_type == 'model' or asset_type == 'resource':
            # index += 1
            items.append(
                utils.nwo_enum(
                    "render", "Render", "Render only geometry", "render_geometry", index
                )
            )
            index += 1
            items.append(
                utils.nwo_enum(
                    "collision",
                    "Collision",
                    "Collision only geometry. Bullets always collide with this mesh. If this mesh is static (cannot move) and does not have a physics model, the collision model will also interact with physics objects such as the player. Must use bone parenting of have each vertex weighted to only a single vertex group if parented to an armature",
                    "collider",
                    index,
                )
            ),
            index += 1
            items.append(
                utils.nwo_enum(
                    "physics",
                    "Physics",
                    "Physics only geometry. Uses havok physics to interact with static and dynamic objects. Must be bone parented / weighted to only one vertex group if parented to an armature",
                    "physics",
                    index,
                )
            ),
            index += 1
            items.append(
                utils.nwo_enum(
                    "io",
                    "Instanced Object",
                    "Instanced render only geometry. Supports assignment to multiple permutations. Must be bone parented / weighted to only one vertex group if parented to an armature",
                    "instance",
                    index,
                )
            ),
        if asset_type == 'scenario' or asset_type == 'resource':
            # index += 1
            items.append(
                utils.nwo_enum(
                    "instance",
                    "Instance",
                    "Geometry capable of cutting through structure mesh. Can be instanced. Provides render, collision, and physics",
                    "instance",
                    index,
                )
            ),
            if h4:
                descrip = "Defines the bounds of the BSP. Is always sky mesh and therefore has no render or collision geometry. Use the proxy instance option to add render/collision geometry"
            else:
                descrip = "Defines the bounds of the BSP. By default acts as render, collision and physics geometry"
            index += 1
            items.append(
                utils.nwo_enum("structure", "Structure", descrip, "structure", index)
            )
            index += 1
            items.append(
                utils.nwo_enum(
                    "seam",
                    "Seam",
                    "Allows visibility and traversal between two or more bsps. Requires zone sets to be set up in the scenario tag",
                    "seam",
                    index,
                )
            )
            index += 1
            items.append(
                utils.nwo_enum(
                    "portal",
                    "Portal",
                    "Planes that cut through structure geometry to define clusters. Used for defining visiblity between different clusters",
                    "portal",
                    index,
                )
            )
            index += 1
            items.append(
                utils.nwo_enum(
                    "water_surface",
                    "Water Surface",
                    "Plane which can cut through geometry to define a water surface, optionally with water physics if the depth is greater than 0. If not material is set on this mesh, it will not render. Additionally the shader/material tag used must explictly support water surfaces. Water physics allows material effects to play when projectiles strike this mesh. Underwater fog atmosphere will be used when the player is inside the volume (this appears broken in H4)",
                    "water",
                    index,
                )
            )
            index += 1
            items.append(
                utils.nwo_enum(
                    "boundary_surface",
                    "Boundary Surface",
                    "Surfaces which prevent the player leaving the intended playspace",
                    "soft_ceiling",
                    index,
                )
            )
            if h4:
                # stream_des = """Defines the region in a zone set that should be used when generating a streamingzoneset tag. By default the full space inside a zone set will be used when generating the streaming zone set tag. This tag tells the game to only generate the tag within the bounds of this volume.\nThis is useful for performance if you have textures in areas of the map the player will not get close to"""
                index += 1
                items.append(
                    utils.nwo_enum("obb_volume", "Bounding Box", "Bounding box which assigns special properties to the geometry inside of it", "obb_volume", index)
                )
            else:
                index += 1
                items.append(
                    utils.nwo_enum(
                        "rain_blocker",
                        "Rain Blocker Volume",
                        "Blocks rain from rendering in the region this volume occupies",
                        "rain_blocker",
                        index,
                    )
                )
                index += 1
                items.append(
                    utils.nwo_enum(
                        "rain_sheet",
                        "Rain Sheet",
                        "A plane which blocks all rain particles that hit it. Regions under this plane will not render rain",
                        "rain_sheet",
                        index,
                    )
                ),
                index += 1
                items.append(
                    utils.nwo_enum(
                        "cookie_cutter",
                        "Pathfinding Cutout Volume",
                        "Cuts out the region this volume defines from the ai navigation mesh. Helpful in cases that you have ai pathing issues in your map",
                        "cookie_cutter",
                        index,
                    )
                )
                index += 1
                items.append(
                    utils.nwo_enum(
                        "fog",
                        "Fog",
                        "Defines an area in a cluster which renders fog defined in the scenario tag",
                        "fog",
                        index,
                    )
                )
        elif asset_type == 'prefab':
            # index += 1
            items.append(
                utils.nwo_enum(
                    "instance",
                    "Instance",
                    "Geometry capable of cutting through structure mesh. Can be instanced. Provides render, collision, and physics",
                    "instance",
                    index,
                )
            ),
            index += 1
            items.append(
                utils.nwo_enum(
                    "collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    "collider",
                    index,
                )
            ),
            index += 1
            items.append(
                utils.nwo_enum(
                    "lightmap_only",
                    "Lightmap Only",
                    "Non-collidable mesh that is used by the lightmapper to calculate lighting & shadows, but otherwise invisible",
                    "lightmap",
                    index,
                )
            )

        return items

    m_type: bpy.props.EnumProperty(
        items=m_type_items,
    )
    
    apply_material: bpy.props.BoolProperty(
        name="Apply Material",
        description="Applies a new material to the object to represent its type",
        default=True,
    )
    
    apply_prefix: bpy.props.BoolProperty(
        name="Apply Prefix",
        description="Applies a prefix to the object name to represent its type",
        default=True,
    )
    
    @classmethod
    def description(cls, context, properties) -> str:
        items = cls.m_type_items(cls, context)
        enum = items[properties['m_type']]
        return enum[2]

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.prop(self, "m_type", text="Mesh Type")
        self.layout.prop(self, "convert_mesh", text="Convert Mesh", expand=True)
        if utils.get_prefs().apply_materials:
            self.layout.prop(self, "apply_material", text="Apply Material")
        
        if utils.get_prefs().apply_prefix != "none":
            self.layout.prop(self, "apply_prefix", text="Apply Prefix")

    def execute(self, context):
        apply_materials = utils.get_prefs().apply_materials
        prefix_setting = utils.get_prefs().apply_prefix
        original_selection = context.selected_objects
        original_active = context.object
        mesh_type, material = utils.mesh_and_material(self.m_type, context)

        meshes = [
            ob for ob in context.selected_objects
            if ob.type in VALID_MESHES
        ]
        for ob in meshes:
            utils.set_active_object(ob)
            ob.select_set(True)
            ob.data.nwo.mesh_type = mesh_type

            if self.apply_prefix:
                apply_prefix(ob, self.m_type, prefix_setting)

            if apply_materials and self.apply_material:
                apply_props_material(ob, material)
                
            if self.convert_mesh == "convex_hull":
                utils.to_convex_hull(ob)
            elif self.convert_mesh == "bounding_box":
                utils.to_bounding_box(ob)

            if self.m_type == "seam":
                closest_bsp = utils.closest_bsp_object(context, ob)
                if closest_bsp is not None:
                    ob.nwo.seam_back = utils.true_region(closest_bsp.nwo)
                    
            ob.select_set(False)

        self.report(
            {"INFO"}, f"Applied Mesh Type [{self.m_type}] to {len(meshes)} objects"
        )
        [ob.select_set(True) for ob in original_selection]
        utils.set_active_object(original_active)
        return {"FINISHED"}

class NWO_OT_ApplyTypeMeshSingle(NWO_OT_ApplyTypeMesh):
    bl_label = "Apply Mesh Type"
    bl_idname = "nwo.apply_type_mesh_single"
    bl_description = "Applies the specified mesh type to the active object"
    
    def execute(self, context):
        apply_materials = utils.get_prefs().apply_materials
        prefix_setting = utils.get_prefs().apply_prefix
        mesh_type, material = utils.mesh_and_material(self.m_type, context)
        ob = context.object
        ob.data.nwo.mesh_type = mesh_type

        apply_prefix(ob, self.m_type, prefix_setting)

        if apply_materials:
            apply_props_material(ob, material)

        if self.m_type == "seam":
            closest_bsp = utils.closest_bsp_object(context, ob)
            if closest_bsp is not None:
                ob.nwo.seam_back = utils.true_region(closest_bsp.nwo)

        return {"FINISHED"}

class NWO_MT_PIE_ApplyTypeMarker(bpy.types.Menu):
    bl_label = "Marker Type"
    bl_idname = "NWO_MT_PIE_ApplyTypeMarker"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        pie.operator_enum("nwo.apply_type_marker", "m_type")


class NWO_PIE_ApplyTypeMarker(bpy.types.Operator):
    bl_label = "Apply Marker Type"
    bl_idname = "nwo.apply_types_marker_pie"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(self, context):
        asset_type = context.scene.nwo.asset_type
        return asset_type in ("model", "sky", "scenario", "prefab")

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="NWO_MT_PIE_ApplyTypeMarker")

        return {"FINISHED"}


class NWO_OT_ApplyTypeMarker(bpy.types.Operator):
    bl_label = "Apply Marker Type"
    bl_idname = "nwo.apply_type_marker"
    bl_description = "Applies the specified marker type to the selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def m_type_items(self, context):
        items = []
        nwo = context.scene.nwo
        asset_type = nwo.asset_type
        reach = not utils.is_corinth(context)
        index = 0
        if asset_type in ("model", "sky", 'resource'):
            index += 1
            items.append(utils.nwo_enum("model", "Model Marker", "", "marker", index)),
            index += 1
            items.append(utils.nwo_enum("effects", "Effects", "", "effects", index)),

            if asset_type == "model" or asset_type == 'resource':
                index += 1
                items.append(utils.nwo_enum("garbage", "Garbage", "", "garbage", index)),
                index += 1
                items.append(utils.nwo_enum("hint", "Hint", "", "hint", index)),
                index += 1
                items.append(
                    utils.nwo_enum(
                        "pathfinding_sphere",
                        "Pathfinding Sphere",
                        "",
                        "pathfinding_sphere",
                        index,
                    )
                ),
                index += 1
                items.append(
                    utils.nwo_enum(
                        "physics_constraint",
                        "Physics Constaint",
                        "",
                        "physics_constraint",
                        index,
                    )
                ),
                index += 1
                items.append(utils.nwo_enum("target", "Target", "", "target", index)),
                if not reach:
                    index += 1
                    items.append(utils.nwo_enum("airprobe", "Air Probe", "", "airprobe", index)),

        if asset_type in ("scenario", "prefab", 'resource'):
            index += 1
            items.append(utils.nwo_enum("model", "Structure Marker", "", "marker", index)),
            index += 1
            items.append(
                utils.nwo_enum("game_instance", "Game Object", "", "game_object", index)
            ),
            if not reach:
                index += 1
                items.append(utils.nwo_enum("airprobe", "Air Probe", "", "airprobe", index)),
                index += 1
                items.append(
                    utils.nwo_enum("envfx", "Environment Effect", "", "environment_effect", index)
                ),
                index += 1
                items.append(utils.nwo_enum("lightcone", "Light Cone", "", "light_cone", index)),

        return items

    m_type: bpy.props.EnumProperty(
        items=m_type_items,
    )
    
    @classmethod
    def description(cls, context, properties) -> str:
        items = cls.m_type_items(cls, context)
        enum = items[properties['m_type']]
        return enum[2]

    def draw(self, context):
        self.layout.prop(self, "m_type", text="Marker Type")
        
    def get_marker_type(self):
        marker_type = "_connected_geometry_marker_type_none"
        display = ''
        match self.m_type:
            case "model":
                marker_type = "_connected_geometry_marker_type_model"
            case "effects":
                marker_type = "_connected_geometry_marker_type_effects"
            case "garbage":
                marker_type = "_connected_geometry_marker_type_garbage"
            case "hint":
                marker_type = "_connected_geometry_marker_type_hint"
            case "pathfinding_sphere":
                marker_type = "_connected_geometry_marker_type_pathfinding_sphere"
                display = 'SPHERE'
            case "physics_constraint":
                marker_type = "_connected_geometry_marker_type_physics_constraint"
            case "target":
                marker_type = "_connected_geometry_marker_type_target"
                display = 'SPHERE'
            case "game_instance":
                marker_type = "_connected_geometry_marker_type_game_instance"
            case "airprobe":
                marker_type = "_connected_geometry_marker_type_airprobe"
                display = 'SPHERE'
            case "envfx":
                marker_type = "_connected_geometry_marker_type_envfx"
            case "lightcone":
                marker_type = "_connected_geometry_marker_type_lightCone"
                
        return marker_type, display

    def execute(self, context):
        prefix_setting = utils.get_prefs().apply_prefix
        marker_type = ""
        original_selection = context.selected_objects
        original_active = context.object

        markers = [
            ob
            for ob in context.selected_objects
            if ob.type in ("MESH", "CURVE", "META", "SURFACE", "FONT", "EMPTY")
        ]

        for ob in markers:
            utils.set_active_object(ob)
            ob.select_set(True)
            nwo = ob.nwo
            nwo.marker_type = marker_type
            apply_prefix(ob, self.m_type, prefix_setting)
            ob.select_set(False)

        self.report(
            {"INFO"}, f"Applied Marker Type: [{self.m_type}] to {len(markers)} objects"
        )
        [ob.select_set(True) for ob in original_selection]
        utils.set_active_object(original_active)
        return {"FINISHED"}
    
class NWO_OT_ApplyTypeMarkerSingle(NWO_OT_ApplyTypeMarker):
    bl_label = "Apply Marker Type"
    bl_idname = "nwo.apply_type_marker_single"
    bl_description = "Applies the specified marker type to the active object"
    
    def execute(self, context):
        prefix_setting = utils.get_prefs().apply_prefix
        apply_display = utils.get_prefs().apply_empty_display
        ob = context.object
        nwo = ob.nwo
        nwo.marker_type, display_type = self.get_marker_type()
        if apply_display and display_type:
            ob.empty_display_type = display_type
        apply_prefix(ob, self.m_type, prefix_setting)
        return {"FINISHED"}
    
def object_context_apply_types(self, context):
    layout = self.layout
    asset_type = context.scene.nwo.asset_type
    layout.separator()
    selection_count = len(context.selected_objects)
    if selection_count > 1:
        layout.label(text=f'{selection_count} Halo Objects Selected', icon_value=get_icon_id('category_object_properties_pinned'))
    else:
        ob = context.object
        object_type = utils.get_object_type(ob, True)
        if object_type in ('Mesh', 'Marker'):
            if object_type == 'Mesh':
                type_name, type_icon = utils.get_mesh_display(ob.nwo.mesh_type)
            elif object_type == 'Marker':
                type_name, type_icon = utils.get_marker_display(ob.nwo.marker_type , ob)
            layout.label(text=f'Halo {object_type} ({type_name})', icon_value=type_icon)
        elif object_type == 'Frame':
            layout.label(text=f'Halo {object_type}', icon_value=get_icon_id('frame'))
        elif object_type == 'Light':
            layout.label(text=f'Halo {object_type}', icon='LIGHT')
        else:
            layout.label(text=f'Halo {object_type}')

    markers_valid = any([utils.is_marker(ob) for ob in context.selected_objects]) and asset_type in ('model', 'scenario', 'sky', 'prefab')
    meshes_valid = any([utils.is_mesh(ob) for ob in context.selected_objects]) and asset_type in ('model', 'scenario', 'prefab', 'sky')
    has_children = any([ob.children for ob in context.selected_objects])
    if markers_valid or meshes_valid:
        if meshes_valid:
            layout.operator_menu_enum("nwo.apply_type_mesh", property="m_type", text="Set Mesh Type", icon='MESH_CUBE')
            if has_children:
                layout.operator("nwo.mesh_to_marker", text="Convert to Frame", icon_value=get_icon_id('frame')).called_once = False
            else:
                layout.operator_menu_enum("nwo.mesh_to_marker", property="marker_type", text="Convert to Marker", icon='EMPTY_AXIS').called_once = False
        elif markers_valid:
            layout.operator_menu_enum("nwo.mesh_to_marker", property="marker_type", text="Set Marker Type", icon='EMPTY_AXIS').called_once = False
            
def object_context_sets(self, context):
    asset_type = context.scene.nwo.asset_type
    regions_valid = asset_type in ('model', 'sky', 'scenario')
    permutations_valid =  asset_type in ('model', 'sky', 'scenario', 'prefab')
    region_name = "BSP" if context.scene.nwo.asset_type == "scenario" else "Region" 
    permutation_name = "Layer" if context.scene.nwo.asset_type in ("scenario", "prefab") else "Permutation"
    layout = self.layout
    layout.separator()
    ob = context.object
    if not ob: return
    nwo = ob.nwo
    if regions_valid:
        row = layout.row()
        if nwo.region_name_locked:
            row.enabled = False
            row.label(text=f"{region_name}: " + utils.true_region(nwo), icon_value=get_icon_id("collection_creator"))
        else:
            row.menu("NWO_MT_RegionsSelection", text=f"{region_name}: " + utils.true_region(nwo), icon_value=get_icon_id("region"))
    
    if permutations_valid:
        row = layout.row()
        if nwo.permutation_name_locked:
            row.enabled = False
            row.label(text=f"{permutation_name}: " + utils.true_permutation(nwo), icon_value=get_icon_id("collection_creator"))
        else:
            row.menu("NWO_MT_PermutationsSelection", text=f"{permutation_name}: " + utils.true_permutation(nwo), icon_value=get_icon_id("permutation"))
            
    if ob.type == 'ARMATURE':
        row = layout.row()
        row.operator('nwo.convert_to_halo_rig', text='Convert to Halo Rig', icon='OUTLINER_OB_ARMATURE')
        
def collection_context(self, context):
    layout = self.layout
    coll = context.view_layer.active_layer_collection.collection
    is_scenario = context.scene.nwo.asset_type in ('scenario', 'prefab')
    if coll and coll.users:
        layout.separator()
        if coll.nwo.type == 'exclude':
            layout.label(text='Exclude Collection')
        elif coll.nwo.type == 'region':
            first_part = 'BSP Collection : ' if is_scenario else 'Region Collection : '
            layout.label(text=first_part + coll.nwo.region)
        elif coll.nwo.type == 'permutation':
            first_part = 'Layer Collection : ' if is_scenario else 'Permutation Collection : '
            layout.label(text=first_part + coll.nwo.permutation)

        layout.menu("NWO_MT_ApplyCollectionMenu", text="Set Halo Collection", icon_value=get_icon_id("collection"))
        
class NWO_CollectionManager(bpy.types.Panel):
    bl_label = "Collection Creator"
    bl_idname = "NWO_PT_CollectionManager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("collection_creator"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_collection_manager = scene.nwo_collection_manager

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_collection_manager, "collection_name", text="Name")
        col.prop(scene_nwo_collection_manager, "collection_type", text="Type")
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.collection_create")

def add_halo_join(self, context):
    self.layout.operator("nwo.join_halo", text="Halo Join")
    
def add_halo_scale_model_button(self, context):
    self.layout.operator(
        "nwo.add_scale_model",
        text="Halo Scale Model",
        icon_value=get_icon_id("biped"),
    )

def add_halo_armature_buttons(self, context):
    self.layout.operator("nwo.add_rig", text="Halo Armature", icon_value=get_icon_id("rig_creator"))

def create_halo_collection(self, context):
    self.layout.operator("nwo.collection_create" , text="", icon_value=get_icon_id("collection_creator"))