"""Small blam-tags field view for converters retaining the old call shape."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .backend import TagDocument

if TYPE_CHECKING:
    import blam_tags


class NativeElements:
    def __init__(self, values: list[NativeTagStruct]) -> None:
        self._values = values

    @property
    def Count(self) -> int:
        return len(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, index: int) -> NativeTagStruct:
        return self._values[index]


class NativeTagBlock:
    def __init__(self, document: TagDocument, block: blam_tags.TagBlock) -> None:
        self.document = document
        self.block = block

    @property
    def Elements(self) -> NativeElements:
        return NativeElements([
            NativeTagStruct(self.document, element, index)
            for index, element in enumerate(self.block)
        ])

    def AddElement(self) -> NativeTagStruct:
        index = self.block.add()
        self.document.tag_has_changes = True
        return NativeTagStruct(self.document, self.block[index], index)

    def RemoveAllElements(self) -> None:
        if len(self.block):
            self.block.clear()
            self.document.tag_has_changes = True

    def RemoveElement(self, index: int) -> None:
        self.block.delete(index)
        self.document.tag_has_changes = True


class NativeEnumItem:
    def __init__(self, name: str) -> None:
        self.EnumName = name


class NativeGameColor:
    """Small color value matching the interface used by the shader converter."""

    ColorMode = 0

    def __init__(self, red: float, green: float, blue: float,
                 alpha: float = 1.0) -> None:
        self.Red = red
        self.Green = green
        self.Blue = blue
        self.Alpha = alpha

    def ToRgb(self) -> NativeGameColor:
        return self


class NativeFunctionValue:
    """Editable view of a serialized blam-tags mapping function."""

    def __init__(self, document: TagDocument, data_field: blam_tags.TagField) -> None:
        from blam_tags import TagFunctionEditor

        self.document = document
        self.data_field = data_field
        self.editor = TagFunctionEditor(data_field.value)

    def _description(self):
        return self.editor.describe()

    def _commit(self) -> None:
        self.data_field.set(self.editor.to_bytes())
        self.document.tag_has_changes = True

    @property
    def ClampRangeMin(self) -> float:
        return self._description()['clamp'][0]

    @ClampRangeMin.setter
    def ClampRangeMin(self, value: float) -> None:
        self.editor.set_clamp_range(float(value), self.ClampRangeMax)
        self._commit()

    @property
    def ClampRangeMax(self) -> float:
        return self._description()['clamp'][1]

    @ClampRangeMax.setter
    def ClampRangeMax(self, value: float) -> None:
        self.editor.set_clamp_range(self.ClampRangeMin, float(value))
        self._commit()

    @property
    def MasterType(self) -> int:
        return self._description()['master_type']

    @MasterType.setter
    def MasterType(self, value) -> None:
        self.editor.set_master_type(int(getattr(value, 'value', value)))
        self._commit()

    @property
    def ColorGraphType(self) -> int:
        return self._description()['color_type']

    @ColorGraphType.setter
    def ColorGraphType(self, value) -> None:
        self.editor.set_color_graph_type(int(getattr(value, 'value', value)))
        self._commit()

    def GetColor(self, index: int) -> NativeGameColor:
        packed = self._description()['colors'][index]
        return NativeGameColor(
            ((packed >> 16) & 255) / 255,
            ((packed >> 8) & 255) / 255,
            (packed & 255) / 255,
            ((packed >> 24) & 255) / 255,
        )

    def SetColor(self, index: int, color: NativeGameColor) -> None:
        channels = [max(0, min(255, round(component * 255))) for component in
                    (color.Alpha, color.Red, color.Green, color.Blue)]
        packed = ((channels[0] << 24) | (channels[1] << 16) |
                  (channels[2] << 8) | channels[3])
        self.editor.set_color(index, packed)
        self._commit()

    def GetExponent(self, index: int) -> float:
        return self._description()['graphs'][index]['exponent']

    def GetAmplitudeMin(self, index: int) -> float:
        return self._description()['graphs'][index]['min']

    def GetAmplitudeMax(self, index: int) -> float:
        return self._description()['graphs'][index]['max']


class NativeTagField:
    def __init__(self, document: TagDocument, parent: blam_tags.TagStruct,
                 field: blam_tags.TagField) -> None:
        self.document = document
        self.parent = parent
        self.field = field

    @property
    def Elements(self) -> NativeElements:
        block = self.field.as_block()
        if block is not None:
            return NativeTagBlock(self.document, block).Elements
        struct = self.field.as_struct()
        return NativeElements([] if struct is None else [
            NativeTagStruct(self.document, struct, 0)])

    @property
    def Data(self):
        value = self.field.value
        return tuple(value.to_array()) if hasattr(value, 'to_array') else value

    @Data.setter
    def Data(self, value) -> None:
        self.field.set(value)
        self.document.tag_has_changes = True

    @property
    def Value(self):
        function = self.field.as_function() if self.field.is_function_data() else None
        if function is not None:
            return function
        struct = self.field.as_struct()
        if struct is not None:
            data_field = next((candidate for candidate in struct.fields()
                               if candidate.type_name == 'data'), None)
            if data_field is not None:
                try:
                    return NativeFunctionValue(self.document, data_field)
                except ValueError:
                    pass
        options = self.field.options()
        if options is not None and options.current is not None:
            return options.current
        return self.field.value

    @Value.setter
    def Value(self, value) -> None:
        self.field.set(value)
        self.document.tag_has_changes = True

    @property
    def Path(self):
        return TagDocument.reference(self.document, self.parent, self.field.clean_name)

    @Path.setter
    def Path(self, value) -> None:
        TagDocument.set_reference(self.document, self.parent, self.field.clean_name, value)

    @property
    def Items(self) -> list[NativeEnumItem]:
        options = self.field.options()
        return [] if options is None else [NativeEnumItem(name) for name in options.names]

    @property
    def FieldType(self) -> str:
        return str(self.field.field_type)

    def GetStringData(self) -> str:
        value = self.field.value
        return '' if value is None else str(value)

    def SetStringData(self, value: str) -> None:
        current = self.field.value
        if isinstance(current, bool):
            parsed = value.lower() in {'1', 'true', 'yes'}
        elif isinstance(current, int):
            parsed = int(value)
        elif isinstance(current, float):
            parsed = float(value)
        else:
            parsed = value
        self.field.set(parsed)
        self.document.tag_has_changes = True

    def SetValue(self, value) -> None:
        self.Value = value

    def TestBit(self, name: str) -> bool:
        try:
            return bool(self.field.get_flag(name))
        except KeyError:
            alternate = name.replace('\\', '/')
            if alternate == name:
                return False
            try:
                return bool(self.field.get_flag(alternate))
            except KeyError:
                return False


class NativeTagStruct:
    def __init__(self, document: TagDocument, struct: blam_tags.TagStruct,
                 element_index: int = 0) -> None:
        self.document = document
        self.struct = struct
        self.ElementIndex = element_index

    @property
    def Fields(self) -> list[NativeTagField]:
        return [NativeTagField(self.document, self.struct, field)
                for field in self.struct.fields()]

    @staticmethod
    def _segment_name(segment: str) -> tuple[str, int]:
        segment = segment.partition(':')[2] or segment
        name, marker, index = segment.rpartition('[')
        if marker and index.endswith(']'):
            return name, int(index[:-1])
        return segment, 0

    def SelectField(self, path: str):
        current = self.struct
        segments = path.split('/')
        for segment in segments[:-1]:
            name, index = self._segment_name(segment)
            field = current.field(name)
            if field is None:
                return None
            block = field.as_block()
            if block is not None:
                if not 0 <= index < len(block):
                    return None
                current = block[index]
                continue
            struct = field.as_struct()
            if struct is None:
                return None
            current = struct
        name, _index = self._segment_name(segments[-1])
        field = current.field(name)
        if field is None and name == 'animation function':
            field = current.field('function')
        if field is None:
            return None
        block = field.as_block()
        if block is not None:
            return NativeTagBlock(self.document, block)
        return NativeTagField(self.document, current, field)
