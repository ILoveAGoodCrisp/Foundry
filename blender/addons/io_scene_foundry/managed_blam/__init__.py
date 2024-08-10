from pathlib import Path
from ..managed_blam.Tags import *
from ..utils import (
    disable_prints,
    dot_partition,
    enable_prints,
    get_asset_path,
    get_data_path,
    get_tags_path,
    linear_to_srgb,
    is_corinth,
    print_error,
    print_warning,
    relative_path,
)
import bpy
import os
from ..utils import get_project_path
import sys
import atexit
import clr

last_saved_tag = None

Halo = None
Tags = TagsNameSpace()
Animation = GameAnimation()

mb_active = False
mb_path = ""
mb_operational = False

class Tag():
    # Stuff classes that inherit from this one may overwrite
    tag_ext = ""
    needs_explicit_path = False
    # Stuff that other classes may change while executing
    tag_has_changes = False # This needs to be marked false when changes are made, so that the tag can be saved
    
    def __init__(self, path="", hide_prints=False, tag_must_exist=False, raise_on_error=True):
        self.tag_must_exist = tag_must_exist
        self.valid = False
        self.tag = None
        if self.needs_explicit_path and not path:
            raise ValueError("Class needs explicit path declared but none given")
        self.hide_prints = hide_prints
        if hide_prints:
            disable_prints()
        if not mb_active:
            mb_init()
            
        # Asset Info
        self.context = bpy.context
        self.tags_dir = get_tags_path() # full path to tags dir
        self.data_dir = get_data_path() # full path to data dir
        self.asset_dir = get_asset_path() # the relative path to the asset directory
        self.asset_name = self.asset_dir.rpartition(os.sep)[2] # the name of the asset (i.e the directory name)
        self.asset_tag_dir = Path(self.tags_dir, self.asset_dir) # full path to the asset data directory
        self.asset_data_dir = Path(self.data_dir, self.asset_dir) # full path to the asset tags directory
        self.corinth = is_corinth(self.context) # bool to check whether the game is H4+
        self.unit_scale = self.context.scene.unit_settings.scale_length
        
        
        
        # Tag Info
        self.path = path
        self.tag_is_new = False
        self._find_tag()
        try:
            if os.path.exists(self.system_path):
                self.tag.Load(self.tag_path)
            elif self.tag_must_exist:
                raise RuntimeError(f"No file exists for {self.path}, but this {self.__class__} has been told one must exist")
            else:
                self.tag.New(self.tag_path)
                self.tag_is_new = True
            
            if not self.tag_path:
                raise RuntimeError(f"Failed to load Tag: {str(self.path)}")
            
            elif not self.tag_path.IsTagFileAccessible():
                raise RuntimeError(f"TagFile not accessible: {self.tag_path.RelativePathWithExtension}")
                
            self._read_fields()
            if self.tag_is_new:
                self._initialize_tag()
                self.tag_has_changes = True # Must always save new tags
                
            self.valid = True
            
        except:
            err_message = f"Failed to Load Tag: {Path(self.path).name}"
            print_error(err_message)
            if raise_on_error:
                raise RuntimeError(err_message)
        
    def _read_fields(self):
        """Read in some useful fields for this tag type"""
        pass
    
    def _initialize_tag(self):
        """Only run when a new tag created. Sets up some default values"""
        pass
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        if self.tag:
            if self.tag_has_changes:
                self.tag.Save()
            self.tag.Dispose()
        if self.hide_prints:
            enable_prints()

    def _find_tag(self):
        is_TagPath = False
        if type(self.path) == str or isinstance(self.path, Path):
            self.path = str(self.path)
            # If path isn't set by now, assume it is in the asset folder with the asset name
            if self.path:
                # enforce relativity
                self.path = relative_path(self.path)
                # Enforce extension if tag has one defined
                if self.tag_ext:
                    self.path = dot_partition(self.path) + '.' + self.tag_ext
            else:
                self.path = str(Path(self.asset_dir, self.asset_name).with_suffix("." + self.tag_ext))

            self.system_path = str(Path(self.tags_dir, self.path))
            
        else:
            # Assume we have instead be given a TagPath
            self.system_path = str(Path(self.tags_dir, self.path.RelativePathWithExtension))
            is_TagPath = True
        
        self.tag, self.tag_path = self._get_tag_and_path(is_TagPath)
            
    def save(self):
        self.tag.Save()
    
    # TAG HELPER FUNCTIONS
    #######################

    def _get_tag_and_path(self, is_TagPath) -> tuple[TagFile, TagPath]:
        """Return the tag and bungie tag path for tag creation"""
        tag = Tags.TagFile()
        if is_TagPath:
            tag_path = self.path
            # convert path to a str
            self.path = tag_path.RelativePathWithExtension
        else:
            tag_path = Tags.TagPath.FromPathAndExtension(*self._get_path_and_ext(self.path))
            
        return tag, tag_path
    
    def _Tag(self) -> TagFile:
        return Tags.TagFile()

    def _get_path_and_ext(self, user_path):
        """Splits a file path into path and extension"""
        return user_path.rpartition(".")[0], user_path.rpartition(".")[2]

    def _block_new_element(self, parent, block_name: str):
        """Creates a new element in the named block and returns the element"""
        block = parent.SelectField(block_name)
        return block.AddElement()
    
    def _Element_create_if_needed(self, block, field_name, value_name):
        element = block.Elements
        element = self. _Element_from_field_value(block, field_name, value_name)
        if element:
            return element
        return block.AddElement()
    
    def _Element_remove_if_needed(self, block, field_name, value_name):
        element = block.Elements
        element = self. _Element_from_field_value(block, field_name, value_name)
        if element:
            block.RemoveElement(element.ElementIndex)
    
    def _Element_create_if_needed_and_confirm(self, block, field_name, value_name):
        element = block.Elements
        element = self. _Element_from_field_value(block, field_name, value_name)
        if element:
            return element, False
        return block.AddElement(), True
            

    
    def _Element_set_field_value(self, element, field_name: str, value):
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
    
    def _Element_set_field_values(self, element, field_value_dict):
        """Sets the value of the given fields by the given dict. Requires the tag element to be specified as the first arg. Returns a list of the fields set"""
        fields = []
        for k, v in field_value_dict.items():
            fields.append(self. _Element_set_field_value(element, k, v))

        return fields
    
    def _Element_get_field_value(self, element, field_name: str, always_string=False):
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
    
    def _Element_get_enum_as_string(self, element, field_name: str):
        """Returns the value of an enum field as a string"""
        field = element.SelectField(field_name)
        field_type_str = str(field.FieldType)
        assert(field_type_str.endswith("Enum")), f"Element_get_enum_as_string supplied a {field_type_str} instead of an enum"
        value = field.Value
        items = [i.EnumName for i in field.Items]
        value_string = items[value]
        return value_string
    
    def _TagPath_from_string(self, path: str) -> TagPath:
        """Returns a Bungie TagPath from the given tag filepath. Filepath must include file extension"""
        rel_path = relative_path(path)
        return Tags.TagPath.FromPathAndExtension(*self._get_path_and_ext(rel_path))
    
    def _TagPath(self) -> TagPath:
        """Returns a new TagPath instance"""
        return Tags.TagPath()
    
    def _AnimationExporter(self) -> AnimationExporter:
        return Animation.AnimationExporter()
    
    def _GameAnimationNode(self) -> GameAnimationNode:
        return Animation.GameAnimationNode()
    
    def _GameAnimationNodeType(self) -> GameAnimationNode:
        return Animation.GameAnimationNode
    
    def _GameRenderGeometry(self) -> GameRenderGeometry:
        """Returns a new GameRenderGeometry instance"""
        return Tags.GameRenderGeometry()
    
    def _GameRenderModel(self) -> GameRenderModel:
        """Returns a new GameRenderModel instance"""
        return Tags.GameRenderModel()
    
    def _GameBitmapChannel(self, index: int) -> GameBitmapChannel:
        """Returns a new GameBitmapChannel instance"""
        return Tags.GameBitmapChannel(index)
    
    def _GameBitmap(self) -> GameBitmap:
        """Returns a new GameBitmap instance"""
        return Tags.GameBitmap(self.tag, 0, 0)
    
    def _FunctionEditorColorGraphType(self, type) -> FunctionEditorColorGraphType:
        """Returns a new FunctionEditorColorGraphType instance"""
        return Tags.FunctionEditorColorGraphType(type)
    
    def _FunctionEditorMasterType(self, type) -> FunctionEditorMasterType:
        """Returns a new FunctionEditorMasterType instance"""
        return Tags.FunctionEditorMasterType(type)
    
    def _tag_exists(self, path: str) -> bool:
        """Returns true if a tag given by the supplied relative path exists"""
        return Path(self.tags_dir, relative_path(path)).exists()
    
    def _EnumItems(self, element, field_name: str) -> list:
        field = element.SelectField(field_name)
        if str(field.FieldType).endswith("Enum"): 
            return [i.EnumName for i in field.Items]
        else:
            return print("Given field is not an Enum")
        
    def _EnumIntValue(self, block, field_name, value):
        elements = block.Elements
        if not elements.Count:
            return #print(f"{block} has no elements")
        items = self. _EnumItems(elements[0], field_name)
        for idx, item in enumerate(items):
            if item == value:
                return idx
        return print("Value not found in items")
        
    def _clear_block_and_set(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
        return block.AddElement()
    
    def _clear_block(self, parent, block_name):
        block = parent.SelectField(block_name)
        block.RemoveAllElements()
    
    def _Element_from_field_value(self, block, field_name, value):
        elements = block.Elements
        if not elements.Count:
            return #print(f"{block} has no elements")
        for e in elements:
            field_value = self._Element_get_field_value(e, field_name)
            if field_value == value:
                return e
            
    def _GameColor_from_RGB(self, r, g, b):
        return Halo.Game.GameColor.FromRgb(linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(b))
    
    def _GameColor_from_ARGB(self, a, r, g, b):
        return Halo.Game.GameColor.FromArgb(a, linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(b))


def mb_init():
    context = bpy.context
    # append the blender python module path to the sys PATH
    packages_path = Path(sys.exec_prefix, "lib", "site-packages")
    sys.path.append(str(packages_path))
    # Get the reference to ManagedBlam.dll
    global mb_path
    mb_path = Path(get_project_path(), "bin", "managedblam.dll")

    # Check that a path to ManagedBlam actually exists
    if not mb_path.exists():
        print_warning("Could not find path to ManagedBlam.dll")
        return

    # Logic for importing the clr module and importing Bungie/Corinth from ManagedBlam.dll
    try:
        clr.AddReference(str(mb_path.with_suffix("")))
        if is_corinth(context):
            import Corinth as Bungie # type: ignore
        else:
            import Bungie # type: ignore
            
        mb_operational = True

    except:
        print("Failed to add reference to ManagedBlam")
        return {"CANCELLED"}

    else:
        global Halo
        Halo = Bungie
        try:
            callback = Halo.ManagedBlamCrashCallback(lambda info: None)
            startup_parameters = Halo.ManagedBlamStartupParameters()
            startup_parameters.InitializationLevel = Halo.InitializationType.TagsOnly
            System = Halo.ManagedBlamSystem()
            System.Start(get_project_path(), callback, startup_parameters)
            global Tags
            Tags = Halo.Tags
            global Animation
            Animation = Halo.Game.Animation
            atexit.register(close_managed_blam)
            global mb_active
            mb_active = True
            
        except:
            print("ManagedBlam already initialised Once. Skipping")
        
def close_managed_blam():
    Halo.ManagedBlamSystem.Stop()