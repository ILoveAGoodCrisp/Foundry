"""A native Blender window containing the Foundry sidebar and bar."""

from functools import partial
from pathlib import Path

import bpy

from .. import startup


_SCREEN_FLAG = "foundry_window"


def is_foundry_window(context):
    screen = getattr(context, 'screen', None)
    return bool(screen and screen.get(_SCREEN_FLAG, False))


def _select_foundry_tab(window, attempts=20):
    # Categories only become writable after Blender has drawn the new sidebar.
    if window not in bpy.context.window_manager.windows[:]:
        return
    area = next((area for area in window.screen.areas if area.type == 'VIEW_3D'), None)
    if area is None:
        return
    region = next((region for region in area.regions if region.type == 'UI'), None)
    if region is not None and not region.is_property_readonly('active_panel_category'):
        try:
            region.active_panel_category = 'Foundry'
            area.tag_redraw()
            return
        except (AttributeError, TypeError):
            pass
    if attempts:
        bpy.app.timers.register(partial(_select_foundry_tab, window, attempts - 1), first_interval=0.1)


class NWO_OT_OpenFoundryWindow(bpy.types.Operator):
    bl_idname = "nwo.open_foundry_window"
    bl_label = "Open Foundry Window"
    bl_description = "Open the Foundry Panel and Foundry Bar in their own Blender window"
    bl_options = set()

    @classmethod
    def poll(cls, context):
        return not bpy.app.background and context.window is not None and context.area is not None

    def execute(self, context):
        template = Path(__file__).resolve().parents[1] / 'blends' / 'foundry_ui.blend'
        if not template.is_file():
            self.report({'ERROR'}, "The Foundry window layout is missing. Reinstall Foundry.")
            return {'CANCELLED'}

        previous = {window.as_pointer() for window in context.window_manager.windows}
        source = context.window
        existing = next((item for item in context.window_manager.windows
                         if item.screen.get(_SCREEN_FLAG, False)
                         and item.scene == source.scene and item.view_layer == source.view_layer
                         and len(item.screen.areas) == 1
                         and item.screen.areas[0].type == 'VIEW_3D'), None)
        # Window-menu and F3 calls can originate in a tiny Outliner or header.
        # Duplicate a useful editor size without changing any source editor.
        area = context.area if context.area.type == 'VIEW_3D' else next(
            (area for area in source.screen.areas if area.type == 'VIEW_3D'),
            max(source.screen.areas, key=lambda area: area.width * area.height),
        )
        duplicate_source = existing or source
        if existing:
            area = existing.screen.areas[0]
        region = next((region for region in area.regions if region.type == 'WINDOW'), None)
        try:
            with context.temp_override(window=duplicate_source, area=area, region=region):
                bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        except RuntimeError as exc:
            self.report({'ERROR'}, f"Could not create the Foundry window: {exc}")
            return {'CANCELLED'}
        window = next((window for window in context.window_manager.windows
                       if window.as_pointer() not in previous), None)
        if window is None:
            self.report({'ERROR'}, "Blender could not create the Foundry window")
            return {'CANCELLED'}

        try:
            # A saved workspace supplies the full-width native sidebar: Blender's
            # Python API exposes region widths as read-only. It contains no assets.
            if not existing:
                used_workspaces = {item.workspace for item in context.window_manager.windows}
                workspace = next((workspace for workspace in bpy.data.workspaces
                                  if workspace.get(_SCREEN_FLAG, False)
                                  and workspace not in used_workspaces
                                  and workspace.screens), None)
                if workspace is None:
                    with bpy.data.libraries.load(str(template)) as (data_from, data_to):
                        data_to.workspaces = ['Foundry']
                    workspace = data_to.workspaces[0]
                if workspace is None:
                    raise RuntimeError("The Foundry workspace is missing from its layout")
                workspace[_SCREEN_FLAG] = True
                with context.temp_override(window=window):
                    window.workspace = workspace
                    window.scene = source.scene
                    window.view_layer = source.view_layer
            window.screen[_SCREEN_FLAG] = True
            # Workspace switching is deferred until Blender processes notifiers;
            # the just-duplicated editor may still be a Console or Outliner here.
            area = window.screen.areas[0]
            if not startup.load_handler_complete:
                with context.temp_override(window=window, area=area):
                    startup.load_handler(None)
                    startup.load_set_output_state(None)
            area.tag_redraw()
            bpy.app.timers.register(partial(_select_foundry_tab, window), first_interval=0.1)
        except Exception as exc:
            with context.temp_override(window=window):
                bpy.ops.wm.window_close()
            self.report({'ERROR'}, f"Could not open the Foundry window: {exc}")
            return {'CANCELLED'}
        return {'FINISHED'}


# def menu_func(self, context):
#     self.layout.operator(NWO_OT_OpenFoundryWindow.bl_idname, icon='WINDOW')
