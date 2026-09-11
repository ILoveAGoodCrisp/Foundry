import os
from pathlib import Path
import shutil
import subprocess

import bpy

from .. import utils


# Keep dynamic enum strings alive while Blender displays the search popup.
_variant_items = []


def valid_megalo_variants(project_path):
    if not project_path:
        return []
    project = Path(project_path)
    maps = project / "maps" / "megalo"
    hot_reload = project / "HotReload"
    if not maps.is_dir() or not hot_reload.is_dir():
        return []
    hot_reload_names = {
        path.name.casefold() for path in hot_reload.iterdir()
        if path.is_file() and path.suffix.lower() == '.mglo'
    }
    return sorted({
        path.stem for path in maps.iterdir()
        if path.is_file() and path.suffix.lower() == '.mglo'
        and path.name.casefold() in hot_reload_names
    }, key=str.casefold)


class NWO_OT_SelectMegaloVariant(bpy.types.Operator):
    bl_idname = "nwo.select_megalo_variant"
    bl_label = "Select Megalo Variant"
    bl_description = "Search MGLO variants present in both maps/megalo and HotReload"
    bl_options = {'UNDO'}
    bl_property = "variant"

    def variant_items(self, context):
        return _variant_items

    variant: bpy.props.EnumProperty(name="Megalo Variant", items=variant_items)

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()

    def invoke(self, context, event):
        try:
            variants = valid_megalo_variants(utils.get_project_path())
        except OSError as error:
            self.report({'ERROR'}, f"Unable to list Megalo variants: {error}")
            return {'CANCELLED'}
        _variant_items.clear()
        _variant_items.extend((name, name, f"{name}.mglo") for name in variants)
        if not _variant_items:
            self.report({'WARNING'}, "No .mglo files present in both maps/megalo and HotReload. Generate them using the Build Megalo Variants Tool in the Foundry Tools Panel")
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            if self.variant not in valid_megalo_variants(utils.get_project_path()):
                self.report({'ERROR'}, "The variant must exist in both maps/megalo and HotReload")
                return {'CANCELLED'}
        except OSError as error:
            self.report({'ERROR'}, f"Unable to check Megalo variant: {error}")
            return {'CANCELLED'}
        utils.get_launcher_props().megalo_variant = self.variant
        return {'FINISHED'}


class NWO_OT_BuildMegaloVariants(bpy.types.Operator):
    bl_idname = "nwo.build_megalo_variants"
    bl_label = "Build"
    bl_description = "Compile all text variants directly in the chosen folder and copy MGLO files to HotReload"

    directory: bpy.props.StringProperty(
        name="Source Folder",
        subtype='DIR_PATH',
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    filter_glob: bpy.props.StringProperty(
        default="*.txt",
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()

    def invoke(self, context, event):
        self.directory = str(Path(utils.get_data_path(), "multiplayer", "megalo")) + os.sep
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        project_path = utils.get_project_path()
        if not project_path:
            self.report({'ERROR'}, "No active project")
            return {'CANCELLED'}
        project = Path(project_path)
        executable = project / "MegaloEdit.exe"
        if not executable.is_file():
            self.report({'ERROR'}, f"MegaloEdit.exe was not found in {project}")
            return {'CANCELLED'}
        if not self.directory or not Path(self.directory).is_dir():
            self.report({'ERROR'}, "Choose an existing source folder")
            return {'CANCELLED'}

        processed = 0
        failed = 0
        try:
            sources = sorted(
                (path for path in Path(self.directory).iterdir()
                 if path.is_file() and path.suffix.lower() == '.txt'),
                key=lambda path: path.name.lower(),
            )
            if not sources:
                self.report({'WARNING'}, "0 .txt files processed: no .txt files in the source folder")
                return {'CANCELLED'}
            (project / "maps" / "megalo").mkdir(parents=True, exist_ok=True)
            hot_reload = project / "HotReload"
            hot_reload.mkdir(parents=True, exist_ok=True)
            for source in sources:
                success = True
                for extension in ('.bin', '.mglo'):
                    output = Path("maps", "megalo", source.stem + extension)
                    try:
                        subprocess.run(
                            [str(executable), "--cli", "--compile", str(source.resolve()), output.as_posix()],
                            cwd=project,
                            check=True,
                        )
                        if not (project / output).is_file():
                            raise OSError(f"MegaloEdit did not create {output}")
                        if extension == '.mglo':
                            shutil.copy2(project / output, hot_reload / output.name)
                    except (OSError, subprocess.CalledProcessError) as error:
                        success = False
                        utils.print_warning(f"Failed to build {source.name} ({extension}): {error}")
                if success:
                    processed += 1
                else:
                    failed += 1
        except OSError as error:
            self.report({'ERROR'}, f"Megalo build failed after {processed} .txt files: {error}")
            return {'CANCELLED'}

        message = f"{processed} .txt files processed and saved to maps/megalo; .mglo files copied to HotReload"
        if failed:
            self.report({'WARNING'}, f"{message}. {failed} failed; see console for details")
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'} if processed else {'CANCELLED'}
