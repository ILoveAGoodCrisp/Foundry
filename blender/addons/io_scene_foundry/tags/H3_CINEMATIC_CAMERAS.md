# Halo 3 and ODST cinematic camera conversion

Halo 3 camera export must preserve the camera's projection and its position
relative to both animated actors and level geometry. The camera frame is in
cinematic shot space; the scenario cutscene flag places that space in the level.
Foundry's Blender anchor moves the level into shot space, so its inverse is the
placement written to the scenario.

## Confirmed anchor defects

The native exporter wrote **degrees into radian Euler fields**. For example, a
30-degree yaw became the float `30` rather than `0.5235988`; Halo interprets that
as approximately -81.127 degrees after wrapping. The error depends on the
authored angle. A fixed 60-degree correction cannot solve it generally.

The exporter and importer also used Blender's `ZYX` Euler order. Halo constructs
the cutscene flag forward vector as:

```text
forward = (cos(yaw) cos(pitch), sin(yaw) cos(pitch), sin(pitch))
```

For an upright yaw/pitch placement this is `Rz(yaw) @ Ry(-pitch)`, represented by
Blender's `XYZ` Euler order. The wrong order introduces errors when yaw and pitch
are combined. Pure yaw cannot reveal that second defect. Native anchor angles
now remain in radians and both cinematic import and export use `XYZ`.

H3 cutscene flags contain no scale or roll. The exporter rejects scaled/sheared
anchors, and the scenario writer rejects a placement requiring roll instead of
silently dropping it. The restriction is on the **exported placement** after
inverting the anchor and converting its axes, not simply a Blender Euler input.
Camera roll itself is supported through the camera forward and up vectors.

## Position and orientation

Let `C` convert Blender positions to Halo axes and world units, `B` be the
Blender scenery anchor, and `K` the Blender camera world matrix. In column-vector
notation:

```text
scenario placement W = C @ inverse(B) @ inverse(C)
camera position      = C @ K.translation
camera forward       = normalize(rotation(C) @ K.linear @ (0, 0, -1))
camera up            = normalize(rotation(C) @ K.linear @ (0, 1, 0))
runtime position     = W @ camera position
runtime directions   = rotation(W) @ camera directions
```

One Halo world unit is 3.048 metres. Blender-scale scenes therefore multiply
position by `1 / 3.048`; Max-scale scenes multiply by `0.01`. The selected scene
forward axis supplies the basis rotation. Unit conversion must not be applied
twice, and the anchor must not be baked into the camera and then applied again
by the engine.

Parent imported level geometry to the anchor. Keep cameras and cinematic actors
in the common shot space. Moving the anchor is not a replacement for moving a
camera relative to an actor. If both camera and actor receive the same rigid
placement, that placement cannot change the actor's size within the frame.

Sampling now uses the evaluated main camera, including constraints, parents,
drivers and animated lens data, at exact integer authoring frames. The previous
conversion from frames to seconds and back could produce a time just before an
integer frame. Extra cameras already used evaluated objects.

H3/ODST cinematic camera frame arrays play at 30 Hz. Export currently stores one
camera record per authoring frame, whereas actor JMA files also carry a frame
rate. A non-30-FPS source can therefore desynchronize actor and camera timing
when the actor animation is compiled. Export now requires an effective 30 FPS
(`fps / fps_base`). Retime existing animation before changing its frame rate;
automatic resampling of non-30-FPS cinematics is not implemented.

## Focal length and the render frame

The installed H3 runtime derives FOV from the **globals cinematic film aperture
and the frame focal length**. Its per-frame horizontal FOV and film-aperture
fields are authoring metadata; changing those alone does not fix playback.

The supplied `halo2_halo3_odst_fov_and_light_power_for_foundry.md` research
(12 October 2026) describes the DLLCache runtime's full pipeline. Foundry now
uses that pipeline for **both H3 and ODST**. The ODST extension is based on the
document's matching tags/shaders and stated common behavior; its runtime binary
was not independently decompiled or live-tested here.

The observer clamps the globals/lens horizontal angle to 1–150 degrees, then
converts it to a vertical angle using a fixed 4:3 aspect. The render camera
multiplies that **vertical angle by 0.785**. Cinematic widescreen correction
preserves the 4:3 horizontal extent and crops vertically to the 16:9 frame.
Angle scaling and tangent scaling do not commute. A constant lens or
film-aperture multiplier cannot describe this projection exactly.

The shared helpers in `camera_fov.py` implement the documented closed form:

```text
G = globals cinematic film aperture, in mm
f = stored tag focal length, in mm
tag_hfov = clamp(2 * atan(G / (2*f)), 1 degree, 150 degrees)
H_final = 2 * atan((4/3) * tan(0.785 * atan(tan(tag_hfov/2) / (4/3))))
V_final = 2 * atan((9/16) * tan(H_final/2))

# Export inverse, where H_target is Blender's resolved horizontal view:
observer_half_vertical = atan(tan(H_target/2) / (4/3)) / 0.785
tag_lens = G / ((8/3) * tan(observer_half_vertical))
```

`H_target` comes from [`Camera.view_frame(scene=scene)`](https://docs.blender.org/api/current/bpy.types.Camera.html#bpy.types.Camera.view_frame), so sensor fit, both sensor
dimensions, render aspect and pixel aspect are resolved together. It is not
always `camera.angle_x` or a gate based only on `camera.sensor_width`.
The representable final horizontal view is approximately 0.785–125 degrees.
Export warns and clamps a requested view outside this range, rather than
writing an unreproducible focal length. Import applies the observer clamp too.

With globals aperture 76 mm, horizontal sensor 36 mm and a 16:9 viewport:

| Blender lens | Corrected tag lens | Final horizontal FOV |
| --- | --- | --- |
| 24 mm | 37.278595 mm | 73.739795 degrees |
| 50 mm | 81.621228 mm | 39.597753 degrees |
| 85 mm | 140.129172 mm | 23.913169 degrees |

Import evaluates the forward runtime equation for **every lens key**, using
a fixed 36 mm horizontal Blender sensor. This keeps the complete clamped FOV
range within Blender's 1–5000 mm lens limits. The engine ignores per-frame
aperture/HFOV metadata; the actual globals aperture controls the conversion.
Changing the authored sensor during a shot is encoded in the runtime focal
length, so no animated sensor width is needed on import.

Author cinematics at 16:9 for matching horizontal and vertical framing.
Export preserves the resolved horizontal view at other authoring aspects and
warns that vertical framing will differ. The conversion uses the documented
cinematic horizontal reference rather than an inferred ultrawide fit. The
document did not verify shipping MCC ultrawide/FOV-slider behavior. Custom
cinematic render settings, camera shake, and different playback times remain
outside this projection contract. Compare images with the same letterbox crop.

Ordinary camera sync follows a different path: it uses the 4:3 observer and
0.785 angle scale, then expands horizontally using the actual display aspect,
without the cinematic crop. Camera sync takes the scene render aspect as the
target game display aspect, so set it to match the game. Writing a viewport
uses Blender's actual [`RegionView3D.window_matrix`](https://docs.blender.org/api/current/bpy.types.RegionView3D.html#bpy.types.RegionView3D.window_matrix);
reading uses the 72 mm perspective-viewport reference from Blender's
[camera parameter implementation](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/camera.cc).
H3/ODST scene-camera sync also resolves the horizontal view from sensor fit.
Reach/H4 camera conversion and auxiliary texture-feed conversion retain their
existing paths; this document does not establish equivalent renderer behavior.

Perspective projection with a centred lens is required. Lens shift creates an
off-axis frustum that H3's camera frame cannot encode. Orthographic cameras,
mirrored/degenerate camera transforms and non-orthogonal camera forward/up axes
are rejected. Export and import prefer the configured globals aperture. If the
tag is missing, unreadable, empty or has an invalid aperture, H3/ODST warn and
fall back to **76 mm**. Reach keeps 45 mm and H4/H2A keep 22.5 mm defaults.

## Executable evidence

The following addresses are virtual addresses in the inspected
`G:\Halo\Modding\Main\H3EK\halo3_tag_test.exe`, SHA-256
`59a78f2c96034d7ceb5d710505b2b36813aa141fc81a083e3f952973dbce4602`.
They are evidence for this build, not offsets to patch or assume in other builds.

| Address | Observed operation |
| --- | --- |
| `0x1407AEC00` | Script callback for `camera_set_cinematic_scene` |
| `0x140649E80` | Records scene, shot and cutscene-flag index in camera state |
| `0x140648670` | Samples/interpolates camera frames and applies the anchor |
| `0x14064BB00` | Reads scenario cutscene flag, builds its matrix and multiplies camera pose |
| `0x1402F4F70` | Converts native yaw/pitch directly through cosine and sine to forward |
| `0x1402E9D30` | Builds upright orthogonal up from forward |
| `0x14064AA26` | Main cinematic camera passes frame focal length to the lens routine |
| `0x1406473D0` | Computes `2 * atan(globals_aperture / (2 * lens))` |
| `0x1404E055B` | Stores the observer's 4:3 reference aspect |
| `0x1404E1D0B` | Converts the observer horizontal angle to vertical |
| `0x140901422` | Multiplies observer vertical FOV angle by 0.785 before render-camera setup |
| `0x140903D41` | Applies cinematic/widescreen adjustment to the final frustum |
| `0x1404ECB00` | Computes letterbox fit from style, state and viewport |

The native blam-tags reader/writer exposes `RealEulerAngles2d/3d` as raw radian
floats. Scenario marker import/export already uses that convention; cinematic
anchor export had retained the old ManagedBlam degree conversion.

## Regression coverage and calibration

Run `blender/tests/test_h3_cinematic_camera_blender.py` with Blender in background
mode and the native blam-tags wheel available. It creates a scenario and camera
tag, saves and reopens both, reconstructs the engine placement/projection with
independent sine/cosine and projection equations, and compares against Blender's
`calc_matrix_camera`.

The tracked test covers eight unit/forward-axis conventions, four anchor
placements, five lens/sensor/aspect combinations and four points at different
depths: 640 projected points, maximum horizontal error 0.033875 pixel, with
vertical projection checked for the documented 16:9 frame. It also tests actual
animated-lens tag import, H3/ODST clamp-limit imports, evaluated camera sampling,
exact frame times, range warnings and rejection of unsupported projections.

`test_camera_fov.py` checks the document's rounded focal/FOV table, the inverse,
custom globals, observer clamps, defaults and unavailable globals.
`test_cinematic_camera_projection_blender.py` checks native saved tags for both
games against Blender's projection matrix, including sensor fit and pixel
aspect. `test_cinematic_camera_roundtrip_blender.py` exercises actual animated
lens/sensor import and re-export for H3 and ODST, and verifies that ignored tag
metadata cannot override globals. `test_camera_sync_fov_blender.py` covers the
separate normal-camera path with real Blender camera projections.

## Live validation, 11 October 2026

A new playable scenario was installed under
`H3EK/tags/foundry_blam/camera_parity_20261011`, referencing the existing
`foundry_blam/box_map/box.scenario_structure_bsp`. Its geometry was imported to
Blender. Camera records were generated with the real `Frame` exporter, and
scenario anchors with the real cinematic/scenario writers. Five new tags were
installed in this separate folder; the game executable was not modified.

The game ran at 1920x1080, `reduce_widescreen_fov_during_cinematics = true`,
`camera_fov_scale = 1`, aspect scale 1, no forced 4:3, letterbox style 2 fully
shown. The 24, 50 and 85 mm identity shots were captured. A fourth capture used
the 24 mm shot through a placement translated to (12.5, -31.75, 8.25) world
units, with yaw 60 degrees and pitch 18 degrees. Blender scenery and camera
were transformed together to keep their relative view identical.

Read-only snapshots of the actual final render-camera position, forward/up and
frustum were compared against Blender's independently projected BSP vertices:

| Live shot | Landmark count | Maximum projected pixel error |
| --- | ---: | ---: |
| 24 mm, identity | 300 | 0.000296 |
| 50 mm, identity | 118 | 0.000527 |
| 85 mm, identity | 19 | 0.000695 |
| 24 mm, translated + yaw/pitch anchor | 300 | 0.000415 |

These are numerical projection errors using the **live final renderer state**,
not image-registration scores or a claim that lighting and antialiasing match.
The paired screenshots show the geometry aligned; materials and lighting differ.
The anchor's final position differs from the identity view by about 0.0000052
world units, with basis component errors below 0.0000002. No empirical yaw
adjustment was used. This validates static pose/projection in the inspected
H3EK build. Other executable builds, custom cinematic render settings and
subframe animated interpolation were not live-validated.

`reports/h3_cinematic_camera/live_fixture` contains the two Blender scenes,
reference renders, native tags, four game captures, live camera snapshots,
`live_verification.json`, and an interactive `comparison.html`. The fixture uses three
240-frame constant shots; running one manually can produce a harmless
"shot finished before next shot began" warning while holding its final camera.
The research folder also contains disassembly and regression logs. The older
`blender/output/cinematic_camera_debug` projection summaries predate discovery
of the 0.785 angle scale and are superseded by this document.

To reproduce, load `foundry_blam\camera_parity_20261011\camera_parity`, start
cinematic camera control, and call `camera_set_cinematic_scene` with scene
`foundry_blam\camera_parity_20261011\identity`, zero-based shot index 0/1/2,
and `identity_anchor`. The alternate scene is `rotated` with `rotated_anchor`.

Existing cinematics need a camera/scenario re-export to receive both the new
lens conversion and radian anchor flags. Restore the intended anchor placement
before exporting if it contains an empirical yaw workaround. The reported
user's source scene was unavailable; their exact actor animation and framing
could not be reproduced. The new playable calibration supplied independent
position, orientation and projection checks instead.

## Document-based FOV update, 12 October 2026

The subsequent implementation applies Part 1 of the supplied research to
cinematic export/import and ordinary camera sync. The earlier animated live
test was stopped at the user's request; it is not evidence of complete actor
alignment. This update does not change skeletal placement or light-power
conversion.

Validation passed 41 automated tests across the FOV helpers, native camera
writer/importer, Blender projection and camera-sync checks, plus 12 actual
animated import/re-export and metadata/globals cases. Saved-camera projection
checks covered 640 points with maximum horizontal error 0.033875 pixels.
Both H3 and ODST use the new conversion; re-export existing cinematic camera
tags to apply it. Use 16:9 authoring for vertical framing as well as horizontal
FOV. The earlier 1920x1080 H3 static live evidence remains applicable, while
ODST runtime and shipping MCC ultrawide behavior retain the supplied document's
verification limits.
