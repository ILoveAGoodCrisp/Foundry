from pathlib import Path

import bpy

from .. import utils


FOUNDRY_PACKAGE_NAME = "io_scene_foundry"


def _foundry_library_target(filepath: str) -> Path | None:
    parts = [part for part in filepath.replace("\\", "/").split("/") if part]
    foundry_indices = [
        index for index, part in enumerate(parts) if part.lower() == FOUNDRY_PACKAGE_NAME
    ]
    if not foundry_indices:
        return None

    suffix = parts[foundry_indices[-1] + 1 :]
    if not suffix:
        return None

    return Path(utils.addon_root(), *suffix)


def _paths_match(filepath: str, target: Path) -> bool:
    try:
        filepath_norm = Path(filepath).resolve()
        target_norm = target.resolve()

        return filepath_norm == target_norm
    except (OSError, RuntimeError, ValueError):
        filepath_norm = filepath.replace("\\", "/").rstrip("/").casefold()
        target_norm = str(target).replace("\\", "/").rstrip("/").casefold()

        return filepath_norm == target_norm


def _fix_shader_node_libraries():
    libraries_to_update = {}
    missing_targets = set()
    failed_libraries = []

    for node_tree in bpy.data.node_groups:
        library = node_tree.library
        if library is None or not library.filepath:
            continue

        target = _foundry_library_target(library.filepath)
        if target is None:
            continue

        if _paths_match(library.filepath, target):
            continue

        if not target.exists():
            missing_targets.add(str(target))
            continue

        libraries_to_update[library.name] = (library, target)

    updated_libraries = set()
    for library_name, (library, target) in libraries_to_update.items():
        try:
            library.filepath = str(target)
            updated_libraries.add(library_name)
        except Exception as ex:
            failed_libraries.append(f"{library.name}: {ex}")

    for library_name in updated_libraries:
        library = bpy.data.libraries.get(library_name)
        if library is not None and hasattr(library, "reload"):
            try:
                library.reload()
            except Exception as ex:
                failed_libraries.append(f"{library.name} reload failed: {ex}")

    return updated_libraries, missing_targets, failed_libraries


def _looks_absolute(filepath: str) -> bool:
    filepath = filepath.strip()
    return (
        Path(filepath).is_absolute()
        or filepath.startswith("\\\\")
        or (len(filepath) > 1 and filepath[1] == ":")
    )


def _split_path(filepath: str) -> list[str]:
    return [part for part in filepath.replace("\\", "/").split("/") if part]


def _project_relative_from_path(filepath: str) -> tuple[str, Path] | None:
    filepath = filepath.strip("\"' ")
    if not filepath:
        return None

    parts = _split_path(filepath)
    for root in ("data", "tags"):
        indices = [index for index, part in enumerate(parts) if part.lower() == root]
        if indices:
            suffix = parts[indices[-1] + 1 :]
            if suffix:
                return root, Path(*suffix)

    if filepath.startswith("//"):
        filepath = filepath[2:]

    if not _looks_absolute(filepath):
        parts = _split_path(filepath)
        if parts:
            return "data", Path(*parts)

    return None


def _image_filepaths(image: bpy.types.Image) -> list[str]:
    filepaths = []
    try:
        user_path = image.filepath_from_user() if image.filepath else ""
    except Exception:
        user_path = ""

    nwo = getattr(image, "nwo", None)

    for filepath in (
        image.filepath,
        _image_absolute_path(image),
        user_path,
        getattr(nwo, "filepath", ""),
    ):
        if filepath and filepath not in filepaths:
            filepaths.append(filepath)

    return filepaths


def _image_absolute_path(image: bpy.types.Image) -> str:
    if not image.filepath:
        return ""

    try:
        return bpy.path.abspath(image.filepath, library=image.library)
    except Exception:
        return image.filepath


def _image_project_candidates(image: bpy.types.Image) -> list[tuple[str, Path]]:
    candidates = []
    seen = set()

    for filepath in _image_filepaths(image):
        candidate = _project_relative_from_path(filepath)
        if candidate is None:
            continue

        root, relative = candidate
        key = (root, str(relative).replace("\\", "/").casefold())
        if key not in seen:
            candidates.append(candidate)
            seen.add(key)

    return candidates


def _image_target_path(root: str, relative: Path) -> Path | None:
    if relative.suffix.lower() == ".bitmap":
        return None

    if root == "tags":
        return Path(utils.get_tags_path(), relative)

    return Path(utils.get_data_path(), relative)


def _bitmap_target_path(relative: Path) -> Path:
    if relative.suffix.lower() == ".bitmap":
        return Path(utils.get_tags_path(), relative)

    return Path(utils.get_tags_path(), relative).with_suffix(".bitmap")


def _apply_image_path(image: bpy.types.Image, filepath: str | Path, bitmap_info=None):
    image.filepath = str(filepath)

    if hasattr(image, "nwo"):
        image.nwo.filepath = utils.relative_path(filepath)

    if bitmap_info is not None:
        if bitmap_info.for_normal:
            image.colorspace_settings.name = "Non-Color"
        elif bitmap_info.curve == 3:
            image.colorspace_settings.name = "Linear Rec.709"
            image.alpha_mode = "CHANNEL_PACKED"
        else:
            image.colorspace_settings.name = "sRGB"
            image.alpha_mode = "CHANNEL_PACKED"

        if bitmap_info.sequence_length > 1:
            image.source = "SEQUENCE"

    try:
        image.reload()
    except Exception:
        pass


def _extract_bitmap_for_image(image: bpy.types.Image, bitmap_path: Path) -> bool:
    from ..managed_blam.bitmap import bitmap_to_image

    info = bitmap_to_image(bitmap_path, True)
    if not info.image_path or not Path(info.image_path).exists():
        return False

    loaded_image = info.image
    _apply_image_path(image, info.image_path, info)

    if loaded_image is not None and loaded_image != image and loaded_image.users == 0:
        bpy.data.images.remove(loaded_image)

    return True


def _fix_image_references(extract_bitmaps: bool, replace_existing_paths: bool):
    updated_images = set()
    extracted_images = set()
    missing_images = set()
    failed_images = set()

    if extract_bitmaps:
        from ..managed_blam.bitmap import clear_path_cache

        clear_path_cache()

    for image in bpy.data.images:
        candidates = _image_project_candidates(image)
        if not candidates:
            continue

        current_path = _image_absolute_path(image)
        original_exists = bool(current_path and Path(current_path).exists())

        for root, relative in candidates:
            target = _image_target_path(root, relative)
            if target is None or not target.exists():
                continue

            if (
                not current_path
                or not original_exists
                or replace_existing_paths
            ) and not _paths_match(current_path, target):
                _apply_image_path(image, target)
                updated_images.add(image.name)

            break
        else:
            if extract_bitmaps and (not original_exists or replace_existing_paths):
                for _root, relative in candidates:
                    bitmap_path = _bitmap_target_path(relative)
                    if not bitmap_path.exists():
                        continue

                    if _extract_bitmap_for_image(image, bitmap_path):
                        extracted_images.add(image.name)
                    else:
                        failed_images.add(image.name)
                    break
                else:
                    if not original_exists:
                        missing_images.add(image.name)
            elif not original_exists:
                missing_images.add(image.name)

    return updated_images, extracted_images, missing_images, failed_images


class NWO_OT_FindFoundryShaderNodes(bpy.types.Operator):
    bl_idname = "nwo.find_foundry_shader_nodes"
    bl_label = "Find Missing Foundry Nodes / Images"
    bl_description = "Repairs linked Foundry shader node and image library paths"
    bl_options = {"REGISTER", "UNDO"}

    fix_shader_nodes: bpy.props.BoolProperty(
        name="Fix Shader Nodes",
        description="Update linked Foundry shader node libraries to this Foundry install",
        default=True,
        options=set(),
    )
    fix_images: bpy.props.BoolProperty(
        name="Fix Images",
        description="Update image filepaths to the current Foundry project when matching files exist",
        default=True,
        options=set(),
    )
    extract_bitmaps: bpy.props.BoolProperty(
        name="Extract Bitmaps",
        description="Extract missing image files from matching bitmap tags in the current project",
        default=True,
        options=set(),
    )
    replace_existing_image_paths: bpy.props.BoolProperty(
        name="Replace Existing Image Paths",
        description=(
            "Use current-project image paths when possible even if the existing "
            "image path still points to a valid file"
        ),
        default=False,
        options=set(),
    )

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "fix_shader_nodes")
        layout.prop(self, "fix_images")
        row = layout.row()
        row.enabled = self.fix_images
        row.prop(self, "extract_bitmaps")
        row = layout.row()
        row.enabled = self.fix_images
        row.prop(self, "replace_existing_image_paths")

    def execute(self, context):
        did_work = False
        had_problem = False

        if self.fix_shader_nodes:
            updated_libraries, missing_targets, failed_libraries = _fix_shader_node_libraries()

            if failed_libraries:
                had_problem = True
                for failure in failed_libraries:
                    self.report({"ERROR"}, failure)

            if missing_targets:
                had_problem = True
                for target in sorted(missing_targets):
                    self.report({"WARNING"}, f"Foundry node library does not exist: {target}")

            if updated_libraries:
                did_work = True
                update_count = len(updated_libraries)
                self.report(
                    {"INFO"},
                    f"Updated {update_count} Foundry shader node "
                    f"{'library path' if update_count == 1 else 'library paths'}",
                )

        if self.fix_images:
            if utils.current_project_valid():
                (
                    updated_images,
                    extracted_images,
                    missing_images,
                    failed_images,
                ) = _fix_image_references(
                    self.extract_bitmaps,
                    self.replace_existing_image_paths,
                )

                if updated_images:
                    did_work = True
                    update_count = len(updated_images)
                    self.report(
                        {"INFO"},
                        f"Updated {update_count} image "
                        f"{'filepath' if update_count == 1 else 'filepaths'}",
                    )

                if extracted_images:
                    did_work = True
                    extract_count = len(extracted_images)
                    self.report(
                        {"INFO"},
                        f"Extracted {extract_count} bitmap "
                        f"{'image' if extract_count == 1 else 'images'}",
                    )

                if missing_images:
                    had_problem = True
                    self.report(
                        {"WARNING"},
                        f"Could not resolve {len(missing_images)} image "
                        f"{'filepath' if len(missing_images) == 1 else 'filepaths'}",
                    )

                if failed_images:
                    had_problem = True
                    self.report(
                        {"ERROR"},
                        f"Failed to extract {len(failed_images)} bitmap "
                        f"{'image' if len(failed_images) == 1 else 'images'}",
                    )
            else:
                had_problem = True
                self.report({"WARNING"}, "No current Foundry project is loaded")

        if did_work:
            return {"FINISHED"}

        if had_problem:
            return {"CANCELLED"}

        if not self.fix_shader_nodes and not self.fix_images:
            self.report({"INFO"}, "No repair options selected")
        else:
            self.report(
                {"INFO"},
                "No Foundry shader node or image paths needed updating",
            )

        return {"FINISHED"}
