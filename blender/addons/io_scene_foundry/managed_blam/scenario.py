from pathlib import Path

from ..managed_blam import Tag
import os
from .. import utils

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
            full_bsp_name = utils.dot_partition(os.path.basename(bsp_reference.ToString()))
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
        self.tag_has_changes = True
        return sky_name, new_sky_element.ElementIndex
    
    def set_bsp_default_sky(self, bsp_name: str, sky_index: int):
        """Sets the default sky of the given bsp"""
        # Get the bsp we want from the list
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        # Check current sky to see if we need to update it
        print(bsp_element)
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
    
    def get_bsp_paths(self):
        bsps = []
        for element in self.block_bsps.Elements:
            bsp_reference = element.SelectField('structure bsp').Path
            if bsp_reference:
                full_path = bsp_reference.Filename
                if Path(full_path).exists:
                    bsps.append(full_path)
                    
        return bsps
    
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