

from pathlib import Path
import bpy

class RenameParser:
    def __init__(self, filepath) -> None:
        self.filepath = Path(filepath)
        self.renames = {}
        self.copies = {}
        
    def parse_file(self):
        with self.filepath.open("r") as file:
            for line in file.readlines():
                source_name, new_name, is_copy = self._parse_line(line)
                if not source_name or not new_name: continue
                if is_copy:
                    if self.copies.get(source_name):
                        self.copies[source_name].append(new_name)
                    else:
                        self.copies[source_name] = [new_name]
                else:
                    if self.renames.get(source_name):
                        self.renames[source_name].append(new_name)
                    else:
                        self.renames[source_name] = [new_name]
    
    @staticmethod                
    def _parse_line(line: str):
        is_copy = False
        stripped_line = line.strip(' .>#"[]\'')
        no_quotes = stripped_line.replace('"', '').replace("'", "")
        parts = no_quotes.split()
        separator = "="
        for part in parts:
            if part == "=":
                separator = "="
                break
            elif part == "==>":
                separator = "==>"
                break
            elif part == "to":
                separator = "to"
                break
        else:
            if "=" in line:
                separator = "="
            else:
                return None, None, False
        
        if no_quotes.lower().startswith("renamed"):
            bit_we_want = " ".join(parts[1:])
        elif no_quotes.lower().startswith("copied all"):
            is_copy = True
            bit_we_want = " ".join(parts[2:])
        elif no_quotes.lower().startswith("copy_weapon_type"):
            is_copy = True
            bit_we_want = " ".join(parts[1:])
        else:
            bit_we_want = no_quotes
            
        if separator == '=':
            new_name, _, source_name = bit_we_want.rpartition(separator)
        else:
            source_name, _, new_name = bit_we_want.rpartition(separator)
        
        return source_name.strip(" ."), new_name.strip(" ."), is_copy
            
class NWO_OT_RenameImporter(bpy.types.Operator):
    bl_idname = "nwo.rename_import"
    bl_label = "Import Rename.txt"
    bl_description = "Imports a file containing details of animation renames and copies (usually called rename.txt) and adds renames & copies to existing blender animations. This operator is capable of importing the import output information you can pull from animation graphs"
    bl_options = {"UNDO"}
    
    filter_glob: bpy.props.StringProperty(
        default="*.txt",
        options={"HIDDEN"},
    )

    filepath: bpy.props.StringProperty(
        name="filepath",
        description="Path to the file containing animation renames/copies",
        subtype="FILE_PATH",
    )
    
    def create_renames(self, renames: dict):
        for action in bpy.data.actions:
            nwo = action.nwo
            if nwo.name_override.strip():
                animation_name = nwo.name_override.strip().replace(":", " ").lower()
            else:
                animation_name = action.name.strip().replace(":", " ").lower()
                
            for source, new in renames.items():
                source_clean = source.replace(":", " ").lower()
                if source_clean != animation_name: continue
                existing_renames = [item.name for item in nwo.animation_renames]
                for name in new:
                    name_clean = name.replace(":", " ").lower()
                    if name_clean not in existing_renames:
                        item = nwo.animation_renames.add()
                        item.name = name_clean
                        self.rename_count += 1
                
    def create_copies(self, context, copies: dict):
        nwo = context.scene.nwo
        for source, new in copies.items():
            source_clean = source.replace(":", " ").lower()
            for name in new:
                name_clean = name.replace(":", " ").lower()
                existing_copies = [f"{item.source_name}:{item.name}" for item in nwo.animation_copies]
                if f"{source_clean}:{name_clean}" not in existing_copies:
                    item = nwo.animation_copies.add()
                    item.source_name = source_clean
                    item.name = name_clean
                    self.copy_count += 1

    def execute(self, context):
        self.rename_count = 0
        self.copy_count = 0
        parser = RenameParser(self.filepath)
        parser.parse_file()
        self.create_renames(parser.renames)
        self.create_copies(context, parser.copies)
        self.report({'INFO'}, f"Imported {self.rename_count} rename{'s' if self.rename_count != 1 else ''} and {self.copy_count} {'copies' if self.copy_count != 1 else 'copy'}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}