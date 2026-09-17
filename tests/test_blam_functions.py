"""Native function decoding: parameters, colors, ranged curves and malformed data."""
import struct
import unittest
import blam_tags


def function_blob(kind, compacts=(), flags=0, colors=()):
    header = bytearray(32)
    header[0:3] = bytes((kind, flags, len(colors)))
    struct.pack_into('<ff', header, 4, 0.25, 0.75)
    if colors:
        slots = {1: [0], 2: [0, 3], 3: [0, 1, 3], 4: [0, 1, 2, 3]}[len(colors)]
        for slot, color in zip(slots, colors):
            struct.pack_into('<I', header, 4 + slot * 4, color)
    struct.pack_into('<i', header, 28, sum(map(len, compacts)))
    return bytes(header) + b''.join(compacts)


class FunctionBindingTests(unittest.TestCase):
    def test_identity_curve_without_editor_trailer(self):
        for flags in (0, 1):
            blob = function_blob(0, flags=flags)
            editor = blam_tags.TagFunctionEditor(blob)
            description = editor.describe()
            self.assertEqual(description['master_type'], 1)
            for graph in description['graphs']:
                self.assertEqual(graph['segments'], [(0, False, [(0., 0.), (1., 1.)])])
            for x in (0., .25, .5, 1.):
                self.assertAlmostEqual(editor.evaluate_shape(x, 0.), x)
            self.assertEqual(editor.to_bytes(), blob)

    def test_basic_colors_evaluation_and_invalid_data(self):
        blob = function_blob(1)
        editor = blam_tags.TagFunctionEditor(blob)
        self.assertEqual(editor.describe()['master_type'], 0)
        self.assertAlmostEqual(editor.evaluate(0.8, 0.), 0.25)
        self.assertEqual(editor.to_bytes(), blob)
        colors = (0xff112233, 0x80445566)
        self.assertEqual(blam_tags.TagFunctionEditor(function_blob(1, flags=1, colors=colors)).describe()['colors'], list(colors))
        with self.assertRaises(ValueError):
            blam_tags.TagFunctionEditor(b'bad')

    def test_periodic_exponent_transition_and_ranged_graphs(self):
        first = struct.pack('<Iffff', 2, 3., 0.5, 0., 1.)
        second = struct.pack('<Iffff', 4, 7., 0.25, 0.2, 0.8)
        blob = function_blob(3, (first, second), flags=1)
        editor = blam_tags.TagFunctionEditor(blob)
        data = editor.describe()
        self.assertTrue(data['is_ranged'])
        self.assertEqual([g['function'] for g in data['graphs']], ['cosine', 'diagonal wave'])
        self.assertEqual([g['frequency'] for g in data['graphs']], [3., 7.])
        self.assertEqual(editor.to_bytes(), blob)
        exponent = blam_tags.TagFunctionEditor(function_blob(9, (struct.pack('<fff', 0., 1., 2.),))).describe()
        self.assertEqual(exponent['graphs'][0]['exponent'], 2.)
        transition = blam_tags.TagFunctionEditor(function_blob(2, (struct.pack('<Iff', 1, 0., 1.),))).describe()
        self.assertEqual(transition['graphs'][0]['function'], 'early')

    def test_ranged_curve_graphs_have_distinct_points(self):
        # One linear segment per graph, followed by the two 148-byte editor trailers.
        compact = struct.pack('<IIfff', 1, 4, 3.4028234663852886e38, 1., 0.)
        trailers = []
        for end_y in (1., 0.5):
            editor = bytearray(148)
            struct.pack_into('<I', editor, 0, 1)
            editor[4] = 4  # Linear segment.
            struct.pack_into('<ffff', editor, 8, 0., 0., 1., end_y)
            trailers.append(bytes(editor))
        second = struct.pack('<IIfff', 1, 4, 3.4028234663852886e38, 0.5, 0.)
        blob = function_blob(8, (compact, second), flags=1) + b''.join(trailers)
        editor = blam_tags.TagFunctionEditor(blob)
        data = editor.describe()
        self.assertEqual(data['graphs'][0]['segments'][0][2][-1], (1., 1.))
        self.assertEqual(data['graphs'][1]['segments'][0][2][-1], (1., 0.5))
        self.assertAlmostEqual(editor.evaluate_shape(0.5, 0.), 0.5)
        self.assertAlmostEqual(editor.evaluate_shape(0.5, 1.), 0.25)


if __name__ == '__main__':
    unittest.main()
