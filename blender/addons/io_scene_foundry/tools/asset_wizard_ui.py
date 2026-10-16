"""Custom, modal New Asset interface drawn over the current 3D viewport.

The layout produces a display list and hit targets. Rendering and event handling
use that same layout, so fields cannot disappear through a UILayout exception.
"""
from dataclasses import dataclass
from pathlib import Path
from math import cos, sin, pi
from time import monotonic
import json
import textwrap

import bpy
import blf
import gpu
from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader

from .. import icons, utils
from ..project import GAME_INFO
from .asset_creation import MODEL_OUTPUTS, asset_folders, folder_tree
from .asset_types import OBJECT_TYPE_DESCRIPTIONS, asset_types, SUPPORTED_ASSETS

_active = set()
_fonts = {}


def window_open(window):
    try:
        return any(item == window for item in bpy.context.window_manager.windows)
    except ReferenceError:
        return False


def _watch_windows():
    for wizard in tuple(_active):
        if not window_open(wizard.window):
            wizard.close()
    return .25 if _active else None


def close_all():
    for wizard in tuple(_active):
        wizard.close()


@persistent
def _close_on_load(*args):
    close_all()
    # Blender frees loaded BLF fonts when opening a Blend. Cached IDs then
    # silently measure/draw empty text, so reload both fonts on the next wizard.
    _fonts.clear()


def register():
    if _close_on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_close_on_load)


def unregister():
    close_all()
    _fonts.clear()
    if _close_on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_close_on_load)


def font(mono=False):
    if mono not in _fonts:
        filename = 'consola.ttf' if mono else 'segoeui.ttf'
        path = Path('C:/Windows/Fonts') / filename
        try:
            loaded = blf.load(str(path)) if path.is_file() else 0
            _fonts[mono] = max(0, loaded)
        except (RuntimeError, OSError):
            _fonts[mono] = 0
    return _fonts[mono]


def color(hex_value, alpha=1):
    return tuple(int(hex_value[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (alpha,)


@dataclass
class Control:
    key: str
    kind: str
    rect: tuple
    label: str = ''
    value: object = None
    options: tuple = ()
    enabled: bool = True
    icon: str = ''
    description: str = ''

    def contains(self, x, y):
        left, top, width, height = self.rect
        return left <= x <= left + width and top <= y <= top + height


class Painter:
    def __init__(self, wizard):
        self.wizard = wizard
        self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self.image_shader = None
        self.textures = {}

    def point(self, x, y):
        w = self.wizard
        region = w.draw_region or w.region
        return (w.region.x - region.x + w.left + x * w.scale,
                w.region.y + w.region.height - region.y - w.top - y * w.scale)

    def rectangle(self, rect, fill, radius=0):
        x, y, width, height = rect
        radius = min(radius, width / 2, height / 2)
        if radius:
            points = []
            for cx, cy, start in ((x + width - radius, y + radius, -pi / 2),
                                  (x + width - radius, y + height - radius, 0),
                                  (x + radius, y + height - radius, pi / 2),
                                  (x + radius, y + radius, pi)):
                points.extend(self.point(cx + radius * cos(start + j * pi / 16),
                                         cy + radius * sin(start + j * pi / 16)) for j in range(9))
        else:
            points = [self.point(x, y), self.point(x + width, y),
                      self.point(x + width, y + height), self.point(x, y + height)]
        triangles = [(0, i, i + 1) for i in range(1, len(points) - 1)]
        batch = batch_for_shader(self.shader, 'TRIS', {'pos': points}, indices=triangles)
        self.shader.bind()
        self.shader.uniform_float('color', fill)
        gpu.state.blend_set('ALPHA')
        batch.draw(self.shader)

    def text(self, text, x, y, size, fill, mono=False):
        ident = font(mono)
        blf.size(ident, size * self.wizard.scale)
        px, py = self.point(x, y + size)
        blf.position(ident, px, py, 0)
        blf.color(ident, *fill)
        blf.draw(ident, str(text))

    def icon(self, name, x, y, size):
        if not name or name.isupper():
            return
        try:
            if name not in self.textures:
                # Copy source RGBA pixels to an independent GPU texture and
                # remove the temporary image so UI assets never enter a Blend.
                image = bpy.data.images.load(str(icons._builtin_icon_path(name)), check_existing=False)
                try:
                    width, height = image.size
                    pixels = gpu.types.Buffer('FLOAT', width * height * 4, image.pixels[:])
                    self.textures[name] = gpu.types.GPUTexture((width, height), format='RGBA32F', data=pixels)
                finally:
                    bpy.data.images.remove(image)
            if self.image_shader is None:
                self.image_shader = gpu.shader.from_builtin('IMAGE')
            batch = batch_for_shader(self.image_shader, 'TRI_FAN', {
                'pos': [self.point(x, y + size), self.point(x + size, y + size),
                        self.point(x + size, y), self.point(x, y)],
                'texCoord': [(0, 0), (1, 0), (1, 1), (0, 1)],
            })
            self.image_shader.bind()
            self.image_shader.uniform_sampler('image', self.textures[name])
            # BLF resets blending after text draws. Restore it for each icon,
            # rather than relying on the state at the start of the frame.
            gpu.state.blend_set('ALPHA')
            batch.draw(self.image_shader)
        except (RuntimeError, ValueError, AttributeError, KeyError, OSError):
            # Icons are supplementary; their loading must never hide fields.
            return

    def clip(self, rect):
        x, y, width, height = rect
        px, py = self.point(x, y + height)
        gpu.state.scissor_set(int(px), int(py), int(width * self.wizard.scale), int(height * self.wizard.scale))
        gpu.state.scissor_test_set(True)

    def draw(self, commands):
        previous_blend = gpu.state.blend_get()
        previous_scissor = gpu.state.scissor_get()
        gpu.state.blend_set('ALPHA')
        try:
            for kind, args in commands:
                if kind == 'rect':
                    self.rectangle(*args)
                elif kind == 'text':
                    self.text(*args)
                elif kind == 'icon':
                    self.icon(*args)
                elif kind == 'clip':
                    self.clip(*args)
                elif kind == 'unclip':
                    gpu.state.scissor_test_set(False)
        finally:
            gpu.state.scissor_set(*previous_scissor)
            gpu.state.scissor_test_set(False)
            gpu.state.blend_set(previous_blend)


class AssetWizard:
    TYPE_ORDER = ('model', 'scenario', 'sky', 'animation', 'decorator_set', 'cinematic')
    STEPS = ('TYPE', 'LOCATION', 'SETUP')
    TITLES = ('Asset type', 'Name & location', 'Setup & create')
    HEIGHT = 800
    TOOLTIP_DELAY = .5
    DRAW_REGIONS = ('WINDOW', 'UI', 'HEADER', 'TOOL_HEADER', 'TOOLS')

    def __init__(self, operator, context):
        self.operator = operator
        self.window = context.window
        self.area = getattr(context, 'area', None)
        if self.area is None or self.area.type != 'VIEW_3D':
            self.area = next((area for area in self.window.screen.areas if area.type == 'VIEW_3D'), None)
        self.region = next((region for region in self.area.regions if region.type == 'WINDOW'), None) if self.area else None
        self.context = context
        self.scale = max(0.75, context.preferences.system.ui_scale)
        self.left = self.top = 0
        self.width = 660
        self.height = self.HEIGHT
        self.commands = []
        self.controls = []
        self.body = (22, 170, 616, 480)
        self.scroll = 0
        self.content_height = 0
        self.focus = ''
        self.dropdown = ''
        self.dropdown_rect = None
        self.dropdown_columns = 1
        self.dropdown_scroll = 0
        self.edit_value = ''
        self.cursor = 0
        self.anchor = 0
        self.hover = ''
        self.hover_position = None
        self.hover_since = 0
        self.tooltip_rect = None
        self.handlers = {}
        self.draw_region = None
        self.drag_position = ((operator.wizard_left * self.scale, operator.wizard_top * self.scale)
                              if getattr(operator, 'wizard_moved', False) else None)
        self.drag_anchor = None
        self.timer = None
        self.closed = False
        self.painter = None
        self._feedback_key = None
        self._feedback = None
        self._error = ''
        self._warning = ''
        brightness = sum(context.preferences.themes[0].user_interface.wcol_regular.inner[:3]) / 3
        light = brightness >= .5
        choices = {
            'bg': ('f6f6f6', '303030'), 'surface': ('ffffff', '383838'),
            'header': ('e8e8e8', '272727'), 'input': ('ffffff', '232323'),
            'text': ('292929', 'eeeeee'), 'muted': ('626262', 'c2c2c2'),
            'line': ('cecece', '555555'), 'accent': ('126985', '8ad4ed'),
            'selected': ('dcedf3', '24424d'), 'button': ('197c9f', '247c9f'),
            'warning': ('805b13', 'ebc97c'), 'warning_bg': ('fff6df', '413b2c'),
            'error': ('ab3434', 'ffadad'),
        }
        self.colors = {key: color(pair[0 if light else 1]) for key, pair in choices.items()}

    def start(self, context):
        if self.area is None or self.region is None:
            self.operator.report({'ERROR'}, 'Open New Asset from a 3D viewport.')
            return {'CANCELLED'}
        # Each region is composited separately. Paint the same panel after its
        # native UI so the sidebar and Foundry Bar cannot cover the wizard.
        for region_type in self.DRAW_REGIONS:
            self.handlers[region_type] = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), region_type, 'POST_PIXEL')
        self.timer = context.window_manager.event_timer_add(.25, window=self.window)
        with context.temp_override(window=self.window, area=self.area, region=self.region):
            context.window_manager.modal_handler_add(self.operator)
        _active.add(self)
        if not bpy.app.timers.is_registered(_watch_windows):
            bpy.app.timers.register(_watch_windows, first_interval=.25)
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def close(self):
        if self.closed:
            return
        self.closed = True
        for region_type, handler in self.handlers.items():
            bpy.types.SpaceView3D.draw_handler_remove(handler, region_type)
        self.handlers.clear()
        if self.timer is not None:
            bpy.context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        if window_open(self.window):
            self.window.cursor_set('DEFAULT')
        self.dropdown = self.focus = ''
        self.clear_hover()
        self.drag_anchor = None
        self.painter = None
        _active.discard(self)
        if self.area and window_open(self.window):
            self.area.tag_redraw()

    @property
    def project(self):
        return utils.get_project(self.operator.project, use_external=False)

    def measure(self, value, size=13, mono=False):
        ident = font(mono)
        blf.size(ident, size)
        return blf.dimensions(ident, str(value))[0]

    def fit(self, value, width, size=13, mono=False):
        value = str(value)
        if self.measure(value, size, mono) <= width:
            return value
        while value and self.measure(value + '…', size, mono) > width:
            value = value[:-1]
        return value + '…'

    def rect(self, rect, fill, radius=0, border=False):
        if border:
            self.commands.append(('rect', (rect, self.colors['line'], radius)))
            x, y, w, h = rect
            rect = (x + 1, y + 1, w - 2, h - 2)
        self.commands.append(('rect', (rect, self.colors[fill] if isinstance(fill, str) else fill, radius)))

    def text(self, value, x, y, size=13, fill='text', mono=False):
        self.commands.append(('text', (str(value), x, y, size,
                                      self.colors[fill] if isinstance(fill, str) else fill, mono)))

    def wrap_lines(self, value, width, size=12, mono=False):
        # Character wrapping also breaks long paths that have no spaces.
        columns = max(8, int(width / max(1, self.measure('m' if mono else 'x', size, mono))))
        lines = textwrap.wrap(str(value), columns, replace_whitespace=False) or ['']
        while columns > 8 and any(self.measure(line, size, mono) > width for line in lines):
            columns -= 1
            lines = textwrap.wrap(str(value), columns, replace_whitespace=False) or ['']
        return lines

    def wrapped(self, value, x, y, width, size=12, fill='muted', mono=False):
        lines = self.wrap_lines(value, width, size, mono)
        for line in lines:
            self.text(self.fit(line, width, size, mono), x, y, size, fill, mono)
            y += size + 6
        return y

    def control(self, key, kind, rect, label='', value=None, options=(), enabled=True, icon='', description=''):
        control = Control(key, kind, rect, label, value, tuple(options), enabled, icon, description)
        self.controls.append(control)
        self.paint_control(control)
        return control

    def field_value(self, field):
        op = self.operator
        value = getattr(op, field)
        if field == 'directory' and self.project:
            try:
                value = str(Path(value).relative_to(Path(self.project.data_directory)))
                return '' if value == '.' else value
            except ValueError:
                pass
        return value

    def set_field(self, field, value):
        if field == 'directory' and self.project and value and not Path(value).is_absolute():
            value = str(Path(self.project.data_directory, value))
        setattr(self.operator, field, value)
        self._feedback_key = None

    def paint_control(self, control):
        key, kind, (x, y, w, h) = control.key, control.kind, control.rect
        selected = (kind in {'tile', 'step', 'radio'} and control.value
                    or kind == 'choice' and control.value == self.operator.object_type)
        focused = self.focus == key
        hovered = self.hover == key and control.enabled
        muted = 'text' if control.enabled else 'muted'
        if kind == 'step':
            self.rect((x, y + h - 2, w, 2), 'accent' if selected else 'line')
            self.rect((x + 4, y + 7, 24, 24), 'selected' if selected else 'header', 12)
            self.text(str(self.STEPS.index(key.split(':')[1]) + 1), x + 12, y + 11, 12,
                      'accent' if selected else 'muted')
            self.text(self.fit(control.label, w - 40, 12), x + 36, y + 12, 12, 'text' if selected else 'muted')
            return
        if kind in {'button', 'primary', 'tile', 'choice', 'input', 'select'}:
            fill = 'button' if kind == 'primary' and control.enabled else 'input' if kind in {'input', 'select'} else 'selected' if selected or hovered else 'surface'
            self.rect(control.rect, fill, 4, True)
            if focused or selected:
                self.rect((x, y, w, 1), 'accent')
                self.rect((x, y + h - 1, w, 1), 'accent')
            if key == 'close':
                self.text('×', x + (w - self.measure('×', 18)) / 2, y + 3, 18, muted)
                return
            if kind == 'input':
                value = self.edit_value if focused else str(self.field_value(key))
                mono = key in {'directory', 'template_tag'}
                shown = self.fit(value, w - 20, 13, mono)
                if focused:
                    start = 0
                    while self.measure(value[start:self.cursor], 13, mono) > w - 24:
                        start += 1
                    shown = self.fit(value[start:], w - 20, 13, mono)
                    lo, hi = sorted((self.cursor, self.anchor))
                    lo = max(lo, start)
                    if hi > lo:
                        offset = self.measure(value[start:lo], 13, mono)
                        length = min(w - 20 - offset, self.measure(value[lo:hi], 13, mono))
                        self.rect((x + 10 + offset, y + 8, length, h - 16), 'selected')
                    caret = self.measure(value[start:self.cursor], 13, mono)
                    self.rect((x + 10 + caret, y + 8, 1, h - 16), 'accent')
                self.text(shown, x + 10, y + (h - 16) / 2, 13, muted, mono)
                return
            if kind == 'select':
                label = next((label for value, label in control.options if value == getattr(self.operator, key)), control.label)
                tx = x + 10
                if control.icon:
                    self.commands.append(('icon', (control.icon, tx, y + (h - 22) / 2, 22)))
                    tx += 30
                self.text(self.fit(label, w - (tx - x) - 28), tx, y + (h - 16) / 2, 13, muted)
                self.text('⌄', x + w - 22, y + 7, 16, 'muted')
                return
            if kind == 'choice':
                padding = 10 if w >= 140 else 6
                icon_size = 23 if w >= 140 else 18
                tx = x + padding + icon_size + 6
                text_width = w - (tx - x) - padding
                size = 13
                words = control.label.split()
                while size > 9 and (max(self.measure(word, size) for word in words) > text_width
                                   or 2 * size + 3 > h - 4):
                    size -= 1
                lines = [control.label] if self.measure(control.label, size) <= text_width else words
                text_height = len(lines) * (size + 3) - 3
                self.commands.append(('icon', (control.icon, x + padding, y + (h - icon_size) / 2, icon_size)))
                for index, line in enumerate(lines):
                    self.text(line, tx, y + (h - text_height) / 2 + index * (size + 3), size,
                              'accent' if selected else muted)
                return
            tx = x + 12
            if kind == 'tile':
                asset = next(asset for asset in asset_types if asset.internal_name == key.split(':')[1])
                self.commands.append(('icon', (asset.icon_name, x + 11, y + (h - 23) / 2, 23)))
                tx += 31
            else:
                tx = x + max(10, (w - self.measure(control.label)) / 2)
            fill = color('ffffff') if kind == 'primary' and control.enabled else 'accent' if selected else muted
            self.text(self.fit(control.label, w - (tx - x) - 10), tx, y + (h - 16) / 2, 13, fill)
            return
        if kind in {'check', 'radio'}:
            checked = bool(getattr(self.operator, key)) if kind == 'check' else bool(control.value)
            self.rect((x, y + 4, 16, 16), 'button' if checked else 'input', 8 if kind == 'radio' else 3, True)
            if checked:
                if kind == 'radio':
                    self.rect((x + 6, y + 10, 4, 4), color('ffffff'), 2)
                else:
                    self.text('✓', x + 3, y + 2, 13, color('ffffff'))
            self.text(control.label, x + 26, y + 2, 13, muted)
            return
        if kind == 'disclosure':
            self.text(('▾' if self.operator.show_advanced_options else '▸') + '  ' + control.label, x, y + 4, 13, 'muted')

    def field(self, label, field, y, options=None, icon='', description=''):
        self.text(label, 22, y)
        self.control(field, 'select' if options is not None else 'input',
                     (22, y + 23, self.width - 44, 36), label, options=options or (), icon=icon,
                     description=description)
        return y + 78

    def feedback(self):
        op = self.operator
        key = (op.project, op.asset_type, op.filename, op.directory,
               op.save_new_blend_file, op.reuse_existing_folder, op.source_mode, op.wizard_step,
               op.template_project, op.template_tag, op.object_type,
               tuple(getattr(op, 'output_' + name) for name in MODEL_OUTPUTS),
               len(self.context.selected_objects))
        if key != self._feedback_key:
            self._feedback_key = key
            project = self.project
            self._error = op.creation_error(self.context, project, validate_template=op.wizard_step == 'SETUP')
            self._feedback = op.location_feedback(project) if project else ('Choose a project.', '', '')
            self._warning = op.overwrite_warning(project) if not self._error else ''
        return self._error, self._feedback

    def type_content(self, y):
        op, project = self.operator, self.project
        projects = [(item.project_id, item.name + ' · ' + GAME_INFO.get(item.game, ('', item.game))[1])
                    for item in utils.get_prefs().projects]
        y = self.field('Project', 'project', y, projects)
        if not project:
            return self.wrapped('Choose an available Foundry project.', 22, y, self.width - 44, fill='error')
        supported = SUPPORTED_ASSETS.get(project.game, set())
        order = {name: index for index, name in enumerate(self.TYPE_ORDER)}
        choices = sorted((asset for asset in asset_types if asset.internal_name in supported),
                         key=lambda asset: order.get(asset.internal_name, len(order)))
        self.text('Asset type', 22, y)
        y += 23
        columns = 3 if self.width >= 520 else 2
        width = (self.width - 44 - 8 * (columns - 1)) / columns
        for index, asset in enumerate(choices):
            self.control('type:' + asset.internal_name, 'tile',
                         (22 + index % columns * (width + 8), y + index // columns * 60, width, 52),
                         asset.display_name, op.asset_type == asset.internal_name, description=asset.description)
        y += ((len(choices) + columns - 1) // columns) * 60 + 10
        if op.asset_type == 'model':
            options = [(item[0], item[1]) for item in op.object_type_items(self.context)]
            y = self.field('Object type', 'object_type', y, options,
                           icon='tags' if op.object_type == 'custom' else op.object_type,
                           description=OBJECT_TYPE_DESCRIPTIONS.get(op.object_type, ''))
            y = self.wrapped('Sets the default output tag. Additional outputs are available in Optional setup.',
                             22, y - 10, self.width - 44)
        return y + 12

    def location_content(self, y):
        op = self.operator
        y = self.field('Asset name', 'filename', y)
        y = self.wrapped('One name for the asset folder and its files. No extension.', 22, y - 12, self.width - 44) + 16
        self.text('Create in · parent folder', 22, y)
        y += 23
        self.rect((22, y, 54, 36), 'header', 4, True)
        self.text('data\\', 32, y + 10, 12, 'muted', True)
        self.control('directory', 'input', (84, y, self.width - 22 - 84 - 86, 36))
        self.control('browse', 'button', (self.width - 100, y, 78, 36), 'Browse…')
        y = self.wrapped('Choose the parent folder. Foundry creates the asset folder inside it.',
                         22, y + 44, self.width - 44) + 12
        self.control('save_new_blend_file', 'check', (22, y, self.width - 44, 28), 'Save Blend file in the asset folder')
        return self.preview(y + 40)

    def setup_content(self, y):
        op = self.operator
        self.text('Start with', 22, y)
        y += 25
        sources = [('CURRENT', 'Current scene', 'Use the current scene as this asset.'),
                   ('SELECTED', 'Selected objects', 'Copy selected objects into a separate asset scene.'),
                   ('EMPTY', 'Empty scene', 'Start with a clean asset scene.'),
                   ('TAG', 'Existing asset tag', 'Import a tag into a clean asset scene. Choose its source project.')]
        for value, label, help_text in sources:
            if value == 'TAG':
                projects = [(item.project_id, item.name + ' · ' + GAME_INFO.get(item.game, ('', item.game))[1])
                            for item in utils.get_prefs().projects]
                split = 22 + (self.width - 44) * .48
                self.control('source:TAG', 'radio', (22, y + 5, split - 30, 26), label, op.source_mode == value)
                self.control('template_project', 'select', (split, y, self.width - 22 - split, 36),
                             'Source project', options=projects, enabled=op.source_mode == 'TAG')
                y = self.wrapped(help_text, 48, y + 42, self.width - 70) + 13
            else:
                self.control('source:' + value, 'radio', (22, y, self.width - 44, 26), label, op.source_mode == value)
                y = self.wrapped(help_text, 48, y + 26, self.width - 70) + 13
        if op.source_mode == 'TAG':
            self.text('Asset tag', 22, y)
            y += 23
            self.control('template_tag', 'input', (22, y, self.width - 218, 36))
            enabled = bool(op.template_extensions())
            self.control('template_browse', 'button', (self.width - 188, y, 78, 36), 'Browse…', enabled=enabled)
            self.control('template_search', 'button', (self.width - 100, y, 78, 36), 'Search…', enabled=enabled)
            extensions = ', '.join(op.template_extensions()) or 'No matching tag type for this source project.'
            y = self.wrapped('Allowed tags: ' + extensions, 22, y + 45, self.width - 44) + 13
            if op.template_project != op.project:
                y = self.wrapped('Animation and material conversion will be enabled for the destination project.',
                                 22, y, self.width - 44) + 13
        self.control('save_new_blend_file', 'check', (22, y, self.width - 44, 28), 'Save Blend file in the asset folder')
        y += 40
        if op.asset_type == 'scenario':
            y = self.field('Scenario type', 'scenario_type', y,
                           [('solo', 'Singleplayer'), ('multiplayer', 'Multiplayer'), ('main menu', 'Main Menu')])
            self.control('scenario_auto_bsp_by_origin', 'check', (22, y, self.width - 44, 28), 'Create BSPs by origin')
            y += 40
        elif op.asset_type == 'animation':
            y = self.field('Animation graph type', 'animation_type', y,
                           [('standalone', 'Standalone'), ('first_person', 'First person')])
        elif op.asset_type == 'particle_model':
            self.control('particle_uses_custom_points', 'check', (22, y, self.width - 44, 28), 'Use a custom emitter shape')
            y += 40
        self.control('advanced', 'disclosure', (22, y, self.width - 44, 28), 'Optional setup')
        y += 38
        if op.show_advanced_options:
            if op.asset_type == 'model' and op.source_mode != 'TAG':
                self.control('generate_halo_skeleton', 'check', (22, y, self.width - 44, 28), 'Generate Halo armature')
                y += 34
            for key, label in [('append_special_materials', 'Add special materials'), ('append_grid_materials', 'Add grid materials')]:
                self.control(key, 'check', (22, y, self.width - 44, 28), label)
                y += 34
            y = self.field('Scene scale', 'scale', y, [('blender', 'Blender · 1 unit = 1 meter'), ('max', 'Halo · 1 unit = 0.03048 meters')])
            y = self.field('Forward axis', 'forward_direction', y, [('x', '+X'), ('x-', '−X'), ('y', '+Y'), ('y-', '−Y')])
            if op.asset_type == 'model':
                self.text('Output tags', 22, y)
                y += 25
                available = [(item[0], item[1]) for item in op.object_type_items(self.context) if item[0] != 'custom']
                columns = 3 if self.width >= 560 else 2
                width = (self.width - 44) / columns
                for index, (value, label) in enumerate(available):
                    self.control('output_' + value, 'check',
                                 (22 + index % columns * width, y + index // columns * 30, width, 28), label)
                y += ((len(available) + columns - 1) // columns) * 30 + 16
        project = self.project
        if project:
            name = next((asset.display_name for asset in asset_types if asset.internal_name == op.asset_type), '')
            y = self.wrapped(project.name + ' · ' + name, 22, y, self.width - 44) + 12
        return self.preview(y)

    def preview(self, y):
        op, project = self.operator, self.project
        if not project:
            return y
        error, (message, action, value) = self.feedback()
        if error:
            top = y
            commands_at = len(self.commands)
            y = self.wrapped(error, 34, y + 10, self.width - 68, fill='warning') + 10
            if action:
                labels = {'NAME': 'Use ' + value, 'REUSE': 'Use ' + Path(value).name + ' as asset folder',
                          'SIBLING': 'Create alongside the existing asset'}
                self.control('repair:' + action, 'button', (34, y, self.width - 68, 34), labels[action], value)
                y += 42
            self.commands.insert(commands_at, ('rect', ((22, top, self.width - 44, y - top + 2), self.colors['warning_bg'], 4)))
            return y + 12
        if self._warning:
            top = y
            commands_at = len(self.commands)
            y = self.wrapped(self._warning, 34, y + 10, self.width - 68, fill='warning') + 10
            self.commands.insert(commands_at, ('rect', ((22, top, self.width - 44, y - top + 2), self.colors['warning_bg'], 4)))
            y += 12
        name, destination = op.asset_location(project)
        start = y
        commands_at = len(self.commands)
        y += 14
        self.text('Folder and files to create', 36, y)
        relative = destination.relative_to(Path(project.data_directory).resolve())
        y = self.wrapped('data\\' + str(relative) + '\\', 36, y + 27,
                         self.width - 72, 12, 'muted', True) + 8
        if op.save_new_blend_file:
            self.text(name + '.blend', 52, y, 12, 'text', True)
            y += 22
        if project.game in {'reach', 'halo4', 'halo2a'}:
            self.text(name + '.sidecar.xml', 52, y, 12, 'text', True)
            y += 27
        for depth, label in folder_tree(asset_folders(project.game, op.asset_type)):
            if depth:
                continue
            self.text(label + '\\', 52, y, 12, 'accent', True)
            y += 22
        if not op.save_new_blend_file:
            y += 10
            label = 'Blend stays at: ' + bpy.data.filepath if bpy.data.filepath else 'The current Blend remains unsaved.'
            y = self.wrapped(label, 36, y, self.width - 72, 12, 'muted', True)
            self.text('The Blend file is not saved or relocated.', 36, y + 2, 12, 'muted')
            y += 28
        y += 10
        self.commands.insert(commands_at, ('rect', ((22, start, self.width - 44, y - start), self.colors['line'], 4)))
        self.commands.insert(commands_at + 1, ('rect', ((23, start + 1, self.width - 46, y - start - 2), self.colors['surface'], 3)))
        if project.game == 'halo2' and op.asset_type in {'particle_model', 'decorator_set'}:
            y = self.wrapped('Per-model render folders are created on export when the model names are known.',
                             22, y + 10, self.width - 44)
        if op.asset_type != 'resource':
            y = self.wrapped('Game files are built later when you Export.', 22, y + 10, self.width - 44)
        else:
            y = self.wrapped('Resource assets do not export.', 22, y + 10, self.width - 44)
        return y + 16

    def build(self, width=660, height=HEIGHT):
        self.width = max(320, min(660, width))
        self.height = max(340, min(self.HEIGHT, height))
        self.commands = []
        self.controls = []
        self.dropdown_rect = None
        self.dropdown_columns = 1
        self.tooltip_rect = None
        op = self.operator
        self.rect((4, 7, self.width, self.height), color('000000', .24), 8)
        self.rect((0, 0, self.width, self.height), 'bg', 7, True)
        self.rect((1, 1, self.width - 2, 44), 'header', 6)
        self.commands.append(('icon', ('halo_asset', 18, 13, 20)))
        self.text('Foundry · New Asset', 48, 14, 13)
        self.control('close', 'button', (self.width - 42, 9, 28, 28), '×')
        index = self.STEPS.index(op.wizard_step)
        title = self.TITLES[index]
        descriptions = ('Choose what kind of asset you want to create',
                        'Where this asset exists in your tags and data directories',
                        'Choose your starting scene, or import from an existing tag')
        self.text(title, 22, 65, 20)
        self.text(self.fit(descriptions[index], self.width - 44), 22, 96, 13, 'muted')
        step_width = (self.width - 44) / 3
        for i, value in enumerate(self.STEPS):
            self.control('step:' + value, 'step', (22 + i * step_width, 127, step_width, 43),
                         self.TITLES[i], value == op.wizard_step)
        body_top = 188
        self.body = (0, body_top - 4, self.width, self.height - body_top - 74)
        self.commands.append(('clip', (self.body,)))
        y = body_top - self.scroll
        if op.wizard_step == 'TYPE':
            y = self.type_content(y)
        elif op.wizard_step == 'LOCATION':
            y = self.location_content(y)
        else:
            y = self.setup_content(y)
        self.content_height = y + self.scroll - body_top
        self.commands.append(('unclip', ()))
        if self.content_height > self.body[3]:
            maximum = max(0, self.content_height - self.body[3])
            self.scroll = min(self.scroll, maximum)
            ratio = self.body[3] / self.content_height
            self.rect((self.width - 7, self.body[1], 3, self.body[3]), 'header', 2)
            self.rect((self.width - 7, self.body[1] + self.scroll * ratio, 3, self.body[3] * ratio), 'line', 2)
        else:
            self.scroll = 0
        footer_y = self.height - 64
        self.rect((1, footer_y, self.width - 2, 63), 'header')
        self.rect((1, footer_y, self.width - 2, 1), 'line')
        if self.width >= 600:
            self.text('Asset Creation Wizard', 22, footer_y + 24, 12, 'muted')
        main_width = 110 if index == 2 else 83
        main_x = self.width - 22 - main_width
        self.control('cancel', 'button', (main_x - 160, footer_y + 14, 72, 36), 'Cancel')
        if index:
            self.control('back', 'button', (main_x - 80, footer_y + 14, 72, 36), 'Back')
        enabled = bool(self.project) if index == 0 else not self.feedback()[0]
        self.control('create' if index == 2 else 'next', 'primary',
                     (main_x, footer_y + 14, main_width, 36),
                     'Create Asset' if index == 2 else 'Next', enabled=enabled)
        if self.dropdown:
            self.dropdown_content()
        self.tooltip_content()
        return self.commands

    def dropdown_content(self):
        control = next((item for item in self.controls if item.key == self.dropdown), None)
        if control is None:
            self.dropdown = ''
            return
        x, y, width, height = control.rect
        if control.key == 'object_type':
            self.object_type_choices(control)
            return
        row_height = 34
        count = min(7, len(control.options))
        popup_height = count * row_height + 8
        top = y + height + 4
        if top + popup_height > self.height - 10:
            top = max(10, y - popup_height - 4)
        self.dropdown_rect = (x, top, width, popup_height)
        self.dropdown_scroll = min(self.dropdown_scroll, max(0, len(control.options) - count))
        self.rect((x + 3, top + 4, width, popup_height), color('000000', .3), 4)
        self.rect((x, top, width, popup_height), 'surface', 4, True)
        for index, (value, label) in enumerate(control.options[self.dropdown_scroll:self.dropdown_scroll + count]):
            rect = (x + 4, top + 4 + index * row_height, width - 8, row_height)
            self.control('option:' + control.key + ':' + str(value), 'button', rect, label, value)
        if len(control.options) > count:
            self.text('↕', x + width - 20, top + popup_height - 23, 12, 'muted')

    def object_type_choices(self, control):
        x, y, width, height = control.rect
        columns = 3
        rows = (len(control.options) + columns - 1) // columns
        above, below = y - 14, self.height - 10 - (y + height + 4)
        available = max(above, below)
        padding, gap = 8, 8
        row_height = min(46, int((available - 2 * padding - (rows - 1) * gap) / rows))
        if row_height < 34:
            padding, gap = 6, 4
            row_height = min(46, int((available - 2 * padding - (rows - 1) * gap) / rows))
        row_height = max(28, row_height)
        popup_height = rows * row_height + (rows - 1) * gap + 2 * padding
        top = y + height + 4 if below >= popup_height else max(10, y - popup_height - 4)
        self.dropdown_rect = (x, top, width, popup_height)
        self.dropdown_columns = columns
        self.rect((x + 3, top + 4, width, popup_height), color('000000', .3), 4)
        self.rect(self.dropdown_rect, 'surface', 4, True)
        button_width = (width - 2 * padding - (columns - 1) * gap) / columns
        for index, (value, label) in enumerate(control.options):
            rect = (x + padding + index % columns * (button_width + gap),
                    top + padding + index // columns * (row_height + gap), button_width, row_height)
            self.control('option:object_type:' + value, 'choice', rect, label, value,
                         icon='tags' if value == 'custom' else value,
                         description=OBJECT_TYPE_DESCRIPTIONS.get(value, ''))

    def clear_hover(self):
        self.hover = ''
        self.hover_position = None
        self.hover_since = 0
        self.tooltip_rect = None

    def update_hover(self, x, y):
        control = self.hit_control(x, y)
        key = control.key if control else ''
        if key != self.hover or (x, y) != self.hover_position:
            self.hover_since = monotonic()
        self.hover = key
        self.hover_position = (x, y)
        return control

    def tooltip_content(self):
        if self.hover_position is None or monotonic() - self.hover_since < self.TOOLTIP_DELAY:
            return
        control = self.hit_control(*self.hover_position)
        if not control or control.key != self.hover or not control.enabled or not control.description:
            return
        title = control.label
        if control.key == 'object_type':
            title = next((label for value, label in control.options if value == self.operator.object_type), title)
        width = min(380, self.width - 24)
        size = 12
        description = ' '.join(control.description.split())
        lines = self.wrap_lines(description, width - 24, size)
        height = 46 + len(lines) * (size + 6)
        while height > self.height - 24 and size > 10:
            size -= 1
            lines = self.wrap_lines(description, width - 24, size)
            height = 46 + len(lines) * (size + 6)
        mouse_x, mouse_y = self.hover_position
        x = max(12, min(self.width - width - 12, mouse_x + 12))
        y = mouse_y + 22
        if y + height > self.height - 12:
            y = mouse_y - height - 12
        y = max(12, min(self.height - height - 12, y))
        self.tooltip_rect = (x, y, width, height)
        # Tooltips are painted last, outside the body clip and above choosers.
        # They add no hit target, so hovering never changes button behavior.
        self.rect((x + 3, y + 4, width, height), color('000000', .3), 4)
        self.rect(self.tooltip_rect, 'header', 4, True)
        self.text(self.fit(title, width - 24), x + 12, y + 10, 13, 'accent')
        for index, line in enumerate(lines):
            self.text(line, x + 12, y + 34 + index * (size + 6), size)

    def popup_contains(self, x, y):
        if not self.dropdown or self.dropdown_rect is None:
            return False
        left, top, width, height = self.dropdown_rect
        return left <= x <= left + width and top <= y <= top + height

    def hit_control(self, x, y):
        inside_popup = self.popup_contains(x, y)
        return next((item for item in reversed(tuple(self.visible_controls())) if item.contains(x, y)
                     and (not inside_popup or item.key.startswith('option:'))), None)

    def viewport_insets(self):
        # Open below the headers, while allowing a dragged panel to cover them.
        top = bottom = 0
        viewport_top = self.region.y + self.region.height
        for region in self.area.regions:
            if region.type not in {'HEADER', 'TOOL_HEADER'} or region.height <= 1:
                continue
            if region.alignment == 'TOP':
                top = max(top, viewport_top - region.y)
            elif region.alignment == 'BOTTOM':
                bottom = max(bottom, region.y + region.height - self.region.y)
        padding = 12 * self.scale
        return top + padding, bottom + padding

    def position(self):
        top, bottom = self.viewport_insets()
        available_height = (self.region.height - top - bottom) / self.scale
        # Keep the panel and progress bar anchored when changing steps.
        height = min(self.HEIGHT, available_height)
        width = self.region.width / self.scale - 24
        if self.drag_position is None:
            self.left = max(8, (self.region.width - min(660, width) * self.scale) / 2)
            self.top = top + max(0, (available_height - height) * self.scale / 2)
        else:
            # Clamp to the whole editor, including its sidebar and headers.
            region_x, region_y = getattr(self.region, 'x', 0), getattr(self.region, 'y', 0)
            area_width = getattr(self.area, 'width', self.region.width)
            area_height = getattr(self.area, 'height', self.region.height)
            margin = 8 * self.scale
            minimum_x = getattr(self.area, 'x', region_x) - region_x + margin
            minimum_y = region_y + self.region.height - getattr(self.area, 'y', region_y) - area_height + margin
            maximum_x = max(minimum_x, minimum_x + area_width - 2 * margin - min(660, width) * self.scale)
            maximum_y = max(minimum_y, minimum_y + area_height - 2 * margin - height * self.scale)
            self.left = max(minimum_x, min(maximum_x, self.drag_position[0]))
            self.top = max(minimum_y, min(maximum_y, self.drag_position[1]))
            self.remember_position((self.left, self.top))
        return width, height

    def remember_position(self, position):
        self.drag_position = position
        self.operator.wizard_moved = position is not None
        self.operator.wizard_left = position[0] / self.scale if position else 0
        self.operator.wizard_top = position[1] / self.scale if position else 0

    def title_contains(self, x, y):
        return 0 <= x < self.width - 44 and 0 <= y <= 45

    def move(self, event):
        mouse_x, mouse_y, left, top, _ = self.drag_anchor
        self.drag_position = (left + event.mouse_x - mouse_x, top - event.mouse_y + mouse_y)
        self.position()

    def draw(self):
        region = bpy.context.region
        if (self.closed or bpy.context.window != self.window or bpy.context.area != self.area
                or region is None or region.type not in self.DRAW_REGIONS or region.width <= 1 or region.height <= 1):
            return
        if self.region.width < 100 or self.region.height < 100:
            return
        width, height = self.position()
        if self.painter is None:
            self.painter = Painter(self)
        self.build(width, height)
        self.commands.insert(0, ('rect', ((-self.left / self.scale, -self.top / self.scale,
            self.region.width / self.scale, self.region.height / self.scale),
            color('000000', .2), 0)))
        self.draw_region = region
        try:
            self.painter.draw(self.commands)
        finally:
            self.draw_region = None

    def coordinates(self, event):
        return ((event.mouse_x - self.region.x - self.left) / self.scale,
                (self.region.height - (event.mouse_y - self.region.y) - self.top) / self.scale)

    def visible_controls(self):
        top, bottom = self.body[1], self.body[1] + self.body[3]
        for control in self.controls:
            y, height = control.rect[1], control.rect[3]
            if control.key.startswith('option:'):
                if self.dropdown == control.key.split(':', 2)[1]:
                    yield control
            elif control.kind == 'step' or control.key in {'close', 'cancel', 'next', 'back', 'create'} or top <= y < bottom and y + height <= bottom + 1:
                yield control

    def focus_input(self, control):
        self.focus = control.key
        self.edit_value = str(self.field_value(control.key))
        self.cursor = self.anchor = len(self.edit_value)

    def edit(self, event):
        key = self.focus
        lo, hi = sorted((self.cursor, self.anchor))
        if event.ctrl and event.type == 'A':
            self.anchor, self.cursor = 0, len(self.edit_value)
            return True
        if event.ctrl and event.type in {'C', 'X'}:
            self.context.window_manager.clipboard = self.edit_value[lo:hi]
            if event.type == 'C':
                return True
            inserted = ''
        elif event.ctrl and event.type == 'V':
            inserted = self.context.window_manager.clipboard.replace('\r', '').replace('\n', '')
        elif event.type in {'LEFT_ARROW', 'RIGHT_ARROW', 'HOME', 'END'}:
            position = max(0, self.cursor - 1) if event.type == 'LEFT_ARROW' else min(len(self.edit_value), self.cursor + 1) if event.type == 'RIGHT_ARROW' else 0 if event.type == 'HOME' else len(self.edit_value)
            self.cursor = position
            if not event.shift:
                self.anchor = position
            return True
        elif event.type == 'BACK_SPACE':
            if lo == hi:
                lo = max(0, lo - 1)
            inserted = ''
        elif event.type == 'DEL':
            if lo == hi:
                hi = min(len(self.edit_value), hi + 1)
            inserted = ''
        elif event.unicode and not event.ctrl and not event.alt:
            inserted = event.unicode
        else:
            return False
        self.edit_value = self.edit_value[:lo] + inserted + self.edit_value[hi:]
        self.cursor = self.anchor = lo + len(inserted)
        self.set_field(key, self.edit_value)
        return True

    def activate(self, control):
        self.clear_hover()
        op = self.operator
        key = control.key
        if not control.enabled:
            return None
        if key in {'cancel', 'close'}:
            self.close()
            return {'CANCELLED'}
        if control.kind == 'input':
            self.dropdown = ''
            self.focus_input(control)
            return None
        self.focus = key
        if control.kind == 'select':
            self.dropdown = '' if self.dropdown == key else key
            self.dropdown_scroll = 0
        elif key.startswith('option:'):
            field = key.split(':', 2)[1]
            self.set_field(field, control.value)
            self.dropdown = ''
        elif key.startswith('step:'):
            op.wizard_step = key.split(':')[1]
            self.scroll = 0
            self.dropdown = ''
        elif key.startswith('type:'):
            self.set_field('asset_type', key.split(':')[1])
        elif key.startswith('source:'):
            self.set_field('source_mode', key.split(':')[1])
        elif control.kind == 'check':
            self.set_field(key, not getattr(op, key))
        elif key == 'advanced':
            op.show_advanced_options = not op.show_advanced_options
        elif key in {'next', 'back'}:
            index = self.STEPS.index(op.wizard_step)
            op.wizard_step = self.STEPS[index + (1 if key == 'next' else -1)]
            self.scroll = 0
        elif key.startswith('repair:'):
            action = key.split(':')[1]
            if action == 'NAME':
                op.filename = control.value
            elif action == 'REUSE':
                op.directory = str(Path(control.value).parent)
                op.reuse_existing_folder = True
            else:
                op.directory = control.value
                op.reuse_existing_folder = False
            self._feedback_key = None
        elif key in {'browse', 'template_browse', 'template_search'}:
            from .asset_creator import _wizard_settings
            settings = json.dumps(_wizard_settings(op))
            # Search popups do not call Operator.cancel on Escape. Keep the
            # wizard alive underneath the popup; its execute updates this UI.
            if key != 'template_search':
                self.close()
            with bpy.context.temp_override(window=self.window, area=self.area, region=self.region):
                picker = {'browse': bpy.ops.nwo.asset_wizard_browse,
                          'template_browse': bpy.ops.nwo.asset_wizard_tag_browse,
                          'template_search': bpy.ops.nwo.asset_wizard_tag_search}[key]
                picker('INVOKE_DEFAULT', wizard_settings=settings)
            return None if key == 'template_search' else {'FINISHED'}
        elif key == 'create':
            if self.feedback()[0]:
                return None
            try:
                with bpy.context.temp_override(window=self.window, area=self.area, region=self.region):
                    result = op.execute(bpy.context)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                op.report({'ERROR'}, f'Could not create asset: {exc}')
                self._feedback_key = None
                return None
            if 'FINISHED' in result:
                self.close()
                return {'FINISHED'}
        return None

    def modal(self, context, event):
        if self.closed:
            return {'CANCELLED'}
        if not window_open(self.window):
            self.close()
            return {'CANCELLED'}
        if self.area.type != 'VIEW_3D':
            self.close()
            return {'CANCELLED'}
        top, bottom = self.viewport_insets()
        if self.region.width / self.scale < 344 or (self.region.height - top - bottom) / self.scale < 340:
            self.close()
            self.operator.report({'WARNING'}, 'Enlarge the viewport and reopen New Asset.')
            return {'CANCELLED'}
        self.context = context
        if event.type == 'TIMER':
            self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if self.drag_anchor is not None:
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                self.move(event)
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.move(event)
                self.drag_anchor = None
                self.window.cursor_set('DEFAULT')
            elif event.type == 'ESC' and event.value == 'PRESS':
                self.remember_position(self.drag_anchor[4])
                self.drag_anchor = None
                self.position()
                self.window.cursor_set('DEFAULT')
            elif event.type == 'WINDOW_DEACTIVATE':
                self.drag_anchor = None
                self.window.cursor_set('DEFAULT')
            self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        x, y = self.coordinates(event)
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            control = self.update_hover(x, y)
            self.window.cursor_set('TEXT' if control and control.kind == 'input' else
                                   'SCROLL_XY' if self.title_contains(x, y) else 'DEFAULT')
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self.clear_hover()
            direction = -1 if event.type == 'WHEELUPMOUSE' else 1
            if self.dropdown == 'object_type':
                pass  # Every object-type choice is visible; keep the popup fixed.
            elif self.dropdown:
                self.dropdown_scroll = max(0, self.dropdown_scroll + direction)
            else:
                self.scroll = max(0, min(max(0, self.content_height - self.body[3]), self.scroll + direction * 36))
        elif event.type == 'WINDOW_DEACTIVATE':
            self.clear_hover()
        elif event.value == 'PRESS':
            self.clear_hover()
            if event.type == 'ESC':
                if self.dropdown or self.focus:
                    self.dropdown = self.focus = ''
                else:
                    self.close()
                    return {'CANCELLED'}
            elif self.dropdown and event.type in {'UP_ARROW', 'DOWN_ARROW', 'LEFT_ARROW', 'RIGHT_ARROW'}:
                options = [item for item in self.controls if item.key.startswith('option:')]
                keys = [item.key for item in options]
                if keys:
                    current = keys.index(self.focus) if self.focus in keys else -1
                    if current == -1 and self.dropdown == 'object_type':
                        current = next((index for index, item in enumerate(options)
                                        if item.value == self.operator.object_type), -1)
                    direction = 1 if event.type in {'DOWN_ARROW', 'RIGHT_ARROW'} else -1
                    stride = self.dropdown_columns if event.type in {'UP_ARROW', 'DOWN_ARROW'} else 1
                    self.focus = keys[(current + direction * stride) % len(keys)]
            elif event.type == 'LEFTMOUSE':
                control = self.hit_control(x, y)
                # Let the open enum bar toggle its own list in activate().
                if self.dropdown and not self.popup_contains(x, y) and (control is None or
                        not control.key.startswith('option:') and control.key != self.dropdown):
                    self.dropdown = ''
                if control:
                    result = self.activate(control)
                    if result:
                        return result
                elif self.title_contains(x, y):
                    self.drag_anchor = (event.mouse_x, event.mouse_y, self.left, self.top, self.drag_position)
                    self.dropdown = self.focus = self.hover = ''
                    self.window.cursor_set('SCROLL_XY')
            elif event.type == 'TAB':
                if self.dropdown == 'object_type':
                    controls = [item for item in self.visible_controls() if item.kind == 'choice']
                else:
                    controls = [item for item in self.visible_controls()
                                if item.kind in {'input', 'select', 'button', 'primary', 'check'}
                                and item.enabled and not item.key.startswith('option:')]
                keys = [item.key for item in controls]
                if keys:
                    index = keys.index(self.focus) if self.focus in keys else (-1 if not event.shift else 0)
                    control = controls[(index + (-1 if event.shift else 1)) % len(controls)]
                    self.focus = control.key
                    if control.kind == 'input':
                        self.focus_input(control)
            elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and not (self.focus in {'filename', 'directory', 'template_tag'} and event.type == 'SPACE'):
                control = next((item for item in self.controls if item.key == self.focus), None)
                if control is None or control.kind == 'input':
                    control = next((item for item in self.controls if item.key in {'next', 'create'}), None)
                if control:
                    result = self.activate(control)
                    if result:
                        return result
            elif self.focus in {'filename', 'directory'}:
                self.edit(event)
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}
