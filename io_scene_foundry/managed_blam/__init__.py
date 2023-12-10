# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from io_scene_foundry.managed_blam.Tags import *
import logging
import traceback
from io_scene_foundry.utils import nwo_globals
from io_scene_foundry.utils.nwo_utils import (
    get_asset_path,
    get_data_path,
    get_tags_path,
    managed_blam_active,
    is_corinth,
    print_error,
    print_warning,
)
import bpy
import os
from bpy.types import Context, Operator, OperatorProperties
from io_scene_foundry.utils.nwo_utils import get_project_path
import sys
import subprocess
import ctypes

last_saved_tag = None

Halo = None
Tags = TagsNameSpace()

class ManagedBlam():
    """Helper class for loading and saving tags"""
    def __init__(self):
        if not managed_blam_active():
            bpy.ops.managed_blam.init()

        # Asset Info
        self.context = bpy.context
        self.tags_dir = get_tags_path() # full path to tags dir + \
        self.data_dir = get_data_path() # full path to data dir + \
        self.asset_dir = get_asset_path() # the relative path to the asset directory
        self.asset_name = self.asset_dir.rpartition(os.sep)[2] # the name of the asset (i.e the directory name)
        self.asset_tag_dir = self.tags_dir + self.asset_dir # full path to the asset data directory
        self.asset_data_dir = self.data_dir + self.asset_dir # full path to the asset tags directory
        self.corinth = is_corinth(self.context) # bool to check whether the game is H4+
        self.unit_scale = self.context.scene.unit_settings.scale_length
        # Tag Info
        self.path = "" # String to hold the tag relative path to the tag we're editing/reading
        # self.read_only = False # Bool to check whether tag should be opened in Read Only mode (i.e. never saved)
        self.tag_is_new = False # Set to True when a tag needs to be created. Not set True if in read_only mode

    def get_path(self): # stub
        print("get_path stub called")
        return ""

    def tag_helper(self):
        if not self.path:
            self.path = self.get_path()

        if not self.path:
            return print("No path to tag found")

        self.system_path = get_tags_path() + self.path
        
        if type(self.path) == str:
            self.tag, self.tag_path = self.get_tag_and_path(self.path)
        else:
            self.tag = self.path
        tag = self.tag
        self.read_only = callable(getattr(self, "tag_read", None))
        try:
            if os.path.exists(self.system_path):
                tag.Load(self.tag_path)
            elif not self.read_only:
                self.tag_is_new = True
                tag.New(self.tag_path)
            else:
                print("Read only mode but tag path does not exist")
            if self.read_only:
                self.tag_read(tag)
            elif callable(getattr(self, "tag_edit", None)):
                self.tag_edit(tag)
                global last_saved_tag
                if not getattr(self, 'skip_save', 0) and last_saved_tag != tag:
                    last_saved_tag = tag
                    tag.Save()

        except Exception as e:
            print_error("\n ManagedBlam Exception hit:\n")
            logging.error(traceback.format_exc())

        finally:
            tag.Dispose()

    
    # TAG HELPER FUNCTIONS
    #######################

    def get_tag_and_path(self, user_path):
        """Return the tag and bungie tag path for tag creation"""
        relative_path, tag_ext = self.get_path_and_ext(user_path)
        tag = Halo.Tags.TagFile()
        tag_path = Halo.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)

        return tag, tag_path

    def get_path_and_ext(self, user_path):
        """Splits a file path into path and extension"""
        return user_path.rpartition(".")[0], user_path.rpartition(".")[2]

    def block_new_element(self, parent, block_name: str):
        """Creates a new element in the named block and returns the element"""
        block = parent.SelectField(block_name)
        return block.AddElement()
    
    def Element_create_if_needed(self, block, field_name, value_name):
        element = block.Elements
        element = self.Element_from_field_value(block, field_name, value_name)
        if element:
            return element
        return block.AddElement()
    
    def Element_remove_if_needed(self, block, field_name, value_name):
        element = block.Elements
        element = self.Element_from_field_value(block, field_name, value_name)
        if element:
            block.RemoveElement(element.ElementIndex)
    
    def Element_create_if_needed_and_confirm(self, block, field_name, value_name):
        element = block.Elements
        element = self.Element_from_field_value(block, field_name, value_name)
        if element:
            return element, False
        return block.AddElement(), True
            

    
    def Element_set_field_value(self, element, field_name: str, value):
        """Sets the value of the given field by name. Requires the tag element to be specified as the first arg. Returns the field"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        match field_type_str:
            case "LongEnum":
                if type(value) == str:
                    field.SetValue(value)
                else:
                    field.Value = value
            case "Reference":
                if type(value) == str:
                    field.Path = self.TagPath_from_string(value)
                else:
                    field.Path = value
            case _:
                field.SetStringData(value)

        return field
    
    def Element_set_field_values(self, element, field_value_dict):
        """Sets the value of the given fields by the given dict. Requires the tag element to be specified as the first arg. Returns a list of the fields set"""
        fields = []
        for k, v in field_value_dict.items():
            fields.append(self.Element_set_field_value(element, k, v))

        return fields
    
    def Element_get_field_value(self, element, field_name: str, always_string=False):
        """Gets the value of the given field by name. Requires the tag element to be specified as the first arg. Returns the fvalue of the given field. If the last arg is specified as True, always returns values as strings"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        value = None
        match field_type_str:
            case "StringId":
                value = field.GetStringData()
            case "ShortInteger":
                value = field.GetStringData()
            case "LongEnum":
                value = field.Value
            case "Reference":
                value = field.Path
            case "WordInteger":
                value = field.GetStringData()
            case "Data":
                value = field.DataAsText

        if always_string:
            return str(value)
        return value
    
    def TagPath_from_string(self, relative_path: str):
        """Returns a Bungie TagPath from the given tag relative filepath. Filepath must include file extension"""
        relative_path, tag_ext = self.get_path_and_ext(relative_path)
        return Halo.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)
    
    def tag_exists(self, relative_path: str) -> bool:
        """Returns if a tag given by the supplied relative path exists"""
        return os.path.exists(self.tags_dir + relative_path)
    
    def EnumItems(self, element, field_name: str) -> list:
        field = element.SelectField(field_name)
        if str(field.FieldType).endswith("Enum"): 
            return [i.EnumName for i in field.Items]
        else:
            return print("Given field is not an Enum")
        
    def EnumIntValue(self, block, field_name, value):
        elements = block.Elements
        if not elements.Count:
            return #print(f"{block} has no elements")
        items = self.EnumItems(elements[0], field_name)
        for idx, item in enumerate(items):
            if item == value:
                return idx
        return print("Value not found in items")
        
    def clear_block_and_set(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
        return block.AddElement()
    
    def clear_block(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
    
    def Element_from_field_value(self, block, field_name, value):
        elements = block.Elements
        if not elements.Count:
            return #print(f"{block} has no elements")
        for e in elements:
            field_value = self.Element_get_field_value(e, field_name)
            if field_value == value:
                return e
            
    def GameColor_from_RGB(self, r, g, b):
        return Halo.Game.GameColor.FromRgb(r, g, b)
    
    def GameColor_from_ARGB(self, a, r, g, b):
        return Halo.Game.GameColor.FromArgb(a, r, g, b)
        
class Tag():
    """Helper class for loading and saving tags (temp for new format)"""
    def __enter__(self, path=""):
        if not managed_blam_active():
            bpy.ops.managed_blam.init()

        # Asset Info
        self.context = bpy.context
        self.tags_dir = get_tags_path() # full path to tags dir + \
        self.data_dir = get_data_path() # full path to data dir + \
        self.asset_dir = get_asset_path() # the relative path to the asset directory
        self.asset_name = self.asset_dir.rpartition(os.sep)[2] # the name of the asset (i.e the directory name)
        self.asset_tag_dir = self.tags_dir + self.asset_dir # full path to the asset data directory
        self.asset_data_dir = self.data_dir + self.asset_dir # full path to the asset tags directory
        self.corinth = is_corinth(self.context) # bool to check whether the game is H4+
        self.unit_scale = self.context.scene.unit_settings.scale_length
        # Tag Info
        self.path = path if path else self._get_path() # String to hold the tag relative path to the tag we're editing/reading
        self.read_only = False # Bool to check whether tag should be opened in Read Only mode (i.e. never saved)
        self.tag_is_new = False # Set to True when a tag needs to be created. Not set True if in read_only mode
        self._find_tag()
        
        if os.path.exists(self.system_path):
            self.tag.Load(self.tag_path)
        else:
            self.tag_is_new = True
            self.tag.New(self.tag_path)

        self._read_blocks()
        
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.tag.Dispose()

    def _get_path(self): # stub
        print("get_path stub called")
        return ""
    
    def _read_blocks(self): # 
        print("read_blocks stub called")

    def _find_tag(self):
        if not self.path:
            return print("No path to tag found")

        self.system_path = get_tags_path() + self.path
        
        if type(self.path) == str:
            self.tag, self.tag_path = self.get_tag_and_path(self.path)
        else:
            self.tag = self.path
            
            
    def save(self):
        self.tag.Save()
    
    # TAG HELPER FUNCTIONS
    #######################

    def get_tag_and_path(self, user_path) -> tuple[TagFile, TagPath]:
        """Return the tag and bungie tag path for tag creation"""
        relative_path, tag_ext = self.get_path_and_ext(user_path)
        tag = Tags.TagFile()
        tag_path = Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)
        return tag, tag_path

    def get_path_and_ext(self, user_path):
        """Splits a file path into path and extension"""
        return user_path.rpartition(".")[0], user_path.rpartition(".")[2]

    def block_new_element(self, parent, block_name: str):
        """Creates a new element in the named block and returns the element"""
        block = parent.SelectField(block_name)
        return block.AddElement()
    
    def Element_create_if_needed(self, block, field_name, value_name):
        element = block.Elements
        element = self.Element_from_field_value(block, field_name, value_name)
        if element:
            return element
        return block.AddElement()
    
    def Element_remove_if_needed(self, block, field_name, value_name):
        element = block.Elements
        element = self.Element_from_field_value(block, field_name, value_name)
        if element:
            block.RemoveElement(element.ElementIndex)
    
    def Element_create_if_needed_and_confirm(self, block, field_name, value_name):
        element = block.Elements
        element = self.Element_from_field_value(block, field_name, value_name)
        if element:
            return element, False
        return block.AddElement(), True
            

    
    def Element_set_field_value(self, element, field_name: str, value):
        """Sets the value of the given field by name. Requires the tag element to be specified as the first arg. Returns the field"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        match field_type_str:
            case "LongEnum":
                if type(value) == str:
                    field.SetValue(value)
                else:
                    field.Value = value
            case "Reference":
                if type(value) == str:
                    field.Path = self.TagPath_from_string(value)
                else:
                    field.Path = value
            case "StringId":
                field.SetStringData(value)
            case _:
                field.Value = value

        return field
    
    def Element_set_field_values(self, element, field_value_dict):
        """Sets the value of the given fields by the given dict. Requires the tag element to be specified as the first arg. Returns a list of the fields set"""
        fields = []
        for k, v in field_value_dict.items():
            fields.append(self.Element_set_field_value(element, k, v))

        return fields
    
    def Element_get_field_value(self, element, field_name: str, always_string=False):
        """Gets the value of the given field by name. Requires the tag element to be specified as the first arg. Returns the fvalue of the given field. If the last arg is specified as True, always returns values as strings"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        value = None
        match field_type_str:
            case "StringId":
                value = field.GetStringData()
            case "ShortInteger":
                value = field.GetStringData()
            case "Reference":
                value = field.Path
            case "WordInteger":
                value = field.GetStringData()
            case "Data":
                value = field.DataAsText
            case _:
                value = field.Value

        if always_string:
            return str(value)
        return value
    
    def Element_get_enum_as_string(self, element, field_name: str):
        """Returns the value of an enum field as a string"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        assert(field_type_str.endswith("Enum")), f"Element_get_enum_as_string supplied a {field_type_str} instead of an enum"
        value = field.Value
        items = [i.EnumName for i in field.Items]
        value_string = items[value]
        return value_string
    
    def TagPath_from_string(self, path: str):
        """Returns a Bungie TagPath from the given tag filepath. Filepath must include file extension"""
        relative_path = path.replace(self.tags_dir, '')
        relative_path, tag_ext = self.get_path_and_ext(relative_path)
        return Halo.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)
    
    def tag_exists(self, relative_path: str) -> bool:
        """Returns if a tag given by the supplied relative path exists"""
        return os.path.exists(self.tags_dir + relative_path)
    
    def EnumItems(self, element, field_name: str) -> list:
        field = element.SelectField(field_name)
        if str(field.FieldType).endswith("Enum"): 
            return [i.EnumName for i in field.Items]
        else:
            return print("Given field is not an Enum")
        
    def EnumIntValue(self, block, field_name, value):
        elements = block.Elements
        if not elements.Count:
            return #print(f"{block} has no elements")
        items = self.EnumItems(elements[0], field_name)
        for idx, item in enumerate(items):
            if item == value:
                return idx
        return print("Value not found in items")
        
    def clear_block_and_set(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
        return block.AddElement()
    
    def clear_block(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
    
    def Element_from_field_value(self, block, field_name, value):
        elements = block.Elements
        if not elements.Count:
            return #print(f"{block} has no elements")
        for e in elements:
            field_value = self.Element_get_field_value(e, field_name)
            if field_value == value:
                return e
            
    def GameColor_from_RGB(self, r, g, b):
        return Halo.Game.GameColor.FromRgb(r, g, b)
    
    def GameColor_from_ARGB(self, a, r, g, b):
        return Halo.Game.GameColor.FromArgb(a, r, g, b)


class ManagedBlam_Init(Operator):
    """Initialises Managed Blam and locks the currently selected game"""

    bl_idname = "managed_blam.init"
    bl_label = "Managed Blam"
    bl_options = {"REGISTER"}
    bl_description = "Initialises Managed Blam and locks the currently selected game"

    install_only : bpy.props.BoolProperty()

    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        if properties.install_only:
            return "Installs pythonnet for Blender's python library. Pythonnet includes the clr module necessary for Foundry to be able to talk to the Halo tag API - Managedblam"

    def execute(self, context):
        # append the blender python module path to the sys PATH
        packages_path = os.path.join(sys.exec_prefix, "lib", "site-packages")
        sys.path.append(packages_path)
        # Get the reference to ManagedBlam.dll
        mb_path = os.path.join(get_project_path(), "bin", "managedblam")

        # Check that a path to ManagedBlam actually exists
        if not os.path.exists(f"{mb_path}.dll"):
            print_warning("Could not find path to ManagedBlam.dll")
            return {"CANCELLED"}

        # Logic for importing the clr module and importing Bungie/Corinth from ManagedBlam.dll
        try:
            import clr

            try:
                clr.AddReference(mb_path)
                if is_corinth(context):
                    import Corinth as Bungie
                else:
                    import Bungie

            except:
                print("Failed to add reference to ManagedBlam")
                return {"CANCELLED"}
        except:
            if not self.install_only:
                print("Couldn't find clr module, attempting pythonnet install")
                install = ctypes.windll.user32.MessageBoxW(
                    0,
                    "ManagedBlam requires the pythonnet module to be installed for Blender.\n\nInstall pythonnet now?",
                    f"Pythonnet Install Required",
                    4,
                )
                if install != 6:
                    return {"CANCELLED"}
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "pythonnet"]
                )
                print("Succesfully installed necessary modules")

                shutdown = ctypes.windll.user32.MessageBoxW(
                    0,
                    "Pythonnet module installed for Blender. Please restart Blender to use ManagedBlam.\n\nClose Blender now?",
                    f"Pythonnet Installed for Blender",
                    4,
                )
                if shutdown != 6:
                    return {"CANCELLED"}
                bpy.ops.wm.quit_blender()

            except:
                print("Failed to install pythonnet")
                return {"CANCELLED"}
            else:
                if self.install_only:
                    self.report({'INFO'}, "ManagedBlam Setup Complete")
                return {"FINISHED"}

        else:
            nwo_globals.clr_installed = True
            if not self.install_only:
                # Initialise ManagedBlam
                print("Initialising ManagedBlam...")
                global Halo
                Halo = Bungie
                try:
                    callback = Halo.ManagedBlamCrashCallback(lambda info: Halo.ManagedBlamSystem.Stop())
                    startup_parameters = Halo.ManagedBlamStartupParameters()
                    Halo.ManagedBlamSystem.Start(
                        get_project_path(), callback, startup_parameters
                    )
                    global Tags
                    Tags = Halo.Tags
                except:
                    print("ManagedBlam already initialised. Skipping")
                    return {"CANCELLED"}
                else:
                    # print("Success!")
                    nwo_globals.mb_active = True
                    nwo_globals.mb_path = mb_path

            return {"FINISHED"}

class ManagedBlam_Close(Operator):
    """Closes Managed Blam"""
    bl_idname = "managed_blam.close"
    bl_label = "Managed Blam Close"
    bl_options = {"REGISTER"}
    bl_description = "Closes Managed Blam"

    def execute(self, context):
        Halo.ManagedBlamSystem.Stop()
        return {"FINISHED"}

classeshalo = (
    ManagedBlam_Init,
    ManagedBlam_Close,
)

def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)

def unregister():
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)

if __name__ == "__main__":
    register()
