from os import path
from bpy.utils import previews

foundry_icons = None
icons_dir = path.dirname(__file__)

def get_icon_id(id):
    return get_icon(id).icon_id

def get_icon(id):
    if id in foundry_icons:
        return foundry_icons[id]
    return foundry_icons.load(id, path.join(icons_dir, id + ".png"), "IMAGE")

def initialize_foundry_icons():
    global foundry_icons
    foundry_icons = previews.new()

def unload_icons():
    previews.remove(foundry_icons)

def register():
    initialize_foundry_icons()

def unregister():
    unload_icons()

if __name__ == '__main__':
    register()
