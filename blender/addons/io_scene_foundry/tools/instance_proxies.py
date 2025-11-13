

"""Handles the creation and maintenance of instance proxy objects - physics, collision & cookie cutters"""

import bmesh
import bpy
from ..tools.property_apply import apply_props_material

from ..utils import deselect_all_objects, get_foundry_storage_scene, is_corinth, layer_faces, set_active_object, set_object_mode, unlink

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
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        self.x_ray_state = space.shading.show_xray
                        self.shading_attr = space.shading
                        space.shading.show_xray = True
                            
        context.scene.nwo.instance_proxy_running = True
        
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        scene_nwo = context.scene.nwo
        active = scene_nwo.instance_proxy_running
        edit_mode = context.mode == 'EDIT_MESH'
        
        if event.type == 'TIMER' and not active:
            if context.mode == 'EDIT_MESH':
                bpy.ops.object.editmode_toggle()

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
    
    @classmethod
    def poll(cls, context):
        return bpy.ops.object.mode_set.poll()

    def proxy_type_items(self, context):
        items = []
        nwo = context.object.data.nwo
        if not nwo.proxy_collision:
            items.append(("collision", "Collision", ""))
        for i in range(200):
            if not getattr(nwo, f"proxy_physics{i}"):
                items.append(("physics", "Physics", ""))
                break
        if not is_corinth(context) and not nwo.proxy_cookie_cutter:
            items.append(("cookie_cutter", "Cookie Cutter", ""))

        return items

    proxy_type : bpy.props.EnumProperty(
        name="Type",
        items=proxy_type_items,
    )

    proxy_source : bpy.props.EnumProperty(
        name="Source",
        items=[
            ("bounding_box", "Bounding Box", "Generates a bounding box based on this instance"),
            ("copy", "Copy", "Copies this instance and removes any render only faces"),
            ("existing", "Mesh", "Creates a proxy using the specified scene mesh object"),
        ]
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
        ob = bpy.data.objects.new(self.proxy_name, me)
        
        return ob

    def execute(self, context):
        self.parent = context.object
        proxy_type = self.proxy_type
        if proxy_type == "":
            proxy_type = self.proxy_type_items(context)[0][0]
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
        proxy_scene = get_foundry_storage_scene()
        proxy_scene.collection.objects.link(ob)
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
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        row = layout.row(heading="Type")
        row.prop(self, "proxy_type", text="Type", expand=True)
        row = layout.row(heading="Source")
        row.prop(self, "proxy_source", text="Source", expand=True)
        if self.proxy_source == "existing":
            row = layout.row()
            row.prop_search(self, "proxy_copy", search_data=bpy.data, search_property="meshes")
        row = layout.row()
        row.prop(self, "proxy_edit", text="Edit Proxy")
    
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
            nwo.proxy_collision = None
        else:
            for i in range(200):
                if getattr(nwo, f"proxy_physics{i}") == proxy_ob:
                    setattr(nwo, f"proxy_physics{i}", None)
        
        return {'FINISHED'}
    
class NWO_ProxyInstanceCancel(bpy.types.Operator):
    bl_idname = "nwo.proxy_instance_cancel"
    bl_description = "Cancels Proxy Instance Edit"
    bl_label = "Instance Proxy Cancel"
    bl_options = {'UNDO'}

    proxy : bpy.props.StringProperty()

    def execute(self, context):
        context.scene.nwo.instance_proxy_running = False
        return {'FINISHED'}