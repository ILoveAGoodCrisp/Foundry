import bpy
from mathutils import Vector
from .sugiyama import sugiyama_layout
from . import config

def arrange(tree: bpy.types.NodeTree):
    config.selected = list(tree.nodes)
    config.MARGIN = Vector((50, 50)).freeze()
    config.tree = tree
    try:
        sugiyama_layout(tree)
    finally:
        config.reset()