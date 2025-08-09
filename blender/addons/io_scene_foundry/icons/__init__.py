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


def _recreate_previews():
    """Recreate the preview collection; icon IDs are not persistent across loads."""
    global foundry_icons
    # remove existing collection(s)
    for col in list(preview_collections.values()):
        try:
            previews.remove(col)
        except Exception:
            pass
    preview_collections.clear()

    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons

@persistent
def _rebuild_previews(_=None):
    _recreate_previews()
    icons_activate()

# ---------------------------------------------------------------------------

def register():
    global foundry_icons
    foundry_icons = previews.new()
    preview_collections["foundry"] = foundry_icons
    icons_activate()
    
    # if _rebuild_previews not in bpy.app.handlers.load_post:
    #     bpy.app.handlers.load_post.append(_rebuild_previews)
    # if _rebuild_previews not in bpy.app.handlers.undo_post:
    #     bpy.app.handlers.undo_post.append(_rebuild_previews)
    # if _rebuild_previews not in bpy.app.handlers.redo_post:
    #     bpy.app.handlers.redo_post.append(_rebuild_previews)

def unregister():
    # for lst in (bpy.app.handlers.load_post,
    #             bpy.app.handlers.undo_post,
    #             bpy.app.handlers.redo_post):
    #     try:
    #         while _rebuild_previews in lst:
    #             lst.remove(_rebuild_previews)
    #     except Exception:
    #         pass

    for icon in list(preview_collections.values()):
        try:
            previews.remove(icon)
        except Exception:
            pass
    preview_collections.clear()
