

from .material import MaterialTag
from .shader_decal import ShaderDecalTag

class DecalSystemTag(ShaderDecalTag):
    tag_ext = 'decal_system'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _read_fields(self):
        self.render_method = self.tag.SelectField("Block:decals[0]/Struct:actual shader?").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference')
        if self.reference.Path and self.reference.Path == self.tag_path: # prevent recursion issues
            self.reference.Path = None
        self.definition = self.render_method.SelectField('definition')
        
    def reread_fields(self, element_index: int):
        self.render_method = self.tag.SelectField(f"Block:decals[{element_index}]/Struct:actual shader?").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference')
        self.definition = self.render_method.SelectField('definition')
        
class DecalSystemCorinthTag(MaterialTag):
    tag_ext = 'decal_system'
    group_supported = True
    
    default_parameters = None
    shader_parameters = None
    material_parameters = None
    
    global_material_shader = None
    last_group_node = None
    last_material_shader = None
    group_node = None
    
    material_shaders = {}
    
    def _read_fields(self):
        self.render_method = self.tag.SelectField(f"Block:decals[0]/Struct:actual material?").Elements[0]
        self.block_parameters = self.render_method.SelectField("material parameters")
        self.reference_material_shader = self.render_method.SelectField('material shader')
        self.alpha_blend_mode = self.render_method.SelectField('CharEnum:alpha blend mode')
        
    def reread_fields(self, element_index: int):
        self.render_method = self.tag.SelectField(f"Block:decals[0]/Struct:actual material?").Elements[0]
        self.block_parameters = self.render_method.SelectField("material parameters")
        self.reference_material_shader = self.render_method.SelectField('material shader')
        self.alpha_blend_mode = self.render_method.SelectField('CharEnum:alpha blend mode')