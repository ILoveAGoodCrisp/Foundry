import bpy
from .connected_geometry import CompressionBounds, Mesh
from . import Tag

class ParticleModelTag(Tag):
    tag_ext = 'particle_model'

    def _read_fields(self):
        self.block_compression_info = self.tag.SelectField("Struct:render geometry[0]/Block:compression info")
        self.block_per_mesh_temporary = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh temporary")
        self.block_meshes = self.tag.SelectField("Struct:render geometry[0]/Block:meshes")
        
    def to_blend_objects(self, collection: bpy.types.Collection, name: str) -> list[bpy.types.Object]:
        objects = []
        if not self.block_compression_info.Elements.Count:
            raise RuntimeError("Render Model has no compression info. Cannot import render model mesh")
        self.bounds = CompressionBounds(self.block_compression_info.Elements[0])
        render_model = self._GameRenderModel()
        
        for element in self.block_meshes.Elements:
            objects.extend(Mesh(element, self.bounds, does_not_need_parts=True).create(render_model, self.block_per_mesh_temporary, name=name))
            
        for ob in objects:
            collection.objects.link(ob)
            
        return objects