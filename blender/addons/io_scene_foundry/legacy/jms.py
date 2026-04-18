from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import sint, to_quaternion, to_vector
from .. import utils
from ..tools.property_apply import halo_material

BOUNDARY_SURFACE_TYPES = {
    "soft_ceiling": "SOFT_CEILING",
    "soft_kill": "SOFT_KILL",
    "slip_surface": "SLIP_SURFACE",
}
LIGHTMAP_PATTERN = re.compile(r"(" + "|".join(re.escape(prefix) for prefix in utils.legacy_lightmap_prefixes) + r")(\d+\.?\d*)")
MARKER_TYPE_MAP = {
    "effects": "_connected_geometry_marker_type_effects",
    "garbage": "_connected_geometry_marker_type_garbage",
    "hint": "_connected_geometry_marker_type_hint",
    "model": "_connected_geometry_marker_type_model",
    "physics_constraint": "_connected_geometry_marker_type_physics_constraint",
    "target": "_connected_geometry_marker_type_target",
}
MODELISH_PREFIXES = ("b_", "bip_", "bone_", "frame_", "frame ")
SUPPORTED_VERSIONS = set(range(8197, 8214))


@dataclass
class Node:
    name: str
    parent_index: int
    rotation: Quaternion
    translation: Vector


@dataclass
class MaterialProperties:
    two_sided: bool = False
    transparent_one_sided: bool = False
    transparent_two_sided: bool = False
    render_only: bool = False
    collision_only: bool = False
    sphere_collision_only: bool = False
    fog_plane: bool = False
    ladder: bool = False
    breakable: bool = False
    ai_deafening: bool = False
    no_shadow: bool = False
    shadow_only: bool = False
    lightmap_only: bool = False
    precise: bool = False
    portal_one_way: bool = False
    portal_door: bool = False
    portal_vis_blocker: bool = False
    ignored_by_lightmaps: bool = False
    blocks_sound: bool = False
    decal_offset: bool = False
    water_surface: bool = False
    slip_surface: bool = False
    lightmap_resolution_scale: int | None = None
    lightmap_additive_transparency: tuple[float, float, float] | None = None
    lightmap_translucency_tint_color: tuple[float, float, float] | None = None
    lightmap_transparency_override: bool = False
    mesh_type: str = "default"

    @property
    def portal_signature(self) -> tuple[bool, bool, bool, bool, bool]:
        return (
            self.ai_deafening,
            self.portal_one_way,
            self.portal_door,
            self.portal_vis_blocker,
            self.blocks_sound,
        )


@dataclass
class Material:
    index: int
    name: str
    definition: str
    slot_index: int | None
    permutation: str
    region: str
    lod: str | None = None
    props: MaterialProperties = field(default_factory=MaterialProperties)

    @property
    def clean_name(self) -> str:
        base = utils.base_material_name(self.name, strip_legacy_halo_names=True).strip()
        if not base:
            base = self.name.strip()
        return utils.get_valid_shader_name(base) or "invalid"


@dataclass
class Marker:
    name: str
    node_index: int
    rotation: Quaternion
    translation: Vector
    radius: float = 1.0
    region_index: int = -1


@dataclass
class Xref:
    path: str
    name: str


@dataclass
class InstanceMarker:
    name: str
    unique_identifier: int | None
    path_index: int
    rotation: Quaternion
    translation: Vector


@dataclass
class NodeInfluence:
    index: int
    weight: float


@dataclass
class TextureCoordinate:
    u: float
    v: float


@dataclass
class Vertex:
    position: Vector
    normal: Vector
    node_influences: list[NodeInfluence] = field(default_factory=list)
    texture_coordinates: list[TextureCoordinate] = field(default_factory=list)
    color: Vector | None = None
    region_index: int | None = None


@dataclass
class Triangle:
    material_index: int
    vertex_indices: tuple[int, int, int]
    region_index: int | None = None


@dataclass
class Sphere:
    name: str
    parent_index: int
    material_index: int | None
    rotation: Quaternion
    translation: Vector
    radius: float


@dataclass
class Box:
    name: str
    parent_index: int
    material_index: int | None
    rotation: Quaternion
    translation: Vector
    width: float
    length: float
    height: float


@dataclass
class Capsule:
    name: str
    parent_index: int
    material_index: int | None
    rotation: Quaternion
    translation: Vector
    height: float
    radius: float


@dataclass
class ConvexShape:
    name: str
    parent_index: int
    material_index: int | None
    rotation: Quaternion
    translation: Vector
    vertices: list[Vector] = field(default_factory=list)


@dataclass
class RagdollConstraint:
    name: str
    attached_index: int
    referenced_index: int
    attached_rotation: Quaternion
    attached_translation: Vector
    referenced_rotation: Quaternion
    referenced_translation: Vector
    min_twist: float
    max_twist: float
    min_cone: float
    max_cone: float
    min_plane: float
    max_plane: float
    friction_limit: float = 0.0


@dataclass
class HingeConstraint:
    name: str
    body_a_index: int
    body_b_index: int
    body_a_rotation: Quaternion
    body_a_translation: Vector
    body_b_rotation: Quaternion
    body_b_translation: Vector
    is_limited: bool
    friction_limit: float
    min_angle: float
    max_angle: float


@dataclass
class PointToPointConstraint:
    name: str
    body_a_index: int
    body_b_index: int
    body_a_rotation: Quaternion
    body_a_translation: Vector
    body_b_rotation: Quaternion
    body_b_translation: Vector
    constraint_type: int
    x_min_limit: float
    x_max_limit: float
    y_min_limit: float
    y_max_limit: float
    z_min_limit: float
    z_max_limit: float
    spring_length: float


@dataclass
class PrismaticConstraint:
    name: str
    body_a_index: int
    body_b_index: int
    body_a_rotation: Quaternion
    body_a_translation: Vector
    body_b_rotation: Quaternion
    body_b_translation: Vector
    is_limited: bool
    friction_limit: float
    min_limit: float
    max_limit: float


@dataclass
class BoundingSphere:
    translation: Vector
    radius: float


@dataclass
class Skylight:
    direction: Vector
    radiant_intensity: Vector
    solid_angle: float


@dataclass
class JMSImportResult:
    marker_objects: list[bpy.types.Object] = field(default_factory=list)
    mesh_objects: list[bpy.types.Object] = field(default_factory=list)
    frame_objects: list[bpy.types.Object] = field(default_factory=list)
    light_objects: list[bpy.types.Object] = field(default_factory=list)
    hidden_objects: list[bpy.types.Object] = field(default_factory=list)
    armature: bpy.types.Object | None = None


class _LineReader:
    def __init__(self, filepath: Path | str):
        self.lines = [line for line in (line.partition(";")[0].strip() for line in Path(filepath).read_text().splitlines()) if line]
        self.index = 0

    def next(self) -> str:
        if self.index >= len(self.lines):
            raise EOFError("Unexpected end of JMS file")
        value = self.lines[self.index]
        self.index += 1
        return value

    def next_int(self) -> int:
        return sint(self.next())

    def next_float(self) -> float:
        return float(self.next())

    def next_vector(self) -> Vector:
        return to_vector(self.next())

    def next_quaternion(self) -> Quaternion:
        return to_quaternion(self.next())


def _parse_material_definition(definition: str) -> tuple[int | None, str | None, str, str]:
    slot_index = None
    lod = None
    permutation = "default"
    region = "default"
    payload: list[str] = []
    for part in definition.split():
        lower = part.lower()
        if lower.startswith("(") and lower.endswith(")") and slot_index is None:
            try:
                slot_index = sint(part.strip("()"))
            except ValueError:
                slot_index = None
        elif lower in {"l1", "l2", "l3", "l4", "l5", "l6"} and lod is None:
            lod = lower
        else:
            payload.append(part)
    if payload:
        permutation = payload[0]
    if len(payload) > 1:
        region = payload[1]
    return slot_index, lod, permutation or "default", region or "default"


def _material_props_from_name(name: str) -> MaterialProperties:
    props = MaterialProperties(
        two_sided="%" in name,
        transparent_one_sided="#" in name,
        transparent_two_sided="?" in name,
        render_only="!" in name,
        collision_only="@" in name,
        sphere_collision_only="*" in name,
        fog_plane="$" in name,
        ladder="^" in name,
        breakable="-" in name,
        ai_deafening="&" in name,
        no_shadow="=" in name,
        lightmap_only=";" in name,
        precise=")" in name,
        portal_one_way="<" in name,
        portal_door="|" in name,
        portal_vis_blocker="~" in name,
        ignored_by_lightmaps="{" in name,
        blocks_sound="}" in name,
        decal_offset="[" in name,
        water_surface="'" in name,
    )
    for prefix, value in LIGHTMAP_PATTERN.findall(name):
        if prefix == "lm:":
            props.lightmap_resolution_scale = utils.clamp(int(float(value) * 3), 1, 7)
    return props


def _mesh_type_from_material_name(name: str, props: MaterialProperties) -> str:
    lower = name.lower()
    if lower.startswith("+portal") or props.portal_one_way or props.portal_vis_blocker:
        return "portal"
    if lower.startswith("+seam") and not lower.startswith("+seams"):
        return "seam"
    if lower.startswith("+soft_ceiling"):
        return "soft_ceiling"
    if lower.startswith("+soft_kill"):
        return "soft_kill"
    if lower.startswith("+slip_surface"):
        return "slip_surface"
    if props.fog_plane:
        return "fog"
    if props.water_surface:
        return "water_surface"
    return "default"


def _mesh_type_and_helper_material(mesh_type_key: str, is_model: bool) -> tuple[str, str]:
    material = ""
    match mesh_type_key:
        case "collision":
            if is_model:
                mesh_type = "_connected_geometry_mesh_type_collision"
                material = "Collision"
            else:
                mesh_type = "_connected_geometry_mesh_type_structure"
        case "physics":
            mesh_type = "_connected_geometry_mesh_type_physics"
            material = "Physics"
        case "default":
            mesh_type = "_connected_geometry_mesh_type_default" if is_model else "_connected_geometry_mesh_type_structure"
        case "seam":
            mesh_type = "_connected_geometry_mesh_type_seam"
            material = "Seam"
        case "portal":
            mesh_type = "_connected_geometry_mesh_type_portal"
            material = "Portal"
        case "water_surface":
            mesh_type = "_connected_geometry_mesh_type_water_surface"
        case "fog":
            mesh_type = "_connected_geometry_mesh_type_planar_fog_volume"
            material = "Fog"
        case "soft_ceiling":
            mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            material = "SoftCeiling"
        case "soft_kill":
            mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            material = "SoftKill"
        case "slip_surface":
            mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            material = "SlipSurface"
        case _:
            mesh_type = "_connected_geometry_mesh_type_default" if is_model else "_connected_geometry_mesh_type_structure"
    return mesh_type, material


def _helper_material_required(mesh_type_key: str, file_kind: str, is_model: bool, helper_material_name: str) -> bool:
    if helper_material_name and mesh_type_key in {"seam", "portal", "fog", "soft_ceiling", "soft_kill", "slip_surface"}:
        return True
    return helper_material_name != "" and file_kind in {"collision", "physics"} and is_model


def _bool_face_map(length: int, indices: list[int]) -> np.ndarray | None:
    if not indices:
        return None
    values = np.zeros(length, dtype=np.int8)
    values[indices] = 1
    return values


class JMS:
    def __init__(self):
        self.filepath = Path()
        self.name = ""
        self.version = 8213
        self.file_kind = "render"
        self.nodes: list[Node] = []
        self.materials: list[Material] = []
        self.markers: list[Marker] = []
        self.xref_instances: list[Xref] = []
        self.xref_markers: list[InstanceMarker] = []
        self.regions: list[str] = []
        self.vertices: list[Vertex] = []
        self.triangles: list[Triangle] = []
        self.spheres: list[Sphere] = []
        self.boxes: list[Box] = []
        self.capsules: list[Capsule] = []
        self.convex_shapes: list[ConvexShape] = []
        self.ragdolls: list[RagdollConstraint] = []
        self.hinges: list[HingeConstraint] = []
        self.point_to_points: list[PointToPointConstraint] = []
        self.prismatics: list[PrismaticConstraint] = []
        self.bounding_spheres: list[BoundingSphere] = []
        self.skylights: list[Skylight] = []

    def from_file(self, filepath: Path | str):
        self.__init__()
        self.filepath = Path(filepath)
        self.name = self.filepath.with_suffix("").name
        self.file_kind = self._infer_file_kind(self.filepath)
        reader = _LineReader(filepath)

        self.version = reader.next_int()
        if self.version not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported JMS version: {self.version}")

        if self.version < 8205:
            reader.next_int()

        node_count = reader.next_int()
        raw_nodes: list[dict] = []
        if self.version >= 8205:
            for _ in range(node_count):
                raw_nodes.append(
                    {
                        "name": reader.next(),
                        "parent": reader.next_int(),
                        "rotation": reader.next_quaternion(),
                        "translation": reader.next_vector(),
                    }
                )
        else:
            child_indices = []
            sibling_indices = []
            for _ in range(node_count):
                name = reader.next()
                child_indices.append(reader.next_int())
                sibling_indices.append(reader.next_int())
                raw_nodes.append(
                    {
                        "name": name,
                        "rotation": reader.next_quaternion(),
                        "translation": reader.next_vector(),
                    }
                )

            parent_lookup = [-1] * node_count

            def assign_parents(index: int, parent: int):
                if index == -1:
                    return
                parent_lookup[index] = parent
                assign_parents(child_indices[index], index)
                assign_parents(sibling_indices[index], parent)

            assign_parents(0, -1)
            for index, raw_node in enumerate(raw_nodes):
                raw_node["parent"] = parent_lookup[index]

        for raw_node in raw_nodes:
            self.nodes.append(Node(raw_node["name"], raw_node["parent"], raw_node["rotation"], raw_node["translation"]))

        material_count = reader.next_int()
        for material_index in range(material_count):
            name = reader.next()
            if 8202 <= self.version <= 8204:
                reader.next()
            definition = reader.next()
            slot_index, lod, permutation, region = _parse_material_definition(definition)
            props = _material_props_from_name(name)
            props.slip_surface = name.lower().startswith("+slip_surface")
            props.mesh_type = _mesh_type_from_material_name(name, props)
            self.materials.append(Material(material_index, name, definition, slot_index, permutation, region, lod, props))

        marker_count = reader.next_int()
        for _ in range(marker_count):
            name = reader.next()
            region_index = reader.next_int() if 8198 <= self.version < 8205 else -1
            node_index = reader.next_int()
            rotation = reader.next_quaternion()
            translation = reader.next_vector()
            radius = reader.next_float() if self.version >= 8200 else 1.0
            self.markers.append(Marker(name, node_index, rotation, translation, radius, region_index))

        if self.version >= 8201:
            xref_count = reader.next_int()
            for _ in range(xref_count):
                path = reader.next()
                name = reader.next() if self.version >= 8208 else ""
                self.xref_instances.append(Xref(path, name))

            xref_marker_count = reader.next_int()
            for _ in range(xref_marker_count):
                name = reader.next()
                unique_identifier = reader.next_int() if self.version >= 8203 else None
                path_index = reader.next_int()
                rotation = reader.next_quaternion()
                translation = reader.next_vector()
                self.xref_markers.append(InstanceMarker(name, unique_identifier, path_index, rotation, translation))

        if self.version < 8205:
            region_count = reader.next_int()
            for _ in range(region_count):
                region_name = reader.next()
                if region_name == "__unnamed":
                    region_name = "unnamed"
                self.regions.append(region_name)

        vertex_count = reader.next_int()
        for _ in range(vertex_count):
            region_index = None
            node_influences: list[NodeInfluence] = []
            texture_coordinates: list[TextureCoordinate] = []
            color = None
            if self.version >= 8205:
                position = reader.next_vector()
                normal = reader.next_vector()
                influence_count = reader.next_int()
                for _ in range(influence_count):
                    node_influences.append(NodeInfluence(reader.next_int(), reader.next_float()))
                uv_count = reader.next_int()
                for _ in range(uv_count):
                    texture_coordinates.append(TextureCoordinate(*reader.next_vector().to_tuple()))
                if self.version >= 8211:
                    color = reader.next_vector()
            else:
                if self.version == 8197:
                    region_index = reader.next_int()
                node_0_index = reader.next_int()
                node_0_weight = reader.next_float() if self.version == 8204 else 1.0
                position = reader.next_vector()
                normal = reader.next_vector()
                node_1_index = reader.next_int()
                node_1_weight = reader.next_float()
                node_indices = [(node_0_index, node_0_weight), (node_1_index, node_1_weight)]
                if self.version == 8204:
                    node_indices.extend(
                        [
                            (reader.next_int(), reader.next_float()),
                            (reader.next_int(), reader.next_float()),
                        ]
                    )
                node_influences = [NodeInfluence(index, weight) for index, weight in node_indices if index != -1]
                uv_pairs = [(reader.next_float(), reader.next_float())]
                if self.version >= 8202:
                    extras = [(reader.next_float(), reader.next_float()) for _ in range(3)]
                    if self.version >= 8203:
                        uv_pairs.extend(extras)
                texture_coordinates = [TextureCoordinate(u, v) for u, v in uv_pairs]
                if self.version >= 8199:
                    reader.next_int()
            self.vertices.append(Vertex(position, normal, node_influences, texture_coordinates, color, region_index))

        triangle_count = reader.next_int()
        for _ in range(triangle_count):
            region_index = reader.next_int() if 8198 <= self.version < 8205 else None
            material_index = reader.next_int()
            self.triangles.append(Triangle(material_index, tuple([int(n) for n in reader.next_vector().to_tuple()]), region_index))

        if self.version >= 8206:
            sphere_count = reader.next_int()
            for _ in range(sphere_count):
                name = reader.next()
                parent_index = reader.next_int()
                material_index = reader.next_int() if self.version >= 8207 else None
                self.spheres.append(Sphere(name, parent_index, material_index, reader.next_quaternion(), reader.next_vector(), reader.next_float()))

            box_count = reader.next_int()
            for _ in range(box_count):
                name = reader.next()
                parent_index = reader.next_int()
                material_index = reader.next_int() if self.version >= 8207 else None
                self.boxes.append(Box(name, parent_index, material_index, reader.next_quaternion(), reader.next_vector(), reader.next_float(), reader.next_float(), reader.next_float()))

            capsule_count = reader.next_int()
            for _ in range(capsule_count):
                name = reader.next()
                parent_index = reader.next_int()
                material_index = reader.next_int() if self.version >= 8207 else None
                self.capsules.append(Capsule(name, parent_index, material_index, reader.next_quaternion(), reader.next_vector(), reader.next_float(), reader.next_float()))

            convex_shape_count = reader.next_int()
            for _ in range(convex_shape_count):
                name = reader.next()
                parent_index = reader.next_int()
                material_index = reader.next_int() if self.version >= 8207 else None
                rotation = reader.next_quaternion()
                translation = reader.next_vector()
                vertex_count = reader.next_int()
                vertices = [reader.next_vector() for _ in range(vertex_count)]
                self.convex_shapes.append(ConvexShape(name, parent_index, material_index, rotation, translation, vertices))

            ragdoll_count = reader.next_int()
            for _ in range(ragdoll_count):
                self.ragdolls.append(
                    RagdollConstraint(
                        reader.next(),
                        reader.next_int(),
                        reader.next_int(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float() if self.version >= 8213 else 0.0,
                    )
                )

            hinge_count = reader.next_int()
            for _ in range(hinge_count):
                self.hinges.append(
                    HingeConstraint(
                        reader.next(),
                        reader.next_int(),
                        reader.next_int(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        bool(reader.next_int()),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                    )
                )

        if self.version >= 8210:
            car_wheel_count = reader.next_int()
            for _ in range(car_wheel_count):
                reader.next()
                reader.next_int()
                reader.next_int()
                reader.next_quaternion()
                reader.next_vector()
                reader.next_quaternion()
                reader.next_vector()
                reader.next_float()
                reader.next_float()
                reader.next_float()
                reader.next_float()
                reader.next_float()

            point_to_point_count = reader.next_int()
            for _ in range(point_to_point_count):
                self.point_to_points.append(
                    PointToPointConstraint(
                        reader.next(),
                        reader.next_int(),
                        reader.next_int(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        reader.next_int(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                    )
                )

            prismatic_count = reader.next_int()
            for _ in range(prismatic_count):
                self.prismatics.append(
                    PrismaticConstraint(
                        reader.next(),
                        reader.next_int(),
                        reader.next_int(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        reader.next_quaternion(),
                        reader.next_vector(),
                        bool(reader.next_int()),
                        reader.next_float(),
                        reader.next_float(),
                        reader.next_float(),
                    )
                )

        if self.version >= 8209:
            bounding_sphere_count = reader.next_int()
            for _ in range(bounding_sphere_count):
                self.bounding_spheres.append(BoundingSphere(reader.next_vector(), reader.next_float()))

        if self.version >= 8212:
            skylight_count = reader.next_int()
            for _ in range(skylight_count):
                self.skylights.append(Skylight(reader.next_vector(), reader.next_vector(), reader.next_float()))

        return self

    def looks_like_model(self) -> bool:
        if self.file_kind in {"collision", "physics"}:
            return True
        if not self.nodes:
            return False
        names = [node.name.lower() for node in self.nodes]
        prefix_matches = sum(name.startswith(MODELISH_PREFIXES) for name in names)
        return prefix_matches >= max(1, len(names) // 4)

    def build(self, collection: bpy.types.Collection, *, is_model: bool = True, existing_armature: bpy.types.Object | None = None, context=None) -> JMSImportResult:
        builder = _JMSSceneBuilder(self, collection, is_model=is_model, existing_armature=existing_armature, context=context)
        return builder.build()

    @staticmethod
    def _infer_file_kind(filepath: Path) -> str:
        lower_parts = [part.lower() for part in filepath.parts]
        lower_name = filepath.stem.lower()
        if any("physics" in part for part in lower_parts) or "physics" in lower_name:
            return "physics"
        if any("collision" in part for part in lower_parts) or "collision" in lower_name:
            return "collision"
        return "render"


class _JMSSceneBuilder:
    def __init__(
        self,
        jms: JMS,
        collection: bpy.types.Collection,
        *,
        is_model: bool,
        existing_armature: bpy.types.Object | None,
        context,
    ):
        self.jms = jms
        self.collection = collection
        self.is_model = is_model
        self.existing_armature = existing_armature
        self.context = context or bpy.context
        self.result = JMSImportResult()
        self.node_world_matrices = self._node_world_matrices()
        self.frame_objects: dict[int, bpy.types.Object] = {}
        self.armature: bpy.types.Object | None = None

    def build(self) -> JMSImportResult:
        if self.is_model:
            self.armature = self._get_or_create_armature()
            self.result.armature = self.armature
            if self.armature is not None:
                self.result.frame_objects.append(self.armature)
        else:
            self._build_frames()

        self._build_markers()
        self._build_xref_markers()
        self._build_triangle_meshes()
        self._build_primitives()
        self._build_constraints()

        return self.result

    def _node_world_matrices(self) -> list[Matrix]:
        local_matrices = [Matrix.Translation(node.translation) @ node.rotation.to_matrix().to_4x4() for node in self.jms.nodes]
        world_matrices = [Matrix.Identity(4) for _ in self.jms.nodes]
        for index, node in enumerate(self.jms.nodes):
            if self.jms.version >= 8205 or node.parent_index == -1:
                world_matrices[index] = local_matrices[index]
            else:
                world_matrices[index] = world_matrices[node.parent_index] @ local_matrices[index]
        return world_matrices

    def _armature_matches(self, armature: bpy.types.Object | None) -> bool:
        if armature is None or armature.type != "ARMATURE":
            return False
        bone_names = {bone.name for bone in armature.data.bones}
        return len(bone_names.intersection({node.name for node in self.jms.nodes})) == len(self.jms.nodes)

    def _get_or_create_armature(self) -> bpy.types.Object | None:
        if self._armature_matches(self.existing_armature):
            return self.existing_armature

        armature_data = bpy.data.armatures.new(self.jms.name)
        armature = bpy.data.objects.new(self.jms.name, armature_data)
        self.collection.objects.link(armature)
        self._build_armature_bones(armature)
        return armature

    def _build_armature_bones(self, armature: bpy.types.Object):
        utils.set_object_mode(bpy.context)
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        utils.set_active_object(armature)
        bpy.ops.object.editmode_toggle()
        edit_bones = armature.data.edit_bones
        for index, node in enumerate(self.jms.nodes):
            bone = edit_bones.new(node.name)
            bone.tail[2] = self._bone_length(index)
            if node.parent_index > -1:
                bone.parent = edit_bones[self.jms.nodes[node.parent_index].name]
            matrix = self.node_world_matrices[index] if self.jms.version >= 8205 else self._legacy_edit_bone_matrix(index, edit_bones)
            bone.matrix = matrix
            if bone.length <= 0.0001:
                bone.length = self._bone_length(index)
        utils.set_object_mode(bpy.context)
        self.context.view_layer.update()

    def _legacy_edit_bone_matrix(self, index: int, edit_bones) -> Matrix:
        node = self.jms.nodes[index]
        local = Matrix.Translation(node.translation) @ node.rotation.to_matrix().to_4x4()
        if node.parent_index > -1:
            parent_name = self.jms.nodes[node.parent_index].name
            return edit_bones[parent_name].matrix @ local
        return local

    def _bone_length(self, index: int) -> float:
        child_distances = [
            (self.jms.nodes[child_index].translation - self.jms.nodes[index].translation).length
            for child_index, child in enumerate(self.jms.nodes)
            if child.parent_index == index
        ]
        if child_distances:
            return max(min(child_distances), 0.1)
        return 1.0

    def _build_frames(self):
        for index, node in enumerate(self.jms.nodes):
            frame = bpy.data.objects.new(node.name, None)
            frame.empty_display_type = "ARROWS"
            frame.nwo.is_frame = True
            frame.matrix_world = self.node_world_matrices[index]
            if node.parent_index > -1:
                frame.parent = self.frame_objects[node.parent_index]
            self.collection.objects.link(frame)
            self.frame_objects[index] = frame
            self.result.frame_objects.append(frame)

    def _build_markers(self):
        for marker in self.jms.markers:
            marker_object = bpy.data.objects.new(marker.name, None)
            marker_type = self._marker_type_from_name(marker.name)
            marker_object.empty_display_type = "SPHERE" if marker_type == MARKER_TYPE_MAP["target"] else "ARROWS"
            marker_object.empty_display_size = abs(marker.radius) if marker.radius > 0 else 1.0
            marker_object.nwo.marker_type = marker_type
            marker_object.matrix_world = self._node_parent_matrix(marker.node_index) @ self._local_transform(marker.translation, marker.rotation)
            if self.is_model and self.armature is not None and marker.node_index > -1:
                self._parent_to_bone(marker_object, marker.node_index)
            elif not self.is_model and marker.node_index > -1 and marker.node_index in self.frame_objects:
                marker_object.parent = self.frame_objects[marker.node_index]

            if 0 <= marker.region_index < len(self.jms.regions):
                utils.set_region(marker_object, self.jms.regions[marker.region_index])
                marker_object.nwo.marker_uses_regions = True

            self.collection.objects.link(marker_object)
            self.result.marker_objects.append(marker_object)

    def _build_xref_markers(self):
        for marker in self.jms.xref_markers:
            marker_object = bpy.data.objects.new(marker.name, None)
            marker_object.empty_display_type = "ARROWS"
            marker_object.empty_display_size = 1.0
            marker_object.nwo.marker_type = "_connected_geometry_marker_type_game_instance"
            marker_object.matrix_world = self._local_transform(marker.translation, marker.rotation)
            xref = self.jms.xref_instances[marker.path_index] if 0 <= marker.path_index < len(self.jms.xref_instances) else None
            if xref is not None:
                marker_object.nwo.marker_game_instance_tag_name = self._resolve_xref_tag_path(marker.name, xref)
            self.collection.objects.link(marker_object)
            self.result.marker_objects.append(marker_object)

    def _resolve_xref_tag_path(self, marker_name: str, xref: Xref) -> str:
        preferred_type = ".device_machine" if marker_name.lower().startswith("?") else ".crate"
        if xref.path and xref.name:
            relative_path = utils.any_partition(xref.path, "\\data\\", True)
            candidate = Path(utils.get_tags_path(), Path(relative_path).parent, xref.name, f"{xref.name}{preferred_type}")
            if candidate.exists():
                return utils.relative_path(candidate)
            return str(candidate)
        return xref.name

    def _build_triangle_meshes(self):
        if not self.jms.triangles or not self.jms.vertices:
            return

        grouped_triangles: dict[tuple[str, str, str, tuple[bool, bool, bool, bool, bool]], list[tuple[int, Triangle]]] = defaultdict(list)
        for triangle_index, triangle in enumerate(self.jms.triangles):
            material = self.jms.materials[triangle.material_index] if 0 <= triangle.material_index < len(self.jms.materials) else None
            if self.jms.file_kind in {"collision", "physics"}:
                mesh_type_key = self.jms.file_kind
            elif material is not None:
                mesh_type_key = material.props.mesh_type
            else:
                mesh_type_key = "default"
            region, permutation = self._triangle_region_permutation(triangle, material)
            portal_signature = material.props.portal_signature if material is not None else (False, False, False, False, False)
            grouped_triangles[(mesh_type_key, region, permutation, portal_signature)].append((triangle_index, triangle))

        for group_key, scoped_triangles in grouped_triangles.items():
            self._build_triangle_group(group_key, scoped_triangles)

    def _build_triangle_group(self, group_key, scoped_triangles):
        mesh_type_key, region, permutation, portal_signature = group_key
        mesh_type, helper_material_name = _mesh_type_and_helper_material(mesh_type_key, self.is_model)
        use_helper_material = _helper_material_required(mesh_type_key, self.jms.file_kind, self.is_model, helper_material_name)

        vertex_lookup: dict[int, int] = {}
        local_vertices: list[Vertex] = []
        faces: list[tuple[int, int, int]] = []
        triangle_materials: list[int] = []
        triangle_original_indices: list[int] = []

        for triangle_index, triangle in scoped_triangles:
            local_face = []
            for vertex_index in triangle.vertex_indices:
                if vertex_index not in vertex_lookup:
                    vertex_lookup[vertex_index] = len(local_vertices)
                    local_vertices.append(self.jms.vertices[vertex_index])
                local_face.append(vertex_lookup[vertex_index])
            if len(set(local_face)) < 3:
                continue
            faces.append(tuple(local_face))
            triangle_materials.append(triangle.material_index)
            triangle_original_indices.append(triangle_index)

        if not faces:
            return

        mesh = bpy.data.meshes.new(self._group_name(region, permutation, mesh_type_key))
        mesh.from_pydata([tuple(vertex.position) for vertex in local_vertices], [], faces)
        mesh.update()
        mesh.nwo.mesh_type = mesh_type
        if mesh_type_key in BOUNDARY_SURFACE_TYPES:
            mesh.nwo.boundary_surface_type = BOUNDARY_SURFACE_TYPES[mesh_type_key]

        if use_helper_material:
            mesh.materials.append(halo_material(helper_material_name))
            slot_lookup: dict[str, int] = defaultdict(int)
        else:
            slot_lookup = {}
            for material_index in triangle_materials:
                if material_index < 0 or material_index >= len(self.jms.materials):
                    continue
                clean_name = self.jms.materials[material_index].clean_name
                if clean_name in slot_lookup:
                    continue
                slot_lookup[clean_name] = len(mesh.materials)
                mesh.materials.append(self._get_or_create_material(clean_name))

        max_uv_count = max((len(vertex.texture_coordinates) for vertex in local_vertices), default=0)
        uv_layers = [mesh.uv_layers.new(name="UVMap_Render" if index == 0 else f"UVMap_Render_{index}") for index in range(max_uv_count)]
        color_layer = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="CORNER") if any(vertex.color is not None for vertex in local_vertices) else None

        for face_index, polygon in enumerate(mesh.polygons):
            polygon.use_smooth = True
            material_index = triangle_materials[face_index]
            if not use_helper_material and 0 <= material_index < len(self.jms.materials):
                polygon.material_index = slot_lookup[self.jms.materials[material_index].clean_name]
            triangle = self.jms.triangles[triangle_original_indices[face_index]]
            for corner_index, vertex_index in enumerate(triangle.vertex_indices):
                vertex = self.jms.vertices[vertex_index]
                loop_index = polygon.loop_start + corner_index
                for uv_index, layer in enumerate(uv_layers):
                    uv = vertex.texture_coordinates[uv_index] if uv_index < len(vertex.texture_coordinates) else TextureCoordinate(0.0, 0.0)
                    layer.data[loop_index].uv = (uv.u, uv.v)
                if color_layer is not None:
                    color = vertex.color if vertex.color is not None else Vector((0.0, 0.0, 0.0))
                    color_layer.data[loop_index].color = (color[0], color[1], color[2], 1.0)

        mesh.validate(clean_customdata=False)
        mesh.normals_split_custom_set_from_vertices([vertex.normal for vertex in local_vertices])
        obj = bpy.data.objects.new(mesh.name, mesh)
        self.collection.objects.link(obj)

        if region:
            utils.set_region(obj, region)
        if permutation:
            utils.set_permutation(obj, permutation)

        if mesh.nwo.mesh_type == "_connected_geometry_mesh_type_structure":
            obj.nwo.proxy_instance = True
        elif mesh.nwo.mesh_type == "_connected_geometry_mesh_type_seam":
            obj.nwo.seam_back_manual = True
        elif mesh.nwo.mesh_type == "_connected_geometry_mesh_type_portal":
            obj.nwo.portal_type = "_connected_geometry_portal_type_two_way"
            obj.nwo.portal_ai_deafening = portal_signature[0]
            if portal_signature[1]:
                obj.nwo.portal_type = "_connected_geometry_portal_type_one_way"
            if portal_signature[3]:
                obj.nwo.portal_type = "_connected_geometry_portal_type_no_way"
            obj.nwo.portal_is_door = portal_signature[2]
            obj.nwo.portal_blocks_sounds = portal_signature[4]

        if self.is_model and self.armature is not None:
            self._skin_object(obj, vertex_lookup)

        faces_by_material: dict[int, list[int]] = defaultdict(list)
        for face_index, material_index in enumerate(triangle_materials):
            faces_by_material[material_index].append(face_index)

        if self.is_model and self.jms.file_kind in {"collision", "physics"}:
            for material_index, face_indices in faces_by_material.items():
                if 0 <= material_index < len(self.jms.materials):
                    prop = utils.add_face_prop(mesh, "global_material", _bool_face_map(len(mesh.polygons), face_indices))
                    prop.global_material = self.jms.materials[material_index].clean_name

        for material_index, face_indices in faces_by_material.items():
            if material_index < 0 or material_index >= len(self.jms.materials):
                continue
            material = self.jms.materials[material_index]
            self._apply_material_props(mesh, obj.nwo, material, _bool_face_map(len(mesh.polygons), face_indices))

        self.result.mesh_objects.append(obj)

    def _triangle_region_permutation(self, triangle: Triangle, material: Material | None) -> tuple[str, str]:
        if material is not None:
            return material.region, material.permutation
        if triangle.region_index is not None and 0 <= triangle.region_index < len(self.jms.regions):
            return self.jms.regions[triangle.region_index], "default"
        return "default", "default"

    def _marker_type_from_name(self, name: str) -> str:
        lower = name.lower()
        if lower.startswith("fx_"):
            return MARKER_TYPE_MAP["effects"]
        if lower.startswith("garbage"):
            return MARKER_TYPE_MAP["garbage"]
        if lower.startswith("hint"):
            return MARKER_TYPE_MAP["hint"]
        if lower.startswith("target"):
            return MARKER_TYPE_MAP["target"]
        return MARKER_TYPE_MAP["model"]

    def _get_or_create_material(self, name: str) -> bpy.types.Material:
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name=name)
        return material

    def _group_name(self, region: str, permutation: str, mesh_type_key: str) -> str:
        parts = [self.jms.name]
        if permutation and permutation != "default":
            parts.append(permutation)
        if region and region != "default":
            parts.append(region)
        if mesh_type_key != "default":
            parts.append(mesh_type_key)
        return "_".join(parts)

    def _build_primitives(self):
        primitive_key = self.jms.file_kind if self.jms.file_kind in {"collision", "physics"} else "physics"
        primitive_mesh_type, helper_material_name = _mesh_type_and_helper_material(primitive_key, self.is_model)
        for sphere in self.jms.spheres:
            self.result.mesh_objects.append(self._build_sphere(sphere, primitive_mesh_type, helper_material_name))
        for box in self.jms.boxes:
            self.result.mesh_objects.append(self._build_box(box, primitive_mesh_type, helper_material_name))
        for capsule in self.jms.capsules:
            self.result.mesh_objects.append(self._build_capsule(capsule, primitive_mesh_type, helper_material_name))
        for convex_shape in self.jms.convex_shapes:
            self.result.mesh_objects.append(self._build_convex_shape(convex_shape, primitive_mesh_type, helper_material_name))

    def _build_constraints(self):
        if not self.is_model or self.armature is None:
            return

        for hinge in self.jms.hinges:
            constraint = bpy.data.objects.new(hinge.name, None)
            constraint.empty_display_type = "ARROWS"
            constraint.nwo.marker_type = MARKER_TYPE_MAP["physics_constraint"]
            constraint.nwo.physics_constraint_parent = self.armature
            constraint.nwo.physics_constraint_parent_bone = self._node_name(hinge.body_a_index)
            constraint.nwo.physics_constraint_child = self.armature
            constraint.nwo.physics_constraint_child_bone = self._node_name(hinge.body_b_index)
            constraint.nwo.physics_constraint_type = "_connected_geometry_marker_type_physics_hinge_constraint"
            if hinge.is_limited:
                constraint.nwo.physics_constraint_uses_limits = True
                constraint.nwo.hinge_constraint_minimum = hinge.min_angle
                constraint.nwo.hinge_constraint_maximum = hinge.max_angle
            self._parent_constraint(constraint, hinge.body_a_index, hinge.body_a_translation, hinge.body_a_rotation)
            self.collection.objects.link(constraint)
            self.result.marker_objects.append(constraint)

        for ragdoll in self.jms.ragdolls:
            constraint = bpy.data.objects.new(ragdoll.name, None)
            constraint.empty_display_type = "ARROWS"
            constraint.nwo.marker_type = MARKER_TYPE_MAP["physics_constraint"]
            constraint.nwo.physics_constraint_parent = self.armature
            constraint.nwo.physics_constraint_parent_bone = self._node_name(ragdoll.attached_index)
            constraint.nwo.physics_constraint_child = self.armature
            constraint.nwo.physics_constraint_child_bone = self._node_name(ragdoll.referenced_index)
            constraint.nwo.physics_constraint_type = "_connected_geometry_marker_type_physics_socket_constraint"
            constraint.nwo.havok_constraint_type = "hkNodeRagDollConstraint"
            constraint.nwo.physics_constraint_uses_limits = True
            constraint.nwo.cone_angle = ragdoll.max_cone
            constraint.nwo.plane_constraint_minimum = ragdoll.min_plane
            constraint.nwo.plane_constraint_maximum = ragdoll.max_plane
            constraint.nwo.twist_constraint_start = ragdoll.min_twist
            constraint.nwo.twist_constraint_end = ragdoll.max_twist
            self._parent_constraint(constraint, ragdoll.attached_index, ragdoll.attached_translation, ragdoll.attached_rotation)
            self.collection.objects.link(constraint)
            self.result.marker_objects.append(constraint)

    def _build_sphere(self, sphere: Sphere, mesh_type: str, helper_material_name: str) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(sphere.name)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(mesh.name, mesh)
        mesh.nwo.mesh_type = mesh_type
        obj.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_sphere"
        self._assign_helper_material(mesh, helper_material_name)
        self._apply_primitive_material(mesh, sphere.material_index)
        self._apply_region_permutation_from_material(obj, sphere.material_index)
        self._place_primitive(obj, sphere.parent_index, Matrix.LocRotScale(sphere.translation, sphere.rotation, Vector.Fill(3, sphere.radius)))
        return obj

    def _build_box(self, box: Box, mesh_type: str, helper_material_name: str) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(box.name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(mesh.name, mesh)
        mesh.nwo.mesh_type = mesh_type
        obj.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_box"
        self._assign_helper_material(mesh, helper_material_name)
        self._apply_primitive_material(mesh, box.material_index)
        self._apply_region_permutation_from_material(obj, box.material_index)
        self._place_primitive(obj, box.parent_index, Matrix.LocRotScale(box.translation, box.rotation, Vector((box.width, box.length, box.height))))
        return obj

    def _build_capsule(self, capsule: Capsule, mesh_type: str, helper_material_name: str) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(capsule.name)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=1.0, radius2=1.0, depth=2.0)
        bm.transform(Matrix.Translation((0.0, 0.0, 1.0)))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(mesh.name, mesh)
        mesh.nwo.mesh_type = mesh_type
        obj.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_pill"
        self._assign_helper_material(mesh, helper_material_name)
        self._apply_primitive_material(mesh, capsule.material_index)
        self._apply_region_permutation_from_material(obj, capsule.material_index)
        scale = Vector((capsule.radius, capsule.radius, capsule.radius + (capsule.height / 2.0)))
        self._place_primitive(obj, capsule.parent_index, Matrix.LocRotScale(capsule.translation, capsule.rotation, scale))
        return obj

    def _build_convex_shape(self, convex_shape: ConvexShape, mesh_type: str, helper_material_name: str) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(convex_shape.name)
        bm = bmesh.new()
        for vertex in convex_shape.vertices:
            bm.verts.new(tuple(vertex))
        bm.verts.ensure_lookup_table()
        if bm.verts:
            bmesh.ops.convex_hull(bm, input=list(bm.verts))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(mesh.name, mesh)
        mesh.nwo.mesh_type = mesh_type
        obj.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_none"
        self._assign_helper_material(mesh, helper_material_name)
        self._apply_primitive_material(mesh, convex_shape.material_index)
        self._apply_region_permutation_from_material(obj, convex_shape.material_index)
        self._place_primitive(obj, convex_shape.parent_index, self._local_transform(convex_shape.translation, convex_shape.rotation))
        return obj

    def _assign_helper_material(self, mesh: bpy.types.Mesh, helper_material_name: str):
        if helper_material_name:
            mesh.materials.clear()
            mesh.materials.append(halo_material(helper_material_name))

    def _apply_primitive_material(self, mesh: bpy.types.Mesh, material_index: int | None):
        if material_index is None or material_index < 0 or material_index >= len(self.jms.materials):
            return
        material = self.jms.materials[material_index]
        prop = utils.add_face_prop(mesh, "global_material")
        prop.global_material = material.clean_name
        self._apply_material_props(mesh, None, material, None)

    def _apply_region_permutation_from_material(self, obj: bpy.types.Object, material_index: int | None):
        if material_index is None or material_index < 0 or material_index >= len(self.jms.materials):
            return
        material = self.jms.materials[material_index]
        if material.region:
            utils.set_region(obj, material.region)
        if material.permutation:
            utils.set_permutation(obj, material.permutation)

    def _place_primitive(self, obj: bpy.types.Object, parent_index: int, local_matrix: Matrix):
        self.collection.objects.link(obj)
        if self.is_model and self.armature is not None and parent_index > -1:
            obj.parent = self.armature
            obj.parent_type = "BONE"
            obj.parent_bone = self._node_name(parent_index)
            obj.matrix_world = self._node_parent_matrix(parent_index) @ local_matrix
        elif self.is_model and self.armature is not None:
            obj.parent = self.armature
            obj.matrix_world = local_matrix
        elif not self.is_model and parent_index > -1 and parent_index in self.frame_objects:
            obj.parent = self.frame_objects[parent_index]
            obj.matrix_world = self.frame_objects[parent_index].matrix_world @ local_matrix
        else:
            obj.matrix_world = local_matrix

    def _parent_constraint(self, obj: bpy.types.Object, parent_index: int, translation: Vector, rotation: Quaternion):
        if self.armature is None or parent_index < 0:
            obj.matrix_world = self._local_transform(translation, rotation)
            return
        self._parent_to_bone(obj, parent_index)
        obj.matrix_world = self._node_parent_matrix(parent_index) @ self._local_transform(translation, rotation)

    def _parent_to_bone(self, obj: bpy.types.Object, node_index: int):
        if self.armature is None or node_index < 0:
            return
        obj.parent = self.armature
        obj.parent_type = "BONE"
        obj.parent_bone = self._node_name(node_index)

    def _skin_object(self, obj: bpy.types.Object, vertex_lookup: dict[int, int]):
        if self.armature is None:
            return
        obj.parent = self.armature
        modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = self.armature
        groups = {index: obj.vertex_groups.new(name=node.name) for index, node in enumerate(self.jms.nodes)}
        for source_index, local_index in vertex_lookup.items():
            for influence in self.jms.vertices[source_index].node_influences:
                group = groups.get(influence.index)
                if group is not None:
                    group.add((local_index,), influence.weight, "REPLACE")

    def _apply_material_props(self, mesh: bpy.types.Mesh, nwo, material: Material, face_map: np.ndarray | None):
        props = material.props
        if props.two_sided or props.transparent_two_sided:
            utils.add_face_prop(mesh, "face_sides", face_map)
        if props.transparent_one_sided or props.transparent_two_sided:
            utils.add_face_prop(mesh, "transparent", face_map)
        if props.render_only and not mesh.nwo.proxy_collision:
            utils.add_face_prop(mesh, "face_mode", face_map).face_mode = "render_only"
        if props.collision_only:
            utils.add_face_prop(mesh, "face_mode", face_map).face_mode = "collision_only"
        if props.sphere_collision_only:
            utils.add_face_prop(mesh, "face_mode", face_map).face_mode = "sphere_collision_only"
        if props.ladder:
            utils.add_face_prop(mesh, "ladder", face_map)
        if props.breakable:
            utils.add_face_prop(mesh, "face_mode", face_map).face_mode = "breakable"
        if props.no_shadow:
            utils.add_face_prop(mesh, "no_shadow", face_map)
        if props.lightmap_only:
            utils.add_face_prop(mesh, "face_mode", face_map).face_mode = "lightmap_only"
        if props.shadow_only:
            utils.add_face_prop(mesh, "face_mode", face_map).face_mode = "shadow_only"
        if props.precise:
            utils.add_face_prop(mesh, "precise_position", face_map)
        if props.ignored_by_lightmaps:
            utils.add_face_prop(mesh, "no_lightmap", face_map)
        if props.decal_offset:
            utils.add_face_prop(mesh, "decal_offset", face_map)
        if props.slip_surface:
            utils.add_face_prop(mesh, "slip_surface", face_map)
        if props.lightmap_resolution_scale:
            utils.add_face_prop(mesh, "lightmap_resolution_scale", face_map).lightmap_resolution_scale = str(props.lightmap_resolution_scale)
        if props.lightmap_additive_transparency:
            utils.add_face_prop(mesh, "lightmap_additive_transparency", face_map).lightmap_additive_transparency = props.lightmap_additive_transparency
        if props.lightmap_translucency_tint_color:
            utils.add_face_prop(mesh, "lightmap_translucency_tint_color", face_map).lightmap_translucency_tint_color = props.lightmap_translucency_tint_color
        if props.lightmap_transparency_override:
            utils.add_face_prop(mesh, "lightmap_transparency_override", face_map)

        if nwo is not None and mesh.nwo.mesh_type == "_connected_geometry_mesh_type_portal":
            nwo.portal_ai_deafening = props.ai_deafening
            if props.portal_one_way:
                nwo.portal_type = "_connected_geometry_portal_type_one_way"
            if props.portal_vis_blocker:
                nwo.portal_type = "_connected_geometry_portal_type_no_way"
            nwo.portal_is_door = props.portal_door
            nwo.portal_blocks_sounds = props.blocks_sound

    def _local_transform(self, translation: Vector, rotation: Quaternion) -> Matrix:
        return Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()

    def _node_parent_matrix(self, node_index: int) -> Matrix:
        if self.armature is not None and node_index > -1:
            bone = self.armature.pose.bones.get(self._node_name(node_index))
            if bone is not None:
                return bone.matrix.copy()
        if node_index > -1:
            return self.node_world_matrices[node_index]
        return Matrix.Identity(4)

    def _node_name(self, node_index: int) -> str:
        if 0 <= node_index < len(self.jms.nodes):
            return self.jms.nodes[node_index].name
        return ""
