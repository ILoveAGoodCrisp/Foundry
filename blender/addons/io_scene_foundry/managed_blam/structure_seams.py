from pathlib import Path
from ..managed_blam import Tag
import os
from .. import utils

class StructureSeamsTag(Tag):
    tag_ext = 'structure_seams'
    
    def to_blend_objects(self):
        pass