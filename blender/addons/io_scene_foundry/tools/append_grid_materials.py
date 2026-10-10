"""Create the grid palette using the selected editing kit's tag formats."""
from pathlib import Path

import bpy

from .. import utils
from ..tags.bitmap import BitmapTag
from ..tags.grid_materials import remove_incompatible_grid_tag, create_grid_shader, grid_shader_path
from .bitmap_tiff import write_image_tiff


ADDON_DIR = Path(__file__).resolve().parents[1]
BITMAP_DIR = Path('shaders', 'foundry', 'bitmaps')
GRID_NAMES = (
    'grid_checkered', 'grid_checkered_cross',
    'grid_dark_cross', 'grid_dark_diagonal', 'grid_dark_square',
    'grid_orange_cross', 'grid_orange_diagonal', 'grid_orange_square',
)


class NWO_OT_AppendGridMaterials(bpy.types.Operator):
    bl_idname = 'nwo.append_grid_materials'
    bl_label = 'Append Grid Materials'
    bl_description = 'Adds a collection of grid materials to the blend file'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()

    def execute(self, context):
        try:
            append_grid_materials()
        except Exception as exc:
            self.report({'ERROR'}, f'Could not create Grid Materials: {exc}')
            return {'CANCELLED'}
        self.report({'INFO'}, 'Grid Materials Added')
        return {'FINISHED'}


def append_grid_materials():
    with utils.busy_cursor():
        _append_grid_materials()


def _append_grid_materials():
    # Existing Blender materials must not prevent missing project tags from
    # being created (for example after switching projects or deleting a bitmap).
    game = utils.get_game()
    images = {name: bpy.data.images.load(
        filepath=str(ADDON_DIR / 'images' / (name + '.png')), check_existing=True)
        for name in GRID_NAMES}
    ensure_grid_bitmaps(images, game)
    for name, image in images.items():
        setup_grid_material(name, image, game)


def setup_grid_material(name, image, game):
    shader_path = grid_shader_path(name, game, utils.get_scene_props().asset_type)
    create_grid_shader(shader_path, BITMAP_DIR / (name + '.bitmap'), game)

    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        material.use_fake_user = True
        tree = material.node_tree
        tree.nodes.clear()
        output = tree.nodes.new('ShaderNodeOutputMaterial')
        output.location = (300, 0)
        bsdf = tree.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Specular IOR Level'].default_value = 0
        texture = tree.nodes.new('ShaderNodeTexImage')
        texture.location = (-300, 0)
        texture.image = image
        tree.links.new(bsdf.outputs[0], output.inputs['Surface'])
        tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])

    # Keep custom replacements and edits, but update Foundry's own reference
    # when changing game or switching between an H1 level and model asset.
    previous = Path(material.nwo.shader_path)
    if not material.nwo.shader_path or (previous.parent == shader_path.parent and previous.stem == name):
        material.nwo.shader_path = str(shader_path)
    return material


def prepare_grid_bitmap(image, name, game):
    relative = BITMAP_DIR / (name + '.bitmap')
    remove_incompatible_grid_tag(relative, game)
    source = relative.with_suffix('.tif')
    data_path = Path(utils.get_data_path(), source)
    if not data_path.exists():
        data_path.parent.mkdir(parents=True, exist_ok=True)
        # Avoid Blender's view transform and TIFF compression unsupported by
        # the older editing kits. The bundled PNG's byte colours are retained.
        write_image_tiff(image, data_path)
    image.nwo.filepath = str(source)
    image.nwo.source_name = source.name

    with BitmapTag(path=relative) as bitmap:
        if bitmap.has_bitmap_data():
            return None
        if game in {'halo1', 'halo2'}:
            root = bitmap.tag.root()
            bitmap.required_field(root, 'usage').set('default')
            # Both classic formats use zero for 2D and DXT1 colour textures.
            bitmap.required_field(root, 'type').set(0)
            bitmap.required_field(root, 'encoding format' if game == 'halo1' else 'format').set(0)
            bitmap.tag_has_changes = True
        else:
            bitmap.new_bitmap(name, 'Diffuse Map', 'sRGB', preserve_size=True)
    return relative


def ensure_grid_bitmaps(images, game):
    pending = [path for name, image in images.items()
               if (path := prepare_grid_bitmap(image, name, game)) is not None]
    if not pending:
        return
    try:
        if game in {'halo1', 'halo2'}:
            # Prepare the entire classic palette first
            # so one Tool call builds it, with the correct settings on every tag.
            utils.run_tool(['bitmaps', str(BITMAP_DIR)], force_tool=True)
        else:
            for relative in pending:
                path = str(relative.with_suffix(''))
                args = ['reimport-bitmaps-single', path]
                if game in {'halo4', 'halo2a'}:
                    args.append('default')
                # Use stock Tool for bitmap compilation.
                utils.run_tool(args, force_tool=True)
        # Some versions of Tool return success even when TIFF import failed.
        for relative in pending:
            with BitmapTag(path=relative) as bitmap:
                if not bitmap.has_bitmap_data():
                    raise RuntimeError(f'{relative}: bitmap compiler produced no pixels')
    except Exception:
        # Leave no empty tag that could be mistaken for a completed bitmap.
        for relative in pending:
            with BitmapTag(path=relative) as bitmap:
                empty = not bitmap.has_bitmap_data()
            if empty:
                Path(utils.get_tags_path(), relative).unlink(missing_ok=True)
        raise
