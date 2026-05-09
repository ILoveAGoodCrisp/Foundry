from math import radians
from pathlib import Path
import struct
import time

import bmesh
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

from .decorator_set import DecoratorSetTag

from .decal_system import DecalSystemCorinthTag, DecalSystemTag

from .Tags import TagFieldBlockElement

from ..managed_blam import Tag
import os
from .. import utils
import bpy

DECORATOR_CLOUD_PROP = "nwo_decorator_placement_cloud"
DECORATOR_INSTANCE_SOURCE_PROP = "nwo_decorator_instance_source"
DECORATOR_ATTR_NORMAL = "normal"
DECORATOR_ATTR_INFO = "decorator_info"
DECORATOR_ATTR_SCALE = "decorator_scale"
DECORATOR_ATTR_TINT = "decorator_tint"

def _serialized_block_data(block):
    count = block.Elements.Count
    if count == 0:
        return memoryview(b""), 0, 0

    block_size = int(block.Size)
    if block_size <= 0 or block_size % count:
        element_size = sum(int(field.Size) for field in block.Elements[0].Fields)
    else:
        element_size = block_size // count

    data = bytes(block.Serialize())
    chunk_start = data.find(b"lbgt")
    if chunk_start == -1:
        raise ValueError("Serialized tag block does not contain an lbgt chunk")

    chunk_count = struct.unpack_from("<I", data, chunk_start + 12)[0]
    if chunk_count != count:
        raise ValueError(f"Serialized tag block count mismatch: {chunk_count} != {count}")

    values_start = chunk_start + 20
    values_end = values_start + element_size * count
    if values_end > len(data):
        raise ValueError("Serialized tag block ended before all element data was read")

    return memoryview(data)[values_start:values_end], element_size, count

def _field_offsets(block, element_size: int):
    offsets = {}
    offset = 0
    for field in block.Elements[0].Fields:
        offsets[field.FieldName] = offset
        offset += int(field.Size)

    if offset > element_size:
        raise ValueError(f"Field size {offset} exceeds serialized element size {element_size}")

    return offsets

def _read_serialized_decorator_placements(placements, corinth: bool):
    data, element_size, count = _serialized_block_data(placements)
    if count == 0:
        return None

    offsets = _field_offsets(placements, element_size)
    required_fields = ("position", "type index", "motion scale", "ground tint", "rotation", "scale", "tint color")
    missing_fields = [name for name in required_fields if name not in offsets]
    if missing_fields:
        raise ValueError(f"Decorator placement block is missing fields: {', '.join(missing_fields)}")

    dtype = np.dtype({
        "names": ["position", "type_index", "motion_scale", "ground_tint", "rotation", "scale", "tint"],
        "formats": [("<f4", (3,)), "<i1", "<i1", "<i1", ("<f4", (4,)), "<f4", ("<f4", (3,))],
        "offsets": [offsets[name] for name in required_fields],
        "itemsize": element_size,
    })
    rows = np.frombuffer(data, dtype=dtype, count=count)

    motion_scale = rows["motion_scale"]
    ground_tint = rows["ground_tint"]
    if not corinth:
        motion_scale = motion_scale.astype(np.uint8)
        ground_tint = ground_tint.astype(np.uint8)

    return {
        "position": rows["position"],
        "type_index": rows["type_index"],
        "motion_scale": motion_scale,
        "ground_tint": ground_tint,
        "rotation": rows["rotation"],
        "scale": rows["scale"],
        "tint": rows["tint"],
        "count": count,
    }

class ScenarioObjectReference:
    def __init__(self, element: TagFieldBlockElement, for_decal=False, corinth=False):
        self.definition = None
        self.name = "object"
        self.decal_material = None
        def_path = element.Fields[0].Path
        if def_path is not None:
            if Path(def_path.Filename).exists():
                self.definition = def_path.RelativePathWithExtension
                self.name = def_path.ShortName
                if for_decal:
                    if corinth:
                        with DecalSystemCorinthTag(path=self.definition) as decal:
                            for element in decal.tag.SelectField("Block:decals").Elements:
                                decal_name = f'{decal.tag_path.ShortName}_{element.SelectField("StringId:decal name").GetStringData()}'
                                mat = bpy.data.materials.get(decal_name)
                                if mat is None:
                                    decal.reread_fields(element.ElementIndex)
                                    mat = bpy.data.materials.new(decal_name)
                                    decal.to_nodes(mat, generated_uvs=True)
                                    
                                self.decal_material = mat
                    else:
                        with DecalSystemTag(path=self.definition) as decal:
                            for element in decal.tag.SelectField("Block:decals").Elements:
                                decal_name = f'{decal.tag_path.ShortName}_{element.SelectField("StringId:decal name").GetStringData()}'
                                mat = bpy.data.materials.get(decal_name)
                                if mat is None:
                                    decal.reread_fields(element.ElementIndex)
                                    mat = bpy.data.materials.new(decal_name)
                                    decal.to_nodes(mat, generated_uvs=True)
                                    
                                self.decal_material = mat
    
class ScenarioObject:
    def __init__(self, element: TagFieldBlockElement, palette: list[ScenarioObjectReference], object_names: list[str], corinth: bool):
        self.name_index = element.SelectField("ShortBlockIndex:name").Value
        self.name = "object"
        self.position = Vector([n * 100 for n in element.SelectField("Struct:object data[0]/RealPoint3d:position").Data])
        yaw, pitch, roll = [radians(n) for n in element.SelectField("Struct:object data[0]/RealEulerAngles3d:rotation").Data]
        self.rotation = Euler((roll, -pitch, yaw), 'ZYX')
        self.scale = element.SelectField("Struct:object data[0]/Real:scale").Data
        if self.scale == 0.0:
            self.scale = 1
        palette_index = element.SelectField("ShortBlockIndex:type").Value
        self.reference = palette[palette_index] if palette_index > -1  and palette_index < len(palette) else None
        self.valid = self.reference is not None and self.reference.definition is not None
        variant = element.SelectField("Struct:permutation data[0]/StringId:variant name")
        if variant is None:
            self.variant = ""
        else:
            self.variant = variant.GetStringData()
        
        self.folder_index = element.SelectField("Struct:object data[0]/ShortBlockIndex:editor folder").Value
        self.parent_index = element.SelectField("Struct:object data[0]/Struct:parent id[0]/ShortBlockIndex:parent object").Value
        self.parent_marker = element.SelectField("Struct:object data[0]/Struct:parent id[0]/StringId:parent marker").GetStringData()
        
        if self.name_index > -1 and self.name_index < len(object_names):
            self.name = object_names[self.name_index]
        elif self.reference is not None:
            self.name = f"{self.reference.name}:{element.ElementIndex}"
            
        self.bsps = set()
        
        origin_bsp = element.SelectField("object data[0]/object id[0]/origin bsp index")
        if origin_bsp is not None:
            if origin_bsp.Value > -1:
                self.bsps.add(origin_bsp.Value)
                
        if not corinth:
            if not self.bsps:
                manual_bsp_flags = element.SelectField("object data[0]/manual bsp flags")
                if manual_bsp_flags is not None:
                    for idx, flag in enumerate(manual_bsp_flags.Items):
                        if flag.IsSet:
                            self.bsps.add(idx)
                            
                attach_bsp_flags = element.SelectField("object data[0]/can attach to bsp flags")
                if attach_bsp_flags is not None:
                    for idx, flag in enumerate(attach_bsp_flags.Items):
                        if flag.IsSet:
                            self.bsps.add(idx)
                        
        def decode_node_bitvector(signed_bytes, node_count):
            result = [False] * node_count
            idx = 0

            for b in signed_bytes:
                u = b & 0xFF

                for bit in range(8):
                    if idx >= node_count:
                        return result

                    result[idx] = bool((u >> bit) & 1)
                    idx += 1

            return result
        
        def decode_orientation(v):
            if v == -32768:
                return -1.0
            else:
                return v / 32767.0
        
        self.orientations = []
        self.node_mask = []
        return # NOTE skipping this until it is implemented correctly
        node_orientations = element.SelectField("object data[0]/node orientations")
        if node_orientations.Elements.Count > 0:
            noe = node_orientations.Elements[0]
            n_count = noe.SelectField("node count").Data
            bit_vectors = [e.Fields[0].Data for e in noe.SelectField("bit vector").Elements]
            orientations = [e.Fields[0].Data for e in noe.SelectField("orientations").Elements]
            o = orientations[:len(orientations) - (len(orientations) % 4)]
            self.orientations = ((decode_orientation(o[i+3]), decode_orientation(o[i]), decode_orientation(o[i+1]), decode_orientation(o[i+2])) for i in range(0, len(o), 4))
            
            self.node_mask = decode_node_bitvector(bit_vectors, n_count)
            
    def to_object(self):
        if self.reference is None or self.reference.definition is None:
            return print(f"Found scenario object named {self.name} but it has no valid tag reference")
            
        ob = bpy.data.objects.new(name=self.name, object_data=None)
        ob.empty_display_type = "ARROWS"
        ob.matrix_world = Matrix.LocRotScale(self.position, self.rotation, Vector.Fill(3, self.scale))

        ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
        ob.nwo.marker_game_instance_tag_name = self.reference.definition
        ob.nwo.marker_game_instance_tag_variant_name = self.variant
        
        return ob
    
class ScenarioDecorator:
    def __init__(self, element: TagFieldBlockElement, path: str, name: str, types: list, corinth: bool):
        
        # NOTE Due to the volume of decorators, pre-processing their final transforms so they don't go through the transform_scene function
        
        self.position = Vector([n * 100 for n in element.SelectField("position").Data])
        self.rotation = utils.ijkw_to_wxyz([n for n in element.SelectField("rotation").Data])
        self.scale = element.SelectField("scale").Data
        type_index = element.SelectField("type index").Data
        self.type = types.get(type_index) if isinstance(types, dict) else next((t for t in types if t.decorator_type_index == type_index), None)
        if self.type is None:
            return
        
        self.name = f"{name}_{self.type}"
        self.path = path
        
        self.motion_scale = element.SelectField("motion scale").Data
        self.ground_tint = element.SelectField("ground tint").Data
        self.tint = element.SelectField("tint color").Data
        
        if not corinth:
            self.motion_scale = utils.unsigned_int8(self.motion_scale)
            self.ground_tint = utils.unsigned_int8(self.ground_tint)

    @classmethod
    def from_values(cls, position, rotation, scale, type_index: int, motion_scale: int, ground_tint: int, tint, path: str, name: str, types: dict, corinth: bool):
        decorator = cls.__new__(cls)
        decorator.position = Vector((float(position[0]) * 100, float(position[1]) * 100, float(position[2]) * 100))
        decorator.rotation = utils.ijkw_to_wxyz((float(rotation[0]), float(rotation[1]), float(rotation[2]), float(rotation[3])))
        decorator.scale = float(scale)
        decorator.type = types.get(int(type_index))
        if decorator.type is None:
            return decorator

        decorator.name = f"{name}_{decorator.type}"
        decorator.path = path
        decorator.motion_scale = int(motion_scale)
        decorator.ground_tint = int(ground_tint)
        decorator.tint = (float(tint[0]), float(tint[1]), float(tint[2]))
        
        if not corinth:
            decorator.motion_scale = utils.unsigned_int8(decorator.motion_scale)
            decorator.ground_tint = utils.unsigned_int8(decorator.ground_tint)

        return decorator
        
    def to_object(self):
        ob = bpy.data.objects.new(name=self.name, object_data=None)
        ob.matrix_world = Matrix.LocRotScale(self.position, self.rotation, Vector.Fill(3, self.scale))

        ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
        ob.nwo.marker_game_instance_tag_name = self.path
        ob.nwo.marker_game_instance_tag_variant_name = self.type.decorator_type_name
        
        ob.nwo.decorator_motion_scale = float(self.motion_scale / 255)
        ob.nwo.decorator_ground_tint = float(self.ground_tint / 255)
        ob.nwo.decorator_tint = [utils.srgb_to_linear(c) for c in self.tint]
        
        return ob

def _set_vector_point_attribute(mesh, name, values):
    attr = mesh.attributes.new(name, 'FLOAT_VECTOR', 'POINT')
    attr.data.foreach_set("vector", np.ascontiguousarray(values, dtype=np.float32).reshape(-1))

def _set_color_point_attribute(mesh, name, values):
    attr = mesh.attributes.new(name, 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", np.ascontiguousarray(values, dtype=np.float32).reshape(-1))

def _decorator_up_vectors(rotations):
    x = rotations[:, 0]
    y = rotations[:, 1]
    z = rotations[:, 2]
    w = rotations[:, 3]
    up = np.empty((len(rotations), 3), dtype=np.float32)
    up[:, 0] = 2.0 * (x * z + w * y)
    up[:, 1] = 2.0 * (y * z - w * x)
    up[:, 2] = 1.0 - 2.0 * (x * x + y * y)
    lengths = np.linalg.norm(up, axis=1)
    valid = lengths > 0.000001
    up[valid] /= lengths[valid, None]
    up[~valid] = (0.0, 0.0, 1.0)
    return up

def _decorator_rotation_values(rotations, up):
    x = rotations[:, 0]
    y = rotations[:, 1]
    z = rotations[:, 2]
    w = rotations[:, 3]
    original_x = np.empty((len(rotations), 3), dtype=np.float32)
    original_x[:, 0] = 1.0 - 2.0 * (y * y + z * z)
    original_x[:, 1] = 2.0 * (x * y + z * w)
    original_x[:, 2] = 2.0 * (x * z - y * w)

    align = np.empty((len(rotations), 4), dtype=np.float32)
    align[:, 0] = 1.0 + up[:, 2]
    align[:, 1] = -up[:, 1]
    align[:, 2] = up[:, 0]
    align[:, 3] = 0.0
    fallback = align[:, 0] < 0.000001
    align[fallback] = (0.0, 1.0, 0.0, 0.0)
    lengths = np.linalg.norm(align, axis=1)
    align /= lengths[:, None]

    aw = align[:, 0]
    ax = align[:, 1]
    ay = align[:, 2]
    az = align[:, 3]
    base_x = np.empty_like(up)
    base_x[:, 0] = 1.0 - 2.0 * (ay * ay + az * az)
    base_x[:, 1] = 2.0 * (ax * ay + az * aw)
    base_x[:, 2] = 2.0 * (ax * az - ay * aw)

    cross = np.cross(base_x, original_x)
    sin = np.einsum("ij,ij->i", up, cross)
    cos = np.einsum("ij,ij->i", base_x, original_x)
    return np.mod(np.arctan2(sin, cos), 2.0 * np.pi) / (2.0 * np.pi)

def _serialized_decorators_to_clouds(serialized_placements, path: str, name: str, types: dict, collection):
    clouds = []
    type_indices = serialized_placements["type_index"].astype(np.int16, copy=False)
    for type_index in np.unique(type_indices):
        decorator_type = types.get(int(type_index))
        if decorator_type is None:
            continue

        indices = np.flatnonzero(type_indices == type_index)
        if not len(indices):
            continue

        cloud_name = f"{name}_{decorator_type.decorator_type_name}_decorator_cloud"
        positions = np.ascontiguousarray(serialized_placements["position"][indices], dtype=np.float32) * 100.0
        rotations = np.ascontiguousarray(serialized_placements["rotation"][indices], dtype=np.float32)
        mesh = bpy.data.meshes.new(cloud_name)
        mesh.vertices.add(len(indices))
        mesh.vertices.foreach_set("co", positions.reshape(-1))
        up = _decorator_up_vectors(rotations)
        _set_vector_point_attribute(mesh, DECORATOR_ATTR_NORMAL, up)
        scales = np.asarray(serialized_placements["scale"][indices], dtype=np.float32)
        info = np.ones((len(indices), 4), dtype=np.float32)
        info[:, 0] = _decorator_rotation_values(rotations, up)
        info[:, 1] = np.asarray(serialized_placements["ground_tint"][indices], dtype=np.float32) / 255.0
        info[:, 2] = np.asarray(serialized_placements["motion_scale"][indices], dtype=np.float32) / 255.0
        _set_color_point_attribute(mesh, DECORATOR_ATTR_INFO, info)
        scale = np.ones((len(indices), 4), dtype=np.float32)
        scale[:, :3] = scales[:, None]
        _set_color_point_attribute(mesh, DECORATOR_ATTR_SCALE, scale)
        tint = np.ones((len(indices), 4), dtype=np.float32)
        tint[:, :3] = np.asarray(serialized_placements["tint"][indices], dtype=np.float32) ** 2.2
        _set_color_point_attribute(mesh, DECORATOR_ATTR_TINT, tint)
        mesh.update()

        ob = bpy.data.objects.new(name=cloud_name, object_data=mesh)
        ob[DECORATOR_CLOUD_PROP] = True
        ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
        ob.nwo.marker_game_instance_tag_name = path
        ob.nwo.marker_game_instance_tag_variant_name = decorator_type.decorator_type_name
        ob.nwo.export_this = False
        collection.objects.link(ob)
        clouds.append(ob)

    return clouds
    
class ScenarioDecal:
    def __init__(self, element: TagFieldBlockElement, palette: list[ScenarioObjectReference], corinth: bool):
        self.rotation = utils.ijkw_to_wxyz([n for n in element.SelectField("RealQuaternion:rotation").Data])
        self.position = Vector([n * 100 for n in element.SelectField("RealPoint3d:position").Data])
        self.scale_x = element.SelectField("Real:scale x").Data * 100
        self.scale_y = element.SelectField("Real:scale y").Data * 100
        self.name = "decal"
        palette_index = element.SelectField("ShortBlockIndex:decal palette index").Value
        self.reference = palette[palette_index] if palette_index > -1  and palette_index < len(palette) else None
        self.valid = self.reference is not None and self.reference.definition is not None
        if self.valid:
            self.name = self.reference.name
            
        self.bsps = set()
        
        if not corinth:
            manual_bsp_flags = element.SelectField("manual bsp flags")
            if manual_bsp_flags is not None:
                for idx, flag in enumerate(manual_bsp_flags.Items):
                    if flag.IsSet:
                        self.bsps.add(idx)
        
    def to_object(self):
        if self.reference is None or self.reference.definition is None:
            return print(f"Found scenario decal object named {self.name} but it has no valid tag reference")
            
        mesh = bpy.data.meshes.new(self.name)

        verts = [
            (-self.scale_x / 2, -self.scale_y / 2, 0),
            ( self.scale_x / 2, -self.scale_y / 2, 0),
            ( self.scale_x / 2,  self.scale_y / 2, 0),
            (-self.scale_x / 2,  self.scale_y / 2, 0),
        ]
        faces = [(0, 1, 2, 3)]
        mesh.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new(name=self.name, object_data=mesh)

        ob.matrix_world = Matrix.LocRotScale(self.position, self.rotation, Vector.Fill(3, 1))
        
        # add a decal offset
        normal = ob.matrix_world.to_3x3() @ Vector((0, 0, 1))
        ob.location += normal.normalized() * 0.1

        if self.reference.decal_material is not None:
            mesh.materials.append(self.reference.decal_material)
        
        return ob
        

class ScenarioTag(Tag):
    tag_ext = 'scenario'
        
    def _read_fields(self):
        self.block_skies = self.tag.SelectField("Block:skies")
        self.block_object_names = self.tag.SelectField("Block:object names")
        self.block_bsps = self.tag.SelectField("Block:structure bsps")
        self.block_zone_sets = self.tag.SelectField("Block:zone sets")
        self.block_structure_designs = self.tag.SelectField("Block:structure designs")
        
    def _get_bsp_from_name(self, bsp_name: str):
        for element in self.block_bsps.Elements:
            bsp_reference = element.SelectField('structure bsp').Path
            if bsp_reference is None:
                continue
            full_bsp_name = utils.dot_partition(os.path.basename(bsp_reference.RelativePath))
            if full_bsp_name == bsp_name:
                return element
        else:
            return print("BSP not found in Scenario Tag, perhaps you need to export the scene")
        
    def _sky_name_from_element(self, element):
        # Check if we can retrieve the name from the object names block
        object_names_block_index = element.SelectField('name').Value
        if object_names_block_index:
            object_names_element = self.block_object_names.Elements[object_names_block_index]
            object_name = object_names_element.SelectField('name').GetStringData()
            if object_name:
                return object_name
        
        # If we haven't yet found the name, just take the tag name
        sky_tag_path = element.SelectField('sky').Path
        if not sky_tag_path: return
        return utils.dot_partition(os.path.basename(sky_tag_path.ToString()))
    
    def get_skies_mapping(self) -> list:
        """Reads the scenario skies block and returns a list of skies"""
        skies = []
        for element in self.block_skies.Elements:
            sky_name = self._sky_name_from_element(element)
            if sky_name is None: continue  
            skies.append(sky_name)
            
        return skies
    
    def add_new_sky(self, path: str) -> tuple[str, int]:
        """Appends a new entry to the scenario skies block, adding a reference to the given sky scenery tag path"""
        new_sky_element = self.block_skies.AddElement()
        new_sky_element.SelectField('sky').Path = self._TagPath_from_string(path)
        new_object_name_element = self.block_object_names.AddElement()
        sky_name = utils.dot_partition(os.path.basename(path))
        new_object_name_element.SelectField('name').SetStringData(sky_name)
        new_sky_element.SelectField('name').Value = new_object_name_element.ElementIndex
        sky_index = new_sky_element.ElementIndex
        if self.corinth and sky_index == 0: # if this is h4+ and is the first sky, add it to all bsps that currently have no default sky
            for element in self.block_bsps.Elements:
                default_sky = element.SelectField("default sky")
                if default_sky.Value == -1:
                    default_sky.Value = sky_index
                    
        self.tag_has_changes = True
        return sky_name, sky_index
    
    def set_bsp_default_sky(self, bsp_name: str, sky_index: int):
        """Sets the default sky of the given bsp"""
        # Get the bsp we want from the list
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        # Check current sky to see if we need to update it
        for f in bsp_element.Fields:
            print(f.DisplayName)
        sky_block_index = bsp_element.SelectField('default sky').Value
        if sky_block_index == sky_index:
            print("Default sky already set to this")
        else:
            bsp_element.SelectField('default sky').Value = sky_index
        self.tag_has_changes = True
        return self._sky_name_from_element(self.block_skies.Elements[sky_index])
        
    def set_bsp_lightmap_res(self, bsp_name: str, size_class: int, refinement_class: int) -> bool:
        """Sets the lightmap resolution and refinement class for this bsp"""
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return False
        bsp_element.SelectField('size class').Value = size_class
        if self.corinth:
            bsp_element.SelectField('refinement size class').Value = refinement_class
        self.tag_has_changes = True
        return bsp_element.SelectField('size class').Items[size_class].DisplayName
        
    def get_bsp_info(self, bsp_name: str) -> dict:
        """Returns interesting information about this BSP in a dict"""
        bsp_info_dict = {}
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        bsp_info_dict["Lightmapper Size Class"] = self._Element_get_enum_as_string(bsp_element, "size class")
        if self.corinth:
            bsp_info_dict["Lightmapper Refinement Class"] = self._Element_get_enum_as_string(bsp_element, "refinement size class")
        sky_index = bsp_element.SelectField('default sky').Data
        if sky_index == -1:
            bsp_info_dict["Default Sky"] = "None"
        else:
            bsp_info_dict["Default Sky"] = self._sky_name_from_element(self.block_skies.Elements[sky_index])
        
        return bsp_info_dict
    
    def read_scenario_type(self) -> int:
        return self.tag.SelectField('type').Value
    
    def survival_mode(self) -> bool:
        return self.read_scenario_type() == 0 and self.tag.SelectField('flags').TestBit('survival')
    
    def get_sky_indices(self):
        return [e.SelectField("default sky").Value for e in self.block_bsps.Elements]
    
    def get_bsp_paths(self, zone_set=""):
        bsps = []
        zone_set_bsp_names = set()
        if zone_set:
            for element in self.block_zone_sets.Elements:
                if element.Fields[0].GetStringData() == zone_set:
                    for flag in element.SelectField("bsp zone flags").Items:
                        if flag.IsSet:
                            zone_set_bsp_names.add(flag.FlagName)
                            
        for element in self.block_bsps.Elements:
            bsp_reference = element.SelectField('structure bsp').Path
            if bsp_reference:
                if zone_set_bsp_names and bsp_reference.ShortName not in zone_set_bsp_names:
                    continue
                full_path = bsp_reference.Filename
                if Path(full_path).exists:
                    bsps.append(full_path)
                    
        return bsps
    
    def get_design_paths(self, zone_set=""):
        designs = []
        zone_set_bsp_names = set()
        if zone_set:
            for element in self.block_zone_sets.Elements:
                if element.Fields[0].GetStringData() == zone_set:
                    for flag in element.SelectField("structure design zone flags").Items:
                        if flag.IsSet:
                            zone_set_bsp_names.add(flag.FlagName)
                            
        for element in self.block_structure_designs.Elements:
            design_reference = element.SelectField('Reference:structure design').Path
            if design_reference:
                if zone_set_bsp_names and design_reference.ShortName not in zone_set_bsp_names:
                    continue
                full_path = design_reference.Filename
                if Path(full_path).exists:
                    designs.append(full_path)
                    
        return designs
    
    def get_bsp_names(self) -> list[str]:
        return [os.path.basename(element.Fields[0].Path.RelativePath) for element in self.block_bsps.Elements if element.Fields[0].Path is not None]
    
    def to_blend(self):
        # Import Seams
        print("Importing Seams")
        
    def get_seams_path(self):
        reference = self.tag.SelectField("Reference:structure seams")
        if reference.Path:
            full_path = reference.Path.Filename
            if Path(full_path).exists:
                return full_path
            
    def create_default_profile(self):
        '''Creates a default player starting profile & location'''
        self.tag.SelectField("Block:player starting locations").AddElement()
        element = self.tag.SelectField("Block:player starting profile").AddElement()
        element.SelectField("name").SetStringData("default_single")
        primary = None
        secondary = None
        equipment = None

        with Tag(path=r"multiplayer\globals.multiplayer_object_type_list", tag_must_exist=True, raise_on_error=False) as mp_globals:
            for mp_element in mp_globals.tag.SelectField("Block:object types").Elements:
                match mp_element.Fields[1].GetStringData():
                    case 'assault_rifle':
                        path = mp_element.Fields[2].Path
                        if path:
                            primary = path.RelativePathWithExtension
                    case 'magnum':
                        path = mp_element.Fields[2].Path
                        if path:
                            secondary = path.RelativePathWithExtension
                    case 'sprint_equipment':
                        path = mp_element.Fields[2].Path
                        if path:
                            equipment = path.RelativePathWithExtension
        
        if primary is not None:
            element.SelectField("Reference:primary weapon").Path = self._TagPath_from_string(primary)
            element.SelectField("ShortInteger:primaryrounds loaded").Data = -1
            element.SelectField("ShortInteger:primaryrounds total").Data = -1
        if secondary is not None:
            element.SelectField("Reference:secondary weapon").Path = self._TagPath_from_string(secondary)
            element.SelectField("ShortInteger:secondaryrounds loaded").Data = -1
            element.SelectField("ShortInteger:secondaryrounds total").Data = -1
        if not self.corinth and equipment is not None:
            element.SelectField("Reference:starting equipment").Path = self._TagPath_from_string(equipment)

        self.tag_has_changes = True
        
    def update_cinematic_resource(self):
        resources = self.tag.SelectField("Block:scenario resources[0]/Block:new split resources")
        if not resources:
            return
        if not resources.Elements.Count:
            return
        element = resources.Elements[0]
        cinematic_resource = element.SelectField("Reference:cutscene data resource")
        if cinematic_resource.Path is None:
            return
        if not Path(self.tags_dir, cinematic_resource.Path.RelativePathWithExtension).exists():
            return

        with Tag(path=cinematic_resource.Path.RelativePathWithExtension) as resource:
            try:
                self.tag.SelectField("Block:cinematics").CopyEntireTagBlock()
                resource.tag.SelectField("Block:cinematics").PasteReplaceEntireBlock()
                self.tag.SelectField("Block:cutscene flags").CopyEntireTagBlock()
                resource.tag.SelectField("Block:flags").PasteReplaceEntireBlock()
            finally:
                resource.tag_has_changes = True
            
    def get_zone_sets_dict(self) -> dict[str, list[str]]:
        """Returns a dict with the key as the zoneset name and values as a str of the bsps"""
        zs_dict = {}
        for element in self.block_zone_sets.Elements:
            zs_dict[element.Fields[0].GetStringData()] = [item.FlagName for item in element.SelectField("BlockFlags:bsp zone flags").Items if item.IsSet]
            
        return zs_dict
    
    def get_info(self, bsp_index: int) -> str | None:
        if self.corinth:
            return None
        field = self.tag.SelectField(f"Block:structure bsps[{bsp_index}]/Reference:structure lighting_info")
        if field is not None and field.Path is not None:
            return Path(field.Path.Filename)
        
    def write_foundry_zone_set(self):
        for element in self.block_zone_sets.Elements:
            if element.Fields[0].GetStringData() == "foundry_debug_zone_set":
                foundry_element = element
                break
        else:
            foundry_element = self.block_zone_sets.AddElement()
            foundry_element.Fields[0].SetStringData("foundry_debug_zone_set")
            self.tag_has_changes = True

        bsp_flags = foundry_element.SelectField("bsp zone flags")
        sd_flags = foundry_element.SelectField("structure design zone flags")
        
        for item in bsp_flags.Items:
            if not item.IsSet:
                self.tag_has_changes = True
                item.IsSet = True
        for item in sd_flags.Items:
            if not item.IsSet:
                self.tag_has_changes = True
                item.IsSet = True
                
    def decorators_to_blender(self, parent_collection=None, bvh=None):
        start_time = time.perf_counter()
        objects = []
        placement_count = 0
        
        block = self.tag.SelectField("Block:decorators[0]/Block:sets")
        if block.Elements.Count > 0:
            print(f"Creating Scenario Decorators")
            objects_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_decorators")
            
            if parent_collection is None:
                bpy.context.scene.collection.children.link(objects_collection)
            else:
                parent_collection.children.link(objects_collection)
            
            for i, element in enumerate(block.Elements):
                # set_start = time.perf_counter()
                decorator_set_path = self.get_path_str(element.SelectField("Reference:decorator set").Path, True)
                
                if decorator_set_path and Path(decorator_set_path).exists():
                    with DecoratorSetTag(path=decorator_set_path) as decorator_set:
                        decorator_types = decorator_set.get_decorator_types()
                        dec_rel_path = decorator_set.tag_path.RelativePathWithExtension
                        dec_short_name = decorator_set.tag_path.ShortName
                        corinth = decorator_set.corinth
                        decorator_types_by_index = {t.decorator_type_index: t for t in decorator_types}
                    
                    placements = element.SelectField("Block:placements")
                    print(f"  Processing {dec_rel_path} - {placements.Elements.Count} placed in scenario")
                    try:
                        serialized_placements = _read_serialized_decorator_placements(placements, corinth)
                    except Exception as ex:
                        utils.print_warning(f"Failed to read decorator placements with Field.Serialize(); falling back to field reads: {ex}")
                        serialized_placements = None

                    if serialized_placements is not None:
                        try:
                            objects.extend(_serialized_decorators_to_clouds(serialized_placements, dec_rel_path, dec_short_name, decorator_types_by_index, objects_collection))
                            placement_count += serialized_placements["count"]
                            continue
                        except Exception as ex:
                            utils.print_warning(f"Failed to create decorator placement clouds; falling back to object creation: {ex}")

                    decorators = (
                        ScenarioDecorator(placement, dec_rel_path, dec_short_name, decorator_types_by_index, corinth)
                        for placement in placements.Elements
                    )

                    for decorator in decorators:
                        
                        if decorator.type is None:
                            continue
                        
                        if bvh:
                            if not utils.test_point_bvh(bvh, decorator.position):
                                continue
                        
                        ob = decorator.to_object()
                        if ob is not None:
                            objects_collection.objects.link(ob)
                            objects.append(ob)
                            placement_count += 1
                
                # set_elapsed = time.perf_counter() - set_start
                # print(f"  Decorator set {i + 1}/{block.Elements.Count} processed in {set_elapsed:.3f}s")

        total_elapsed = time.perf_counter() - start_time
        if placement_count != len(objects):
            print(f"Finished creating {placement_count} decorator placements in {len(objects)} cloud objects in {total_elapsed:.3f}s total")
        else:
            print(f"Finished creating {len(objects)} decorators in {total_elapsed:.3f}s total")

        return objects
                
    def decals_to_blender(self, parent_collection=None, bvh=None, bsp_indices=None):
        objects = []
            
        block = self.tag.SelectField(f"Block:decals")
        if block.Elements.Count > 0:
            print(f"Creating Scenario Decals")
            objects_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_decals")
            objects_collection.nwo.type = 'exclude'
            
            if parent_collection is None:
                bpy.context.scene.collection.children.link(objects_collection)
            else:
                parent_collection.children.link(objects_collection)
            
            palette = [ScenarioObjectReference(e, True, self.corinth) for e in self.tag.SelectField("Block:decal palette").Elements]
            for element in block.Elements:
                decal = ScenarioDecal(element, palette, self.corinth)
                
                if not decal.valid:
                    continue
                
                if bsp_indices is not None and decal.bsps:
                    if not decal.bsps.intersection(bsp_indices):
                        continue
                
                elif bvh:
                    if not utils.test_point_bvh(bvh, decal.position):
                        continue
                
                ob = decal.to_object()
                if ob is not None:
                    objects_collection.objects.link(ob)
                    objects.append(ob)
                    
        return objects
                
                
    def objects_to_blender(self, parent_collection=None, bvh=None, bsp_indices=None):
        
        objects = []
        child_objects = {}
        
        objects_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_objects")
        objects_collection.nwo.type = 'exclude'
        
        if parent_collection is None:
            bpy.context.scene.collection.children.link(objects_collection)
        else:
            parent_collection.children.link(objects_collection)
            
        object_names = [e.Fields[0].GetStringData() for e in self.tag.SelectField("Block:object names").Elements]
        named_objects = [None] * len(object_names)
        editor_folders = {bpy.data.collections.new(e.Fields[1].GetStringData()): e.Fields[0].Value for e in self.tag.SelectField("Block:editor folders").Elements}
        folders = list(editor_folders)
        
        for collection, parent_index in editor_folders.items():
            if parent_index < 0 or parent_index >= len(editor_folders):
                objects_collection.children.link(collection)
            else:
                folders[parent_index].children.link(collection)
                
        used_folders = set()
        skeleton_poses = []
        
        def process_object_block(block_name: str, palette_name: str):
            block = self.tag.SelectField(f"Block:{block_name}")
            if block.Elements.Count > 0:
                used_collection = False
                print(f"Creating Scenario {block_name.capitalize()} Objects")
                collection = bpy.data.collections.new(name=block_name)
                objects_collection.children.link(collection)
                palette = [ScenarioObjectReference(e) for e in self.tag.SelectField(f"Block:{palette_name} palette").Elements]
                for element in block.Elements:
                    scenario_object = ScenarioObject(element, palette, object_names, self.corinth)
                    if not scenario_object.valid:
                        continue
                    
                    if bsp_indices is not None and scenario_object.bsps:
                        if not scenario_object.bsps.intersection(bsp_indices):
                            continue
                        
                    elif bvh:
                        if not utils.test_point_bvh(bvh, scenario_object.position):
                            continue
                    
                    ob = scenario_object.to_object()
                    if ob is not None:
                        if scenario_object.name_index > -1 and scenario_object.name_index < len(object_names):
                            named_objects[scenario_object.name_index] = ob
                            
                        if scenario_object.parent_index > -1:
                            child_objects[ob] = scenario_object.parent_index
                            
                        if scenario_object.folder_index > -1 and scenario_object.folder_index < len(folders):
                            folder = folders[scenario_object.folder_index]
                            folder.objects.link(ob)
                            used_folders.add(folder)
                        else:
                            collection.objects.link(ob)
                            used_collection = True
                            
                        objects.append(ob)
                        if scenario_object.orientations and scenario_object.node_mask:
                            skeleton_poses.append((scenario_object.node_mask, scenario_object.orientations))
                        else:
                            skeleton_poses.append(None)
                        
                if not used_collection:
                    bpy.data.collections.remove(collection)
        
        process_object_block("scenery", "scenery")
        process_object_block("bipeds", "biped")
        process_object_block("vehicles", "vehicle")
        process_object_block("equipment", "equipment")
        process_object_block("weapons", "weapon")
        process_object_block("machines", "machine")
        process_object_block("terminals", "terminal")
        process_object_block("controls", "control")
        process_object_block("giants", "giant")
        process_object_block("crates", "crate")
                
        # Parent
        for ob, parent_index in child_objects.items():
            if parent_index < len(named_objects):
                parent = named_objects[parent_index]
                if parent is not None:
                    ob.parent = parent
                    
        for folder in folders:
            if folder not in used_folders:
                for child_folder in folder.children_recursive:
                    if child_folder in used_folders:
                        break
                else:
                    bpy.data.collections.remove(folder)
                    
        return objects, skeleton_poses
    
    def collect_cutscene_titles(self):
        titles = []
        
        def add_titles(block: TagFieldBlockElement):
            for e in block:
                text = e.Fields[0].GetStringData()
                titles.append((text, text, ""))
                
        add_titles(self.tag.SelectField("Block:cutscene titles"))
        
        if not self.corinth:
            return titles
        
        for element in self.tag.SelectField("Block:child scenarios").Elements:
            path = element.Fields[0].Path
            if self.path_exists(path):
                with ScenarioTag(path=path) as child_scenario:
                    ct_block = child_scenario.tag.SelectField("Block:cutscene titles")
                    if ct_block.Elements.Count > 0:
                        titles.append(("", path.ShortName, ""))
                        add_titles(ct_block)
                        
        return titles