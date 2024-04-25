# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

import bpy
from mathutils import Matrix
from io_scene_foundry.icons import get_icon_id

from io_scene_foundry.utils.nwo_utils import get_foundry_storage_scene, is_corinth, is_marker, is_mesh, poll_ui, set_active_object, unlink

class NWO_MeshToMarker(bpy.types.Operator):
    bl_idname = 'nwo.mesh_to_marker'
    bl_label = 'Convert to Marker'
    bl_description = 'Converts selected objects to markers'
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object
    
    def items_marker_type(self, context):
        h4 = is_corinth()
        items = []

        if poll_ui(("model", "sky")):
            items.append(
                (
                    "_connected_geometry_marker_type_model",
                    "Model Marker",
                    "Default marker type. Can be used as an attachment point for objects and effects",
                    get_icon_id("marker"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_marker_type_effects",
                    "Effects",
                    'Marker type which automatically gets "fx_" prepended to the marker name at export',
                    get_icon_id("effects"),
                    1,
                )
            )
            if poll_ui("model"):
                items.append(
                    (
                        "_connected_geometry_marker_type_garbage",
                        "Garbage",
                        "Marker for creating effects with velocity. Typically used for model damage sections",
                        get_icon_id("garbage"),
                        2,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_hint",
                        "Hint",
                        "This marker tells AI how to interact with parts of the model",
                        get_icon_id("hint"),
                        3,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_pathfinding_sphere",
                        "Pathfinding Sphere",
                        "Informs AI about how to path around this object. The sphere defines a region that AI should not enter",
                        get_icon_id("pathfinding_sphere"),
                        4,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_physics_constraint",
                        "Physics Constraint",
                        "Used for creating hinge and socket like contraints for objects. Allows object to have parts which react physically. For example creating a door which can be pushed open by the player, or a bipeds ragdoll",
                        get_icon_id("physics_constraint"),
                        5,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_target",
                        "Target",
                        "Used to specify an area on the model AI should target. Also used for checking whether a player is aiming at a target or not. Target properties are specified in the model tag",
                        get_icon_id("target"),
                        6,
                    )
                )
                if h4:
                    items.append(
                        (
                            "_connected_geometry_marker_type_airprobe",
                            "Airprobe",
                            "Airprobes store a representation of scenario lighting at their origins. Objects close to this airprobe will take its lighting values as their own. Helpful if an object is not being lit correctly in the scenario",
                            get_icon_id("airprobe"),
                            7,
                        )
                    )
        elif poll_ui("scenario"):
            items.append(
                (
                    "_connected_geometry_marker_type_model",
                    "Structure Marker",
                    "Default marker type. Can be used as an attachment point for objects in Sapien",
                    get_icon_id("marker"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_marker_type_game_instance",
                    'Game Object',
                    "Creates the specified tag at this point in the scenario",
                    get_icon_id('game_object'),
                    1,
                )
            )

            if h4:
                items.append(
                    (
                        "_connected_geometry_marker_type_envfx",
                        "Environment Effect",
                        "Marker which loops the specified effect",
                        get_icon_id("environment_effect"),
                        2,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_lightCone",
                        "Light Cone",
                        "Creates a light cone with the parameters defined",
                        get_icon_id("light_cone"),
                        3,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_marker_type_airprobe",
                        "Airprobe",
                        "Airprobes store a representation of scenario lighting at their origins. Objects close to this airprobe will take its lighting values as their own. Helpful if an object is not being lit correctly in the scenario",
                        get_icon_id("airprobe"),
                        4,
                    )
                )

        return items
    
    marker_type: bpy.props.EnumProperty(
        name='Marker Type',
        items=items_marker_type,
        options={'SKIP_SAVE'}
    )
    maintain_mesh: bpy.props.BoolProperty(
        description='Saves the object mesh to the blend and adds to an instanced collection linked to the new marker',
        options={'SKIP_SAVE'}
    )
    
    called_once: bpy.props.BoolProperty()
    
    meshes_selected: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        self.meshes_selected = any([is_mesh(ob) for ob in context.selected_objects])
        if not self.called_once and self.meshes_selected and self.marker_type == '_connected_geometry_marker_type_game_instance':
            self.maintain_mesh = True
        self.called_once = True
        to_convert = set()
        to_set = set()
        active_name = context.object.name
        for ob in context.selected_objects:
            if is_mesh(ob):
                to_convert.add(ob)
            elif is_marker(ob):
                to_set.add(ob)
                ob.select_set(False)
            else:
                ob.select_set(False)

        if not to_convert and not to_set:
            self.report({'INFO'}, 'No valid objects to convert')
            return {'CANCELLED'}

        for ob in to_convert:
            marker = convert_to_marker(ob, self.maintain_mesh)
            marker.select_set(False)
            to_set.add(marker)

        for ob in to_set:
            match self.marker_type:
                case '_connected_geometry_marker_type_model':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_model'
                    ob.empty_display_type = 'ARROWS'
                case '_connected_geometry_marker_type_effects':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_effects'
                    ob.empty_display_type = 'ARROWS'
                    ob.name = 'fx_' + ob.name
                case '_connected_geometry_marker_type_garbage':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_garbage'
                    ob.empty_display_type = 'ARROWS'
                case '_connected_geometry_marker_type_hint':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_hint'
                    ob.empty_display_type = 'ARROWS'
                case '_connected_geometry_marker_type_pathfinding_sphere':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_pathfinding_sphere'
                    ob.empty_display_type = 'SPHERE'
                case '_connected_geometry_marker_type_physics_constraint':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_physics_constraint'
                    ob.empty_display_type = 'ARROWS'
                case '_connected_geometry_marker_type_target':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_target'
                    ob.empty_display_type = 'SPHERE'
                case '_connected_geometry_marker_type_airprobe':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_airprobe'
                    ob.empty_display_type = 'SPHERE'
                case '_connected_geometry_marker_type_game_instance':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_game_instance'
                    ob.empty_display_type = 'ARROWS'
                case '_connected_geometry_marker_type_envfx':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_envfx'
                    ob.empty_display_type = 'ARROWS'
                case '_connected_geometry_marker_type_lightCone':
                    ob.nwo.marker_type_ui = '_connected_geometry_marker_type_lightCone'
                    ob.empty_display_type = 'ARROWS'
            if self.maintain_mesh and ob.instance_type == 'COLLECTION':
                ob.empty_display_type = 'PLAIN_AXES'
                ob.empty_display_size = 0.01
        
        bpy.ops.object.delete()
        
        [ob.select_set(True) for ob in to_set]
        new_active = bpy.data.objects.get(active_name, 0)
        if new_active:
            set_active_object(new_active)
        self.report({'INFO'}, f"Converted {len(to_set)} objects to markers")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if self.mesh_selected and self.marker_type == '_connected_geometry_marker_type_game_instance':
            self.maintain_mesh = True
        return self.execute(context)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'marker_type', text='Marker Type')
        if self.meshes_selected:
            layout.prop(self, 'maintain_mesh', text='Keep Mesh')
            

def convert_to_marker(ob: bpy.types.Object, maintain_mesh=False) -> bpy.types.Object:
    original_name = str(ob.name)
    ob.name += "_OLD"
    children = {child_ob: child_ob.matrix_world.copy() for child_ob in ob.children}
    original_collections = ob.users_collection
    marker = bpy.data.objects.new(original_name, None)
    for coll in original_collections:
        coll.objects.link(marker)
    if ob.parent is not None:
        marker.parent = ob.parent
        marker.parent_type = ob.parent_type
        if marker.parent_type == "BONE":
            marker.parent_bone = ob.parent_bone

    marker.matrix_world = ob.matrix_world
    marker.nwo.region_name_ui = ob.nwo.region_name_ui
    marker.nwo.permutation_name_ui = ob.nwo.permutation_name_ui
    marker.nwo.marker_uses_regions = ob.nwo.marker_uses_regions
    for perm in ob.nwo.marker_permutations:
        marker.nwo.marker_permutations.add().name = perm.name
        
    ob_length = max(ob.dimensions.x, ob.dimensions.y, ob.dimensions.z)
    if ob_length == ob.dimensions.x:
        ob_length_scaled = ob_length / ob.scale.x
    elif ob_length == ob.dimensions.y:
        ob_length_scaled = ob_length / ob.scale.y
    else:
        ob_length_scaled = ob_length / ob.scale.z
        
    marker.empty_display_size = ob_length_scaled / 2
    # node.matrix_local = ob.matrix_local
    # node.matrix_parent_inverse = ob.matrix_parent_inverse
    marker.scale = ob.scale
    if maintain_mesh:
        ob.name += '_MARKER_SHAPE'
        ob.matrix_world = Matrix()
        # mesh_ob = bpy.data.objects.new(original_name + '_TEMP', ob.data)
        secret_coll = bpy.data.collections.new(original_name)
        get_foundry_storage_scene().collection.children.link(secret_coll)
        secret_coll.objects.link(ob)
        marker.instance_type = 'COLLECTION'
        marker.instance_collection = secret_coll
        
    for child_ob, matrix_world in children.items():
        child_ob.parent = marker
        child_ob.matrix_world = matrix_world
        
    return marker