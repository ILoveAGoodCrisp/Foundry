"""Native shader metadata used during the incremental shader migration."""
from .backend import TagDocument
from .blender import BlenderTag


class EmptyShaderTag(BlenderTag, TagDocument):
    """Create an empty shader tag using the schema selected by the path suffix."""


class MaterialMetadataTag(BlenderTag, TagDocument):
    tag_ext = 'material'

    def global_material(self):
        return self.value(self.tag.root(), 'physics material name')

    def get_albedo_bitmap(self):
        for element in self.block(self.tag.root(), 'material parameters'):
            if self.value(element, 'parameter name') == 'color_map':
                bitmap = self.reference(element, 'bitmap')
                if self.path_exists(bitmap):
                    return bitmap
        return None

    def albedo_fill_alpha(self):
        field = self.required_field(self.tag.root(), 'alpha blend mode')
        return field.options().current < 1


class ShaderMetadataTag(BlenderTag, TagDocument):
    def _render_method(self):
        field = self.required_field(self.tag.root(), 'render_method')
        render_method = field.as_struct()
        if render_method is None:
            raise TypeError(f'{self.path}: render_method is not a struct')
        return render_method

    def global_material(self, visited=None):
        visited = set() if visited is None else visited
        identity = self.path.lower()
        if identity in visited:
            raise ValueError(f'Circular shader reference at {self.path}')
        visited.add(identity)
        root = self.tag.root()
        field = root.field('material name') or root.field('material name 0')
        if field is None:
            return ''
        material = field.value
        if material:
            return material
        render_method = self._render_method()
        reference_field = render_method.field('reference')
        if reference_field is None:
            return ''
        reference = self.reference(render_method, 'reference')
        if not self.path_exists(reference):
            return ''
        with ShaderMetadataTag(path=reference) as parent:
            return parent.global_material(visited)

    def get_albedo_bitmap(self):
        for element in self.block(self._render_method(), 'parameters'):
            if self.value(element, 'parameter name') == 'base_map':
                bitmap = self.reference(element, 'bitmap')
                if self.path_exists(bitmap):
                    return bitmap
        return None

    def _option(self, index):
        options = self.block(self._render_method(), 'options')
        if index >= len(options):
            raise ValueError(f'{self.path}: missing render-method option {index}')
        return self.value(options[index], 'short')

    def is_opaque(self):
        return self._option(2) == 0 and self._option(7) == 0

    def albedo_fill_alpha(self):
        return self._option(7) < 1


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
