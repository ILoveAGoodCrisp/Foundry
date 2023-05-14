import bpy
from bpy.types import Menu
from bpy.app.handlers import persistent

from io_scene_foundry.utils.splash_screen import FoundrySplashScreen

@persistent
def load_handler_for_preferences(_):
    from bpy import context

    prefs = context.preferences
    prefs.use_preferences_save = False

    bpy.ops.preferences.addon_enable(module="io_scene_foundry")

@persistent
def load_handler(dummy):
    bpy.ops.nwo.make_asset('INVOKE_DEFAULT', asset_name="new_model")

class WM_MT_splash(FoundrySplashScreen):
    bl_label = "Splash"

classes = (
    WM_MT_splash,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_factory_preferences_post.append(load_handler_for_preferences)
    bpy.app.handlers.load_post.append(load_handler)

def unregister():
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.app.handlers.load_factory_preferences_post.remove(load_handler_for_preferences)
    for cls in classes:
        bpy.utils.unregister_class(cls)