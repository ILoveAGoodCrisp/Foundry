"""Native readers for authored PCA blendshape data and render-model metadata."""
import struct
from types import SimpleNamespace
from .backend import TagDocument


class PCAAnimationDocument(TagDocument):
    tag_ext = 'pca_animation'

    def mesh_data(self):
        return self.block(self.tag.root(), 'mesh data')

    def raw_vertices(self, mesh):
        return [tuple(self.value(v, 'position').to_array())
                for v in self.block(mesh, 'raw blendshape verts')]

    def coefficient_rows(self):
        rows = []
        for index, frame in enumerate(self.block(self.tag.root(), 'frame data')):
            data = self.value(frame, 'Coefficients')
            if len(data) % 4:
                raise ValueError(f'PCA frame {index} has an incomplete float coefficient')
            rows.append(struct.unpack('<' + 'f' * (len(data) // 4), data))
        return rows

    def render_mesh_info(self):
        reference = self.reference(self.tag.root(), 'RenderModel')
        if not self.path_exists(reference):
            return None
        with TagDocument(reference.RelativePathWithExtension, tags_root=self.tags_root,
                         game=self.game, definitions=self.definitions, must_exist=True) as render:
            geometry = render.required_field(render.tag.root(), 'render geometry').as_struct()
            meshes = render.block(geometry, 'per mesh temporary')
            indices = [render.value(e, 'mesh index') for e in render.block(geometry, 'PCA Mesh Indices')]
            indices = [i for i in indices if 0 <= i < len(meshes)]
            if not indices:
                return None
            counts = {len(render.block(meshes[i], 'raw vertices')): i for i in indices}
            compression = render.block(geometry, 'compression info')
            if not len(compression):
                raise ValueError('PCA render model has no compression bounds')
            limits = [v * 100 for name in ('position bounds 0', 'position bounds 1')
                      for v in render.value(compression[0], name).to_array()]
            bounds = SimpleNamespace(**dict(zip(('x0', 'x1', 'y0', 'y1', 'z0', 'z1'), limits)))
            return counts, bounds
