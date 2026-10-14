# Import Tool patches

Foundry applies these patches to the suspended import process. It does not
rewrite the installed executable. The selected PE build and the original
instruction bytes must match `tool_patch_data.py`; an unknown build or a
changed patch site stops the patched launch with an explanation. Disabling
**Allow Tool Patches** runs the executable without applying these patches.

## Coverage

| Kit | Skip vertex compression | Uncompressed vertex weights | Skip import source data | Plane assertions | Ignore node depth sort |
| --- | --- | --- | --- | --- | --- |
| H1 | Not verified | Not verified | Not verified | Not ported | Not ported |
| H2 | Both tools | Both tools | Both tools | Standard tool; absent in fast | Not ported |
| H3 | Both tools | Both tools | Both tools | Both tools | Not ported |
| ODST | Both tools | Both tools | Both tools | Both tools | Not ported |
| Reach | Both tools | Both tools | Both tools | Both tools | Both tools |
| H4 | Both tools | Not ported | Both tools | Both tools | Not ported |
| H2AMP | Both tools | Not ported | Both tools | Both tools | Not ported |

"Both tools" means `tool.exe` and `tool_fast.exe`. Legacy structure export
continues to select standard Tool. Other imports use Foundry's selected tool.
H2's 32-bit processes use the WOW64 PEB when launched by 64-bit Blender.

H1 has a different geometry pipeline and no `tool_fast.exe` in the inspected
HCEEK installation. Its compressed model/BSP vertex formats are not the
connected-geometry welding pass used by the later games. No equivalent H1
patch has been verified, so H1 receives no import patches. Its
`bsp3d_plane_test_point` assertions are also left intact.

The Frame ID node comparator patch remains Reach-specific. The JMS/ASS
importers use a different node ordering scheme, and Foundry's legacy writer
already matches that scheme. Reach's lightmap-color and wetness patches are
separate from this import patch table and have not been ported.

## Behavior

- **Skip Vertex Compression** skips the connected-geometry vertex welding
  loop and duplicate/degenerate triangle compression loop. It follows each
  loop's existing empty-input exit, retaining required cleanup. It does not
  change the game's final GPU vertex format or disable every geometry pass.
- **Uncompressed Vertex Weights** skips the connected-point weight
  quantization pass. Final tag/runtime vertex formats may still constrain
  stored precision.
  Without this patch (including when **Allow Tool Patches** is disabled),
  render export rounds H2/H3/ODST/Reach weights to Tool's tenths before building
  the bone palette. This prevents tiny influences disappearing only after
  Tool has classified a mesh as skinned. Both preference switches must be
  enabled to preserve those influences. H1 uses a different importer;
  H4/H2AMP already have uncompressed Tool weights and skip this extra rounding.
  Source Blender vertex groups are not changed.
- **Skip Import Source Data** omits the zipped source payload while retaining
  import-file metadata. H2/H3/ODST still read the source to calculate its CRC
  and size; the patch skips ZIP allocation, compression, and resizing. Their
  import helper combines metadata and compression, so skipping the entire
  helper would be incorrect.
- **Plane assertions** are enabled for scenario/prefab imports by the master
  patch switch. They bypass the three original-plane/triangle-point checks.
  H3 onward also bypass the BSP `test_plane`/`new_point` check and the
  `plane->plane`/`triangle_points[vertex_num]` check, all expressed as
  `plane3d_passes_through_point`. The corresponding H2 fast assertions are
  compiled out. The existing additional Reach fast plane-builder bypasses
  are retained.
- **Ignore Node Depth Sort** makes Reach's render and animation comparators
  continue to Frame ID comparison instead of returning the depth comparison.

## Verified builds

Profile identity is `(Machine, TimeDateStamp, SizeOfImage)` from the PE
header. The timestamp and image size below are hexadecimal, not file dates.
H2 uses machine `014C`; all other supported builds use `8664`.

| Kit | Executable | Timestamp | Image size |
| --- | --- | --- | --- |
| H2 | tool | 6491EFB1 | 1B4F000 |
| H2 | tool_fast | 6491F037 | 13A9000 |
| H3 | tool | 6595A3A1 | 19B31000 |
| H3 | tool_fast | 6595A253 | 199BE000 |
| ODST | tool | 64F22702 | 1940D000 |
| ODST | tool_fast | 64F227DE | 19290000 |
| Reach | tool | 64B47BC1 | 1B9F0000 |
| Reach | tool_fast | 64B47C63 | 1ABC7000 |
| H4 | tool | 649B075D | 6E66000 |
| H4 | tool_fast | 649B0A11 | 6644000 |
| H2AMP | tool | 6595A91D | 55FB000 |
| H2AMP | tool_fast | 6595A9F4 | 4D98000 |

An existing H2 standard-tool jump at file offset `0x7B63C` is accepted as an
alternative original instruction. It has the same destination as the new
patch and is normalized only in memory. Other unexpected modifications are
rejected. Patch records avoid relocated absolute addresses on x86.

## Validation

Validated against the installed MCC kits on 2026-10-11:

- All 12 supported executables were launched suspended, patched, and read
  back to check every replacement. Reapplication was harmless and executable
  SHA-256 hashes remained unchanged.
- H2, H3, and ODST each compiled a two-bone JMS model successfully with both
  tool variants, with patches disabled and with all applicable patches
  enabled. H3/ODST used `bulk-import-model-folder-draft`; H2 used
  `bulk-import-model-folder`.
- Baseline render models contained zipped JMS source data. Patched render
  models omitted that data and retained `default.jms` metadata.
- Unit tests cover build selection, changed instruction rejection, disabled
  options, already-patched files, the existing H2 jump, actual executable
  routing, Corinth plane-patch selection, and WOW64 image-base lookup.

The model smoke tests do not reproduce a failing BSP plane assertion or
establish in-game rendering correctness. H4/H2AMP patches have instruction,
control-flow, and suspended-process verification; an end-to-end import with
those kits has not been run as part of this change.

Run the regression tests without Blender:

```text
python -m unittest discover -s blender/tests -p test_tool_patches.py -v
```

When adding a build, locate each routine using diagnostic strings and call
references, check its entry/exit control flow, and record original instruction
context. Do not transplant another kit's offsets or bypass an entire helper
that also owns cleanup or metadata work.
