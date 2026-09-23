

from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
import numpy as np

from .structure_meta import StructureMetaTag

from .structure_lighting import ScenarioStructureLightingInfoTag

from ..managed_blam.connected_geometry import BSP, BSPCollisionMaterial, Cluster, Emissive, EnvironmentObject, HavokCollision, Instance, InstanceDefinition, Material, Mesh, ModelCollision, Portal, StructureCollision, StructureMarker, SurfaceMapping
from .. import import_transform
from ..utils import jstr
from .. import utils
from .prefab import ScenarioStructureBspMetadataTag, StructureBspHavokGeometry

class ScenarioStructureBspTag(ScenarioStructureBspMetadataTag):
    tag_ext = 'scenario_structure_bsp'

    def _classic_render_objects(
        self, collection: bpy.types.Collection,
    ) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
        material_names, material_paths, mesh_records, instances = self.classic_render_scene()
        materials = {}
        for index, (name, shader_path) in enumerate(zip(material_names, material_paths, strict=True)):
            material = bpy.data.materials.get(name)
            if material is None:
                material = bpy.data.materials.new(name)
            if shader_path:
                material.nwo.shader_path = shader_path
            materials[index] = material

        source_objects: dict[int, list[bpy.types.Object]] = {}
        for index, record in enumerate(mesh_records):
            if record is None or not record.parts or not record.positions:
                continue
            source_objects[index] = Mesh.from_native(record, materials, False).create(
                None, None, name=f'classic_bsp_mesh:{index}')

        objects: list[bpy.types.Object] = []
        game_objects: list[bpy.types.Object] = []
        for instance in instances:
            name = instance['name']
            mesh_type = instance['mesh_type']
            is_weather = (mesh_type == 'helper'
                          and name.casefold().startswith('+weather'))
            if (instance['object_index'] < 0 or name == 'Scene Root'
                    or (mesh_type == 'helper' and not is_weather)):
                continue
            sources = source_objects.get(instance['object_index'], ())
            x, y, z, w = instance['rotation']
            transform = Matrix.LocRotScale(
                Vector(instance['translation']) * 100,
                Quaternion((w, x, y, z)),
                Vector.Fill(3, instance['scale']),
            )
            if mesh_type in {'marker', 'environment'}:
                ob = bpy.data.objects.new(name=name, object_data=None)
                ob.empty_display_type = 'ARROWS'
                ob.matrix_world = import_transform.marker_matrix(transform)
                if mesh_type == 'marker':
                    ob.empty_display_size *= (1 / 0.03048) * import_transform.scale_factor()
                else:
                    ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                    ob.nwo.marker_game_instance_tag_name = instance['reference']
                    game_objects.append(ob)
                collection.objects.link(ob)
                objects.append(ob)
                continue
            for source in sources:
                ob = source.copy()
                ob.data = source.data
                ob.name = name
                ob.matrix_world = import_transform.object_matrix(transform)
                if is_weather:
                    ob.display_type = 'WIRE'
                    ob.show_in_front = True
                ob.data.nwo.mesh_type = (
                    '_connected_geometry_mesh_type_collision'
                    if mesh_type == 'collision'
                    else '_connected_geometry_mesh_type_portal'
                    if mesh_type == 'portal'
                    else '_connected_geometry_mesh_type_weather_polyhedron'
                    if is_weather
                    else '_connected_geometry_mesh_type_structure'
                )
                collection.objects.link(ob)
                objects.append(ob)

        for sources in source_objects.values():
            for source in sources:
                bpy.data.objects.remove(source)
        return objects, game_objects
    
    def to_blend_objects(self, collection: bpy.types.Collection, for_cinematic: bool, lighting_info_path: Path = None, import_geometry=True, import_lights=True, always_get_structure_collision=False, sky_index=-1, import_havok=False, skip_structure_merge=False):
        
        objects = []
        game_objects = []
        bvh = None
        
        if not import_geometry and not import_lights and not import_havok:
            return objects, game_objects, bvh
        
        self.collection = collection

        if self.game in {'halo1', 'halo2'}:
            if import_geometry:
                classic_objects, classic_game_objects = self._classic_render_objects(collection)
                objects.extend(classic_objects)
                game_objects.extend(classic_game_objects)
            return objects, game_objects, bvh

        def new_structure_collection():
            layer = utils.add_permutation("structure", utils.SetType.SCENARIO)
            structure_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_structure")
            structure_collection.nwo.type = "permutation"
            structure_collection.nwo.permutation = layer
            self.collection.children.link(structure_collection)
            return structure_collection

        def add_havok_collision_objects(havok_collisions: list[HavokCollision], structure_collection: bpy.types.Collection, face_indices_by_collision: dict[HavokCollision, list[int]] | None = None):
            if not havok_collisions:
                return

            collision_objects = []
            for havok_collision in havok_collisions:
                face_indices = None if face_indices_by_collision is None else face_indices_by_collision.get(havok_collision, [])
                if face_indices is not None and not face_indices:
                    continue
                ob = havok_collision.to_object(face_indices=face_indices)
                collision_objects.append(ob)

            if collision_objects:
                utils.print_step(f"Creating Havok Collision ({len(collision_objects)})")
            for ob in collision_objects:
                objects.append(ob)
                structure_collection.objects.link(ob)

        collision_materials = (
            [BSPCollisionMaterial(record) for record in self.collision_materials()]
            if import_geometry or import_havok else []
        )
        structure_lighting_info = self.structure_lighting_info()
        native_emissives = self.emissive_materials() if import_geometry else []
        native_render_materials = self.render_materials() if import_geometry else []
        native_portals = self.portals() if import_geometry and not for_cinematic else []
        native_markers = self.markers() if import_geometry and not for_cinematic else []
        native_environment_objects = (
            self.environment_objects()
            if import_geometry and not for_cinematic and not self.corinth else []
        )
        native_cookie_cutters = (
            self.cookie_cutters() if import_geometry and not for_cinematic else []
        )
        native_havok_geometry = (
            self.havok_geometry() if import_havok and not for_cinematic else []
        )
        native_structure_collision = (
            self.structure_collision()
            if import_geometry and not for_cinematic else None
        )
        native_surface_mappings = (
            self.surface_triangle_mappings()
            if import_geometry and not for_cinematic else []
        )
        native_cluster_mesh_indices = self.cluster_mesh_indices() if import_geometry else []
        native_instances = self.instances() if import_geometry else []
        native_instance_definitions = (
            self.instance_definitions() if import_geometry else []
        )
        native_render_meshes = (
            self.render_meshes(native_instance_definitions) if import_geometry else []
        )
        structure_meta_data = self.structure_meta_data()
            
        # Get all emissive data
        emissives = [Emissive.from_native(record) for record in native_emissives]
                
        if not lighting_info_path:
            if self.corinth:
                if structure_lighting_info is not None:
                    lighting_info_path = Path(structure_lighting_info.Filename)
            else:
                lighting_info_path = Path(self.tag_path.Filename).with_suffix(".scenario_structure_lighting_info")
        
        if lighting_info_path is not None and lighting_info_path.exists():
            with ScenarioStructureLightingInfoTag(path=str(lighting_info_path)) as info:
                if not self.corinth:
                    emissives.extend(
                        Emissive.from_native(record)
                        for record in info.material_emissives()
                    )
                    
                    if import_geometry:
                        if not for_cinematic:
                            lightmap_regions = info.lightmap_regions_to_blender()
                            if lightmap_regions:
                                utils.print_step(f"Imported {len(lightmap_regions)} lightmap regions from {info.tag_path.RelativePathWithExtension}")
                                objects.extend(lightmap_regions)
                
                if import_lights:
                    light_objects = info.to_blender(collection)
                    if light_objects:
                        utils.print_step(f"Imported {len(light_objects)} lights from {info.tag_path.RelativePathWithExtension}")
                        objects.extend(light_objects)
                            
        if not import_geometry:
            if import_havok and not for_cinematic:
                havok_collisions = self._read_havok_collisions(
                    collision_materials, native_havok_geometry)
                if havok_collisions:
                    add_havok_collision_objects(havok_collisions, new_structure_collection())
                    if always_get_structure_collision:
                        bvh = havok_collisions[0].to_bvh()
            return objects, game_objects, bvh
                    
        # Get all render materials
        render_materials = [
            Material.from_native(record, emissives, True)
            for record in native_render_materials
        ]
            
        havok_collisions = []
        havok_standalone_face_indices = None
        if import_havok and not for_cinematic:
            havok_collisions = self._read_havok_collisions(
                collision_materials, native_havok_geometry)

        # Get all instance definitions
        instance_definitions = []
        instances = []
        created_instance_indices = set()
        ig_collection = None
        permitted_collections = set()
        num_defs = len(native_instance_definitions)
        if num_defs > 0:
            instance_definitions = [
                InstanceDefinition.from_native(
                    record, native_render_meshes, render_materials,
                    collision_materials, self.corinth, for_cinematic)
                for record in native_instance_definitions
            ]
            instances = [
                Instance.from_native(record, instance_definitions)
                for record in native_instances
            ]
            if havok_collisions:
                havok_standalone_face_indices = self._map_havok_instance_collision(
                    havok_collisions,
                    instances,
                    None,
                    None,
                )

            process = "  - Creating Instance Definitions"
            with utils.Spinner():
                utils.update_job_count(process, "", 0, num_defs)
                for definition in instance_definitions:
                    objects.extend(definition.create(None, None))
                    utils.update_job_count(process, "", definition.index, num_defs)
                utils.update_job_count(process, "", num_defs, num_defs)
            
            # Create instanced geometries
        
            # poops = []
            utils.print_step("Creating Instanced Objects")
            ig_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_instances")
            self.collection.children.link(ig_collection)
            # Keeping track of the collections we add in this bsp import
            # This avoids putting objects in collections that already existed prior to export
            # and therefore prevents incorrect bsp assignment
            for io in instances:
                if io.definition.blender_render or io.definition.blender_collision:
                    io_collection = io.get_collection(ig_collection, permitted_collections, self.tag_path.ShortName)
                    permitted_collections.add(io_collection)
                    ob = io.create()
                    objects.append(ob)
                    io_collection.objects.link(ob)
                    created_instance_indices.add(io.index)
        
        # if poops:
        #     with bpy.context.temp_override(selected_editable_objects=poops, object=poops[0]):
        #         bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
        
        def get_collision():
            if native_structure_collision is None:
                return None
            return StructureCollision.from_native(
                native_structure_collision, collision_materials, sky_index)
            
        # Create structure
        structure_objects = []
        collision = None
        merged_collision_geometry = False
        
        structure_collection = new_structure_collection()
        structure_surface_triangle_mapping = []
        clusters = [
            Cluster.from_native(
                index, mesh_index, native_render_meshes,
                render_materials, self.corinth)
            for index, mesh_index in enumerate(native_cluster_mesh_indices)
        ]
        if not for_cinematic:
            collision = get_collision()
            if import_havok:
                proxy_objects, havok_standalone_face_indices = self._create_havok_instance_proxies(
                    havok_collisions,
                    instances,
                    havok_standalone_face_indices,
                )
                objects.extend(proxy_objects)
                if ig_collection is not None:
                    for io in instances:
                        if io.index in created_instance_indices or not (io.definition.blender_render or io.definition.blender_collision):
                            continue
                        io_collection = io.get_collection(ig_collection, permitted_collections, self.tag_path.ShortName)
                        permitted_collections.add(io_collection)
                        ob = io.create()
                        objects.append(ob)
                        io_collection.objects.link(ob)
                        created_instance_indices.add(io.index)
            legacy_surface_triangle_mapping = []
            if collision is not None:
                if len(native_surface_mappings) > len(collision.surfaces):
                    raise ValueError('Structure surface mapping count exceeds collision surfaces')
                legacy_surface_triangle_mapping = [
                    SurfaceMapping.from_native(record, collision.surfaces[record.surface_index])
                    for record in native_surface_mappings
                ]
                structure_surface_triangle_mapping = legacy_surface_triangle_mapping
        
        
        num_clusters = len(clusters)
        if num_clusters > 0:
            instance_definitions = []
            process = "  - Creating Clusters"
            with utils.Spinner():
                utils.update_job_count(process, "", 0, num_clusters)
                for structure in clusters:
                    structure_obs = structure.create(None, None, structure_surface_triangle_mapping, structure.index, collision)
                    for ob in structure_obs:
                        if ob is not None and ob.data and ob.data.polygons:
                            # structure_collection.objects.link(ob)

                            if ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_water_surface':
                                objects.append(ob)
                                structure_collection.objects.link(ob)
                            else:
                                structure_objects.append(ob)
                    utils.update_job_count(process, "", structure.index, num_clusters)
                utils.update_job_count(process, "", num_clusters, num_clusters)
            
        # Create Structure Collision
        # self.structure_collision = None
        if collision is not None:
            if self.corinth:
                utils.print_step("Creating Structure Sky")
            else:
                utils.print_step("Creating Structure Collision")
            
            collision_only_indices = [idx for idx, mapping in enumerate(structure_surface_triangle_mapping) if mapping.collision_only]
            if collision_only_indices:
                ob = collision.to_object(surface_indices=collision_only_indices)
                collision_mesh = ob.data
                if clusters:
                    matcher = clusters[0].mesh
                    for structure_ob in structure_objects:
                        matcher.remove_render_duplicate_faces(collision_mesh, structure_ob.data)
                        if len(collision_mesh.polygons) == 0:
                            break
                if collision.some_sphere_collision:
                    sphere_coll_face_props = [prop for prop in collision_mesh.nwo.face_props if prop.name == "Sphere Collision Only"]
                    if sphere_coll_face_props:
                        sphere_coll_face_prop = sphere_coll_face_props[0]
                        sphere_coll_attribute = collision_mesh.attributes.get(sphere_coll_face_prop.attribute_name)
                        array = np.zeros(len(collision_mesh.polygons), dtype=np.int8)
                        sphere_coll_attribute.data.foreach_get("value", array)
                        coll_only_array = array ^ 1
                        utils.add_face_prop(collision_mesh, "face_mode", coll_only_array).face_mode = 'collision_only'
                    else:
                        utils.add_face_prop(collision_mesh, "face_mode").face_mode = 'sphere_collision_only'
                    
                elif not collision.sphere_collision_only:
                    utils.add_face_prop(collision_mesh, "face_mode").face_mode = 'collision_only'
                if len(collision_mesh.polygons) > 0:
                    merged_collision_geometry = True
                    structure_objects.append(ob)
                else:
                    bpy.data.objects.remove(ob)
                    bpy.data.meshes.remove(collision_mesh)
                
        if havok_collisions:
            add_havok_collision_objects(havok_collisions, structure_collection, havok_standalone_face_indices)

        if always_get_structure_collision:
            if collision is None:
                collision = get_collision()
                        
            if collision is not None:
                bvh = collision.to_bvh()
            elif havok_collisions:
                bvh = havok_collisions[0].to_bvh()
                        
        seam_collection = None

        def add_structure_object(ob: bpy.types.Object, seam_name: str | None = None, connect_edges=False):
            nonlocal seam_collection
            if connect_edges and not for_cinematic:
                utils.connect_verts_on_edge(ob.data)
            objects.append(ob)
            # utils.unlink(ob)
            structure_collection.objects.link(ob)
            ob.nwo.proxy_instance = not self.corinth
            ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_structure'
            
            # separate out the seams
            seam_material_indices = {idx for idx, m in enumerate(ob.data.materials) if m.name == "+seam"}
            if seam_material_indices:
                if seam_collection is None:
                    seam_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_seams")
                    seam_collection.hide_render = True
                    structure_collection.children.link(seam_collection)

                seam_ob = ob.copy()
                seam_ob.data = ob.data.copy()
                
                bm = bmesh.new()
                bm.from_mesh(ob.data)
                preserve_normals = ob.data.has_custom_normals
                if preserve_normals and bm.faces:
                    utils.save_loop_normals(bm, ob.data)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in seam_material_indices], context='FACES')
                bm.to_mesh(ob.data)
                bm.free()
                if preserve_normals:
                    utils.apply_loop_normals(ob.data)
                
                bm = bmesh.new()
                bm.from_mesh(seam_ob.data)
                preserve_normals = seam_ob.data.has_custom_normals
                if preserve_normals and bm.faces:
                    utils.save_loop_normals(bm, seam_ob.data)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in seam_material_indices], context='FACES')
                bm.to_mesh(seam_ob.data)
                bm.free()
                if preserve_normals:
                    utils.apply_loop_normals(seam_ob.data)
                
                seam_ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_seam'
                seam_ob.nwo.seam_back_manual = True
                seam_ob.name = seam_name or f"{ob.name}_seams"
                objects.append(seam_ob)
                seam_collection.objects.link(seam_ob)

        # Merge all structure objects
        if skip_structure_merge:
            if structure_objects:
                utils.print_step("Adding Unmerged Structure")
                for ob in structure_objects:
                    add_structure_object(ob)
        else:
            main_structure_ob = None
            utils.print_step("Merging Structure")
            if len(structure_objects) > 1:
                main_structure_ob, remaining_structure_obs = structure_objects[0], structure_objects[1:]
                main_structure_ob.name = f"{self.tag_path.ShortName}_structure"
                utils.join_objects([main_structure_ob] + remaining_structure_obs)

            elif structure_objects:
                main_structure_ob = structure_objects[0]

            if main_structure_ob is not None:
                add_structure_object(main_structure_ob, f"{self.tag_path.ShortName}_seams", merged_collision_geometry)
        
        utils.print_step("Removing Duplicate Material Slots")
        ob_meshes = {o.data for o in objects if o.type == 'MESH'}
        for me in ob_meshes:
            utils.consolidate_face_attributes(me)
            utils.consolidate_materials(me)
                
        # Create Portals
        if not for_cinematic:
            if native_portals:
                utils.print_step("Creating Portals")
                layer = utils.add_permutation("portals", utils.SetType.SCENARIO)
                portals_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_portals")
                portals_collection.hide_render = True
                portals_collection.nwo.type = "permutation"
                portals_collection.nwo.permutation = layer
                self.collection.children.link(portals_collection)
                for record in native_portals:
                    portal = Portal(record)
                    ob = portal.create()
                    objects.append(ob)
                    portals_collection.objects.link(ob)
            
            if native_cookie_cutters:
                utils.print_step("Creating Cookie Cutters")
                layer = utils.add_permutation("cookie_cutters", utils.SetType.SCENARIO)
                cookies_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_cookie_cutters")
                cookies_collection.hide_render = True
                cookies_collection.nwo.type = "permutation"
                cookies_collection.nwo.permutation = layer
                self.collection.children.link(cookies_collection)
                for record in native_cookie_cutters:
                    cookie = ModelCollision.from_native(record)
                    ob = cookie.to_object(cookie_cutter=True)
                    objects.append(ob)
                    cookies_collection.objects.link(ob)
        
            # Create markers
            if native_markers:
                utils.print_step("Creating Structure Markers")
                layer = utils.add_permutation("markers", utils.SetType.SCENARIO)
                markers_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_markers")
                markers_collection.nwo.type = "permutation"
                markers_collection.nwo.permutation = layer
                self.collection.children.link(markers_collection)
            
                for record in native_markers:
                    marker = StructureMarker(record)
                    ob = marker.to_object()
                    objects.append(ob)
                    markers_collection.objects.link(ob)
            
        # Now do environment objects
        if self.corinth:
            if structure_meta_data is not None:
                structure_meta_path = Path(structure_meta_data.Filename)
                if structure_meta_path.exists():
                    utils.print_step("Importing Structure Meta")
                    layer = utils.add_permutation("meta", utils.SetType.SCENARIO)
                    meta_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_meta")
                    meta_collection.nwo.type = "permutation"
                    meta_collection.nwo.permutation = layer
                    self.collection.children.link(meta_collection)
                    with StructureMetaTag(path=structure_meta_path) as meta:
                        meta_objects, meta_game_objects = meta.to_blender(meta_collection, for_cinematic)
                        objects.extend(meta_objects)
                        objects.extend(meta_game_objects)
                        game_objects.extend(meta_game_objects)
            
            # Prefabs
            prefabs = self._import_prefabs(self.collection)
            objects.extend(prefabs)
            game_objects.extend(prefabs)
                
        else:
            if native_environment_objects:
                utils.print_step("Creating Game Object Markers")
                layer = utils.add_permutation("objects", utils.SetType.SCENARIO)
                env_objects_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_objects")
                env_objects_collection.nwo.type = "permutation"
                env_objects_collection.nwo.permutation = layer
                self.collection.children.link(env_objects_collection)
                for record in native_environment_objects:
                    env_object = EnvironmentObject(record)
                    ob = env_object.to_object()
                    if ob is not None:
                        env_objects_collection.objects.link(ob)
                        objects.append(ob)
                        game_objects.append(ob)
            
        return objects, game_objects, bvh
    
    def _import_prefabs(self, parent_collection):
        objects = []
        with ScenarioStructureBspMetadataTag(
                path=self.tag_path.RelativePathWithExtension) as native_bsp:
            prefabs = native_bsp.prefabs()
        if not prefabs:
            return objects
        
        utils.print_step("Importing Prefabs")
        layer = utils.add_permutation("prefabs", utils.SetType.SCENARIO)
        prefabs_collection = bpy.data.collections.new(name=f"{self.tag_path.ShortName}_prefabs")
        prefabs_collection.nwo.type = "permutation"
        prefabs_collection.nwo.permutation = layer
        parent_collection.children.link(prefabs_collection)
        
        for prefab in prefabs:
            ref = prefab.reference.Filename
            if not Path(ref).exists():
                continue

            ob = bpy.data.objects.new(name=prefab.name, object_data=None)
            ob.empty_display_type = "ARROWS"
            ob.empty_display_size *= import_transform.scale_factor()
            
            ob.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
            ob.nwo.marker_game_instance_tag_name = utils.relative_path(ref)
            
            matrix = Matrix((
                (prefab.forward[0], prefab.left[0], prefab.up[0], prefab.position[0] * 100),
                (prefab.forward[1], prefab.left[1], prefab.up[1], prefab.position[1] * 100),
                (prefab.forward[2], prefab.left[2], prefab.up[2], prefab.position[2] * 100),
                (0, 0, 0, 1),
            ))
            ob.matrix_world = import_transform.marker_matrix(matrix)
            if prefab.scale != 0:
                ob.scale = Vector.Fill(3, prefab.scale)

            prefabs_collection.objects.link(ob)
            objects.append(ob)
            
        return objects
    
    @staticmethod
    def _cluster_triangle_ranges(clusters: list[Cluster], temp_meshes) -> list[tuple[int, int, int]]:
        section_triangle_ranges = []
        first_triangle_index = 0
        for cluster in clusters:
            try:
                cluster.mesh.temp_meshes = temp_meshes
                cluster.mesh.real_mesh_index = None
                cluster.mesh._get_raw_mesh_data()
            except Exception:
                continue

            triangle_count = len(cluster.mesh.tris)
            if triangle_count:
                section_triangle_ranges.append((cluster.index, first_triangle_index, triangle_count))
                first_triangle_index += triangle_count

        return section_triangle_ranges

    @staticmethod
    def _havok_surface_triangle_mapping(havok_collisions: list[HavokCollision], section_triangle_ranges: list[tuple[int, int, int]]) -> tuple[list[SurfaceMapping], dict[HavokCollision, list[int]]]:
        surface_triangle_mapping = []
        standalone_face_indices = {}
        claimed_render_triangles = {}
        for havok_collision in havok_collisions:
            rejected_face_indices = set()
            surface_triangle_mapping.extend(havok_collision.to_surface_triangle_mappings(section_triangle_ranges, claimed_render_triangles, rejected_face_indices))
            if rejected_face_indices:
                standalone_face_indices[havok_collision] = sorted(rejected_face_indices)

        return surface_triangle_mapping, standalone_face_indices

    @staticmethod
    def _map_havok_instance_collision(
        havok_collisions: list[HavokCollision],
        instances: list[Instance],
        render_model,
        temp_meshes,
    ) -> dict[HavokCollision, list[int]]:
        """Map definition-local Havok faces back to their original render triangles."""
        mapped_face_indices = {collision: set() for collision in havok_collisions}
        fallback_face_indices = {collision: list(range(len(collision.faces))) for collision in havok_collisions}
        if not havok_collisions or not instances:
            return fallback_face_indices

        triangle_counts = {}
        for instance in instances:
            definition = instance.definition
            if definition in triangle_counts:
                continue

            mesh = definition.mesh
            if not mesh.valid:
                triangle_counts[definition] = 0
                continue

            mesh.render_model = render_model
            mesh.temp_meshes = temp_meshes
            mesh.instances = []
            mesh.real_mesh_index = None
            try:
                mesh._get_raw_mesh_data()
            except (IndexError, ValueError):
                triangle_counts[definition] = 0
                continue
            triangle_counts[definition] = len(mesh.tris)

        instances_by_index = {instance.index: instance for instance in instances}
        claimed_render_triangles = {}
        mapped_definitions = set()
        for collision in havok_collisions:
            for source_instance_index, face_indices in collision.source_instance_face_indices().items():
                instance = instances_by_index.get(source_instance_index)
                if instance is None:
                    continue

                definition = instance.definition
                triangle_count = triangle_counts.get(definition, 0)
                if triangle_count < 1:
                    continue
                # Collision type is object-wide in Foundry. Leave conflicting
                # faces for the standalone fallback instead of mixing a mesh.
                if definition.havok_collision_type_name not in {None, collision.collision_type_name}:
                    continue

                definition_claims = claimed_render_triangles.setdefault(definition, {})
                definition_mapped_faces = set()
                mappings = collision.to_surface_triangle_mappings(
                    [(0, 0, triangle_count)],
                    definition_claims,
                    face_indices=face_indices,
                    mapped_face_indices=definition_mapped_faces,
                )
                if not definition_mapped_faces:
                    continue

                mapped_face_indices[collision].update(definition_mapped_faces)
                if mappings:
                    definition.surface_triangle_mapping.extend(mappings)
                definition.havok_collision_type_name = collision.collision_type_name
                definition.has_collision = True
                definition.collision_is_proxy = False
                mapped_definitions.add(definition)

        mapped_count = sum(len(indices) for indices in mapped_face_indices.values())
        if mapped_count:
            utils.print_step(f"Mapped {mapped_count} Havok faces to {len(mapped_definitions)} original instance definitions")

        for collision, mapped_indices in mapped_face_indices.items():
            fallback_face_indices[collision] = [
                face_index for face_index in range(len(collision.faces))
                if face_index not in mapped_indices
            ]
        return fallback_face_indices

    @staticmethod
    def _create_havok_instance_proxies(
        havok_collisions: list[HavokCollision],
        instances: list[Instance],
        face_indices_by_collision: dict[HavokCollision, list[int]] | None = None,
    ) -> tuple[list[bpy.types.Object], dict[HavokCollision, list[int]]]:
        """Recover definition-local collision from static-compound instance children."""
        allowed_face_indices = {
            collision: set(range(len(collision.faces))) if face_indices_by_collision is None else set(face_indices_by_collision.get(collision, []))
            for collision in havok_collisions
        }
        claimed_face_indices = {collision: set() for collision in havok_collisions}
        standalone_face_indices = {collision: sorted(indices) for collision, indices in allowed_face_indices.items()}
        if not havok_collisions or not instances:
            return [], standalone_face_indices

        instances_by_index = {instance.index: instance for instance in instances}
        parts_by_definition = {}
        for collision in havok_collisions:
            for source_instance_index, face_indices in collision.source_instance_face_indices().items():
                face_indices = [face_index for face_index in face_indices if face_index in allowed_face_indices[collision]]
                if not face_indices:
                    continue
                instance = instances_by_index.get(source_instance_index)
                if instance is None or abs(instance.scale) < 1.0e-8:
                    continue

                definition = instance.definition
                render_object = definition.blender_render
                has_render_mesh = render_object is not None and render_object.type == 'MESH'
                if has_render_mesh and render_object.data.nwo.proxy_collision is not None:
                    claimed_face_indices[collision].update(face_indices)
                    continue
                if not has_render_mesh and definition.blender_collision is not None:
                    claimed_face_indices[collision].update(face_indices)
                    continue

                collision_type_name = collision.collision_type_name
                # Tool cannot safely partition shared proxy vertices by
                # collision type, so recover at most one type per definition.
                if definition.havok_collision_type_name not in {None, collision_type_name}:
                    continue

                part = parts_by_definition.get(definition)
                if part is not None and part["collision_type_name"] != collision_type_name:
                    continue
                if part is not None and part["source_instance_index"] != source_instance_index:
                    claimed_face_indices[collision].update(face_indices)
                    continue

                if part is None:
                    part = {
                        "source_instance_index": source_instance_index,
                        "collision_type": collision.collision_type,
                        "collision_type_name": collision_type_name,
                        "vertices": [],
                        "faces": [],
                        "material_indices": [],
                        "collision_materials": collision.collision_materials,
                    }
                    parts_by_definition[definition] = part
                    definition.havok_collision_type_name = collision_type_name

                used_vertex_indices = sorted({vertex_index for face_index in face_indices for vertex_index in collision.faces[face_index]})
                vertex_remap = {vertex_index: remapped_index for remapped_index, vertex_index in enumerate(used_vertex_indices)}
                first_vertex = len(part["vertices"])
                if collision.has_source_local_vertices:
                    part["vertices"].extend(collision.source_local_vertices[index] for index in used_vertex_indices)
                else:
                    world_from_definition = instance.matrix @ Matrix.Diagonal((instance.scale, instance.scale, instance.scale, 1.0))
                    definition_from_world = world_from_definition.inverted_safe()
                    part["vertices"].extend((definition_from_world @ Vector(collision.vertices[index])).to_tuple() for index in used_vertex_indices)
                part["faces"].extend(
                    tuple(first_vertex + vertex_remap[vertex_index] for vertex_index in collision.faces[face_index])
                    for face_index in face_indices
                )
                part["material_indices"].extend(
                    collision.material_indices[face_index] if face_index < len(collision.material_indices) else -1
                    for face_index in face_indices
                )
                claimed_face_indices[collision].update(face_indices)

        definition_collision_objects = []
        proxy_count = 0
        collision_only_count = 0
        for definition, part in parts_by_definition.items():
            if not part["faces"]:
                continue

            render_object = definition.blender_render
            has_render_mesh = render_object is not None and render_object.type == 'MESH'
            name = f"{render_object.name}_proxy_collision" if has_render_mesh else f"instance_definition:{definition.index}"
            collision_object = HavokCollision(
                name,
                part["vertices"],
                part["faces"],
                part["material_indices"],
                part["collision_materials"],
                collision_type=part["collision_type"],
            ).to_object()
            definition.blender_collision = collision_object
            definition.has_collision = True
            if has_render_mesh:
                collision_object.nwo.proxy_type = "collision"
                render_object.data.nwo.proxy_collision = collision_object
                definition.collision_is_proxy = True
                proxy_count += 1
            else:
                definition.collision_is_proxy = False
                collision_only_count += 1
            definition_collision_objects.append(collision_object)

        for collision, claimed_indices in claimed_face_indices.items():
            standalone_face_indices[collision] = [
                face_index for face_index in sorted(allowed_face_indices[collision])
                if face_index not in claimed_indices
            ]

        if definition_collision_objects:
            utils.print_step(f"Creating Havok Instance Collision ({proxy_count} proxies, {collision_only_count} collision-only definitions)")
        return definition_collision_objects, standalone_face_indices

    def _read_havok_collisions(self, collision_materials: list[BSPCollisionMaterial],
                               records: list[StructureBspHavokGeometry]) -> list[HavokCollision]:
        havok_collisions = []
        for record in records:
            name = f"{self.tag_path.ShortName}_{record.kind}_{record.collision_type}"
            collision = HavokCollision.from_serialized_shape(
                record.data, name, collision_materials, record.bounds_min,
                record.bounds_max, record.collision_type)
            if collision is not None:
                havok_collisions.append(collision)

        return sorted(havok_collisions, key=lambda collision: collision.collision_type)
    
def are_faces_overlapping(face1, face2):
    if not face1.normal.dot(face2.normal) > 0.999:
        return False
    
    verts1 = {vert.co.to_tuple() for vert in face1.verts}
    verts2 = {vert.co.to_tuple() for vert in face2.verts}
    
    return verts1 == verts2

def auto_merge_and_split():
    ts = bpy.context.scene.tool_settings
    ts.use_mesh_automerge         = True
    ts.use_mesh_automerge_and_split = True
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            bpy.context.view_layer.objects.active = obj

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            bpy.ops.transform.rotate(
                value=0.0,
                orient_axis='X',
                orient_type='GLOBAL'
            )

            # Back to Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')
