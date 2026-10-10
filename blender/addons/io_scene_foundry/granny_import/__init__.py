"""Portable GR2 decoding, independent of Blender and the Granny runtime."""

from .container import UnsupportedGrannyFormat
from .reader import GrannyReader

__all__ = ('GrannyReader', 'UnsupportedGrannyFormat')
