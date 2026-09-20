"""Native shader metadata used during the incremental shader migration."""
from .backend import TagDocument
from .blender import BlenderTag


class EmptyShaderTag(BlenderTag, TagDocument):
    """Create an empty shader tag using the schema selected by the path suffix."""


class ShaderTerrainMetadataTag(BlenderTag, TagDocument):
    tag_ext = 'shader_terrain'

    def global_material(self, visited=None):
        visited = set() if visited is None else visited
        identity = self.path.lower()
        if identity in visited:
            raise ValueError(f'Circular terrain shader reference at {self.path}')
        visited.add(identity)

        root = self.tag.root()
        material = self.value(root, 'material name 0')
        if material:
            return material
        render_method_field = root.field('render_method')
        if render_method_field is None:
            return material
        render_method = render_method_field.as_struct()
        if render_method is None:
            raise TypeError(f'{self.path}: render method is not a struct')
        reference = self.reference(render_method, 'reference')
        if not self.path_exists(reference):
            return material
        with ShaderTerrainMetadataTag(path=reference) as parent:
            return parent.global_material(visited)
