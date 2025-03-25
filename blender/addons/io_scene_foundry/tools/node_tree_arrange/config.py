# Code adapted from node-arrange (GPLv3) by Leonardo Pike-Excell
# https://github.com/Leonardo-Pike-Excell/node-arrange

from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING

from bpy.types import Node, NodeSocket
from mathutils import Vector

selected: list[Node] = []
linked_sockets = defaultdict(set)
multi_input_sort_ids = defaultdict(dict)

MARGIN: Vector

def reset() -> None:
    selected.clear()
    linked_sockets.clear()
    multi_input_sort_ids.clear()

    global MARGIN
    MARGIN = None
