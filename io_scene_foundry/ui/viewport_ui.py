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
from io_scene_foundry.utils.nwo_utils import closest_bsp_object, get_prefs, nwo_enum, true_bsp
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
        return asset_type in ("MODEL", "SCENARIO", "PREFAB")

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="NWO_MT_PIE_ApplyTypeMesh")

        return {"FINISHED"}


class NWO_ApplyTypeMesh(NWO_Op):
    bl_label = "Apply Mesh Type"
    bl_idname = "nwo.apply_type_mesh"
    bl_description = "Applies the specified mesh type to the selected objects"

    def m_type_items(self, context):
        items = []
        nwo = context.scene.nwo
        asset_type = nwo.asset_type
        reach = nwo.game_version == "reach"
        if asset_type == "MODEL":
            items.append(
                nwo_enum(
                    "collision",
                    "Collision",
                    "Collision only geometry. Bullets always collide with this mesh. If this mesh is static (cannot move) and does not have a physics model, the collision model will also interact with physics objects such as the player",
                    "collider",
                    0,
                )
            ),
            items.append(
                nwo_enum(
                    "physics",
                    "Physics",
                    "Physics only geometry. Uses havok physics to interact with static and dynamic objects",
                    "physics",
                    1,
                )
            ),
            items.append(
                nwo_enum(
                    "render", "Render", "Render only geometry", "render_geometry", 2
                )
            )

        elif asset_type in ("SCENARIO", "PREFAB"):
            items.append(
                nwo_enum(
                    "collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    "collider",
                    0,
                )
            ),
            items.append(
                nwo_enum(
                    "poop",
                    "Instance",
                    "Geometry capable of cutting through structure mesh. Can be instanced. Provides render, collision, and physics",
                    "instance",
                    1,
                )
            ),
            if asset_type == "SCENARIO":
                if not reach:
                    descrip = "Defines the bounds of the BSP. Is always sky mesh and therefore has no render or collision geometry. Use the proxy instance option to add render/collision geometry"
                else:
                    descrip = "Defines the bounds of the BSP. By default acts as render, collision and physics geometry"
                items.append(
                    nwo_enum("structure", "Structure", descrip, "structure", 2)
                )
                items.append(
                    nwo_enum(
                        "seam",
                        "Seam",
                        "Allows visibility and traversal between two or more bsps. Requires zone sets to be set up in the scenario tag",
                        "seam",
                        3,
                    )
                )
                items.append(
                    nwo_enum(
                        "portal",
                        "Portal",
                        "Planes that cut through structure geometry to define clusters. Used for defining visiblity between different clusters.",
                        "portal",
                        4,
                    )
                )
                items.append(
                    nwo_enum(
                        "water_surface",
                        "Water Surface",
                        "Plane which can cut through structure geometry to define a water surface. Supports tesselation",
                        "water",
                        5,
                    )
                )
                items.append(
                    nwo_enum(
                        "water_physics",
                        "Water Physics",
                        "Defines a region where water physics should apply. Material effects will play when projectiles strike this mesh. Underwater fog atmosphere will be used when the player is inside the volume",
                        "water_physics",
                        6,
                    )
                )
                items.append(
                    nwo_enum(
                        "soft_ceiling",
                        "Soft Ceiling",
                        "Soft barrier that blocks the player and player camera",
                        "soft_ceiling",
                        7,
                    )
                )
                items.append(
                    nwo_enum(
                        "soft_kill",
                        "Soft Kill",
                        "Defines a region where the player will be killed... softly",
                        "soft_kill",
                        8,
                    )
                )
                items.append(
                    nwo_enum(
                        "slip_surface",
                        "Slip Surface",
                        "Defines a region in which surfaces become slippery",
                        "slip_surface",
                        9,
                    )
                )
                items.append(
                    nwo_enum(
                        "fog",
                        "Fog",
                        "Defines an area in a cluster which renders fog defined in the scenario tag",
                        "fog",
                        10,
                    )
                )
                if reach:
                    items.append(
                        nwo_enum(
                            "cookie_cutter",
                            "Cookie Cutter",
                            "Cuts out the region this volume defines from the ai navigation mesh. Helpful in cases that you have ai pathing issues in your map",
                            "cookie_cutter",
                            11,
                        )
                    ),
                    # items.append(
                    #     nwo_enum(
                    #         "lightmap",
                    #         "Lightmap Region",
                    #         "Restricts lightmapping to this area when specified during lightmapping",
                    #         "lightmap_region",
                    #         0,
                    #     )
                    # )
                else:
                    items.append(
                        nwo_enum(
                            "lightmap",
                            "Lightmap Exclusion",
                            "Defines a region that should not be lightmapped",
                            "lightmap_exclude",
                            11,
                        )
                    )

                items.append(
                    nwo_enum(
                        "rain_blocker",
                        "Rain Blocker",
                        "Blocks rain from rendering in the region this volume occupies",
                        "rain_sheet",
                        12,
                    )
                )
                if reach:
                    items.append(
                        nwo_enum(
                            "rain_sheet",
                            "Rain Sheet",
                            "A plane which blocks all rain particles that hit it. Regions under this plane will not render rain",
                            "rain_sheet",
                            13,
                        )
                    )
                else:
                    stream_des = """Defines the region in a zone set that should be used when generating a streamingzoneset tag. 
                     By default the full space inside a zone set should be used when generating the streaming zone set. 
                     This is useful for performance if you have textures in areas of the map the player will not get close to"""
                    items.append(
                        nwo_enum("streaming", "Streaming", stream_des, "streaming", 14)
                    )

        return items

    m_type: bpy.props.EnumProperty(
        items=m_type_items,
    )

    def draw(self, context):
        self.layout.prop(self, "m_type", text="Mesh Type")

    def execute(self, context):
        apply_materials = get_prefs().apply_materials
        mesh_type = ""
        sub_type = ""
        material = ""
        match self.m_type:
            case "collision":
                if context.scene.nwo.asset_type == "MODEL":
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
                if context.scene.nwo.game_version == "reach":
                    sub_type = "_connected_geometry_volume_type_lightmap_region"
                else:
                    sub_type = "_connected_geometry_volume_type_lightmap_exclude"
                material = "Volume"

            case "cookie_cutter":
                if context.scene.nwo.asset_type == "PREFAB":
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

        meshes = [
            ob
            for ob in context.selected_objects
            if ob.type
            in (
                "MESH",
                "CURVE",
                "META",
                "SURFACE",
                "FONT",
            )
        ]

        for ob in meshes:
            nwo = ob.nwo
            nwo.object_type_ui = "_connected_geometry_object_type_mesh"
            nwo.mesh_type_ui = mesh_type
            if sub_type:
                if mesh_type == "_connected_geometry_mesh_type_volume":
                    nwo.volume_type_ui = sub_type
                else:
                    nwo.plane_type_ui = sub_type

            if apply_materials:
                apply_props_material(ob, material)

            if self.m_type == "seam":
                closest_bsp = closest_bsp_object(ob)
                if closest_bsp is not None:
                    ob.nwo.seam_back_ui = true_bsp(closest_bsp.nwo)

        self.report(
            {"INFO"}, f"Applied Mesh Type [{self.m_type}] to {len(meshes)} objects"
        )
        return {"FINISHED"}


class NWO_MT_PIE_ApplyTypeMarker(bpy.types.Menu):
    bl_label = "Marker Type"
    bl_idname = "NWO_MT_PIE_ApplyTypeMarker"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        pie.operator_enum("nwo.apply_type_marker", "m_type")


class NWO_PIE_ApplyTypeMarker(NWO_Op):
    bl_label = "Apply Marker Type"
    bl_idname = "nwo.apply_types_marker_pie"

    @classmethod
    def poll(self, context):
        asset_type = context.scene.nwo.asset_type
        return asset_type in ("MODEL", "SKY", "SCENARIO", "PREFAB")

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="NWO_MT_PIE_ApplyTypeMarker")

        return {"FINISHED"}


class NWO_ApplyTypeMarker(NWO_Op):
    bl_label = "Apply Marker Type"
    bl_idname = "nwo.apply_type_marker"
    bl_description = "Applies the specified marker type to the selected objects"

    def m_type_items(self, context):
        items = []
        nwo = context.scene.nwo
        asset_type = nwo.asset_type
        reach = nwo.game_version == "reach"
        if asset_type in ("MODEL", "SKY"):
            items.append(nwo_enum("model", "Model Marker", "", "marker", 0)),
            items.append(nwo_enum("effects", "Effects", "", "effects", 1)),

            if asset_type == "MODEL":
                items.append(nwo_enum("garbage", "Garbage", "", "garbage", 2)),
                items.append(nwo_enum("hint", "Hint", "", "hint", 3)),
                items.append(
                    nwo_enum(
                        "pathfinding_sphere",
                        "Pathfinding Sphere",
                        "",
                        "pathfinding_sphere",
                        4,
                    )
                ),
                items.append(
                    nwo_enum(
                        "physics_constraint",
                        "Physics Constaint",
                        "",
                        "physics_constraint",
                        5,
                    )
                ),
                items.append(nwo_enum("target", "Target", "", "target", 6)),
                if not reach:
                    items.append(nwo_enum("airprobe", "Air Probe", "", "airprobe", 7)),

        elif asset_type in ("SCENARIO", "PREFAB"):
            items.append(nwo_enum("model", "Structure Marker", "", "marker", 0)),
            items.append(
                nwo_enum("game_instance", "Game Object", "", "game_object", 1)
            ),
            if not reach:
                items.append(nwo_enum("airprobe", "Air Probe", "", "airprobe", 2)),
                items.append(
                    nwo_enum("envfx", "Environment Effect", "", "environment_effect", 3)
                ),
                items.append(nwo_enum("lightcone", "Light Cone", "", "light_cone", 4)),

        return items

    m_type: bpy.props.EnumProperty(
        items=m_type_items,
    )

    def draw(self, context):
        self.layout.prop(self, "m_type", text="Marker Type")

    def execute(self, context):
        marker_type = ""
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
            case "physics_constraint":
                marker_type = "_connected_geometry_marker_type_physics_constraint"
            case "target":
                marker_type = "_connected_geometry_marker_type_target"
            case "game_instance":
                marker_type = "_connected_geometry_marker_type_game_instance"
            case "airprobe":
                marker_type = "_connected_geometry_marker_type_airprobe"
            case "envfx":
                marker_type = "_connected_geometry_marker_type_envfx"
            case "lightcone":
                marker_type = "_connected_geometry_marker_type_lightCone"

        markers = [
            ob
            for ob in context.selected_objects
            if ob.type in ("MESH", "CURVE", "META", "SURFACE", "FONT", "EMPTY")
        ]

        for ob in markers:
            nwo = ob.nwo
            nwo.object_type_ui = "_connected_geometry_object_type_marker"
            nwo.marker_type_ui = marker_type

        self.report(
            {"INFO"}, f"Applied Marker Type: [{self.m_type}] to {len(markers)} objects"
        )
        return {"FINISHED"}
