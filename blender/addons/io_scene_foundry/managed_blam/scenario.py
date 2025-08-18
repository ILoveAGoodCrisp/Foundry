from math import radians
from pathlib import Path

from mathutils import Euler, Matrix, Quaternion, Vector

from .Tags import TagFieldBlockElement

from ..managed_blam import Tag
import os
from .. import utils
import bpy

class ScenarioObjectReference:
    def __init__(self, element: TagFieldBlockElement):
        self.definition = ""
        self.name = "object"
        def_path = element.Fields[0].Path
        if def_path is not None:
            if Path(def_path.Filename).exists():
                self.definition = def_path.RelativePathWithExtension
                self.name = def_path.ShortName
    
class ScenarioObject:
    def __init__(self, element: TagFieldBlockElement, palette: list[ScenarioObjectReference], object_names: list[str]):
        self.name_index = element.SelectField("ShortBlockIndex:name").Value
        self.name = "object"
        self.position = Vector([n * 100 for n in element.SelectField("Struct:object data[0]/RealPoint3d:position").Data])
        rot = [radians(n) for n in element.SelectField("Struct:object data[0]/RealEulerAngles3d:rotation").Data]
        self.rotation = Euler((rot[2], rot[1], rot[0]))
        self.scale = element.SelectField("Struct:object data[0]/Real:scale").Data
        if self.scale == 0.0:
            self.scale = 1
        palette_index = element.SelectField("ShortBlockIndex:type").Value
        self.reference = palette[palette_index] if palette_index > -1  and palette_index < len(palette) else None
        self.variant = element.SelectField("Struct:permutation data[0]/StringId:variant name").GetStringData()
        
        self.folder_index = element.SelectField("Struct:object data[0]/ShortBlockIndex:editor folder").Value
        self.parent_index = element.SelectField("Struct:object data[0]/Struct:parent id[0]/ShortBlockIndex:parent object").Value
        self.parent_marker = element.SelectField("Struct:object data[0]/Struct:parent id[0]/StringId:parent marker").GetStringData()
        
        if self.name_index > -1 and self.name_index < len(object_names):
            self.name = object_names[self.name_index]
        elif self.reference is not None:
            self.name = f"{self.reference.name}:{element.ElementIndex}"
            
    def to_object(self):
        if self.reference is None or self.reference.definition is None:
            return print(f"Found scenario object named {self.name} but it has no valid tag reference")
            
        ob = bpy.data.objects.new(name=self.name, object_data=None)
        ob.empty_display_type = "ARROWS"
        ob.matrix_world = Matrix.LocRotScale(self.position, self.rotation, Vector.Fill(3, self.scale))

        ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
        ob.nwo.marker_game_instance_tag_name = self.reference.definition
        ob.nwo.marker_game_instance_tag_variant_name = self.variant
        
        return ob

class ScenarioTag(Tag):
    tag_ext = 'scenario'
        
    def _read_fields(self):
        self.block_skies = self.tag.SelectField("Block:skies")
        self.block_object_names = self.tag.SelectField("Block:object names")
        self.block_bsps = self.tag.SelectField("Block:structure bsps")
        self.block_zone_sets = self.tag.SelectField("Block:zone sets")
        self.block_structure_designs = self.tag.SelectField("Block:structure designs")
        
    def _get_bsp_from_name(self, bsp_name: str):
        for element in self.block_bsps.Elements:
            bsp_reference = element.SelectField('structure bsp').Path
            if bsp_reference is None:
                continue
            full_bsp_name = utils.dot_partition(os.path.basename(bsp_reference.RelativePath))
            if full_bsp_name == bsp_name:
                return element
        else:
            return print("BSP not found in Scenario Tag, perhaps you need to export the scene")
        
    def _sky_name_from_element(self, element):
        # Check if we can retrieve the name from the object names block
        object_names_block_index = element.SelectField('name').Value
        if object_names_block_index:
            object_names_element = self.block_object_names.Elements[object_names_block_index]
            object_name = object_names_element.SelectField('name').GetStringData()
            if object_name:
                return object_name
        
        # If we haven't yet found the name, just take the tag name
        sky_tag_path = element.SelectField('sky').Path
        if not sky_tag_path: return
        return utils.dot_partition(os.path.basename(sky_tag_path.ToString()))
    
    def get_skies_mapping(self) -> list:
        """Reads the scenario skies block and returns a list of skies"""
        skies = []
        for element in self.block_skies.Elements:
            sky_name = self._sky_name_from_element(element)
            if sky_name is None: continue  
            skies.append(sky_name)
            
        return skies
    
    def add_new_sky(self, path: str) -> tuple[str, int]:
        """Appends a new entry to the scenario skies block, adding a reference to the given sky scenery tag path"""
        new_sky_element = self.block_skies.AddElement()
        new_sky_element.SelectField('sky').Path = self._TagPath_from_string(path)
        new_object_name_element = self.block_object_names.AddElement()
        sky_name = utils.dot_partition(os.path.basename(path))
        new_object_name_element.SelectField('name').SetStringData(sky_name)
        new_sky_element.SelectField('name').Value = new_object_name_element.ElementIndex
        sky_index = new_sky_element.ElementIndex
        if self.corinth and sky_index == 0: # if this is h4+ and is the first sky, add it to all bsps that currently have no default sky
            for element in self.block_bsps.Elements:
                default_sky = element.SelectField("default sky")
                if default_sky.Value == -1:
                    default_sky.Value = sky_index
                    
        self.tag_has_changes = True
        return sky_name, sky_index
    
    def set_bsp_default_sky(self, bsp_name: str, sky_index: int):
        """Sets the default sky of the given bsp"""
        # Get the bsp we want from the list
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        # Check current sky to see if we need to update it
        for f in bsp_element.Fields:
            print(f.DisplayName)
        sky_block_index = bsp_element.SelectField('default sky').Value
        if sky_block_index == sky_index:
            print("Default sky already set to this")
        else:
            bsp_element.SelectField('default sky').Value = sky_index
        self.tag_has_changes = True
        return self._sky_name_from_element(self.block_skies.Elements[sky_index])
        
    def set_bsp_lightmap_res(self, bsp_name: str, size_class: int, refinement_class: int) -> bool:
        """Sets the lightmap resolution and refinement class for this bsp"""
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return False
        bsp_element.SelectField('size class').Value = size_class
        if self.corinth:
            bsp_element.SelectField('refinement size class').Value = refinement_class
        self.tag_has_changes = True
        return bsp_element.SelectField('size class').Items[size_class].DisplayName
        
    def get_bsp_info(self, bsp_name: str) -> dict:
        """Returns interesting information about this BSP in a dict"""
        bsp_info_dict = {}
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        bsp_info_dict["Lightmapper Size Class"] = self._Element_get_enum_as_string(bsp_element, "size class")
        if self.corinth:
            bsp_info_dict["Lightmapper Refinement Class"] = self._Element_get_enum_as_string(bsp_element, "refinement size class")
        sky_index = bsp_element.SelectField('default sky').Data
        if sky_index == -1:
            bsp_info_dict["Default Sky"] = "None"
        else:
            bsp_info_dict["Default Sky"] = self._sky_name_from_element(self.block_skies.Elements[sky_index])
        
        return bsp_info_dict
    
    def read_scenario_type(self) -> int:
        return self.tag.SelectField('type').Value
    
    def survival_mode(self) -> bool:
        return self.read_scenario_type() == 0 and self.tag.SelectField('flags').TestBit('survival')
    
    def get_bsp_paths(self, zone_set=""):
        bsps = []
        zone_set_bsp_names = set()
        if zone_set:
            for element in self.block_zone_sets.Elements:
                if element.Fields[0].GetStringData() == zone_set:
                    for flag in element.SelectField("bsp zone flags").Items:
                        if flag.IsSet:
                            zone_set_bsp_names.add(flag.FlagName)
                            
        for element in self.block_bsps.Elements:
            bsp_reference = element.SelectField('structure bsp').Path
            if bsp_reference:
                if zone_set_bsp_names and bsp_reference.ShortName not in zone_set_bsp_names:
                    continue
                full_path = bsp_reference.Filename
                if Path(full_path).exists:
                    bsps.append(full_path)
                    
        return bsps
    
    def get_design_paths(self, zone_set=""):
        designs = []
        zone_set_bsp_names = set()
        if zone_set:
            for element in self.block_zone_sets.Elements:
                if element.Fields[0].GetStringData() == zone_set:
                    for flag in element.SelectField("structure design zone flags").Items:
                        if flag.IsSet:
                            zone_set_bsp_names.add(flag.FlagName)
                            
        for element in self.block_structure_designs.Elements:
            design_reference = element.SelectField('Reference:structure design').Path
            if design_reference:
                if zone_set_bsp_names and design_reference.ShortName not in zone_set_bsp_names:
                    continue
                full_path = design_reference.Filename
                if Path(full_path).exists:
                    designs.append(full_path)
                    
        return designs
    
    def get_bsp_names(self) -> list[str]:
        return [os.path.basename(element.Fields[0].Path.RelativePath) for element in self.block_bsps.Elements if element.Fields[0].Path is not None]
    
    def to_blend(self):
        # Import Seams
        print("Importing Seams")
        
    def get_seams_path(self):
        reference = self.tag.SelectField("Reference:structure seams")
        if reference.Path:
            full_path = reference.Path.Filename
            if Path(full_path).exists:
                return full_path
            
    def create_default_profile(self):
        '''Creates a default player starting profile & location'''
        self.tag.SelectField("Block:player starting locations").AddElement()
        element = self.tag.SelectField("Block:player starting profile").AddElement()
        element.SelectField("name").SetStringData("default_single")
        primary = None
        secondary = None
        equipment = None

        with Tag(path=r"multiplayer\globals.multiplayer_object_type_list", tag_must_exist=True, raise_on_error=False) as mp_globals:
            for mp_element in mp_globals.tag.SelectField("Block:object types").Elements:
                match mp_element.Fields[1].GetStringData():
                    case 'assault_rifle':
                        path = mp_element.Fields[2].Path
                        if path:
                            primary = path.RelativePathWithExtension
                    case 'magnum':
                        path = mp_element.Fields[2].Path
                        if path:
                            secondary = path.RelativePathWithExtension
                    case 'sprint_equipment':
                        path = mp_element.Fields[2].Path
                        if path:
                            equipment = path.RelativePathWithExtension
        
        if primary is not None:
            element.SelectField("Reference:primary weapon").Path = self._TagPath_from_string(primary)
            element.SelectField("ShortInteger:primaryrounds loaded").Data = -1
            element.SelectField("ShortInteger:primaryrounds total").Data = -1
        if secondary is not None:
            element.SelectField("Reference:secondary weapon").Path = self._TagPath_from_string(secondary)
            element.SelectField("ShortInteger:secondaryrounds loaded").Data = -1
            element.SelectField("ShortInteger:secondaryrounds total").Data = -1
        if not self.corinth and equipment is not None:
            element.SelectField("Reference:starting equipment").Path = self._TagPath_from_string(equipment)

        self.tag_has_changes = True
        
    def update_cinematic_resource(self):
        resources = self.tag.SelectField("Block:scenario resources[0]/Block:new split resources")
        if not resources:
            return
        if not resources.Elements.Count:
            return
        element = resources.Elements[0]
        cinematic_resource = element.SelectField("Reference:cutscene data resource")
        if cinematic_resource.Path is None:
            return
        if not Path(self.tags_dir, cinematic_resource.Path.RelativePathWithExtension).exists():
            return

        with Tag(path=cinematic_resource.Path.RelativePathWithExtension) as resource:
            self.tag.SelectField("Block:cinematics").CopyEntireTagBlock()
            resource.tag.SelectField("Block:cinematics").PasteReplaceEntireBlock()
            self.tag.SelectField("Block:cutscene flags").CopyEntireTagBlock()
            resource.tag.SelectField("Block:flags").PasteReplaceEntireBlock()
            resource.tag_has_changes = True
            
    def get_zone_sets_dict(self) -> dict[str, list[str]]:
        """Returns a dict with the key as the zoneset name and values as a str of the bsps"""
        zs_dict = {}
        for element in self.block_zone_sets.Elements:
            zs_dict[element.Fields[0].GetStringData()] = [item.FlagName for item in element.SelectField("BlockFlags:bsp zone flags").Items if item.IsSet]
            
        return zs_dict
    
    def get_info(self, bsp_index: int) -> str | None:
        if self.corinth:
            return None
        field = self.tag.SelectField(f"Block:structure bsps[{bsp_index}]/Reference:structure lighting_info")
        if field is not None and field.Path is not None:
            return Path(field.Path.Filename)
        
    def write_foundry_zone_set(self):
        for element in self.block_zone_sets.Elements:
            if element.Fields[0].GetStringData() == "foundry_debug_zone_set":
                foundry_element = element
                break
        else:
            foundry_element = self.block_zone_sets.AddElement()
            foundry_element.Fields[0].SetStringData("foundry_debug_zone_set")
            self.tag_has_changes = True

        bsp_flags = foundry_element.SelectField("bsp zone flags")
        sd_flags = foundry_element.SelectField("structure design zone flags")
        
        for item in bsp_flags.Items:
            if not item.IsSet:
                self.tag_has_changes = True
                item.IsSet = True
        for item in sd_flags.Items:
            if not item.IsSet:
                self.tag_has_changes = True
                item.IsSet = True
                
                
    def objects_to_blender(self, parent_collection=None):
        
        objects = []
        child_objects = {}
        
        objects_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_objects")
        objects_collection.nwo.type = 'exclude'
        
        if parent_collection is None:
            bpy.context.scene.collection.children.link(objects_collection)
        else:
            parent_collection.children.link(objects_collection)
            
        object_names = [e.Fields[0].GetStringData() for e in self.tag.SelectField("Block:object names").Elements]
        named_objects = [None] * len(object_names)
        editor_folders = {bpy.data.collections.new(e.Fields[1].GetStringData()): e.Fields[0].Value for e in self.tag.SelectField("Block:editor folders").Elements}
        folders = list(editor_folders)
        
        for collection, parent_index in editor_folders.items():
            if parent_index < 0 or parent_index >= len(editor_folders):
                objects_collection.children.link(collection)
            else:
                folders[parent_index].children.link(collection)
        
        # Scenery
        scenery = self.tag.SelectField("Block:scenery")
        if scenery.Elements.Count > 0:
            used_collection = False
            print("Creating Scenario Scenery Objects")
            scenery_collection = bpy.data.collections.new(name="scenery")
            objects_collection.children.link(scenery_collection)
            scenery_palette = [ScenarioObjectReference(e) for e in self.tag.SelectField("Block:scenery palette").Elements]
            for element in scenery.Elements:
                scenario_object = ScenarioObject(element, scenery_palette, object_names)
                ob = scenario_object.to_object()
                if ob is not None:
                    if scenario_object.name_index > -1 and scenario_object.name_index < len(object_names):
                        named_objects[scenario_object.name_index] = ob
                        
                    if scenario_object.parent_index > -1:
                        child_objects[ob] = scenario_object.parent_index
                        
                    if scenario_object.folder_index > -1 and scenario_object.folder_index < len(folders):
                        folder = folders[scenario_object.folder_index]
                        folder.objects.link(ob)
                    else:
                        scenery_collection.objects.link(ob)
                        used_collection = True
                        
                    objects.append(ob)
                    
            if not used_collection:
                bpy.data.collections.remove(scenery_collection)
                
        # Parent
        for ob, parent_index in child_objects.items():
            if parent_index < len(named_objects):
                parent = named_objects[parent_index]
                if parent is not None:
                    ob.parent = parent
                    
        return objects