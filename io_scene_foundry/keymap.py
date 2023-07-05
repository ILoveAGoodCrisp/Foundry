# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

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
        idname="nwo.join_halo", type="J", value="PRESS", ctrl=True, shift=True
    )
    keys.append((km, kmi))

    kmi = km.keymap_items.new(
        idname="nwo.apply_types_mesh_pie",
        type="F",
        value="PRESS",
        ctrl=True,
        shift=False,
    )
    keys.append((km, kmi))

    kmi = km.keymap_items.new(
        idname="nwo.apply_types_marker_pie",
        type="F",
        value="PRESS",
        ctrl=False,
        shift=True,
    )
    keys.append((km, kmi))

    kmi = km.keymap_items.new(
        idname="nwo.collection_create_move",
        type="M",
        value="PRESS",
        alt=True,
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
