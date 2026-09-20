"""Native particle tag entry points."""
from .backend import TagDocument
from .blender import BlenderTag


class ParticleEmitterCustomPointsTag(BlenderTag, TagDocument):
    tag_ext = 'particle_emitter_custom_points'

