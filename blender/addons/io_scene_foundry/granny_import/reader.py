"""Read GR2 data into the existing Blender importer's detached data contract."""
from math import floor

import numpy as np

from .container import Container, count
from .curves import sample
from .records import Records
from .textures import texture
from .transforms import Basis


def references(record, name, limit=100_000):
    values = record.get(name, ())
    count(len(values), limit)
    return [value for value in values if value is not None]


def object_id(record):
    return record.id if record else 0


class GrannyReader:
    def __init__(self, *, decompress=None, texture_decoder=None):
        self.decompress, self.texture_decoder = decompress, texture_decoder

    def read(self, path, animations=True, *, source_game=None, convert_scale=True):
        return self._read(Container.read(path, decompress=self.decompress), animations, source_game, convert_scale)

    def read_bytes(self, data, animations=True, *, source_game=None, convert_scale=True):
        return self._read(Container(data, decompress=self.decompress), animations, source_game, convert_scale)

    def _read(self, container, animations, source_game, convert_scale):
        records = Records(container)
        root = records.record(container.root_type, container.root_address)
        if not {'Models', 'Meshes', 'Skeletons'} <= {m.name for m in records.layout(root.dtype)[0]}:
            raise ValueError('GR2 root is not a file info record')
        models = references(root, 'Models')
        skeletons = {r.id: r for r in references(root, 'Skeletons')}
        meshes = {r.id: r for r in references(root, 'Meshes')}
        for model in models:
            skeleton = model.get('Skeleton')
            if skeleton:
                skeletons[skeleton.id] = skeleton
            for binding in references(model, 'MeshBindings'):
                mesh = binding.get('Mesh')
                if mesh:
                    meshes[mesh.id] = mesh
        basis = Basis(root.get('ArtToolInfo'), skeletons.values(), source_game, convert_scale)
        result = dict(materials={}, textures={}, skeletons={}, meshes={}, models=[], animations=[],
                      props=records.detach(root.get('ExtendedData')), source_basis=basis.info)
        textures = {r.id: r for r in references(root, 'Textures')}
        pending = references(root, 'Materials')
        for mesh in meshes.values():
            pending.extend(b.get('Material') for b in references(mesh, 'MaterialBindings'))
        while pending:
            material = pending.pop()
            if material is None or material.id in result['materials']:
                continue
            count(len(result['materials']) + 1, 100_000)
            maps = references(material, 'Maps')
            image = material.get('Texture')
            if image:
                textures[image.id] = image
            result['materials'][material.id] = dict(name=material.get('Name', ''),
                props=records.detach(material.get('ExtendedData')), texture=object_id(image),
                maps=[dict(usage=m.get('Usage', ''), material=object_id(m.get('Map'))) for m in maps])
            pending.extend(m.get('Map') for m in maps)
        for address, image in textures.items():
            result['textures'][address] = texture(image, self.texture_decoder)
        for address, skeleton in skeletons.items():
            bones = references(skeleton, 'Bones')
            parents = [b.get('ParentIndex') for b in bones]
            complete = set()
            for index in range(len(bones)):
                chain = set()
                current = index
                while current != -1 and current not in complete:
                    if not isinstance(current, int) or not 0 <= current < len(bones) or current in chain:
                        raise ValueError('Invalid GR2 skeleton parent hierarchy')
                    chain.add(current)
                    current = parents[current]
                complete.update(chain)
            result['skeletons'][address] = dict(name=skeleton.get('Name', ''), bones=[
                dict(name=b.get('Name', ''), parent=parents[i], matrix=basis.matrix(b.get('Transform')),
                     props=records.detach(b.get('ExtendedData'))) for i, b in enumerate(bones)])
        vertex_cache = {}
        for address, mesh in meshes.items():
            result['meshes'][address] = self.mesh(mesh, basis, vertex_cache)
        for model in models:
            bound_meshes = [b.get('Mesh') for b in references(model, 'MeshBindings')]
            result['models'].append(dict(name=model.get('Name', ''), skeleton=object_id(model.get('Skeleton')),
                matrix=basis.matrix(model.get('InitialPlacement')), props=records.detach(model.get('ExtendedData')),
                meshes=[mesh.id for mesh in bound_meshes if mesh is not None]))
        if animations:
            budget = 50_000_000
            for animation in references(root, 'Animations'):
                dt, duration = animation.get('TimeStep'), animation.get('Duration')
                if not np.isfinite(duration) or not np.isfinite(dt) or duration < 0 or dt <= 0:
                    raise ValueError('Invalid GR2 animation timing')
                n = count(max(1, int(floor(duration / dt + .001)) + 1), 100_000)
                times = np.arange(n) * dt
                groups = []
                for group in references(animation, 'TrackGroups'):
                    tracks = []
                    for track in references(group, 'TransformTracks'):
                        budget -= n * 16
                        if budget < 0:
                            raise ValueError('GR2 animation samples exceed the memory limit')
                        positions = sample(track.get('PositionCurve'), 3, times, (0, 0, 0))
                        orientations = sample(track.get('OrientationCurve'), 4, times, (0, 0, 0, 1), True)
                        scales = sample(track.get('ScaleShearCurve'), 9, times, (1, 0, 0, 0, 1, 0, 0, 0, 1))
                        positions, orientations, scales = basis.tracks(positions, orientations, scales)
                        tracks.append(dict(name=track.get('Name', ''), positions=positions, orientations=orientations, scales=scales))
                    name = group.get('Name', '')
                    skeleton = next((s for s in result['skeletons'].values() if s['name'].casefold() == name.casefold()), None)
                    root_bone = next((b for b in skeleton['bones'] if b['parent'] == -1 and b['name'].casefold() == name.casefold()), None) if skeleton else None
                    groups.append(dict(name=name, tracks=tracks, root_rest=root_bone['matrix'] if root_bone else None))
                result['animations'].append(dict(name=animation.get('Name', ''), dt=dt, duration=duration, groups=groups))
        return result

    def mesh(self, mesh, basis, vertex_cache):
        records = mesh.owner
        result = dict(name=mesh.get('Name', ''), props=records.detach(mesh.get('ExtendedData')),
                      materials=[object_id(b.get('Material')) for b in references(mesh, 'MaterialBindings')],
                      bones=[b.get('BoneName', '') for b in references(mesh, 'BoneBindings')])
        data, topology = mesh.get('PrimaryVertexData'), mesh.get('PrimaryTopology')
        missing = [name for name, record in (('primary_vertex_data', data), ('primary_topology', topology)) if record is None]
        if missing:
            result.update(vertices={}, component_names={}, triangles=np.empty((0, 3), dtype=np.int32),
                          groups=[], annotations={}, geometry_missing=missing)
            return result
        array = data.get('Vertices')
        count(len(array))
        indices32, indices16 = topology.get('Indices'), topology.get('Indices16')
        index_array = indices32 if indices32 else indices16
        count(len(index_array) if index_array else 0, 30_000_000)
        indices = index_array.scalar() if index_array else np.empty(0, dtype=np.int32)
        if not len(array) and not len(indices):
            result.update(vertices={}, component_names={}, triangles=np.empty((0, 3), dtype=np.int32),
                          groups=[], annotations={}, geometry_missing=['vertices'])
            return result
        if data.id not in vertex_cache:
            vertex_cache[data.id] = basis.vertices(array.numeric())
        vertices = vertex_cache[data.id]
        if 'Position' not in vertices:
            raise ValueError('GR2 mesh has no positions')
        # Index16 is declared as signed in standard Granny schemas but its
        # topology interpretation is an unsigned 16-bit vertex index.
        if not indices32 and indices16:
            indices = indices.astype(np.uint16)
        if len(indices) % 3 or (len(indices) and (indices.min() < 0 or indices.max() >= len(vertices['Position']))):
            raise ValueError('GR2 triangle index outside vertex array')
        triangles = indices.astype(np.int32).reshape(-1, 3)
        if basis.reflected:
            triangles = triangles[:, (2, 1, 0)].copy()
        names = references(data, 'VertexComponentNames', 1024)
        component_names = {member.name: names[i].get('String', '') for i, member in enumerate(records.layout(array.dtype)[0]) if i < len(names)}
        annotations = {}
        for annotation in references(topology, 'TriAnnotationSets', 1024):
            values, remap = annotation.get('TriAnnotations'), annotation.get('TriAnnotationIndices')
            if not values and not remap:
                continue
            count(len(values), 100_000)
            detached = [records.detach(record, allow_nonfinite=True) for record in values]
            if remap:
                indices = remap.scalar()
                if np.any(indices < 0) or np.any(indices >= len(detached)):
                    raise ValueError('Invalid GR2 triangle annotation index')
                detached = [detached[int(index)] for index in indices]
            if len(detached) != len(triangles):
                raise ValueError('GR2 triangle annotation count does not match geometry')
            annotations[annotation.get('Name', '')] = detached
        groups = [(g.get('MaterialIndex'), g.get('TriFirst'), g.get('TriCount')) for g in references(topology, 'Groups')]
        for material, first, length in groups:
            if material < 0 or first < 0 or length < 0 or first + length > len(triangles):
                raise ValueError('Invalid GR2 triangle material group')
        result.update(vertices=vertices, component_names=component_names, triangles=triangles, groups=groups, annotations=annotations)
        return result
