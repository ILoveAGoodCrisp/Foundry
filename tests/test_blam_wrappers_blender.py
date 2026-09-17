"""Exercise the real addon imports and migrated wrappers without starting .NET."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import sys

ADDONS = Path(__file__).resolve().parents[1] / 'blender/addons'
sys.path.insert(0, str(ADDONS))
from io_scene_foundry import utils, managed_blam
from io_scene_foundry.managed_blam.model import ModelTag
from io_scene_foundry.managed_blam.object import ObjectTag
from io_scene_foundry.managed_blam.cinematic_lighting import CinematicLightingTag
from io_scene_foundry.managed_blam.globals import GlobalsTag
from io_scene_foundry.managed_blam.render_method_option import RenderMethodOptionTag
from io_scene_foundry.managed_blam.render_method_definition import RenderMethodDefinitionTag
from io_scene_foundry.managed_blam.material_shader import MaterialShaderTag


class WrapperTests(unittest.TestCase):
    def test_unconnected_native_curves_resolve_constant_light_values(self):
        import struct
        from blam_tags import TagFunctionEditor
        from io_scene_foundry.managed_blam.connected_material import Function, OutputModifierType
        from io_scene_foundry.managed_blam.light_functions import constant_light_value
        from test_blam_functions import function_blob
        # A nonlinear exponent curve whose endpoint differs from both clamp bounds.
        blob = function_blob(9, (struct.pack('<fff', 2., 6., 2.),))
        function = Function()
        function.native_function_type = 9
        function.editor = TagFunctionEditor(blob)
        function.clamp_min, function.clamp_max = .25, .75
        self.assertAlmostEqual(constant_light_value(function), 3.25)
        function.uses_input = True
        self.assertIsNone(constant_light_value(function))
        function.uses_input = False
        function.is_ranged, function.range = True, 'radius_range'
        self.assertIsNone(constant_light_value(function))
        function.range = ''
        self.assertAlmostEqual(constant_light_value(function), 3.25)
        function.output_modifier_type = OutputModifierType.TIMES
        self.assertIsNone(constant_light_value(function))
        function.output_modifier_type = OutputModifierType.NONE
        function.native_function_type = 3  # Periodic/noise must not be frozen.
        self.assertIsNone(constant_light_value(function))

    def test_normalized_light_additive_modifier_keeps_units(self):
        import bpy
        from io_scene_foundry.managed_blam import connected_material as material
        function = material.Function()
        function.clamp_min, function.clamp_max = 2., 8.
        function.output_modifier_type = material.OutputModifierType.PLUS
        function.output_modifier = 'boost'
        tree = bpy.data.node_groups.new('native_light_modifier_test', 'ShaderNodeTree')
        def attribute(tree, name):
            node = tree.nodes.new('ShaderNodeValue')
            node.outputs[0].default_value = 3.
            return node
        def evaluate(socket):
            node = socket.node
            if node.bl_idname == 'ShaderNodeValue':
                return socket.default_value
            values = [evaluate(i.links[0].from_socket) if i.is_linked else i.default_value for i in node.inputs[:2]]
            if node.operation == 'ADD':
                return sum(values)
            if node.operation == 'DIVIDE':
                return values[0] / values[1]
            self.fail(f'Unexpected operation: {node.operation}')
        try:
            with patch.object(material, 'add_attribute_node', side_effect=attribute):
                output = function.to_blend_nodes(tree=tree, normalize=True)
            self.assertAlmostEqual(evaluate(output) * 8., 5.)  # 2 intensity + 3 boost.
        finally:
            bpy.data.node_groups.remove(tree)

    def test_native_light_conversion(self):
        import struct
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam import cheap_light, light
        from io_scene_foundry.managed_blam.connected_material import Function, OutputModifierType

        def mapping(tag, name, value, color=False):
            element = tag.required_field(tag.tag.root(), name).as_struct()
            data = bytearray(32)
            data[0] = 1
            if color:
                data[2] = 1
                struct.pack_into('<I', data, 4, 0xff804020)
            else:
                struct.pack_into('<ff', data, 4, value, value)
            function = tag.required_field(element, 'Mapping').as_struct()
            tag.required_field(function, 'data').set(bytes(data))
            if name == 'intensity':
                tag.required_field(element, 'Input Variable').set('power')
                tag.required_field(element, 'Range Variable').set('pulse')
                tag.required_field(element, 'Output Modifier Input').set('boost')
                tag.required_field(element, 'Output Modifier').set(2)
                parsed = Function()
                parsed.from_native_light(tag, element)
                self.assertEqual(parsed.output_modifier_type, OutputModifierType.TIMES)
                self.assertTrue(parsed.uses_input)
                self.assertEqual(parsed.range, 'pulse')

        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            for module, cls in ((cheap_light, cheap_light.CheapLightTag), (light, light.LightTag)):
                if game in {'halo3', 'halo3odst'}:
                    continue  # No cheap_light group; regular light falloff is not supported yet.
                if cls is light.LightTag and game in {'halo4', 'halo2a'}:
                    continue  # Covered by the separate Midnight parameter-layout test.
                with self.subTest(game=game, kind=cls.tag_ext), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=root), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                    path = 'lamp.' + cls.tag_ext
                    unsupported = cls is light.LightTag and game in {'halo4', 'halo2a'}
                    with cls(path) as tag:
                        if not unsupported:
                            mapping(tag, 'color', 0, True)
                            mapping(tag, 'intensity', 4.)
                            if cls is cheap_light.CheapLightTag:
                                mapping(tag, 'Falloff End' if tag.corinth else 'radius', 8.)
                            else:
                                for name, value in [('type', 1), ('frustum field of view', 60.),
                                                    ('angular hotspot', 30.), ('attenuation start distance', 2.),
                                                    ('attenuation end distance', 8.)]:
                                    tag.required_field(tag.tag.root(), name).set(value)
                    before = (Path(root) / path).read_bytes()
                    data = SimpleNamespace(nwo=SimpleNamespace())
                    factory = MagicMock(return_value=data)
                    fake_bpy = SimpleNamespace(data=SimpleNamespace(lights=SimpleNamespace(new=factory)))
                    attachment = SimpleNamespace(function_names=set())
                    with cls(path) as tag, patch.object(module, 'bpy', fake_bpy), \
                         patch.object(module.import_transform, 'scale_factor', return_value=1.), \
                         patch.object(module.import_transform, 'distance', side_effect=lambda x: x * 100), \
                         patch.object(utils, 'make_halo_light') as make:
                        result = tag.to_blender('primary', 'secondary', attachment)
                        if unsupported:
                            self.assertIsNone(result)
                            factory.assert_not_called()
                        else:
                            self.assertIs(result, data)
                            self.assertEqual(data.nwo.light_intensity, 4.)
                            self.assertEqual(data.nwo.light_far_attenuation_end, 800.)
                            self.assertEqual(data.color, [utils.srgb_to_linear(c / 255) for c in (128, 64, 32)])
                            self.assertEqual(attachment.function_names, {'power', 'boost'})
                            make.assert_called_once()
                            if cls is light.LightTag:
                                self.assertAlmostEqual(data.spot_size, 1.0471975512)
                                self.assertEqual(data.spot_blend, .5)
                                self.assertEqual(data.nwo.light_far_attenuation_start, 200.)
                    self.assertEqual(before, (Path(root) / path).read_bytes())

    def test_native_midnight_lights(self):
        import struct
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam import light
        for game in ('halo4', 'halo2a'):
            for kind in (0, 1, 2, 3, 4):
                for mode in (0, 1):
                    with self.subTest(game=game, kind=kind, mode=mode), tempfile.TemporaryDirectory() as root, \
                         patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                         patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                         patch.object(utils, 'get_tags_path', return_value=root), \
                         patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                        with light.LightTag('lamp.light') as tag:
                            parameters = tag.required_field(tag.tag.root(), 'Midnight_Light_Parameters').as_struct()
                            for name, value in [('Light Type', kind), ('Lighting Mode', mode),
                                                ('Inner Cone Angle', 30.), ('Distance Attenuation Start', 2.),
                                                ('Shadows', 1), ('Cinema Only', 1), ('Specular Contribution', 1)]:
                                tag.required_field(parameters, name).set(value)
                            color = tag.required_field(parameters, 'Light Color')
                            color.set(type(color.value)(.5, .25, .125))
                            for name, number in [('Intensity', 4.), ('Distance Attenuation End', 8.), ('Outer Cone End', 60.)]:
                                element = tag.required_field(parameters, name).as_struct()
                                mapping = tag.required_field(element, 'Mapping').as_struct()
                                blob = bytearray(32)
                                blob[0] = 1
                                struct.pack_into('<ff', blob, 4, number, number)
                                if name == 'Distance Attenuation End':
                                    blob[0] = 0  # Unconnected identity resolves at input=1, not clamp_min.
                                    struct.pack_into('<ff', blob, 4, 2., number)
                                tag.required_field(mapping, 'data').set(bytes(blob))
                        before = (Path(root) / 'lamp.light').read_bytes()
                        data = SimpleNamespace(nwo=SimpleNamespace())
                        factory = MagicMock(return_value=data)
                        fake_bpy = SimpleNamespace(context=object(), data=SimpleNamespace(lights=SimpleNamespace(new=factory)))
                        with light.LightTag('lamp.light') as tag, patch.object(light, 'bpy', fake_bpy), \
                             patch.object(light.import_transform, 'distance', side_effect=lambda x: x * 100), \
                             patch.object(utils, 'get_import_scale', return_value=10.), \
                             patch.object(utils, 'make_halo_light') as make:
                            if kind == 3:
                                with self.assertRaisesRegex(NotImplementedError, 'Area'):
                                    tag.to_blender()
                                factory.assert_not_called()
                                continue
                            self.assertIs(tag.to_blender(), data)
                            self.assertEqual(factory.call_args.kwargs['type'], ('POINT', 'SPOT', 'SUN', 'AREA', 'SUN')[kind])
                            self.assertEqual(data.nwo.light_intensity, 4.)
                            self.assertEqual(data.nwo.light_far_attenuation_start, 200.)
                            self.assertEqual(data.nwo.light_far_attenuation_end, 800.)
                            self.assertEqual(data.color, [utils.srgb_to_linear(c) for c in (.5, .25, .125)])
                            self.assertTrue(data.nwo.light_shadows)
                            self.assertEqual(data.nwo.light_cinema, '_connected_geometry_lighting_cinema_only')
                            if kind == 1:
                                self.assertAlmostEqual(data.spot_size, 1.0471975512)
                                self.assertEqual(data.spot_blend, .5)
                            if kind in {2, 4}:
                                self.assertEqual(data.energy, 4.)
                                make.assert_not_called()
                            elif mode == 0:
                                self.assertEqual(data.energy, 400.)
                                make.assert_not_called()
                            else:
                                make.assert_called_once()
                        self.assertEqual(before, (Path(root) / 'lamp.light').read_bytes())

    def test_animated_midnight_intensity(self):
        import struct
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam import light
        from io_scene_foundry.managed_blam.connected_material import Function
        for game in ('halo4', 'halo2a'):
            for mode, animated_radius in ((1, False), (0, False), (1, True)):
                with self.subTest(game=game, mode=mode, radius=animated_radius), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=root), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                    with light.LightTag('lamp.light') as tag:
                        p = tag.required_field(tag.tag.root(), 'Midnight_Light_Parameters').as_struct()
                        tag.required_field(p, 'Lighting Mode').set(mode)
                        for name in ('Intensity', 'Distance Attenuation End'):
                            element = tag.required_field(p, name).as_struct()
                            mapping = tag.required_field(element, 'Mapping').as_struct()
                            blob = bytearray(32)  # Identity curve; no editor trailer.
                            limits = (2., 8.) if name == 'Intensity' or animated_radius else (8., 8.)
                            struct.pack_into('<ff', blob, 4, *limits)
                            if name == 'Distance Attenuation End' and animated_radius:
                                tag.required_field(element, 'Input Variable').set('radius_control')
                            if name == 'Intensity':
                                blob[1] = 1  # Ranged.
                                tag.required_field(element, 'Input Variable').set('power')
                                tag.required_field(element, 'Range Variable').set('pulse')
                                tag.required_field(element, 'Output Modifier Input').set('boost')
                                tag.required_field(element, 'Output Modifier').set(2)
                            tag.required_field(mapping, 'data').set(bytes(blob))
                    before = (Path(root) / 'lamp.light').read_bytes()
                    data = SimpleNamespace(nwo=SimpleNamespace())
                    factory = MagicMock(return_value=data)
                    fake = SimpleNamespace(data=SimpleNamespace(lights=SimpleNamespace(new=factory)))
                    attachment = SimpleNamespace(function_names=set())
                    strength = object()
                    with light.LightTag('lamp.light') as tag, patch.object(light, 'bpy', fake), \
                         patch.object(light.import_transform, 'distance', side_effect=lambda x: x * 100), \
                         patch.object(Function, 'to_blend_nodes', return_value=strength) as nodes, \
                         patch.object(utils, 'make_halo_light') as make:
                        if mode == 0 or animated_radius:
                            with self.assertRaises(NotImplementedError):
                                tag.to_blender(attachment=attachment)
                            factory.assert_not_called()
                            nodes.assert_not_called()
                        else:
                            self.assertIs(tag.to_blender('primary', 'secondary', attachment), data)
                            self.assertEqual(data.nwo.light_intensity, 8.)
                            self.assertEqual(data.nwo.light_far_attenuation_end, 800.)
                            self.assertEqual(attachment.function_names, {'power', 'pulse', 'boost'})
                            nodes.assert_called_once_with(name='lamp_strength', normalize=True)
                            self.assertIs(make.call_args.kwargs['strength_node_tree'], strength)
                    self.assertEqual(before, (Path(root) / 'lamp.light').read_bytes())

    def test_bad_light_mapping_falls_back_before_creating_lights(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam import cheap_light
        factory = MagicMock()
        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
             patch.object(utils, 'get_tags_path', return_value=root):
            with cheap_light.CheapLightTag('bad.cheap_light') as tag:
                color = tag.required_field(tag.tag.root(), 'color').as_struct()
                mapping = tag.required_field(color, 'Mapping').as_struct()
                tag.required_field(mapping, 'data').set(b'bad')
            with cheap_light.CheapLightTag('bad.cheap_light') as tag, \
                 patch.object(cheap_light, 'bpy', SimpleNamespace(data=SimpleNamespace(lights=SimpleNamespace(new=factory)))), \
                 patch.object(managed_blam, 'Tag', side_effect=ValueError('legacy unavailable')):
                with self.assertRaisesRegex(ValueError, 'legacy unavailable'):
                    tag.to_blender()
                factory.assert_not_called()

    def test_native_object_functions_create_blender_nodes(self):
        import bpy
        import struct
        from io_scene_foundry.managed_blam.connected_material import Function
        name = 'foundry_native_function_test'
        group_name = 'function -> ' + name
        try:
            with tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                blob = bytearray(32)
                blob[0] = 1  # Scalar constant.
                struct.pack_into('<ff', blob, 4, 0.375, 1.)
                with ObjectTag('test.scenery') as obj:
                    functions = obj.block(obj.object_struct(), 'functions')
                    element = functions[functions.add()]
                    obj.required_field(element, 'export name').set(name)
                    mapping = obj.nested(element, 'default function')
                    next(f for f in mapping.fields() if f.type_name == 'data').set(bytes(blob))
                    dependencies = obj.functions_to_blender()
                    self.assertEqual(dependencies[name], ['one'])
                    group = bpy.data.node_groups[group_name]
                    values = [n.outputs[0].default_value for n in group.nodes if n.bl_idname == 'ShaderNodeValue']
                    self.assertIn(0.375, values)
                    decoded = Function()
                    decoded.from_native_object(obj, element)
                    self.assertEqual(decoded.sample(0, 1, 4), [(0.25, 0.375, 'AUTO'), (0.5, 0.375, 'AUTO'), (0.75, 0.375, 'AUTO')])
                    blob[0] = 0  # Identity has no curve-editor trailer.
                    next(f for f in mapping.fields() if f.type_name == 'data').set(bytes(blob))
                    identity = Function()
                    identity.from_native_object(obj, element)
                    tree = bpy.data.node_groups.new('native_identity_curve_test', 'ShaderNodeTree')
                    try:
                        identity._graph_to_nodes(tree, 0, False)
                        curve_node = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeFloatCurve')
                        curve = curve_node.mapping.curves[0]
                        for x in (0., .25, .5, 1.):
                            self.assertAlmostEqual(curve_node.mapping.evaluate(curve, x), x, places=5)
                    finally:
                        bpy.data.node_groups.remove(tree)
                    blob[0] = 0  # Identity has no curve-editor trailer.
                    next(f for f in mapping.fields() if f.type_name == 'data').set(bytes(blob))
                    identity = Function()
                    identity.from_native_object(obj, element)
                    tree = bpy.data.node_groups.new('native_identity_curve_test', 'ShaderNodeTree')
                    try:
                        identity._graph_to_nodes(tree, 0, False)
                        curve_node = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeFloatCurve')
                        curve = curve_node.mapping.curves[0]
                        for x in (0., .25, .5, 1.):
                            self.assertAlmostEqual(curve_node.mapping.evaluate(curve, x), x, places=5)
                    finally:
                        bpy.data.node_groups.remove(tree)
                    unsupported = functions[functions.add()]
                    obj.required_field(unsupported, 'export name').set(name + '_unsupported')
                    mapping = obj.nested(unsupported, 'default function')
                    next(f for f in mapping.fields() if f.type_name == 'data').set(b'bad')
                    with patch('io_scene_foundry.managed_blam.object_legacy.LegacyObjectTag') as legacy, \
                         patch.object(Function, 'make_node_group') as create_nodes:
                        legacy.return_value.__enter__.return_value.functions_to_blender.return_value = {'legacy': []}
                        self.assertEqual(obj.functions_to_blender(), {'legacy': []})
                        create_nodes.assert_not_called()
                        legacy.assert_called_once()
                    unsupported = functions[functions.add()]
                    obj.required_field(unsupported, 'export name').set(name + '_unsupported')
                    mapping = obj.nested(unsupported, 'default function')
                    next(f for f in mapping.fields() if f.type_name == 'data').set(b'bad')
                    with patch('io_scene_foundry.managed_blam.object_legacy.LegacyObjectTag') as legacy, \
                         patch.object(Function, 'make_node_group') as create_nodes:
                        legacy.return_value.__enter__.return_value.functions_to_blender.return_value = {'legacy': []}
                        self.assertEqual(obj.functions_to_blender(), {'legacy': []})
                        create_nodes.assert_not_called()
                        legacy.assert_called_once()
        finally:
            group = bpy.data.node_groups.get(group_name)
            if group is not None:
                bpy.data.node_groups.remove(group)

    def test_native_attachment_records_reach_light_converter(self):
        from unittest.mock import MagicMock
        collection = SimpleNamespace(nwo=SimpleNamespace(), objects=SimpleNamespace(link=MagicMock()))
        parent = SimpleNamespace(children=SimpleNamespace(link=MagicMock()))
        created = []
        def new_object(name, data):
            ob = SimpleNamespace(name=name, data=data, type='EMPTY')
            created.append(ob)
            return ob
        fake_bpy = SimpleNamespace(data=SimpleNamespace(
            collections=SimpleNamespace(new=MagicMock(return_value=collection), remove=MagicMock()),
            objects=SimpleNamespace(new=new_object)))
        marker = SimpleNamespace(nwo=SimpleNamespace(marker_model_group='head'))
        other = SimpleNamespace(nwo=SimpleNamespace(marker_model_group='body'))
        armature = object()
        converter = MagicMock()
        converter.__enter__.return_value.to_blender.return_value = SimpleNamespace(name='lamp')
        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
             patch.object(utils, 'get_tags_path', return_value=root), \
             patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
            (Path(root) / 'lamp.light').touch()
            with ObjectTag('test.scenery') as obj:
                block = obj.block(obj.object_struct(), 'attachments')
                element = block[block.add()]
                obj.set_reference(element, 'type', 'lamp.light')
                obj.required_field(element, 'marker').set('head')
                obj.required_field(element, 'primary scale').set('power')
                obj.required_field(element, 'secondary scale').set('pulse')
                with patch.dict(sys.modules, {'bpy': fake_bpy}), \
                     patch('io_scene_foundry.managed_blam.light.LightTag', return_value=converter) as factory:
                    attachments = obj.attachments_to_blender(armature, [marker, other], parent)
                self.assertEqual(factory.call_args.kwargs['path'].RelativePathWithExtension, 'lamp.light')
                self.assertTrue(factory.call_args.kwargs['tag_must_exist'])
                self.assertEqual(len(created), 1)
                self.assertIs(created[0].parent, marker)
                self.assertEqual(attachments[0].objects, created)
                self.assertIs(attachments[0].armature, armature)
                self.assertEqual(attachments[0].function_names, {'power', 'pulse'})
                converter.__enter__.return_value.to_blender.assert_called_once_with('power', 'pulse', attachments[0])
                parent.children.link.assert_called_once_with(collection)

    def test_migrated_wrappers_do_not_initialize_managedblam(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(utils, 'get_asset_path', return_value='objects/test'), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with ModelTag('test.model') as model:
                    model.reference_render_model.Path = 'test.render_model'
                    self.assertEqual(model.get_model_variants(), [])
                with ModelTag('test.model') as model:
                    self.assertEqual(model.reference_render_model.Path.RelativePathWithExtension, 'test.render_model')
                with ObjectTag('test.scenery') as obj:
                    obj.set_model_tag_path('test.model')
                    self.assertEqual(obj.get_variants(), [])
                    self.assertEqual(obj.functions_to_blender(), {})
                    self.assertEqual(obj.attachments_to_blender(None, [], None), [])
                    attachments = obj.block(obj.object_struct(), 'attachments')
                    for reference in (None, 'missing.light', 'test.model'):
                        obj.set_reference(attachments[attachments.add()], 'type', reference)
                    # A populated block must not start .NET for missing or unsupported attachments.
                    self.assertEqual(obj.attachments_to_blender(None, [], None), [])
                with ObjectTag('test.scenery') as obj:
                    self.assertEqual(obj.get_model_tag_path(), 'test.model')
                    with ObjectTag('cinematic.scenery') as scenery:
                        scenery.copy_cinematic_object(obj)
                        self.assertEqual(scenery.get_model_tag_path(), 'test.model')
                (Path(root) / 'lamp.light').touch()
                with CinematicLightingTag('test.new_cinematic_lighting') as tag:
                    block = tag.block(tag.tag.root(), 'dynamic lights')
                    element = block[block.add()]
                    tag.set_reference(element, 'light', 'lamp.light')
                    for field, value in [('Direction', 90.), ('Front-Back', 30.), ('Distance', 2.)]:
                        tag.required_field(element, field).set(value)
                    result = tag.to_cinematic_lighting('head', True, 3)
                    self.assertEqual((result.marker, result.persist, result.shot_index), ('head', True, 3))
                    light = result.dynamic_lights[0]
                    self.assertEqual(light.light_tag.RelativePathWithExtension, 'lamp.light')
                    self.assertAlmostEqual(light.matrix.translation.x, 0., places=4)
                    self.assertAlmostEqual(light.matrix.translation.y, 173.20508, places=4)
                    self.assertAlmostEqual(light.matrix.translation.z, 100., places=4)
                for cls, method in [(GlobalsTag, 'get_global_materials'),
                                    (RenderMethodOptionTag, 'read_options'),
                                    (RenderMethodDefinitionTag, 'get_defaults')]:
                    with cls('test.' + cls.tag_ext, tag_must_exist=False) as tag:
                        self.assertFalse(getattr(tag, method)())
                with patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo4')):
                    with MaterialShaderTag('test.material_shader', tag_must_exist=False) as tag:
                        self.assertEqual(tag.read_parameters_list(), [])
                (Path(root) / 'bad.model').write_bytes(b'not a tag')
                with ModelTag('bad.model', raise_on_error=False, hide_prints=True, always_save=True) as model:
                    self.assertFalse(model.valid)
                    self.assertIsNotNone(model.error)
                self.assertEqual((Path(root) / 'bad.model').read_bytes(), b'not a tag')

    def test_reference_converts_at_legacy_boundary(self):
        from io_scene_foundry.tags.backend import TagReference
        tag = object.__new__(managed_blam.Tag)
        tag.path = TagReference(Path('G:/tags'), 'textures/test', 'bitmap')
        factory = SimpleNamespace(TagFile=lambda: 'file',
                                  TagPath=SimpleNamespace(FromPathAndExtension=lambda p, e: (p, e)))
        with patch.object(managed_blam, 'Tags', factory):
            file, path = tag._get_tag_and_path(True)
        self.assertEqual(file, 'file')
        self.assertEqual(path, ('textures/test', 'bitmap'))

    def test_failed_legacy_object_conversion_does_not_save(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam.object_legacy import LegacyObjectTag
        document = object.__new__(LegacyObjectTag)
        document.tag = MagicMock()
        document.tag_has_changes = True
        document.always_save = True
        document.hide_prints = False
        document.__exit__(RuntimeError, RuntimeError('copy failed'), None)
        document.tag.Save.assert_not_called()
        document.tag.Dispose.assert_called_once()

    def test_failed_legacy_object_conversion_does_not_save(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam.object_legacy import LegacyObjectTag
        document = object.__new__(LegacyObjectTag)
        document.tag = MagicMock()
        document.tag_has_changes = True
        document.always_save = True
        document.hide_prints = False
        document.__exit__(RuntimeError, RuntimeError('copy failed'), None)
        document.tag.Save.assert_not_called()
        document.tag.Dispose.assert_called_once()


if __name__ == '__main__':
    unittest.main()
