# Code adapted from node-arrange (GPLv3) by Leonardo Pike-Excell
# https://github.com/Leonardo-Pike-Excell/node-arrange

from __future__ import annotations

import ctypes
import platform
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from math import inf
from typing import TYPE_CHECKING, Literal, TypeGuard

import bpy
from bpy.types import Node, NodeFrame, NodeSocket

from .arrange_utils import REROUTE_DIM, abs_loc, dimensions, get_bottom, get_top

if TYPE_CHECKING:
    from .placement.linear_segments import Segment


class GType(Enum):
    NODE = auto()
    DUMMY = auto()
    CLUSTER = auto()
    HORIZONTAL_BORDER = auto()
    VERTICAL_BORDER = auto()


@dataclass(slots=True)
class CrossingReduction:
    socket_ranks: dict[Socket, float] = field(default_factory=dict)
    barycenter: float | None = None

    def reset(self) -> None:
        self.socket_ranks.clear()
        self.barycenter = None


_NonCluster = Literal[GType.NODE, GType.DUMMY, GType.HORIZONTAL_BORDER, GType.VERTICAL_BORDER]


def is_real(v: GNode | Cluster) -> TypeGuard[_RealGNode]:
    return isinstance(v.node, Node)


class GNode:
    node: Node | None
    cluster: Cluster | None
    type: _NonCluster

    is_reroute: bool
    width: float
    height: float

    rank: int
    po_num: int
    lowest_po_num: int

    col: list[GNode]
    cr: CrossingReduction

    x: float
    y: float

    segment: Segment

    root: GNode
    aligned: GNode
    cells: tuple[list[int], list[float]] | None
    sink: GNode
    shift: float

    __slots__ = tuple(__annotations__)

    def __init__(
      self,
      node: Node | None = None,
      cluster: Cluster | None = None,
      type: _NonCluster = GType.NODE,
      rank: int | None = None,
    ) -> None:
        real = isinstance(node, Node)

        self.node = node
        self.cluster = cluster
        self.type = type
        self.rank = rank  # type: ignore
        self.is_reroute = type == GType.DUMMY or (real and node.bl_idname == 'NodeReroute')

        if self.is_reroute:
            self.width = REROUTE_DIM.x
            self.height = REROUTE_DIM.y
        elif real:
            self.width = dimensions(node).x
            self.height = get_top(node) - get_bottom(node)
        else:
            self.width = 0
            self.height = 0

        self.po_num = None  # type: ignore
        self.lowest_po_num = None  # type: ignore

        self.col = None  # type: ignore
        self.cr = CrossingReduction()

        self.x = None  # type: ignore
        self.reset()

        self.segment = None  # type: ignore

    def __hash__(self) -> int:
        return id(self)

    def reset(self) -> None:
        self.root = self
        self.aligned = self
        self.cells = None

        self.sink = self
        self.shift = inf
        self.y = None  # type: ignore

    def corrected_y(self) -> float:
        assert is_real(self)
        return self.y + (abs_loc(self.node).y - get_top(self.node))


class _RealGNode(GNode):
    node: Node  # type: ignore


@dataclass(slots=True)
class Cluster:
    node: NodeFrame | None
    cluster: Cluster | None = None
    nesting_level: int | None = None
    cr: CrossingReduction = field(default_factory=CrossingReduction)
    left: GNode = field(init=False)
    right: GNode = field(init=False)

    def __post_init__(self) -> None:
        self.left = GNode(None, self, GType.HORIZONTAL_BORDER)
        self.right = GNode(None, self, GType.HORIZONTAL_BORDER)

    def __hash__(self) -> int:
        return id(self)

    @property
    def type(self) -> Literal[GType.CLUSTER]:
        return GType.CLUSTER


class bNodeStack(ctypes.Structure):
    vec: ctypes.c_float * 4
    min: ctypes.c_float
    max: ctypes.c_float
    data: ctypes.c_void_p
    hasinput: ctypes.c_short
    hasoutput: ctypes.c_short
    datatype: ctypes.c_short
    sockettype: ctypes.c_short
    is_copy: ctypes.c_short
    external: ctypes.c_short
    _pad: ctypes.c_char * 4


class bNodeSocketRuntimeHandle(ctypes.Structure):
    if platform.system() == 'Windows':
        _pad0: ctypes.c_char * 8
    declaration: ctypes.c_void_p
    changed_flag: ctypes.c_uint32
    total_inputs: ctypes.c_short
    _pad1: ctypes.c_char * 2
    location: ctypes.c_float * 2


class bNodeSocket(ctypes.Structure):
    next: ctypes.c_void_p
    prev: ctypes.c_void_p
    prop: ctypes.c_void_p
    identifier: ctypes.c_char * 64
    name: ctypes.c_char * 64
    storage: ctypes.c_void_p
    in_out: ctypes.c_short
    typeinfo: ctypes.c_void_p
    idname: ctypes.c_char * 64
    default_value: ctypes.c_void_p
    _pad: ctypes.c_char * 4
    label: ctypes.c_char * 64
    description: ctypes.c_char * 64
    short_label: ctypes.c_char * 64
    default_attribute_name: ctypes.POINTER(ctypes.c_char)
    to_index: ctypes.c_int
    link: ctypes.c_void_p
    ns: bNodeStack
    runtime: ctypes.POINTER(bNodeSocketRuntimeHandle)


for cls in (bNodeStack, bNodeSocketRuntimeHandle, bNodeSocket):
    cls._fields_ = [(k, eval(v)) for k, v in cls.__annotations__.items()]


def get_socket_y(socket: NodeSocket) -> float:
    b_socket = bNodeSocket.from_address(socket.as_pointer())
    ui_scale = bpy.context.preferences.system.ui_scale  # type: ignore
    return b_socket.runtime.contents.location[1] / ui_scale


@dataclass(frozen=True)
class Socket:
    owner: GNode
    idx: int
    is_output: bool

    @property
    def bpy(self) -> NodeSocket | None:
        v = self.owner

        if not is_real(v):
            return None

        sockets = v.node.outputs if self.is_output else v.node.inputs
        return sockets[self.idx]

    @property
    def x(self) -> float:
        v = self.owner
        return v.x + v.width if self.is_output else v.x

    @cached_property
    def _offset_y(self) -> float:
        v = self.owner

        if v.is_reroute or not is_real(v):
            return 0

        assert self.bpy
        return get_socket_y(self.bpy) - get_top(v.node)

    @property
    def y(self) -> float:
        return self.owner.y + self._offset_y
