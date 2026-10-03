from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from ... import utils
from ...tags.object_blender import ObjectTag
from ...tags.animation_names import convert_animation_name_for_project

# Add (identifier, display name, description) entries to these lists as needed.
HARD_CODED_MODE_OPTIONS = [
    ("combat", "combat", "The default mode for units"),
    ("crouch", "crouch", "Active when a biped is crouching"),
    ("sprint", "sprint", "Active when a biped is sprinting"),
]
HARD_CODED_SET_OPTIONS = [("sync_actions", "sync_actions", "For ai sync actions"),]
HARD_CODED_STATE_OPTIONS = [("idle", "idle", "The animation a unit should play when idle"),]

BUNKER_SET_OPTIONS = [
    ("center_crouch_closed", "center_crouch_closed", "Closed center crouch bunker set"),
    ("center_crouch_open", "center_crouch_open", "Open center crouch bunker set"),
    ("left_crouch_closed", "left_crouch_closed", "Closed left crouch bunker set"),
    ("left_crouch_open", "left_crouch_open", "Open left crouch bunker set"),
    ("left_stand_closed", "left_stand_closed", "Closed left standing bunker set"),
    ("left_stand_open", "left_stand_open", "Open left standing bunker set"),
    ("right_crouch_closed", "right_crouch_closed", "Closed right crouch bunker set"),
    ("right_crouch_open", "right_crouch_open", "Open right crouch bunker set"),
    ("right_stand_closed", "right_stand_closed", "Closed right standing bunker set"),
    ("right_stand_open", "right_stand_open", "Open right standing bunker set"),
]
BUNKER_CLOSED_ACTION_OPTIONS = [
    ("brace", "brace", "Closed-set bunker action"),
    ("enter", "enter", "Closed-set bunker action"),
    ("exit", "exit", "Closed-set bunker action"),
    ("idle", "idle", "Closed-set bunker action"),
    ("open", "open", "Closed-set bunker action"),
    ("peek", "peek", "Closed-set bunker action"),
    ("throw_grenade", "throw_grenade", "Closed-set bunker action"),
]
BUNKER_CLOSED_OVERLAY_OPTIONS = [
    ("aim_open", "aim_open", "Closed-set bunker overlay animation"),
    ("aim_open_out", "aim_open_out", "Closed-set bunker overlay animation"),
    ("aim_still_up", "aim_still_up", "Closed-set bunker overlay animation"),
    ("look_still_up", "look_still_up", "Closed-set bunker overlay animation"),
]
BUNKER_OPEN_ACTION_OPTIONS = [
    ("close", "close", "Open-set bunker action"),
    ("enter", "enter", "Open-set bunker action"),
    ("exit", "exit", "Open-set bunker action"),
    ("idle", "idle", "Open-set bunker action"),
]
BUNKER_OPEN_OVERLAY_OPTIONS = [
    ("aim_enter", "aim_enter", "Open-set bunker overlay animation"),
    ("aim_enter_out", "aim_enter_out", "Open-set bunker overlay animation"),
    ("aim_exit", "aim_exit", "Open-set bunker overlay animation"),
    ("aim_exit_in", "aim_exit_in", "Open-set bunker overlay animation"),
    ("aim_still_up", "aim_still_up", "Open-set bunker overlay animation"),
    ("fire_1", "fire_1", "Open-set bunker overlay animation"),
    ("look_still_up", "look_still_up", "Open-set bunker overlay animation"),
]

USEFUL_TAG_EXTS = ".biped", ".vehicle", ".giant", ".weapon"
PICKER_PLACEHOLDER = ("__pick__", "Choose...", "Choose a predefined graph value")
ANY_OPTION = ("any", "any", "No restrictions on use; exact matches have higher priority")

ANIMATION_NAME_TYPE_ACTION = (
    "action",
    "Action / Overlay",
    "A mode, weapon class, weapon type, set, and state graph entry",
)
ANIMATION_NAME_TYPE_TRANSITION = (
    "transition",
    "Transition",
    "A transition between source and destination graph entries",
)
ANIMATION_NAME_TYPE_DAMAGE = (
    "damage",
    "Death & Damage",
    "A ping or kill animation, optionally scoped to graph values",
)
ANIMATION_NAME_TYPE_BUNKER = (
    "bunker",
    "Bunker",
    "A bunker animation with a fixed bunker mode and predefined set and state options",
)
ANIMATION_NAME_TYPE_VEHICLE = ("vehicle", "Vehicle", "A vehicle animation that resolves to any mode")
ANIMATION_NAME_TYPE_FIRST_PERSON = (
    "first_person",
    "First Person",
    "A first-person animation that resolves to any mode",
)
ANIMATION_NAME_TYPE_WEAPON = ("weapon", "Weapon", "A weapon animation that resolves to any mode")
ANIMATION_NAME_TYPE_DEVICE = ("device", "Device", "A device animation that resolves to any mode")
ANIMATION_NAME_TYPE_SUSPENSION = (
    "suspension",
    "Vehicle Suspension",
    "An animation added to the vehicle suspension block",
)
ANIMATION_NAME_TYPE_OBJECT = (
    "object",
    "Object Function Overlay",
    "An animation added to the function overlays block",
)
ANIMATION_NAME_TYPE_CUSTOM = ("custom", "Custom", "Set the complete animation name directly")


def _is_first_person_animation_graph(context) -> bool:
    scene = getattr(context, "scene", None)
    scene_nwo = getattr(scene, "nwo", None)
    return bool(
        scene_nwo
        and scene_nwo.asset_type == "animation"
        and scene_nwo.asset_animation_type == "first_person"
    )


def _animation_game() -> str:
    project = utils.get_project(use_external=False)
    return getattr(project, "game", "")


def _animation_name_type_items(_self, context):
    items = []
    if _is_first_person_animation_graph(context):
        items.append(ANIMATION_NAME_TYPE_FIRST_PERSON)

    items.extend((
        ANIMATION_NAME_TYPE_ACTION,
        ANIMATION_NAME_TYPE_TRANSITION,
        ANIMATION_NAME_TYPE_DAMAGE,
        ANIMATION_NAME_TYPE_BUNKER,
    ))
    scene = getattr(context, "scene", None)
    scene_nwo = getattr(scene, "nwo", None)
    if scene_nwo is not None:
        if scene_nwo.asset_type == "model":
            if scene_nwo.output_vehicle:
                items.extend((ANIMATION_NAME_TYPE_VEHICLE, ANIMATION_NAME_TYPE_SUSPENSION))
            if scene_nwo.output_weapon:
                items.append(ANIMATION_NAME_TYPE_WEAPON)
            if any((
                scene_nwo.output_device_control,
                scene_nwo.output_device_dispenser,
                scene_nwo.output_device_machine,
                scene_nwo.output_device_terminal,
            )):
                items.append(ANIMATION_NAME_TYPE_DEVICE)

    items.extend((ANIMATION_NAME_TYPE_OBJECT, ANIMATION_NAME_TYPE_CUSTOM))
    return items


info_cache = None
active_animation_name_editor = None
vehicle_mode_operator_classes = []
vehicle_mode_operator_ids = {}

@dataclass
class ExternalGraphInfo:
    vehicle_modes: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    vehicle_modes_by_tag: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    weapon_classes: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    weapon_types: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    mode_items: list[tuple[str, str, str]] = field(default_factory=list)
    vehicle_mode_groups: list[tuple[str, str, str]] = field(default_factory=list)
    weapon_class_items: list[tuple[str, str, str]] = field(default_factory=list)
    weapon_type_items: list[tuple[str, str, str]] = field(default_factory=list)
    vehicle_mode_items: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)
    set_items: list[tuple[str, str, str]] = field(default_factory=list)
    state_items: list[tuple[str, str, str]] = field(default_factory=list)


def _build_option_items(
    hardcoded_options: list[tuple[str, str, str]],
    discovered_options: dict[str, set[str]],
    discovered_heading: str,
    include_any: bool = True,
) -> list[tuple[str, str, str]]:
    entries = {}
    if include_any:
        entries[ANY_OPTION[0]] = (ANY_OPTION[1], ANY_OPTION[2])

    for identifier, label, description in hardcoded_options:
        identifier = _clean_graph_value(identifier, "")
        if identifier:
            entries[identifier] = (label, description)

    for identifier, tag_paths in discovered_options.items():
        identifier = _clean_graph_value(identifier, "")
        if not identifier:
            continue

        tag_description = f"{discovered_heading}:\n" + "\n".join(sorted(tag_paths))
        if identifier in entries:
            label, description = entries[identifier]
            description = f"{description}\n\n{tag_description}" if description else tag_description
            entries[identifier] = (label, description)
        else:
            entries[identifier] = (identifier, tag_description)

    any_item = None
    if include_any:
        any_item = (ANY_OPTION[0], *entries.pop(ANY_OPTION[0]))
    discovered_items = [
        (identifier, label, description)
        for identifier, (label, description) in entries.items()
    ]
    discovered_items.sort(key=lambda item: (item[1].casefold(), item[0]))
    if any_item is not None:
        return [PICKER_PLACEHOLDER, any_item, *discovered_items]
    return [PICKER_PLACEHOLDER, *discovered_items]


def _build_vehicle_mode_groups(info: ExternalGraphInfo):
    tag_paths = sorted(
        info.vehicle_modes_by_tag,
        key=lambda tag_path: (Path(tag_path).stem.casefold(), tag_path.casefold()),
    )
    stem_counts = Counter(Path(tag_path).stem.casefold() for tag_path in tag_paths)

    for tag_path in tag_paths:
        stem = Path(tag_path).stem
        display_name = stem
        if stem_counts[stem.casefold()] > 1:
            display_name = str(Path(tag_path).with_suffix(""))

        mode_items = []
        for mode in sorted(info.vehicle_modes_by_tag[tag_path], key=str.casefold):
            applicable_tags = sorted(info.vehicle_modes[mode])
            description = "Vehicle/unit tags using this mode:\n" + "\n".join(applicable_tags)
            mode_items.append((mode, mode, description))

        if mode_items:
            info.vehicle_mode_groups.append(
                (tag_path, display_name, f"Seat modes from {tag_path}")
            )
            info.vehicle_mode_items[tag_path] = mode_items


def _get_external_graph_info() -> ExternalGraphInfo:
    global info_cache
    if info_cache is not None:
        return info_cache

    useful_tags = utils.paths_in_dir(utils.get_tags_path(), USEFUL_TAG_EXTS)
    info = ExternalGraphInfo()

    for path in useful_tags:
        try:
            match Path(path).suffix.lower():
                case ".biped" | ".vehicle" | ".giant":
                    with ObjectTag(path=path) as unit:
                        rel_path = unit.tag_path.RelativePathWithExtension
                        for label in unit.get_seat_names():
                            if label:
                                info.vehicle_modes[label].add(rel_path)
                                info.vehicle_modes_by_tag[rel_path].add(label)
                case ".weapon":
                    with ObjectTag(path=path) as weapon:
                        rel_path = weapon.tag_path.RelativePathWithExtension
                        weapon_class, weapon_type = weapon.get_weapon_names()
                        if weapon_class:
                            info.weapon_classes[weapon_class].add(rel_path)
                        if weapon_type:
                            info.weapon_types[weapon_type].add(rel_path)
        except Exception as ex:
            utils.print_warning(f"Could not read animation name options from {path}: {ex}")

    info.mode_items = _build_option_items(
        HARD_CODED_MODE_OPTIONS,
        info.vehicle_modes,
        "Vehicle/unit tags using this mode",
    )
    _build_vehicle_mode_groups(info)
    info.weapon_class_items = _build_option_items(
        [],
        info.weapon_classes,
        "Weapon tags using this class",
    )
    info.weapon_type_items = _build_option_items(
        [],
        info.weapon_types,
        "Weapon tags using this type",
    )
    info.set_items = _build_option_items(HARD_CODED_SET_OPTIONS, {}, "")
    info.state_items = _build_option_items(
        HARD_CODED_STATE_OPTIONS,
        {},
        "",
        include_any=False,
    )
    info_cache = info
    return info_cache


def _mode_picker_items(_self, _context):
    return _get_external_graph_info().mode_items


def _weapon_class_picker_items(_self, _context):
    return _get_external_graph_info().weapon_class_items


def _weapon_type_picker_items(_self, _context):
    return _get_external_graph_info().weapon_type_items


def _set_picker_items(_self, _context):
    return _get_external_graph_info().set_items


def _state_picker_items(_self, _context):
    return _get_external_graph_info().state_items



def _bunker_state_options(set_name: str):
    if _clean_graph_value(set_name, "").endswith("_open"):
        return BUNKER_OPEN_ACTION_OPTIONS, BUNKER_OPEN_OVERLAY_OPTIONS
    return BUNKER_CLOSED_ACTION_OPTIONS, BUNKER_CLOSED_OVERLAY_OPTIONS


def _bunker_state_picker_items(self, _context):
    actions, overlays = _bunker_state_options(self.set_name)
    return [
        PICKER_PLACEHOLDER,
        ("", "Actions", ""),
        *actions,
        None,
        ("", "Overlay Animations", ""),
        *overlays,
    ]

def _copy_picker_value(operator, picker_property: str, value_property: str):
    value = getattr(operator, picker_property)
    if value != PICKER_PLACEHOLDER[0]:
        setattr(operator, value_property, value)


def _update_mode_picker(self, _context):
    _copy_picker_value(self, "mode_picker", "mode")


def _update_weapon_class_picker(self, _context):
    _copy_picker_value(self, "weapon_class_picker", "weapon_class")


def _update_weapon_type_picker(self, _context):
    _copy_picker_value(self, "weapon_type_picker", "weapon_type")


def _update_set_picker(self, _context):
    _copy_picker_value(self, "set_picker", "set_name")


def _update_state_picker(self, _context):
    _copy_picker_value(self, "state_picker", "state")



def _update_bunker_set_picker(self, _context):
    _copy_picker_value(self, "bunker_set_picker", "set_name")
    self.bunker_state_picker = PICKER_PLACEHOLDER[0]


def _update_bunker_state_picker(self, _context):
    _copy_picker_value(self, "bunker_state_picker", "state")


def _update_animation_name_type(self, _context):
    if self.name_type != "bunker":
        return

    self.mode = "bunker"
    self.is_stance = False
    if _clean_graph_value(self.set_name) == "any":
        self.set_name = BUNKER_SET_OPTIONS[0][0]
    if _clean_graph_value(self.state) == "any":
        self.state = "idle"

def _update_destination_mode_picker(self, _context):
    _copy_picker_value(self, "destination_mode_picker", "destination_mode")


def _update_destination_state_picker(self, _context):
    _copy_picker_value(self, "destination_state_picker", "destination_state")
            

def _clean_graph_value(value: str, fallback: str = "any") -> str:
    """Return one lower-case graph token, converting whitespace to underscores."""
    value = str(value).strip(" :_,-").lower().replace(":", " ")
    return "_".join(value.split()) or fallback


def _clean_custom_name(value: str) -> str:
    value = str(value).strip(" :_,-").lower().replace(":", " ")
    return " ".join(value.split())


def _shortest_graph_prefix(mode: str, weapon_class: str, weapon_type: str, set_name: str) -> list[str]:
    values = [
        _clean_graph_value(mode),
        _clean_graph_value(weapon_class),
        _clean_graph_value(weapon_type),
        _clean_graph_value(set_name),
    ]
    last_specific = -1
    for index, value in enumerate(values):
        if value != "any":
            last_specific = index
    return values[:last_specific + 1]


def build_shortest_animation_name(
    name_type: str,
    *,
    game: str = "",
    is_stance: bool = False,
    is_first_person_dual: bool = False,
    mode: str = "any",
    weapon_class: str = "any",
    weapon_type: str = "any",
    set_name: str = "any",
    state: str = "idle",
    destination_mode: str = "any",
    destination_state: str = "idle",
    damage_power: str = "s",
    damage_type: str = "ping",
    damage_direction: str = "front",
    damage_region: str = "gut",
    variant: int = 0,
    custom: str = "",
) -> str:
    """Build the shortest name that resolves to the requested graph values."""
    if name_type == "custom":
        return _clean_custom_name(custom) or "idle"

    state = _clean_graph_value(state, "idle")
    prefix = _shortest_graph_prefix(mode, weapon_class, weapon_type, set_name)

    if name_type == "action":
        tokens = [*prefix, state] if prefix else ["any", state]
    elif name_type == "bunker":
        bunker_prefix = _shortest_graph_prefix("bunker", weapon_class, weapon_type, set_name)
        tokens = [*bunker_prefix, state]
    elif name_type == "transition":
        tokens = [*prefix, state] if prefix else [state]
        tokens.append("2")
        destination_mode = _clean_graph_value(destination_mode)
        destination_state = _clean_graph_value(destination_state, "idle")
        if destination_mode != "any":
            tokens.append(destination_mode)
        tokens.append(destination_state)
    elif name_type == "damage":
        power = "h" if damage_power in {"h", "hard"} else "s"
        damage_type = "kill" if damage_type == "kill" else "ping"
        tokens = [*prefix, f"{power}_{damage_type}"]
        tokens.append(_clean_graph_value(damage_direction, "front"))
        tokens.append(_clean_graph_value(damage_region, "gut"))
    else:
        if name_type == "first_person":
            special_mode = ("first_person dual"
                            if is_first_person_dual and game != "halo1"
                            else "first_person")
        else:
            special_mode = {
                "vehicle": "vehicle",
                "weapon": "weapon",
                "device": "device",
                "suspension": "suspension",
                "object": "object",
            }.get(name_type)
        tokens = [*special_mode.split(), state] if special_mode else ["any", state]

    if is_stance and name_type in {"action", "transition", "damage"}:
        tokens.insert(0, "stance")

    if variant > 0:
        tokens.append(f"var{variant}")

    name = " ".join(tokens)
    if name_type == "first_person" and game == "halo1":
        return convert_animation_name_for_project(name, "reach", "halo1")
    return name


def build_animation_name_from_editor(operator) -> str:
    return build_shortest_animation_name(
        operator.name_type,
        game=_animation_game(),
        is_stance=operator.is_stance,
        is_first_person_dual=operator.is_first_person_dual,
        mode=operator.mode,
        weapon_class=operator.weapon_class,
        weapon_type=operator.weapon_type,
        set_name=operator.set_name,
        state=operator.state,
        destination_mode=operator.destination_mode,
        destination_state=operator.destination_state,
        damage_power=operator.damage_power,
        damage_type=operator.damage_type,
        damage_direction=operator.damage_direction,
        damage_region=operator.damage_region,
        variant=operator.variant,
        custom=operator.custom,
    )


ANIMATION_NAME_PICKER_MENUS = {
    "mode_picker": "NWO_MT_AnimationNameModePicker",
    "weapon_class_picker": "NWO_MT_AnimationNameWeaponClassPicker",
    "weapon_type_picker": "NWO_MT_AnimationNameWeaponTypePicker",
    "set_picker": "NWO_MT_AnimationNameSetPicker",
    "state_picker": "NWO_MT_AnimationNameStatePicker",
    "bunker_set_picker": "NWO_MT_AnimationNameBunkerSetPicker",
    "bunker_state_picker": "NWO_MT_AnimationNameBunkerStatePicker",
    "destination_mode_picker": "NWO_MT_AnimationNameDestinationModePicker",
    "destination_state_picker": "NWO_MT_AnimationNameDestinationStatePicker",
}


def _draw_shared_graph_value(
    operator,
    layout,
    value_property: str,
    picker_property: str,
    text: str | None = None,
):
    row = layout.row(align=True)
    if text is None:
        row.prop(operator, value_property)
    else:
        row.prop(operator, value_property, text=text)
    row.menu(ANIMATION_NAME_PICKER_MENUS[picker_property], text="", icon="DOWNARROW_HLT")


def draw_animation_name_fields(operator, layout, context):
    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.prop(operator, "name_type")
    if operator.name_type in {"action", "transition", "damage"}:
        layout.prop(operator, "is_stance")
    elif operator.name_type == "first_person" and _animation_game() != "halo1":
        layout.prop(operator, "is_first_person_dual")

    if operator.name_type == "custom":
        layout.prop(operator, "custom")
    elif operator.name_type == "bunker":
        row = layout.row()
        row.enabled = False
        row.prop(operator, "mode")
        _draw_shared_graph_value(operator, layout, "weapon_class", "weapon_class_picker")
        _draw_shared_graph_value(operator, layout, "weapon_type", "weapon_type_picker")
        _draw_shared_graph_value(operator, layout, "set_name", "bunker_set_picker")
        _draw_shared_graph_value(operator, layout, "state", "bunker_state_picker")
        layout.prop(operator, "variant")
    elif operator.name_type in {
        "vehicle",
        "first_person",
        "weapon",
        "device",
        "suspension",
        "object",
    }:
        _draw_shared_graph_value(operator, layout, "state", "state_picker")
        layout.prop(operator, "variant")
    else:
        if operator.name_type == "transition":
            layout.label(text="Source Graph Entry")
        elif operator.name_type == "damage":
            layout.label(text="Graph Scope")

        _draw_shared_graph_value(operator, layout, "mode", "mode_picker")
        _draw_shared_graph_value(operator, layout, "weapon_class", "weapon_class_picker")
        _draw_shared_graph_value(operator, layout, "weapon_type", "weapon_type_picker")
        _draw_shared_graph_value(operator, layout, "set_name", "set_picker")

        if operator.name_type == "transition":
            _draw_shared_graph_value(operator, layout, "state", "state_picker", "Source State")
            layout.separator()
            layout.label(text="Destination Graph Entry")
            _draw_shared_graph_value(operator, layout, "destination_mode", "destination_mode_picker")
            _draw_shared_graph_value(operator, layout, "destination_state", "destination_state_picker")
        elif operator.name_type == "damage":
            layout.separator()
            layout.prop(operator, "damage_power")
            layout.prop(operator, "damage_type")
            layout.prop(operator, "damage_direction")
            layout.prop(operator, "damage_region")
        else:
            _draw_shared_graph_value(operator, layout, "state", "state_picker")

        layout.prop(operator, "variant")

    layout.separator()
    layout.box().label(
        text=f"Result: {build_animation_name_from_editor(operator)}",
        icon="SORTALPHA",
    )


def prepare_animation_name_editor(operator):
    global active_animation_name_editor
    _get_external_graph_info()
    _ensure_vehicle_mode_operators()
    active_animation_name_editor = operator


def release_animation_name_editor(operator=None):
    global active_animation_name_editor
    if operator is None or active_animation_name_editor is operator:
        active_animation_name_editor = None


def _poll_animation_name_mode_operator(_cls, _context):
    return active_animation_name_editor is not None


def _describe_animation_name_mode_operator(cls, _context, properties):
    return properties.description_text or cls.bl_description


def _execute_animation_name_mode_operator(operator, context):
    if operator.target_property not in {"mode", "destination_mode"}:
        return {"CANCELLED"}

    try:
        setattr(active_animation_name_editor, operator.target_property, operator.mode)
    except (AttributeError, ReferenceError):
        return {"CANCELLED"}

    if context.area is not None:
        context.area.tag_redraw()
    return {"FINISHED"}


class NWO_OT_AnimationNameSetMode(bpy.types.Operator):
    bl_idname = "nwo.animation_name_set_mode"
    bl_label = "Set Animation Mode"
    bl_description = "Set a predefined mode on the open animation name editor"
    bl_property = "mode"

    mode: bpy.props.StringProperty(options={"HIDDEN"})
    target_property: bpy.props.StringProperty(default="mode", options={"HIDDEN"})
    description_text: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        return _describe_animation_name_mode_operator(cls, context, properties)

    @classmethod
    def poll(cls, context):
        return _poll_animation_name_mode_operator(cls, context)

    def execute(self, context):
        return _execute_animation_name_mode_operator(self, context)


class NWO_OT_AnimationNameSetGraphValue(bpy.types.Operator):
    bl_idname = "nwo.animation_name_set_graph_value"
    bl_label = "Set Animation Graph Value"
    bl_description = "Set a predefined value on the open animation name editor"

    value: bpy.props.StringProperty(options={"HIDDEN"})
    target_property: bpy.props.StringProperty(options={"HIDDEN"})
    description_text: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        return properties.description_text or cls.bl_description

    @classmethod
    def poll(cls, context):
        return active_animation_name_editor is not None

    def execute(self, context):
        if self.target_property not in {
            "weapon_class", "weapon_type", "set_name", "state", "destination_state"
        }:
            return {"CANCELLED"}

        try:
            setattr(active_animation_name_editor, self.target_property, self.value)
        except (AttributeError, ReferenceError):
            return {"CANCELLED"}

        if context.area is not None:
            context.area.tag_redraw()
        return {"FINISHED"}


def _ensure_vehicle_mode_operators():
    if vehicle_mode_operator_ids:
        return

    info = _get_external_graph_info()
    operator_id_by_items = {}

    try:
        for tag_path, _display_name, _description in info.vehicle_mode_groups:
            items = tuple(info.vehicle_mode_items[tag_path])
            operator_id = operator_id_by_items.get(items)
            if operator_id is None:
                index = len(operator_id_by_items)
                class_name = f"NWO_OT_AnimationNameVehicleMode{index:04d}"
                operator_id = f"nwo.animation_name_vehicle_mode_{index:04d}"
                operator_class = type(
                    class_name,
                    (bpy.types.Operator,),
                    {
                        "__module__": __name__,
                        "bl_idname": operator_id,
                        "bl_label": "Set Vehicle Mode",
                        "bl_description": "Set a vehicle seat mode on the open animation name editor",
                        "bl_property": "mode",
                        "__annotations__": {
                            "mode": bpy.props.EnumProperty(
                                name="Vehicle Mode",
                                options=set(),
                                items=list(items),
                            ),
                            "target_property": bpy.props.StringProperty(
                                default="mode",
                                options={"HIDDEN"},
                            ),
                            "description_text": bpy.props.StringProperty(options={"HIDDEN"}),
                        },
                        "poll": classmethod(_poll_animation_name_mode_operator),
                        "description": classmethod(_describe_animation_name_mode_operator),
                        "execute": _execute_animation_name_mode_operator,
                    },
                )
                bpy.utils.register_class(operator_class)
                vehicle_mode_operator_classes.append(operator_class)
                operator_id_by_items[items] = operator_id

            vehicle_mode_operator_ids[tag_path] = operator_id
    except Exception:
        unregister_vehicle_mode_operators()
        raise


def unregister_vehicle_mode_operators():
    vehicle_mode_operator_ids.clear()
    for operator_class in reversed(vehicle_mode_operator_classes):
        try:
            bpy.utils.unregister_class(operator_class)
        except RuntimeError:
            pass
    vehicle_mode_operator_classes.clear()


def _draw_animation_name_mode_menu(layout, target_property: str):
    for identifier, label, description in (ANY_OPTION, *HARD_CODED_MODE_OPTIONS):
        operator = layout.operator("nwo.animation_name_set_mode", text=label)
        operator.mode = identifier
        operator.target_property = target_property
        operator.description_text = description

    layout.separator()
    layout.label(text="Seat (Vehicle) Modes")

    info = _get_external_graph_info()
    if not info.vehicle_mode_groups:
        layout.label(text="No seat modes found", icon="INFO")
        return

    _ensure_vehicle_mode_operators()

    for tag_path, display_name, description in info.vehicle_mode_groups:
        operator = layout.operator_menu_enum(
            vehicle_mode_operator_ids[tag_path],
            "mode",
            text=display_name,
        )
        operator.target_property = target_property
        operator.description_text = description


class NWO_MT_AnimationNameModePicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameModePicker"
    bl_label = "Mode Options"

    def draw(self, context):
        _draw_animation_name_mode_menu(self.layout, "mode")


class NWO_MT_AnimationNameDestinationModePicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameDestinationModePicker"
    bl_label = "Destination Mode Options"

    def draw(self, context):
        _draw_animation_name_mode_menu(self.layout, "destination_mode")


def _draw_animation_name_value_menu(layout, target_property: str, items):
    for item in items:
        if item is None:
            layout.separator()
            continue

        identifier, label, description = item
        if identifier == PICKER_PLACEHOLDER[0]:
            continue
        if not identifier:
            layout.label(text=label)
            continue

        operator = layout.operator("nwo.animation_name_set_graph_value", text=label)
        operator.value = identifier
        operator.target_property = target_property
        operator.description_text = description


class NWO_MT_AnimationNameWeaponClassPicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameWeaponClassPicker"
    bl_label = "Weapon Class Options"

    def draw(self, context):
        _draw_animation_name_value_menu(
            self.layout, "weapon_class", _get_external_graph_info().weapon_class_items
        )


class NWO_MT_AnimationNameWeaponTypePicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameWeaponTypePicker"
    bl_label = "Weapon Type Options"

    def draw(self, context):
        _draw_animation_name_value_menu(
            self.layout, "weapon_type", _get_external_graph_info().weapon_type_items
        )


class NWO_MT_AnimationNameSetPicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameSetPicker"
    bl_label = "Set Options"

    def draw(self, context):
        _draw_animation_name_value_menu(
            self.layout, "set_name", _get_external_graph_info().set_items
        )


class NWO_MT_AnimationNameStatePicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameStatePicker"
    bl_label = "State Options"

    def draw(self, context):
        _draw_animation_name_value_menu(
            self.layout, "state", _get_external_graph_info().state_items
        )


class NWO_MT_AnimationNameBunkerSetPicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameBunkerSetPicker"
    bl_label = "Bunker Set Options"

    def draw(self, context):
        _draw_animation_name_value_menu(self.layout, "set_name", BUNKER_SET_OPTIONS)


class NWO_MT_AnimationNameBunkerStatePicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameBunkerStatePicker"
    bl_label = "Bunker State Options"

    def draw(self, context):
        if active_animation_name_editor is None:
            return
        _draw_animation_name_value_menu(
            self.layout,
            "state",
            _bunker_state_picker_items(active_animation_name_editor, context),
        )


class NWO_MT_AnimationNameDestinationStatePicker(bpy.types.Menu):
    bl_idname = "NWO_MT_AnimationNameDestinationStatePicker"
    bl_label = "Destination State Options"

    def draw(self, context):
        _draw_animation_name_value_menu(
            self.layout, "destination_state", _get_external_graph_info().state_items
        )


class NWO_OT_SetAnimationName(bpy.types.Operator):
    bl_idname = "nwo.set_animation_name"
    bl_label = "Edit Animation Name"
    bl_description = "Edit the active animation or animation rename using its graph values"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.StringProperty(default="animation", options={"HIDDEN"})
    name_type: bpy.props.EnumProperty(
        name="Animation Name Type",
        options=set(),
        items=_animation_name_type_items,
        update=_update_animation_name_type,
    )
    mode: bpy.props.StringProperty(
        name="Mode",
        default="any",
        options=set(),
        description="The mode required to use this animation, or 'any' for every mode",
    )
    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        default="any",
        options=set(),
        description="The required weapon class, or 'any' for every class",
    )
    weapon_type: bpy.props.StringProperty(
        name="Weapon Type",
        default="any",
        options=set(),
        description="The required weapon type, or 'any' for every type",
    )
    set_name: bpy.props.StringProperty(
        name="Set",
        default="any",
        options=set(),
        description="The required animation set, or 'any' for every set",
    )
    state: bpy.props.StringProperty(
        name="State",
        default="idle",
        options=set(),
        description="The state in which this animation plays",
    )
    destination_mode: bpy.props.StringProperty(
        name="Destination Mode",
        default="any",
        options=set(),
        description="The mode entered by this transition, or 'any' when unspecified",
    )
    destination_state: bpy.props.StringProperty(
        name="Destination State",
        default="idle",
        options=set(),
        description="The state entered by this transition",
    )
    damage_power: bpy.props.EnumProperty(
        name="Power",
        options=set(),
        items=[("h", "Hard", ""), ("s", "Soft", "")],
    )
    damage_type: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        items=[
            ("ping", "Ping", ""),
            ("kill", "Kill", ""),
        ],
    )
    damage_direction: bpy.props.EnumProperty(
        name="Direction",
        options=set(),
        items=[
            ("front", "Front", ""),
            ("left", "Left", ""),
            ("right", "Right", ""),
            ("back", "Back", ""),
        ],
    )
    damage_region: bpy.props.EnumProperty(
        name="Region",
        options=set(),
        items=[
            ("gut", "Gut", ""),
            ("chest", "Chest", ""),
            ("head", "Head", ""),
            ("l_arm", "Left Arm", ""),
            ("l_hand", "Left Hand", ""),
            ("l_leg", "Left Leg", ""),
            ("l_foot", "Left Foot", ""),
            ("r_arm", "Right Arm", ""),
            ("r_hand", "Right Hand", ""),
            ("r_leg", "Right Leg", ""),
            ("r_foot", "Right Foot", ""),
        ],
    )
    variant: bpy.props.IntProperty(
        name="Variant",
        default=0,
        min=0,
        options=set(),
        description="Values greater than zero add 'var' followed by this number to the animation name",
    )
    custom: bpy.props.StringProperty(
        name="Name",
        options=set(),
        description="The complete custom animation name",
    )
    is_stance: bpy.props.BoolProperty(
        name="Stance",
        options=set(),
        description="Prefix this animation name with the stance token",
    )
    is_first_person_dual: bpy.props.BoolProperty(
        name="Dual Wield",
        options=set(),
        description="Use the dual-wield first-person animation name form",
    )
    mode_picker: bpy.props.EnumProperty(
        name="Mode Options",
        options=set(),
        items=_mode_picker_items,
        update=_update_mode_picker,
    )
    weapon_class_picker: bpy.props.EnumProperty(
        name="Weapon Class Options",
        options=set(),
        items=_weapon_class_picker_items,
        update=_update_weapon_class_picker,
    )
    weapon_type_picker: bpy.props.EnumProperty(
        name="Weapon Type Options",
        options=set(),
        items=_weapon_type_picker_items,
        update=_update_weapon_type_picker,
    )
    set_picker: bpy.props.EnumProperty(
        name="Set Options",
        options=set(),
        items=_set_picker_items,
        update=_update_set_picker,
    )
    state_picker: bpy.props.EnumProperty(
        name="State Options",
        options=set(),
        items=_state_picker_items,
        update=_update_state_picker,
    )
    bunker_set_picker: bpy.props.EnumProperty(
        name="Bunker Set Options",
        options=set(),
        items=[PICKER_PLACEHOLDER, *BUNKER_SET_OPTIONS],
        update=_update_bunker_set_picker,
    )
    bunker_state_picker: bpy.props.EnumProperty(
        name="Bunker State Options",
        options=set(),
        items=_bunker_state_picker_items,
        update=_update_bunker_state_picker,
    )
    destination_mode_picker: bpy.props.EnumProperty(
        name="Destination Mode Options",
        options=set(),
        items=_mode_picker_items,
        update=_update_destination_mode_picker,
    )
    destination_state_picker: bpy.props.EnumProperty(
        name="Destination State Options",
        options=set(),
        items=_state_picker_items,
        update=_update_destination_state_picker,
    )

    @classmethod
    def poll(cls, context):
        scene_nwo = getattr(context.scene, "nwo", None)
        return bool(
            scene_nwo
            and scene_nwo.animations
            and 0 <= scene_nwo.active_animation_index < len(scene_nwo.animations)
        )

    @staticmethod
    def _active_animation(context):
        scene_nwo = context.scene.nwo
        return scene_nwo.animations[scene_nwo.active_animation_index]

    def _active_name_target(self, context):
        animation = self._active_animation(context)
        if self.target != "rename":
            return animation

        index = animation.active_animation_rename_index
        if 0 <= index < len(animation.animation_renames):
            return animation.animation_renames[index]
        return None

    def _set_graph_values(self, parsed: utils.AnimationName):
        self.mode = parsed.mode or "any"
        self.weapon_class = parsed.weapon_class or "any"
        self.weapon_type = parsed.weapon_type or "any"
        self.set_name = parsed.set or "any"
        self.state = parsed.state or "idle"

    def _load_name(self, context, name: str):
        original_name = name
        # Parse H1 first-person names with the editor's canonical tokens so
        # edits retain the mode and %variant instead of becoming unit actions.
        if _animation_game() == "halo1" and utils.tokenise(name)[:1] == ("first-person",):
            name = convert_animation_name_for_project(name, "halo1", "reach")
        parsed = utils.AnimationName(name)
        tokens = utils.tokenise(name)
        self.custom = original_name
        self.is_stance = parsed.stance
        self.is_first_person_dual = False
        variant = parsed.variant.removeprefix("var")
        self.variant = int(variant) if variant.isdigit() else 0

        if not parsed.valid or not tokens:
            self.name_type = "custom"
            return

        self._set_graph_values(parsed)
        first_token = tokens[0]

        if not parsed.stance and first_token == "first_person":
            name_type = "first_person"
            self.is_first_person_dual = len(tokens) > 1 and tokens[1] == "dual"
        elif not parsed.stance and first_token in {"vehicle", "weapon", "device", "suspension", "object"}:
            name_type = first_token
        elif not parsed.stance and first_token == "tread":
            name_type = "custom"
        elif not parsed.stance and first_token.startswith("device_"):
            name_type = "device"
            self.state = first_token.removeprefix("device_") or "idle"
        elif not parsed.stance and parsed.mode == "bunker":
            name_type = "bunker"
        elif parsed.type == utils.AnimationStateType.TRANSITION:
            name_type = "transition"
            self.destination_mode = parsed.destination_mode or "any"
            self.destination_state = parsed.destination_state or "idle"
        elif parsed.type == utils.AnimationStateType.DAMAGE:
            name_type = "damage"
            self.damage_power = "h" if parsed.state.startswith("h_") else "s"
            self.damage_type = "kill" if parsed.state.endswith("_kill") else "ping"
            self.damage_direction = parsed.direction or "front"
            self.damage_region = parsed.region or "gut"
        else:
            name_type = "action"

        available_types = {item[0] for item in _animation_name_type_items(self, context)}
        self.name_type = name_type if name_type in available_types else "custom"

    def build_name(self) -> str:
        return build_animation_name_from_editor(self)

    def _draw_graph_value(self, layout, value_property: str, picker_property: str, text: str | None = None):
        row = layout.row(align=True)
        if text is None:
            row.prop(self, value_property)
        else:
            row.prop(self, value_property, text=text)
        row.menu(ANIMATION_NAME_PICKER_MENUS[picker_property], text="", icon="DOWNARROW_HLT")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "name_type")
        if self.name_type in {"action", "transition", "damage"}:
            layout.prop(self, "is_stance")
        elif self.name_type == "first_person" and _animation_game() != "halo1":
            layout.prop(self, "is_first_person_dual")

        if self.name_type == "custom":
            layout.prop(self, "custom")
        elif self.name_type == "bunker":
            row = layout.row()
            row.enabled = False
            row.prop(self, "mode")
            self._draw_graph_value(layout, "weapon_class", "weapon_class_picker")
            self._draw_graph_value(layout, "weapon_type", "weapon_type_picker")
            self._draw_graph_value(layout, "set_name", "bunker_set_picker")
            self._draw_graph_value(layout, "state", "bunker_state_picker")
            layout.prop(self, "variant")
        elif self.name_type in {
            "vehicle",
            "first_person",
            "weapon",
            "device",
            "suspension",
            "object",
        }:
            self._draw_graph_value(layout, "state", "state_picker")
            layout.prop(self, "variant")
        else:
            if self.name_type == "transition":
                layout.label(text="Source Graph Entry")
            elif self.name_type == "damage":
                layout.label(text="Graph Scope")

            self._draw_graph_value(layout, "mode", "mode_picker")
            self._draw_graph_value(layout, "weapon_class", "weapon_class_picker")
            self._draw_graph_value(layout, "weapon_type", "weapon_type_picker")
            self._draw_graph_value(layout, "set_name", "set_picker")

            if self.name_type == "transition":
                self._draw_graph_value(layout, "state", "state_picker", "Source State")
                layout.separator()
                layout.label(text="Destination Graph Entry")
                self._draw_graph_value(layout, "destination_mode", "destination_mode_picker")
                self._draw_graph_value(layout, "destination_state", "destination_state_picker")
            elif self.name_type == "damage":
                layout.separator()
                layout.prop(self, "damage_power")
                layout.prop(self, "damage_type")
                layout.prop(self, "damage_direction")
                layout.prop(self, "damage_region")
            else:
                self._draw_graph_value(layout, "state", "state_picker")

            layout.prop(self, "variant")

        layout.separator()
        layout.box().label(text=f"Result: {self.build_name()}", icon="SORTALPHA")

    def execute(self, context):
        animation = self._active_animation(context)
        name_target = self._active_name_target(context)
        if name_target is None:
            release_animation_name_editor(self)
            self.report({"ERROR"}, "No animation rename is selected")
            return {"CANCELLED"}

        old_name = name_target.name
        new_name = self.build_name()

        siblings = (
            animation.animation_renames
            if self.target == "rename"
            else context.scene.nwo.animations
        )
        for other in siblings:
            if other.as_pointer() != name_target.as_pointer() and other.name == new_name:
                release_animation_name_editor(self)
                self.report({"ERROR"}, f"An animation named '{new_name}' already exists")
                return {"CANCELLED"}

        name_target.name = new_name
        release_animation_name_editor(self)
        self.report({"INFO"}, f"Renamed '{old_name}' to '{new_name}'")
        return {"FINISHED"}

    def cancel(self, context):
        release_animation_name_editor(self)
    
    def invoke(self, context, _event):
        name_target = self._active_name_target(context)
        if name_target is None:
            self.report({"ERROR"}, "No animation rename is selected")
            return {"CANCELLED"}

        self._load_name(context, name_target.name)
        prepare_animation_name_editor(self)
        return context.window_manager.invoke_props_dialog(self, width=520)


ANIMATION_NAME_PROPERTY_NAMES = (
    "name_type", "mode", "weapon_class", "weapon_type", "set_name", "state",
    "destination_mode", "destination_state", "damage_power", "damage_type",
    "damage_direction", "damage_region", "variant", "custom", "is_stance",
    "is_first_person_dual", "mode_picker", "weapon_class_picker",
    "weapon_type_picker", "set_picker", "state_picker", "bunker_set_picker",
    "bunker_state_picker", "destination_mode_picker", "destination_state_picker",
)


def reuse_animation_name_properties(operator_class):
    annotations = dict(getattr(operator_class, "__annotations__", {}))
    source_annotations = NWO_OT_SetAnimationName.__annotations__
    for property_name in ANIMATION_NAME_PROPERTY_NAMES:
        source_property = source_annotations[property_name]
        annotations[property_name] = source_property.function(**source_property.keywords)
    operator_class.__annotations__ = annotations
    return operator_class
