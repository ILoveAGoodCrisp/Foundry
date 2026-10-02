"""Run with Blender --background --factory-startup --python this_file."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import bpy


SOURCE = Path(__file__).resolve().parents[1] / 'addons/io_scene_foundry/tools/shader_reader.py'


def load_function(name, namespace, class_name=None):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    body = tree.body
    if class_name:
        body = next(node for node in body if isinstance(node, ast.ClassDef)
                    and node.name == class_name).body
    function = next(node for node in body if isinstance(node, ast.FunctionDef)
                    and node.name == name)
    function.decorator_list = []
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace[name]


class TestMaterialProperties(bpy.types.PropertyGroup):
    RenderMaterial: bpy.props.BoolProperty(default=True)
    shader_path: bpy.props.StringProperty()


bpy.utils.register_class(TestMaterialProperties)
bpy.types.Material.nwo = bpy.props.PointerProperty(type=TestMaterialProperties)
for material in list(bpy.data.materials):
    bpy.data.materials.remove(material)

with TemporaryDirectory() as directory:
    root = Path(directory)
    shader_path = root / 'test.shader'
    shader_path.touch()
    source = bpy.data.materials.new('Library material')
    source.use_nodes = True
    source.nwo.shader_path = 'test.shader'
    source['foundry_material_conversion_error'] = 'preserve me'
    library_path = root / 'materials.blend'
    bpy.data.libraries.write(str(library_path), {source})
    bpy.data.materials.remove(source)
    with bpy.data.libraries.load(str(library_path), link=True) as (data_from, data_to):
        data_to.materials = data_from.materials
    linked = data_to.materials[0]
    assert linked.library is not None
    original_nodes = [(node.name, node.bl_idname) for node in linked.node_tree.nodes]
    original_links = len(linked.node_tree.links)

    local = bpy.data.materials.new('Local material')
    local.nwo.shader_path = 'test.shader'
    missing = bpy.data.materials.new('Missing tag')
    missing.nwo.shader_path = 'missing.shader'
    calls = []
    reports = []
    utils = SimpleNamespace(
        is_corinth=lambda context: False,
        clear_output=lambda: None,
        get_export_props=lambda: SimpleNamespace(show_output=False),
        relative_path=lambda path: path,
        get_tags_path=lambda: directory,
    )
    namespace = {'bpy': bpy, 'Path': Path, 'utils': utils,
                 'tag_to_nodes': lambda *args: calls.append(args)}
    bulk = load_function('execute', namespace, 'NWO_OT_ShaderToNodesBulk')
    operator = SimpleNamespace(report=lambda level, message: reports.append(message))
    assert bulk(operator, None) == {'FINISHED'}
    assert [call[1] for call in calls] == [local]
    assert reports == ['Built 1 blender materials; skipped 1 linked library materials']

    single = load_function('execute', namespace, 'NWO_ShaderToNodes')
    operator.mat_name = linked.name
    assert single(operator, None) == {'CANCELLED'}
    assert len(calls) == 1

    convert = load_function('tag_to_nodes', namespace)
    assert convert(False, linked, 'test.shader') is None
    assert [(node.name, node.bl_idname) for node in linked.node_tree.nodes] == original_nodes
    assert len(linked.node_tree.links) == original_links
    assert linked['foundry_material_conversion_error'] == 'preserve me'
    assert linked.nwo.shader_path == 'test.shader'

print('PASS: bulk conversion processes local materials and preserves linked library materials; direct conversion is guarded')
