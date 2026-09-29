from pathlib import Path

import bpy
from bpy.app.handlers import persistent
from bpy.utils import previews

icons_dir = Path(__file__).parent.resolve()
icons_light_dir = icons_dir.parent / "icons_light"
preview_collections = {}
foundry_icons = None
icons_active = False
_active_icons_dir = None
_warned_messages = set()


def _warn_once(message):
    if message in _warned_messages:
        return
    _warned_messages.add(message)
    print(f"[Foundry Icons] {message}")


def _theme_icons_dir():
    try:
        color = bpy.context.preferences.themes[0].user_interface.wcol_regular.inner
        brightness = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
        if brightness >= 0.5 and icons_light_dir.is_dir():
            return icons_light_dir
    except (AttributeError, IndexError, TypeError):
        pass
    return icons_dir


def _builtin_icon_path(icon_name):
    directory = _active_icons_dir or _theme_icons_dir()
    themed_path = directory / f"{icon_name}.png"
    if themed_path.is_file():
        return themed_path
    return icons_dir / f"{icon_name}.png"


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
    return _load_icon_into_collection(icon_name, _builtin_icon_path(icon_name))


def load_all_icons(force_reload=False):
    global _active_icons_dir
    if bpy.app.background:
        return

    directory = _theme_icons_dir()
    collection = _ensure_collection(recreate=force_reload or directory != _active_icons_dir)
    if collection is None:
        return
    _active_icons_dir = directory

    names = {path.stem for path in icons_dir.glob("*.png")}
    if directory != icons_dir:
        names.update(path.stem for path in directory.glob("*.png"))
    for name in names:
        _load_builtin_icon(name)


def _tag_redraw():
    window_manager = bpy.context.window_manager
    if window_manager is None:
        return
    for window in window_manager.windows:
        if window.screen:
            for area in window.screen.areas:
                area.tag_redraw()


def _check_theme():
    if _theme_icons_dir() != _active_icons_dir:
        load_all_icons(force_reload=True)
        _tag_redraw()
    return 1.0


@persistent
def _reload_icons(_dummy):
    # Blender may discard preview image data on file load.
    load_all_icons(force_reload=True)
    _tag_redraw()


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
    if not bpy.app.timers.is_registered(_check_theme):
        bpy.app.timers.register(_check_theme, first_interval=1.0, persistent=True)


def unregister():
    global foundry_icons, icons_active, _active_icons_dir
    if bpy.app.timers.is_registered(_check_theme):
        bpy.app.timers.unregister(_check_theme)
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
    _active_icons_dir = None
