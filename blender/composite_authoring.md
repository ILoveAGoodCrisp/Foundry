# Composite authoring (Halo 4 / H2AMP)

Use one chain of blend axes, with every source and phase set on the innermost
axis. The supplied H4 Tool importer counts each axis as a dimension and stores
at most three axes. Each phase set needs its own valid blend geometry.

## Choosing a blend space

- Forward-only movement: Movement Speed, with idle/walk/run at distinct speeds.
- Directional movement at one speed: Movement Angles.
- Directional movement at multiple speeds: Movement Angles, then Movement Speed
  as its child, with sources on the speed axis.
- One sprint cycle: Movement Speed with the same source at two distinct manual
  speed coordinates. This produces a constant-pose blend, not a second gait.
  Adjust the speed range and check stride and playback in the game.

Export removes constant movement dimensions when their values are known. It
repairs old single-source speed blends using two endpoints, without changing
the saved Blender setup. Explicit phase-selection policies and outer-axis set
bounds prevent reductions that would discard those controls.

Samples must be distinct and span the remaining dimensions: three collinear
samples do not make a valid two-dimensional blend. Foundry validates resolved
values before Tool runs. Tool must still validate unresolved animation motion,
source availability, and the resulting triangulation.

### Angle spacing and blend limits

An Animation Source Limit restricts how far apart samples may blend; it is not
the angular spacing of the animation clips. Adding 45-degree diagonals does not
automatically justify a limit of 45. Sparse converted locomotes use limit 0
(unlimited), including their aim composites.

The stock Marine and Master Chief crouch/rifle composites use angle columns
from 0 through 360 in 45-degree steps, with stationary, walk and run samples at
each column. This gives their 45-degree limit enough local triangle coverage.
Repeating a source at multiple manual coordinates does not require duplicate
Blender actions. Include both ends of the angular seam when copying this layout.

For resolved two-axis layouts, Foundry checks that each sample can participate
in a non-degenerate triangle within the configured limits. If it cannot, export
warns and changes finite animation limits to 0 in the exported XML only. Saved
Blender settings remain unchanged. This repairs the demonstrated sparse crouch
layout; it does not certify every possible Tool triangulation or runtime blend.
Review the resulting transitions in game. Invalid sample counts, duplicates,
and deficient dimensional coverage still stop export with an explanation.

Tool processing also has a watchdog in every output mode: a recognised composite
is stopped after 60 seconds without output or 180 seconds in that composite.
If progress messages are suppressed, a fallback stops Tool after 30 minutes
without any output. Only the Tool process started for that import is stopped.

## Groups and phase sets

A group supplies common axis values to its sources. Its optional **Phase Set**
field assigns those sources to a set on the same axis. Leaf overrides take
precedence over group values. A blank field exports the group on the axis.

A phase set is a separate population for triangulation and synchronisation.
Generated locomotes store sources directly in Blend Axis Animations; one blend
population does not need an explicit phase set. Add a phase set when you need
authored synchronization keys or separate populations with their own timing.
Use one locomotion set for compatible walk/run/directional cycles. Do not split
each direction into a separate set in a two-axis locomote merely for organisation.
Use groups for direction labels instead.

If named sets and unassigned sources coexist, unassigned sources are exported
in a separate set. That set must independently have valid blend geometry.

**Synchronise Using Frame Events** selects existing frame-event types as timing
landmarks. For example, left/right foot events identify matching foot phases
across cycles. Checking these controls neither creates events nor enables foot
locking. Author consistent events in the source clips. Match A–D and primary /
secondary / tertiary keyframes are useful landmarks for other authored actions.

The optional set **Timing Source** overrides the composite timing source for that
set. **Manual Set Bounds** specifies its range in the outermost animation axis's
units. Equal bounds request Tool's automatic range calculation.

**Phase Selection Priority** belongs to a blend axis. It exports Tool's
`phase_select` policy (`current`, `cycle`, or `alternate`). Default uses `current`,
or a consistent priority saved on legacy phase sets. Conflicting legacy values
require an explicit axis choice. The supplied importer verifies these policies
but does not contain the runtime implementation of their switching behaviour;
leave Default unless reproducing a known setup or testing that behaviour in game.

Older Foundry versions displayed priority on each set but did not export it.
Changing a priority now has an exported effect.

## Export checks

Foundry reports empty sources, missing timing selection, unknown group set names,
conflicting legacy priority, invalid axis layout, duplicate coordinates, insufficient
samples and deficient dimensional coverage. Different clips at identical resolved
coordinates are reported rather than silently discarded.

Automatic values come from exported movement where available. Manual values
remain authoritative: recheck them after changing motion or timing, particularly
on converted locomotes and aim overlays. A successful XML check is not a substitute
for importing with the target Tool executable and checking animation in the game.

## Generated diagonal cycles

Diagonal generation redirects a coherent forward/backward cycle, including the
pelvis position and orientation and both complete leg chains. It retains that
cycle's duration and frame events. The sideways source supplies movement direction
and contributes to the target speed; its potentially incompatible leg and hip
poses are not averaged into the result. Torso orientation is compensated while
its position follows the hips.

This avoids mixing opposite foot phases or twisting the pelvis between
incompatible forward/backward and strafe poses. It is a conservative fallback,
not a replacement for authored diagonal animation or a foot-contact IK solver.
Different source speeds can still require stride tuning. Both source cycles need
horizontal pedestal displacement for automatic direction measurement.

The change applies when diagonals are generated again. Existing diagonal actions
are preserved, including hand-authored ones; reimport the original movement cycles
into a fresh animation setup to regenerate them safely.

## Conversion from older games

The older-game/Reach animation-graph conversion path for H4 and H2AMP uses these
same generators. It fills missing aim locomotes against the final base cycles,
including newly generated diagonals, preferring a matching movement aim screen
over a still screen. Existing overlays and authored diagonals are preserved.
Generated aim composites are explicitly exported as composite overlays.

Legacy `sprint ... move_front_fast` cycles also produce speed-only locomotes,
including a single-cycle fallback when no other sprint speed is available.
Converted composites always use manual coordinates: run/sprint 1.0, walk 0.5,
walkslow 0.2, and idle/in-place 0.0, independently of measured root speed.
Animation and runtime speed bounds are 0..1. Directional composites put Movement
Angles before Movement Speed; forward-only composites keep just Movement Speed.
Base and aim composites use the same coordinates. Sources are stored directly
on the terminal axis without automatically created phase sets or sync keys.
Source frame events are preserved. When imported clips share a blend coordinate, the
generator reports the collision and uses the first clip (idle before an in-place
cycle); all source actions remain available for manual editing.

When a stationary source exists, conversion reuses it at each moving angle.
This supplies stationary triangle coverage for the normalized gait rows without
duplicating the source action. Tool testing showed that a single idle at angle
zero with a flat run-speed row can stall even with unlimited blending; the
stationary row imported successfully. Existing composites are preserved;
these defaults apply to newly converted composites.
