"""Read the Coordinate3/indexed geometry emitted by classic Tool error WRLs."""
import re
import os
from collections import defaultdict


def _numbers(text):
    return [float(v) for v in re.findall(
        r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', text)]


def _label(color, palette):
    rgb = tuple(round(v, 2) for v in color[:3])
    colors = {tuple(round(v, 2) for v in c[:3]) for c in palette}
    if {(1, 0, 0), (0, 1, 0)} <= colors and rgb in {(1, 0, 0), (0, 1, 0)}:
        return 'Nearly coplanar (' + ('red)' if rgb == (1, 0, 0) else 'green)')
    return {
        (1, .5, 0): 'Overlap or duplicate (orange)',
        (1, .41, .7): 'Possible T-junction (pink)',
        (1, 0, 0): 'Bad geometry (red)',
        (0, 1, 0): 'Portal does not divide space (green)',
        (1, 1, 0): 'Portal not closed (yellow)',
        (1, 0, 1): 'Outside BSP or unearthed (magenta)',
        (0, 1, 1): 'Surface clipped away (cyan)',
        (0, 0, 1): 'Degenerate triangle or UVs (blue)',
        (0, 0, 0): 'Intersecting fog planes (black)',
    }.get(rgb, 'Diagnostic')


def error_geometry(text, *, include_styles=False):
    vertices, edges, faces = [], [], []
    edge_styles, face_styles = [], []
    # Tool writes each diagnostic in its own Separator, with local indices.
    for block in re.split(r'\bCoordinate3\s*\{', text)[1:]:
        points = re.search(r'\bpoint\s*\[([^]]*)\]', block)
        if points is None:
            continue
        values = _numbers(points[1])
        if len(values) % 3:
            raise ValueError('Invalid WRL coordinate list')
        local = list(zip(values[::3], values[1::3], values[2::3]))
        offset = len(vertices)
        vertices.extend(local)
        colors = re.search(r'\bdiffuseColor\s*\[([^]]*)\]', block)
        values = _numbers(colors[1]) if colors else [1, 0, 0]
        if not values or len(values) % 3:
            raise ValueError('Invalid WRL color list')
        transparency = re.search(r'\btransparency\s*\[([^]]*)\]', block)
        alphas = _numbers(transparency[1]) if transparency else [0]
        palette = [(*values[i:i+3], 1 - alphas[min(i // 3, len(alphas)-1)] if alphas else 1)
                   for i in range(0, len(values), 3)]
        binding = re.search(r'\bMaterialBinding\s*\{\s*value\s+(\w+)', block)
        per_vertex = binding is not None and binding[1] in {'PER_VERTEX', 'PER_VERTEX_INDEXED'}
        overall = binding is not None and binding[1] == 'OVERALL'

        def style(index):
            color = palette[min(index, len(palette)-1)]
            return color, _label(color, palette)

        for kind, indices in re.findall(
                r'Indexed(Face|Line)Set\s*\{\s*coordIndex\s*\[([^]]*)\]', block):
            polygon = []
            primitive = 0
            for index in [int(v) for v in re.findall(r'-?\d+', indices)] + [-1]:
                if index == -1:
                    if kind == 'Face' and len(polygon) >= 3:
                        faces.append(tuple(polygon))
                        face_styles.append(style(0 if overall else primitive))
                    elif kind == 'Line':
                        for a, b in zip(polygon, polygon[1:]):
                            sa = style(a-offset if per_vertex else 0 if overall else primitive)
                            sb = style(b-offset) if per_vertex else sa
                            if sa == sb:
                                edges.append((a, b))
                                edge_styles.append(sa)
                            else:
                                # Preserve both endpoint colors on Tool's
                                # PER_VERTEX line diagnostics in wire display.
                                mid = len(vertices)
                                vertices.append(tuple((x+y)*.5 for x,y in zip(vertices[a], vertices[b])))
                                edges.extend(((a, mid), (mid, b)))
                                edge_styles.extend((sa, sb))
                    if polygon:
                        primitive += 1
                    polygon = []
                else:
                    if not 0 <= index < len(local):
                        raise ValueError('WRL index outside coordinate list')
                    polygon.append(offset + index)
    if include_styles:
        return vertices, edges, faces, edge_styles, face_styles
    return vertices, edges, faces


def import_errors(path, scene, rotation, scale):
    import bpy
    from mathutils import Matrix, Vector

    vertices, edges, faces, edge_styles, face_styles = error_geometry(
        path.read_text(errors='replace'), include_styles=True)
    inverse = Matrix.Rotation(-rotation, 4, 'Z')
    vertices = [inverse @ (Vector(v) / scale) for v in vertices]
    groups = defaultdict(lambda: ([], []))
    for edge, style in zip(edges, edge_styles):
        groups[style][0].append(edge)
    for face, style in zip(faces, face_styles):
        groups[style][1].append(face)
    built = []
    try:
        for (color, label), (group_edges, group_faces) in groups.items():
            used = sorted({v for geometry in (*group_edges, *group_faces) for v in geometry})
            remap = {v: i for i, v in enumerate(used)}
            mesh = bpy.data.meshes.new(f'{path.stem} - {label}')
            built.append((mesh, color, label))
            mesh.from_pydata([vertices[v] for v in used],
                             [tuple(remap[v] for v in e) for e in group_edges],
                             [tuple(remap[v] for v in f) for f in group_faces])
            mesh.update()
    except Exception:
        for mesh, _, _ in built:
            bpy.data.meshes.remove(mesh)
        raise
    source = os.path.normcase(str(path.resolve()))
    name = f'BSP Errors - {path.stem}'
    collections = list(scene.collection.children_recursive)
    collection = next((c for c in collections
                       if c.get('foundry_wrl_source') == source), None)
    if collection is None:
        # Adopt collections created before WRL source tracking was added.
        collection = next((c for c in collections if c.name == name
                           and not c.get('foundry_wrl_source')
                           and c.nwo.type == 'exclude'), None)
    if collection is None:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
    collection['foundry_wrl_source'] = source
    collection.nwo.type = 'exclude'
    # Build the replacement first so parsing/mesh errors leave the old display.
    for old in list(collection.objects):
        old_mesh = old.data if old.type == 'MESH' else None
        collection.objects.unlink(old)
        if old.users == 0:
            bpy.data.objects.remove(old)
        if old_mesh is not None and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
    for mesh, color, label in built:
        material_name = f'WRL {label} {color}'
        material = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
        material.diffuse_color = color
        mesh.materials.append(material)
        ob = bpy.data.objects.new(f'{path.stem} - {label}', mesh)
        collection.objects.link(ob)
        ob.show_in_front = True
        ob.display_type = 'WIRE'
        ob.color = color
        ob.hide_render = True
    # Object colors also distinguish wire-only edge errors. Material slots
    # retain the same colors if the user switches an error object to Solid.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.wireframe_color_type = 'OBJECT'
    print(f'--- Imported BSP errors into excluded collection: {collection.name}')
