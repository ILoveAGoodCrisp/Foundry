

from .shader_decal import ShaderDecalTag

class DecalSystemTag(ShaderDecalTag):
    tag_ext = 'decal_system'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _read_fields(self):
        self.decal_name = self.tag.SelectField("Block:decals[0]/StringId:decal name")
        self.render_method = self.tag.SelectField("Block:decals[0]/Struct:actual shader?").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.reference = self.render_method.SelectField('reference')
        if self.reference.Path and self.reference.Path == self.tag_path: # prevent recursion issues
            self.reference.Path = None
        self.definition = self.render_method.SelectField('definition')