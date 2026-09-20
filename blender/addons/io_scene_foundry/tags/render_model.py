"""Native render-model metadata."""

from .backend import TagDocument
from .blender import BlenderTag


class RenderModelMetadataTag(BlenderTag, TagDocument):
    tag_ext = 'render_model'

    def get_nodes(self):
        return [self.value(element, 'name')
                for element in self.block(self.tag.root(), 'nodes')]

    def get_regions(self):
        return [self.value(element, 'name')
                for element in self.block(self.tag.root(), 'regions')]

    def get_permutations(self, region=''):
        regions = self.block(self.tag.root(), 'regions')
        names = []
        for element in regions:
            if region and self.value(element, 'name') != region:
                continue
            names.extend(self.value(permutation, 'name')
                         for permutation in self.block(element, 'permutations'))
            if region:
                break
        return list(dict.fromkeys(names))

    def get_markers(self):
        return [self.value(element, 'name')
                for element in self.block(self.tag.root(), 'marker groups')]

    def set_structure_meta_ref(self, meta_path):
        if not self.corinth:
            raise ValueError(
                'Structure metadata references only exist in H4/H2AMP render models')
        if not self.path_exists(self.reference_from_path(meta_path)):
            raise FileNotFoundError(meta_path)
        self.set_reference(self.tag.root(), 'structure meta data', meta_path)

    def first_render_method(self):
        materials = self.block(self.tag.root(), 'materials')
        if not len(materials):
            return None
        return self.reference(materials[0], 'render method')

    def insert_empty_region_perms(self, empty_region_perms: dict[str, set]):
        print("\nAdding Empty Region Permutations")
        regions = self.block(self.tag.root(), 'regions')
        for region_element in regions:
            region = self.value(region_element, 'name')
            permutations = empty_region_perms.get(region)
            if permutations is None:
                continue
            block = self.block(region_element, 'permutations')
            existing = {self.value(element, 'name') for element in block}
            print(f"\n--- Adding empty permutations to existing region {region}")
            for permutation in sorted(permutations.difference(existing)):
                element = block[block.add()]
                self.required_field(element, 'name').set(permutation)
                self.required_field(element, 'mesh index').set(-1)
                print(f"\tAdded permutation {permutation}")
                self.tag_has_changes = True
            empty_region_perms.pop(region)

        for region, permutations in empty_region_perms.items():
            region_element = regions[regions.add()]
            self.required_field(region_element, 'name').set(region)
            print(f"\n--- Created new empty region {region}")
            block = self.block(region_element, 'permutations')
            for permutation in sorted(permutations):
                element = block[block.add()]
                self.required_field(element, 'name').set(permutation)
                self.required_field(element, 'mesh index').set(-1)
                print(f"\tAdded permutation {permutation}")
            self.tag_has_changes = True
