from pathlib import Path
import bpy
from bpy.utils import previews
from bpy.app.handlers import persistent

foundry_icons = None
icons_dir = Path(__file__).parent.resolve()
preview_collections = {}
icons_active = False

def get_icon_id_special(id):

    if foundry_icons is None:
        return 0
    if id in foundry_icons:
        return foundry_icons[id].icon_id
    return foundry_icons.load(id, str(Path(icons_dir, id).with_suffix(".png")), "IMAGE", True).icon_id

def get_icon_id(id):
    global icons_active

    if not icons_active or foundry_icons is None:
        return 0
    if id in foundry_icons:
        return foundry_icons[id].icon_id
    return foundry_icons.load(id, str(Path(icons_dir, id).with_suffix(".png")), "IMAGE", True).icon_id

def get_icon_id_in_directory(thumnail_path):
    global icons_active

    if not icons_active or foundry_icons is None:
        return 0
    id = thumnail_path
    if id in foundry_icons:
        return foundry_icons[id].icon_id
    return foundry_icons.load(id, thumnail_path, "IMAGE", True).icon_id

def icons_activate():
    global icons_active
    icons_active = True


def register():
    global foundry_icons
    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons
    icons_activate()

def unregister():
    for icon in list(preview_collections.values()):
        try:
            previews.remove(icon)
        except Exception:
            pass
    preview_collections.clear()
