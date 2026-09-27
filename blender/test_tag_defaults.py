"""Native tag creation regression tests; run with ordinary Python or Blender.

Tests the bundled wheel, without an installed addon or editing kit.
"""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from zipfile import ZipFile

addon = Path(__file__).parent / 'addons/io_scene_foundry'
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
with ZipFile(next((addon / 'wheels').glob('blam_tags-*.whl'))) as archive:
    archive.extractall(wheels.name)
sys.path.insert(0, wheels.name)
import blam_tags


class TagDefaultsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        fields = []
        self.indices = []
        for prefix in ('', 'custom_'):
            for width in ('char', 'short', 'long'):
                kind = f'{prefix}{width}_block_index'
                self.indices.append(kind)
                field = dict(type=kind, name=kind)
                if not prefix:
                    field['definition'] = 'items'
                elif width == 'long':
                    field['definition'] = 'test_custom_search'
                fields.append(field)
        for width in ('char', 'short', 'long'):
            fields.append(dict(type=f'{width}_enum', name=f'{width}_enum', definition='choices'))
        fields.extend((dict(type='long_flags', name='flags', definition='choices'),
                       dict(type='long_integer', name='integer'), dict(type='terminator')))
        schema = dict(tag='test', version=1, flags=0, block='root',
                      blocks={'root': dict(max_count=1, struct='root'),
                              'items': dict(max_count=100, struct='leaf')},
                      arrays={'pair': dict(count=2, struct='leaf')},
                      enums_flags={'choices': {'options': ['first', 'second']}},
                      structs={
                          'leaf': dict(guid='11' * 16, size=29, fields=fields),
                          'root': dict(guid='22' * 16, size=99, fields=[
                              dict(type='struct', name='nested', definition='leaf'),
                              dict(type='array', name='array', definition='pair'),
                              dict(type='block', name='items', definition='items'),
                              dict(type='terminator')])})
        path = Path(directory.name) / 'test.json'
        path.write_text(json.dumps(schema))
        self.tag = blam_tags.TagFile.new(path)

    def assert_defaults(self, element):
        for name in self.indices:
            self.assertEqual(element.field(name).value, -1, name)
        for width in ('char', 'short', 'long'):
            self.assertEqual(element.field(f'{width}_enum').options().current, 0)
        self.assertEqual(element.field('flags').value, [])
        self.assertEqual(element.field('integer').value, 0)

    def test_root_nested_struct_and_array_defaults(self):
        root = self.tag.root()
        self.assert_defaults(root.field('nested').as_struct())
        for element in root.field('array').as_array():
            self.assert_defaults(element)

    def test_add_insert_duplicate_and_roundtrip_preserve_choices(self):
        block = self.tag.root().field('items').as_block()
        block.add()
        self.assert_defaults(block[0])
        block[0].field('short_block_index').set(0)
        block[0].field('short_enum').set(1)
        block.insert(0)
        self.assert_defaults(block[0])
        block.duplicate(1)
        loaded = blam_tags.TagFile.read_from_bytes(self.tag.write_to_bytes())
        block = loaded.root().field('items').as_block()
        self.assert_defaults(block[0])
        for i in (1, 2):
            self.assertEqual(block[i].field('short_block_index').value, 0)
            self.assertEqual(block[i].field('short_enum').options().current, 1)

    def test_custom_search_definitions_reference_a_real_table_entry(self):
        data = self.tag.write_to_bytes()
        def chunk(name):
            start = data.index(name[::-1].encode())
            size = struct.unpack_from('<I', data, start + 8)[0]
            return data[start + 12:start + 12 + size]
        strings = chunk('str*')
        def string(offset):
            return strings[offset:strings.index(b'\0', offset)].decode()
        searches = [string(offset) for offset, in struct.iter_unpack('<I', chunk('csbn'))]
        self.assertEqual(set(searches), {'void', 'test_custom_search'})
        types = [string(name) for name, _, _ in struct.iter_unpack('<III', chunk('tgft'))]
        for _, field_type, definition in struct.iter_unpack('<III', chunk('gras')):
            if types[field_type].startswith('custom ') and types[field_type].endswith('block index'):
                self.assertLess(definition, len(searches))

    def test_reach_animation_graph_null_gait_and_scenario_enum(self):
        schemas = addon / 'tags/definitions/haloreach_mcc'
        graph = blam_tags.TagFile.new(schemas / 'model_animation_graph.json')
        content = graph.root().field('content').as_struct()
        self.assertEqual(content.field('default gait group').value, -1)
        scenario = blam_tags.TagFile.new(schemas / 'scenario.json')
        self.assertEqual(scenario.root().field('type').options().current, 0)
        starts = scenario.root().field('player starting locations').as_block()
        starts.add()
        self.assertEqual(starts[0].field('editor folder').value, -1)


if __name__ == '__main__':
    unittest.main(argv=[__file__])
