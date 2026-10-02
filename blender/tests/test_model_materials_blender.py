"""Run with Blender --background --factory-startup --python this_file."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace

import bpy


ADDON = Path(__file__).resolve().parents[1] / 'addons' / 'io_scene_foundry'


def load_function(path, name, namespace, class_name=None):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    body = tree.body
    if class_name:
        body = next(node for node in body if isinstance(node, ast.ClassDef)
                    and node.name == class_name).body
    function = next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class TestMaterialProperties(bpy.types.PropertyGroup):
    shader_path: bpy.props.StringProperty()


bpy.utils.register_class(TestMaterialProperties)
bpy.types.Material.nwo = bpy.props.PointerProperty(type=TestMaterialProperties)
for material in list(bpy.data.materials):
    bpy.data.materials.remove(material)

namespace = {'bpy': bpy}
get_material = load_function(ADDON / 'legacy' / 'jms_importer.py', 'material', namespace, 'JMSImporter')
owner = SimpleNamespace(created_materials=[])
wheel_path = r'objects\vehicles\warthog\shaders\blur.shader'
barrel_path = r'objects\vehicles\warthog\turrets\chaingun\shaders\blur.shader'
wheel = get_material(owner, 'blur', wheel_path)
barrel = get_material(owner, 'blur', barrel_path)
assert wheel != barrel
assert get_material(owner, 'blur', wheel_path) == wheel
assert wheel.nwo.shader_path == wheel_path
assert barrel.nwo.shader_path == barrel_path

duplicate = wheel.copy()
mesh = bpy.data.meshes.new('material_identity_test')
mesh.materials.append(wheel)
mesh.materials.append(barrel)
mesh.materials.append(duplicate)
obj = bpy.data.objects.new('material_identity_test', mesh)
bpy.context.scene.collection.objects.link(obj)
namespace['base_material_name'] = lambda name, strip: re.sub(r'\.\d{3}$', '', name)
deduplicate = load_function(ADDON / 'tools' / 'clear_duplicate_materials.py',
                           'clear_duplicate_materials', namespace)
result = deduplicate(True, [wheel, barrel, duplicate])
assert len(result) == 2
assert mesh.materials[0] == mesh.materials[2] == wheel
assert mesh.materials[1] == barrel
assert barrel.nwo.shader_path == barrel_path
assert len(deduplicate(True, [wheel, barrel])) == 2
print('PASS: source shader paths remain distinct; matching duplicates merge; repeated cleanup preserves both shaders')
