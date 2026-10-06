"""Detect an unchanged native ASS scene without depending on mesh index order.

Blender's editable cleanup changes vertex indices and custom-normal encoding.
Compare corners, resolved face overrides and authoring settings instead. A
complete unchanged scene can keep the compiler's original records, including
unused vertices and degenerate authoring faces which Blender cannot represent.
"""
import hashlib
import json


_UI_FIELDS = {'name', 'attribute_name', 'face_count', 'color', 'index', 'rna_type'}
_EXPORT_CACHE_FIELDS = {'collection_region', 'collection_permutation', 'export_collection'}


def properties(group, skip=()):
    result = {}
    for field in group.bl_rna.properties:
        name = field.identifier
        if name in skip or name == 'rna_type' or field.type == 'COLLECTION':
            continue
        value = getattr(group, name)
        if field.type == 'POINTER':
            if value is None or hasattr(value, 'name_full'):
                result[name] = None if value is None else (value.bl_rna.identifier, value.name_full)
            continue
        result[name] = list(value) if getattr(field, 'is_array', False) else value
    return result


def collection_states():
    import bpy
    parents = {}
    for parent in bpy.data.collections:
        for child in parent.children:
            parents.setdefault(child, []).append(parent)
    result = {}
    def state(collection):
        if collection not in result:
            result[collection] = (collection.name, properties(collection.nwo),
                                  sorted(state(parent) for parent in parents.get(collection, ())))
        return result[collection]
    for collection in bpy.data.collections:
        state(collection)
    return result


def fingerprint(ob, *, details=False, collections=None):
    collections = collection_states() if collections is None else collections
    value = dict(name=ob.name, matrix=[list(row) for row in ob.matrix_world],
                 parent=(ob.parent.name if ob.parent else None, ob.parent_type, ob.parent_bone),
                 properties=properties(ob.nwo, _EXPORT_CACHE_FIELDS), modifiers=[],
                 collections=sorted(collections[c] for c in ob.users_collection if c in collections),
                 constraints=[properties(c) for c in ob.constraints])
    for modifier in ob.modifiers:
        value['modifiers'].append(properties(modifier))
    if ob.type == 'MESH':
        mesh = ob.data
        source = mesh.attributes.get('legacy_source_normal')
        baseline = mesh.attributes.get('legacy_import_normal')
        if source is not None and baseline is not None:
            if any((normal.vector - imported.vector).length > 1e-7
                   for normal,imported in zip(mesh.corner_normals, baseline.data)):
                return None
        material_values = []
        for material in mesh.materials:
            material_values.append(None if material is None else
                dict(name=material.name, properties=properties(material.nwo),
                     overrides=[properties(prop, _UI_FIELDS) for prop in material.nwo.material_props]))
        overrides = []
        for prop in mesh.nwo.face_props:
            signature = json.dumps(properties(prop, _UI_FIELDS), sort_keys=True)
            attribute = mesh.attributes.get(prop.attribute_name)
            mask = [bool(v.value) for v in attribute.data] if attribute is not None else [True] * len(mesh.polygons)
            overrides.append((signature,mask))
        identities = mesh.attributes.get('legacy_source_vertex')
        uv_layers = list(mesh.uv_layers)
        colors = list(mesh.color_attributes)
        faces = []
        for face in mesh.polygons:
            corners = []
            for index in face.loop_indices:
                loop = mesh.loops[index]
                corners.append((identities.data[index].value if identities is not None else -1,
                    tuple(mesh.vertices[loop.vertex_index].co),
                    tuple(source.data[index].vector if source is not None else mesh.corner_normals[index].vector),
                    tuple(tuple(uv.data[index].uv) for uv in uv_layers),
                    tuple(tuple(layer.data[index if layer.domain == 'CORNER' else loop.vertex_index].color) for layer in colors),
                    tuple((attr.name,attr.data[index].value) for attr in mesh.attributes
                          if attr.domain == 'CORNER' and attr.name.startswith('ass_uv_w_'))))
            corners = tuple(corners)
            faces.append((min(corners[i:] + corners[:i] for i in range(len(corners))),
                          material_values[face.material_index] if face.material_index < len(material_values) else None,
                          sorted({signature for signature,mask in overrides if mask[face.index]})))
        # JSON keys sort dictionaries; the serialized records sort faces even
        # when their dictionaries would otherwise be unorderable in Python.
        value['geometry'] = sorted(json.dumps(face,sort_keys=True) for face in faces)
        value['mesh_properties'] = properties(mesh.nwo)
        value['shape_keys'] = [(key.name, key.value, [tuple(v.co) for v in key.data])
                               for key in mesh.shape_keys.key_blocks] if mesh.shape_keys else []
    elif ob.type == 'LIGHT':
        value['light'] = properties(ob.data)
        value['light_properties'] = properties(ob.data.nwo)
    return value if details else hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def capture_collections(collections, objects, scene):
    objects = list(objects)
    states = collection_states()
    for collection in collections:
        if not collection.get('ass_source_scene'):
            continue
        key = collection['ass_source_key']
        members = [ob for ob in objects if ob.get('ass_source_key') == key and ob.get('ass_object_key')]
        if members:
            for mesh in {ob.data for ob in members if ob.type == 'MESH'}:
                baseline = mesh.attributes.get('legacy_import_normal')
                if baseline is not None:
                    # Joining proxies and welding editable vertices re-encode
                    # custom normals. This is the final import baseline; the
                    # authored source normals remain in their separate layer.
                    baseline.data.foreach_set('vector', [c for normal in mesh.corner_normals for c in normal.vector])
            collection['ass_source_fingerprints'] = json.dumps({ob['ass_object_key']:fingerprint(ob,collections=states) for ob in members})
            collection['ass_source_settings'] = json.dumps(dict(scale=scene.scale, forward_direction=scene.forward_direction))


def finalize_import(objects, scene):
    """Capture the completed import after material lookup and editable cleanup."""
    import bpy
    keys = {ob.get('ass_source_key') for ob in objects}
    collections = [c for c in bpy.data.collections
                   if c.get('ass_source_key') in keys and c.get('ass_source_pending')]
    capture_collections(collections, bpy.data.objects, scene)
    for collection in collections:
        collection['ass_source_pending'] = False


def unchanged_collections(collections, objects, scene, game):
    objects = list(objects)
    states = collection_states()
    result = {}
    for collection in collections:
        if not collection.get('ass_source_scene') or not collection.get('ass_source_fingerprints'):
            continue
        if collection.get('ass_source_game') != game:
            continue
        key = collection['ass_source_key']
        settings = json.loads(collection['ass_source_settings'])
        if settings != dict(scale=scene.scale, forward_direction=scene.forward_direction):
            continue
        expected = json.loads(collection['ass_source_fingerprints'])
        members = [ob for ob in objects if ob.get('ass_source_key') == key and ob.get('ass_object_key')]
        current = {ob['ass_object_key']:ob for ob in members}
        if (len(members) == len(expected) and current.keys() == expected.keys()
                and all(digest is not None and fingerprint(current[name],collections=states) == digest for name,digest in expected.items())):
            result[key] = collection['ass_source_scene']
    return result
