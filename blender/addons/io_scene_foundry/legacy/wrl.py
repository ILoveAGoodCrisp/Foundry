"""Read the Coordinate3/indexed geometry emitted by classic Tool error WRLs."""
import re
import os


def error_geometry(text):
    vertices, edges, faces = [], [], []
    # Tool writes each diagnostic in its own Separator, with local indices.
    for block in re.split(r'\bCoordinate3\s*\{', text)[1:]:
        points = re.search(r'\bpoint\s*\[([^]]*)\]', block)
        if points is None:
            continue
        values = [float(v) for v in re.findall(
            r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', points[1])]
        if len(values) % 3:
            raise ValueError('Invalid WRL coordinate list')
        local = list(zip(values[::3], values[1::3], values[2::3]))
        offset = len(vertices)
        vertices.extend(local)
        for kind, indices in re.findall(
                r'Indexed(Face|Line)Set\s*\{\s*coordIndex\s*\[([^]]*)\]', block):
            polygon = []
            for index in [int(v) for v in re.findall(r'-?\d+', indices)] + [-1]:
                if index == -1:
                    if kind == 'Face' and len(polygon) >= 3:
                        faces.append(tuple(polygon))
                    elif kind == 'Line':
                        edges.extend(zip(polygon, polygon[1:]))
                    polygon = []
                else:
                    if not 0 <= index < len(local):
                        raise ValueError('WRL index outside coordinate list')
                    polygon.append(offset + index)
    return vertices, edges, faces


def import_errors(path, scene, rotation, scale):
    import bpy
    from mathutils import Matrix, Vector

    vertices, edges, faces = error_geometry(path.read_text(errors='replace'))
    inverse = Matrix.Rotation(-rotation, 4, 'Z')
    vertices = [inverse @ (Vector(v) / scale) for v in vertices]
    mesh = bpy.data.meshes.new(path.stem)
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()
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
    if not vertices:
        bpy.data.meshes.remove(mesh)
        return
    ob = bpy.data.objects.new(path.stem, mesh)
    collection.objects.link(ob)
    ob.show_in_front = True
    ob.display_type = 'WIRE'
    ob.color = (1, 0, 0, 1)
    ob.hide_render = True
    print(f'--- Imported BSP errors into excluded collection: {collection.name}')
