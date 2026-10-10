"""Face property tables backed by one integer assignment channel per type.

Zero means inherit; positive IDs identify records, never collection positions.
Legacy masks are read without mutation. Conversion is requested explicitly by
the operator, export preparation, or joining geometry. No load handlers.
"""

from uuid import uuid4

import bmesh
import bpy
import numpy as np

VERSION = 2
PREFIX = 'foundry_face_'
STORAGE_FIELDS = {'rna_type', 'name', 'attribute_name', 'assignment_id', 'face_count', 'color'}


def assignment_id(prop):
    return getattr(prop, 'assignment_id', 0)


def has_legacy(mesh):
    return any(not assignment_id(p) for p in mesh.nwo.face_props)


def read_attribute(attribute, count):
    if attribute.domain != 'FACE' or attribute.data_type not in {'BOOLEAN', 'INT', 'INT8', 'FLOAT'}:
        raise ValueError(f'{attribute.name}: expected a scalar face attribute')
    if len(attribute.data) != count:
        raise ValueError(f'{attribute.name}: face count does not match the mesh')
    dtype = np.float32 if attribute.data_type == 'FLOAT' else np.int32
    values = np.empty(count, dtype=dtype)
    attribute.data.foreach_get('value', values)
    return values


def mask(mesh, prop, *, strict=False):
    """Read either representation, including evaluated meshes, without writes."""
    attribute = mesh.attributes.get(prop.attribute_name)
    if attribute is None:
        if strict or assignment_id(prop):
            raise ValueError(f'{prop.name}: missing face attribute {prop.attribute_name!r}')
        return np.zeros(len(mesh.polygons), dtype=bool)
    if assignment_id(prop) and attribute.data_type != 'INT':
        raise ValueError(f'{prop.name}: assignment channel must be an integer face attribute')
    values = read_attribute(attribute, len(mesh.polygons))
    return values == assignment_id(prop) if assignment_id(prop) else values != 0


def matches(mesh, prop, index):
    attribute = mesh.attributes.get(prop.attribute_name)
    if attribute is None:
        return False
    value = attribute.data[index].value
    return value == assignment_id(prop) if assignment_id(prop) else bool(value)


def bm_layer(bm, prop):
    groups = (bm.faces.layers.int,) if assignment_id(prop) else (
        bm.faces.layers.bool, bm.faces.layers.int, bm.faces.layers.float)
    for group in groups:
        layer = group.get(prop.attribute_name)
        if layer is not None:
            return layer
    return None


def bm_matches(face, prop, layer):
    if layer is None:
        return False
    value = face[layer]
    return value == assignment_id(prop) if assignment_id(prop) else bool(value)


def count(mesh, prop):
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        layer = bm_layer(bm, prop)
        return sum(bm_matches(f, prop, layer) for f in bm.faces)
    return int(np.count_nonzero(mask(mesh, prop)))


def refresh_counts(mesh, channel=None):
    if mesh.is_editmode:
        for prop in mesh.nwo.face_props:
            if channel is None or prop.attribute_name == channel:
                prop.face_count = count(mesh, prop)
        return
    channels = {}
    for prop in mesh.nwo.face_props:
        if channel is not None and prop.attribute_name != channel:
            continue
        if not assignment_id(prop):
            prop.face_count = count(mesh, prop)
            continue
        if prop.attribute_name not in channels:
            attribute = mesh.attributes.get(prop.attribute_name)
            if attribute is None:
                raise ValueError(f'Missing assignment channel {prop.attribute_name!r}')
            ids, counts = np.unique(read_attribute(attribute, len(mesh.polygons)), return_counts=True)
            channels[prop.attribute_name] = dict(zip(ids, counts))
        prop.face_count = int(channels[prop.attribute_name].get(assignment_id(prop), 0))


def _next_id(mesh):
    value = max(getattr(mesh.nwo, 'face_attribute_next_id', 1),
                max((assignment_id(p) for p in mesh.nwo.face_props), default=0) + 1)
    if value >= 2**31 - 1:
        raise ValueError('Face assignment IDs exhausted')
    mesh.nwo.face_attribute_next_id = value + 1
    mesh.nwo.face_attribute_version = VERSION
    return value


def _channel(mesh, prop):
    existing = next((p for p in mesh.nwo.face_props
                     if p.type == prop.type and assignment_id(p) and p != prop), None)
    if existing is not None:
        return existing.attribute_name
    name = PREFIX + prop.type
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        # BMesh's layer API may return an existing layer: never adopt user data.
        names = {n for group in (bm.faces.layers.int, bm.faces.layers.bool,
                                bm.faces.layers.float, bm.faces.layers.float_vector)
                 for n in group.keys()}
        while name in names:
            name = PREFIX + prop.type + '_' + uuid4().hex[:8]
        layer = bm.faces.layers.int.new(name)
        bmesh.update_edit_mesh(mesh)
        return layer.name
    return mesh.attributes.new(name, 'INT', 'FACE').name


def add(mesh, prop_type, values=None, *, legacy=None):
    """New meshes use IDs. Existing legacy meshes wait for explicit conversion."""
    if legacy is None:
        legacy = isinstance(mesh, bpy.types.Mesh) and has_legacy(mesh)
    if isinstance(mesh, bpy.types.Mesh):
        size = len(bmesh.from_edit_mesh(mesh).faces) if mesh.is_editmode else len(mesh.polygons)
        selection = np.ones(size, dtype=bool) if values is None else np.asarray(values, dtype=bool)
        if selection.shape != (size,):
            raise ValueError('Face selection must contain one value per face')
    prop = mesh.nwo.face_props.add()
    prop.type = prop_type
    if not isinstance(mesh, bpy.types.Mesh):
        return prop
    if legacy:
        name = 'foundry_attribute__' + uuid4().hex[:8]
        if mesh.is_editmode:
            bm = bmesh.from_edit_mesh(mesh)
            prop.attribute_name = bm.faces.layers.bool.new(name).name
        else:
            prop.attribute_name = mesh.attributes.new(name, 'BOOLEAN', 'FACE').name
    else:
        prop.attribute_name = _channel(mesh, prop)
        prop.assignment_id = _next_id(mesh)
    set_mask(mesh, prop, selection)
    return prop


def set_mask(mesh, prop, selection):
    """Replace one record's membership, preserving other IDs in its channel."""
    selection = np.asarray(selection, dtype=bool)
    value = assignment_id(prop) or 1
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        if selection.shape != (len(bm.faces),):
            raise ValueError('Face selection must contain one value per face')
        layer = bm_layer(bm, prop)
        if layer is None:
            raise ValueError(f'Missing face attribute {prop.attribute_name!r}')
        for face, selected in zip(bm.faces, selection):
            if selected:
                face[layer] = value
            elif bm_matches(face, prop, layer):
                face[layer] = 0
        bmesh.update_edit_mesh(mesh)
    else:
        if selection.shape != (len(mesh.polygons),):
            raise ValueError('Face selection must contain one value per face')
        attribute = mesh.attributes.get(prop.attribute_name)
        if attribute is None:
            raise ValueError(f'Missing face attribute {prop.attribute_name!r}')
        values = read_attribute(attribute, len(mesh.polygons))
        values[values == value if assignment_id(prop) else values != 0] = 0
        values[selection] = value
        attribute.data.foreach_set('value', values)
        mesh.update()
    refresh_counts(mesh, prop.attribute_name)


def assign_selected(mesh, prop, *, remove=False, all_faces=False):
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        layer = bm_layer(bm, prop)
        current = np.array([bm_matches(f, prop, layer) for f in bm.faces])
        selected = np.array([all_faces or f.select for f in bm.faces])
    else:
        current = mask(mesh, prop)
        selected = np.ones(len(mesh.polygons), dtype=bool)
    set_mask(mesh, prop, current & ~selected if remove else current | selected)


def select(mesh, prop, selected=True):
    bm = bmesh.from_edit_mesh(mesh)
    layer = bm_layer(bm, prop)
    for face in bm.faces:
        if not face.hide and bm_matches(face, prop, layer):
            face.select_set(selected)
    bm.select_flush_mode()
    bmesh.update_edit_mesh(mesh)


def delete(mesh, index, *, remove_record=True):
    prop = mesh.nwo.face_props[index]
    name = prop.attribute_name
    owned = bool(assignment_id(prop))
    if owned:
        size = len(bmesh.from_edit_mesh(mesh).faces) if mesh.is_editmode else len(mesh.polygons)
        set_mask(mesh, prop, np.zeros(size, dtype=bool))
    if remove_record:
        mesh.nwo.face_props.remove(index)
    # Legacy/external attributes may have other consumers; never delete them.
    if owned and not any(p.attribute_name == name for p in mesh.nwo.face_props):
        if mesh.is_editmode:
            bm = bmesh.from_edit_mesh(mesh)
            layer = bm.faces.layers.int.get(name)
            if layer is not None:
                bm.faces.layers.int.remove(layer)
            bmesh.update_edit_mesh(mesh)
        else:
            attribute = mesh.attributes.get(name)
            if attribute is not None:
                mesh.attributes.remove(attribute)
    mesh.nwo.face_props_active_index = max(0, min(mesh.nwo.face_props_active_index,
                                               len(mesh.nwo.face_props) - 1))


def resolved_masks(mesh, *, strict=False):
    """Legacy export order: last row wins, except explicit opaque wins."""
    props = list(mesh.nwo.face_props)
    masks = [mask(mesh, p, strict=strict) for p in props]
    order = [i for i, p in enumerate(props) if p.type != 'transparent' or p.transparent]
    order += [i for i, p in enumerate(props) if p.type == 'transparent' and not p.transparent]
    taken = {}
    for i in reversed(order):
        used = taken.setdefault(props[i].type, np.zeros(len(mesh.polygons), dtype=bool))
        masks[i] &= ~used
        used |= masks[i]
    return masks


def conversion_plan(mesh):
    if mesh.is_editmode:
        raise ValueError('Leave Edit Mode before converting face attributes')
    if not has_legacy(mesh):
        return None
    props = list(mesh.nwo.face_props)
    masks = resolved_masks(mesh, strict=True)
    next_id = max(getattr(mesh.nwo, 'face_attribute_next_id', 1),
                  max((assignment_id(p) for p in props), default=0) + 1)
    ids = [assignment_id(p) or next_id + i for i, p in enumerate(props)]
    if ids and max(ids) >= 2**31 - 1:
        raise ValueError('Face assignment IDs exhausted')
    channels = {}
    for p, selection, ident in zip(props, masks, ids):
        values = channels.setdefault(p.type, np.zeros(len(mesh.polygons), dtype=np.int32))
        values[selection] = ident
    return ids, channels


def convert(mesh, *, remove_legacy_masks=False, plan=None):
    """Idempotent migration. Validate before changing any records."""
    plan = conversion_plan(mesh) if plan is None else plan
    if plan is None:
        return 0
    ids, channels = plan
    old_names = {p.attribute_name for p in mesh.nwo.face_props}
    created = {}
    try:
        for kind, values in channels.items():
            attribute = mesh.attributes.new(PREFIX + kind, 'INT', 'FACE')
            created[kind] = attribute.name
            attribute.data.foreach_set('value', values)
    except Exception:
        for name in created.values():
            mesh.attributes.remove(mesh.attributes[name])
        raise
    for prop, ident in zip(mesh.nwo.face_props, ids):
        prop.assignment_id = ident
        prop.attribute_name = created[prop.type]
    mesh.nwo.face_attribute_version = VERSION
    mesh.nwo.face_attribute_next_id = max(ids, default=0) + 1
    if remove_legacy_masks:
        for name in old_names:
            # External attributes are always preserved, even with cleanup opted in.
            if name.startswith('foundry_attribute__'):
                attribute = mesh.attributes.get(name)
                if attribute is not None:
                    mesh.attributes.remove(attribute)
    refresh_counts(mesh)
    mesh.update()
    return len(ids)


def copy(mesh, prop, target):
    if mesh == target:
        return None
    if isinstance(mesh, bpy.types.Mesh) and isinstance(target, bpy.types.Mesh):
        source = mask(mesh, prop)
        selection = np.ones(len(target.polygons), dtype=bool) if source.size and source.all() else np.zeros(len(target.polygons), dtype=bool)
        if not source.size or not source.all():
            size = min(len(source), len(selection))
            selection[:size] = source[:size]
        result = add(target, prop.type, selection)
    else:
        result = add(target, prop.type)
    for key, value in prop.items():
        if key not in STORAGE_FIELDS:
            result[key] = value
    result.color = prop.color
    return result


def signature(prop):
    """Compare stored settings, not rounded display names or row identities."""
    return tuple((field.identifier, tuple(getattr(prop, field.identifier))
                  if getattr(field, 'is_array', False) else getattr(prop, field.identifier))
                 for field in prop.bl_rna.properties
                 if field.identifier not in STORAGE_FIELDS
                 and field.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'})


def consolidate(mesh):
    if has_legacy(mesh):
        raise ValueError('Convert Legacy Face Attributes before merging')
    if mesh.is_editmode:
        raise ValueError('Leave Edit Mode before merging face attributes')
    primary = {}
    removals = []
    for index, prop in enumerate(mesh.nwo.face_props):
        key = signature(prop)
        if key in primary:
            target = mesh.nwo.face_props[primary[key]]
            set_mask(mesh, target, mask(mesh, target) | mask(mesh, prop))
            removals.append(index)
        else:
            primary[key] = index
    for index in reversed(removals):
        delete(mesh, index)
    refresh_counts(mesh)


def prepare_join(meshes):
    """Remap tables before Blender/BMesh joins the channels by name.

    Callers must provide writable mesh copies when data has unselected users.
    All input records are installed on the first mesh; source channels use the
    same names and globally unique IDs, including diverged mesh duplicates.
    """
    meshes = list(dict.fromkeys(meshes))
    if not meshes or not any(m.nwo.face_props for m in meshes):
        return
    # Detach nested groups and arrays before clearing their owning collections.
    # A shallow dict retains IDPropertyArray wrappers backed by freed memory.
    snapshots = [(m, [p.id_properties_ensure().to_dict() for p in m.nwo.face_props],
                  [(p.type, tuple(p.color)) for p in m.nwo.face_props],
                  resolved_masks(m, strict=True)) for m in meshes]
    kinds = {kind for _, _, records, _ in snapshots for kind, _ in records}
    token = uuid4().hex[:8]
    names = {kind: PREFIX + kind + '_' + token for kind in kinds}
    records = []
    source_records = {}
    ident = 1
    for mesh, properties, metadata, masks in snapshots:
        local_records = []
        local_kinds = kinds if mesh == meshes[0] else {kind for kind, _ in metadata}
        channels = {kind: np.zeros(len(mesh.polygons), dtype=np.int32) for kind in local_kinds}
        for settings, (kind, color), selection in zip(properties, metadata, masks):
            settings.update(attribute_name=names[kind], assignment_id=ident, face_count=int(selection.sum()), color=color)
            records.append(settings)
            local_records.append(settings)
            channels[kind][selection] = ident
            ident += 1
        source_records[mesh] = local_records
        old_owned = {p.attribute_name for p in mesh.nwo.face_props if assignment_id(p)}
        for kind, values in channels.items():
            attribute = mesh.attributes.new(names[kind], 'INT', 'FACE')
            if attribute.name != names[kind]:
                raise ValueError('Conflicting join assignment channel')
            attribute.data.foreach_set('value', values)
        for name in old_owned:
            attribute = mesh.attributes.get(name)
            if attribute is not None:
                mesh.attributes.remove(attribute)
        mesh.nwo.face_props.clear()
    for mesh in meshes:
        # Keep source tables valid too until their geometry has been joined.
        for settings in records if mesh == meshes[0] else source_records[mesh]:
            prop = mesh.nwo.face_props.add()
            for key, value in settings.items():
                prop[key] = value
        mesh.nwo.face_attribute_version = VERSION
        mesh.nwo.face_attribute_next_id = ident
        refresh_counts(mesh)
