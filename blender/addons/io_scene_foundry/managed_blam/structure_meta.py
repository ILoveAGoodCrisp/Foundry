

from pathlib import Path
from typing import cast
import bpy
from mathutils import Euler, Matrix, Vector

from ..managed_blam import Tag
from .. import utils

class StructureMetaTag(Tag):
    tag_ext = 'structure_meta'
    
    def _read_fields(self):
        self.effects = self.tag.SelectField("Block:Effects markers")
        self.airprobes = self.tag.SelectField("Block:Airprobes")
        self.light_cones = self.tag.SelectField("Block:Light Cones")
        self.object_palette = self.tag.SelectField("Block:Object Palette")
        self.objects = self.tag.SelectField("Block:Objects")
        
    def _import_effects(self, parent_collection: bpy.types.Collection = None):
        objects = []
        for element in self.effects.Elements:
            name = element.Fields[0].GetStringData()
            rotation = utils.ijkw_to_wxyz((*element.Fields[1].Data,))
            position = Vector((*element.Fields[2].Data,)) * 100
            effect = self.get_path_str(element.Fields[3].Path)
            
            if not effect:
                continue
            
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "ARROWS"
            ob.empty_display_size *= (1 / 0.03048)
            ob.matrix_world = Matrix.LocRotScale(position, rotation, Vector.Fill(3, 1))
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
        for element in self.airprobes.Elements:
            position = Vector((*element.Fields[0].Data,)) * 100
            name = element.Fields[1].GetStringData()
            
            if not name:
                continue
            
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "SPHERE"
            ob.empty_display_size *= (1 / 0.03048)
            ob.matrix_world = Matrix.LocRotScale(position, Euler(), Vector.Fill(3, 1))
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
        for element in self.light_cones.Elements:
            name = element.Fields[0].GetStringData()
            rotation = utils.ijkw_to_wxyz((*element.Fields[1].Data,))
            position = Vector((*element.Fields[2].Data,)) * 100
            length = element.Fields[3].Data
            width = element.Fields[4].Data
            intensity = element.Fields[5].Data
            light_color = (*element.Fields[6].Data,)
            light_color = light_color[1], light_color[2], light_color[3], light_color[0]
            light_cone_tag = self.get_path_str(element.Fields[7].Path)
            intensity_curve = self.get_path_str(element.Fields[8].Path)
            
            if not light_cone_tag:
                continue
            
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "CONE"
            ob.empty_display_size *= (1 / 0.03048)
            ob.matrix_world = Matrix.LocRotScale(position, rotation, Vector.Fill(3, 1))
            ob.nwo.marker_type = '_connected_geometry_marker_type_lightCone'
            ob.nwo.marker_light_cone_length = length
            ob.nwo.marker_light_cone_width = width
            ob.nwo.marker_light_cone_intensity = intensity
            ob.nwo.marker_light_cone_color = light_color
            ob.nwo.marker_light_cone_tag = light_cone_tag
            ob.nwo.marker_light_cone_intensity = intensity_curve
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
    
    def _import_objects(self, parent_collection: bpy.types.Collection = None):
        
        palette = [self.get_path_str(element.Fields[0].Path) for element in self.object_palette.Elements]
        
        objects = []
        for element in self.objects.Elements:
            name = element.Fields[0].GetStringData()
            rotation = utils.ijkw_to_wxyz((*element.Fields[1].Data,))
            translation = Vector((*element.Fields[2].Data,)) * 100
            scale = element.Fields[3].Data
            palette_index = element.Fields[4].Value
            if palette_index > -1 and palette_index < len(palette):
                object_path = palette[palette_index]
                if not object_path:
                    continue
            else:
                continue
            
            run_scripts = element.Fields[5].TestBit("scripts always run")
            variant = element.Fields[9].GetStringData()
            
            if not name:
                continue

            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "ARROWS"
            ob.matrix_world = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
            
            ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
            ob.nwo.marker_game_instance_tag_name = object_path
            ob.nwo.marker_game_instance_tag_variant_name = variant
            ob.nwo.marker_always_run_scripts = run_scripts
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
        
    def to_blender(self, parent_collection: bpy.types.Collection = None) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
        objects = []
        objects.extend(self._import_effects(parent_collection))
        objects.extend(self._import_airprobes(parent_collection))
        objects.extend(self._import_light_cones(parent_collection))
        
        return objects, self._import_objects(parent_collection)