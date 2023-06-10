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

import bpy

from io_scene_foundry.tools.property_apply import apply_props_material
from io_scene_foundry.utils.nwo_utils import nwo_enum
from .templates import NWO_Op

class NWO_MT_PIE_ApplyTypeMesh(bpy.types.Menu):
    bl_label = "Mesh Type"
    bl_idname = "NWO_MT_PIE_ApplyTypeMesh"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        pie.operator_enum("nwo.apply_type_mesh", "m_type")


class NWO_PIE_ApplyTypeMesh(NWO_Op):
    bl_label = "Apply Mesh Type"
    bl_idname = "nwo.apply_types_mesh_pie"

    @classmethod
    def poll(self, context):
        asset_type = context.scene.nwo.asset_type
        return asset_type in ('MODEL', 'SCENARIO', 'PREFAB')

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="NWO_MT_PIE_ApplyTypeMesh")

        return {'FINISHED'}


class NWO_ApplyTypeMesh(NWO_Op):
    bl_label = "Apply Mesh Type"
    bl_idname = "nwo.apply_type_mesh"

    def m_type_items(self, context):
        items = []
        nwo = context.scene.nwo
        asset_type = nwo.asset_type
        reach = nwo.game_version == "reach"
        if asset_type == 'MODEL':
            items.append(nwo_enum("collision", "Collision", "", "collider", 0)),
            items.append(nwo_enum("physics", "Physics", "", "physics", 1)),
            items.append(nwo_enum("render", "Render", "", "render_geometry", 2))

        elif asset_type in ('SCENARIO', 'PREFAB'):
            items.append(nwo_enum("collision", "Collision", "", "collider", 0)),
            items.append(nwo_enum("poop", "Instance", "", "instance", 1)),
            items.append(nwo_enum("cookie_cutter", "Cookie Cutter", "", "cookie_cutter", 2)),
            if asset_type == 'SCENARIO':
                items.append(nwo_enum("structure", "Structure", "", "structure", 3))
                items.append(nwo_enum("seam", "Seam", "", "seam", 4))
                items.append(nwo_enum("portal", "Portal", "", "portal", 5))
                items.append(nwo_enum("water_surface", "Water Surface", "", "water", 6))
                items.append(nwo_enum("fog", "Fog", "", "fog", 7))
                items.append(nwo_enum("soft_ceiling", "Soft Ceiling", "", "soft_ceiling", 8))
                items.append(nwo_enum("soft_kill", "Soft Kill", "", "soft_kill", 9))
                items.append(nwo_enum("slip_surface", "Slip Surface", "", "slip_surface", 10))
                items.append(nwo_enum("water_physics", "Water Physics", "", "water_physics", 11))
                if reach:
                    items.append(nwo_enum("lightmap", "Lightmap Region", "", "lightmap_region", 12))
                else:
                    items.append(nwo_enum("lightmap", "Lightmap Exclusion", "", "lightmap_exclude", 12))

                items.append(nwo_enum("rain_blocker", "Rain Blocker", "", "rain_sheet", 13))
                if reach:
                    items.append(nwo_enum("rain_sheet", "Rain Sheet", "", "rain_sheet", 14))
                else:
                    items.append(nwo_enum("streaming", "Streaming", "", "streaming", 14))
    
        return items

    m_type : bpy.props.EnumProperty(
        items=m_type_items,
            
    )

    def draw(self, context):
        self.layout.prop(self, "m_type", text="Mesh Type")

    def execute(self, context):
        selection = context.selected_objects
        mesh_type = ""
        sub_type = ""
        material = ""
        match self.m_type:
            case "collision":
                if context.scene.nwo.asset_type == 'MODEL':
                    mesh_type = "_connected_geometry_mesh_type_collision"
                    material = "Collision"
                else:
                    mesh_type = "_connected_geometry_mesh_type_poop_collision"
                    material = "Collision"
            case "physics":
                mesh_type = "_connected_geometry_mesh_type_physics"
                material = "Physics"
            case "render":
                mesh_type = "_connected_geometry_mesh_type_render"
            case "poop":
                mesh_type = "_connected_geometry_mesh_type_poop"
            case "structure":
                mesh_type = "_connected_geometry_mesh_type_structure"
            case "seam":
                mesh_type = "_connected_geometry_mesh_type_seam"
                material = "Seam"
            case "portal":
                mesh_type = "_connected_geometry_mesh_type_plane"
                sub_type = "_connected_geometry_plane_type_portal"
                material = "Portal"
            case "water_surface":
                mesh_type = "_connected_geometry_mesh_type_plane"
                sub_type = "_connected_geometry_plane_type_water_surface"
            case "rain_sheet":
                mesh_type = "_connected_geometry_mesh_type_plane"
                sub_type = "_connected_geometry_plane_type_poop_vertical_rain_sheet"
                material = "RainSheet"
            case "fog":
                mesh_type = "_connected_geometry_mesh_type_plane"
                sub_type = "_connected_geometry_plane_type_planar_fog_volume"
                material = "Fog"
            case "rain_sheet":
                mesh_type = "_connected_geometry_mesh_type_plane"
                sub_type = "_connected_geometry_plane_type_vertical_rain_sheet"
                material = "RainSheet"
            case "soft_ceiling":
                mesh_type = "_connected_geometry_mesh_type_volume"
                sub_type = "_connected_geometry_volume_type_soft_ceiling"
                material = "SoftCeiling"
            case "soft_kill":
                mesh_type = "_connected_geometry_mesh_type_volume"
                sub_type = "_connected_geometry_volume_type_soft_kill"
                material = "SoftKill"
            case "slip_surface":
                mesh_type = "_connected_geometry_mesh_type_volume"
                sub_type = "_connected_geometry_volume_type_slip_surface"
                material = "SlipSurface"
            case "water_physics":
                mesh_type = "_connected_geometry_mesh_type_volume"
                sub_type = "_connected_geometry_volume_type_water_physics_volume"
                material = "WaterVolume"
            case "streaming":
                mesh_type = "_connected_geometry_mesh_type_volume"
                sub_type = "_connected_geometry_volume_type_streaming"
                material = "Volume"
            case "lightmap":
                mesh_type = "_connected_geometry_mesh_type_volume"
                if context.scene.nwo.game_version == 'reach':
                    sub_type = "_connected_geometry_volume_type_lightmap_region"
                else:
                    sub_type = "_connected_geometry_volume_type_lightmap_exclude"
                material = "Volume"

            case "cookie_cutter":
                if context.scene.nwo.asset_type == 'PREFAB':
                    mesh_type = "_connected_geometry_mesh_type_cookie_cutter"
                else:
                    mesh_type = "_connected_geometry_mesh_type_volume"
                    sub_type = "_connected_geometry_volume_type_cookie_cutter"

                material = "CookieCutter"

            case "rain_blocker":
                mesh_type = "_connected_geometry_mesh_type_volume"
                sub_type = "_connected_geometry_volume_type_poop_rain_blocker"
                material = "RainBlocker"
            case "decorator":
                mesh_type = "_connected_geometry_mesh_type_decorator"

        for ob in selection:
            nwo = ob.nwo
            nwo.mesh_type_ui = mesh_type
            if sub_type:
                if mesh_type == "_connected_geometry_mesh_type_volume":
                    nwo.volume_type_ui = sub_type
                else:
                    nwo.plane_type_ui = sub_type

            apply_props_material(ob, material)


        return {'FINISHED'}
        
