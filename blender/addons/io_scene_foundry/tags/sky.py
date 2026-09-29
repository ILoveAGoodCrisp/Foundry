"""Sky tag references for the legacy games."""
from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, cos, sin, sqrt
from pathlib import Path

from .backend import TagDocument, TagReference


MAX_SKY_LIGHTS = 8


@dataclass(frozen=True)
class SkyLightRecord:
    direction: tuple[float, float, float]  # Towards the sun, in Halo coordinates.
    color: tuple[float, float, float]
    power: float


def direction_from_angles(angles) -> tuple[float, float, float]:
    yaw, pitch = map(float, angles)
    return (cos(pitch) * cos(yaw), cos(pitch) * sin(yaw), sin(pitch))


def angles_from_direction(direction) -> tuple[float, float]:
    x, y, z = map(float, direction)
    length = sqrt(x * x + y * y + z * z)
    if length == 0:
        raise ValueError('Sky light direction must be nonzero')
    return atan2(y, x), asin(max(-1.0, min(1.0, z / length)))


class SkyDocument(TagDocument):
    tag_ext = 'sky'

    def _components(self, struct, name):
        value = self.value(struct, name)
        if hasattr(value, 'to_array'):
            return tuple(map(float, value.to_array()))
        if name == 'direction':
            return float(value.yaw), float(value.pitch)
        return float(value.red), float(value.green), float(value.blue)

    def _set_components(self, struct, name, values):
        field = self.required_field(struct, name)
        field.set(type(field.value)(*values))

    def sky_lights(self) -> tuple[SkyLightRecord, ...]:
        lights = []
        for light in self.block(self.tag.root(), 'lights'):
            if self.game == 'halo1':
                radiosity = self.required_field(light, 'radiosity').as_struct()
            else:
                radiosity_block = self.block(light, 'radiosity')
                radiosity = radiosity_block[0] if radiosity_block else None
            if self.game == 'halo2':
                vector = self._components(light, 'direction vector')
                direction = (vector if sum(v * v for v in vector) > 1e-12
                             else direction_from_angles(self._components(light, 'direction')))
            else:
                direction = direction_from_angles(self._components(radiosity, 'direction'))
            color = (self._components(radiosity, 'color')
                     if radiosity is not None else (1.0, 1.0, 1.0))
            power = float(self.value(radiosity, 'power')) if radiosity is not None else 1.0
            lights.append(SkyLightRecord(direction, color, power))
        return tuple(lights)

    def set_sky_lights(self, lights: list[SkyLightRecord]) -> None:
        if len(lights) > MAX_SKY_LIGHTS:
            raise ValueError(f'Sky tags support at most {MAX_SKY_LIGHTS} lights; found {len(lights)}')
        block = self.block(self.tag.root(), 'lights')
        while len(block) > len(lights):
            block.delete(len(block) - 1)
            self.tag_has_changes = True
        for index, light_data in enumerate(lights):
            new_light = index >= len(block)
            if new_light:
                block.add()
                self.tag_has_changes = True
            light = block[index]
            angles = angles_from_direction(light_data.direction)
            if self.game == 'halo1':
                radiosity = self.required_field(light, 'radiosity').as_struct()
                self._set_components(radiosity, 'direction', angles)
            else:
                self._set_components(light, 'direction vector', light_data.direction)
                self._set_components(light, 'direction', angles)
                radiosity_block = self.block(light, 'radiosity')
                new_radiosity = not len(radiosity_block)
                if new_radiosity:
                    radiosity_block.add()
                radiosity = radiosity_block[0]
            self._set_components(radiosity, 'color', light_data.color)
            self.required_field(radiosity, 'power').set(float(light_data.power))
            if new_light or (self.game == 'halo2' and new_radiosity):
                self.required_field(radiosity, 'flags').set_flag('affects exteriors', True)
            self.tag_has_changes = True

    def _reference_filename(self, field_name: str,
                            optional_tag_root: str | Path | None = None) -> str:
        reference = self.reference(self.tag.root(), field_name)
        if reference is None:
            return ''

        root = Path(optional_tag_root) if optional_tag_root is not None else reference.root
        resolved = TagReference(root, reference.RelativePath, reference.Extension)
        if self.game == 'halo1' and field_name == 'model' and reference.Extension == 'model':
            model_path = Path(resolved.Filename)
            gbxmodel_path = model_path.with_suffix('.gbxmodel')
            if not model_path.is_file() and gbxmodel_path.is_file():
                resolved = TagReference(root, reference.RelativePath, 'gbxmodel')
        return resolved.Filename

    def get_model_path(self, optional_tag_root: str | Path | None = None) -> str:
        field_name = 'model' if self.game == 'halo1' else 'render model'
        return self._reference_filename(field_name, optional_tag_root)

    def get_animation_path(self, optional_tag_root: str | Path | None = None) -> str:
        return self._reference_filename('animation graph', optional_tag_root)

