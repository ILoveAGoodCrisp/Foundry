"""Run with ``python -B -m unittest blender/test_animation_copies.py``."""
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).parent / 'addons/io_scene_foundry/tags/animation_names.py'
spec = importlib.util.spec_from_file_location('animation_names', path)
animation_names = importlib.util.module_from_spec(spec)
spec.loader.exec_module(animation_names)


class AnimationCopyInferenceTests(unittest.TestCase):
    def test_complete_weapon_class_copy(self):
        paths = {
            'combat:rifle:idle': [
                'combat:rifle:any:any:idle', 'combat:pistol:any:any:idle'],
            'combat:rifle:fire': [
                'combat:rifle:any:any:fire', 'combat:pistol:any:any:fire'],
        }
        copies = animation_names.copies_from_paths(paths)
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0][:2], (
            'combat rifle any any', 'combat pistol any any'))
        self.assertEqual(copies[0][2], frozenset({
            ('combat:rifle:idle', 'combat:pistol:idle'),
            ('combat:rifle:fire', 'combat:pistol:fire'),
        }))

    def test_incomplete_source_subtree_stays_as_renames(self):
        paths = {
            'combat:rifle:idle': [
                'combat:rifle:any:any:idle', 'combat:pistol:any:any:idle'],
            'combat:rifle:fire': [
                'combat:rifle:any:any:fire', 'combat:pistol:any:any:fire'],
            'combat:rifle:reload': ['combat:rifle:any:any:reload'],
        }
        self.assertEqual(animation_names.copies_from_paths(paths), [])
        self.assertEqual(len(animation_names.renames_from_paths(paths)), 2)

    def test_conflicting_destination_stays_as_renames(self):
        paths = {
            'combat:rifle:idle': [
                'combat:rifle:any:any:idle', 'combat:pistol:any:any:idle'],
            'combat:rifle:fire': [
                'combat:rifle:any:any:fire', 'combat:pistol:any:any:fire'],
            'combat:pistol:fire': ['combat:pistol:any:any:fire'],
        }
        self.assertEqual(animation_names.copies_from_paths(paths), [])

    def test_weapon_type_and_set_copies(self):
        for source, destination, expected_source, expected_destination in (
                ('combat:rifle:assault:any', 'combat:rifle:smg:any',
                 'combat rifle assault any', 'combat rifle smg any'),
                ('combat:rifle:assault:standard',
                 'combat:rifle:assault:alternate',
                 'combat rifle assault standard',
                 'combat rifle assault alternate')):
            with self.subTest(destination=destination):
                paths = {
                    f'{source}:{state}': [f'{source}:{state}',
                                           f'{destination}:{state}']
                    for state in ('idle', 'fire')
                }
                copies = animation_names.copies_from_paths(paths)
                self.assertEqual(len(copies), 1)
                self.assertEqual(copies[0][:2], (
                    expected_source, expected_destination))

    def test_copy_requires_noncanonical_source_paths(self):
        paths = {
            'combat:rifle:idle': [
                'combat:rifle:any:any:idle', 'combat:pistol:any:any:idle'],
            'combat:rifle:fire': [
                'combat:rifle:any:any:fire', 'combat:pistol:any:any:fire'],
            'combat:rifle:ready': [
                'combat:rifle:any:any:idle:2:combat:ready',
                'combat:pistol:any:any:idle:2:combat:ready'],
        }
        # The transition is an alias in the source branch and must also be
        # represented at the destination for a class copy to be complete.
        self.assertEqual(len(animation_names.copies_from_paths(paths)), 1)
        paths['combat:rifle:ready'].pop()
        self.assertEqual(animation_names.copies_from_paths(paths), [])


if __name__ == '__main__':
    unittest.main()
