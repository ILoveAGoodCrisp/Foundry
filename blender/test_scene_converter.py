"""Blender --background --factory-startup --python-exit-code 1 --python this_file.

Pass -- --toolset PATH to test against an installed io_scene_halo checkout.
"""
import importlib.util
import ast
from math import radians
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import bpy
from mathutils import Matrix

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(wheels.name)
sys.path.insert(0, wheels.name)
from io_scene_foundry import props, utils
from io_scene_foundry.tools.importer import JMSMaterialSlot, NWOImporter, NWO_OT_ConvertScene
from io_scene_foundry.legacy.scene_converter import HaloSceneConverter, CONVERTED
from io_scene_foundry.legacy.jms_importer import JMSImporter
from io_scene_foundry.legacy.jms_format import JMS
from io_scene_foundry.legacy.writers import write_jms
from io_scene_foundry.export.legacy import LegacyExportScene
from io_scene_foundry.export.virtual_geometry import VirtualScene, VirtualMesh
from io_scene_foundry.tools.asset_types import AssetType

# Share the real mesh-export harness without rerunning its Blender registration.
helper_path = Path(__file__).with_name('test_jms_roundtrip.py')
helper_tree = ast.parse(helper_path.read_text(encoding='utf-8'))
helper = next(n for n in helper_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'export_file')
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(helper_path), 'exec'), globals())

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
toolset = Path(args[args.index('--toolset') + 1]) if '--toolset' in args else Path(bpy.utils.user_resource('SCRIPTS')) / 'addons/io_scene_halo'


def load_ui(name):
    path = toolset / 'global_ui' / (name + '.py')
    spec = importlib.util.spec_from_file_location('converter_test_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


material_ui, object_ui, region_ui = (load_ui(name) for name in ('material_ui', 'object_ui', 'region_ui'))
for target, name, cls in (
    (bpy.types.Material, 'ass_jms', material_ui.ASS_JMS_MaterialPropertiesGroup),
    (bpy.types.Light, 'halo_light', material_ui.ASS_LightPropertiesGroup),
    (bpy.types.Object, 'ass_jms', object_ui.ASS_JMS_ObjectPropertiesGroup),
    (bpy.types.Mesh, 'ass_jms', object_ui.ASS_JMS_MeshPropertiesGroup),
):
    bpy.utils.register_class(cls)
    setattr(target, name, bpy.props.PointerProperty(type=cls))
bpy.types.Bone.ass_jms = bpy.props.PointerProperty(type=object_ui.ASS_JMS_ObjectPropertiesGroup)
bpy.utils.register_class(region_ui.RegionItem)
bpy.types.Mesh.region_list = bpy.props.CollectionProperty(type=region_ui.RegionItem)
bpy.types.Mesh.active_region = bpy.props.IntProperty(default=-1)
bpy.types.Scene.active_region_list = []

project = SimpleNamespace(game='halo3', corinth=False)
utils.get_project = lambda *a, **k: project
utils.current_project_valid = lambda: True
props.register()
bpy.utils.register_class(NWO_OT_ConvertScene)


def owner(game):
    project.game = game
    value = NWOImporter.__new__(NWOImporter)
    value.game = value.target_game = game
    value.context = bpy.context
    value.scene_nwo = bpy.context.scene.nwo
    value.region_names, value.permutation_names = set(), set()
    value.scale_factor = .03048
    value.from_x_rot = 0
    value.corinth = False
    return value


def face_props(mesh, kind):
    collection = mesh.nwo.material_props if isinstance(mesh, bpy.types.Material) else mesh.nwo.face_props
    return [p for p in collection if p.type == kind]


class SceneConverterTests(unittest.TestCase):
    def setUp(self):
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        for collection in list(bpy.data.collections):
            bpy.data.collections.remove(collection)
        bpy.context.scene.nwo.asset_type = 'model'
        self.owner = owner('halo3')

    def material(self, name='surface'):
        return bpy.data.materials.new(name)

    def mesh(self, name='mesh', materials=()):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [],
                         [(0, 1, 2), (0, 3, 1)])
        for mat in materials:
            mesh.materials.append(mat)
        if len(materials) > 1:
            mesh.polygons[1].material_index = 1
        uv = mesh.uv_layers.new()
        uv.data.foreach_set('uv', [.1, .2] * len(mesh.loops))
        ob = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    def test_game_specific_materials_and_units(self):
        mat = self.material()
        mat.ass_jms.lightmap_res = 2.5
        mat.ass_jms.lightmap_resolution_scale = .75
        mat.ass_jms.lightmap_power_scale = 4
        mat.ass_jms.two_sided_transparent_tint = (.2, .4, .6)
        mat.ass_jms.additive_transparency = (.7, .1, .3)
        mat.ass_jms.power = 12
        mat.ass_jms.attenuation_enabled = True
        mat.ass_jms.falloff_distance = 100
        mat.ass_jms.cutoff_distance = 200
        mat.ass_jms.ignore_default_res_scale = True
        for game in ('halo1', 'halo2', 'halo3', 'halo3odst'):
            with self.subTest(game=game):
                importer = owner(game)
                ob = self.mesh(materials=[mat])
                HaloSceneConverter(importer, False).convert([ob])
                lightmaps = face_props(ob.data, 'lightmap_resolution_scale')
                emissive = face_props(ob.data, 'emissive')
                if game == 'halo1':
                    self.assertFalse(lightmaps)
                    self.assertFalse(emissive)
                    self.assertEqual(face_props(ob.data.materials[0], 'emissive')[0].material_lighting_emissive_power, 12)
                else:
                    self.assertAlmostEqual(lightmaps[0].lightmap_resolution_scale_legacy, .75 if game == 'halo2' else 2.5)
                    if game == 'halo2':
                        self.assertEqual(emissive[0].material_lighting_emissive_power_scale, 4)
                        self.assertEqual(face_props(ob.data.materials[0], 'emissive')[0].material_lighting_emissive_power, 12)
                        self.assertFalse(face_props(ob.data, 'lightmap_translucency_tint_color'))
                    else:
                        self.assertAlmostEqual(emissive[0].material_lighting_attenuation_falloff, 3.048, places=5)
                        self.assertAlmostEqual(emissive[0].material_lighting_attenuation_cutoff, 6.096, places=5)
                        tint = face_props(ob.data, 'lightmap_translucency_tint_color')[0].lightmap_translucency_tint_color
                        self.assertAlmostEqual(tint[1], .4)
                        self.assertTrue(face_props(ob.data, 'lightmap_ignore_default_resolution_scale'))

    def test_mixed_materials_preserve_masks_and_shared_mesh(self):
        a, b = self.material('a'), self.material('b')
        a.ass_jms.two_sided = True
        b.ass_jms.render_only = True
        ob = self.mesh(materials=[a, b])
        other = ob.copy()
        bpy.context.scene.collection.objects.link(other)
        original = other.data
        converter = HaloSceneConverter(self.owner, False)
        converter.convert([ob])
        self.assertIsNot(ob.data, original)
        self.assertEqual(len(original.nwo.face_props), 0)
        prop = face_props(ob.data, 'face_sides')[0]
        self.assertEqual([v.value for v in ob.data.attributes[prop.attribute_name].data], [True, False])
        self.assertEqual(converter.convert([ob]), 0)

    def test_split_portals_and_regions_keep_transforms_uvs_and_weights(self):
        a, b = self.material('+portal'), self.material('+portal')
        a.ass_jms.portal_1_way = True
        b.ass_jms.portal_vis_blocker = True
        ob = self.mesh(materials=[a, b])
        ob.matrix_world = Matrix.Translation((3, 4, 5))
        ob.vertex_groups.new(name='bone').add([0, 1, 2, 3], 1, 'REPLACE')
        converter = HaloSceneConverter(self.owner, False)
        self.assertEqual(converter.convert([ob]), 2)
        result = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        self.assertEqual({o.nwo.portal_type for o in result}, {'_connected_geometry_portal_type_one_way', '_connected_geometry_portal_type_no_way'})
        for o in result:
            self.assertEqual(len(o.data.polygons), 1)
            self.assertEqual(tuple(o.matrix_world.translation), (3, 4, 5))
            self.assertAlmostEqual(o.data.uv_layers[0].data[0].uv.x, .1)
            self.assertTrue(o.data.vertices[0].groups)

    def test_face_regions_include_permutation_and_lod(self):
        ob = self.mesh()
        for name in ('L2 damaged hull', 'L5 default wing'):
            ob.data.region_list.add().name = name
        attribute = ob.data.attributes.new('Region Assignment', 'INT', 'FACE')
        attribute.data.foreach_set('value', [1, 2])
        HaloSceneConverter(owner('halo2'), True).convert([ob])
        self.assertEqual({(o.nwo.region_name, o.nwo.permutation_name, o.nwo.mesh_lod) for o in bpy.context.scene.objects},
                         {('hull', 'damaged', 'L2'), ('wing', 'default', 'L5')})

    def test_exact_portal_and_mesh_marker_parenting(self):
        mat = self.material('exact')
        mat.ass_jms.portal_exact = True
        portal = self.mesh(materials=[mat])
        marker = self.mesh('#socket')
        marker.ass_jms.marker_region = 'hull'
        marker.ass_jms.name_override = 'attachment'
        child = bpy.data.objects.new('child', None)
        bpy.context.scene.collection.objects.link(child)
        child.parent = marker
        child.matrix_world = Matrix.Translation((2, 3, 4))
        HaloSceneConverter(owner('halo1'), True).convert([portal, marker])
        self.assertEqual(portal.data.nwo.mesh_type, '_connected_geometry_mesh_type_portal')
        self.assertTrue(portal.data.materials[0].name.startswith('+exactportal'))
        self.assertEqual(child.parent.type, 'EMPTY')
        self.assertEqual(child.parent.name, 'attachment')
        self.assertEqual(child.parent.nwo.region_name, 'hull')
        self.assertEqual(tuple(child.matrix_world.translation), (2, 3, 4))
        self.assertEqual(mat.name, 'exact')

    def test_physics_and_lights(self):
        ob = self.mesh('$body', [self.material('steel')])
        ob.data.ass_jms.Object_Type = 'CAPSULES'
        data = bpy.data.lights.new('spot', 'SPOT')
        light = bpy.data.objects.new('spot', data)
        bpy.context.scene.collection.objects.link(light)
        data.halo_light.light_cone_shape = '0'
        data.halo_light.aspect_ratio = 2
        data.halo_light.spot_size = radians(45)
        data.halo_light.use_far_atten = True
        data.halo_light.far_atten_start = 100
        data.halo_light.far_atten_end = 200
        HaloSceneConverter(self.owner, True).convert([ob, light])
        self.assertEqual(ob.nwo.mesh_primitive_type, '_connected_geometry_primitive_type_pill')
        self.assertEqual(face_props(ob.data, 'global_material')[0].global_material, 'steel')
        self.assertEqual(data.nwo.light_shape, '_connected_geometry_light_shape_rectangle')
        self.assertEqual(data.nwo.light_aspect, 2)
        self.assertAlmostEqual(data.nwo.light_far_attenuation_end, 6.096, places=5)

    def test_halo2_ass_resolution_fallback_and_name_flags(self):
        mat = self.material('wall! lm:0.5 lp:2')
        prop = JMSMaterialSlot.from_material(mat, 'halo2')
        self.assertTrue(prop.render_only)
        self.assertEqual(prop.lightmap_resolution_scale_legacy, .5)
        self.assertEqual(prop.emissive_power_scale, 2)
        mat.ass_jms.lightmap_res = 3.5
        self.assertEqual(JMSMaterialSlot.from_material(mat, 'halo2').lightmap_resolution_scale_legacy, 3.5)

    def test_operator_selected_scope_and_scene_scope(self):
        ob = self.mesh(materials=[self.material()])
        other = ob.copy()
        bpy.context.scene.collection.objects.link(other)
        outside_scene = bpy.data.objects.new('outside', ob.data)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        with patch('io_scene_foundry.tools.importer.NWOImporter', return_value=self.owner):
            self.assertEqual(bpy.ops.nwo.convert_scene(selected_only=True, jms_type='scenario'), {'FINISHED'})
            self.assertTrue(ob.get(CONVERTED))
            self.assertFalse(other.get(CONVERTED))
            self.assertEqual(bpy.ops.nwo.convert_scene(selected_only=False, jms_type='scenario'), {'FINISHED'})
            self.assertTrue(other.get(CONVERTED))
            self.assertFalse(outside_scene.get(CONVERTED))

    def test_constraint_and_instance_collision_proxy(self):
        instance = self.mesh('%+instance')
        collision = self.mesh('@collision')
        collision.parent = instance
        constraint = bpy.data.objects.new('$hinge', None)
        bpy.context.scene.collection.objects.link(constraint)
        bpy.context.view_layer.objects.active = constraint
        constraint.select_set(True)
        if bpy.context.scene.rigidbody_world is None:
            bpy.ops.rigidbody.world_add()
        bpy.ops.rigidbody.constraint_add()
        constraint.rigid_body_constraint.type = 'HINGE'
        constraint.rigid_body_constraint.object1 = instance
        constraint.rigid_body_constraint.object2 = collision
        constraint.rigid_body_constraint.use_limit_ang_z = True
        constraint.rigid_body_constraint.limit_ang_z_lower = -.3
        constraint.rigid_body_constraint.limit_ang_z_upper = .7
        HaloSceneConverter(self.owner, False).convert([collision, instance, constraint])
        self.assertEqual(instance.data.nwo.proxy_collision, collision)
        self.assertFalse(collision.nwo.export_this)
        self.assertEqual(instance.nwo.poop_pathfinding, 'static')
        self.assertEqual(constraint.nwo.physics_constraint_parent, instance)
        self.assertAlmostEqual(constraint.nwo.hinge_constraint_maximum, .7)
        constraint.rigid_body_constraint.type = 'MOTOR'
        converter = HaloSceneConverter(self.owner, False)
        converter.constraint(constraint)
        self.assertFalse(constraint.nwo.export_this)
        self.assertTrue(converter.warnings)

    def test_unsupported_fields_warn_and_remain_on_material(self):
        mat = self.material()
        mat.ass_jms.conveyor = True
        ob = self.mesh(materials=[mat])
        converter = HaloSceneConverter(self.owner, False)
        converter.convert([ob])
        self.assertTrue(any('conveyor' in warning for warning in converter.warnings))
        self.assertTrue(ob.data.materials[0].ass_jms.conveyor)

    def collection(self, name, objects, parent=None):
        collection = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(collection)
        for ob in objects:
            for previous in tuple(ob.users_collection):
                previous.objects.unlink(ob)
            collection.objects.link(ob)
        return collection

    def test_halo1_scene_conversion_round_trip_matches_jms_properties(self):
        self.owner = owner('halo1')
        bpy.context.scene.nwo.asset_type = 'scenario'
        exact, portal_mat = self.material('+exactportal&'), self.material('+portal')
        portals = self.mesh('portals', [exact, portal_mat])
        # Occupy the clean name to exercise private material copies with .001 suffixes.
        self.material('+ladder stair')
        ladder_a, ladder_b = self.material('+ladder stair%*^'), self.material('+ladder stair%*')
        ladder = self.mesh('ladder', [ladder_a, ladder_b])
        sky = self.mesh('sky', [self.material('+sky@')])
        collision = self.mesh('@blocker', [self.material('collision_shader')])
        render = self.mesh('render', [self.material('render_shader!')])
        marker = self.mesh('#socket')
        frame = bpy.data.objects.new('frame_root', None)
        light = bpy.data.objects.new('light', bpy.data.lights.new('light', 'POINT'))
        for ob in (frame, light):
            bpy.context.scene.collection.objects.link(ob)
        source = self.collection('a10e.jms', [portals, ladder, sky, collision, render, marker, frame, light])
        converter = HaloSceneConverter(self.owner, False)
        converter.convert(list(source.all_objects))
        self.assertEqual(source.nwo.type, 'region')
        self.assertEqual(source.nwo.region, 'a10e')
        converted = list(source.all_objects)
        self.assertTrue(all(ob.nwo.region_name == 'a10e' for ob in converted))
        portal_objects = [ob for ob in converted if ob.type == 'MESH' and ob.data.nwo.mesh_type.endswith('_portal')]
        self.assertEqual(sorted(ob.nwo.portal_exact for ob in portal_objects), [False, True])
        self.assertTrue(next(ob for ob in portal_objects if ob.nwo.portal_exact).nwo.portal_ai_deafening)
        self.assertEqual(face_props(ladder.data, 'face_mode')[0].face_mode, 'sphere_collision_only')
        self.assertEqual(face_props(ladder.data, 'face_mode')[0].face_count, 2)
        self.assertEqual(face_props(ladder.data, 'ladder')[0].face_count, 1)
        self.assertEqual(face_props(sky.data, 'face_mode')[0].face_mode, 'collision_only')
        self.assertEqual(face_props(collision.data, 'face_mode')[0].face_mode, 'collision_only')
        self.assertEqual(ladder_a.name, '+ladder stair%*^')
        with tempfile.TemporaryDirectory() as directory:
            first = export_file(converted, Path(directory, 'first.jms'))
            imported = JMSImporter(self.owner, Path(directory, 'first.jms'), 'bsp')
            imported.build()
            # The converter operates in place; import distances here use the same scene units.
            second = export_file(imported.objects, Path(directory, 'second.jms'), self.owner.scale_factor)
            from collections import Counter
            def names(asset):
                return Counter(asset.materials[t.material].name for t in asset.triangles)
            self.assertEqual(names(first), names(second))
            self.assertEqual(names(first)['+ladder stair*^'], 1)
            self.assertEqual(names(first)['+ladder stair*'], 1)
            self.assertEqual(names(first)['+exactportal&'], 1)
            self.assertEqual(names(first)['+portal'], 1)
            self.assertEqual(names(first)['+sky@'], 2)
            self.assertEqual(names(first)['collision_shader@'], 2)
            self.assertEqual(names(first)['render_shader!'], 2)

    def test_selected_only_keeps_shared_collection_and_materials_unchanged(self):
        self.owner = owner('halo1')
        bpy.context.scene.nwo.asset_type = 'scenario'
        mat = self.material('+ladder stair%*^')
        ob = self.mesh('selected', [mat])
        other = ob.copy()
        bpy.context.scene.collection.objects.link(other)
        source = self.collection('selected_bsp', [ob, other])
        other.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        original_mesh = other.data
        with patch('io_scene_foundry.tools.importer.NWOImporter', return_value=self.owner):
            self.assertEqual(bpy.ops.nwo.convert_scene(selected_only=True), {'FINISHED'})
        self.assertEqual(source.nwo.type, 'none')
        self.assertFalse(other.get(CONVERTED))
        self.assertIs(other.data, original_mesh)
        self.assertIs(other.data.materials[0], mat)
        destination = next(c for c in ob.users_collection if c.nwo.type == 'region')
        self.assertEqual(destination.nwo.region, 'selected_bsp')
        self.assertNotIn(other.name, destination.all_objects)
        # Converting the remainder reuses the same BSP identity and collection.
        HaloSceneConverter(self.owner, False).convert([other])
        self.assertIn(other.name, destination.all_objects)
        self.assertEqual(HaloSceneConverter(self.owner, False).convert([ob, other]), 0)

    def test_existing_bsp_assignments_and_child_categories_survive(self):
        self.owner = owner('halo1')
        bpy.context.scene.nwo.asset_type = 'scenario'
        a, b = self.mesh('part_a'), self.mesh('part_b')
        bsp_a = self.collection('a10e', [])
        bsp_b = self.collection('a10f', [b])
        for collection in (bsp_a, bsp_b):
            collection.nwo.type = 'region'
            collection.nwo.region = collection.name
        child = self.collection('render', [a], parent=bsp_a)
        child.nwo.type = 'permutation'
        child.nwo.permutation = 'render'
        HaloSceneConverter(self.owner, False).convert([a, b])
        self.assertEqual(a.nwo.region_name, 'a10e')
        self.assertEqual(b.nwo.region_name, 'a10f')
        self.assertIn(child, a.users_collection)
        self.assertEqual(child.nwo.type, 'permutation')

    def test_operator_auto_and_explicit_bsp_name(self):
        self.owner = owner('halo1')
        bpy.context.scene.nwo.asset_type = 'scenario'
        ob = self.mesh(materials=[self.material('+exactportal')])
        self.collection('unrelated_source_name', [ob])
        with patch('io_scene_foundry.tools.importer.NWOImporter', return_value=self.owner):
            self.assertEqual(bpy.ops.nwo.convert_scene(bsp_name='a10e.ass'), {'FINISHED'})
        self.assertEqual(ob.nwo.region_name, 'a10e')
        self.assertTrue(ob.nwo.portal_exact)
        self.assertTrue(any(c.nwo.type == 'region' and c.nwo.region == 'a10e' for c in ob.users_collection))

    def test_operator_registered(self):
        self.assertEqual(bpy.ops.nwo.convert_scene.get_rna_type().identifier, 'NWO_OT_convert_scene')


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Scene converter regression tests failed')
