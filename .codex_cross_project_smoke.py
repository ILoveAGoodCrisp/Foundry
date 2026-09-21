import sys
from pathlib import Path

sys.path[:0] = [
    r'G:\Halo\Modding\Foundry\blender\addons',
    r'G:\Halo\Modding\Foundry\blender\addons\io_scene_foundry\wheels\networkx-3.4.2-py3-none-any.whl',
    r'C:\Users\tom27\AppData\Roaming\Python\Python314\site-packages',
]

import bpy
import io_scene_foundry

bpy.ops.preferences.addon_enable(module='io_scene_foundry')

from io_scene_foundry import utils
from io_scene_foundry.managed_blam import connected_material
from io_scene_foundry.tags.object_blender import ObjectTag
from io_scene_foundry.tags.physics_blender import PhysicsTag
from io_scene_foundry.tools.importer import NWOImporter

prefs = utils.get_prefs()
prefs.projects.clear()
reach = prefs.projects.add()
reach.name = 'Reach only'
reach.project_name = 'Reach only'
reach.project_path = r'G:\Halo\Modding\Main\HREK'
reach.tags_directory = r'G:\Halo\Modding\Main\HREK\tags'
reach.data_directory = r'G:\Halo\Modding\Main\HREK\data'
reach.game = 'reach'
reach.corinth = False
bpy.context.scene.nwo.scene_project = reach.name

target = Path(r'G:\Halo\Modding\Main\H3ODSTEK\tags\objects\vehicles\odst_pod\odst_pod.vehicle')
utils.switch_project_from_filepath(bpy.context, target)
project = utils.get_project()
print('SOURCE_CONTEXT_OK', project.project_name, project.game, project.tags_directory)

with ObjectTag(path=target) as tag:
    print('VARIANT_READ_OK', len(tag.get_variants()))

physics_path = target.with_suffix('.physics_model')
with PhysicsTag(path=physics_path) as tag:
    root = tag.tag.root()
    nodes = [tag.value(e, 'name') for e in tag.block(root, 'nodes')]
    print('PHYSICS_NODES', len(nodes), nodes)
    bodies = tag.block(root, 'rigid bodies')
    print('PHYSICS_BODIES', len(bodies))
    for index, body in enumerate(bodies):
        reference = tag.required_field(body, 'shape reference').as_struct()
        print('BODY', index, 'node', tag.value(body, 'node'), 'shape_type', tag.value(reference, 'shape type'), 'shape', tag.value(reference, 'shape'))
    for region in tag.block(root, 'regions'):
        for permutation in tag.block(region, 'permutations'):
            indices = [tag.value(entry, 'rigid body') for entry in tag.block(permutation, 'rigid bodies')]
            print('REGION_PERM', tag.value(region, 'name'), tag.value(permutation, 'name'), indices)

connected_material.arrange = lambda _tree: None
ObjectTag.functions_to_blender = lambda _self: []
importer = NWOImporter(bpy.context, [str(target)], ['object'])
importer.tag_render = True
importer.tag_markers = True
importer.tag_collision = True
importer.tag_physics = True
objects, animations = importer.import_object([str(target)], None)
print('CROSS_PROJECT_IMPORT_OK', len(objects), len(animations))
utils.clear_external_project()
