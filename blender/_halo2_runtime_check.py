import sys
import tempfile
import zipfile
from pathlib import Path

import bpy

root = Path(r'G:\Halo\Modding\Foundry')
kit = Path(r'G:\Halo\Modding\Main\H2EK')
dependency_dir = tempfile.mkdtemp(prefix='foundry_blender_check_')
for wheel in (root / 'blender/addons/io_scene_foundry/wheels').glob('*.whl'):
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(dependency_dir)
sys.path[:0] = [dependency_dir, str(root / 'blender/addons')]

bpy.ops.preferences.addon_enable(module='io_scene_foundry')
from io_scene_foundry.tags import connected_material
# Background Blender has a zero UI scale; node placement is unrelated to this check.
connected_material.arrange = lambda tree: None
prefs = bpy.context.preferences.addons['io_scene_foundry'].preferences
project = prefs.projects.add()
project.name = 'H2EK Runtime Check'
project.project_name = 'H2EK'
project.project_path = str(kit)
project.tags_directory = str(kit / 'tags')
project.data_directory = str(kit / 'data')
project.game = 'halo2'
bpy.context.scene.nwo.scene_project = project.name

tag = kit / 'tags/objects/characters/masterchief/masterchief.biped'
result = bpy.ops.nwo.foundry_import(
    filepath=str(tag),
    use_import_info=True,
    tag_render=True,
    tag_markers=True,
    tag_collision=True,
    tag_physics=True,
    tag_animation=False,
    setup_as_asset=True,
    build_blender_materials=False,
    always_extract_bitmaps=False,
)
print('IMPORT_RESULT', result)
armatures = [ob for ob in bpy.data.objects if ob.type == 'ARMATURE']
print('ARMATURES', [(ob.name, len(ob.data.bones), ob.nwo.node_order_source) for ob in armatures])
assert len(armatures) == 1
armature = armatures[0]
assert armature.name == 'masterchief'
assert armature.nwo.node_order_source.endswith('masterchief.render_model')
assert armature.data.bones['l_clavicle'].parent.name == 'spine1'
assert armature.data.bones['l_thigh'].parent.name == 'pelvis'
meshes = [ob for ob in bpy.data.objects if ob.type == 'MESH']
print('MESH_COUNT', len(meshes))
print('MESH_SAMPLES', [(ob.name, len(ob.vertex_groups)) for ob in meshes[:8]])
assert meshes
assert any(group.name == 'l_upperarm' for ob in meshes for group in ob.vertex_groups)
assert all(group.name in armature.data.bones for ob in meshes for group in ob.vertex_groups)
print('HALO2_IMPORT_INFO_CHECK_OK')
