"""Store optional texture W coordinates in editable Blender UV maps.

A companion named ``W:<base UV map>`` stores W in U and zero in V. It is
created only for nonzero W, and is not an additional texture coordinate set.
"""
import numpy as np


W_PREFIX = 'W:'


def store_uv_w(mesh, layer, values):
    values = np.asarray(values, dtype=np.float32)
    if not np.any(values):
        return
    coordinates = np.zeros((len(mesh.loops), 2), dtype=np.float32)
    coordinates[:, 0] = values
    name = W_PREFIX + layer.name
    companion = mesh.uv_layers.new(name=name, do_init=False)
    if companion is None:
        raise ValueError(f'{mesh.name}: no UV map slot available for {layer.name} W coordinates')
    if companion.name != name:
        raise ValueError(f'{mesh.name}: rename {layer.name} so its W companion has a unique, untruncated name')
    companion.uv.foreach_set('vector', coordinates.ravel())


def texture_uv_layers(mesh):
    """Yield base UV maps and their optional W companions in Blender order."""
    for layer in mesh.uv_layers:
        if layer.name.startswith(W_PREFIX):
            continue
        yield layer, mesh.uv_layers.get(W_PREFIX + layer.name)
