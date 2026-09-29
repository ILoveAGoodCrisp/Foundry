from pathlib import Path

import bpy
from bpy.app.handlers import persistent
from bpy.utils import previews

icons_dir = Path(__file__).parent.resolve()
preview_collections = {}
foundry_icons = None
icons_active = False
_warned_messages = set()


def _warn_once(message):
    if message in _warned_messages:
        return
    _warned_messages.add(message)
    print(f"[Foundry Icons] {message}")


def _is_collection_valid(collection):
    if collection is None:
        return False
    try:
        # Accessing len on stale preview collections raises in some Blender states.
        len(collection)
        return True
    except Exception:
        return False


def _preview_icon_id(collection, key):
    if collection is None:
        return 0
    try:
        if key not in collection:
            return 0
        icon_id = int(getattr(collection[key], "icon_id", 0) or 0)
        return icon_id if icon_id > 0 else 0
    except Exception:
        return 0


def _remove_collection():
    global foundry_icons, icons_active
    if foundry_icons is not None:
        try:
            previews.remove(foundry_icons)
        except Exception:
            pass
    foundry_icons = None
    icons_active = False
    preview_collections.pop("foundry", None)


def _ensure_collection(recreate=False):
    global foundry_icons, icons_active
    if bpy.app.background:
        return None

    if recreate:
        _remove_collection()

    if _is_collection_valid(foundry_icons):
        return foundry_icons

    try:
        foundry_icons = previews.new()
        preview_collections["foundry"] = foundry_icons
        icons_active = True
        return foundry_icons
    except Exception as ex:
        foundry_icons = None
        icons_active = False
        _warn_once(f"Failed to create icon preview collection: {ex}")
        return None


def _load_icon_into_collection(icon_id, icon_path):
    collection = _ensure_collection()
    if collection is None:
        return 0

    if not icon_path.exists():
        return 0

    key = str(icon_id)
    image_path = str(icon_path)
    existing_id = _preview_icon_id(collection, key)
    if existing_id:
        return existing_id

    # Blender rejects duplicate keys even when force_reload is True.
    if key in collection:
        try:
            del collection[key]
        except Exception as ex:
            _warn_once(f"Failed to release icon '{key}': {ex}")
            return 0

    try:
        preview = collection.load(key, image_path, "IMAGE")
        loaded_id = int(getattr(preview, "icon_id", 0) or 0)
        if loaded_id > 0:
            return loaded_id
    except Exception as ex:
        _warn_once(f"Failed to load icon '{key}' from '{icon_path.name}': {ex}")
        return 0

    _warn_once(f"Failed to load icon '{key}' from '{icon_path.name}': Blender returned icon_id 0")
    return 0


def _load_builtin_icon(icon_name):
    return _load_icon_into_collection(icon_name, icons_dir / f"{icon_name}.png")


def load_all_icons(force_reload=False):
    if bpy.app.background:
        return

    if force_reload:
        _ensure_collection(recreate=True)

    for path in icons_dir.glob("*.png"):
        _load_icon_into_collection(path.stem, path)


@persistent
def _reload_icons(_dummy):
    # Blender may discard preview image data on file load.
    load_all_icons(force_reload=True)
    for window in bpy.context.window_manager.windows:
        if window.screen:
            for area in window.screen.areas:
                area.tag_redraw()


def get_icon_id(id):
    if not id:
        return 0

    key = str(id)
    collection = _ensure_collection()
    if collection is None:
        return 0

    existing_id = _preview_icon_id(collection, key)
    if existing_id:
        return existing_id

    return _load_builtin_icon(key)


def get_icon_id_in_directory(thumnail_path):
    if not thumnail_path:
        return 0

    thumbnail_path = Path(thumnail_path)
    if not thumbnail_path.exists():
        return 0

    collection = _ensure_collection()
    if collection is None:
        return 0

    try:
        key = str(thumbnail_path.resolve())
    except Exception:
        key = str(thumbnail_path)

    existing_id = _preview_icon_id(collection, key)
    if existing_id:
        return existing_id

    if key in collection:
        try:
            del collection[key]
        except Exception as ex:
            _warn_once(f"Failed to release thumbnail icon '{thumbnail_path}': {ex}")
            return 0

    try:
        preview = collection.load(key, str(thumbnail_path), "IMAGE")
        loaded_id = int(getattr(preview, "icon_id", 0) or 0)
        if loaded_id > 0:
            return loaded_id
    except Exception as ex:
        _warn_once(f"Failed to load thumbnail icon '{thumbnail_path}': {ex}")
    return 0


def register():
    if bpy.app.background:
        return

    load_all_icons(force_reload=True)
    if _reload_icons not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_reload_icons)


def unregister():
    global foundry_icons, icons_active
    try:
        if _reload_icons in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_reload_icons)
    except Exception:
        pass

    for icon in list(preview_collections.values()):
        try:
            previews.remove(icon)
        except Exception:
            pass

    preview_collections.clear()
    foundry_icons = None
    icons_active = False
