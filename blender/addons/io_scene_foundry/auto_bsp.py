from collections import defaultdict

import bpy
from mathutils import Matrix, bvhtree

from .constants import VALID_MESHES
from . import utils

AUTO_BSP_MANUAL_MESH_TYPES = {
    "_connected_geometry_mesh_type_structure",
    "_connected_geometry_mesh_type_portal",
    "_connected_geometry_mesh_type_planar_fog_volume",
    "_connected_geometry_mesh_type_lightmap_region",
    "_connected_geometry_mesh_type_water_surface",
    "_connected_geometry_mesh_type_water_physics_volume",
    "_connected_geometry_mesh_type_boundary_surface",
    "_connected_geometry_mesh_type_seam",
    "_connected_geometry_mesh_type_weather_polyhedron",
}

AUTO_BSP_SOURCE_MESH_TYPES = {
    "_connected_geometry_mesh_type_structure",
    "_connected_geometry_mesh_type_seam",
}


class AutoBSPAssigner:
    def __init__(
        self,
        context: bpy.types.Context,
        scene_settings,
        export_structure: bool,
        collection_map: dict | None = None,
        export_objects: list | None = None,
        depsgraph: bpy.types.Depsgraph | None = None,
        warnings: list[str] | None = None,
    ):
        self.context = context
        self.scene_settings = scene_settings
        self.export_structure = export_structure
        self.collection_map = collection_map or utils.create_parent_mapping(context)
        self.depsgraph = depsgraph or context.evaluated_depsgraph_get()
        self.warnings = warnings
        self.enabled = scene_settings.asset_type == "scenario" and scene_settings.scenario_auto_bsp_by_origin
        self.regions = [region.name for region in scene_settings.regions_table]
        self.regions_set = frozenset(self.regions)
        self.default_region = scene_settings.regions_table[0].name
        self.structure_regions = set()
        self.bvhs = {}

        if not self.enabled:
            return

        source_objects = export_objects if export_objects is not None else list(self._iter_scene_source_objects())
        self.structure_regions = self._build_structure_regions(source_objects)
        self.bvhs = self._build_bvhs(source_objects)

    def _mesh_type(self, ob) -> str:
        if ob.type not in VALID_MESHES or ob.data is None:
            return ""

        source = getattr(ob, 'ob', None)
        data = source.data if source is not None and source.type == 'POINTCLOUD' else ob.data
        mesh_type = data.nwo.mesh_type or "_connected_geometry_mesh_type_default"
        if mesh_type == "_connected_geometry_mesh_type_structure":
            seam_material = ob.data.materials.get("+seam")
            if seam_material is not None and len(ob.data.materials) == 1:
                return "_connected_geometry_mesh_type_seam"

        return mesh_type

    def _manual_region(self, ob, parent=None) -> str:
        region = ""
        if parent is not None:
            export_collection = parent.nwo.export_collection
            if export_collection:
                collection = self.collection_map[export_collection]
                region = collection.region

        if not region:
            region = ob.collection_region or ob.nwo.collection_region or ob.nwo.region_name or self.default_region

        if region not in self.regions_set:
            return self.default_region

        return region

    def _iter_scene_source_objects(self):
        for inst in self.depsgraph.object_instances:
            obj = inst.object
            original = obj.original
            nwo = original.nwo
            parent = original

            if inst.is_instance:
                obj = inst.instance_object
                original = obj.original
                nwo = original.nwo
                parent = inst.parent

            if original.type not in VALID_MESHES:
                continue

            if utils.ignore_for_export_fast(original, self.collection_map, parent):
                continue

            if original.type == 'POINTCLOUD' and (inst.object.type != 'MESH'
                    or utils.is_decorator_cloud(original)):
                continue

            proxy = utils.ExportObject()
            proxy.name = original.name
            proxy.ob = original
            proxy.data = original.data
            proxy.type = original.type
            proxy.nwo = nwo
            proxy.matrix_world = inst.matrix_world.copy()
            proxy.eval_ob = obj
            proxy.modifiers = tuple(obj.modifiers)
            if original.type == 'POINTCLOUD':
                proxy.type = 'MESH'
                proxy.data = inst.object.data
                proxy.eval_ob = inst.object
            proxy.collection_region = self._manual_region(proxy, parent)
            yield proxy

    def _source_regions(self, ob) -> tuple[str, ...]:
        mesh_type = self._mesh_type(ob)
        if mesh_type not in AUTO_BSP_SOURCE_MESH_TYPES:
            return tuple()

        region = ob.collection_region or self._manual_region(ob)
        if region.lower() == "shared":
            return tuple()

        regions = {region}
        if mesh_type == "_connected_geometry_mesh_type_seam" and not ob.nwo.seam_back_manual:
            back_region = ob.nwo.seam_back
            if back_region in self.regions_set and back_region.lower() != "shared":
                regions.add(back_region)

        return tuple(regions)

    def _adds_structure(self, ob) -> bool:
        if self._mesh_type(ob) != "_connected_geometry_mesh_type_structure":
            return False

        seam_material = ob.data.materials.get("+seam")
        return seam_material is None or len(ob.data.materials) > 1

    def _build_structure_regions(self, source_objects) -> set[str]:
        regions = set()
        for ob in source_objects:
            if not self._adds_structure(ob):
                continue

            region = ob.collection_region or self._manual_region(ob)
            if region.lower() != "shared":
                regions.add(region)

        return regions

    def _object_bvh(self, ob):
        eval_ob = ob.eval_ob
        if eval_ob is None and ob.ob is not None and ob.ob.type != 'POINTCLOUD':
            eval_ob = ob.ob.evaluated_get(self.depsgraph)

        mesh = None
        evaluated = eval_ob is not None
        mesh_from_eval = False
        try:
            if evaluated:
                mesh = eval_ob.to_mesh(preserve_all_data_layers=True, depsgraph=self.depsgraph)
                mesh_from_eval = True
            else:
                mesh = ob.data

            if mesh is None or not mesh.polygons:
                return None

            mesh.calc_loop_triangles()
            if not mesh.loop_triangles:
                return None

            matrix_world = ob.matrix_world or Matrix.Identity(4)
            verts = [matrix_world @ vertex.co for vertex in mesh.vertices]
            flip_winding = matrix_world.is_negative
            if ob.invert_topology:
                flip_winding = not flip_winding

            tris = []
            for tri in mesh.loop_triangles:
                indices = tuple(tri.vertices)
                if flip_winding:
                    indices = indices[0], indices[2], indices[1]
                tris.append(indices)

            if not tris:
                return None

            return bvhtree.BVHTree.FromPolygons(verts, tris)
        finally:
            if mesh_from_eval:
                eval_ob.to_mesh_clear()

    def _build_bvhs(self, source_objects) -> dict[str, list]:
        bvhs_by_region = defaultdict(list)
        for ob in source_objects:
            regions = self._source_regions(ob)
            if not regions:
                continue

            bvh = self._object_bvh(ob)
            if bvh is None:
                continue

            for region in regions:
                bvhs_by_region[region].append(bvh)

        return dict(bvhs_by_region)

    def uses_auto_assignment(self, ob) -> bool:
        if not self.enabled:
            return False

        if ob.type in VALID_MESHES:
            return self._mesh_type(ob) not in AUTO_BSP_MANUAL_MESH_TYPES

        return True

    def region_for_object(self, ob) -> str | None:
        point = (ob.matrix_world or Matrix.Identity(4)).to_translation()
        for region in self.regions:
            if region.lower() == "shared":
                continue

            bvhs = self.bvhs.get(region)
            if bvhs and utils.test_point_bvh(bvhs, point):
                return region

        if self.export_structure and self.default_region not in self.structure_regions:
            return self.default_region

        warning = (
            f"Object [{ob.name}] is not inside any BSP and will not be exported. "
            "Auto BSP by Object Origin only falls back to the default BSP when automatic structure is being generated"
        )
        if self.warnings is None:
            utils.print_warning(warning)
        else:
            self.warnings.append(warning)

        return None
