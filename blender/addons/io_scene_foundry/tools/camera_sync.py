from dataclasses import dataclass
import math
from pathlib import Path
import re

import bpy
from mathutils import Matrix, Vector

from .. import utils


CAMERA_SYNC_NAME = utils.CAMERA_SYNC_DEBUG_NAME
CAMERA_SYNC_FILENAME = f"{CAMERA_SYNC_NAME}.txt"
FLOAT_PATTERN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
MIN_FOV = math.radians(1.0)
MAX_FOV = math.radians(150.0)
VECTOR_EPSILON = 1e-6


class CameraSyncError(Exception):
    pass


@dataclass
class CameraState:
    location: Vector
    forward: Vector
    up: Vector
    fov: float


def camera_sync_path() -> Path:
    project_path = utils.get_project_path()
    if not project_path:
        raise CameraSyncError("No valid Halo project is selected")

    return Path(project_path, CAMERA_SYNC_FILENAME)


def clamp_fov(fov: float) -> float:
    if not math.isfinite(fov):
        return math.radians(78.0)

    return utils.clamp(fov, MIN_FOV, MAX_FOV)


def format_float(value: float) -> str:
    return f"{value:.6f}"


def format_vector(vector: Vector) -> str:
    return " ".join(format_float(v) for v in vector)


def orthonormalize(forward: Vector, up: Vector) -> tuple[Vector, Vector]:
    if forward.length <= VECTOR_EPSILON:
        raise CameraSyncError("Camera file has an invalid forward vector")
    if up.length <= VECTOR_EPSILON:
        raise CameraSyncError("Camera file has an invalid up vector")

    forward = forward.normalized()
    up = up.normalized()
    right = forward.cross(up)
    if right.length <= VECTOR_EPSILON:
        raise CameraSyncError("Camera file forward and up vectors are parallel")

    right.normalize()
    up = right.cross(forward)
    up.normalize()

    return forward, up


def state_from_blender_matrix(matrix: Matrix, fov: float) -> CameraState:
    halo_matrix = utils.halo_transform_matrix(matrix)
    rotation = halo_matrix.to_3x3().normalized()
    forward, up = orthonormalize(-rotation.col[2], rotation.col[1])

    return CameraState(
        location=halo_matrix.translation.copy(),
        forward=forward,
        up=up,
        fov=clamp_fov(fov),
    )


def blender_matrix_from_state(state: CameraState) -> Matrix:
    forward, up = orthonormalize(state.forward, state.up)
    right = forward.cross(up)
    right.normalize()
    back = -forward

    halo_matrix = Matrix(
        (
            (right.x, up.x, back.x, state.location.x),
            (right.y, up.y, back.y, state.location.y),
            (right.z, up.z, back.z, state.location.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )

    return utils.blender_transform_matrix(halo_matrix)


def state_to_text(state: CameraState) -> str:
    return (
        f"{format_vector(state.location)}\n"
        f"{format_vector(state.forward)}\n"
        f"{format_vector(state.up)}\n"
        f"{format_float(clamp_fov(state.fov))}\n"
    )


def state_from_text(text: str) -> CameraState:
    values = [float(match.group(0)) for match in FLOAT_PATTERN.finditer(text)]
    if len(values) < 10:
        raise CameraSyncError("Camera file must contain position, forward, up, and FOV values")

    if any(not math.isfinite(value) for value in values[:10]):
        raise CameraSyncError("Camera file contains non-finite values")

    forward, up = orthonormalize(Vector(values[3:6]), Vector(values[6:9]))
    return CameraState(
        location=Vector(values[:3]),
        forward=forward,
        up=up,
        fov=clamp_fov(values[9]),
    )


def write_camera_state(state: CameraState) -> Path:
    path = camera_sync_path()
    path.write_text(state_to_text(state), encoding="utf-8")
    return path


def read_camera_state() -> CameraState:
    path = camera_sync_path()
    if not path.exists():
        raise CameraSyncError(f"Camera sync file does not exist: {path}")

    return state_from_text(path.read_text(encoding="utf-8"))


def viewport_region_3d(context: bpy.types.Context) -> bpy.types.RegionView3D:
    space = context.space_data
    if not space or space.type != 'VIEW_3D' or not space.region_3d:
        raise CameraSyncError("A 3D Viewport must be active for viewport camera sync")

    return space.region_3d


def viewport_fov(context: bpy.types.Context) -> float:
    sensor_width = 36.0 if utils.is_corinth(context) else 74.0
    lens = max(context.space_data.lens, VECTOR_EPSILON)
    return clamp_fov(2.0 * math.atan(sensor_width / (2.0 * lens)))


def set_viewport_fov(context: bpy.types.Context, fov: float):
    sensor_width = 36.0 if utils.is_corinth(context) else 74.0
    context.space_data.lens = sensor_width / (2.0 * math.tan(clamp_fov(fov) / 2.0))


def write_viewport_camera(context: bpy.types.Context) -> Path:
    region_3d = viewport_region_3d(context)
    matrix = region_3d.view_matrix.inverted_safe()
    return write_camera_state(state_from_blender_matrix(matrix, viewport_fov(context)))


def write_scene_camera(context: bpy.types.Context) -> Path:
    camera = context.scene.camera
    if not camera:
        raise CameraSyncError("Scene has no active camera")

    return write_camera_state(state_from_blender_matrix(camera.matrix_world, camera.data.angle))


def read_to_viewport(context: bpy.types.Context):
    region_3d = viewport_region_3d(context)
    state = read_camera_state()
    matrix = blender_matrix_from_state(state)

    region_3d.view_perspective = 'PERSP'
    try:
        region_3d.view_matrix = matrix.inverted_safe()
    except Exception:
        region_3d.view_location = matrix.translation
        region_3d.view_rotation = matrix.to_quaternion()
        region_3d.view_distance = 0.0

    set_viewport_fov(context, state.fov)
    if context.area:
        context.area.tag_redraw()


def read_to_scene_camera(context: bpy.types.Context):
    camera = context.scene.camera
    if not camera:
        name = "Game Camera"
        camera_data = bpy.data.cameras.new(name)
        camera = bpy.data.objects.new(name, camera_data)
        context.scene.collection.objects.link(camera)

    state = read_camera_state()
    camera.matrix_world = blender_matrix_from_state(state)
    camera.data.angle = state.fov


def update_camera_debug_menu() -> bool:
    utils.update_debug_menu(update_type=utils.DebugMenuType.CAMERA)
    return True


class NWO_OT_CameraSync(bpy.types.Operator):
    bl_idname = "nwo.camera_sync"
    bl_label = "Camera Sync"
    bl_description = "Reads and writes camera positions between Blender the game. Please note that writing camera positions to the game in Halo 4 Sapien is bugged and will always put the camera to the world origin"
    bl_options = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        items=[
            ("WRITE_VIEWPORT", "Write Viewport", ""),
            ("WRITE_CAMERA", "Write Camera", ""),
            ("READ_VIEWPORT", "Read Viewport", ""),
            ("READ_CAMERA", "Read Camera", ""),
            ("UPDATE_DEBUG_MENU", "Update Debug Menu", ""),
        ],
        default="WRITE_VIEWPORT",
        options={'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()

    def execute(self, context):
        try:
            match self.mode:
                case "WRITE_VIEWPORT":
                    path = write_viewport_camera(context)
                    update_camera_debug_menu()
                    self.report({'INFO'}, f"Wrote viewport camera to {path}")
                case "WRITE_CAMERA":
                    path = write_scene_camera(context)
                    update_camera_debug_menu()
                    self.report({'INFO'}, f"Wrote scene camera to {path}")
                case "READ_VIEWPORT":
                    read_to_viewport(context)
                    update_camera_debug_menu()
                    self.report({'INFO'}, f"Read camera sync file into viewport")
                case "READ_CAMERA":
                    read_to_scene_camera(context)
                    update_camera_debug_menu()
                    self.report({'INFO'}, f"Read camera sync file into scene camera")
                case "UPDATE_DEBUG_MENU":
                    update_camera_debug_menu()
                    self.report({'INFO'}, "Updated camera sync debug menu entries")
                case _:
                    raise CameraSyncError(f"Unknown camera sync mode: {self.mode}")
        except CameraSyncError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        except OSError as error:
            self.report({'WARNING'}, f"Camera sync file error: {error}")
            return {'CANCELLED'}

        return {'FINISHED'}

    @classmethod
    def description(cls, context, properties) -> str:
        match properties.mode:
            case "WRITE_VIEWPORT":
                return f"Write the current Blender viewport to {CAMERA_SYNC_FILENAME}"
            case "WRITE_CAMERA":
                return f"Write the active Blender camera to {CAMERA_SYNC_FILENAME}"
            case "READ_VIEWPORT":
                return f"Move the current Blender viewport to the camera in {CAMERA_SYNC_FILENAME}"
            case "READ_CAMERA":
                return f"Move the active Blender camera to the camera in {CAMERA_SYNC_FILENAME}"
            case "UPDATE_DEBUG_MENU":
                return "Create game debug menu entries for loading and saving the Foundry camera sync file"

        return cls.bl_description
