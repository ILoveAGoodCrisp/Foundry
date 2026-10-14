"""Export editable frame hierarchies without flattening small local offsets."""
from mathutils import Matrix, Quaternion
from struct import pack, unpack

from . import ass_format as ass
from .coordinates import axis_rotation


def local_transform(ob):
    """Return representable local TRS, falling back for constrained/sheared data."""
    if ob.parent_type != 'OBJECT' or ob.constraints:
        return None
    if ob.matrix_parent_inverse != Matrix.Identity(4):
        return None
    if any(ob.delta_location) or any(ob.delta_rotation_euler) or tuple(ob.delta_scale) != (1, 1, 1):
        return None
    if ob.rotation_mode == 'QUATERNION':
        if tuple(ob.delta_rotation_quaternion) != (1, 0, 0, 0):
            return None
        rotation = ob.rotation_quaternion
    elif ob.rotation_mode == 'AXIS_ANGLE':
        angle, x, y, z = ob.rotation_axis_angle
        rotation = Quaternion((x, y, z), angle)
    else:
        rotation = ob.rotation_euler.to_quaternion()
    scale = tuple(ob.scale)
    if not scale[0] or any(s != scale[0] for s in scale):
        return None
    return ass.Transform((rotation.x, rotation.y, rotation.z, rotation.w), tuple(ob.location), scale)


class AssHierarchy:
    def __init__(self, asset, depsgraph, unit_scale, rotation):
        self.asset, self.depsgraph = asset, depsgraph
        self.unit_scale, self.rotation = unit_scale, rotation
        self.frames = {}

    def placement(self, node):
        wrapped = node.ob
        ob = getattr(wrapped, 'ob', None)
        if ob is None or wrapped.transform is not None or not ob.parent:
            return None
        chain = []
        parent = ob.parent
        while parent is not None:
            if parent.type != 'EMPTY' or not parent.nwo.is_frame:
                return None
            value = local_transform(parent.evaluated_get(self.depsgraph))
            if value is None:
                return None
            chain.append((parent, value))
            parent = parent.parent
        value = local_transform(ob.evaluated_get(self.depsgraph))
        if value is None:
            return None
        # Convert units before Tool builds world matrices. Baking a large root
        # scale afterwards changes its float32 plane and instance calculations.
        root = chain[-1][1]
        units = unpack('f', pack('f', self.unit_scale * abs(root.scale[0])))[0]
        root.scale = (1 if root.scale[0] > 0 else -1,) * 3
        for frame, local in chain:
            local.translation = tuple(c * (self.unit_scale if frame.parent is None else units)
                                      for c in local.translation)
        value.translation = tuple(c * units for c in value.translation)
        # A mesh's editable parent supplies its placement and the mesh's own
        # local transform supplies its pivot. Keep these operations separate.
        placement_local = value
        pivot = ass.Transform()
        if len(chain) > 1:
            _, placement_local = chain.pop(0)
            pivot = value
        parent_index = 0
        for frame, local in reversed(chain):
            if frame not in self.frames:
                if frame.parent is None:
                    if self.rotation:
                        r = axis_rotation(self.rotation).to_quaternion() @ Quaternion((local.rotation[3], *local.rotation[:3]))
                        r.normalize()
                        local.rotation = (r.x, r.y, r.z, r.w)
                        rows = axis_rotation(self.rotation).to_3x3()
                        local.translation = tuple(sum(row[c] * local.translation[c] for c in range(3))
                                                  for row in rows)
                index = len(self.asset.instances)
                self.asset.instances.append(ass.Instance(-1, 'frame ' + frame.name, index,
                                                        parent_index, 0, local, ass.Transform()))
                self.frames[frame] = index
            parent_index = self.frames[frame]
        return parent_index, placement_local, pivot, units
