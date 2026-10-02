"""Blender-facing object metadata wrapper."""
from collections import defaultdict

from .blender import BlenderTag
from .object import ObjectDocument


class ObjectTag(BlenderTag, ObjectDocument):
    def __init__(self, path='', *, tag_must_exist=False, **kwargs):
        super().__init__(path, tag_must_exist=tag_must_exist, **kwargs)

    def functions_to_blender(self):
        from .connected_material import Function, game_functions
        if self.game == 'halo1':
            # Halo 1 stores four positional object functions rather than the
            # named mapping functions introduced in Halo 2. Its current shader
            # converter does not consume these mappings, but retain their
            # authored input dependencies for Blender object properties.
            object_struct = self.object_struct()
            result = {}
            for index, element in enumerate(self.block(object_struct, 'functions')):
                usage = str(self.value(element, 'usage')).strip()
                if not usage:
                    continue
                input_field = object_struct.field(f'{chr(97 + index)} in') if index < 4 else None
                input_name = '' if input_field is None else str(input_field.value).strip()
                result[usage] = ([] if not input_name or input_name == 'none'
                                 else [input_name])
            return result
        candidates = [e for e in self.block(self.object_struct(), 'functions')
                      if self.value(e, 'export name').strip()
                      and self.value(e, 'export name') != self.value(e, 'import name')
                      and self.value(e, 'export name') not in game_functions]
        if not candidates:
            return {}
        decoded = {}
        try:
            for element in candidates:
                function = Function()
                function.from_native_object(self, element)
                decoded[self.value(element, 'export name')] = function
        except ValueError as exc:
            raise ValueError(
                f'Cannot decode native object functions in {self.system_path}: {exc}') from exc
        for name, function in decoded.items():
            function.make_node_group(name)
        dependencies = defaultdict(list)
        for name, function in decoded.items():
            function.to_blend_nodes(name=name)
            if function.input.strip():
                dependencies[name].append(function.input)
            for dependency in (function.range, function.scale_by,
                               function.turn_off_with):
                if dependency.strip():
                    dependencies[name].append(
                        decoded[dependency].input if dependency in decoded else dependency)
        return dependencies

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
        from .. import import_transform
        from .light import LightTag
        from .cheap_light import CheapLightTag

        collection = bpy.data.collections.new(f'{self.tag_path.ShortName}_attachments')
        collection.nwo.type = 'exclude'
        parent_collection.children.link(collection)
        attachments = []
        for record in records:
            matching_markers = [marker for marker in markers
                                if marker.nwo.marker_model_group.strip().casefold()
                                == record.marker.strip().casefold()]
            if not matching_markers:
                utils.print_warning(
                    f'{self.tag_path.ShortName}: skipped {record.reference.RelativePathWithExtension}: '
                    f'no imported marker matched attachment group {record.marker!r}')
                continue
            attachment = SimpleNamespace(
                function_names={name for name in
                                (record.primary_scale, record.secondary_scale) if name},
                objects=[], armature=armature)
            cls = LightTag if record.reference.Extension == 'light' else CheapLightTag
            with cls(path=record.reference, tag_must_exist=True) as light:
                data = light.to_blender(
                    record.primary_scale, record.secondary_scale, attachment)
            if data is None:
                continue
            for marker in matching_markers:
                ob = bpy.data.objects.new(data.name, data)
                collection.objects.link(ob)
                ob.parent = marker
                ob.parent_type = 'OBJECT'
                if ob.type == 'LIGHT':
                    # Halo lights emit along marker +X; Blender lights emit
                    # along local -Z. This is a marker-local transform, so do
                    # not apply the Blender-to-Halo world rotation again.
                    local_rotation = Matrix.Rotation(radians(-90.0), 4, 'Y')
                    if utils.get_scene_props().maintain_marker_axis:
                        local_rotation = import_transform.rotation_matrix() @ local_rotation
                    ob.matrix_basis = utils.halo_transforms_matrix(local_rotation, rotation=0)
                    ob.scale *= (1 / 0.03048) * import_transform.scale_factor()
                attachment.objects.append(ob)
            attachments.append(attachment)
        if not attachments:
            bpy.data.collections.remove(collection)
        return attachments
