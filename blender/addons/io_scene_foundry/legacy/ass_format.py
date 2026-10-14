"""Blender-independent ASS data. Transforms and distances retain file units.

Geometry definitions are separate from instances, including pivots and skin
bindings, so an exporter can populate this model from evaluated virtual geometry.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

from .jms_format import Reader, JMSError, Vertex, Triangle


class ASSError(JMSError):
    pass


class ASSReader(Reader):
    def text(self):
        while not self.pending:
            try:
                line = next(self.stream)
            except StopIteration:
                raise ASSError(f'Unexpected end of ASS at line {self.line}') from None
            self.line += 1
            # ASS strings are quoted, may be empty, and may contain spaces or
            # semicolons. Backslashes in tag paths are literal, not escapes.
            pos = 0
            while pos < len(line):
                if line[pos].isspace():
                    pos += 1
                elif line[pos] == ';':
                    break
                elif line[pos] == '"':
                    end = line.find('"', pos + 1)
                    # Shipped ASS sources can contain unescaped quotes in
                    # names (e.g. %"-?bridge_cliffsupp05). Only a quote at a
                    # token boundary closes the string; keep interior quotes.
                    while (end >= 0 and end + 1 < len(line)
                           and not line[end + 1].isspace() and line[end + 1] != ';'):
                        end = line.find('"', end + 1)
                    if end < 0:
                        raise ASSError(f'Unterminated string at line {self.line}')
                    self.pending.append(line[pos + 1:end])
                    pos = end + 1
                else:
                    match = re.match(r'[^\s;]+', line[pos:])
                    self.pending.append(match[0])
                    pos += len(match[0])
        return self.pending.popleft()

    def transform(self, version):
        rotation, translation = self.vector(4), self.vector()
        scale = self.vector() if version == 1 else (self.number(),) * 3
        return Transform(rotation, translation, scale)


@dataclass(slots=True)
class Transform:
    rotation: tuple = (0, 0, 0, 1)
    translation: tuple = (0, 0, 0)
    scale: tuple = (1, 1, 1)


@dataclass(slots=True)
class Material:
    name: str
    variant: str
    lighting: tuple = ()

    def region_permutation(self):
        parts = self.variant.split()
        return (parts[-1] if parts else 'default', parts[-2] if len(parts) > 1 else 'default')


@dataclass(slots=True)
class Light:
    kind: str
    color: tuple
    intensity: float
    hotspot: float
    falloff: float
    near_enabled: int
    near_start: float
    near_end: float
    far_enabled: int
    far_start: float
    far_end: float
    shape: int
    aspect: float


@dataclass
class Geometry:
    kind: str
    xref_path: str = ''
    xref_name: str = ''
    material: int = -1
    dimensions: tuple = ()
    vertices: list = field(default_factory=list)
    triangles: list = field(default_factory=list)
    node_indices: list = field(default_factory=list)
    light: Light | None = None


@dataclass(slots=True)
class Instance:
    geometry: int
    name: str
    unique_id: int
    parent: int
    inheritance: int
    local: Transform
    pivot: Transform
    bones: tuple = ()


@dataclass
class ASS:
    name: str = ''
    version: int = 7
    header: tuple = ()
    materials: list = field(default_factory=list)
    geometries: list = field(default_factory=list)
    instances: list = field(default_factory=list)
    invalid_uv_components: int = 0
    first_invalid_uv_line: int = 0

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
        r = ASSReader(stream)
        a = cls(name=name, version=r.integer())
        if a.version not in range(1, 8):
            raise ASSError(f'Unsupported ASS version {a.version}')
        v = a.version
        a.header = tuple(r.text() for _ in range(4))
        for _ in r.count():
            name, variant = r.text(), r.text()
            lighting = tuple(r.text() for _ in r.count()) if v >= 4 else ()
            a.materials.append(Material(name, variant, lighting))
        for _ in r.count():
            g = Geometry(r.text(), r.text(), r.text())
            if g.kind in {'SPHERE', 'BOX', 'PILL'}:
                g.material = r.integer()
                g.dimensions = r.vector({'SPHERE': 1, 'BOX': 3, 'PILL': 2}[g.kind])
            elif g.kind == 'MESH':
                nodes = {}
                for _ in r.count():
                    position, normal = r.vector(), r.vector()
                    color = r.vector() if v >= 6 else None
                    influences = tuple((r.integer(), r.number()) for _ in r.count())
                    for index, _ in influences:
                        nodes.setdefault(index, None)
                    uvs = tuple(r.uv_vector(3 if v >= 5 else 2) for _ in r.count())
                    g.vertices.append(Vertex(position, normal, influences, uvs, color))
                g.node_indices = list(nodes)
                for _ in r.count():
                    g.triangles.append(Triangle(r.integer(), tuple(r.integer() for _ in range(3))))
            elif g.kind == 'GENERIC_LIGHT':
                g.light = Light(r.text(), r.vector(), r.number(), r.number(), r.number(),
                                r.integer(), r.number(), r.number(), r.integer(),
                                r.number(), r.number(), r.integer(), r.number())
            else:
                raise ASSError(f'Unknown ASS geometry class {g.kind!r} at line {r.line}')
            a.geometries.append(g)
        for _ in r.count():
            geometry = r.integer()
            if geometry < -1 or geometry >= len(a.geometries):
                raise ASSError(f'Invalid ASS geometry index {geometry} at line {r.line}')
            i = Instance(geometry, r.text(), r.integer(), r.integer(), r.integer(),
                         r.transform(v), r.transform(v))
            count = len(a.geometries[geometry].node_indices) if geometry != -1 else 0
            i.bones = tuple(r.integer() for _ in range(count))
            a.instances.append(i)
        try:
            extra = r.text()
        except ASSError as error:
            if not str(error).startswith('Unexpected end'):
                raise
        else:
            raise ASSError(f'Unexpected ASS data at line {r.line}: {extra!r}')
        a.invalid_uv_components = r.invalid_uv_components
        a.first_invalid_uv_line = r.first_invalid_uv_line
        a.validate()
        return a

    def validate(self):
        def index(i, records, label):
            if i != -1 and not 0 <= i < len(records):
                raise ASSError(f'Invalid ASS {label} index {i}')
        for g in self.geometries:
            index(g.material, self.materials, 'material')
            if any(d < 0 for d in g.dimensions):
                raise ASSError('Negative ASS primitive dimension')
            for t in g.triangles:
                index(t.material, self.materials, 'material')
                if any(i < 0 or i >= len(g.vertices) for i in t.vertices):
                    raise ASSError('Invalid ASS triangle vertex')
            for vert in g.vertices:
                if any(weight < 0 or node < -1 for node, weight in vert.influences):
                    raise ASSError('Invalid ASS vertex influence')
                if any(node >= len(g.node_indices) for node, _ in vert.influences):
                    raise ASSError('Invalid ASS local bone palette index')
        for instance in self.instances:
            index(instance.geometry, self.geometries, 'geometry')
            index(instance.parent, self.instances, 'parent')
            for bone in instance.bones:
                index(bone, self.instances, 'bone')
        self.instance_order()

    def instance_order(self):
        """Linear, non-recursive topological order; parents are array indices."""
        done, order = set(), []
        for start in range(len(self.instances)):
            chain, visiting, current = [], set(), start
            while current != -1 and current not in done:
                if current in visiting:
                    raise ASSError('Cyclic ASS instance hierarchy')
                visiting.add(current)
                chain.append(current)
                current = self.instances[current].parent
            for index in reversed(chain):
                done.add(index)
                order.append(index)
        return order
