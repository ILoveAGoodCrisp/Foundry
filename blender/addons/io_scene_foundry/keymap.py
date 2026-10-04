import bpy

keys = []

SHORTCUTS = (
    ('3D View', 'Show Foundry Panel', 'nwo.show_foundry_panel'),
    ('3D View', 'Apply Mesh Type', 'nwo.apply_types_mesh_pie'),
    ('3D View', 'Apply Marker Type', 'nwo.apply_types_marker_pie'),
    ('3D View', 'Halo Join', 'nwo.join_halo'),
    ('3D View', 'Move to Halo Collection', 'nwo.collection_create_move'),
    ('3D View', 'Translate Bone Without Children', 'nwo.translate_bone_without_children'),
    ('3D View', 'Rotate Bone Without Children', 'nwo.rotate_bone_without_children'),
    ('3D View', 'Resize Bone Without Children', 'nwo.resize_bone_without_children'),
    ('Outliner', 'Move to Halo Collection', 'nwo.collection_create_move'),
)


def draw_shortcuts(layout, context):
    """Edit the effective user keymap so Blender persists user overrides."""
    config = context.window_manager.keyconfigs.user
    if config is None:
        layout.label(text='Keyboard shortcuts are unavailable', icon='INFO')
        return
    layout.label(text='Click a shortcut to change its keys.')
    previous_map = None
    for map_name, label, operator in SHORTCUTS:
        if map_name != previous_map:
            col = layout.column(align=True)
            col.label(text=map_name)
            previous_map = map_name
        keymap = config.keymaps.get(map_name)
        items = [item for item in keymap.keymap_items if item.idname == operator] if keymap else []
        if not items:
            row = col.row()
            row.enabled = False
            row.label(text=label)
            row.label(text='Not assigned')
            continue
        for item in items:
            row = col.row(align=True)
            row.context_pointer_set('keymap', keymap)
            row.prop(item, 'active', text='')
            row.label(text=label)
            row.prop(item, 'type', text='', full_event=True)
            if item.is_user_modified and not item.is_user_defined:
                row.operator('preferences.keyitem_restore', text='', icon='BACK').item_id = item.id
    if not context.preferences.use_preferences_save or bpy.app.use_userpref_skip_save_on_exit:
        layout.operator('wm.save_userpref', text='Save Preferences', icon='FILE_TICK')


def register():
    wm = bpy.context.window_manager
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
        idname="nwo.translate_bone_without_children",
        type="G",
        value="PRESS",
        ctrl=True,
        shift=True,
    )
    keys.append((km, kmi))
    
    kmi = km.keymap_items.new(
        idname="nwo.rotate_bone_without_children",
        type="R",
        value="PRESS",
        ctrl=True,
        shift=True,
    )
    keys.append((km, kmi))
    
    kmi = km.keymap_items.new(
        idname="nwo.resize_bone_without_children",
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
