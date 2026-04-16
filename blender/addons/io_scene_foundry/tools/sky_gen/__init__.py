from __future__ import annotations

from pathlib import Path
import math

import bpy
from mathutils import Vector
import numpy as np

from ... import utils
from .sky_light import (
    EPSILON,
    SkyAtmosphereParameters,
    SkyLightSample,
    build_analytic_sky_image,
    build_sky_dome_data,
    generate_sky_lights,
    get_sun_angles_from_image,
    get_sun_light,
    modifier_apply_sky_color,
    modifier_apply_sky_lighting,
    modifier_apply_sun_lighting,
)

SKY_GEN_MARKER = "_nwo_sky_gen"
SKY_GEN_COLLECTION_SUFFIX = "_sky_gen"
SKY_GEN_DOME_OBJECT = "SkyDome"
SKY_GEN_DOME_MATERIAL = "sky_gen_emission"
SKY_GEN_COLOR_ATTRIBUTE = "Color"
ANALYTIC_SKY_WIDTH = 512
ANALYTIC_SKY_HEIGHT = 256
SUPPORTED_SKY_IMAGE_FILTER = "*.jpg;*.jpeg;*.png;*.webp;*.exr;*.hdr;*.tif;*.tiff;*.bmp;*.tga;*.cin;*.dpx;*.sgi;*.rgb;*.bw;*.jp2;*.j2c;*.avif"

SKY_TYPE_MAP = {
    "PREETHAM": 0,
    "CIE": 1,
    "CUSTOM": 3,
}

SKY_GEN_PERSISTENT_PROPS = (
    "build_sky_from_map",
    "input_sky_map_name",
    "generate_type",
    "lit_objects_by_sky",
    "generate_light_count",
    "lattitude_slices",
    "longitude_slices",
    "horizontal_fov",
    "vertical_fov",
    "sun_theta",
    "sun_phi",
    "turpidity",
    "sky_type",
    "cie_sky_number",
    "sky_intensity",
    "sun_intensity",
    "luminance_only",
    "exposure",
    "sun_cone_angle",
    "custom_sun_color_override",
    "sun_color",
    "sky_dome_radius",
    "zenith_color",
    "haze_color",
    "override_zenith_color",
    "override_horizon_color",
    "horizon_haze_height",
    "sun_blur",
)
SKY_GEN_VECTOR_PROPS = {"sun_color", "zenith_color", "haze_color"}


def _sky_gen_scene_prop_name(name: str) -> str:
    return f"sky_gen_{name}"


def _initialize_sky_gen_settings(scene_nwo):
    if scene_nwo.sky_gen_settings_initialized:
        return

    scene_nwo.sky_gen_sun_cone_angle = scene_nwo.sun_size
    scene_nwo.sky_gen_settings_initialized = True


def _load_sky_gen_settings(operator: bpy.types.Operator, scene_nwo):
    for name in SKY_GEN_PERSISTENT_PROPS:
        value = getattr(scene_nwo, _sky_gen_scene_prop_name(name))
        if name == "build_sky_from_map" and isinstance(value, bool):
            value = "FILE" if value else "NONE"
        if name in SKY_GEN_VECTOR_PROPS:
            value = tuple(value)
        setattr(operator, name, value)


def _store_sky_gen_settings(operator: bpy.types.Operator, scene_nwo):
    for name in SKY_GEN_PERSISTENT_PROPS:
        setattr(scene_nwo, _sky_gen_scene_prop_name(name), getattr(operator, name))

    scene_nwo.sky_gen_settings_initialized = True
    scene_nwo.sun_size = operator.sun_cone_angle



def _ensure_generation_collection(context: bpy.types.Context) -> bpy.types.Collection:
    name = "Generated Sky"
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)

    if not any(child == collection for child in context.scene.collection.children):
        context.scene.collection.children.link(collection)

    collection[SKY_GEN_MARKER] = True
    return collection

def _clear_generated_objects(collection: bpy.types.Collection):
    light_datas = set()
    mesh_datas = set()
    objects = set()
    for ob in list(collection.all_objects):
        if ob.get(SKY_GEN_MARKER):
            objects.add(ob)
            match ob.type:
                case 'MESH':
                    mesh_datas.add(ob.data)
                case 'LIGHT':
                    light_datas.add(ob.data)
    
    if objects:
        bpy.data.batch_remove(objects)
    if light_datas:
        bpy.data.batch_remove(light_datas)
    if mesh_datas:
        bpy.data.batch_remove(mesh_datas)

def _mark_generated(ob: bpy.types.Object, kind: str):
    ob[SKY_GEN_MARKER] = True
    ob["nwo_sky_gen_kind"] = kind


def _ensure_unique_mesh_data(ob: bpy.types.Object) -> bpy.types.Mesh:
    mesh = ob.data
    if mesh.users > 1:
        mesh = mesh.copy()
        ob.data = mesh
    return mesh


def _solid_angle_to_angle(solid_angle: float) -> float:
    two_pi = 2.0 * math.pi
    cos_theta = 1.0 - (solid_angle / two_pi)
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.acos(cos_theta) * 2.0


def _position_light_object(ob: bpy.types.Object, direction: tuple[float, float, float], radius: float):
    vector = Vector(direction)
    if vector.length_squared <= EPSILON:
        vector = Vector((0.0, 0.0, 1.0))
    else:
        vector.normalize()

    ob.location = vector * radius
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = vector.to_track_quat("Z", "Y")


def _encode_light_color_energy(rgb: np.ndarray) -> tuple[tuple[float, float, float], float]:
    rgb = np.asarray(rgb, dtype=np.float32)
    length = float(np.linalg.norm(rgb))
    if length <= EPSILON:
        return (1.0, 1.0, 1.0), 0.0
    return tuple((rgb / length).tolist()), length * 0.5


def _integrate_light_sample_color(sample: SkyLightSample) -> np.ndarray:
    return np.asarray(sample.color, dtype=np.float32) * float(sample.solid_angle)


def _ensure_color_attribute(mesh: bpy.types.Mesh, name: str) -> bpy.types.Attribute:
    attribute = mesh.color_attributes.get(name)
    if attribute is not None and getattr(attribute, "domain", "POINT") != "POINT":
        mesh.color_attributes.remove(attribute)
        attribute = None

    if attribute is None:
        attribute = mesh.color_attributes.new(name, "FLOAT_COLOR", "POINT")

    return attribute


def _apply_vertex_colors(attribute: bpy.types.Attribute, colors: np.ndarray):
    colors = np.asarray(colors, dtype=np.float32)
    rgba = np.ones((len(colors), 4), dtype=np.float32)
    rgba[:, :3] = colors
    attribute.data.foreach_set("color", rgba.ravel())


def _ensure_dome_material() -> bpy.types.Material:
    material = bpy.data.materials.get(SKY_GEN_DOME_MATERIAL)
    if material is None:
        material = bpy.data.materials.new(SKY_GEN_DOME_MATERIAL)

    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()

    node_attribute = tree.nodes.new(type="ShaderNodeAttribute")
    node_attribute.attribute_name = SKY_GEN_COLOR_ATTRIBUTE
    node_attribute.location = (-320, 0)

    node_emission = tree.nodes.new(type="ShaderNodeBsdfDiffuse")
    node_emission.location = (-80, 0)

    node_output = tree.nodes.new(type="ShaderNodeOutputMaterial")
    node_output.location = (140, 0)

    tree.links.new(node_emission.inputs["Color"], node_attribute.outputs["Color"])
    tree.links.new(node_output.inputs["Surface"], node_emission.outputs[0])

    material.use_backface_culling = False
    
    material.nwo.shader_path = r'levels\shared\shaders\simple\white.material' if utils.is_corinth(bpy.context) else r'levels\shared\shaders\simple\white.shader'
    
    return material


def _load_sky_image_pixels(filepath: str) -> np.ndarray:
    resolved_path = Path(bpy.path.abspath(filepath))
    if not resolved_path.exists():
        raise FileNotFoundError(f"Sky map not found: {resolved_path}")

    image = bpy.data.images.load(str(resolved_path), check_existing=True)
    return _load_sky_image_from_image(image, str(resolved_path))


def _load_sky_image_from_image(image: bpy.types.Image, source_name: str) -> np.ndarray:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Sky map has no pixel data: {source_name}")

    channels = max(int(image.channels), 4)
    pixels = np.asarray(image.pixels[:], dtype=np.float32)
    pixel_count = width * height * channels
    if pixels.size < pixel_count:
        raise RuntimeError(f"Sky map pixel data is incomplete: {source_name}")

    pixels = pixels[:pixel_count].reshape(height, width, channels)
    return np.flipud(pixels[..., :3]).copy()


def _find_sky_image_in_node_tree(
    tree: bpy.types.NodeTree | None,
    output_types: set[str],
    visited_trees: set[int] | None = None,
) -> bpy.types.Image | None:
    if tree is None:
        return None

    if visited_trees is None:
        visited_trees = set()

    tree_id = tree.as_pointer()
    if tree_id in visited_trees:
        return None
    visited_trees.add(tree_id)

    nodes = tree.nodes
    output_node = next(
        (node for node in nodes if node.type in output_types and getattr(node, "is_active_output", False)),
        None,
    )
    if output_node is None:
        output_node = next((node for node in nodes if node.type in output_types), None)

    visited_nodes: set[int] = set()
    stack = []
    if output_node is not None:
        for input_socket in output_node.inputs:
            for link in input_socket.links:
                stack.append(link.from_node)

    while stack:
        node = stack.pop()
        node_id = node.as_pointer()
        if node_id in visited_nodes:
            continue
        visited_nodes.add(node_id)

        if node.type in {"TEX_ENVIRONMENT", "TEX_IMAGE"} and getattr(node, "image", None) is not None:
            return node.image

        if node.type == "GROUP" and getattr(node, "node_tree", None) is not None:
            image = _find_sky_image_in_node_tree(node.node_tree, {"GROUP_OUTPUT"}, visited_trees)
            if image is not None:
                return image

        for input_socket in node.inputs:
            for link in input_socket.links:
                stack.append(link.from_node)

    for node in nodes:
        if node.type in {"TEX_ENVIRONMENT", "TEX_IMAGE"} and getattr(node, "image", None) is not None:
            return node.image
        if node.type == "GROUP" and getattr(node, "node_tree", None) is not None:
            image = _find_sky_image_in_node_tree(node.node_tree, {"GROUP_OUTPUT"}, visited_trees)
            if image is not None:
                return image

    return None


def _find_world_sky_image(scene: bpy.types.Scene) -> bpy.types.Image | None:
    world = scene.world
    if world is None or not world.use_nodes or world.node_tree is None:
        return None

    return _find_sky_image_in_node_tree(world.node_tree, {"OUTPUT_WORLD"})


def _default_region_name() -> str:
    scene_nwo = utils.get_scene_props()
    if scene_nwo.regions_table:
        return scene_nwo.regions_table[0].name
    return utils.add_region("default")


def _default_permutation_name() -> str:
    scene_nwo = utils.get_scene_props()
    if scene_nwo.permutations_table:
        return scene_nwo.permutations_table[0].name
    return utils.add_permutation("default")


class NWO_OT_SkyGenerate(bpy.types.Operator):
    bl_idname = "nwo.sky_generate"
    bl_label = "Generate Sky"
    bl_description = "Generates a skydome and skylights ready for export to the game"
    bl_options = {"REGISTER", "UNDO"}

    build_sky_from_map: bpy.props.EnumProperty(
        name="Sky Source",
        description="Choose whether to use the analytic sky, the active Blender World image, or a selected image file",
        items=[
            ("NONE", "Generated", "Generate the sky analytically"),
            ("WORLD", "Scene World Image", "Sample the active Blender scene World image"),
            ("FILE", "Image File", "Sample a selected image file"),
        ],
        default="NONE",
    )

    filter_glob: bpy.props.StringProperty(
        default=SUPPORTED_SKY_IMAGE_FILTER,
        options={"HIDDEN"},
        maxlen=1024,
    )
    
    input_sky_map_name: bpy.props.StringProperty(
        name="Sky Map",
        description="Path to the sky map image to sample. Can be a HDRI map or a regular image",
        subtype="FILE_PATH",
    )
    
    generate_type: bpy.props.EnumProperty(
        name="Generate",
        items=[
            ("BOTH", "Skylights & Skydome", ""),
            ("SKYLIGHT", "Skylights Only", ""),
            ("SKYDOME", "Skydome Only", ""),
        ],
        default="BOTH",
    )
    lit_objects_by_sky: bpy.props.BoolProperty(
        name="Light Selected Meshes",
        description="Write sky lighting color attributes to selected mesh objects",
        default=False,
    )
    generate_light_count: bpy.props.IntProperty(
        name="Skylight Count",
        default=32,
        min=1,
        max=1024,
    )

    lattitude_slices: bpy.props.IntProperty(
        name="Latitude Slices",
        default=24,
        min=2,
        max=256,
    )
    longitude_slices: bpy.props.IntProperty(
        name="Longitude Slices",
        default=48,
        min=2,
        max=512,
    )
    horizontal_fov: bpy.props.FloatProperty(
        name="Horizontal FOV",
        default=360.0,
        min=1.0,
        max=360.0,
    )
    vertical_fov: bpy.props.FloatProperty(
        name="Vertical FOV",
        default=180.0,
        min=1.0,
        max=180.0,
    )

    sun_theta: bpy.props.FloatProperty(
        name="Sun Zenith",
        description="Angle from straight up in degrees",
        default=45.0,
        min=0.0,
        max=180.0,
    )
    sun_phi: bpy.props.FloatProperty(
        name="Sun Azimuth",
        default=0.0,
        min=0.0,
        max=360.0,
    )
    turpidity: bpy.props.FloatProperty(
        name="Turbidity",
        default=3.0,
        min=2.0,
        max=6.0,
    )
    sky_type: bpy.props.EnumProperty(
        name="Sky Model",
        items=[
            ("PREETHAM", "Preetham", ""),
            ("CIE", "CIE", ""),
            ("CUSTOM", "Custom", ""),
        ],
        default="PREETHAM",
    )
    cie_sky_number: bpy.props.IntProperty(
        name="CIE Sky Number",
        default=12,
        min=0,
        max=14,
    )
    sky_intensity: bpy.props.FloatProperty(
        name="Sky Intensity",
        default=1.0,
        min=0.0,
    )
    sun_intensity: bpy.props.FloatProperty(
        name="Sun Intensity",
        default=1.0,
        min=0.0,
    )
    luminance_only: bpy.props.BoolProperty(
        name="Luminance Only",
        default=False,
    )
    exposure: bpy.props.FloatProperty(
        name="Exposure",
        default=1.0,
        min=0.0,
    )
    sun_cone_angle: bpy.props.FloatProperty(
        name="Sun Size",
        default=1.0,
        min=0.0,
    )
    custom_sun_color_override: bpy.props.BoolProperty(
        name="Override Sun Color",
        default=False,
    )
    sun_color: bpy.props.FloatVectorProperty(
        name="Sun Color",
        subtype="COLOR",
        default=(1.0, 0.95, 0.9),
        min=0.0,
        max=1.0,
        size=3,
    )
    sky_dome_radius: bpy.props.FloatProperty(
        name="Sky Dome Radius",
        default=200,
        min=10,
    )
    zenith_color: bpy.props.FloatVectorProperty(
        name="Zenith Color",
        subtype="COLOR",
        default=(0.22, 0.35, 1.0),
        min=0.0,
        max=1.0,
        size=3,
    )
    haze_color: bpy.props.FloatVectorProperty(
        name="Horizon Color",
        subtype="COLOR",
        default=(1.0, 0.65, 0.3),
        min=0.0,
        max=1.0,
        size=3,
    )
    override_zenith_color: bpy.props.BoolProperty(
        name="Override Zenith Color",
        default=False,
    )
    override_horizon_color: bpy.props.BoolProperty(
        name="Override Horizon Color",
        default=False,
    )
    horizon_haze_height: bpy.props.FloatProperty(
        name="Horizon Haze Height",
        default=1.0,
        min=0.0,
        max=4.0,
    )
    sun_blur: bpy.props.FloatProperty(
        name="Sun Blur",
        default=1.0,
        min=0.01,
        max=4.0,
    )

    def invoke(self, context, _event):
        scene_nwo = utils.get_scene_props()
        _initialize_sky_gen_settings(scene_nwo)
        _load_sky_gen_settings(self, scene_nwo)
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        box = layout.box()
        col = box.column()
        col.label(text="Output")
        col.prop(self, "generate_type")
        col.prop(self, "lit_objects_by_sky")

        source_box = layout.box()
        source_col = source_box.column()
        source_col.label(text="Sky Source")
        source_col.prop(self, "build_sky_from_map", expand=True)
        if self.build_sky_from_map == "WORLD":
            world_image = _find_world_sky_image(context.scene)
            if world_image is None:
                source_col.label(text="No World image found", icon="ERROR")
            else:
                source_col.label(text=f"Using: {world_image.name}", icon="WORLD")
        elif self.build_sky_from_map == "FILE":
            source_col.prop(self, "input_sky_map_name")

        if self.generate_type != "SKYLIGHT":
            dome_box = layout.box()
            dome_col = dome_box.column()
            dome_col.label(text="Dome")
            dome_col.prop(self, "lattitude_slices")
            dome_col.prop(self, "longitude_slices")
            dome_col.prop(self, "horizontal_fov")
            dome_col.prop(self, "vertical_fov")
            dome_col.prop(self, "sky_dome_radius")

        if self.generate_type != "SKYDOME" or self.lit_objects_by_sky:
            lights_box = layout.box()
            lights_col = lights_box.column()
            lights_col.label(text="Lighting")
            lights_col.prop(self, "generate_light_count")

        atmosphere_box = layout.box()
        atmosphere_col = atmosphere_box.column()
        atmosphere_col.label(text="Atmosphere")
        atmosphere_col.prop(self, "sky_intensity")
        atmosphere_col.prop(self, "sun_intensity")
        atmosphere_col.prop(self, "exposure")
        atmosphere_col.prop(self, "turpidity")
        atmosphere_col.prop(self, "sun_theta")
        atmosphere_col.prop(self, "sun_phi")
        atmosphere_col.prop(self, "sun_cone_angle")
        atmosphere_col.prop(self, "sun_blur")

        analytic_box = layout.box()
        analytic_col = analytic_box.column()
        analytic_col.enabled = self.build_sky_from_map == "NONE"
        analytic_col.label(text="Analytic Sky")
        analytic_col.prop(self, "sky_type")
        analytic_col.prop(self, "luminance_only")
        if self.sky_type == "CIE":
            analytic_col.prop(self, "cie_sky_number")
        elif self.sky_type == "CUSTOM":
            analytic_col.prop(self, "override_zenith_color")
            if self.override_zenith_color:
                analytic_col.prop(self, "zenith_color")
            analytic_col.prop(self, "override_horizon_color")
            if self.override_horizon_color:
                analytic_col.prop(self, "haze_color")
                analytic_col.prop(self, "horizon_haze_height")

        sun_box = layout.box()
        sun_col = sun_box.column()
        sun_col.label(text="Sun Color")
        sun_col.prop(self, "custom_sun_color_override")
        if self.custom_sun_color_override:
            sun_col.prop(self, "sun_color")

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        params = self._build_parameters()

        horizontal_fov = math.radians(self.horizontal_fov)
        vertical_fov = math.radians(self.vertical_fov)
        sky_pixels = self._get_sky_pixels(context, params)

        if self.build_sky_from_map != "NONE":
            derived_sun_angles = get_sun_angles_from_image(sky_pixels)
            if derived_sun_angles is not None:
                self.sun_theta = math.degrees(derived_sun_angles[0])
                self.sun_phi = math.degrees(derived_sun_angles[1])
                params = self._build_parameters()
            else:
                self.report({"WARNING"}, "Could not derive a sun direction from the image; using the current sun zenith and azimuth")

        _store_sky_gen_settings(self, scene_nwo)

        collection = _ensure_generation_collection(context)
        _clear_generated_objects(collection)

        dome_object = None
        if self.generate_type in {"BOTH", "SKYDOME"}:
            dome_object = self._create_dome_object(collection, sky_pixels, params, horizontal_fov, vertical_fov)

        need_light_samples = self.generate_type in {"BOTH", "SKYLIGHT"} or self.lit_objects_by_sky
        sky_light_samples = (
            generate_sky_lights(sky_pixels, params, self.generate_light_count, vertical_fov)
            if need_light_samples
            else []
        )
        sun_sample = get_sun_light(params)

        if self.generate_type in {"BOTH", "SKYLIGHT"}:
            self._create_light_objects(collection, params, sky_light_samples, sun_sample)

        lit_mesh_count = 0
        if self.lit_objects_by_sky:
            lighting_samples = list(sky_light_samples)
            lighting_samples.append(sun_sample)
            lit_mesh_count = self._light_selected_meshes(context, params, lighting_samples)
            
        is_blender_scale = scene_nwo.scale == 'blender'
        rotation = utils.blender_halo_rotation_diff(scene_nwo.forward_direction)
        print(rotation)
        if not is_blender_scale or rotation != 0.0:
            utils.transform_scene(context, 1 if is_blender_scale else (1 / 0.03048), rotation, 'x', scene_nwo.forward_direction, objects=collection.all_objects, actions=[])

        message_parts = []
        if dome_object is not None:
            message_parts.append("skydome")
        if self.generate_type in {"BOTH", "SKYLIGHT"}:
            total_lights = len(sky_light_samples) + 1
            message_parts.append(f"{total_lights} light{'s' if total_lights != 1 else ''}")
        if self.lit_objects_by_sky:
            message_parts.append(f"lit {lit_mesh_count} mesh{'es' if lit_mesh_count != 1 else ''}")

        self.report({"INFO"}, f"Generated {', '.join(message_parts)}")
        return {"FINISHED"}

    def _build_parameters(self) -> SkyAtmosphereParameters:
        return SkyAtmosphereParameters(
            sun_theta=math.radians(self.sun_theta),
            sun_phi=math.radians(self.sun_phi % 360.0),
            turbidity=self.turpidity,
            sky_type=SKY_TYPE_MAP[self.sky_type],
            cie_sky_number=self.cie_sky_number,
            sky_intensity=self.sky_intensity,
            sun_intensity=self.sun_intensity,
            luminance_only=self.luminance_only,
            exposure=self.exposure,
            sun_cone_angle=math.radians(self.sun_cone_angle),
            custom_sun_color_override=self.custom_sun_color_override,
            sun_color_override=tuple(self.sun_color),
            sky_dome_radius=self.sky_dome_radius,
            zenith_color=tuple(self.zenith_color),
            haze_color=tuple(self.haze_color),
            override_zenith_color=self.override_zenith_color,
            override_horizon_color=self.override_horizon_color,
            horizon_haze_height=self.horizon_haze_height,
            sun_blur=self.sun_blur,
        )

    def _get_sky_pixels(self, context: bpy.types.Context, params: SkyAtmosphereParameters) -> np.ndarray:
        if self.build_sky_from_map == "WORLD":
            world_image = _find_world_sky_image(context.scene)
            if world_image is None:
                raise ValueError("The active Blender scene World does not have an environment or image texture to sample")
            return _load_sky_image_from_image(world_image, world_image.name)

        if self.build_sky_from_map == "FILE":
            sky_map = self.input_sky_map_name.strip()
            if not sky_map:
                raise ValueError("Sky map path is required when 'Image File' is selected as the sky source")
            return _load_sky_image_pixels(sky_map)

        return build_analytic_sky_image(ANALYTIC_SKY_WIDTH, ANALYTIC_SKY_HEIGHT, params)

    def _create_dome_object(
        self,
        collection: bpy.types.Collection,
        sky_pixels: np.ndarray,
        params: SkyAtmosphereParameters,
        horizontal_fov: float,
        vertical_fov: float,
    ) -> bpy.types.Object:
        vertices, faces, colors, texcoords = build_sky_dome_data(
            sky_pixels,
            params,
            self.lattitude_slices,
            self.longitude_slices,
            horizontal_fov,
            vertical_fov,
            clamp=True,
        )

        mesh = bpy.data.meshes.new(SKY_GEN_DOME_OBJECT)
        mesh.from_pydata(vertices, [], faces)

        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        for polygon in mesh.polygons:
            for vertex_index, loop_index in zip(polygon.vertices, polygon.loop_indices):
                uv_layer.data[loop_index].uv = texcoords[vertex_index]
            polygon.use_smooth = True

        color_attribute = _ensure_color_attribute(mesh, SKY_GEN_COLOR_ATTRIBUTE)
        _apply_vertex_colors(color_attribute, np.asarray(colors, dtype=np.float32))

        material = _ensure_dome_material()
        if mesh.materials:
            mesh.materials[0] = material
        else:
            mesh.materials.append(material)

        ob = bpy.data.objects.new(SKY_GEN_DOME_OBJECT, mesh)
        _mark_generated(ob, "dome")
        utils.set_region(ob, _default_region_name())
        utils.set_permutation(ob, _default_permutation_name())
        collection.objects.link(ob)
        return ob

    def _create_light_objects(
        self,
        collection: bpy.types.Collection,
        params: SkyAtmosphereParameters,
        sky_light_samples: list[SkyLightSample],
        sun_sample: SkyLightSample,
    ):
        radius = params.sky_dome_radius * 0.85
        sun_radius = radius * 1.5
        scene_nwo = utils.get_scene_props()

        for index, sample in enumerate(sky_light_samples):
            data = bpy.data.lights.new(f"skylight:{index}", "SUN")
            data.energy = float(sample.solid_angle)
            data.color = sample.color
            data.angle = _solid_angle_to_angle(sample.solid_angle)

            ob = bpy.data.objects.new(data.name, data)
            _mark_generated(ob, "skylight")
            _position_light_object(ob, sample.direction, radius)
            collection.objects.link(ob)

        # if scene_nwo.sun_as_vmf_light:
        #     data = bpy.data.lights.new(f"skylight:{len(sky_light_samples)}", "SUN")
        #     data.energy = float(sun_sample.solid_angle)
        #     data.color = sun_sample.color
        #     data.angle = math.radians(self.sun_cone_angle)

        #     ob = bpy.data.objects.new(data.name, data)
        #     _mark_generated(ob, "sun_vmf")
        #     _position_light_object(ob, sun_sample.direction, sun_radius)
        #     collection.objects.link(ob)
        #     return

        # Match the render-model import path: the standalone Blender sun should
        # use the sun's integrated RGB intensity, not the raw radiance sample.
        sun_color, sun_energy = _encode_light_color_energy(_integrate_light_sample_color(sun_sample))
        data = bpy.data.lights.new("Sun", "SUN")
        data.energy = sun_energy
        data.color = sun_color
        data.angle = math.radians(self.sun_cone_angle)

        ob = bpy.data.objects.new(data.name, data)
        _mark_generated(ob, "sun")
        _position_light_object(ob, sun_sample.direction, sun_radius)
        collection.objects.link(ob)

    def _light_selected_meshes(
        self,
        context: bpy.types.Context,
        params: SkyAtmosphereParameters,
        lighting_samples: list[SkyLightSample],
    ) -> int:
        lit_object_count = 0

        for ob in context.selected_objects:
            if ob.type != "MESH" or ob.get(SKY_GEN_MARKER):
                continue

            mesh = _ensure_unique_mesh_data(ob)
            vertex_count = len(mesh.vertices)
            if vertex_count == 0:
                continue

            local_positions = np.empty(vertex_count * 3, dtype=np.float32)
            local_normals = np.empty(vertex_count * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", local_positions)
            mesh.vertices.foreach_get("normal", local_normals)

            local_positions = local_positions.reshape(vertex_count, 3)
            local_normals = local_normals.reshape(vertex_count, 3)

            world_matrix = np.array(ob.matrix_world, dtype=np.float32)
            position_matrix = world_matrix[:3, :3]
            translation = world_matrix[:3, 3]
            positions = local_positions @ position_matrix.T + translation

            normal_matrix = np.array(ob.matrix_world.inverted_safe().transposed().to_3x3(), dtype=np.float32)
            normals = local_normals @ normal_matrix.T
            normal_lengths = np.linalg.norm(normals, axis=1, keepdims=True)
            normals = np.divide(
                normals,
                np.where(normal_lengths <= EPSILON, 1.0, normal_lengths),
                out=np.zeros_like(normals),
            )

            sky_color = modifier_apply_sky_color(positions, params, clamp=True)
            sun_lighting = modifier_apply_sun_lighting(normals, params, clamp=True)
            sky_lighting = modifier_apply_sky_lighting(normals, params, lighting_samples, clamp=True)

            _apply_vertex_colors(_ensure_color_attribute(mesh, "sky_color"), sky_color)
            _apply_vertex_colors(_ensure_color_attribute(mesh, "sun_lighting"), sun_lighting)
            _apply_vertex_colors(_ensure_color_attribute(mesh, "sky_lighting"), sky_lighting)

            mesh.update()
            lit_object_count += 1

        return lit_object_count


__all__ = ("NWO_OT_SkyGenerate",)
