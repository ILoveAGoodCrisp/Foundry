"""Blender-facing object metadata wrapper."""
from .blender import BlenderTag
from .object import ObjectDocument


class ObjectTag(BlenderTag, ObjectDocument):
    def __init__(self, path='', *, tag_must_exist=False, **kwargs):
        super().__init__(path, tag_must_exist=tag_must_exist, **kwargs)

    def functions_to_blender(self):
        from .connected_material import Function, game_functions
        from .function_driver import Halo1Function, ObjectFunctions
        if self.game == 'halo1':
            object_struct = self.object_struct()
            inputs = self.get_halo1_function_inputs()
            inputs = {name: source.replace(' ', '_') if source.replace(' ', '_') in game_functions
                      else source for name, source in inputs.items()}
            result = ObjectFunctions()
            for index, element in enumerate(self.block(object_struct, 'functions')):
                if index >= 4:
                    break
                name = f'{chr(97 + index)} out'
                function = Halo1Function.read(self, element, inputs)
                result.decoded[name] = function
                result[name] = []
                usage = str(self.value(element, 'usage')).strip()
                if usage and usage != name:
                    result.decoded[usage] = function
                    result[usage] = []
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
        dependencies = ObjectFunctions(decoded=decoded)
        for name, function in decoded.items():
            if self.game in {'reach', 'halo3', 'halo3odst'}:
                # The importer evaluates decoded functions on each object's
                # properties. A shared shader helper must read that value;
                # baking a particular object's curve into a globally named
                # group makes other objects with the same export name inherit it.
                tree = function.make_node_group(name)
                tree.nodes.clear()
                output = tree.nodes.new('NodeGroupOutput'); output.location = (240, 0)
                attribute = tree.nodes.new('ShaderNodeAttribute'); attribute.location = (0, 0)
                attribute.attribute_type = 'INSTANCER'; attribute.attribute_name = name
                tree.links.new(attribute.outputs['Fac'], output.inputs[0])
            else:
                function.to_blend_nodes(name=name)
            dependencies[name] = []
            if function.input.strip():
                dependencies[name].append(function.input)
            for dependency in (function.range, function.scale_by,
                               function.turn_off_with):
                if dependency.strip():
                    dependencies[name].append(
                        dependency if self.game == 'halo2' or dependency not in decoded
                        else decoded[dependency].input)
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
                    local_rotation = import_transform.rotation_matrix() @ local_rotation
                    ob.matrix_basis = utils.halo_transforms_matrix(local_rotation, rotation=0)
                    ob.scale *= (1 / 0.03048) * import_transform.scale_factor()
                attachment.objects.append(ob)
            attachments.append(attachment)
        if not attachments:
            bpy.data.collections.remove(collection)
        return attachments
