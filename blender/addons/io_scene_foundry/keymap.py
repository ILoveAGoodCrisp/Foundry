import bpy

keys = []


def register():
    wm = bpy.context.window_manager
    active_keyconfig = wm.keyconfigs.active
    addon_keyconfig = wm.keyconfigs.addon

    kc = addon_keyconfig
    if not kc:
        return


    # VIEW_3D

    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")

    kmi = km.keymap_items.new(
        idname="nwo.join_halo", type="J", value="PRESS", alt=True
    )
    keys.append((km, kmi))

    kmi = km.keymap_items.new(
        idname="nwo.apply_types_mesh_pie",
        type="F",
        value="PRESS",
        ctrl=True,
    )
    keys.append((km, kmi))

    kmi = km.keymap_items.new(
        idname="nwo.apply_types_marker_pie",
        type="F",
        value="PRESS",
        alt=True,
    )
    keys.append((km, kmi))

    kmi = km.keymap_items.new(
        idname="nwo.collection_create_move",
        type="M",
        value="PRESS",
        alt=True,
    )
    keys.append((km, kmi))
    
    kmi = km.keymap_items.new(
        idname="nwo.show_foundry_panel",
        type="F",
        value="PRESS",
        shift=True,
    )
    keys.append((km, kmi))
    
    # POSE MODE
    kmi = km.keymap_items.new(
        idname="nwo.lock_child_bone_location",
        type="G",
        value="PRESS",
        ctrl=True,
        shift=True,
    )
    keys.append((km, kmi))
    
    kmi = km.keymap_items.new(
        idname="nwo.lock_child_bone_rotation",
        type="R",
        value="PRESS",
        ctrl=True,
        shift=True,
    )
    keys.append((km, kmi))
    
    kmi = km.keymap_items.new(
        idname="nwo.lock_child_bone_scale",
        type="S",
        value="PRESS",
        ctrl=True,
        shift=True,
    )
    keys.append((km, kmi))

    # OUTLINER

    km = kc.keymaps.new(name="Outliner", space_type="OUTLINER")

    kmi = km.keymap_items.new(
        idname="nwo.collection_create_move",
        type="M",
        value="PRESS",
        alt=True,
    )
    keys.append((km, kmi))


def unregister():
    for km, kmi in keys:
        km.keymap_items.remove(kmi)

    keys.clear()
