

from math import radians
from typing import cast

from mathutils import Color, Matrix, Vector

from ..tools.property_apply import apply_props_material

from ..constants import WU_SCALAR

from ..props.object import NWO_ObjectPropertiesGroup
from ..props.light import NWO_LightPropertiesGroup
from ..managed_blam.Tags import TagFieldBlockElement
from ..managed_blam import Tag
from .. import utils
import bpy

class LightmapperGlobalsTag(Tag):
    tag_ext = 'lightmapper_globals'
        
    def _read_fields(self):
        self.global_flags = self.tag.SelectField("Struct:Global lightmapper settings[0]/Flags:Global flags")
        self.local_flags = self.tag.SelectField("Struct:Local lightmapper settings[0]/Flags:Local flags")
        self.aabb_min = self.tag.SelectField("Struct:Global lightmapper settings[0]/RealVector3d:Indirect Restrict AABB Min")
        self.aabb_max = self.tag.SelectField("Struct:Global lightmapper settings[0]/RealVector3d:Indirect Restrict AABB Max")
        self.mode = self.tag.SelectField("Struct:Global lightmapper settings[0]/LongEnum:Mode")
        
