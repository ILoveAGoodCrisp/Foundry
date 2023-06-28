from os import path
from bpy.utils import previews

foundry_icons = None
icons_dir = path.dirname(__file__)
preview_collections = {}
icons_active = False

def get_icon_id_special(id):
    if id in foundry_icons:
        return foundry_icons[id].icon_id
    return foundry_icons.load(id, path.join(icons_dir, id + ".png"), "IMAGE").icon_id

def get_icon_id(id):
    global icons_active
    if icons_active:
        if id in foundry_icons:
            return foundry_icons[id].icon_id
        return foundry_icons.load(id, path.join(icons_dir, id + ".png"), "IMAGE").icon_id
    return 0

def icons_activate():
    global icons_active
    icons_active = True

def register():
    global foundry_icons
    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons

def unregister():
    for icon in preview_collections.values():
        previews.remove(icon)
    preview_collections.clear()
