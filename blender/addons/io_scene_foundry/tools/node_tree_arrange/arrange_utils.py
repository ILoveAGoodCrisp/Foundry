# Code adapted from node-arrange (GPLv3) by Leonardo Pike-Excell
# https://github.com/Leonardo-Pike-Excell/node-arrange

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable
from operator import itemgetter
from typing import TypeVar

import bpy
from bpy.types import Node
from mathutils import Vector

from . import config

# Updated this function to just pull the tree from config, rather than the edit_tree (which is not relevant for this approach)
def get_ntree() -> bpy.types.NodeTree:
    return config.tree

_T1 = TypeVar('_T1', bound=Hashable)
_T2 = TypeVar('_T2', bound=Hashable)


def group_by(
  iterable: Iterable[_T1],
  key: Callable[[_T1], _T2],
  sort: bool = False,
) -> dict[tuple[_T1, ...], _T2]:
    groups = defaultdict(list)
    for item in iterable:
        groups[key(item)].append(item)

    items = sorted(groups.items(), key=itemgetter(0)) if sort else groups.items()
    return {tuple(g): k for k, g in items}


def abs_loc(node: Node) -> Vector:
    loc = node.location.copy()

    parent = node
    while parent := parent.parent:
        loc += parent.location

    return loc


REROUTE_DIM = Vector((8, 8))

# This function now no uses dimension. Dimension is calculated once the nodes have been drawn once
# As I am sorting the nodes before drawing (and invoking drawing adds complexity and time)
# I have opted to calculate the proper width and heights of nodes
# NOTE this code will like need to be updated as Blender adds / updates nodes
def dimensions(node: Node) -> Vector:
    height_fac = 25
    if node.bl_idname != 'NodeReroute':
        assert bpy.context
        added_height = 0
        match node.bl_idname:
            case 'ShaderNodeTexImage':
                added_height = height_fac * 5
            case 'ShaderNodeFloatCurve':
                added_height = height_fac * 5
        return Vector((node.width, height_fac *(len(node.inputs) + len(node.outputs)) + node.height + added_height)) / bpy.context.preferences.system.ui_scale
    else:
        return REROUTE_DIM


_HIDE_OFFSET = 10


def get_top(node: Node, y_loc: float | None = None) -> float:
    if y_loc is None:
        y_loc = abs_loc(node).y

    return (y_loc + dimensions(node).y / 2) - _HIDE_OFFSET if node.hide else y_loc


def get_bottom(node: Node, y_loc: float | None = None) -> float:
    if y_loc is None:
        y_loc = abs_loc(node).y

    dim_y = dimensions(node).y
    bottom = y_loc - dim_y
    return bottom + dim_y / 2 - _HIDE_OFFSET if node.hide else bottom


_MAX_LOC = 100_000


def move(node: Node, *, x: float = 0, y: float = 0) -> None:
    if x == 0 and y == 0:
        return

    # If the (absolute) value of a node's X/Y axis exceeds 100k,
    # `node.location` can't be affected directly. (This often happens with
    # frames since their locations are relative.)

    loc = node.location
    if abs(loc.x + x) <= _MAX_LOC and abs(loc.y + y) <= _MAX_LOC:
        loc += Vector((x, y))
