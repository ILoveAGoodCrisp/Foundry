"""Blender-facing sky tag wrapper."""

import bpy

from .. import import_transform
from .blender import BlenderTag
from .sky import SkyDocument


class SkyTag(BlenderTag, SkyDocument):
    tag_ext = 'sky'

    def lights_to_blender(self, collection):
        objects = []
        for index, record in enumerate(self.sky_lights()):
            data = bpy.data.lights.new(f'{self.tag_path.ShortName}_sun_{index + 1}', 'SUN')
            data.color = record.color
            data.energy = record.power
            obj = bpy.data.objects.new(data.name, data)
            direction = import_transform.direction(record.direction, self.scene_nwo).normalized()
            obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
            collection.objects.link(obj)
            objects.append(obj)
        return objects

