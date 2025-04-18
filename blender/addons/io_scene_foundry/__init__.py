import bpy
from . import startup

from . import props
from . import tools
from . import ui
from . import export
from . import keymap
from . import icons
from . import preferences

modules = [
    preferences,
    props,
    ui,
    tools,
    export,
    keymap,
    icons,
]
            
def register():
    bpy.app.handlers.load_post.append(startup.load_handler)
    bpy.app.handlers.load_post.append(startup.load_set_output_state)
    bpy.app.handlers.save_post.append(startup.save_object_positions_to_tags)
    bpy.app.handlers.blend_import_post.append(startup.import_handler)
    for module in modules:
        module.register()
    icons.icons_activate()

def unregister():
    bpy.app.handlers.blend_import_post.remove(startup.import_handler)
    bpy.app.handlers.save_post.remove(startup.save_object_positions_to_tags)
    bpy.app.handlers.load_post.remove(startup.load_set_output_state)
    bpy.app.handlers.load_post.remove(startup.load_handler)
    for module in reversed(modules):
        module.unregister()