

from pathlib import Path
from typing import cast
import bpy
from mathutils import Euler, Matrix, Vector

from .backend import TagDocument
from .blender import BlenderTag
from ..tags.metadata import rgba
from .. import utils
from .. import import_transform

class StructureMetaTag(BlenderTag, TagDocument):
    tag_ext = 'structure_meta'
    
    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def _reference_path(self, element, name):
        reference = self.reference(element, name)
        return reference.RelativePathWithExtension if reference else ''

    def _rotation(self, element):
        return utils.ijkw_to_wxyz(self.value(element, 'rotation').to_array())
        
    def _import_effects(self, parent_collection: bpy.types.Collection = None):
        objects = []
        for element in self.block(self.tag.root(), 'Effects markers'):
            name = self.value(element, 'marker name')
            rotation = self._rotation(element)
            position = Vector(self.value(element, 'position').to_array()) * 100
            effect = self._reference_path(element, 'optional attached effect')
            
            if not effect:
                continue
            
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "ARROWS"
            ob.empty_display_size *= (1 / 0.03048) * import_transform.scale_factor()
            ob.matrix_world = import_transform.marker_matrix(Matrix.LocRotScale(position, rotation, Vector.Fill(3, 1)))
            ob.nwo.marker_type = '_connected_geometry_marker_type_envfx'
            ob.nwo.marker_looping_effect = effect
            objects.append(ob)
        
        if objects:
            collection = cast(bpy.types.Collection, bpy.data.collections.new(f"{self.tag_path.ShortName}_effects"))
            if parent_collection is None:
                bpy.context.scene.collection.children.link(collection)
            else:
                parent_collection.children.link(collection)
                
            for ob in objects:
                collection.objects.link(ob)
            
        return objects
    
    def _import_airprobes(self, parent_collection: bpy.types.Collection = None):
        objects = []
        for element in self.block(self.tag.root(), 'Airprobes'):
            position = Vector(self.value(element, 'airprobe position').to_array()) * 100
            name = self.value(element, 'airprobe name')
            
            if not name:
                continue
            
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "SPHERE"
            ob.empty_display_size *= (1 / 0.03048) * import_transform.scale_factor()
            ob.matrix_world = import_transform.marker_matrix(Matrix.LocRotScale(position, Euler(), Vector.Fill(3, 1)))
            ob.nwo.marker_type = '_connected_geometry_marker_type_airprobe'
            objects.append(ob)
        
        if objects:
            collection = cast(bpy.types.Collection, bpy.data.collections.new(f"{self.tag_path.ShortName}_airprobes"))
            if parent_collection is None:
                bpy.context.scene.collection.children.link(collection)
            else:
                parent_collection.children.link(collection)
                
            for ob in objects:
                collection.objects.link(ob)
            
        return objects
    
    def _import_light_cones(self, parent_collection: bpy.types.Collection = None):
        objects = []
        for element in self.block(self.tag.root(), 'Light Cones'):
            name = self.value(element, 'marker name')
            rotation = self._rotation(element)
            position = Vector(self.value(element, 'position').to_array()) * 100
            length = self.value(element, 'length')
            width = self.value(element, 'width')
            intensity = self.value(element, 'intensity')
            light_color = rgba(self.value(element, 'light color'))
            light_cone_tag = self._reference_path(element, 'light cone tag')
            intensity_curve = self._reference_path(element, 'intensity curve')
            
            if not light_cone_tag:
                continue
            
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "CONE"
            ob.empty_display_size *= (1 / 0.03048) * import_transform.scale_factor()
            ob.matrix_world = import_transform.marker_matrix(Matrix.LocRotScale(position, rotation, Vector.Fill(3, 1)))
            ob.nwo.marker_type = '_connected_geometry_marker_type_lightCone'
            ob.nwo.marker_light_cone_length = length
            ob.nwo.marker_light_cone_width = width
            ob.nwo.marker_light_cone_intensity = intensity
            ob.nwo.marker_light_cone_color = light_color
            ob.nwo.marker_light_cone_tag = light_cone_tag
            ob.nwo.marker_light_cone_curve = intensity_curve
            objects.append(ob)
        
        if objects:
            collection = cast(bpy.types.Collection, bpy.data.collections.new(f"{self.tag_path.ShortName}_light_cones"))
            if parent_collection is None:
                bpy.context.scene.collection.children.link(collection)
            else:
                parent_collection.children.link(collection)
                
            for ob in objects:
                collection.objects.link(ob)
            
        return objects
    
    def _import_objects(self, parent_collection: bpy.types.Collection = None):
        
        palette = [self._reference_path(element, 'definition') for element in self.block(self.tag.root(), 'Object Palette')]
        
        objects = []
        for element in self.block(self.tag.root(), 'Objects'):
            name = self.value(element, 'name')
            rotation = self._rotation(element)
            translation = Vector(self.value(element, 'translation').to_array()) * 100
            scale = self.value(element, 'scale')
            palette_index = self.value(element, 'palette_index')
            if palette_index > -1 and palette_index < len(palette):
                object_path = palette[palette_index]
                if not object_path:
                    continue
            else:
                continue
            
            run_scripts = self.required_field(element, 'flags').get_flag('scripts always run')
            variant = self.value(element, 'variant name')
            
            if not name:
                continue

            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "ARROWS"
            ob.matrix_world = import_transform.marker_matrix(Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale)))
            
            ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
            ob.nwo.marker_game_instance_tag_name = object_path
            ob.nwo.marker_game_instance_tag_variant_name = variant
            ob.nwo.marker_always_run_scripts = run_scripts
            objects.append(ob)
        
        if objects:
            collection = cast(bpy.types.Collection, bpy.data.collections.new(f"{self.tag_path.ShortName}_objects"))
            if parent_collection is None:
                bpy.context.scene.collection.children.link(collection)
            else:
                parent_collection.children.link(collection)
                
            for ob in objects:
                collection.objects.link(ob)
            
        return objects
        
    def to_blender(self, parent_collection: bpy.types.Collection = None, objects_only=False) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
        objects = []
        if not objects_only:
            objects.extend(self._import_effects(parent_collection))
            objects.extend(self._import_airprobes(parent_collection))
            objects.extend(self._import_light_cones(parent_collection))
            
        return objects, self._import_objects(parent_collection)
