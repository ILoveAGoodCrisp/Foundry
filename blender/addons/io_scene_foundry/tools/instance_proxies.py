

"""Handles the creation and maintenance of instance proxy objects - physics, collision & cookie cutters"""

import bmesh
import bpy
from ..tools.property_apply import apply_props_material
from ..game_capabilities import instance_proxy_types

from ..utils import deselect_all_objects, get_game, get_scene_props, set_active_object, set_object_mode, unlink


def coacd_property_annotations():
    return {
        "coacd_threshold": bpy.props.FloatProperty(
            name="Concavity Threshold",
            description="Controls how tightly hulls hug the mesh; higher values create fewer hulls and run faster",
            default=0.3,
            min=0.01,
            max=1.0,
        ),
        "coacd_max_hulls": bpy.props.IntProperty(
            name="Max Hulls",
            description="Sets the absolute limit on generated convex shapes when Merge Hulls is enabled (-1 for no limit)",
            default=5,
            min=-1,
            max=64,
        ),
        "coacd_preprocess_mode": bpy.props.EnumProperty(
            name="Preprocess",
            description="Controls manifold preprocessing mode. Set to 'Off' for open or unclosed meshes",
            items=[
                ("auto", "Auto", "Automatically checks and preprocesses non-manifold meshes"),
                ("on", "On", "Forces preprocessing on (for non-watertight/dirty meshes)"),
                ("off", "Off", "Forces preprocessing off (retains original open mesh structure)"),
            ],
            default="auto",
        ),
        "coacd_decimate": bpy.props.BoolProperty(
            name="Decimate Hulls",
            description="Enable vertex decimation on generated convex hulls",
            default=True,
        ),
        "coacd_max_vertices": bpy.props.IntProperty(
            name="Max Vertices per Hull",
            description="Maximum number of vertices allowed for each convex hull",
            default=32,
            min=4,
            max=1024,
        ),
        "coacd_preprocess_resolution": bpy.props.IntProperty(
            name="Preprocess Resolution",
            description="Resolution for manifold preprocessing (20-100)",
            default=20,
            min=20,
            max=100,
        ),
        "coacd_sample_resolution": bpy.props.IntProperty(
            name="Sample Resolution",
            description="Sampling resolution for Hausdorff distance calculation (1000-10000)",
            default=1000,
            min=1000,
            max=10000,
        ),
        "coacd_mcts_nodes": bpy.props.IntProperty(
            name="MCTS Nodes",
            description="Max number of child nodes in MCTS (10-40)",
            default=10,
            min=10,
            max=40,
        ),
        "coacd_mcts_iterations": bpy.props.IntProperty(
            name="MCTS Iterations",
            description="Number of search iterations in MCTS (60-2000)",
            default=60,
            min=60,
            max=2000,
        ),
        "coacd_mcts_max_depth": bpy.props.IntProperty(
            name="MCTS Max Depth",
            description="Max search depth in MCTS (1-7)",
            default=2,
            min=1,
            max=7,
        ),
        "coacd_pca": bpy.props.BoolProperty(
            name="PCA",
            description="Enable PCA pre-processing",
            default=False,
        ),
        "coacd_merge": bpy.props.BoolProperty(
            name="Merge Hulls",
            description="Merge hulls after decomposition; enables Max Hulls but can substantially increase processing time",
            default=False,
        ),
        "coacd_seed": bpy.props.IntProperty(
            name="Seed",
            description="Random seed used for sampling (0 for random)",
            default=0,
            min=0,
        ),
        "coacd_advanced": bpy.props.BoolProperty(
            name="Advanced Settings",
            description="Show advanced CoACD parameters",
            default=False,
        ),
    }


def draw_coacd_settings(layout, settings):
    layout.prop(settings, "coacd_threshold")
    layout.prop(settings, "coacd_merge")
    row = layout.row()
    row.enabled = settings.coacd_merge
    row.prop(settings, "coacd_max_hulls")
    layout.prop(settings, "coacd_decimate")
    if settings.coacd_decimate:
        layout.prop(settings, "coacd_max_vertices")

    advanced = layout.box()
    advanced.prop(
        settings,
        "coacd_advanced",
        text="Advanced Settings",
        icon="TRIA_DOWN" if settings.coacd_advanced else "TRIA_RIGHT",
        emboss=False,
    )
    if settings.coacd_advanced:
        advanced.prop(settings, "coacd_preprocess_mode")
        if settings.coacd_preprocess_mode != "off":
            advanced.prop(settings, "coacd_preprocess_resolution")
        advanced.prop(settings, "coacd_sample_resolution")
        advanced.prop(settings, "coacd_mcts_nodes")
        advanced.prop(settings, "coacd_mcts_iterations")
        advanced.prop(settings, "coacd_mcts_max_depth")
        advanced.prop(settings, "coacd_pca")
        advanced.prop(settings, "coacd_seed")


def _close_manifold_holes(bm):
    """Return a hole-capped copy when it forms a valid solid, otherwise return bm."""
    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    if not boundary_edges or any(len(edge.link_faces) > 2 for edge in bm.edges):
        return bm

    repaired = bm.copy()
    bounds = [vert.co for vert in repaired.verts]
    diagonal = (max(bounds, key=lambda co: co.x).x - min(bounds, key=lambda co: co.x).x) ** 2
    diagonal += (max(bounds, key=lambda co: co.y).y - min(bounds, key=lambda co: co.y).y) ** 2
    diagonal += (max(bounds, key=lambda co: co.z).z - min(bounds, key=lambda co: co.z).z) ** 2
    merge_distance = max(diagonal ** 0.5 * 1e-7, 1e-9)
    bmesh.ops.remove_doubles(repaired, verts=repaired.verts, dist=merge_distance)
    repaired_boundary = [edge for edge in repaired.edges if len(edge.link_faces) == 1]
    bmesh.ops.holes_fill(repaired, edges=repaired_boundary, sides=0)
    bmesh.ops.recalc_face_normals(repaired, faces=repaired.faces[:])

    is_manifold = all(len(edge.link_faces) == 2 for edge in repaired.edges)
    has_volume = is_manifold and abs(repaired.calc_volume(signed=True)) > 1e-8
    if not has_volume:
        repaired.free()
        return bm

    bm.free()
    return repaired


def run_coacd(context, active_ob, settings, log_level="warn"):
    """Decompose an object's evaluated mesh and return (parts, elapsed_seconds)."""
    from time import perf_counter

    import coacd
    import numpy as np

    eval_ob = active_ob.evaluated_get(context.evaluated_depsgraph_get())
    mesh = eval_ob.to_mesh()
    try:
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            bm = _close_manifold_holes(bm)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(mesh)
        finally:
            bm.free()

        vertices = np.empty((len(mesh.vertices), 3), dtype=np.float32)
        mesh.vertices.foreach_get('co', vertices.ravel())

        mesh.calc_loop_triangles()
        faces = np.empty((len(mesh.loop_triangles), 3), dtype=np.int32)
        mesh.loop_triangles.foreach_get('vertices', faces.ravel())
    finally:
        eval_ob.to_mesh_clear()

    merge = settings.coacd_merge
    kwargs = {
        "threshold": settings.coacd_threshold,
        # CoACD only applies the hull limit during its expensive merge pass.
        "max_convex_hull": settings.coacd_max_hulls if merge else -1,
        "preprocess_mode": settings.coacd_preprocess_mode,
        "preprocess_resolution": settings.coacd_preprocess_resolution,
        "resolution": settings.coacd_sample_resolution,
        "mcts_nodes": settings.coacd_mcts_nodes,
        "mcts_iterations": settings.coacd_mcts_iterations,
        "mcts_max_depth": settings.coacd_mcts_max_depth,
        "pca": settings.coacd_pca,
        "merge": merge,
        "seed": settings.coacd_seed,
    }

    if settings.coacd_decimate:
        kwargs["max_ch_vertex"] = settings.coacd_max_vertices
        kwargs["decimate"] = True

    coacd.set_log_level(log_level)
    start = perf_counter()
    parts = coacd.run_coacd(coacd.Mesh(vertices, faces), **kwargs)
    return parts, perf_counter() - start


class NWO_ProxyInstanceEdit(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_edit"
    bl_description = "Switches to Proxy instance edit mode"
    bl_label = "Instance Proxy Mode"
    bl_options = {'UNDO'}

    proxy : bpy.props.StringProperty()

    _timer = None
    
    @classmethod
    def poll(cls, context):
        return bpy.ops.object.mode_set.poll()

    def exit_local_view(self, context):
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                view_3d = area.spaces.active
                if view_3d.local_view:
                    bpy.ops.view3d.localview()
                    break

    def execute(self, context):
        self.old_sel = context.selected_objects.copy()
        self.linked_objects = []
        self.x_ray_state = False
        self.shading_attr = None
        self.exit_local_view(context)

        set_object_mode(context)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.parent = context.object
        self.proxy_ob = bpy.data.objects[self.proxy]
        self.scene_coll = context.scene.collection.objects
        old_ob = None
        # if self.proxy_ob.nwo.proxy_parent != self.parent.data:
        #     old_ob = self.proxy_ob
        #     self.proxy_ob = self.proxy_ob.copy()
        #     self.proxy_ob.data = self.proxy_ob.data.copy()
        #     self.proxy_ob.nwo.proxy_parent = self.parent.data
        #     for collection in old_ob.users_collection:
        #         collection.objects.link(self.proxy_ob)
                
        data_nwo = self.parent.data.nwo
        if data_nwo.proxy_collision is not None:
            if data_nwo.proxy_collision == old_ob:
                data_nwo.proxy_collision = self.proxy_ob
            self.linked_objects.append(data_nwo.proxy_collision)
            
            if context.scene.collection not in data_nwo.proxy_collision.users_collection:
                self.scene_coll.link(data_nwo.proxy_collision)
                
            data_nwo.proxy_collision.hide_set(False)
            data_nwo.proxy_collision.select_set(True)
            data_nwo.proxy_collision.matrix_world = self.parent.matrix_world
        if data_nwo.proxy_cookie_cutter is not None:
            if data_nwo.proxy_cookie_cutter == old_ob:
                data_nwo.proxy_cookie_cutter = self.proxy_ob
            self.linked_objects.append(data_nwo.proxy_cookie_cutter)
            
            if context.scene.collection not in data_nwo.proxy_cookie_cutter.users_collection:
                self.scene_coll.link(data_nwo.proxy_cookie_cutter)

            data_nwo.proxy_cookie_cutter.hide_set(False)
            data_nwo.proxy_cookie_cutter.select_set(True)
            data_nwo.proxy_cookie_cutter.matrix_world = self.parent.matrix_world
        for i in range(200):
            phys = getattr(data_nwo, f"proxy_physics{i}", None)
            if phys is not None:
                if phys == old_ob:
                    setattr(data_nwo, f"proxy_physics{i}", self.proxy_ob)
                    phys = self.proxy_ob
                self.linked_objects.append(phys)
                
                if context.scene.collection not in phys.users_collection:
                    self.scene_coll.link(phys)
 
                phys.hide_set(False)
                phys.select_set(True)
                phys.matrix_world = self.parent.matrix_world
                
        bpy.ops.view3d.localview()
        deselect_all_objects()
        self.proxy_ob.select_set(True)
        set_active_object(self.proxy_ob)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='SELECT')
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        self.x_ray_state = space.shading.show_xray
                        self.shading_attr = space.shading
                        space.shading.show_xray = True
                            
        get_scene_props().instance_proxy_running = True
        
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        scene_nwo = get_scene_props()
        active = scene_nwo.instance_proxy_running
        edit_mode = context.mode == 'EDIT_MESH'
        
        if event.type == 'TIMER' and not active:
            if context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

            self.exit_local_view(context)
            if self.shading_attr is not None:
                self.shading_attr.show_xray = self.x_ray_state
            try:
                self.proxy_ob.select_set(False)
                for ob in self.linked_objects:
                    self.scene_coll.unlink(ob)
                for sel_ob in self.old_sel:
                    sel_ob.select_set(True)
                set_active_object(self.parent)
            except:
                pass
            scene_nwo.instance_proxy_running = False
            return {'FINISHED'}
        
        return {'PASS_THROUGH'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.scene.instance_proxy_running = False

class NWO_ProxyInstanceNew(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_new"
    bl_description = "New Proxy Instance"
    bl_label = "Instance Proxy New"
    bl_options = {'REGISTER', 'UNDO'}
    __annotations__ = coacd_property_annotations()
    
    @classmethod
    def poll(cls, context):
        return bpy.ops.object.mode_set.poll()

    def proxy_type_items(self, context):
        items = []
        nwo = context.object.data.nwo
        supported_types = instance_proxy_types(get_game())
        if 'collision' in supported_types and not nwo.proxy_collision:
            items.append(("collision", "Collision", "", 0))
        if 'physics' in supported_types:
            for i in range(200):
                if not getattr(nwo, f"proxy_physics{i}"):
                    items.append(("physics", "Physics", "", 1))
                    break
        if 'cookie_cutter' in supported_types and not nwo.proxy_cookie_cutter:
            items.append(("cookie_cutter", "Cookie Cutter", "", 2))

        return items

    proxy_type : bpy.props.EnumProperty(
        name="Type",
        items=proxy_type_items,
    )

    def proxy_source_items(self, context):
        items = [
            ("bounding_box", "Bounding Box", "Generates a bounding box based on this instance"),
            ("copy", "Copy", "Copies this instance and removes any render only faces"),
            ("existing", "Mesh", "Creates a proxy using the specified scene mesh object"),
        ]
        
        proxy_type = getattr(self, "proxy_type", "")
        if proxy_type == "":
            pt_items = NWO_ProxyInstanceNew.proxy_type_items(self, context)
            if pt_items:
                proxy_type = pt_items[0][0]
                
        if proxy_type == "physics":
            items.append(("coacd", "Decomposition", "Generates optimized game-ready convex hulls using CoACD"))
            
        return items

    proxy_source : bpy.props.EnumProperty(
        name="Source",
        items=proxy_source_items,
    )

    proxy_copy : bpy.props.StringProperty(
        name="Mesh"
    )

    proxy_edit : bpy.props.BoolProperty(
        name="Edit",
        default=True
    )

    def build_bounding_box(self):
        me = bpy.data.meshes.new(self.proxy_name)
        ob = bpy.data.objects.new(self.proxy_name, me)
        bm = bmesh.new()
        bbox = self.parent.bound_box
        for co in bbox:
            bmesh.ops.create_vert(bm, co=co)

        bm.verts.ensure_lookup_table()
        back_face = [bm.verts[0], bm.verts[1], bm.verts[2], bm.verts[3]]
        front_face = [bm.verts[4], bm.verts[5], bm.verts[6], bm.verts[7]]
        left_face = [bm.verts[0], bm.verts[1], bm.verts[4], bm.verts[5]]
        right_face = [bm.verts[2], bm.verts[3], bm.verts[6], bm.verts[7]]
        bottom_face = [bm.verts[0], bm.verts[3], bm.verts[4], bm.verts[7]]
        top_face = [bm.verts[1], bm.verts[2], bm.verts[5], bm.verts[6]]
        bmesh.ops.contextual_create(bm, geom=back_face, mat_nr=0, use_smooth=False)
        bmesh.ops.contextual_create(bm, geom=front_face, mat_nr=0, use_smooth=False)
        bmesh.ops.contextual_create(bm, geom=left_face, mat_nr=0, use_smooth=False)
        bmesh.ops.contextual_create(bm, geom=right_face, mat_nr=0, use_smooth=False)
        bmesh.ops.contextual_create(bm, geom=bottom_face, mat_nr=0, use_smooth=False)
        bmesh.ops.contextual_create(bm, geom=top_face, mat_nr=0, use_smooth=False)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()

        return ob

    def build_from_parent(self):
        # bm = bmesh.new()
        # bm.from_mesh(self.parent.data)

        # cut out render_only faces
        # for f in bm.faces:
        #     f.smooth = False
        #     f.select = False

        # face_attributes = self.parent.data.nwo.face_props
        # layer_faces_dict = {
        #     layer: layer_faces(bm, bm.faces.layers.int.get(layer.attribute_name))
        #     for layer in face_attributes
        # }
        
        # for layer, face_seq in layer_faces_dict.items():
        #     face_count = len(face_seq)
        #     if not face_count:
        #         continue
        #     if layer.face_mode_override and layer.face_mode_ui in (
        #         "render_only",
        #         "lightmap_only",
        #         "shadow_only",
        #     ):
        #         for f in face_seq:
        #             f.select = True

        # selected = [f for f in bm.faces if f.select]
        # bmesh.ops.delete(bm, geom=selected, context="FACES")

        # make new object to take this bmesh
        me = bpy.data.meshes.new(self.proxy_name)
        # bm.to_mesh(me)
        ob = bpy.data.objects.new(me.name, self.parent.data.copy())

        return ob
    
    def copy_mesh(self):
        if not self.proxy_copy:
            return None
        
        me = bpy.data.meshes.new(self.proxy_name)
        bm = bmesh.new()
        bm.from_mesh(bpy.data.meshes[self.proxy_copy])
        for f in bm.faces:
            f.smooth = False

        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(self.proxy_name, me)
        
        return ob

    def build_coacd(self, context):
        from time import perf_counter

        active_ob = self.parent
        original_selected = context.selected_objects.copy()
        created_meshes = []
        created_proxies = []
        assignments = []

        try:
            parts, decomposition_time = run_coacd(context, active_ob, self)

            if not parts:
                self.report({'ERROR'}, "CoACD generated no mesh hulls.")
                return {'CANCELLED'}

            original_name = active_ob.name
            armature_parent = active_ob.parent
            parent_nwo = active_ob.data.nwo
            available_slots = [
                f"proxy_physics{i}"
                for i in range(200)
                if getattr(parent_nwo, f"proxy_physics{i}", None) is None
            ]
            if len(parts) > len(available_slots):
                self.report(
                    {'ERROR'},
                    f"CoACD generated {len(parts)} hulls, but only {len(available_slots)} physics proxy slots are free."
                )
                return {'CANCELLED'}

            proxy_start = perf_counter()
            for idx, (p_verts, p_faces) in enumerate(parts):
                proxy_name = f"$physics_hull_{original_name}_{idx:02d}"
                me = bpy.data.meshes.new(proxy_name)
                created_meshes.append(me)
                me.from_pydata(p_verts.tolist(), [], p_faces.tolist())
                me.update()

                proxy_ob = bpy.data.objects.new(proxy_name, me)
                created_proxies.append(proxy_ob)
                proxy_ob.nwo.proxy_type = "physics"
                me.nwo.mesh_type = '_connected_geometry_mesh_type_physics'
                proxy_ob.matrix_world = active_ob.matrix_world.copy()

                if armature_parent and armature_parent.type == 'ARMATURE':
                    matrix_world = proxy_ob.matrix_world.copy()
                    proxy_ob.parent = armature_parent
                    proxy_ob.matrix_world = matrix_world

                slot = available_slots[idx]
                setattr(parent_nwo, slot, proxy_ob)
                assignments.append((slot, proxy_ob))

            proxy_time = perf_counter() - proxy_start
            self.report(
                {'INFO'},
                f"Generated {len(created_proxies)} Havok hulls in "
                f"{decomposition_time + proxy_time:.2f}s "
                f"(CoACD {decomposition_time:.2f}s, proxies {proxy_time:.2f}s)."
            )

        except ImportError:
            self.report({'ERROR'}, "CoACD module not found. Please rebuild the extension with build_extension.py")
            return {'CANCELLED'}
        except Exception as e:
            parent_nwo = active_ob.data.nwo
            for slot, proxy_ob in reversed(assignments):
                if getattr(parent_nwo, slot, None) == proxy_ob:
                    setattr(parent_nwo, slot, None)
            for proxy_ob in reversed(created_proxies):
                bpy.data.objects.remove(proxy_ob, do_unlink=True)
            for proxy_mesh in reversed(created_meshes):
                if proxy_mesh.users == 0:
                    bpy.data.meshes.remove(proxy_mesh)
            self.report({'ERROR'}, f"Error during CoACD physics generation: {str(e)}")
            return {'CANCELLED'}

        finally:
            for ob in original_selected:
                try:
                    ob.select_set(True)
                except:
                    pass
            try:
                context.view_layer.objects.active = active_ob
            except:
                pass

        return {'FINISHED'}

    def ensure_available_options(self, context):
        types = [item[0] for item in self.proxy_type_items(context)]
        if not types:
            self.report({'WARNING'}, "No instance proxy slots are available")
            return False
        if self.proxy_type not in types:
            self.proxy_type = types[0]
        sources = [item[0] for item in self.proxy_source_items(context)]
        if self.proxy_source not in sources:
            self.proxy_source = sources[0]
        return True

    def execute(self, context):
        if not self.ensure_available_options(context):
            return {'CANCELLED'}
        self.parent = context.object
        proxy_type = self.proxy_type
            
        if self.proxy_source == "coacd":
            if proxy_type != "physics":
                self.report({'WARNING'}, "CoACD only generates Physics proxies.")
                return {'CANCELLED'}
            return self.build_coacd(context)

        # self.scene_coll = context.scene.collection.objects
        self.proxy_name = f"{self.parent.name}_proxy_{proxy_type}"
        if self.proxy_source == "bounding_box":
            ob = self.build_bounding_box()
        elif self.proxy_source == "copy":
            ob = self.build_from_parent()
        else:
            ob = self.copy_mesh()

        if ob is None:
            self.report({'WARNING'}, "No Mesh specified")
            return {'CANCELLED'}

        # self.scene_coll.link(ob)
        # ob.nwo.proxy_parent = self.parent.data
        ob.nwo.proxy_type = proxy_type
        # proxy_scene = get_foundry_storage_scene()
        # proxy_scene.collection.objects.link(ob)
        if proxy_type == "physics":
            for i in range(200):
                if getattr(self.parent.data.nwo, f"proxy_physics{i}", None) is None:
                    print("setting for ", f"proxy_physics{i}")
                    setattr(self.parent.data.nwo, f"proxy_physics{i}", ob)
                    break
            else:
                setattr(self.parent.data.nwo, "proxy_physics0", ob)
        else:
            setattr(self.parent.data.nwo, f"proxy_{proxy_type}", ob)
        if proxy_type == "collision":
            ob.data.nwo.mesh_type = "_connected_geometry_mesh_type_collision"
            if self.parent.data.materials:
                ob.data.materials.append(self.parent.data.materials[0])
        elif proxy_type == "physics":
            pass
            # apply_props_material(ob, "Physics")
        else:
            apply_props_material(ob, "CookieCutter")

        if self.proxy_edit:
            bpy.ops.nwo.proxy_instance_edit(proxy=ob.name)
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if not self.ensure_available_options(context):
            return {'CANCELLED'}
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        col = layout.column()
        col.label(text="Type")
        col.prop(self, "proxy_type", text="Type", expand=True)
        col.label(text="Source")
        col.prop(self, "proxy_source", text="Source", expand=True)
        if self.proxy_source == "existing":
            col.prop_search(self, "proxy_copy", search_data=bpy.data, search_property="meshes")
        elif self.proxy_source == "coacd":
            layout.separator()
            draw_coacd_settings(layout, self)
                
        if self.proxy_source != "coacd":
            col.prop(self, "proxy_edit", text="Edit Proxy")
    
class NWO_ProxyInstanceCopyToSelected(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_copy_to_selected"
    bl_label = "Copy to Selected"
    bl_description = "Copy the active instance's proxies to the other selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}

    copy_mode: bpy.props.EnumProperty(
        name="Copy Method",
        items=[
            ("DUPLICATE", "Duplicate", "Create independent proxy objects and meshes"),
            ("LINKED", "Duplicate and Link", "Create proxy objects sharing the source proxy meshes"),
        ],
        default="DUPLICATE",
    )

    @staticmethod
    def proxy_slots():
        return ("proxy_collision", "proxy_cookie_cutter", *(f"proxy_physics{i}" for i in range(200)))

    @staticmethod
    def targets(context):
        return [
            ob for ob in context.selected_objects
            if ob != context.object and ob.type == 'MESH' and ob.data is not None
            and ob.is_editable and ob.data.is_editable and not ob.nwo.proxy_type
        ]

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (
            context.mode == 'OBJECT' and ob is not None and ob.type == 'MESH'
            and ob in context.selected_objects and not ob.nwo.proxy_type
            and any(getattr(ob.data.nwo, slot, None) is not None for slot in cls.proxy_slots())
            and bool(cls.targets(context))
        )

    def invoke(self, context, _event):
        self.copy_mode = 'DUPLICATE'
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Copy proxies from {context.object.name}")
        layout.prop(self, "copy_mode", expand=True)
        layout.label(text="Replaces existing proxies on selected mesh objects.")

    def execute(self, context):
        if not self.poll(context):
            self.report({'WARNING'}, "Select an active instance with proxies and another editable mesh object")
            return {'CANCELLED'}

        source = context.object
        slots = self.proxy_slots()
        source_proxies = {slot: getattr(source.data.nwo, slot, None) for slot in slots}
        created_objects = []
        created_meshes = []
        assignments = []
        targets = self.targets(context)
        try:
            for target in targets:
                # Proxy pointers live on the mesh: isolate this target from the
                # source and any other objects using the same instance mesh.
                original_mesh = target.data
                target_mesh = original_mesh
                if original_mesh.users > 1:
                    target_mesh = original_mesh.copy()
                    created_meshes.append(target_mesh)
                old_proxies = {slot: getattr(original_mesh.nwo, slot, None) for slot in slots}
                copies = {}
                target_proxies = {}
                for slot, proxy in source_proxies.items():
                    if proxy is None:
                        target_proxies[slot] = None
                        continue
                    if proxy not in copies:
                        duplicate = proxy.copy()
                        created_objects.append(duplicate)
                        if self.copy_mode == 'DUPLICATE':
                            duplicate.data = proxy.data.copy()
                            created_meshes.append(duplicate.data)
                        duplicate.name = f"{target.name}_{slot}"
                        duplicate.parent = target.parent if target.parent and target.parent.type == 'ARMATURE' else None
                        duplicate.matrix_world = target.matrix_world.copy()
                        copies[proxy] = duplicate
                    target_proxies[slot] = copies[proxy]

                assignments.append((target, original_mesh, old_proxies))
                target.data = target_mesh
                for slot, proxy in target_proxies.items():
                    setattr(target_mesh.nwo, slot, proxy)
        except Exception as exc:
            for target, original_mesh, old_proxies in reversed(assignments):
                target.data = original_mesh
                for slot, proxy in old_proxies.items():
                    setattr(original_mesh.nwo, slot, proxy)
            for duplicate in reversed(created_objects):
                bpy.data.objects.remove(duplicate, do_unlink=True)
            for mesh in reversed(created_meshes):
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            self.report({'ERROR'}, f"Could not copy instance proxies: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Copied instance proxies to {len(targets)} selected objects")
        return {'FINISHED'}


class NWO_ProxyInstanceDelete(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_delete"
    bl_description = "Unlinks a proxy object"
    bl_label = "Instance Proxy Unlink"
    bl_options = {'UNDO'}

    proxy : bpy.props.StringProperty()
    
    @classmethod
    def poll(cls, context):
        return bpy.ops.object.mode_set.poll()

    def execute(self, context):
        proxy_ob = bpy.data.objects.get(self.proxy)
        if proxy_ob is None:
            return {'CANCELLED'}
        
        parent_ob = context.object
        
        if proxy_ob.data is None:
            return {'CANCELLED'}
        
        nwo = parent_ob.data.nwo
        
        if nwo is None:
            return {'CANCELLED'}
        
        if nwo.proxy_collision == proxy_ob:
            nwo.proxy_collision = None
        elif nwo.proxy_cookie_cutter == proxy_ob:
            nwo.proxy_cookie_cutter = None
        else:
            for i in range(200):
                if getattr(nwo, f"proxy_physics{i}") == proxy_ob:
                    setattr(nwo, f"proxy_physics{i}", None)
        
        return {'FINISHED'}


class NWO_ProxyInstancePhysicsClear(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_physics_clear"
    bl_label = "Clear Physics Proxies"
    bl_description = "Clear every physics proxy from this instance"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None or ob.type != 'MESH' or ob.data is None:
            return False
        nwo = ob.data.nwo
        return any(getattr(nwo, f"proxy_physics{i}", None) is not None for i in range(200))

    def execute(self, context):
        nwo = context.object.data.nwo
        proxies = set()
        cleared = 0
        for i in range(200):
            slot = f"proxy_physics{i}"
            proxy_ob = getattr(nwo, slot, None)
            if proxy_ob is None:
                continue
            proxies.add(proxy_ob)
            setattr(nwo, slot, None)
            cleared += 1

        for proxy_ob in proxies:
            if proxy_ob.users != 0:
                continue
            proxy_mesh = proxy_ob.data if proxy_ob.type == 'MESH' else None
            bpy.data.objects.remove(proxy_ob)
            if proxy_mesh is not None and proxy_mesh.users == 0:
                bpy.data.meshes.remove(proxy_mesh)

        self.report({'INFO'}, f"Cleared {cleared} physics {'proxy' if cleared == 1 else 'proxies'}.")
        return {'FINISHED'}

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        nwo = context.object.data.nwo
        count = sum(
            getattr(nwo, f"proxy_physics{i}", None) is not None
            for i in range(200)
        )
        layout = self.layout
        layout.label(
            text=f"Clear all {count} physics {'proxy' if count == 1 else 'proxies'}?",
            icon='ERROR',
        )
        layout.label(text="This removes them from the active instance.")


class NWO_ProxyInstanceCancel(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_cancel"
    bl_description = "Cancels Proxy Instance Edit"
    bl_label = "Instance Proxy Cancel"
    bl_options = {'UNDO'}

    proxy : bpy.props.StringProperty()

    def execute(self, context):
        get_scene_props().instance_proxy_running = False
        return {'FINISHED'}
