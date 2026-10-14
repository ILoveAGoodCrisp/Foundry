# New Asset UI and the separate viewport window experiment

New Asset uses the custom GPU/BLF wizard over the current 3D viewport. It opens below the headers and Foundry Bar. Drag the title ribbon to move it anywhere inside the viewport editor, including over the Foundry sidebar and bar; the close button remains clickable. The position stays fixed between steps and survives folder/tag browsing. Escape during a drag restores the previous position. Resizing keeps the panel within the editor, shrinking its height and scrolling its content when necessary. The `Use New Asset Editor Wizard` preference selects this UI or the original file browser operator.

Blender composites each editor region separately, so a `WINDOW` draw handler alone sits behind overlapping UI. The wizard registers `POST_PIXEL` handlers for `WINDOW`, `UI`, `HEADER`, `TOOL_HEADER`, and `TOOLS`. Each paints the same display list in its own local pixel coordinates, translated from the source viewport region. Modal hit targets use window coordinates, so controls work across region boundaries. All handlers are removed on close, file load, and add-on shutdown. No sidebar/header visibility settings are changed or saved in the Blend file.

Opening a Blend resets Blender's loaded BLF fonts. The file-load handler also clears the wizard's cached font IDs so copying an opened asset reloads its labels and path font instead of drawing empty controls.

The asset type step shows all supported asset types as buttons. The Object type field opens a complete grid of icon buttons filtered for the selected game, with every choice visible without scrolling. The grid adjusts its button height and wraps labels in smaller layouts. The selected icon also appears in the field. Clicking the field again or pressing Escape closes the chooser; arrow keys and Tab navigate its buttons. Selecting a button updates the output tags and suggested destination through the existing operator callbacks.

Hovering an asset type button, an object type button, or the selected Object type field for half a second shows its description. Tooltips wrap within the wizard and draw above the chooser without adding hit targets. Moving the mouse, clicking, scrolling, or leaving the window dismisses them. Asset descriptions are shared with the asset menu; object descriptions are shared with the operator's enum.

Projects have a **Default Asset Folder**, relative to `data`. It prefixes suggested wizard locations: `crisp` plus a scenery model gives `data/crisp/objects/scenery`. New and older configurations without the setting default to the Windows profile folder name, falling back to the platform account name or blank when unavailable. An explicitly empty value stays empty. This setting is stored per project configuration and survives project editing, duplication, and folder/image browsing. Explicit wizard destinations are preserved; remembered destinations are scoped to the configured prefix so changing it applies the new default.

Existing asset folders show an overwrite warning while retaining the destination preview and allowing Next/Create. Creation replaces matching asset metadata and saves over the matching Blend file when saving is enabled; other files and folders are retained. Keeping the Blend in its current location still skips all Blend saves, including an existing Blend in the destination. Selecting an existing asset root offers the folder-reuse action so creation does not introduce another nested asset folder. Invalid paths and creating a different asset inside another asset remain blocking errors.

## Starting from an existing tag

The fourth starting option creates a clean asset scene and then opens `nwo.import_from_drop` for the selected tag. The source project defaults to the destination project. Both the file browser and searchable popup filter by asset type and model object type, using the source game's tag names. Paths are validated beneath that project's tags folder before any asset files are created. A custom model output selection permits only its enabled object tag classes; a model with no object outputs uses the model tag itself.

The import dialog explicitly uses the Default preset and enables collision, physics, and animation import. Material and animation conversion are enabled when the source and destination project IDs differ. Import source context uses the selected registered project, while the new scene keeps its destination project. Search stays above the existing wizard because Blender's search popup does not call the operator's cancel hook when dismissed with Escape. The file browser closes the wizard and restores its serialized settings on selection or cancellation.

Wizard imports disable mouse placement. Only object, prefab, and decorator drops into an existing scenario asset read the viewport mouse position; regular imports do not calculate a mouse transform.

## Separate Blender viewport window: retained for future work

The separate viewport window experiment worked on Blender 5.1.2. It is useful for a future tool that needs a dedicated Blender editor, but it is a Blender child window rather than a standalone application window. It is not active for New Asset.

To create one, keep the source window, area, and `WINDOW` region, then duplicate the area with an **invoke** call (the operator has no execute callback):

```python
previous = {window.as_pointer() for window in context.window_manager.windows}
with context.temp_override(window=source_window, area=source_area, region=source_region):
    bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
editor_window = next(window for window in context.window_manager.windows
                     if window.as_pointer() not in previous)
editor_area = next(area for area in editor_window.screen.areas if area.type == 'VIEW_3D')
editor_region = next(region for region in editor_area.regions if region.type == 'WINDOW')
```

The new screen contains one editor. Hide its headers, toolbar, sidebar, HUD, gizmos, and overlays without changing the source editor. Check `space.is_property_readonly(name)` before assigning visibility flags: the asset shelf can be dynamically read-only in modes with no shelf. Draw through `SpaceView3D.draw_handler_add(..., 'WINDOW', 'POST_PIXEL')`, and add the modal handler and event timer in the new window's context. Filter drawing by both area and region, since the handler is shared across viewports.

Remove the draw handler and event timer on Cancel, completion, file load, add-on shutdown, or native window closure. A small application timer can detect when either window disappears. Schedule closing the owned window with `bpy.app.timers` after the modal callback returns, and close only the window created by the tool. Keep folder-picker return context tied to the source editor. Run asset changes and reports in that source context.

Close the editor window before saving a Blend file, then run creation from a later timer using a snapshot of the operator settings. Otherwise the extra window can be saved into the file's workspace layout. The experiment verified mouse input, text editing, dropdowns, folder browsing and resume, native window closure, creation with and without saving, and reopening a saved Blend with only the original window.

## A standalone application window

The existing wizard renderer uses Blender's GPU, font, and event APIs; `area_dupli` cannot detach it from Blender. A standalone window needs another renderer and event loop, with a bridge that sends settings back to Blender for validation and creation on Blender's main thread. Foundry's external `foundry_output_viewer.pyw` is an existing example of a separate Windows process, but the wizard cannot reuse its Blender renderer in that process.
