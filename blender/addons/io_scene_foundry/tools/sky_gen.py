class ImageToVertexColor():
    def __init__():
        """"""
        pass

    def get_verts_color_dict(self, ob):
        """Loops through each vert, gets the color of the material using the UV, and creates a dict in the form vert: [r,g,b]"""
        me = ob.data
        faces = me.polygons
        for f in faces:
            mat_index = f.material_index
            # get image texture
            material = me.materials[mat_index]
            if material and material.use_nodes and material.node_tree:
                node_tree  = material.node_tree.nodes
                for node in node_tree:
                    if node.type in ('TEX_IMAGE', 'TEX_ENVIRONMENT'):
                        image_node = node
                        break
                else:
                    continue

            uv_layer = me.uv_layers.active.data if me.uv_layers.active else None
            if not uv_layer:
                continue
            for loop_index in f.loop_indices:
                vertex_index = me.loops[loop_index].vertex_index
                uv_data = uv_layer[loop_index].uv
                # get the color at this index
                image = image_node.image
                if image:
                    width, height = image.size
                    tex_x = int(uv_data[0] * width)
                    tex_y = int(uv_data[1] * height)
                    color = image.pixels[(tex_y * width + tex_x) * 4 : (tex_y * width + tex_x) * 4 + 3]

class SkyGen():
    def __init__(self):
        pass

    def get_face_color_dict(self):
        pass