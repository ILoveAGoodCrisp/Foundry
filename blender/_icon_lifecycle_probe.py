import bpy
from bpy.utils import previews
from bpy.app.handlers import persistent
from pathlib import Path

icon = Path(__file__).parent / "addons" / "io_scene_foundry" / "icons" / "foundry.png"
blend = r"C:\Users\tom27\Downloads\poa_evolved_master(3).blend"
collection = previews.new()
preview = collection.load("foundry", str(icon), "IMAGE")
print("ICON_PROBE before", preview.icon_id, preview.image_size[:], preview.is_image_custom)

@persistent
def report(_):
    old = collection["foundry"]
    print("ICON_PROBE after", old.icon_id, old.image_size[:], old.is_image_custom)
    refreshed = collection.load("foundry", str(icon), "IMAGE", True)
    print("ICON_PROBE reload", refreshed.icon_id, refreshed.image_size[:], refreshed.is_image_custom)

bpy.app.handlers.load_post.append(report)
bpy.ops.wm.open_mainfile(filepath=blend)
bpy.ops.wm.quit_blender()
