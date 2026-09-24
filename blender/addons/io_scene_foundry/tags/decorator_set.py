from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from types import SimpleNamespace
import bpy
from mathutils import Matrix

if TYPE_CHECKING:
    import blam_tags

from .bitmap import bitmap_to_image
from .. import import_transform, utils

from .render_model_blender import RenderModelTag

from .backend import TagDocument, ReferenceField
from .blender import BlenderTag

class DecoratorType:
    def __init__(self):
        self.render_model_instance_index = -1
        self.decorator_type_index = -1
        self.decorator_type_name = ""

class DecoratorSetTag(BlenderTag, TagDocument):
    tag_ext = 'decorator_set'
    
    def __init__(self, path='', **kwargs):
        super().__init__(path, **kwargs)
        for attribute, field in [('base', 'Base'), ('lod2', 'Lod2'), ('lod3', 'Lod3'),
                                 ('lod4', 'Lod4'), ('texture', 'texture')]:
            if attribute == 'base' and self.tag.root().field(field) is None:
                field = 'render model'
            reference = ReferenceField(self, field) if self.tag.root().field(field) is not None else SimpleNamespace(Path=None)
            setattr(self, 'reference_' + attribute, reference)

    @staticmethod
    def get_path_str(reference, full=False):
        return (reference.Filename if full else reference.RelativePathWithExtension) if reference else ''

    def ensure_default_type(self) -> bool | None:
        """Add mesh zero when instances exist; return None when no instance exists."""
        decorator_types = self.block(self.tag.root(), 'decorator types')
        if len(decorator_types):
            return False
        instances = self.block(self.tag.root(), 'render model instance names')
        if not len(instances):
            return None
        element = decorator_types[decorator_types.add()]
        self.required_field(element, 'mesh').set(0)
        self.tag_has_changes = True
        return True

    def set_render_shader(self, value: int) -> None:
        self.required_field(self.tag.root(), 'render shader').set(value)
        self.tag_has_changes = True
        
    def get_decorator_types(self) -> list[DecoratorType]:
        if self.game == 'halo2':
            decorator_types = []
            for index, element in enumerate(self.block(self.tag.root(), 'classes')):
                name = str(self.value(element, 'name')).strip()
                if not name:
                    continue
                dec_type = DecoratorType()
                dec_type.render_model_instance_index = index
                dec_type.decorator_type_index = index
                dec_type.decorator_type_name = name
                decorator_types.append(dec_type)
            return decorator_types
        decorator_types = []
        instances = self.block(self.tag.root(), 'render model instance names')
        instance_count = len(instances)
        for index, element in enumerate(self.block(self.tag.root(), 'decorator types')):
            value = self.value(element, 'mesh')
            if value > -1 and value < instance_count:
                name = self.value(instances[value], 'name')
                if name:
                    dec_type = DecoratorType()
                    dec_type.render_model_instance_index = value
                    dec_type.decorator_type_index = index
                    dec_type.decorator_type_name = name
                    decorator_types.append(dec_type)
                    
        return decorator_types
    
    def get_first_valid_render_model(self):
        base = self.get_path_str(self.reference_base.Path, True)
        lod2 = self.get_path_str(self.reference_lod2.Path, True)
        lod3 = self.get_path_str(self.reference_lod3.Path, True)
        lod4 = self.get_path_str(self.reference_lod4.Path, True)
        base_exists = base and Path(base).exists()
        lod2_exists = lod2 and Path(lod2).exists()
        lod3_exists = lod3 and Path(lod3).exists()
        lod4_exists = lod4 and Path(lod4).exists()
        
        if base_exists:
            return self.reference_base.Path
        if lod2_exists:
            return self.reference_lod2.Path
        if lod3_exists:
            return self.reference_lod3.Path
        if lod4_exists:
            return self.reference_lod4.Path
        
        return None

    def _halo2_materials(
        self, build_nodes: bool, always_extract_bitmaps: bool,
    ) -> dict[int, bpy.types.Material]:
        materials = {}
        for index, element in enumerate(self.block(self.tag.root(), 'shaders')):
            reference = self.reference(element, 'shader')
            if reference is None:
                continue
            material = bpy.data.materials.get(reference.ShortName)
            if material is None:
                material = bpy.data.materials.new(reference.ShortName)
            material.nwo.shader_path = reference.RelativePathWithExtension
            if build_nodes and self.path_exists(reference):
                from .shader_converter import ShaderTag
                with ShaderTag(path=reference) as shader:
                    shader.to_nodes(material, always_extract_bitmaps)
            materials[index] = material
        return materials

    def _halo2_model_object(
        self, model: blam_tags.TagStruct, vertices: blam_tags.TagBlock,
        indices: list[int], material: bpy.types.Material | None, name: str,
    ) -> bpy.types.Object | None:
        index_start = int(self.value(model, 'index start'))
        index_count = int(self.value(model, 'index count'))
        model_indices = indices[index_start:index_start + index_count]
        if len(model_indices) < 3:
            return None
        if len(model_indices) % 3:
            utils.print_warning(
                f'{self.tag_path.ShortName}: decorator model {name!r} has '
                f'{len(model_indices)} indices; ignoring its incomplete final triangle')
            model_indices = model_indices[:len(model_indices) // 3 * 3]
        used_indices = sorted(set(model_indices))
        if (not used_indices or used_indices[0] < 0
                or used_indices[-1] >= len(vertices)):
            utils.print_warning(
                f'{self.tag_path.ShortName}: decorator model {name!r} has an invalid vertex index')
            return None
        remap = {source: target for target, source in enumerate(used_indices)}
        positions = []
        normals = []
        texcoords = []
        for source_index in used_indices:
            vertex = vertices[source_index]
            position = self.value(vertex, 'position')
            normal = self.value(vertex, 'normal')
            texcoord = self.value(vertex, 'texcoord')
            positions.append((position.x, position.y, position.z))
            normals.append((normal.i, normal.j, normal.k))
            texcoords.append((texcoord.x, 1.0 - texcoord.y))
        faces = [tuple(remap[index] for index in model_indices[offset:offset + 3])
                 for offset in range(0, len(model_indices), 3)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(positions, [], faces)
        mesh.transform(import_transform.mesh_matrix() @ Matrix.Scale(100.0, 4))
        mesh.normals_split_custom_set_from_vertices(normals)
        uv_layer = mesh.uv_layers.new(name='UVMap0', do_init=False)
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv = texcoords[loop.vertex_index]
        if material is not None:
            mesh.materials.append(material)
        ob = bpy.data.objects.new(name, mesh)
        ob.nwo.decorator_lod = 'high'
        return ob

    def _halo2_quad_object(
        self, name: str, kind: str, scale: float,
        material: bpy.types.Material | None,
    ) -> bpy.types.Object:
        half = max(abs(scale), 1.0) * 0.5
        if kind in {'floating decal', 'projected decal'}:
            positions = ((-half, -half, 0.0), (half, -half, 0.0),
                         (half, half, 0.0), (-half, half, 0.0))
        else:
            positions = ((-half, 0.0, 0.0), (half, 0.0, 0.0),
                         (half, 0.0, half * 2.0), (-half, 0.0, half * 2.0))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(positions, [], ((0, 1, 2, 3),))
        mesh.transform(import_transform.mesh_matrix() @ Matrix.Scale(100.0, 4))
        uv_layer = mesh.uv_layers.new(name='UVMap0', do_init=False)
        texcoords = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv = texcoords[loop.vertex_index]
        if material is not None:
            mesh.materials.append(material)
        ob = bpy.data.objects.new(name, mesh)
        ob.nwo.decorator_lod = 'high'
        return ob

    def _to_blender_halo2(
        self, collection: bpy.types.Collection, build_materials: bool,
        always_extract_bitmaps: bool, single_type: str | None,
        only_single_type: bool,
    ) -> list[bpy.types.Object]:
        """Import Halo 2's embedded decorator models and generated quad classes."""
        root = self.tag.root()
        classes = self.block(root, 'classes')
        models = self.block(root, 'models')
        vertices = self.block(root, 'raw vertices')
        indices = [int(self.value(element, 'index'))
                   for element in self.block(root, 'indices')]
        materials = self._halo2_materials(build_materials, always_extract_bitmaps)
        result = []
        wanted = '' if single_type is None else single_type.casefold()
        for class_element in classes:
            class_name = str(self.value(class_element, 'name')).strip()
            if wanted and class_name.casefold() != wanted:
                continue
            kind = str(self.value(class_element, 'type')).casefold()
            class_scale = float(self.value(class_element, 'scale'))
            permutations = self.block(class_element, 'permutations')
            for permutation in permutations:
                permutation_name = str(self.value(permutation, 'name')).strip()
                shader_index = int(self.value(permutation, 'shader'))
                if not permutation_name and shader_index < 0:
                    continue
                name = permutation_name or class_name
                material = materials.get(shader_index)
                permutation_index = int(self.value(permutation, 'index'))
                ob = None
                if kind == 'model' and 0 <= permutation_index < len(models):
                    ob = self._halo2_model_object(
                        models[permutation_index], vertices, indices, material, name)
                elif kind != 'model':
                    ob = self._halo2_quad_object(name, kind, class_scale, material)
                if ob is None:
                    continue
                collection.objects.link(ob)
                result.append(ob)
                if only_single_type:
                    break
            if wanted or (only_single_type and result):
                break
        return result
        
    def to_blender(self, collection, get_material=False, always_extract_bitmaps=False, single_type=None, lod=0, only_single_type=False):
        if self.game == 'halo2':
            return self._to_blender_halo2(
                collection, get_material, always_extract_bitmaps,
                single_type, only_single_type)
        base = self.get_path_str(self.reference_base.Path, True)
        lod2 = self.get_path_str(self.reference_lod2.Path, True)
        lod3 = self.get_path_str(self.reference_lod3.Path, True)
        lod4 = self.get_path_str(self.reference_lod4.Path, True)
        texture = self.get_path_str(self.reference_texture.Path, True)
        
        all_obs = []
        single_type_instance_index = None
        
        types = self.get_decorator_types()

        if single_type is not None:
            for t in types:
                if t.decorator_type_name == single_type:
                    single_type_instance_index = t.render_model_instance_index
                    break
                
        if single_type_instance_index is None and only_single_type and types:
            single_type_instance_index = types[0].decorator_type_index
            
        ignore_lods = lod < 1
        continue_getting_lods = True
        
        base_exists = base and Path(base).exists()
        lod2_exists = lod2 and Path(lod2).exists()
        lod3_exists = lod3 and Path(lod3).exists()
        lod4_exists = lod4 and Path(lod4).exists()
        
        if not ignore_lods:
            if lod > 3 and not lod4_exists:
                lod = 3
            if lod > 2 and not lod3_exists:
                lod = 2
            if lod > 1 and not lod2_exists:
                lod = 1
        
        if base_exists and lod < 2:
            base_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_high")
            collection.children.link(base_collection)
            with RenderModelTag(path=base) as base_render:
                base_obs = base_render.to_blend_objects(collection, True, False, base_collection, no_armature=True, specific_io_index=single_type_instance_index)
                for ob in base_obs:
                    ob.nwo.decorator_lod = 'high'
                    utils.unlink(ob)
                    base_collection.objects.link(ob)
                    
                all_obs.extend(base_obs)
                continue_getting_lods = ignore_lods
        
        if lod2_exists and continue_getting_lods and lod < 3:
            lod2_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_medium")
            collection.children.link(lod2_collection)
            with RenderModelTag(path=lod2) as lod2_render:
                lod2_obs = lod2_render.to_blend_objects(collection, True, False, lod2_collection, no_armature=True, specific_io_index=single_type_instance_index)
                for ob in lod2_obs:
                    ob.nwo.decorator_lod = 'medium'
                    utils.unlink(ob)
                    lod2_collection.objects.link(ob)
                    
                all_obs.extend(lod2_obs)
                continue_getting_lods = ignore_lods
        
        if lod3_exists and continue_getting_lods and lod < 4:
            lod3_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_low")
            collection.children.link(lod3_collection)
            with RenderModelTag(path=lod3) as lod3_render:
                lod3_obs = lod3_render.to_blend_objects(collection, True, False, lod3_collection, no_armature=True, specific_io_index=single_type_instance_index)
                for ob in lod3_obs:
                    ob.nwo.decorator_lod = 'low'
                    utils.unlink(ob)
                    lod3_collection.objects.link(ob)
                
                all_obs.extend(lod3_obs)
                continue_getting_lods = ignore_lods
        
        if lod4_exists and continue_getting_lods:
            lod4_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_very_low")
            collection.children.link(lod4_collection)
            with RenderModelTag(path=lod4) as lod4_render:
                lod4_obs = lod4_render.to_blend_objects(collection, True, False, lod4_collection, no_armature=True, specific_io_index=single_type_instance_index)
                for ob in lod4_obs:
                    ob.nwo.decorator_lod = 'very_low'
                    utils.unlink(ob)
                    lod4_collection.objects.link(ob)
                    
                all_obs.extend(lod4_obs)
        
        if texture and Path(texture).exists():
            
            name = Path(texture).with_suffix("").name
            mat = bpy.data.materials.get(name)
            if mat is None:
                mat = bpy.data.materials.new(name)
                if get_material:
                    tree = cast(bpy.types.NodeTree, mat.node_tree)
                    tree.nodes.clear()
                    node_image = tree.nodes.new(type="ShaderNodeTexImage")
                    
                    info = bitmap_to_image(texture, always_extract_bitmaps)
                    
                    if info.image:
                        node_image.image = info.image
                    node_group = tree.nodes.new(type='ShaderNodeGroup')
                    node_group.node_tree = utils.add_node_from_resources("shared_nodes", "Decorator")
                    tree.links.new(input=node_group.inputs[0], output=node_image.outputs[0])
                    tree.links.new(input=node_group.inputs[1], output=node_image.outputs[1])
                    node_output = tree.nodes.new(type='ShaderNodeOutputMaterial')
                    tree.links.new(input=node_output.inputs[0], output=node_group.outputs[0])
                    render_shader = self.value(self.tag.root(), 'render shader')
                    if render_shader in (0, 1, 'wind + dynamic lights', 'still + dynamic lights'):
                        mat.surface_render_method = 'BLENDED'
            
            for ob in all_obs:
                ob.data.materials.clear()
                ob.data.materials.append(mat)
                
        return all_obs
    
    def from_blender(self):
        pass
