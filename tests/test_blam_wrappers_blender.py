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
    def test_native_cinematic_shot_arrays(self):
        from io_scene_foundry.tags.cinematic import CinematicCameraDocument
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                path = Path(root, 'test.cinematic_scene_data')
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    shots = doc.block(doc.tag.root(), 'shots')
                    for _ in range(34):
                        shots.add()
                    objects = doc.block(doc.tag.root(), 'objects')
                    element = objects[objects.add()]
                    flags = doc.required_field(element, 'shots active flags')
                    chunks = flags.as_array()
                    self.assertGreaterEqual(len(chunks), 2)
                    doc.required_field(chunks[0], 'shot flag data').set(0x80000001)
                    doc.required_field(chunks[1], 'shot flag data').set(7)
                    self.assertEqual(doc.object_records()[0].active_shots, [0,31,32,33])
                    self.assertIsNone(doc.required_field(element, 'name').as_array())
                    stale = chunks[0]
                    objects.add()
                    with self.assertRaises(doc.api.StaleHandleError):
                        doc.value(stale, 'shot flag data')
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    self.assertEqual(doc.object_records()[0].active_shots, [0,31,32,33])

    def test_native_cinematic_music(self):
        from io_scene_foundry.tags.cinematic import CinematicCameraDocument
        from io_scene_foundry.managed_blam.cinematic_scene import CinematicMusic
        from io_scene_foundry.managed_blam.cinematic_scene import CinematicObjectFunctionKeyframe
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                path = Path(root, 'test.cinematic_scene')
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    shots = doc.block(doc.tag.root(), 'shots')
                    music = doc.block(shots[shots.add()], 'music')
                    doc.required_field(doc.tag.root(), 'anchor').set('cinematic_anchor')
                    if game in {'halo4','halo2a'}:
                        lights = doc.block(doc.tag.root(), 'lights')
                        doc.set_reference(lights[lights.add()], 'structure lighting info', 'lighting/test.scenario_structure_lighting_info')
                    for stop in (False, True):
                        element = music[music.add()]
                        doc.set_reference(element, r'music\foley', 'sound/music.sound_looping')
                        doc.required_field(element, 'frame').set(15)
                        doc.required_field(element, 'flags').set_flag('Stop Music At Frame (rather than starting it)', stop)
                    music.add()
                    if game != 'halo3':
                        screens = doc.block(shots[0], 'screen effects')
                        screen = screens[screens.add()]
                        doc.set_reference(screen, 'screen effect', 'effects/test.area_screen_effect')
                        doc.required_field(screen, 'frame').set(5)
                        doc.required_field(screen, 'stop frame').set(25)
                        if game in {'halo4','halo2a'}:
                            doc.required_field(screen, 'flags').set_flag('Persist Entire Shot', True)
                        screens.add()
                        constraints = doc.block(shots[0], 'user input constraints')
                        constraint = constraints[constraints.add()]
                        field = doc.required_field(constraint, 'maximum look angles')
                        field.set(type(field.value)(10, -20, -30, 40))
                        doc.required_field(constraint, 'frame').set(7)
                        doc.required_field(constraint, 'ticks').set(60)
                        doc.required_field(constraint, 'frictional force').set(.5)
                    objects = doc.block(doc.tag.root(), 'objects')
                    doc.required_field(objects[objects.add()], 'name').set('chief')
                    doc.required_field(objects[0], 'variant name').set('default')
                    if game in {'halo3', 'halo3odst', 'reach'}:
                        doc.required_field(objects[0], 'shots active flags').set(3)
                    lights = doc.block(shots[0], 'lighting')
                    for subject in (0, -1, 99):
                        light = lights[lights.add()]
                        doc.set_reference(light, 'lighting', 'lighting/test.new_cinematic_lighting')
                        doc.required_field(light, 'subject').set(subject)
                        doc.required_field(light, 'marker').set('head')
                        if light.field('flags') is not None:
                            doc.required_field(light, 'flags').set_flag('persists across shots', True)
                    lights.add()
                    functions = doc.block(shots[0], 'object functions')
                    function = functions[functions.add()]
                    doc.required_field(function, 'object').set(0)
                    doc.required_field(function, 'function name').set('shield')
                    keys = doc.block(function, 'keyframes')
                    for value in (.25, .75):
                        key = keys[keys.add()]
                        doc.required_field(key, 'frame').set(15)
                        doc.required_field(key, 'value').set(value)
                        doc.required_field(key, 'interpolation time').set(30)
                        doc.required_field(key, 'flags').set_flag('clear function (Value and Interpolation time are unused)', True)
                before = path.read_bytes()
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    records, = doc.music_shots()
                    metadata = doc.scene_metadata()
                    self.assertEqual(metadata.anchor, 'cinematic_anchor')
                    self.assertEqual(len(metadata.lights), 1 if game in {'halo4','halo2a'} else 0)
                    object_record, = doc.object_records()
                    self.assertEqual((object_record.index, object_record.name, object_record.variant), (0,'chief','default'))
                    self.assertEqual(object_record.active_shots, [0] if game in {'halo3','halo3odst','reach'} else None)
                    light, = doc.lighting_shots()[0]
                    self.assertEqual((light.subject, light.marker), (0, 'head'))
                    self.assertEqual(light.lighting.RelativePathWithExtension, 'lighting\\test.new_cinematic_lighting')
                    if game != 'halo3':
                        screen, = doc.screen_effect_shots()[0]
                        self.assertEqual(screen.screen_effect.RelativePathWithExtension, 'effects\\test.area_screen_effect')
                        self.assertEqual((screen.frame, screen.stop_frame), (5,25))
                        self.assertEqual(screen.persist_entire_shot, game in {'halo4','halo2a'})
                        constraint, = doc.user_constraint_shots()[0]
                        self.assertEqual(constraint.maximum_look_angles, (10,-20,-30,40))
                        self.assertEqual((constraint.frame, constraint.ticks, constraint.frictional_force), (7,60,.5))
                    else:
                        self.assertEqual(doc.user_constraint_shots(), [[]])
                    function_record, = doc.object_function_shots()[0]
                    self.assertEqual(function_record.object, 'chief')
                    event = SimpleNamespace()
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        CinematicObjectFunctionKeyframe.from_native(function_record).to_event(
                            SimpleNamespace(cinematic_events=SimpleNamespace(add=lambda: event)), game in {'halo4','halo2a'})
                    self.assertEqual(event.value, .75)
                    self.assertEqual(event.interpolation_time, 1.)
                    self.assertEqual(event.function_name, 'shield')
                    self.assertTrue(event.clear_function)
                self.assertEqual(len(records), 2)
                for record, stop in zip(records, (False, True)):
                    event = SimpleNamespace()
                    nwo = SimpleNamespace(cinematic_events=SimpleNamespace(add=lambda: event))
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        CinematicMusic.from_native(record).to_event(nwo, game in {'halo4','halo2a'})
                    self.assertEqual(event.music, 'sound\\music.sound_looping')
                    self.assertEqual(event.stop, stop)
                    self.assertEqual(event.frame, 15 if game in {'halo4','halo2a'} else 16)
                self.assertEqual(before, path.read_bytes())

    def test_native_cinematic_camera_frames(self):
        from io_scene_foundry.tags.cinematic import CinematicCameraDocument
        from io_scene_foundry.managed_blam.cinematic_scene import CinematicDialogue, CinematicEffect, CinematicCustomScript
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                extension = 'cinematic_scene_data' if game in {'halo4', 'halo2a'} else 'cinematic_scene'
                path = Path(root, 'test.' + extension)
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    shots = doc.block(doc.tag.root(), 'shots')
                    frames = doc.block(shots[shots.add()], 'frame data')
                    doc.required_field(shots[0], 'frame count').set(24)
                    camera = doc.required_field(frames[frames.add()], 'camera frame').as_struct()
                    dynamic = camera.field('dynamic data')
                    constant = camera.field('constant data')
                    dynamic = dynamic.as_struct() if dynamic is not None else camera
                    constant = constant.as_struct() if constant is not None else camera
                    for name, values in [('camera position',(1.,2.,3.)), ('camera forward',(1.,0.,0.)), ('camera up',(0.,0.,1.))]:
                        field = doc.required_field(dynamic, name)
                        field.set(type(field.value)(*values))
                    doc.required_field(constant, 'focal length').set(35.)
                    dialogue = doc.block(shots[0], 'dialogue')
                    element = dialogue[dialogue.add()]
                    doc.set_reference(element, 'dialogue', 'sound/test.sound')
                    doc.required_field(element, 'frame').set(10)
                    doc.required_field(element, 'scale').set(.5)
                    doc.required_field(element, 'lipsync actor').set('chief')
                    doc.required_field(element, 'subtitle').set('hello')
                    objects = doc.block(doc.tag.root(), 'objects')
                    doc.required_field(objects[objects.add()], 'name').set('chief')
                    effects = doc.block(shots[0], 'effects')
                    element = effects[effects.add()]
                    doc.set_reference(element, 'effect', 'effects/test.effect')
                    doc.required_field(element, 'marker parent').set(0)
                    doc.required_field(element, 'frame').set(20)
                    if game in {'halo4', 'halo2a'}:
                        doc.required_field(element, 'state').set(2)
                        doc.required_field(element, 'flags').set_flag('looping', True)
                    effects.add()  # Empty effect references must not create events.
                    doc.set_reference(objects[0], 'model animation graph', 'objects/chief.model_animation_graph')
                    doc.set_reference(objects[0], 'object type', 'objects/chief.biped')
                    scripts = doc.block(shots[0], 'custom script')
                    element = scripts[scripts.add()]
                    doc.required_field(element, 'frame').set(12)
                    script = doc.required_field(element, 'script').as_struct()
                    doc.required_field(script, 'script').set(b'(print "hello")\r\n\x00')
                before = path.read_bytes()
                with CinematicCameraDocument(path, tags_root=root, game=game) as doc:
                    records = doc.camera_shots()
                    self.assertEqual(doc.shot_frame_counts(), [24])
                    self.assertEqual(records[0][0].position, (1.,2.,3.))
                    self.assertEqual(records[0][0].lens, 35.)
                    dialogue_record = doc.dialogue_shots()[0][0]
                    dialogue = CinematicDialogue.from_native(dialogue_record)
                    event = SimpleNamespace()
                    nwo = SimpleNamespace(cinematic_events=SimpleNamespace(add=lambda: event))
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        dialogue.to_event(nwo, game in {'halo4', 'halo2a'})
                    self.assertEqual(event.sound_tag, 'sound\\test.sound')
                    self.assertEqual(event.frame, 10 if game in {'halo4','halo2a'} else 11)
                    self.assertEqual(event.sound_scale, .5)
                    self.assertEqual(event.subtitle, 'hello')
                    self.assertEqual(dialogue.actor, 'chief')
                    object_record, = doc.object_records()
                    self.assertEqual(object_record.graph.RelativePathWithExtension, 'objects\\chief.model_animation_graph')
                    self.assertEqual(object_record.object_type.RelativePathWithExtension, 'objects\\chief.biped')
                    effect_record, = doc.effect_shots()[0]
                    effect = CinematicEffect.from_native(effect_record)
                    with patch.object(utils, 'blender_frame', side_effect=lambda frame: frame):
                        effect.to_event(nwo, game in {'halo4', 'halo2a'})
                    self.assertEqual(effect.marker_parent, 'chief')
                    self.assertEqual(event.effect, 'effects\\test.effect')
                    self.assertEqual(event.effect_state, '2' if game in {'halo4','halo2a'} else '0')
                    self.assertEqual(event.frame, 20 if game in {'halo4','halo2a'} else 21)
                    script_record, = doc.script_shots()[0]
                    self.assertEqual(script_record.frame, 12)
                    CinematicCustomScript.from_native(script_record).to_event(nwo)
                    self.assertEqual(event.type, 'SCRIPT')
                    self.assertEqual(event.script_type, 'CUSTOM')
                    self.assertEqual(event.script, '(print "hello")\r\n')
                    frames = doc.block(doc.block(doc.tag.root(), 'shots')[0], 'frame data')
                    frames.clear()
                    with self.assertRaisesRegex(ValueError, 'no camera frames'):
                        doc.camera_shots()
                self.assertEqual(records[0][0].forward, (1.,0.,0.))
                self.assertEqual(before, path.read_bytes())

    def test_native_polyart_roundtrip_and_mesh(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.managed_blam.polyart import PolyArtTag, _float_to_short
        from io_scene_foundry.managed_blam import import_transform
        packed = [tuple(_float_to_short(v, 'test') for v in row) for row in
                  [(0.,0.,0.,.5,0.,0.), (10.,0.,0.,1.,1.,0.), (0.,10.,0.,.25,0.,1.)]]
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                 patch.object(import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(import_transform, 'object_matrix', side_effect=lambda m: m), \
                 patch.object(import_transform, 'scale_factor', return_value=1.):
                with PolyArtTag('test.polyart_asset') as tag:
                    tag.from_blender(packed, [(0,1,2)])
                before = Path(root, 'test.polyart_asset').read_bytes()
                old_objects, old_meshes, old_cameras, old_materials = map(set, (bpy.data.objects, bpy.data.meshes, bpy.data.cameras, bpy.data.materials))
                try:
                    with PolyArtTag('test.polyart_asset') as tag:
                        self.assertEqual(len(tag.block_vertices), 3)
                        self.assertEqual(len(tag.placement_data), 1)
                        objects = tag.to_blender()
                        mesh = next(ob.data for ob in objects if ob.type == 'MESH')
                        self.assertEqual(len(mesh.polygons), 1)
                        self.assertAlmostEqual(mesh.vertices[1].co.x, 1.)
                        self.assertAlmostEqual(mesh.color_attributes['Color'].data[0].color[3], .5)
                        self.assertEqual(tuple(mesh.uv_layers[0].data[1].uv), (1.,0.))
                        with self.assertRaisesRegex(RuntimeError, 'outside the vertex block'):
                            tag.from_blender(packed, [(0,1,99)])
                    self.assertEqual(before, Path(root, 'test.polyart_asset').read_bytes())
                finally:
                    for ob in set(bpy.data.objects) - old_objects:
                        bpy.data.objects.remove(ob, do_unlink=True)
                    for data, previous in ((bpy.data.meshes, old_meshes), (bpy.data.cameras, old_cameras), (bpy.data.materials, old_materials)):
                        for item in set(data) - previous:
                            data.remove(item)

    def test_native_decorator_metadata(self):
        from io_scene_foundry.managed_blam.decorator_set import DecoratorSetTag
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with DecoratorSetTag('test.decorator_set', tag_must_exist=False) as tag:
                    instances = tag.block(tag.tag.root(), 'render model instance names')
                    tag.required_field(instances[instances.add()], 'name').set('grass')
                    types = tag.block(tag.tag.root(), 'decorator types')
                    for index in (-1, 0, 99):
                        tag.required_field(types[types.add()], 'mesh').set(index)
                    if game in {'halo3', 'halo3odst'}:
                        tag.reference_base.Path = 'grass.render_model'
                    else:
                        tag.reference_lod2.Path = 'grass.render_model'
                Path(root, 'grass.render_model').touch()
                before = Path(root, 'test.decorator_set').read_bytes()
                with DecoratorSetTag('test.decorator_set') as tag:
                    item, = tag.get_decorator_types()
                    self.assertEqual((item.decorator_type_name, item.decorator_type_index, item.render_model_instance_index), ('grass', 1, 0))
                    self.assertEqual(tag.get_first_valid_render_model().RelativePathWithExtension, 'grass.render_model')
                self.assertEqual(before, Path(root, 'test.decorator_set').read_bytes())

    def test_native_serialized_physics_records(self):
        from io_scene_foundry.managed_blam.physics_model import PhysicsTag
        from io_scene_foundry.managed_blam.connected_geometry import HavokCollision, RigidBody
        from io_scene_foundry.managed_blam import import_transform
        from mathutils import Matrix
        from unittest.mock import MagicMock
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with PhysicsTag('serialized.physics_model') as tag:
                    groups = tag.block(tag.tag.root(), 'RigidBody Serialized Shapes')
                    group = groups[groups.add()]
                    shapes = tag.block(group, 'Mopp Serialized Havok Data')
                    element = shapes[shapes.add()]
                    base = tag.required_field(element, 'base').as_struct()
                    tag.required_field(base, 'name').set('serialized_body')
                    tag.required_field(base, 'material').set(-1)
                    tag.required_field(base, 'friction').set(.5)
                    tag.required_field(element, 'Serialized Havok Data').set(b'\x00\x01\xfe\xff')
                    def add(parent, name):
                        block = tag.block(parent, name)
                        return block[block.add()]
                    tag.required_field(add(tag.tag.root(), 'nodes'), 'name').set('root')
                    body = add(tag.tag.root(), 'rigid bodies')
                    tag.required_field(body, 'node').set(0)
                    tag.required_field(body, 'serialized shapes').set(0)
                    reference = tag.required_field(body, 'shape reference').as_struct()
                    tag.required_field(reference, 'shape').set(-1)
                    region = add(tag.tag.root(), 'regions')
                    permutation = add(region, 'permutations')
                    tag.required_field(add(permutation, 'rigid bodies'), 'rigid body').set(0)
                before = (Path(root) / 'serialized.physics_model').read_bytes()
                with PhysicsTag('serialized.physics_model') as tag:
                    record, = tag.serialized_shapes(0)
                    with self.assertRaisesRegex(ValueError, 'index'):
                        tag.serialized_shapes(-1)
                    with self.assertRaisesRegex(ValueError, 'index'):
                        tag.serialized_shapes(1)
                    native_record, = tag.primitive_bodies(include_serialized=True)
                    self.assertEqual(native_record.kind, 'serialized')
                    rig = SimpleNamespace(pose=SimpleNamespace(bones={'root': SimpleNamespace(matrix=Matrix.Identity(4))}))
                    collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
                    decoded = SimpleNamespace()
                    def convert(body):
                        body.shapes[0].ob = SimpleNamespace()
                    with patch.object(HavokCollision, 'from_serialized_shape', return_value=decoded) as decoder, \
                         patch.object(RigidBody, 'to_objects', convert), \
                         patch.object(utils, 'set_region'), patch.object(utils, 'set_permutation'), \
                         patch.object(import_transform, 'object_matrix', side_effect=lambda matrix, **kw: matrix):
                        objects = tag.to_blend_objects(collection, rig)
                        self.assertEqual(len(objects), 1)
                        self.assertEqual(objects[0].parent_bone, 'root')
                        self.assertEqual(decoded.friction, .5)
                        decoder.assert_called_once()
                        collection.objects.link.reset_mock()
                        with self.assertRaisesRegex(ValueError, 'armature bone'):
                            tag.to_blend_objects(collection, SimpleNamespace(pose=SimpleNamespace(bones={})))
                        collection.objects.link.assert_not_called()
                    with patch.object(HavokCollision, 'from_serialized_shape', return_value=None), \
                         patch.object(RigidBody, 'to_objects') as convert, \
                         patch('io_scene_foundry.managed_blam.physics_legacy.LegacyPhysicsTag') as legacy:
                        legacy.return_value.__enter__.return_value.to_blend_objects.return_value = []
                        self.assertEqual(tag.to_blend_objects(collection, rig), [])
                        legacy.assert_called_once()
                        convert.assert_not_called()
                        collection.objects.link.assert_not_called()
                self.assertEqual(record.data, b'\x00\x01\xfe\xff')
                self.assertEqual(record.name, 'serialized_body')
                self.assertEqual(record.friction, .5)
                self.assertIsNone(record.material)
                self.assertEqual((Path(root) / 'serialized.physics_model').read_bytes(), before)

    def test_native_physics_mesh_creation(self):
        import bpy
        from mathutils import Matrix
        from io_scene_foundry.managed_blam.connected_geometry import Sphere, Box, Pill, Polyhedron, RigidBody, HavokCollision
        from io_scene_foundry.managed_blam import import_transform

        class PhysicsTestProperties(bpy.types.PropertyGroup):
            mesh_type: bpy.props.StringProperty()
            mesh_primitive_type: bpy.props.StringProperty()
            global_material: bpy.props.StringProperty()

        bpy.utils.register_class(PhysicsTestProperties)
        bpy.types.Mesh.nwo = bpy.props.PointerProperty(type=PhysicsTestProperties)
        bpy.types.Object.nwo = bpy.props.PointerProperty(type=PhysicsTestProperties)
        existing_objects, existing_meshes = set(bpy.data.objects), set(bpy.data.meshes)
        existing_materials = set(bpy.data.materials)
        try:
            with patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')), \
                 patch.object(import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                 patch.object(import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)):
                record = SimpleNamespace(name='native_physics_mesh', material=SimpleNamespace(name='metal'),
                    material_index=0, friction=.5, restitution=.25, radius=.5, translation=(1.,2.,3.),
                    half_extents=(1.,2.,3.), axes=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),
                    bottom=(0.,0.,0.), top=(0.,0.,2.), offset=0,
                    vertices=[(0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.)])
                for cls in (Sphere, Box, Pill, Polyhedron, HavokCollision):
                    with self.subTest(shape=cls.__name__):
                        if cls is HavokCollision:
                            shape = HavokCollision(record.name, [(0.,0.,0.),(100.,0.,0.),(0.,100.,0.)],
                                [(0,1,2)], [0], [record.material], [(7,8)])
                            shape.material = record.material
                        else:
                            shape = cls.from_native(record)
                        body = RigidBody.__new__(RigidBody)
                        body.shapes, body.is_havok_rigid_body = [shape], False
                        body.to_objects()
                        self.assertGreater(len(shape.ob.data.polygons), 0)
                        self.assertEqual(shape.ob.nwo.global_material, 'metal')
                        self.assertEqual(shape.ob.data.nwo.mesh_type, '_connected_geometry_mesh_type_physics')
                        self.assertEqual(shape.ob.data.materials[0].name, 'Physics')
                        if cls is Box:
                            self.assertEqual(len(shape.ob.data.polygons), 6)
                        elif cls is Polyhedron:
                            self.assertEqual(len(shape.ob.data.polygons), 4)
                        elif cls is HavokCollision:
                            self.assertEqual(len(shape.ob.data.polygons), 1)
                            self.assertEqual(shape.ob.data.attributes['foundry_havok_render_triangle_index'].data[0].value, 7)
                            self.assertEqual(shape.ob.data.attributes['foundry_havok_render_triangle_count'].data[0].value, 2)
        finally:
            for ob in set(bpy.data.objects) - existing_objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            for mesh in set(bpy.data.meshes) - existing_meshes:
                bpy.data.meshes.remove(mesh)
            for material in set(bpy.data.materials) - existing_materials:
                bpy.data.materials.remove(material)
            del bpy.types.Object.nwo
            del bpy.types.Mesh.nwo
            bpy.utils.unregister_class(PhysicsTestProperties)

    def test_native_physics_primitive_bodies(self):
        from mathutils import Matrix, Vector
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam.physics_model import PhysicsTag
        from io_scene_foundry.managed_blam.connected_geometry import RigidBody, Sphere, Box, Pill, Polyhedron
        from io_scene_foundry.tags.physics import PhysicsShapesUnsupported
        from io_scene_foundry.managed_blam import import_transform
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with PhysicsTag('test.physics_model') as tag:
                    def add(parent, name):
                        block = tag.block(parent, name)
                        return block[block.add()]
                    node = add(tag.tag.root(), 'nodes')
                    tag.required_field(node, 'name').set('root')
                    material = add(tag.tag.root(), 'materials')
                    tag.required_field(material, 'name').set('metal')
                    sphere = add(tag.tag.root(), 'spheres')
                    base = tag.required_field(sphere, 'base').as_struct()
                    tag.required_field(base, 'name').set('ball')
                    tag.required_field(base, 'material').set(0)
                    translate = tag.required_field(sphere, 'translate shape').as_struct()
                    convex = tag.required_field(translate, 'convex').as_struct()
                    tag.required_field(convex, 'radius').set(.5)
                    field = tag.required_field(translate, 'translation')
                    field.set(type(field.value)(1., 2., 3.))
                    body = add(tag.tag.root(), 'rigid bodies')
                    tag.required_field(body, 'node').set(0)
                    if game in {'halo4', 'halo2a'}:
                        tag.required_field(body, 'serialized shapes').set(-1)
                    reference = tag.required_field(body, 'shape reference').as_struct()
                    tag.required_field(reference, 'shape type').set(0)
                    tag.required_field(reference, 'shape').set(0)
                    region = add(tag.tag.root(), 'regions')
                    tag.required_field(region, 'name').set('body')
                    permutation = add(region, 'permutations')
                    tag.required_field(permutation, 'name').set('default')
                    tag.required_field(add(permutation, 'rigid bodies'), 'rigid body').set(0)
                before = (Path(root) / 'test.physics_model').read_bytes()
                rig = SimpleNamespace(pose=SimpleNamespace(bones={'root': SimpleNamespace(matrix=Matrix.Identity(4))}))
                collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
                def convert(body):
                    body.shapes[0].ob = SimpleNamespace()
                with PhysicsTag('test.physics_model') as tag, \
                     patch.object(RigidBody, 'to_objects', convert), \
                     patch.object(utils, 'set_region') as region_set, patch.object(utils, 'set_permutation'), \
                     patch.object(import_transform, 'object_matrix', side_effect=lambda matrix, **kw: matrix):
                    record, = tag.primitive_bodies()
                    shape = Sphere.from_native(record)
                    self.assertEqual(shape.radius, 50.)
                    self.assertEqual(shape.material.name, 'metal')
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(len(objects), 1)
                    self.assertEqual(objects[0].parent_bone, 'root')
                    self.assertEqual(tuple(objects[0].matrix_world.translation), (100., 200., 300.))
                    region_set.assert_called_once()
                    base = tag.required_field(tag.block(tag.tag.root(), 'spheres')[0], 'base').as_struct()
                    friction = tag.required_field(base, 'friction')
                    saved_friction = friction.value
                    friction.set(float('nan'))
                    collection.objects.link.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'friction or restitution'):
                        tag.to_blend_objects(collection, rig)
                    collection.objects.link.assert_not_called()
                    friction.set(saved_friction)
                    body = tag.block(tag.tag.root(), 'rigid bodies')[0]
                    if game in {'halo4', 'halo2a'}:
                        flags = tag.required_field(body, 'flags')
                        for flag in ('Havok rigid body', 'explicit mass', 'absolute center of mass'):
                            flags.set_flag(flag, True)
                        for name, value in [('mass', 12.), ('inertia tensor scale', 2.),
                                            ('inertia tensor scale x', 1.), ('inertia tensor scale y', 2.),
                                            ('inertia tensor scale z', 3.), ('linear damping', .5), ('angular damping', .25)]:
                            tag.required_field(body, name).set(value)
                        center = tag.required_field(body, 'center off mass offset')
                        center.set(type(center.value)(1., 2., 3.))
                        record, = tag.primitive_bodies()
                        native_body = RigidBody.__new__(RigidBody)
                        native_body.havok_info = record.havok
                        native_shape = Sphere.from_native(record)
                        native_shape.ob = SimpleNamespace(nwo=SimpleNamespace())
                        native_body.setup_havok_props(native_shape)
                        props = native_shape.ob.nwo
                        self.assertEqual(props.havok_mass, 12.)
                        self.assertTrue(props.havok_change_mass)
                        self.assertEqual(props.havok_center_of_mass, (1., 2., 3.))
                        self.assertEqual(props.havok_inertia_tensor, (1., 2., 3.))
                        self.assertEqual(props.havok_linear_damping, .5)
                        self.assertEqual(props.rigid_body_type, 'HAVOK')
                        tag.required_field(body, 'serialized shapes').set(0)
                        with self.assertRaisesRegex(PhysicsShapesUnsupported, 'Serialized'):
                            tag.primitive_bodies()
                        tag.required_field(body, 'serialized shapes').set(-1)
                        flags.set_flag('Havok rigid body', False)
                    reference = tag.required_field(body, 'shape reference').as_struct()
                    tag.required_field(reference, 'shape type').set(2)
                    boxes = tag.block(tag.tag.root(), 'boxes')
                    box = boxes[boxes.add()]
                    base = tag.required_field(box, 'base').as_struct()
                    tag.required_field(base, 'name').set('box')
                    tag.required_field(base, 'material').set(0)
                    convex = tag.required_field(box, 'box shape').as_struct()
                    tag.required_field(convex, 'radius').set(.5)
                    transform = tag.required_field(box, 'convex transform shape').as_struct()
                    for name, values in [('translation', (1., 2., 3.)), ('rotation i', (1.,0.,0.)),
                                         ('rotation j', (0.,1.,0.)), ('rotation k', (0.,0.,1.))]:
                        field = tag.required_field(transform, name)
                        field.set(type(field.value)(*values))
                    extents = tag.required_field(box, 'half extents')
                    extents.set(type(extents.value)(.25, .75, 1.25))
                    record, = tag.primitive_bodies()
                    converted = Box.from_native(record)
                    self.assertEqual((converted.width, converted.length, converted.height), (150., 250., 350.))
                    self.assertEqual(tuple(converted.matrix.to_scale()), (150., 250., 350.))
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(tuple(objects[0].matrix_world.translation), (100., 200., 300.))
                    extents.set(type(extents.value)(-1., .75, 1.25))
                    with self.assertRaisesRegex(ValueError, 'box dimensions'):
                        tag.primitive_bodies()
                    tag.required_field(body, 'node').set(-1)
                    with self.assertRaisesRegex(PhysicsShapesUnsupported, 'Unbound'):
                        tag.primitive_bodies()
                    tag.required_field(body, 'node').set(0)
                    tag.required_field(reference, 'shape type').set(1)
                    pills = tag.block(tag.tag.root(), 'pills')
                    pill = pills[pills.add()]
                    base = tag.required_field(pill, 'base').as_struct()
                    tag.required_field(base, 'name').set('capsule')
                    tag.required_field(base, 'material').set(0)
                    capsule = tag.required_field(pill, 'capsule shape').as_struct()
                    tag.required_field(capsule, 'radius').set(.5)
                    for name, values in [('bottom', (1., 2., 3.)), ('top', (1., 2., 5.))]:
                        field = tag.required_field(pill, name)
                        field.set(type(field.value)(*values))
                    record, = tag.primitive_bodies()
                    converted = Pill.from_native(record)
                    self.assertEqual(converted.radius, 50.)
                    self.assertEqual(tuple(converted.matrix @ Vector((0., 0., 0.))), (100., 200., 250.))
                    self.assertEqual(tuple(converted.matrix @ Vector((0., 0., 2.))), (100., 200., 550.))
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(tuple(objects[0].matrix_world.translation), (100., 200., 250.))
                    top = tag.required_field(pill, 'top')
                    top.set(type(top.value)(1., 2., 3.))
                    with self.assertRaisesRegex(PhysicsShapesUnsupported, 'Zero-length'):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(4)
                    polyhedra = tag.block(tag.tag.root(), 'polyhedra')
                    for i in range(2):
                        poly = polyhedra[polyhedra.add()]
                        tag.required_field(poly, 'four vectors size').set(1)
                    tag.required_field(reference, 'shape').set(1)
                    vectors = tag.block(tag.tag.root(), 'polyhedron four vectors')
                    vectors.add()  # First shape's vector group must not leak into the second.
                    packed = vectors[vectors.add()]
                    for axis, values, last in [('x', (0.,1.,0.), 0.), ('y',(0.,0.,1.),0.), ('z',(0.,0.,0.),1.)]:
                        field = tag.required_field(packed, f'four vectors {axis}')
                        field.set(type(field.value)(*values))
                        tag.required_field(packed, f'havok w four vectors {axis}').set(last)
                    record, = tag.primitive_bodies()
                    self.assertEqual(record.offset, 1)
                    converted = Polyhedron.from_native(record)
                    self.assertEqual([tuple(v) for v in converted.vertices], [(0.,0.,0.),(100.,0.,0.),(0.,100.,0.),(0.,0.,100.)])
                    import bmesh
                    bm = bmesh.new()
                    try:
                        for point in converted.vertices:
                            bm.verts.new(point)
                        bmesh.ops.convex_hull(bm, input=list(bm.verts))
                        self.assertEqual(len(bm.faces), 4)
                    finally:
                        bm.free()
                    self.assertEqual(len(tag.to_blend_objects(collection, rig)), 1)
                    poly = polyhedra[1]
                    tag.required_field(poly, 'four vectors size').set(99)
                    with self.assertRaisesRegex(ValueError, 'vector range'):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(14)
                    lists = tag.block(tag.tag.root(), 'lists')
                    for count in (1, 2):
                        element = lists[lists.add()]
                        tag.required_field(element, 'child shapes size').set(count)
                    children = tag.block(tag.tag.root(), 'list shapes')
                    for kind in (3, 0, 0):
                        child = children[children.add()]
                        child_ref = tag.required_field(child, 'shape reference').as_struct()
                        tag.required_field(child_ref, 'shape type').set(kind)
                        tag.required_field(child_ref, 'shape').set(0)
                    # List 1 skips the unsupported child belonging to list 0.
                    records = tag.primitive_bodies()
                    self.assertEqual([r.name for r in records], ['ball', 'ball'])
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(len(objects), 2)
                    self.assertTrue(all(ob.parent_bone == 'root' for ob in objects))
                    mopps = tag.block(tag.tag.root(), 'mopps')
                    mopp = mopps[mopps.add()]
                    if game in {'halo4', 'halo2a'}:
                        mopp_ref = tag.required_field(mopp, 'childShapePointer').as_struct()
                        tag.required_field(mopp_ref, 'shape type').set(14)
                        tag.required_field(mopp_ref, 'shape').set(1)
                    else:
                        tag.required_field(mopp, 'list').set(1)
                    tag.required_field(reference, 'shape type').set(15)
                    tag.required_field(reference, 'shape').set(0)
                    self.assertEqual([r.name for r in tag.primitive_bodies()], ['ball', 'ball'])
                    self.assertEqual(len(tag.to_blend_objects(collection, rig)), 2)
                    if game == 'halo3':
                        # Older H4 tags retain the pre-serialized-body/MOPP layout.
                        tag.game = 'halo4'
                        try:
                            self.assertEqual([r.name for r in tag.primitive_bodies()], ['ball', 'ball'])
                            self.assertEqual(len(tag.to_blend_objects(collection, rig)), 2)
                        finally:
                            tag.game = game
                    tag.required_field(reference, 'shape').set(99)
                    with self.assertRaisesRegex(ValueError, 'MOPP index'):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape').set(0)
                    if game in {'halo4', 'halo2a'}:
                        tag.required_field(mopp_ref, 'shape type').set(0)
                        tag.required_field(mopp_ref, 'shape').set(0)
                        self.assertEqual(len(tag.primitive_bodies()), 1)
                        tag.required_field(mopp_ref, 'shape type').set(15)
                        with self.assertRaisesRegex(ValueError, 'Circular'):
                            tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(14)
                    tag.required_field(reference, 'shape').set(1)
                    tag.required_field(lists[1], 'child shapes size').set(99)
                    with self.assertRaisesRegex(ValueError, 'list child range'):
                        tag.primitive_bodies()
                    tag.required_field(lists[1], 'child shapes size').set(-1)
                    with self.assertRaisesRegex(ValueError, 'Negative physics list'):
                        tag.primitive_bodies()
                    tag.required_field(lists[1], 'child shapes size').set(2)
                    child_ref = tag.required_field(children[2], 'shape reference').as_struct()
                    tag.required_field(child_ref, 'shape type').set(14)
                    first_ref = tag.required_field(children[0], 'shape reference').as_struct()
                    tag.required_field(first_ref, 'shape type').set(0)
                    self.assertEqual([r.name for r in tag.primitive_bodies()], ['ball', 'ball'])
                    # Reusing a list in separate branches is not a cycle.
                    second_ref = tag.required_field(children[1], 'shape reference').as_struct()
                    tag.required_field(second_ref, 'shape type').set(14)
                    self.assertEqual(len(tag.to_blend_objects(collection, rig)), 2)
                    tag.required_field(first_ref, 'shape type').set(14)
                    tag.required_field(first_ref, 'shape').set(1)
                    collection.objects.link.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'Circular'):
                        tag.to_blend_objects(collection, rig)
                    collection.objects.link.assert_not_called()
                    tag.required_field(first_ref, 'shape type').set(3)
                    with self.assertRaises(PhysicsShapesUnsupported):
                        tag.primitive_bodies()
                    tag.required_field(reference, 'shape type').set(3)
                    with self.assertRaises(PhysicsShapesUnsupported):
                        tag.primitive_bodies()
                self.assertEqual((Path(root) / 'test.physics_model').read_bytes(), before)

    def test_native_physics_constraints(self):
        from mathutils import Matrix
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam.physics_model import PhysicsTag
        from io_scene_foundry.managed_blam import connected_geometry, import_transform
        from io_scene_foundry.tags.physics import CONSTRAINT_FIELDS
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with PhysicsTag('test.physics_model') as tag:
                    nodes = tag.block(tag.tag.root(), 'nodes')
                    for name in ('parent', 'child'):
                        tag.required_field(nodes[nodes.add()], 'name').set(name)
                    for kind, fields in CONSTRAINT_FIELDS.items():
                        block = tag.block(tag.tag.root(), kind)
                        element = block[block.add()]
                        body = tag.required_field(element, 'constraint bodies').as_struct()
                        tag.required_field(body, 'name').set(kind)
                        tag.required_field(body, 'node a').set(0)
                        tag.required_field(body, 'node b').set(1)
                        for side in ('a', 'b'):
                            for name, values in [('forward', (1.,0.,0.)), ('left',(0.,1.,0.)), ('up',(0.,0.,1.)),
                                                 ('position', (1.,2.,3. if side == 'a' else 7.))]:
                                field = tag.required_field(body, f'{side} {name}')
                                field.set(type(field.value)(*values))
                        for i, name in enumerate(fields.values(), start=1):
                            tag.required_field(element, name).set(float(i))
                before = (Path(root) / 'test.physics_model').read_bytes()
                factory = MagicMock(side_effect=lambda name, data: SimpleNamespace(name=name, nwo=SimpleNamespace(), empty_display_size=1.))
                fake = SimpleNamespace(data=SimpleNamespace(objects=SimpleNamespace(new=factory)))
                rig = SimpleNamespace(pose=SimpleNamespace(bones={name: SimpleNamespace(matrix=Matrix.Identity(4)) for name in ('parent','child')}))
                collection = SimpleNamespace(objects=SimpleNamespace(link=MagicMock()))
                with PhysicsTag('test.physics_model') as tag, patch.object(connected_geometry, 'bpy', fake), \
                     patch.object(import_transform, 'scale_factor', return_value=1.), \
                     patch.object(import_transform, 'object_matrix', side_effect=lambda matrix, **kw: matrix), \
                     patch.object(import_transform, 'keep_marker_axis', side_effect=lambda matrix: matrix):
                    records = tag.constraints()
                    constraint = connected_geometry.Constraint.from_native(records[0])
                    self.assertEqual(constraint.matrix_a.translation.z, 300.)
                    self.assertEqual(constraint.matrix_b.translation.z, 700.)
                    objects = tag.to_blend_objects(collection, rig)
                    self.assertEqual(len(objects), 6)
                    self.assertEqual(objects[0].nwo.physics_constraint_type, '_connected_geometry_marker_type_physics_hinge_constraint')
                    self.assertAlmostEqual(objects[1].nwo.hinge_constraint_maximum, .034906585)
                    self.assertEqual(objects[-1].nwo.prismatic_limit_min, 1.)
                    self.assertEqual(objects[-1].nwo.prismatic_limit_max, 2.)
                    self.assertEqual(objects[-1].nwo.prismatic_limit_friction, 3.)
                    self.assertEqual(objects[-1].parent_bone, 'parent')
                    factory.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'requires both armature bones'):
                        tag.to_blend_objects(collection, SimpleNamespace(pose=SimpleNamespace(bones={})))
                    factory.assert_not_called()
                self.assertEqual((Path(root) / 'test.physics_model').read_bytes(), before)

    def test_native_collision_geometry_and_invalid_loops(self):
        from mathutils import Vector
        from io_scene_foundry.managed_blam.collision_model import CollisionTag
        from io_scene_foundry.managed_blam.connected_geometry import ModelCollision
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with CollisionTag('test.collision_model') as tag:
                    def add(parent, name):
                        block = tag.block(parent, name)
                        return block[block.add()]
                    node = add(tag.tag.root(), 'nodes')
                    tag.required_field(node, 'name').set('root')
                    material = add(tag.tag.root(), 'materials')
                    tag.required_field(material, 'name').set('metal')
                    region = add(tag.tag.root(), 'regions')
                    tag.required_field(region, 'name').set('body')
                    permutation = add(region, 'permutations')
                    tag.required_field(permutation, 'name').set('default')
                    record = add(permutation, 'bsps')
                    tag.required_field(record, 'node index').set(0)
                    bsp = tag.required_field(record, 'bsp').as_struct()
                    for point in ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)):
                        vertex = add(bsp, 'vertices')
                        field = tag.required_field(vertex, 'point')
                        field.set(type(field.value)(*point))
                    for i in range(3):
                        edge = add(bsp, 'edges')
                        for name, value in [('start vertex', i), ('end vertex', (i+1)%3),
                                            ('forward edge', (i+1)%3), ('reverse edge', -1),
                                            ('left surface', 0), ('right surface', -1)]:
                            tag.required_field(edge, name).set(65535 if value == -1 and game in {'halo4', 'halo2a'} else value)
                    surface = add(bsp, 'surfaces')
                    tag.required_field(surface, 'first edge').set(0)
                    tag.required_field(surface, 'material').set(0)
                    tag.required_field(surface, 'flags').set_flag('climbable', True)
                    if game in {'halo3', 'halo3odst'}:
                        tag.required_field(surface, 'plane').set(-32768)
                    else:
                        tag.required_field(surface, 'flags').set_flag('plane negated', True)
                    sphere = add(tag.tag.root(), 'pathfinding spheres')
                    tag.required_field(sphere, 'node').set(0)
                    tag.required_field(sphere, 'radius').set(.5)
                    tag.required_field(sphere, 'flags').set_flag('vehicle only', True)
                before = (Path(root) / 'test.collision_model').read_bytes()
                with CollisionTag('test.collision_model') as tag:
                    meshes, spheres = tag.read_collision()
                    self.assertEqual(meshes[0].polygons, [[0, 1, 2]])
                    self.assertEqual(meshes[0].bone, 'root')
                    self.assertTrue(meshes[0].surfaces[0].ladder)
                    self.assertTrue(meshes[0].surfaces[0].negated)
                    self.assertEqual(meshes[0].surfaces[0].material.name, 'metal')
                    self.assertTrue(spheres[0].vehicle)
                    collision = ModelCollision.from_native(meshes[0])
                    hit, normal, index, distance = collision.to_bvh().ray_cast(Vector((25, 25, 100)), Vector((0, 0, -1)))
                    self.assertAlmostEqual(hit.z, 0.)
                    self.assertAlmostEqual(distance, 100.)
                    with self.assertRaisesRegex(ValueError, 'missing from the armature'):
                        tag.to_blend_objects(None, SimpleNamespace(pose=SimpleNamespace(bones={})))
                    region = tag.block(tag.tag.root(), 'regions')[0]
                    perm = tag.block(region, 'permutations')[0]
                    bsp = tag.required_field(tag.block(perm, 'bsps')[0], 'bsp').as_struct()
                    tag.required_field(tag.block(bsp, 'edges')[1], 'forward edge').set(1)
                    with self.assertRaisesRegex(ValueError, 'invalid edge loop'):
                        tag.read_collision()
                self.assertEqual((Path(root) / 'test.collision_model').read_bytes(), before)

    def test_native_pca_creates_shape_keys_and_animation(self):
        import bpy
        import struct
        from io_scene_foundry.managed_blam.pca_animation import PCAAnimationTag
        for game in ('halo4', 'halo2a'):
            mesh = bpy.data.meshes.new('native_pca_test')
            mesh.from_pydata([(0., 0., 0.), (1., 1., 0.)], [], [])
            ob = bpy.data.objects.new('native_pca_test', mesh)
            action = None
            try:
                with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                     patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                     patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                     patch.object(utils, 'get_tags_path', return_value=root), \
                     patch.object(utils, 'halo_scale', return_value=1.), \
                     patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                    with PCAAnimationTag('test.pca_animation') as tag:
                        meshes = tag.mesh_data()
                        item = meshes[meshes.add()]
                        tag.required_field(item, 'vertices per shape').set(2)
                        vertices = tag.block(item, 'raw blendshape verts')
                        for vector in ((1., 0., 0.), (0., 1., 0.)):
                            field = tag.required_field(vertices[vertices.add()], 'position')
                            field.set(type(field.value)(*vector))
                        frames = tag.block(tag.tag.root(), 'frame data')
                        for weight in (0., 1.):
                            tag.required_field(frames[frames.add()], 'Coefficients').set(struct.pack('<f', weight))
                    with PCAAnimationTag('test.pca_animation') as tag:
                        bounds = SimpleNamespace(x0=0., x1=10., y0=0., y1=10., z0=0., z1=10.)
                        animation = SimpleNamespace(action_tracks=SimpleNamespace(add=lambda: SimpleNamespace()))
                        with self.assertRaisesRegex(ValueError, 'frame range'):
                            tag.import_animation(ob, 0, bounds, 5, 1, 1, 0, 'bad', animation, 'pca', {})
                        self.assertIsNone(mesh.shape_keys)
                        keys, action, slot = tag.import_animation(ob, 0, bounds, 0, 2, 1, 0, 'test', animation, 'pca', {})
                        self.assertEqual(tuple(keys.key_blocks['pca_1'].data[0].co), (1., 0., 0.))
                        self.assertEqual(tuple(keys.key_blocks['pca_1'].data[1].co), (1., 2., 0.))
                        fcurve, = utils.get_fcurves(action, slot)
                        self.assertEqual([tuple(k.co) for k in fcurve.keyframe_points], [(1., 0.), (2., 1.)])
                        self.assertTrue(all(k.interpolation == 'LINEAR' for k in fcurve.keyframe_points))
            finally:
                bpy.data.objects.remove(ob, do_unlink=True)
                bpy.data.meshes.remove(mesh)
                if action is not None:
                    bpy.data.actions.remove(action)

    def test_native_structure_metadata_markers(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam import structure_meta
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with structure_meta.StructureMetaTag('test.structure_meta') as tag:
                    def add(name):
                        block = tag.block(tag.tag.root(), name)
                        return block[block.add()]
                    def vector(element, name, values):
                        field = tag.required_field(element, name)
                        field.set(type(field.value)(*values))
                    effect = add('Effects markers')
                    tag.required_field(effect, 'marker name').set('fx')
                    vector(effect, 'rotation', (0., 0., 0., 1.))
                    vector(effect, 'position', (1., 2., 3.))
                    tag.set_reference(effect, 'optional attached effect', 'test.effect')
                    air = add('Airprobes')
                    tag.required_field(air, 'airprobe name').set('air')
                    vector(air, 'airprobe position', (4., 5., 6.))
                    cone = add('Light Cones')
                    tag.required_field(cone, 'marker name').set('cone')
                    vector(cone, 'rotation', (0., 0., 0., 1.))
                    for name, number in (('length', 2.), ('width', 3.), ('intensity', 4.)):
                        tag.required_field(cone, name).set(number)
                    vector(cone, 'light color', (1., .2, .4, .6))
                    tag.set_reference(cone, 'light cone tag', 'test.light_cone')
                    tag.set_reference(cone, 'intensity curve', 'test.curve_scalar')
                    palette = add('Object Palette')
                    tag.set_reference(palette, 'definition', 'test.scenery')
                    obj = add('Objects')
                    tag.required_field(obj, 'name').set('instance')
                    vector(obj, 'rotation', (0., 0., 0., 1.))
                    vector(obj, 'translation', (7., 8., 9.))
                    tag.required_field(obj, 'scale').set(2.)
                    tag.required_field(obj, 'palette_index').set(0)
                    tag.required_field(obj, 'variant name').set('variant')
                    tag.required_field(obj, 'flags').set_flag('scripts always run', True)
                before = (Path(root) / 'test.structure_meta').read_bytes()
                collections = []
                def collection(name):
                    result = SimpleNamespace(name=name, objects=SimpleNamespace(link=MagicMock()))
                    collections.append(result)
                    return result
                fake = SimpleNamespace(types=SimpleNamespace(Collection=object), data=SimpleNamespace(
                    collections=SimpleNamespace(new=collection), objects=SimpleNamespace(
                        new=lambda name, data: SimpleNamespace(name=name, nwo=SimpleNamespace(), empty_display_size=1.))))
                parent = SimpleNamespace(children=SimpleNamespace(link=MagicMock()))
                with structure_meta.StructureMetaTag('test.structure_meta') as tag, \
                     patch.object(structure_meta, 'bpy', fake), \
                     patch.object(structure_meta.import_transform, 'scale_factor', return_value=1.), \
                     patch.object(structure_meta.import_transform, 'marker_matrix', side_effect=lambda m: m):
                    markers, instances = tag.to_blender(parent)
                    self.assertEqual([o.name for o in markers], ['fx', 'air', 'cone'])
                    self.assertEqual(tuple(markers[0].matrix_world.translation), (100., 200., 300.))
                    self.assertAlmostEqual(markers[0].matrix_world.to_quaternion().w, 1.)
                    self.assertEqual(markers[2].nwo.marker_light_cone_intensity, 4.)
                    self.assertEqual(markers[2].nwo.marker_light_cone_curve, 'test.curve_scalar')
                    self.assertAlmostEqual(markers[2].nwo.marker_light_cone_color[0], .2)
                    self.assertEqual(instances[0].nwo.marker_game_instance_tag_name, 'test.scenery')
                    self.assertTrue(instances[0].nwo.marker_always_run_scripts)
                    self.assertEqual(instances[0].nwo.marker_game_instance_tag_variant_name, 'variant')
                    self.assertEqual(tuple(instances[0].matrix_world.to_scale()), (2., 2., 2.))
                    self.assertEqual([c.name for c in collections], ['test_effects', 'test_airprobes', 'test_light_cones', 'test_objects'])
                    self.assertEqual(tag.to_blender(parent, objects_only=True)[0], [])
                self.assertEqual((Path(root) / 'test.structure_meta').read_bytes(), before)

    def test_native_structure_seam_blender_mesh(self):
        import bpy
        from mathutils import Matrix, Vector
        from io_scene_foundry.managed_blam import structure_seams
        class SeamTestProperties(bpy.types.PropertyGroup):
            mesh_type: bpy.props.StringProperty()
            region_name: bpy.props.StringProperty()
            seam_back: bpy.props.StringProperty()
        bpy.utils.register_class(SeamTestProperties)
        bpy.types.Mesh.nwo = bpy.props.PointerProperty(type=SeamTestProperties)
        bpy.types.Object.nwo = bpy.props.PointerProperty(type=SeamTestProperties)
        collection = bpy.data.collections.new('native_seam_test')
        objects = []
        try:
            with tempfile.TemporaryDirectory() as root, \
                 patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with structure_seams.StructureSeamsTag('test.structure_seams') as tag:
                    block = tag.block(tag.tag.root(), 'seams')
                    element = block[block.add()]
                    final = tag.required_field(element, 'final').as_struct()
                    points = tag.block(final, 'points')
                    for coords in ((0., 0., 0.), (0., 1., 0.), (1., 0., 0.)):
                        point = points[points.add()]
                        field = tag.required_field(point, 'final point')
                        field.set(type(field.value)(*coords))
                    triangles = tag.block(final, 'triangles')
                    triangle = triangles[triangles.add()]
                    for i in range(3):
                        tag.required_field(triangle, f'final point{i}').set(i)
                    with patch.object(structure_seams, 'apply_props_material'), \
                         patch.object(structure_seams.import_transform, 'mesh_matrix', return_value=Matrix.Identity(4)), \
                         patch.object(structure_seams.import_transform, 'rotation_matrix', return_value=Matrix.Identity(4)):
                        with self.assertRaisesRegex(ValueError, 'metadata'):
                            tag.to_blend_objects([], collection)
                        self.assertEqual(len(collection.objects), 0)
                        objects = tag.to_blend_objects([SimpleNamespace(bsps=['front', 'back'], origin=Vector((0, 0, 100)))], collection)
                        ob, = objects
                        self.assertEqual(ob.nwo.region_name, 'front')
                        self.assertEqual(ob.nwo.seam_back, 'back')
                        self.assertEqual(len(ob.data.polygons), 1)
                        self.assertAlmostEqual(max(v.co.x for v in ob.data.vertices), 100.)
                        self.assertGreater(ob.data.polygons[0].normal.z, .99)
        finally:
            for ob in list(collection.objects):
                mesh = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                bpy.data.meshes.remove(mesh)
            bpy.data.collections.remove(collection)
            del bpy.types.Mesh.nwo
            del bpy.types.Object.nwo
            bpy.utils.unregister_class(SeamTestProperties)

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
