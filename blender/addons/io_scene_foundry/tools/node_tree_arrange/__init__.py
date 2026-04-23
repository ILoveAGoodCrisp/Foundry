import bpy
from mathutils import Vector
from .sugiyama import sugiyama_layout
from . import config

def arrange(tree: bpy.types.NodeTree):
    # return # Until I can figure out why this crashes
    config.selected = list(tree.nodes)
    config.MARGIN = Vector((150, 150)).freeze()
    config.tree = tree
    try:
        sugiyama_layout(tree)
    finally:
        config.reset()
