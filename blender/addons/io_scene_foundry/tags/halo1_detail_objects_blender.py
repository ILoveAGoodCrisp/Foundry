"""Static crossed-card previews for Halo 1's camera-facing detail sprites."""
import bpy

from .. import import_transform
from .bitmap import bitmap_to_image
from .halo1_detail_objects import read_detail_object_sprites


def sprite_material(sprite, build_materials, always_extract_bitmaps):
    key = sprite.bitmap.replace('\\', '/').casefold()
    material = next((mat for mat in bpy.data.materials
                     if mat.get('halo1_detail_bitmap') == key
                     and mat.get('halo1_detail_bitmap_index') == sprite.bitmap_index
                     and mat.use_nodes == build_materials), None)
    if material is not None and not always_extract_bitmaps:
        return material
    if material is None:
        material = bpy.data.materials.new(f'{sprite.type_name} detail plate {sprite.bitmap_index}')
    material['halo1_detail_bitmap'] = key
    material['halo1_detail_bitmap_index'] = sprite.bitmap_index
    material.use_nodes = build_materials
    material.use_backface_culling = False
    if not build_materials:
        return material
    info = bitmap_to_image(sprite.bitmap, always_extract_bitmaps, frame_index=sprite.bitmap_index)
    tree = material.node_tree
    tree.nodes.clear()
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = info.image
    texture.extension = 'CLIP'
    texture.location = (-600, 150)
    tint = tree.nodes.new('ShaderNodeAttribute')
    tint.attribute_type = 'INSTANCER'
    tint.attribute_name = 'nwo.decorator_tint'
    tint.location = (-600, -120)
    multiply = tree.nodes.new('ShaderNodeMixRGB')
    multiply.blend_type = 'MULTIPLY'
    multiply.location = (-350, 150)
    # Missing instancer tint (standalone imports) leaves the bitmap unchanged.
    tree.links.new(tint.outputs['Alpha'], multiply.inputs[0])
    tree.links.new(texture.outputs['Color'], multiply.inputs[1])
    tree.links.new(tint.outputs['Color'], multiply.inputs[2])
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.location = (-100, 150)
    tree.links.new(multiply.outputs[0], emission.inputs['Color'])
    transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
    transparent.location = (-100, -80)
    mix = tree.nodes.new('ShaderNodeMixShader')
    mix.location = (120, 150)
    tree.links.new(texture.outputs['Alpha'], mix.inputs[0])
    tree.links.new(transparent.outputs[0], mix.inputs[1])
    tree.links.new(emission.outputs[0], mix.inputs[2])
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    output.location = (350, 150)
    tree.links.new(mix.outputs[0], output.inputs['Surface'])
    material.surface_render_method = 'DITHERED'
    return material


def detail_objects_to_blender(tag, collection, build_materials=False,
                              always_extract_bitmaps=False, single_type=None,
                              only_single_type=False, sprite_index=None):
    if single_type is None and only_single_type:
        types = tag.get_decorator_types()
        single_type = types[0].decorator_type_name if types else None
    sprites = read_detail_object_sprites(tag, single_type, sprite_index)
    materials = {}
    objects = []
    for sprite in sprites:
        name = f'{sprite.type_name}_sprite_{sprite.sprite_index}'
        half = sprite.width / 2
        bottom, top = sprite.z_offset, sprite.z_offset + sprite.height
        positions = ((-half, 0, bottom), (half, 0, bottom), (half, 0, top), (-half, 0, top),
                     (0, -half, bottom), (0, half, bottom), (0, half, top), (0, -half, top))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(value * 100 for value in point) for point in positions], [],
                         ((0, 1, 2, 3), (4, 5, 6, 7)))
        mesh.transform(import_transform.mesh_matrix())
        left, right, top, bottom = sprite.uv_bounds
        uvs = ((left, 1 - bottom), (right, 1 - bottom), (right, 1 - top), (left, 1 - top))
        layer = mesh.uv_layers.new(name='UVMap0')
        for loop in mesh.loops:
            layer.data[loop.index].uv = uvs[loop.vertex_index % 4]
        key = sprite.bitmap, sprite.bitmap_index
        if key not in materials:
            materials[key] = sprite_material(sprite, build_materials, always_extract_bitmaps)
        mesh.materials.append(materials[key])
        ob = bpy.data.objects.new(name, mesh)
        ob.nwo.decorator_lod = 'high'
        ob.nwo.decorator_type_index = sprite.type_index
        ob.nwo.detail_object_sprite_index = sprite.sprite_index
        collection.objects.link(ob)
        objects.append(ob)
    return objects
