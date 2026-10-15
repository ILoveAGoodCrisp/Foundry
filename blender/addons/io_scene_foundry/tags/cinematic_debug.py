"""H3/ODST cinematic debugging using only existing engine functions/globals."""
from pathlib import Path

from .cinematic_import import CinematicImportDocument, tag_path_key


# Retained only to unlink the mission source installed by older Foundry builds.
DEBUG_SOURCE_PATH = Path('foundry/debug/foundry_cinematic_controls')

# These documented BSP diagnostics default to -1 in H3 and ODST. Foundry borrows
# them while using cinematic controls: 0/1 is the loop setting, and -1 means no
# active cinematic. Thread ownership/cancellation belongs to loop_it/loop_clear.
LOOP_VARIABLE = 'debug_leaf0_index'
ACTIVE_CINEMATIC_VARIABLE = 'debug_leaf1_index'


class CinematicDebugDocument(CinematicImportDocument):
    def remove_controls_source(self):
        """Remove only the obsolete Foundry source reference and cached source.

        The old synthesized source tag could assert during native tag loading.
        Don't load or rewrite that tag, or touch any other mission sources.
        """
        target = tag_path_key(DEBUG_SOURCE_PATH.with_suffix('.scenario_hs_source_file'))
        root = self.tag.root()
        field = root.field('scenario resources')
        resources = field.as_block() if field is not None else ()
        for resource_index in range(len(resources)):
            sources = self.block(resources[resource_index], 'script source')
            for index in reversed(range(len(sources))):
                reference = self.reference(sources[index], 'reference')
                if reference is not None and tag_path_key(reference.RelativePathWithExtension) == target:
                    sources.delete(index)
                    self.tag_has_changes = True
        field = self.tag.root().field('source files')
        sources = field.as_block() if field is not None else ()
        for index in reversed(range(len(sources))):
            if self.value(sources[index], 'name') == DEBUG_SOURCE_PATH.name:
                sources.delete(index)
                self.tag_has_changes = True


def h3_debug_commands(cinematic, scene_name, shot_number):
    """Resolve the cinematic index and migrate away from the old helper tag."""
    reference, _ = cinematic.scenario_reference()
    if not cinematic.path_exists(reference):
        raise ValueError('The cinematic must reference an existing scenario for H3/ODST debug playback')
    with CinematicDebugDocument(reference, tags_root=cinematic.tags_root,
                               game=cinematic.game, definitions=cinematic.definitions,
                               must_exist=True) as scenario:
        indices = scenario.cinematic_indices(cinematic.path)
        if not indices:
            raise ValueError(f'{scenario.path}: cinematic {cinematic.path} is not in the scenario cinematic list')
        cinematic_index = indices[0]
        scenario.remove_controls_source()

    active = ACTIVE_CINEMATIC_VARIABLE
    # Guard cleanup so Stop is safe before playback and after normal completion.
    cleanup = (
        f'(if (>= {active} 0) (begin '
        '(cinematic_lights_destroy) (cinematic_clips_destroy) '
        '(cinematic_destroy) (cinematic_stop) (camera_control off) '
        f'(render_exposure_fade_out 0) (cinematic_zone_deactivate {active}) '
        '(fade_in 0 0 0 0) (cinematic_show_letterbox_immediate 0) '
        f'(set {active} -1)))'
    )
    stop = f'(begin (loop_clear) {cleanup})'

    root = cinematic.tag.root()
    name = cinematic.value(root, 'name') or Path(cinematic.path).stem
    fade = cinematic.value(root, 'fade in color')
    fade_time = cinematic.value(root, 'fade in time')
    setup = (
        f'(set {active} {cinematic_index}) '
        f'(cinematic_zone_activate_for_debugging {cinematic_index}) (sleep 1) '
        '(camera_control on) (cinematic_start) (set cinematic_letterbox_style 2) '
        '(cinematic_show_letterbox_immediate 1) (camera_set_cinematic) '
        f'(cinematic_set (cinematic_tag_reference_get_cinematic {cinematic_index})) '
        f'(fade_in {fade.red:g} {fade.green:g} {fade.blue:g} {fade_time})'
    )
    # The generated full-cinematic wrapper already performs its own cleanup.
    full = (
        f'(begin (set {active} {cinematic_index}) ({name}_debug) '
        f'(set {active} -1) '
        '(fade_in 0 0 0 0) (cinematic_show_letterbox_immediate 0))'
    )
    bodies = {
        'cinematic': full,
        'scene': f'(begin {setup} (!{scene_name}) {cleanup})',
        'shot': f'(begin {setup} (!{scene_name}_sh{shot_number}) {cleanup})',
    }
    commands = {}
    for kind, body in bodies.items():
        # Even one-shot playback uses the engine's managed loop thread. Sleeping
        # after its sole pass prevents repetition while keeping Stop able to
        # cancel it. Never call loop_clear from inside the thread it would kill.
        expression = f'(begin {body} (if (!= {LOOP_VARIABLE} 1) (sleep_forever)))'
        commands[kind] = (
            f'(begin {stop} '
            f'(if (!= {LOOP_VARIABLE} 1) (set {LOOP_VARIABLE} 0)) '
            f'(loop_it "{expression}"))'
        )
    commands['stop'] = stop
    return commands
