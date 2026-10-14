"""Blender surfaces backed by native structure-design records."""
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

from ..constants import WU_SCALAR
from .blender import BlenderTag
from .structure_design import StructureDesignDocument
from .. import import_transform
from .. import utils
from ..tools.property_apply import apply_props_material


class StructureDesignTag(BlenderTag, StructureDesignDocument):
    tag_ext = 'structure_design'

    def to_blender(self, collection):
        # Preflight all fields before creating any Blender data.
        records = self.surfaces()
        rain_meshes, placements = self.rain_geometry()
        objects = self._rain_to_blender(collection, rain_meshes, placements)
        for record in records:
            name = record.name
            if record.kind == 'boundary' and not name:
                name = ('soft_ceiling', 'soft_kill', 'slip_surface')[record.boundary_type]
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata([Vector(v) * 100 for v in record.vertices], [],
                             [(i, i+1, i+2) for i in range(0, len(record.vertices), 3)])
            mesh.transform(import_transform.mesh_matrix())
            ob = bpy.data.objects.new(name, mesh)
            ob.matrix_world = import_transform.rotation_matrix()
            if record.kind == 'boundary':
                mesh.nwo.mesh_type = '_connected_geometry_mesh_type_boundary_surface'
                mesh.nwo.boundary_surface_type = ('SOFT_CEILING', 'SOFT_KILL', 'SLIP_SURFACE')[record.boundary_type]
                apply_props_material(ob, ('SoftCeiling', 'SoftKill', 'SlipSurface')[record.boundary_type])
            elif record.kind == 'fog':
                mesh.nwo.mesh_type = '_connected_geometry_mesh_type_planar_fog_volume'
                ob.nwo.fog_appearance_tag = record.appearance.RelativePathWithExtension if record.appearance else ''
                ob.nwo.fog_volume_depth = record.depth
                apply_props_material(ob, 'Fog')
            elif record.kind == 'water_volume':
                mesh.nwo.mesh_type = '_connected_geometry_mesh_type_water_surface'
                ob.nwo.water_type = 'PHYSICS'
                ob.nwo.water_volume_direction = record.direction
                ob.nwo.water_volume_angle = record.angle
            else:
                mesh.nwo.mesh_type = '_connected_geometry_mesh_type_water_surface'
                ob.nwo.water_type = 'PHYSICS'
                ob.nwo.water_volume_depth = record.depth / WU_SCALAR
                direction, velocity = get_water_flow_direction_velocity(Vector(record.flow))
                ob.nwo.water_volume_flow_direction = direction
                ob.nwo.water_volume_flow_velocity = velocity
                color = [utils.srgb_to_linear(c) for c in record.color]
                ob.nwo.water_volume_fog_color = color[1], color[2], color[3], color[0]
                ob.nwo.water_volume_fog_murkiness = record.murkiness
                material = bpy.data.materials.get('WaterDirection')
                if material is None:
                    with bpy.data.libraries.load(str(Path(utils.MATERIAL_RESOURCES, 'shared_nodes.blend')), link=False) as (_, data_to):
                        data_to.materials = ['WaterDirection']
                    material = bpy.data.materials['WaterDirection']
                mesh.materials.append(material)
            collection.objects.link(ob)
            objects.append(ob)
        return objects

    def _rain_to_blender(self, collection, meshes, placements):
        if not placements:
            return []
        from .connected_geometry import Material, Mesh
        from .prefab import ScenarioStructureBspMetadataTag

        # Use the shared render importer to retain UVs, normals and materials.
        material_records = ScenarioStructureBspMetadataTag.render_materials(self)
        records = [ScenarioStructureBspMetadataTag._render_mesh_record(i, mesh)
                   for i, mesh in enumerate(meshes)]
        materials = [Material.from_native(record) for record in material_records]
        instances_collection = bpy.data.collections.new(f'{self.tag_path.ShortName}_instances')
        collection.children.link(instances_collection)
        templates = {}
        objects = []
        for placement in placements:
            # Mesh type lives on the mesh datablock, so sheets and blockers
            # must not share it even when they reference the same definition.
            key = placement.mesh_index, placement.vertical_rain_sheet
            if key not in templates:
                mesh = Mesh.from_native(records[placement.mesh_index], materials, self.game in {'halo4', 'halo2a'})
                templates[key] = mesh.create(None, None, name=placement.name)
                first = True
            else:
                first = False
            for template in templates[key]:
                ob = template if first else template.copy()
                ob.name = utils.any_partition(placement.name, '__(')
                ob.matrix_world = import_transform.matrix_from_axes(
                    placement.forward, placement.left, placement.up, placement.position
                ) @ Matrix.Scale(placement.scale, 4)
                ob.data.nwo.mesh_type = ('_connected_geometry_mesh_type_poop_vertical_rain_sheet'
                    if placement.vertical_rain_sheet else '_connected_geometry_mesh_type_poop_rain_blocker')
                instances_collection.objects.link(ob)
                objects.append(ob)
        return objects


def get_water_flow_direction_velocity(flow_velocity_vector):
    
    match utils.get_scene_props().forward_direction:
        case 'y-':
            global_forward = Vector((0, -1, 0))
        case 'y':
            global_forward = Vector((0, 1, 0))
        case 'x-':
            global_forward = Vector((-1, 0, 0))
        case 'x':
            global_forward = Vector((1, 0, 0))
            
    # global_forward = Vector((1, 0, 0))
    
    
    global_up = Vector((0, 0, 1))

    velocity = flow_velocity_vector.length

    if velocity == 0:
        return 0.0, 0.0

    direction_vector = flow_velocity_vector.normalized()

    direction_flat = direction_vector - global_up * direction_vector.dot(global_up)
    direction_flat.normalize()

    dot = global_forward.dot(direction_flat)
    cross = global_forward.cross(direction_flat).dot(global_up)
    angle = math.atan2(cross, dot)

    return angle, velocity
