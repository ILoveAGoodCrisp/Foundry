from os import path
from bpy.utils import previews

foundry_icons = None
icons_dir = path.dirname(__file__)
preview_collections = {}

def get_icon_id(id):
    return get_icon(id).icon_id

def get_icon(id):
    if id in foundry_icons:
        return foundry_icons[id]
    return foundry_icons.load(id, path.join(icons_dir, id + ".png"), "IMAGE")

def register():
    global foundry_icons
    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons

def unregister():
    for icon in preview_collections.values():
        previews.remove(icon)
    preview_collections.clear()
