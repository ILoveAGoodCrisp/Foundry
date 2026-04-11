from pathlib import Path
from bpy.utils import previews
import bpy

foundry_icons = None
icons_dir = Path(__file__).parent.resolve()
preview_collections = {}
icons_active = False

foundry_icons = None

def get_icon_id(id):
    if foundry_icons is None:
        return 0
    return foundry_icons[id].icon_id if id in foundry_icons else 0

def get_icon_id_in_directory(thumnail_path):
    if foundry_icons is None:
        return 0
    id = thumnail_path
    if id in foundry_icons:
        return foundry_icons[id].icon_id
    return foundry_icons.load(id, thumnail_path, "IMAGE", True).icon_id

def load_all_icons():
    global foundry_icons
    for path in Path(icons_dir).glob("*.png"):
        foundry_icons.load(path.stem, str(path), "IMAGE")

def _reload_icons(dummy):
    global foundry_icons

    if foundry_icons:
        previews.remove(foundry_icons)

    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons
    load_all_icons()

def register():
    global foundry_icons
    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons
    load_all_icons()

    bpy.app.handlers.load_post.append(_reload_icons)
