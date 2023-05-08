import bpy
from bpy.types import Menu
from bpy.app.handlers import persistent

from bpy.app.translations import (
    pgettext_iface as iface_,
    pgettext_tip as tip_,
    contexts as i18n_contexts,
)

@persistent
def load_handler_for_preferences(_):
    print("Changing Preference Defaults!")
    from bpy import context

    prefs = context.preferences
    prefs.use_preferences_save = False

    bpy.ops.preferences.addon_enable(module="io_scene_foundry")

    # kc = context.window_manager.keyconfigs["blender"]
    # kc_prefs = kc.preferences
    # if kc_prefs is not None:
    #     kc_prefs.select_mouse = 'RIGHT'
    #     kc_prefs.spacebar_action = 'SEARCH'
    #     kc_prefs.use_pie_click_drag = True

    # view = prefs.view
    # view.header_align = 'BOTTOM'


# @persistent
# def load_handler_for_startup(_):
#     print("Changing Startup Defaults!")
    # context = bpy.context
    # scene = context.scene
    # nwo_scene = scene.nwo_global
    # scene.unit_settings.scale_length = 0.03048
    # scene.render.fps = 30

class WM_MT_splash(Menu):
    bl_label = "Splash"

    def draw(self, context):
        from io_scene_foundry.icons import get_icon_id
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        layout.emboss = 'PULLDOWN_MENU'

        split = layout.split()

        # Templates
        col1 = split.column()
        col1.label(text="New Asset")
        #col1.scale_y = 0.8

        # bpy.types.TOPBAR_MT_file_new.draw_ex(col1, context, use_splash=True)
        col1.operator("wm.read_homefile", text="Model", icon_value=get_icon_id("model")).app_template = "Foundry"
        col1.operator("wm.read_homefile", text="Scenario", icon_value=get_icon_id("scenario")).app_template = "Foundry"
        col1.operator("wm.read_homefile", text="Sky", icon_value=get_icon_id("sky")).app_template = "Foundry"
        col1.operator("wm.read_homefile", text="Decorator Set", icon_value=get_icon_id("decorator")).app_template = "Foundry"
        col1.operator("wm.read_homefile", text="Particle Model", icon_value=get_icon_id("particle_model")).app_template = "Foundry"
        col1.operator("wm.read_homefile", text="Prefab", icon_value=get_icon_id("prefab")).app_template = "Foundry"
        col1.operator("wm.read_homefile", text="First Person Animation", icon_value=get_icon_id("animation")).app_template = "Foundry"
        # Recent
        col2 = split.column()
        col2_title = col2.row()

        found_recent = col2.template_recent_files()

        if found_recent:
            col2_title.label(text="Recent Files")
        else:

            # Links if no recent files
            col2_title.label(text="Getting Started")

            col2.operator("wm.url_open_preset", text="Manual", icon='URL').type = 'MANUAL'
            col2.operator("wm.url_open_preset", text="Blender Website", icon='URL').type = 'BLENDER'
            col2.operator("wm.url_open_preset", text="Credits", icon='URL').type = 'CREDITS'

        layout.separator()

        split = layout.split()

        col1 = split.column()
        sub = col1.row()
        sub.operator_context = 'INVOKE_DEFAULT'
        sub.operator("wm.open_mainfile", text="Open...", icon='FILE_FOLDER')
        col1.operator("wm.recover_last_session", icon='RECOVER_LAST')

        col2 = split.column()

        col2.operator("wm.url_open", text="Github").url = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"
        col2.operator("wm.url_open", text="Documentation").url = r"https://c20.reclaimers.net/"
        # col2.operator("wm.url_open_preset", text="Development Fund", icon='FUND').type = 'FUND'

        layout.separator()
        layout.separator()


classes = (
    WM_MT_splash,
)

def register():
    print("Registering to Change Defaults")
    pass
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_factory_preferences_post.append(load_handler_for_preferences)
    #bpy.app.handlers.load_factory_startup_post.append(load_handler_for_startup)

def unregister():
    print("Unregistering to Change Defaults")
    pass
    bpy.app.handlers.load_factory_preferences_post.remove(load_handler_for_preferences)
    #bpy.app.handlers.load_factory_startup_post.remove(load_handler_for_startup)
    for cls in classes:
        bpy.utils.unregister_class(cls)