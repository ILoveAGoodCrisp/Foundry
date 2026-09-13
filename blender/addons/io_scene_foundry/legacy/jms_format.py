"""Blender-independent JMS interchange data, reusable by a future exporter.

Distances are JMS units; rotations are file-order XYZW. No scene conversion or
material creation occurs here. VirtualScene adapters belong at the boundary.
"""
from dataclasses import dataclass, field
from collections import defaultdict, deque
from pathlib import Path
import math
import re


@dataclass(slots=True)
class Transform:
    rotation: tuple
    translation: tuple


@dataclass(slots=True)
class Node:
    name: str
    parent: int
    transform: Transform
    child: int = -1
    sibling: int = -1


@dataclass(slots=True)
class Material:
    name: str
    definition: str
    region: str = 'default'
    permutation: str = 'default'
    lod: str = ''
    texture: str = ''


@dataclass(slots=True)
class Marker:
    name: str
    region: int
    parent: int
    transform: Transform
    radius: float


@dataclass(slots=True)
class Vertex:
    position: tuple
    normal: tuple
    influences: tuple
    uvs: tuple
    color: tuple | None = None
    region: int = -1


@dataclass(slots=True)
class Triangle:
    material: int
    vertices: tuple
    region: int = -1


@dataclass(slots=True)
class Shape:
    kind: str
    name: str
    parent: int
    material: int
    transform: Transform
    dimensions: tuple = ()
    vertices: tuple = ()


@dataclass(slots=True)
class Constraint:
    kind: str
    name: str
    parent: int
    child: int
    parent_transform: Transform
    child_transform: Transform
    limits: tuple


class JMSError(ValueError):
    pass


class Reader:
    """Stream records; numeric fields can share a line, names can contain spaces."""
    def __init__(self, stream):
        self.stream = iter(stream)
        self.pending = deque()
        self.line = 0

    def text(self):
        while not self.pending:
            try:
                line = next(self.stream)
            except StopIteration:
                raise JMSError(f'Unexpected end of JMS at line {self.line}') from None
            self.line += 1
            # An attached semicolon is a shader flag, not a comment.
            line = re.split(r'(?<!\S);', line, maxsplit=1)[0].strip()
            self.pending.extend(p.strip() for p in line.split('\t') if p.strip())
        return self.pending.popleft()

    def number(self, integer=False):
        parts = self.text().split()
        if not parts:
            raise JMSError(f'Expected number at line {self.line}')
        self.pending.extendleft(reversed(parts[1:]))
        try:
            if integer and re.fullmatch(r'[+-]?\d+', parts[0]):
                return int(parts[0])
            value = float(parts[0].replace(',', '.'))
            if not math.isfinite(value) or (integer and value != int(value)):
                raise ValueError
            return int(value) if integer else value
        except (ValueError, OverflowError):
            raise JMSError(f'Invalid number at line {self.line}: {parts[0]!r}') from None

    def integer(self):
        return self.number(True)

    def count(self):
        n = self.integer()
        if n < 0:
            raise JMSError(f'Negative count at line {self.line}')
        return range(n)

    def vector(self, size=3):
        return tuple(self.number() for _ in range(size))

    def transform(self):
        return Transform(self.vector(4), self.vector())


@dataclass
class JMS:
    name: str = ''
    version: int = 8213
    checksum: int = 0
    nodes: list = field(default_factory=list)
    materials: list = field(default_factory=list)
    markers: list = field(default_factory=list)
    xrefs: list = field(default_factory=list)
    instances: list = field(default_factory=list)
    regions: list = field(default_factory=list)
    vertices: list = field(default_factory=list)
    triangles: list = field(default_factory=list)
    shapes: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    bounding_spheres: list = field(default_factory=list)
    skylights: list = field(default_factory=list)

    @classmethod
    def from_file(cls, filepath):
        path = Path(filepath)
        with path.open('rb') as stream:
            bom = stream.read(2)
        encoding = 'utf-16' if bom in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig'
        try:
            with path.open(encoding=encoding) as stream:
                return cls.read(stream, path.stem)
        except UnicodeDecodeError:
            with path.open(encoding='cp1252') as stream:
                return cls.read(stream, path.stem)

    @classmethod
    def read(cls, stream, name=''):
        r = Reader(stream)
        j = cls(name=name, version=r.integer())
        v = j.version
        if not 8197 <= v <= 8213:
            raise JMSError(f'Unsupported JMS version: {v}')
        if v < 8205:
            j.checksum = r.integer()
        for _ in r.count():
            name = r.text()
            if v >= 8205:
                j.nodes.append(Node(name, r.integer(), r.transform()))
            else:
                child, sibling = r.integer(), r.integer()
                j.nodes.append(Node(name, -1, r.transform(), child, sibling))
        for _ in r.count():
            name = r.text()
            texture = r.text() if 8202 <= v <= 8204 else ''
            definition = r.text()
            m = Material(name, definition, texture=texture)
            if v >= 8201:
                parts = []
                for part in definition.split():
                    if re.fullmatch(r'\(\d+\)', part):
                        continue
                    if re.fullmatch(r'L\d+', part, re.I):
                        m.lod = part.lower()
                    else:
                        parts.append(part)
                if parts:
                    m.region = parts[-1]
                if len(parts) > 1:
                    m.permutation = parts[-2]
            j.materials.append(m)
        for _ in r.count():
            name = r.text()
            region = r.integer() if 8198 <= v < 8205 else -1
            j.markers.append(Marker(name, region, r.integer(), r.transform(), r.number() if v >= 8200 else 1.0))
        if v >= 8201:
            for _ in r.count():
                j.xrefs.append((r.text(), r.text() if v >= 8208 else ''))
            for _ in r.count():
                name = r.text()
                uid = r.integer() if v >= 8203 else 0
                j.instances.append((name, uid, r.integer(), r.transform()))
        if v < 8205:
            j.regions = [r.text() for _ in r.count()]
        for _ in r.count():
            region, color = -1, None
            if v >= 8205:
                position, normal = r.vector(), r.vector()
                weights = tuple((r.integer(), r.number()) for _ in r.count())
                uvs = tuple(r.vector(2) for _ in r.count())
                if v >= 8211:
                    color = r.vector()
            else:
                if v == 8197:
                    region = r.integer()
                n0 = r.integer()
                w0 = r.number() if v == 8204 else 1.0
                position, normal = r.vector(), r.vector()
                n1, w1 = r.integer(), r.number()
                if v != 8204:
                    w0 = 1.0 - w1 if n1 != -1 else 1.0
                weights = ((n0, w0), (n1, w1))
                if v == 8204:
                    weights += tuple((r.integer(), r.number()) for _ in range(2))
                uvs = tuple(r.vector(2) for _ in range(4 if v >= 8202 else 1))
                if v >= 8199:
                    r.integer()
            j.vertices.append(Vertex(position, normal, weights, uvs, color, region))
        for _ in r.count():
            region = r.integer() if 8198 <= v < 8205 else -1
            material = r.integer()
            j.triangles.append(Triangle(material, tuple(r.integer() for _ in range(3)), region))
        if v >= 8206:
            for kind, size in (('sphere', 1), ('box', 3), ('pill', 2), ('convex', 0)):
                for _ in r.count():
                    name, parent = r.text(), r.integer()
                    material = r.integer() if v >= 8207 else -1
                    transform = r.transform()
                    dimensions = r.vector(size)
                    vertices = tuple(r.vector() for _ in r.count()) if kind == 'convex' else ()
                    j.shapes.append(Shape(kind, name, parent, material, transform, dimensions, vertices))
            # Six angular limits; 8213 adds one friction value.
            for kind, size in (('ragdoll', 7 if v >= 8213 else 6), ('hinge', 4)):
                j._read_constraints(r, kind, size)
        if v >= 8210:
            for kind, size in (('car_wheel', 5), ('point_to_point', 8), ('prismatic', 4)):
                j._read_constraints(r, kind, size)
        if v >= 8209:
            j.bounding_spheres = [(r.vector(), r.number()) for _ in r.count()]
        if v >= 8212:
            j.skylights = [(r.vector(), r.vector(), r.number()) for _ in r.count()]
        try:
            extra = r.text()
        except JMSError:
            pass
        else:
            raise JMSError(f'Unexpected trailing JMS data at line {r.line}: {extra!r}')
        j.validate()
        return j

    def _read_constraints(self, r, kind, size):
        for _ in r.count():
            self.constraints.append(Constraint(kind, r.text(), r.integer(), r.integer(), r.transform(), r.transform(), r.vector(size)))

    def validate(self):
        def index(i, items, label, optional=True):
            if not (optional and i == -1) and not 0 <= i < len(items):
                raise JMSError(f'Invalid {label} index: {i}')
        if len({n.name for n in self.nodes}) != len(self.nodes):
            raise JMSError('Duplicate JMS node names')
        if self.version < 8205:
            for node in self.nodes:
                node.parent = -1
            for parent, node in enumerate(self.nodes):
                index(node.sibling, self.nodes, 'sibling')
                child, seen = node.child, set()
                while child != -1:
                    index(child, self.nodes, 'child')
                    if child in seen or self.nodes[child].parent != -1:
                        raise JMSError('Cyclic or multiply parented JMS node graph')
                    seen.add(child)
                    self.nodes[child].parent = parent
                    child = self.nodes[child].sibling
        for n in self.nodes:
            index(n.parent, self.nodes, 'parent')
        done = set()
        for start in range(len(self.nodes)):
            chain, current = set(), start
            while current != -1 and current not in done:
                if current in chain:
                    raise JMSError('Cyclic JMS node graph')
                chain.add(current)
                current = self.nodes[current].parent
            done.update(chain)
        for vertex in self.vertices:
            index(vertex.region, self.regions, 'vertex region')
            for node, weight in vertex.influences:
                index(node, self.nodes, 'vertex node')
                if weight < 0:
                    raise JMSError('Negative JMS vertex weight')
        for triangle in self.triangles:
            index(triangle.material, self.materials, 'material')
            index(triangle.region, self.regions, 'triangle region')
            for vertex in triangle.vertices:
                index(vertex, self.vertices, 'vertex', False)
        for item in self.markers + self.shapes:
            index(item.parent, self.nodes, 'parent')
        for marker in self.markers:
            index(marker.region, self.regions, 'marker region')
            # Tool-generated JMS files use negative marker radii for unspecified
            # sizes. Preserve the source value; the scene adapter supplies a size.
        for shape in self.shapes:
            index(shape.material, self.materials, 'shape material')
            if any(d < 0 for d in shape.dimensions):
                raise JMSError('Negative JMS shape dimensions')
        for constraint in self.constraints:
            index(constraint.parent, self.nodes, 'constraint parent')
            index(constraint.child, self.nodes, 'constraint child')
        for _, _, path, _ in self.instances:
            index(path, self.xrefs, 'xref', False)

    def triangle_groups(self):
        """Partition once; preserve source material indices through deduplication."""
        groups = defaultdict(list)
        for triangle in self.triangles:
            material = self.materials[triangle.material] if triangle.material != -1 else Material('default', '')
            region = triangle.region
            if self.version == 8197:
                region = self.vertices[triangle.vertices[0]].region
            region_name = self.regions[region] if region != -1 else material.region
            groups[(region_name, material.permutation, material.lod)].append(triangle)
        return groups
