# Import materials for the current project

Enable **Build Materials for Current Project** beneath **Generate Materials**
in the import options. It is available for file imports, drag-and-drop imports,
and the shader import dialog. It defaults to off, preserving source-game imports.
Disabling Generate Materials also disables this option.

Tags and bitmaps are still read using the source editing kit. After reading,
Foundry replaces the surface nodes with the closest available nodes for the
scene's project. Texture nodes and UV mappings are reused where native shader
options match. Generated texture calculations are baked before shader export;
the material does not depend on the exporter evaluating Blender math nodes.
Conversion does not switch the scene project or modify source tags/bitmaps.

## Game and family mapping

| Source / destination | Mapping |
| --- | --- |
| Same game | No conversion. |
| H3 ↔ ODST; H4 ↔ H2AMP | Shared node libraries; retain the graph. Detach foreign tag paths when importing for the current project. |
| H3/ODST ↔ Reach | Match shader, custom, decal, halogram and terrain families. Copy matching menus, parameter values and upstream links. Preserve repeated socket names by occurrence. |
| Reach glass → H3/ODST | Default shader with alpha blending and two-lobe Phong. |
| Reach foliage → H3/ODST | Default shader with foliage lighting and alpha testing. |
| H1 model/environment → H3/ODST/Reach | Default shader; explicitly unpack classic masks and translate details, illumination, reflections and alpha flags. |
| H1 transparent shader previews → later games | Translate the source reader's Principled preview, including composited base color, alpha, emission and an immediately connected normal-map node. |
| H3/ODST/Reach → H4/H2AMP | Blinn, Blinn detail, or character Blinn reflection/self-illumination according to material features. Glass → glass; foliage → foliage; halogram → constant; terrain → layered-three. Use clip variants for alpha-tested Blinn, foliage and constant surfaces where available. |
| H4/H2AMP → earlier games | Common color/detail/normal/reflection/illumination inputs and supported packed control maps translate through Reach's parameter model. Three-layer terrain retains its color/normal layers. H2AMP PBR terrain reverses layer numbering (2, 1, 0 → 0, 1, 2). |
| Later games → H1 | Environment for opaque normal-mapped surfaces/terrain; model otherwise. Terrain uses a three-layer color blend and the first normal layer. |
| H2 → supported destination | Approximation from the existing H2 Principled preview. No new H2 template decoder. |
| Any game → H2 | Unsupported: retain source nodes and report it. H2 has no custom surface library. |

Specialized effects do not have exact cross-game equivalents. Library/menu
differences produce warnings; unsupported target menus retain their resource
defaults. Conversion notes are also stored on the material as
`foundry_material_conversion_notes`.

## H1 multipurpose bitmaps

The layouts follow the shipped H1 model node's channel-order switch:

| Meaning | PC layout | Original Xbox layout | Modern destination |
| --- | --- | --- | --- |
| Auxiliary/detail mask | R | A | Used by the classic detail-mask calculation. |
| Self illumination | G | G | Separate self-illumination mask. |
| Reflection/specular mask | B | R | Separate specular-mask texture, including its alpha channel. |
| Change color | A | B | Red of a modern change-color texture; other change-color channels are zero. |

H1 model change color uses the destination's two-change-color option with only
the primary channel enabled. Base alpha supplies alpha testing. Detail masks
support their inverse variants. Unmasked double-multiply detail plugs directly
into the native detail input. Masked/multiply detail is baked to a derived detail
TIFF; biased-add detail is baked into base color, retaining base alpha. This
avoids applying detail both inside the base image and in the detail input.
Environment primary/secondary detail blending uses base alpha as an
approximation; micro detail is applied afterwards. Environment RGB illumination
channels retain their individual static activation colors. As in the existing
H1 reader, classic animation functions are represented by their imported static
bounds/activation values.

## Automatic packed-image conversion

Conversion writes derived TIFFs under the current project's data directory,
mirroring the source bitmap's original tagset directory. For example,
`objects/weapons/rifle/bitmaps/rifle_multi.bitmap` produces TIFFs alongside
`objects/weapons/rifle/bitmaps/rifle_multi_<conversion>_<digest>.tif`. The normal
bitmap exporter uses the same relative paths under the current project's tags
directory. Intermediate bakes retain the original source path. Inputs with no
source bitmap path are written directly under the data root.

Names include the source bitmap stem, conversion name, and a digest of dimensions
and pixel content so separate derived maps do not overwrite each other. Source image pixels and
files are not modified. Masks use Non-Color data and independent packed alpha.
Color blends are computed in linear RGB and saved as sRGB; ACEScg and other
configured source spaces use Blender's OCIO transform. Image saving bypasses
the scene view transform. Texture sampling and the reference vector connection
are retained. Images receive Foundry bitmap
metadata and can be built into `.bitmap` tags by the normal bitmap/material
export workflow; importing does not launch the destination editing kit's tool.

Supported image operations include channel extraction/packing, mask arithmetic,
color mixing, multiplication and biased addition. These cover:

- H1 PC/Xbox multipurpose → separate modern masks.
- Modern masks → H1 multipurpose (auxiliary = 1, illumination = G,
  specular/reflection = B, primary change mask = A).
- H4 `control_map_spglsi`: R specular, G gloss, B illumination.
- H4 `control_map_spglrf`: R specular, G gloss, B reflection.
- H4 `control_map_spglrfsi`: R specular, G gloss, B reflection, A illumination.
- Modern → H4 character RGBA control packing. Gloss is approximated by
  `1 - roughness`; self illumination is reduced to a scalar mask.

Ordinary 2D images with different resolutions and static UV scale/offset can be
resampled into the reference texture's coordinates. Resolution increases to
retain detail density, up to 4096 per axis for combined bakes; a warning records
any limit or color clipping. Single-image mask extraction retains its original
resolution. Derived TIFFs are 8-bit, matching typical extracted packed masks.

Derived TIFFs use uncompressed RGBA storage. Blender's default TIFF save uses
Adobe Deflate, which Reach Tool rejects while still returning success and
producing a 1x1 bitmap. Converted images are file-backed so the saved pixels
survive reopening the blend. Export disables size optimization for these maps
and verifies the compiled dimensions. The next shader build repairs older
converted TIFFs and recompiles their existing bitmap tags automatically.

Cubemaps keep an equirectangular image for Blender preview, with the original
cube-layout TIFF recorded separately. Shader export, individual bitmap export,
and Shader Farm resolve that original image and losslessly rearrange its six
faces into a separate `_cube.tif` in the current project's bitmap folder.
Reach Tool's cube slicer reads the middle row, then the top-left and bottom-left
cells; the extracted DirectX cross has a different arrangement. No pixels are
resampled through the equirectangular preview. The result is compiled with
cube-map usage and slicing. Legacy images
without that metadata resolve the corresponding non-equirectangular TIFF by
filename. A missing original reports an error requesting reimport rather than
writing the preview into a game bitmap.

Different UV sets, generated-coordinate compositions, animated/tiled images,
rotated/procedural transforms and unsupported pixel operations are not silently
flattened. If a required bake fails, conversion retains the source material,
records `foundry_material_conversion_error`, and shader building reports the
incomplete conversion instead of writing a misleading target shader.

## Approximation and export boundaries

This is a material-node conversion, not a lossless tag porter. BRDFs, reflection
brightness, gloss response, transparency and emission can differ between games.
H4's three-layer terrain loses an active fourth Reach layer. H1 cannot represent
modern multi-color masks, multilayer lighting, all normal/alpha combinations or
many specialized effects. Colored emission reduced to packed masks uses its red
channel. H4 shader-specific effects outside the common parameter/control-map
mapping remain approximate.

Converted bitmap parameters use direct image-to-group connections. RGB and alpha
belonging to one tag bitmap parameter use the same image. Unused source images
and helper nodes are removed from the material graph. Constant color/float
calculations become actual socket defaults, which are what the exporter reads.
When a texture drives a parameter the destination only supports as a constant,
its average is used and recorded as an approximation. Primary change-color
attributes remain connected to their native change-color inputs.

Successful cross-game imports retain the original tag path in
`foundry_material_source_shader`, clear the active foreign shader/material path,
and enable Blender-node export. No destination shader or bitmap tags are written
during import. Failed graph conversions preserve the original surface graph and
report the failure.

## Validation

Run `test_material_game_mapping.py` with Blender in background factory-startup
mode. It loads the shipped node libraries and checks game/family routing,
PC/Xbox mask pixels after TIFF save/reload, H4 control packing/unpacking, retained
UV links, duplicate parameter names, material copying, unsupported destinations,
and failure rollback. A masked-detail regression uses ACEScg textures with
different tiling, verifies saved color/alpha, and exercises the actual Reach
exporter's parameter discovery and tiling reader. The tests require no editing kit and do not verify
in-engine rendering or shader-tag compilation.

`test_bitmap_export.py` tests uncompressed TIFF storage, row/alpha preservation,
file-backed conversions, cubemap source selection and missing-source errors.
Append `-- --kit <Reach editing kit directory>` to its Blender invocation to
also run the real bitmap compiler in a temporary project. Those tests verify
decoded color/alpha and dimensions, all six compiled cubemap faces, and replacement of existing
bitmap references. They copy Tool and its dependencies and never modify the
supplied editing kit. In-engine shader appearance remains unverified.
