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

from gc import enable
from io_scene_foundry.utils import nwo_globals
from io_scene_foundry.managed_blam.mb_utils import get_bungie, get_path_and_ext, get_tag_and_path
from io_scene_foundry.utils.nwo_utils import (
    disable_prints,
    get_asset_path,
    get_data_path,
    get_tags_path,
    managed_blam_active,
    not_bungie_game,
    print_warning,
)
import bpy
import os
from bpy.types import Context, Operator, OperatorProperties
from bpy.props import StringProperty
from io_scene_foundry.utils.nwo_utils import get_ek_path
import sys
import subprocess
import ctypes

class ManagedBlam():
    """Helper class for loading and saving tags"""
    def __init__(self):
        if not managed_blam_active():
            bpy.ops.managed_blam.init()

        # Asset Info
        self.tags_dir = get_tags_path() # full path to tags dir + \
        self.data_dir = get_data_path() # full path to data dir + \
        self.asset_dir = get_asset_path() # the relative path to the asset directory
        self.asset_name = self.asset_dir.rpartition(os.sep)[2] # the name of the asset (i.e the directory name)
        self.asset_tag_dir = self.tags_dir + self.asset_dir # full path to the asset data directory
        self.asset_data_dir = self.data_dir + self.asset_dir # full path to the asset tags directory
        self.corinth = not_bungie_game() # bool to check whether the game is H4+
        # Tag Info
        self.path = "" # String to hold the tag relative path to the tag we're editing/reading
        self.read_only = False # Bool to check whether tag should be opened in Read Only mode (i.e. never saved)
        self.tag_is_new = False # Set to True when a tag needs to be created. Not set True if in read_only mode

    def get_path(self): # stub
        print("get_path stub called")
        return ""

    def tag_edit(self, tag): # stub
        print("tag_edit stub called")

    def tag_read(self, tag): # stub
        print("tag_read stub called")

    def tag_helper(self):
        if not self.path:
            self.path = self.get_path()

        self.system_path = get_tags_path() + self.path

        self.Bungie = get_bungie()
        self.tag, self.tag_path = get_tag_and_path(self.Bungie, self.path)
        tag = self.tag
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
            else:
                self.tag_edit(tag)
                tag.Save()

        finally:
            tag.Dispose()

    
    # TAG HELPER FUNCTIONS
    #######################
    def block_new_element_by_name(self, parent, block_name: str):
        """Creates a new element in the named block and returns the element"""
        block = parent.SelectField(block_name)
        return block.AddElement()
    
    def field_set_value_by_name(self, element, field_name: str, value):
        """Sets the value of the given field by name. Requires the tag element to be specified as the first arg. Returns the field"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        match field_type_str:
            case "StringId":
                field.SetStringData(value)
            case "ShortInteger":
                field.SetStringData(value)
            case "LongEnum":
                field.SetValue(value)
            case "Reference":
                field.Path = self.TagPath_from_string(value)
            case "WordInteger":
                field.SetStringData(value)

        return field
    
    def TagPath_from_string(self, relative_path: str):
        """Returns a Bungie TagPath from the given tag relative filepath. Filepath must include file extension"""
        relative_path, tag_ext = get_path_and_ext(relative_path)
        return self.Bungie.Tags.TagPath.FromPathAndExtension(relative_path, tag_ext)
    
    def tag_exists(self, relative_path: str) -> bool:
        """Returns if a tag given by the supplied relative path exists"""
        return os.path.exists(self.tags_dir + relative_path)
    
    def EnumItems_by_name(self, element, field_name: str) -> list:
        field = element.SelectField(field_name)
        if str(field.Type).endswith("Enum"): 
            return [i.EnumName for i in field.Items]
        else:
            return print("Given field is not an Enum")
        
    def clear_block_and_set_by_name(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
        return block.AddElement()

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

    def callback(self):
        pass

    def execute(self, context):
        # append the blender python module path to the sys PATH
        packages_path = os.path.join(sys.exec_prefix, "lib", "site-packages")
        sys.path.append(packages_path)
        # Get the reference to ManagedBlam.dll
        mb_path = os.path.join(get_ek_path(), "bin", "managedblam")

        # Check that a path to ManagedBlam actually exists
        if not os.path.exists(f"{mb_path}.dll"):
            print_warning("Could not find path to ManagedBlam.dll")
            return {"CANCELLED"}

        # Logic for importing the clr module and importing Bungie/Corinth from ManagedBlam.dll
        try:
            import clr

            try:
                clr.AddReference(mb_path)
                if context.scene.nwo.game_version == "reach":
                    import Bungie
                else:
                    import Corinth as Bungie

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
                try:
                    startup_parameters = Bungie.ManagedBlamStartupParameters()
                    Bungie.ManagedBlamSystem.Start(
                        get_ek_path(), self.callback(), startup_parameters
                    )
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
        Bungie = get_bungie(self.report)
        Bungie.ManagedBlamSystem.Stop()
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
