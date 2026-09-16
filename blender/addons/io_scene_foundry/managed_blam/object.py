"""Blender object metadata backed by blam-tags."""
from ..tags.blender import BlenderTag
from ..tags.object import ObjectDocument


class ObjectTag(BlenderTag, ObjectDocument):
    def __init__(self, path='', *, tag_must_exist=False, **kwargs):
        super().__init__(path, tag_must_exist=tag_must_exist, **kwargs)

    def functions_to_blender(self):
        from .connected_material import game_functions
        candidates = [e for e in self.block(self.object_struct(), 'functions')
                      if self.value(e, 'export name').strip()
                      and self.value(e, 'export name') != self.value(e, 'import name')
                      and self.value(e, 'export name') not in game_functions]
        if not candidates:
            return {}
        # Custom function editors have no Python binding yet.
        from .object_legacy import LegacyObjectTag
        with LegacyObjectTag(path=self.system_path, tag_must_exist=True) as legacy:
            return legacy.functions_to_blender()

    def attachments_to_blender(self, armature, markers, parent_collection):
        records = [record for record in self.get_attachments()
                   if record.reference is not None
                   and record.reference.Extension in {'light', 'cheap_light'}
                   and self.path_exists(record.reference)]
        if not records:
            return []

        import bpy
        from math import radians
        from mathutils import Matrix
        from types import SimpleNamespace
        from .. import utils
        from . import import_transform
        from .light import LightTag
        from .cheap_light import CheapLightTag

        collection = bpy.data.collections.new(f'{self.tag_path.ShortName}_attachments')
        collection.nwo.type = 'exclude'
        parent_collection.children.link(collection)
        attachments = []
        for record in records:
            attachment = SimpleNamespace(
                function_names={name for name in (record.primary_scale, record.secondary_scale) if name},
                objects=[], armature=armature)
            # Only the referenced light still needs a legacy custom function editor.
            cls = LightTag if record.reference.Extension == 'light' else CheapLightTag
            with cls(path=record.reference, tag_must_exist=True) as light:
                data = light.to_blender(record.primary_scale, record.secondary_scale, attachment)
            if data is None:
                continue
            for marker in markers:
                if marker.nwo.marker_model_group != record.marker:
                    continue
                ob = bpy.data.objects.new(data.name, data)
                collection.objects.link(ob)
                if ob.type == 'LIGHT':
                    ob.matrix_world = utils.halo_transforms(ob) @ Matrix.Rotation(radians(-90.0), 4, 'X')
                    ob.scale *= (1 / 0.03048) * import_transform.scale_factor()
                ob.parent = marker
                ob.parent_type = 'OBJECT'
                attachment.objects.append(ob)
            attachments.append(attachment)
        if not attachments:
            bpy.data.collections.remove(collection)
        return attachments
