"""Match the connected-geometry importer's weight quantization before export."""
import numpy as np


COMPRESSED_WEIGHT_GAMES = frozenset({'halo2', 'halo3', 'halo3odst', 'reach'})


def uses_compressed_weights(game, *, allow_tool_patches=False,
                            uncompressed_vertex_weights=False):
    # H1 has a different importer. H4/H2AMP already retain uncompressed weights.
    return (game in COMPRESSED_WEIGHT_GAMES
            and not (allow_tool_patches and uncompressed_vertex_weights))


def quantize_weights(weights, indices, *, steps=10):
    """Return rounded weights and matching indices, in Tool's influence order.

    Tool floors each float32 weight times ten, then distributes the rounded
    sum of the fractional remainders, largest first. Ties use the lower node
    index. It finally sorts by descending weight, then ascending node index.
    Inputs are normalized rows with at most four influences; zero padding is
    harmless because it cannot win a positive fractional remainder.
    """
    scaled = np.asarray(weights, dtype=np.float32) * np.float32(steps)
    integral = np.floor(scaled).astype(np.int32)
    fractions = scaled - integral
    # Accumulate in influence order, as Tool does with scalar float32 additions.
    remaining = np.floor(np.add.accumulate(fractions, axis=-1)[..., -1]
                         + np.float32(0.5)).astype(np.int32)
    order = np.lexsort((indices, -fractions), axis=-1)
    rank = np.argsort(order, axis=-1)
    integral += rank < remaining[..., None]
    order = np.lexsort((indices, -integral), axis=-1)
    rounded = np.take_along_axis(integral, order, axis=-1).astype(np.float32)
    return rounded / np.float32(steps), np.take_along_axis(indices, order, axis=-1)
