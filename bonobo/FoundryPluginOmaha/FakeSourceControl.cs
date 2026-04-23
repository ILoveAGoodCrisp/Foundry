using Bonobo.PluginSystem;
using Bonobo.PluginSystem.Custom;
using Bungie.Reactive;
using Corinth.Connections;
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Threading;

namespace FoundryPlugin
{
    [BonoboPlugin("Foundry Fake Source Control", Priority = InitializationPriority.Normal)]
    public class FoundryFakeSourceControl :
        BonoboPlugin,
        ISourceControlProvider,
        IAsyncSourceControlProvider,
        ISourceControlMenuProvider
    {
        private static readonly string[] FilePathPropertyNames =
        {
            "FilePath",
            "FullName",
            "FileName",
            "Filename",
            "Path",
            "FullPath",
            "TagPath",
            "DisplayPath",
            "RelativePathWithExtension",
            "RelativePath"
        };

        private static readonly string[] NestedPathPropertyNames =
        {
            "ContentInfo",
            "SourceControlFile",
            "ProjectPath",
            "File",
            "SourceFile",
            "TagFile",
            "Entry",
            "Item",
            "ActualItem",
            "Node",
            "Content"
        };

        private static readonly IReadOnlyList<string> EmptyClientList =
            new List<string>();

        private static readonly HashSet<string> HiddenContextMenuItems =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "Get Latest",
                "Force Get Latest",
                "Check Out",
                "Scratch Check Out",
                "Submit",
                "Revert",
                "Delete",
                "Show Differences From Depot",
                "Show History...",
                "Force XSync",
                "XSync",
                "Drop in Max",
                "XDrop tag in game"
            };

        private static readonly string[] TagFileMenuMarkers =
        {
            "Open in Tag view",
            "Open in Grid view",
            "Copy Paths"
        };

        private static readonly HashSet<string> ClipboardDropTagTypes =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "model",
                "biped",
                "crate",
                "creature",
                "device_control",
                "device_dispenser",
                "effect_scenery",
                "equipment",
                "giant",
                "device_machine",
                "projectile",
                "scenery",
                "spawner",
                "sound_scenery",
                "device_terminal",
                "vehicle",
                "weapon"
            };

        private static readonly HashSet<string> ClipboardAnimationPlayTagTypes =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "frame_event_list"
            };

        private static readonly string[] FolderMenuMarkers =
        {
            "Get Latest",
            "Force Get Latest",
            "Check Out",
            "Scratch Check Out"
        };

        private static bool _sourceControlToolTipsInstalled;
        private static bool _contextMenuCleanupInstalled;
        private static bool _renderModelDropButtonsInstalled;

        public FoundryFakeSourceControl(IPluginHost host)
            : base(host)
        {
            //System.Windows.MessageBox.Show("Fake SCM Plugin Loaded");
            ProjectInfo.Initialize();
            InstallSourceControlToolTipOverride();
            InstallContextMenuCleanup();
            InstallRenderModelDropButtonOverride();
            SuppressSourceControlStyles();
        }

        public bool RepoExists => true;

        public IObservableValue<bool> IsAvailable =>
            new AlwaysTrueObservable();

        public SourceControlFile GetSingleFileState(string fileName)
        {
            //System.Windows.MessageBox.Show("Fake SCM hit");
            return CreateUpToDateFile(fileName);
        }

        public IEnumerable<SourceControlFile> GetFileStates(IEnumerable<string> fileSpecs)
            => fileSpecs.Select(CreateUpToDateFile);

        public IEnumerable<SourceControlFile> GetFileStateForDirectory(string directoryPath)
        {
            if (!System.IO.Directory.Exists(directoryPath))
                return Enumerable.Empty<SourceControlFile>();

            return System.IO.Directory
                .EnumerateFiles(directoryPath)
                .Select(CreateUpToDateFile)
                .ToList();
        }

        public IEnumerable<SourceControlFile> GetOpenedFiles() => Enumerable.Empty<SourceControlFile>();

        public IEnumerable<string> GetCheckedOutClients(string fileName) => EmptyClientList;

        public IEnumerable<string> GetFilesNotInDefaultChangelist(IEnumerable<string> fileNames) => EmptyClientList;

        public int GetLastDepotRevision(string fileName) => 0;

        public bool IsFileOperationAvailable(
            SourceControlOperation operation,
            SourceControlFileState state,
            bool isWritable,
            string file = null)
        {
            switch (operation)
            {
                default:
                    return false;
            }
        }

        public void RefreshAvailability() { }

        public IEnumerable<MenuItemDescription> GetSourceControlMenuItems<T>(
            Func<T, IEnumerable<SourceControlMenuFile>> getFocusedWindowMenuFilesFunc,
            Func<T, bool> saveFocusedWindowFunc)
            where T : System.Windows.FrameworkElement
            => Enumerable.Empty<MenuItemDescription>();

        public IObservable<IEnumerable<SourceControlFile>> GetFileStatesAsync(IEnumerable<string> fileSpecs)
            => new FakeObservable<IEnumerable<SourceControlFile>>(GetFileStates(fileSpecs));

        public IObservable<IEnumerable<SourceControlFile>> GetFileStateForDirectoryAsync(IEnumerable<string> directoryPaths)
        {
            var results = new List<SourceControlFile>();

            foreach (var dir in directoryPaths)
            {
                results.AddRange(GetFileStateForDirectory(dir));
            }

            return new FakeObservable<IEnumerable<SourceControlFile>>(results);
        }

        // ---- Helpers ----

        private SourceControlFile CreateUpToDateFile(string fileName)
        {
            return new SourceControlFile(
                fileName,
                SourceControlFileState.CheckedOutOnThisClient,
                false,
                EmptyClientList,
                EmptyClientList,
                true);
        }

        private static void SuppressSourceControlStyles()
        {
            var application = Application.Current;
            if (application == null)
                return;

            ApplySourceControlStyleOverrides(application);
            application.Dispatcher.BeginInvoke(
                new Action(() => ApplySourceControlStyleOverrides(application)),
                DispatcherPriority.ApplicationIdle);
        }

        private static void InstallSourceControlToolTipOverride()
        {
            if (_sourceControlToolTipsInstalled)
                return;

            var sourceControlBorderType = GetSourceControlBorderType();
            if (sourceControlBorderType == null)
                return;

            EventManager.RegisterClassHandler(
                sourceControlBorderType,
                FrameworkElement.ToolTipOpeningEvent,
                new ToolTipEventHandler(OnSourceControlToolTipOpening),
                true);

            _sourceControlToolTipsInstalled = true;
        }

        private static void InstallContextMenuCleanup()
        {
            if (_contextMenuCleanupInstalled)
                return;

            EventManager.RegisterClassHandler(
                typeof(ContextMenu),
                ContextMenu.OpenedEvent,
                new RoutedEventHandler(OnContextMenuOpened),
                true);

            _contextMenuCleanupInstalled = true;
        }

        private static void InstallRenderModelDropButtonOverride()
        {
            if (_renderModelDropButtonsInstalled)
                return;

            EventManager.RegisterClassHandler(
                typeof(ButtonBase),
                ButtonBase.ClickEvent,
                new RoutedEventHandler(OnRenderModelDropButtonClick),
                true);
            EventManager.RegisterClassHandler(
                typeof(ButtonBase),
                FrameworkElement.ToolTipOpeningEvent,
                new ToolTipEventHandler(OnRenderModelDropButtonToolTipOpening),
                true);

            _renderModelDropButtonsInstalled = true;
        }

        private static void ApplySourceControlStyleOverrides(Application application)
        {
            var iconResourcesType = GetIconResourcesType();
            if (iconResourcesType == null || application.Resources == null)
                return;

            var defaultBackground = FindResource(
                application,
                GetStaticFieldValue(iconResourcesType, "DefaultBackgroundColorKey"),
                Brushes.Transparent);
            var defaultSelectedBackground = FindResource(
                application,
                GetStaticFieldValue(iconResourcesType, "DefaultSelectedBackgroundColorKey"),
                defaultBackground);

            foreach (var field in iconResourcesType.GetFields(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
            {
                var key = field.GetValue(null);
                if (key == null)
                    continue;

                if (field.Name.EndsWith("BackgroundColorKey") || field.Name.EndsWith("BackgroundBrushKey"))
                {
                    application.Resources[key] = field.Name.Contains("Selected")
                        ? defaultSelectedBackground
                        : defaultBackground;
                }
                else if (field.Name.StartsWith("fileState", StringComparison.OrdinalIgnoreCase))
                {
                    application.Resources[key] = new DrawingBrush();
                }
            }
        }

        private static Type GetIconResourcesType()
        {
            return Type.GetType("Bungie.UI.Wpf.IconResources, Bungie.Core.Wpf")
                ?? Type.GetType("Corinth.UI.Wpf.IconResources, Corinth.Core.Wpf");
        }

        private static Type GetSourceControlBorderType()
        {
            return Type.GetType("Bungie.UI.Wpf.SourceControlBorder, Bungie.Core.Wpf")
                ?? Type.GetType("Corinth.UI.Wpf.SourceControlBorder, Corinth.Core.Wpf");
        }

        private static object GetStaticFieldValue(Type type, string fieldName)
        {
            var field = type.GetField(fieldName, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
            return field?.GetValue(null);
        }

        private static object FindResource(Application application, object key, object fallback)
        {
            return key == null
                ? fallback
                : application.TryFindResource(key) ?? fallback;
        }

        private static void OnSourceControlToolTipOpening(object sender, ToolTipEventArgs e)
        {
            var element = sender as FrameworkElement;
            if (element == null)
                return;

            if (!GetBooleanPropertyValue(element, "IsWritable"))
            {
                element.ClearValue(ToolTipService.ToolTipProperty);
                return;
            }

            element.SetValue(
                ToolTipService.ToolTipProperty,
                BuildWritableFileToolTip(element));
        }

        private static void OnContextMenuOpened(object sender, RoutedEventArgs e)
        {
            var contextMenu = sender as ContextMenu;
            if (contextMenu == null)
                return;

            PruneSourceControlContextMenu(contextMenu);
        }

        private static void OnRenderModelDropButtonClick(object sender, RoutedEventArgs e)
        {
            var button = sender as ButtonBase;
            if (button == null)
                return;

            if (!TryBuildClipboardDropScript(button, out string script))
                return;

            e.Handled = true;

            try
            {
                Clipboard.SetText(script);
            }
            catch
            {
                try
                {
                    Clipboard.SetDataObject(script, true);
                }
                catch
                {
                }
            }
        }

        private static void OnRenderModelDropButtonToolTipOpening(object sender, ToolTipEventArgs e)
        {
            var button = sender as ButtonBase;
            if (button == null)
                return;

            if (!TryBuildDropButtonToolTip(button, out string toolTip))
                return;

            button.SetValue(ToolTipService.ToolTipProperty, toolTip);
        }

        private static void PruneSourceControlContextMenu(ContextMenu contextMenu)
        {
            if (!LooksLikeTagFileContextMenu(contextMenu) &&
                !LooksLikeFolderContextMenu(contextMenu))
                return;

            bool removedAnyItems = false;

            for (int index = contextMenu.Items.Count - 1; index >= 0; index--)
            {
                var menuItem = contextMenu.Items[index] as MenuItem;
                if (menuItem == null)
                    continue;

                string header = GetMenuHeaderText(menuItem.Header);
                if (!HiddenContextMenuItems.Contains(header))
                    continue;

                contextMenu.Items.RemoveAt(index);
                removedAnyItems = true;
            }

            if (removedAnyItems)
            {
                RemoveDuplicateSeparators(contextMenu.Items);
                CloseIfEmpty(contextMenu);
            }
        }

        private static bool LooksLikeTagFileContextMenu(ContextMenu contextMenu)
        {
            int matchedMarkers = 0;

            foreach (var item in contextMenu.Items.OfType<MenuItem>())
            {
                string header = GetMenuHeaderText(item.Header);
                if (TagFileMenuMarkers.Contains(header, StringComparer.OrdinalIgnoreCase))
                    matchedMarkers++;
            }

            return matchedMarkers >= 2;
        }

        private static bool LooksLikeFolderContextMenu(ContextMenu contextMenu)
        {
            int matchedMarkers = contextMenu.Items
                .OfType<MenuItem>()
                .Select(item => GetMenuHeaderText(item.Header))
                .Where(header => !string.IsNullOrWhiteSpace(header))
                .Count(header => FolderMenuMarkers.Contains(header, StringComparer.OrdinalIgnoreCase));

            return matchedMarkers >= 2;
        }

        private static string GetMenuHeaderText(object header)
        {
            if (header == null)
                return string.Empty;

            if (header is string stringHeader)
                return NormalizeMenuHeader(stringHeader);

            if (header is AccessText accessText)
                return NormalizeMenuHeader(accessText.Text);

            if (header is TextBlock textBlock)
                return NormalizeMenuHeader(textBlock.Text);

            return NormalizeMenuHeader(header.ToString());
        }

        private static string NormalizeMenuHeader(string header)
        {
            if (string.IsNullOrWhiteSpace(header))
                return string.Empty;

            return header
                .Replace("_", string.Empty)
                .Replace("\u2026", "...")
                .Trim();
        }

        private static void RemoveDuplicateSeparators(ItemCollection items)
        {
            while (items.Count > 0 && items[0] is Separator)
                items.RemoveAt(0);

            while (items.Count > 0 && items[items.Count - 1] is Separator)
                items.RemoveAt(items.Count - 1);

            bool previousWasSeparator = false;

            for (int index = 0; index < items.Count; index++)
            {
                if (items[index] is Separator)
                {
                    if (previousWasSeparator)
                    {
                        items.RemoveAt(index);
                        index--;
                        continue;
                    }

                    previousWasSeparator = true;
                    continue;
                }

                previousWasSeparator = false;
            }
        }

        private static void CloseIfEmpty(ContextMenu contextMenu)
        {
            if (contextMenu.Items.OfType<MenuItem>().Any())
                return;

            contextMenu.Dispatcher.BeginInvoke(
                new Action(() => contextMenu.IsOpen = false),
                DispatcherPriority.ApplicationIdle);
        }

        private static bool TryBuildClipboardDropScript(ButtonBase button, out string script)
        {
            return TryBuildRenderModelClipboardDropScript(button, out script) ||
                TryBuildPlayOnPlayerClipboardScript(button, out script) ||
                TryBuildSoundClipboardScript(button, out script) ||
                TryBuildSoundLoopingClipboardScript(button, out script);
        }

        private static bool TryBuildDropButtonToolTip(ButtonBase button, out string toolTip)
        {
            return TryBuildRenderModelDropButtonToolTip(button, out toolTip) ||
                TryBuildPlayOnPlayerButtonToolTip(button, out toolTip) ||
                TryBuildSoundButtonToolTip(button, out toolTip) ||
                TryBuildSoundLoopingButtonToolTip(button, out toolTip);
        }

        private static bool TryBuildRenderModelClipboardDropScript(ButtonBase button, out string script)
        {
            script = null;

            string buttonText = GetButtonText(button);
            if (!IsClipboardDropButtonText(buttonText))
                return false;

            object dropPanel = FindAncestorByTypeName(
                button,
                "Bonobo.Plugins.RenderModel.RenderModelDropPanel");
            if (dropPanel == null)
                return false;

            object tagPath = GetReadableFieldValue(dropPanel, "_tagPath");
            string relativePathWithExtension = GetTagRelativePathWithExtension(tagPath);
            if (string.IsNullOrWhiteSpace(relativePathWithExtension) ||
                !IsSupportedClipboardDropTagType(tagPath, relativePathWithExtension))
                return false;

            if (buttonText.Equals("Drop Variant", StringComparison.OrdinalIgnoreCase))
                return TryBuildVariantDropScript(dropPanel, relativePathWithExtension, out script);

            return TryBuildPermutationDropScript(dropPanel, relativePathWithExtension, out script);
        }

        private static bool TryBuildRenderModelDropButtonToolTip(ButtonBase button, out string toolTip)
        {
            toolTip = null;

            string buttonText = GetButtonText(button);
            if (!IsClipboardDropButtonText(buttonText))
                return false;

            object dropPanel = FindAncestorByTypeName(
                button,
                "Bonobo.Plugins.RenderModel.RenderModelDropPanel");
            if (dropPanel == null)
                return false;

            object tagPath = GetReadableFieldValue(dropPanel, "_tagPath");
            string relativePathWithExtension = GetTagRelativePathWithExtension(tagPath);
            if (string.IsNullOrWhiteSpace(relativePathWithExtension) ||
                !IsSupportedClipboardDropTagType(tagPath, relativePathWithExtension))
                return false;

            if (buttonText.Equals("Drop Variant", StringComparison.OrdinalIgnoreCase))
            {
                toolTip = "Copies the script for dropping the selected variant to the clipboard.";
                return true;
            }

            toolTip = "Copies the script for dropping the selected permutation set to the clipboard.";
            return true;
        }

        private static bool TryBuildPlayOnPlayerClipboardScript(ButtonBase button, out string script)
        {
            script = null;

            if (!IsAnimationPlayButtonText(GetButtonText(button)))
                return false;

            object tagPath = TryFindNearbyTagPath(button);
            if (tagPath == null || !IsSupportedAnimationPlayTagType(tagPath))
                return false;

            string relativePath = GetTagRelativePath(tagPath);
            if (string.IsNullOrWhiteSpace(relativePath))
                return false;

            string animationName = TryGetPlayOnPlayerAnimationName(button);
            if (string.IsNullOrWhiteSpace(animationName))
                return false;

            script = "custom_animation (player_get 0) " + relativePath + " " + animationName + " FALSE";
            return true;
        }

        private static bool TryBuildPlayOnPlayerButtonToolTip(ButtonBase button, out string toolTip)
        {
            toolTip = null;

            string buttonText = GetButtonText(button);
            if (!IsAnimationPlayButtonText(buttonText))
                return false;

            if (!IsSupportedAnimationPlayTagType(TryFindNearbyTagPath(button)))
                return false;

            toolTip = buttonText.Equals("Play on player", StringComparison.OrdinalIgnoreCase)
                ? "Copies the HS script for playing this animation on the player to the clipboard."
                : "Copies the HS script for playing this animation to the clipboard.";
            return true;
        }

        private static bool TryBuildSoundClipboardScript(ButtonBase button, out string script)
        {
            script = null;

            string buttonText = GetButtonText(button);
            if (!IsSoundPlaybackButtonText(buttonText))
                return false;

            object soundSection = FindAncestorByTypeName(
                button,
                "Bonobo.Plugins.TagCustomSection.SoundSection");
            if (soundSection == null)
                return false;

            string tagPath = TryGetSoundTagPath(button, soundSection);
            if (string.IsNullOrWhiteSpace(tagPath))
                return false;

            switch (buttonText)
            {
                case "Play":
                    script = BuildHsCommandScript(
                        "sound_impulse_start_editor",
                        tagPath,
                        "NONE",
                        GetReadablePropertyValue(soundSection, "InputScale"));
                    return true;

                case "Play on Object":
                    script = BuildHsCommandScript(
                        "sound_impulse_start_editor",
                        tagPath,
                        GetReadablePropertyValue(soundSection, "Object"),
                        GetReadablePropertyValue(soundSection, "InputScale"));
                    return true;

                case "Trigger":
                    script = BuildHsCommandScript(
                        "sound_impulse_trigger",
                        tagPath,
                        GetReadablePropertyValue(soundSection, "Object"),
                        GetReadablePropertyValue(soundSection, "InputScale"),
                        GetReadablePropertyValue(soundSection, "Count"));
                    return true;

                case "Play w/ Effect":
                    script = BuildHsCommandScript(
                        "sound_impulse_start_effect_editor",
                        tagPath,
                        GetReadablePropertyValue(soundSection, "Object"),
                        GetReadablePropertyValue(soundSection, "InputScale"),
                        GetReadablePropertyValue(soundSection, "EffectName"));
                    return true;

                case "Play 3D":
                    script = BuildHsCommandScript(
                        "sound_impulse_start_3d_editor",
                        tagPath,
                        GetReadablePropertyValue(soundSection, "Azimuth"),
                        GetReadablePropertyValue(soundSection, "InputScale"));
                    return true;

                case "Stop":
                    script = BuildHsCommandScript(
                        "sound_impulse_stop",
                        tagPath);
                    return true;
            }

            return false;
        }

        private static bool TryBuildSoundButtonToolTip(ButtonBase button, out string toolTip)
        {
            toolTip = null;

            string buttonText = GetButtonText(button);
            if (!IsSoundPlaybackButtonText(buttonText))
                return false;

            object soundSection = FindAncestorByTypeName(
                button,
                "Bonobo.Plugins.TagCustomSection.SoundSection");
            if (soundSection == null ||
                string.IsNullOrWhiteSpace(TryGetSoundTagPath(button, soundSection)))
                return false;

            switch (buttonText)
            {
                case "Play":
                    toolTip = "Copies the HS script for playing this sound to the clipboard.";
                    return true;

                case "Play on Object":
                    toolTip = "Copies the HS script for playing this sound on the selected object to the clipboard.";
                    return true;

                case "Trigger":
                    toolTip = "Copies the HS script for triggering this sound to the clipboard.";
                    return true;

                case "Play w/ Effect":
                    toolTip = "Copies the HS script for playing this sound with the selected effect to the clipboard.";
                    return true;

                case "Play 3D":
                    toolTip = "Copies the HS script for playing this sound in 3D to the clipboard.";
                    return true;

                case "Stop":
                    toolTip = "Copies the HS script for stopping this sound to the clipboard.";
                    return true;
            }

            return false;
        }

        private static bool TryBuildSoundLoopingClipboardScript(ButtonBase button, out string script)
        {
            script = null;

            string buttonText = GetButtonText(button);
            if (!IsSoundLoopingPlaybackButtonText(buttonText) &&
                !IsSoundLoopingCheckBoxText(buttonText))
                return false;

            object soundLoopingSection = FindAncestorByTypeName(
                button,
                "Bonobo.Plugins.TagCustomSection.SoundLoopingSection");
            if (soundLoopingSection == null)
                return false;

            string tagPath = TryGetSoundLoopingTagPath(button, soundLoopingSection);
            if (string.IsNullOrWhiteSpace(tagPath))
                return false;

            if (TryBuildSoundLoopingCheckBoxClipboardScript(button, buttonText, tagPath, out script))
                return true;

            switch (buttonText)
            {
                case "Play":
                    script = BuildHsCommandScript(
                        "sound_looping_start_editor",
                        tagPath,
                        GetReadablePropertyValue(soundLoopingSection, "Object"),
                        GetReadablePropertyValue(soundLoopingSection, "InputScale"));
                    return true;

                case "Stop":
                    script = BuildHsCommandScript(
                        "sound_looping_stop",
                        tagPath);
                    return true;

                case "Kill":
                    script = BuildHsCommandScript(
                        "sound_looping_stop_immediately",
                        tagPath);
                    return true;
            }

            return false;
        }

        private static bool TryBuildSoundLoopingButtonToolTip(ButtonBase button, out string toolTip)
        {
            toolTip = null;

            string buttonText = GetButtonText(button);
            if (!IsSoundLoopingPlaybackButtonText(buttonText) &&
                !IsSoundLoopingCheckBoxText(buttonText))
                return false;

            object soundLoopingSection = FindAncestorByTypeName(
                button,
                "Bonobo.Plugins.TagCustomSection.SoundLoopingSection");
            if (soundLoopingSection == null ||
                string.IsNullOrWhiteSpace(TryGetSoundLoopingTagPath(button, soundLoopingSection)))
                return false;

            if (TryBuildSoundLoopingCheckBoxToolTip(button, buttonText, out toolTip))
                return true;

            switch (buttonText)
            {
                case "Play":
                    toolTip = "Copies the HS script for playing this looping sound to the clipboard.";
                    return true;

                case "Stop":
                    toolTip = "Copies the HS script for stopping this looping sound to the clipboard.";
                    return true;

                case "Kill":
                    toolTip = "Copies the HS script for killing this looping sound immediately to the clipboard.";
                    return true;
            }

            return false;
        }

        private static bool TryBuildSoundLoopingCheckBoxClipboardScript(
            ButtonBase button,
            string buttonText,
            string tagPath,
            out string script)
        {
            script = null;

            if (buttonText.Equals("Play alternate tracks", StringComparison.OrdinalIgnoreCase))
            {
                script = BuildHsCommandScript(
                    "sound_looping_set_alternate",
                    tagPath,
                    IsToggleButtonChecked(button) ? "1" : "0");
                return true;
            }

            if (!buttonText.StartsWith("activate layer", StringComparison.OrdinalIgnoreCase))
                return false;

            string layer = ConvertToString(GetReadablePropertyValue(button, "Tag")) ??
                TryExtractTrailingNumber(buttonText);
            if (string.IsNullOrWhiteSpace(layer))
                return false;

            script = BuildHsCommandScript(
                IsToggleButtonChecked(button)
                    ? "sound_looping_activate_layer"
                    : "sound_looping_deactivate_layer",
                tagPath,
                layer);
            return true;
        }

        private static bool TryBuildSoundLoopingCheckBoxToolTip(
            ButtonBase button,
            string buttonText,
            out string toolTip)
        {
            toolTip = null;

            if (buttonText.Equals("Play alternate tracks", StringComparison.OrdinalIgnoreCase))
            {
                toolTip = IsToggleButtonChecked(button)
                    ? "Copies the HS script for enabling alternate tracks on this looping sound to the clipboard."
                    : "Copies the HS script for disabling alternate tracks on this looping sound to the clipboard.";
                return true;
            }

            if (!buttonText.StartsWith("activate layer", StringComparison.OrdinalIgnoreCase))
                return false;

            string layer = ConvertToString(GetReadablePropertyValue(button, "Tag")) ??
                TryExtractTrailingNumber(buttonText);
            if (string.IsNullOrWhiteSpace(layer))
                return false;

            toolTip = IsToggleButtonChecked(button)
                ? $"Copies the HS script for activating layer {layer} on this looping sound to the clipboard."
                : $"Copies the HS script for deactivating layer {layer} on this looping sound to the clipboard.";
            return true;
        }

        private static bool IsClipboardDropButtonText(string buttonText)
        {
            return buttonText.Equals("Drop Variant", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Drop Permutation", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsAnimationPlayButtonText(string buttonText)
        {
            return buttonText.Equals("Play", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSoundPlaybackButtonText(string buttonText)
        {
            return buttonText.Equals("Play", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Play on Object", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Trigger", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Play w/ Effect", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Play 3D", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Stop", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSoundLoopingPlaybackButtonText(string buttonText)
        {
            return buttonText.Equals("Play", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Stop", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Kill", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSoundLoopingCheckBoxText(string buttonText)
        {
            return buttonText.Equals("Play alternate tracks", StringComparison.OrdinalIgnoreCase) ||
                buttonText.StartsWith("activate layer", StringComparison.OrdinalIgnoreCase);
        }

        private static string GetButtonText(ButtonBase button)
        {
            return GetMenuHeaderText(GetReadablePropertyValue(button, "Content"));
        }

        private static string TryGetSoundTagPath(ButtonBase button, object soundSection)
        {
            object tagPath = TryFindNearbyTagPath(button);
            string relativePathWithExtension = GetTagRelativePathWithExtension(tagPath);
            if (!string.IsNullOrWhiteSpace(relativePathWithExtension) &&
                string.Equals(Path.GetExtension(relativePathWithExtension), ".sound", StringComparison.OrdinalIgnoreCase))
                return relativePathWithExtension;

            string fieldTagPath = ConvertToString(GetReadableFieldValueFromHierarchy(soundSection, "tagPath"));
            return string.IsNullOrWhiteSpace(fieldTagPath) ||
                !string.Equals(Path.GetExtension(fieldTagPath), ".sound", StringComparison.OrdinalIgnoreCase)
                ? null
                : fieldTagPath;
        }

        private static string TryGetSoundLoopingTagPath(ButtonBase button, object soundLoopingSection)
        {
            object tagPath = TryFindNearbyTagPath(button);
            string relativePathWithExtension = GetTagRelativePathWithExtension(tagPath);
            if (!string.IsNullOrWhiteSpace(relativePathWithExtension) &&
                string.Equals(Path.GetExtension(relativePathWithExtension), ".sound_looping", StringComparison.OrdinalIgnoreCase))
                return relativePathWithExtension;

            string fieldTagPath = ConvertToString(GetReadableFieldValueFromHierarchy(soundLoopingSection, "tagPath"));
            return string.IsNullOrWhiteSpace(fieldTagPath) ||
                !string.Equals(Path.GetExtension(fieldTagPath), ".sound_looping", StringComparison.OrdinalIgnoreCase)
                ? null
                : fieldTagPath;
        }

        private static string BuildHsCommandScript(string commandName, params object[] parameters)
        {
            var parts = new List<string>(1 + parameters.Length)
            {
                commandName
            };

            foreach (object parameter in parameters)
                parts.Add(ConvertToString(parameter) ?? string.Empty);

            return string.Join(" ", parts).Trim();
        }

        private static bool IsToggleButtonChecked(ButtonBase button)
        {
            object value = GetReadablePropertyValue(button, "IsChecked");
            if (value is bool booleanValue)
                return booleanValue;

            if (value != null &&
                bool.TryParse(value.ToString(), out bool parsedValue))
                return parsedValue;

            return false;
        }

        private static string TryExtractTrailingNumber(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return null;

            for (int index = text.Length - 1; index >= 0; index--)
            {
                if (!char.IsDigit(text[index]))
                    continue;

                int end = index;
                int start = index;
                while (start > 0 && char.IsDigit(text[start - 1]))
                    start--;

                return text.Substring(start, end - start + 1);
            }

            return null;
        }

        private static string TryGetPlayOnPlayerAnimationName(ButtonBase button)
        {
            foreach (object candidate in GetAnimationNameCandidates(button))
            {
                string animationName = TryExtractAnimationName(
                    candidate,
                    new HashSet<object>(ReferenceEqualityComparer.Instance),
                    0);
                if (!string.IsNullOrWhiteSpace(animationName))
                    return animationName;
            }

            return null;
        }

        private static bool TryBuildVariantDropScript(
            object dropPanel,
            string relativePathWithExtension,
            out string script)
        {
            script = null;

            object variantsControl = GetReadableFieldValue(dropPanel, "_variantsControl");
            string variantName = ConvertToString(InvokeParameterlessMethod(variantsControl, "GetCurrentVariantName"));
            if (variantName == null)
                return false;

            script = "drop_variant " + relativePathWithExtension + " " + variantName;
            return true;
        }

        private static bool TryBuildPermutationDropScript(
            object dropPanel,
            string relativePathWithExtension,
            out string script)
        {
            script = null;

            object permutationsControl = GetReadableFieldValue(dropPanel, "_permutationsControl");
            string selection = SerializePermutationSelection(
                InvokeParameterlessMethod(permutationsControl, "GetCurrentSelection"));
            if (selection == null)
                return false;

            script = "drop_permutation " + relativePathWithExtension + " " + selection;
            return true;
        }

        private static string SerializePermutationSelection(object selection)
        {
            if (selection == null)
                return null;

            var parts = new List<string>();

            var dictionary = selection as IDictionary;
            if (dictionary != null)
            {
                foreach (DictionaryEntry entry in dictionary)
                {
                    string key = ConvertToString(entry.Key);
                    if (string.IsNullOrWhiteSpace(key))
                        continue;

                    parts.Add(key + "=" + (ConvertToString(entry.Value) ?? string.Empty));
                }

                return parts.Count == 0
                    ? null
                    : string.Join(",", parts);
            }

            var enumerable = selection as IEnumerable;
            if (enumerable == null || selection is string)
                return null;

            foreach (object entry in enumerable)
            {
                string key = ConvertToString(GetReadablePropertyValue(entry, "Key"));
                if (string.IsNullOrWhiteSpace(key))
                    continue;

                parts.Add(key + "=" + (ConvertToString(GetReadablePropertyValue(entry, "Value")) ?? string.Empty));
            }

            return parts.Count == 0
                ? null
                : string.Join(",", parts);
        }

        private static bool IsSupportedClipboardDropTagType(object tagPath, string relativePathWithExtension)
        {
            string extension = ConvertToString(GetReadablePropertyValue(tagPath, "Extension"));
            if (string.IsNullOrWhiteSpace(extension))
                extension = Path.GetExtension(relativePathWithExtension);

            if (string.IsNullOrWhiteSpace(extension))
                return false;

            return ClipboardDropTagTypes.Contains(extension.TrimStart('.'));
        }

        private static bool IsSupportedAnimationPlayTagType(object tagPath)
        {
            string extension = ConvertToString(GetReadablePropertyValue(tagPath, "Extension"));
            if (string.IsNullOrWhiteSpace(extension))
            {
                string relativePathWithExtension = GetTagRelativePathWithExtension(tagPath);
                extension = Path.GetExtension(relativePathWithExtension);
            }

            return !string.IsNullOrWhiteSpace(extension) &&
                ClipboardAnimationPlayTagTypes.Contains(extension.TrimStart('.'));
        }

        private static string GetTagRelativePathWithExtension(object tagPath)
        {
            string relativePathWithExtension = ConvertToString(
                GetReadablePropertyValue(tagPath, "RelativePathWithExtension"));
            if (!string.IsNullOrWhiteSpace(relativePathWithExtension))
                return relativePathWithExtension;

            string relativePath = ConvertToString(GetReadablePropertyValue(tagPath, "RelativePath"));
            if (string.IsNullOrWhiteSpace(relativePath))
                return null;

            string extension = ConvertToString(GetReadablePropertyValue(tagPath, "Extension"));
            if (string.IsNullOrWhiteSpace(extension))
                return relativePath;

            extension = extension.TrimStart('.');
            return relativePath.EndsWith("." + extension, StringComparison.OrdinalIgnoreCase)
                ? relativePath
                : relativePath + "." + extension;
        }

        private static string GetTagRelativePath(object tagPath)
        {
            string relativePath = ConvertToString(GetReadablePropertyValue(tagPath, "RelativePath"));
            if (!string.IsNullOrWhiteSpace(relativePath))
                return relativePath;

            string relativePathWithExtension = GetTagRelativePathWithExtension(tagPath);
            if (string.IsNullOrWhiteSpace(relativePathWithExtension))
                return null;

            int extensionIndex = relativePathWithExtension.LastIndexOf('.');
            return extensionIndex > 0
                ? relativePathWithExtension.Substring(0, extensionIndex)
                : relativePathWithExtension;
        }

        private static object TryFindNearbyTagPath(DependencyObject start)
        {
            var visited = new HashSet<object>(ReferenceEqualityComparer.Instance);

            foreach (object candidate in GetTagPathCandidates(start))
            {
                object tagPath = TryExtractTagPath(candidate, visited, 0);
                if (tagPath != null)
                    return tagPath;
            }

            return null;
        }

        private static IEnumerable<object> GetTagPathCandidates(DependencyObject start)
        {
            for (DependencyObject current = start; current != null; current = GetParentObject(current))
            {
                yield return current;

                if (current is FrameworkElement frameworkElement)
                {
                    if (frameworkElement.DataContext != null)
                        yield return frameworkElement.DataContext;

                    if (frameworkElement.Tag != null)
                        yield return frameworkElement.Tag;
                }
            }
        }

        private static object TryExtractTagPath(object value, HashSet<object> visited, int depth)
        {
            if (value == null || depth > 4)
                return null;

            if (LooksLikeTagPath(value))
                return value;

            Type valueType = value.GetType();
            if (!valueType.IsValueType && !visited.Add(value))
                return null;

            foreach (string memberName in new[]
            {
                "Path",
                "TagPath",
                "TagFile",
                "_tagPath",
                "_tagFile",
                "Field",
                "Owner",
                "Source",
                "Item",
                "Content",
                "DataContext",
                "Tag"
            })
            {
                object nestedValue = GetReadablePropertyValue(value, memberName) ??
                    GetReadableFieldValue(value, memberName);
                object nestedTagPath = TryExtractTagPath(nestedValue, visited, depth + 1);
                if (nestedTagPath != null)
                    return nestedTagPath;
            }

            return null;
        }

        private static bool LooksLikeTagPath(object value)
        {
            return !string.IsNullOrWhiteSpace(ConvertToString(GetReadablePropertyValue(value, "RelativePath"))) ||
                !string.IsNullOrWhiteSpace(ConvertToString(GetReadablePropertyValue(value, "RelativePathWithExtension")));
        }

        private static IEnumerable<object> GetAnimationNameCandidates(ButtonBase button)
        {
            object commandParameter = GetReadablePropertyValue(button, "CommandParameter");
            if (commandParameter != null)
                yield return commandParameter;

            for (DependencyObject current = button; current != null; current = GetParentObject(current))
            {
                if (current is FrameworkElement frameworkElement)
                {
                    if (frameworkElement.DataContext != null)
                        yield return frameworkElement.DataContext;

                    if (frameworkElement.Tag != null)
                        yield return frameworkElement.Tag;
                }
            }
        }

        private static string TryExtractAnimationName(object value, HashSet<object> visited, int depth)
        {
            if (value == null || depth > 4)
                return null;

            if (value is string textValue)
                return string.IsNullOrWhiteSpace(textValue)
                    ? null
                    : textValue;

            Type valueType = value.GetType();
            if (!valueType.IsValueType && !visited.Add(value))
                return null;

            foreach (string memberName in new[]
            {
                "AnimationName",
                "Name",
                "DisplayName",
                "CommandParameter",
                "Item",
                "Content",
                "DataContext",
                "Tag"
            })
            {
                object nestedValue = GetReadablePropertyValue(value, memberName) ??
                    GetReadableFieldValue(value, memberName);
                string animationName = TryExtractAnimationName(nestedValue, visited, depth + 1);
                if (!string.IsNullOrWhiteSpace(animationName))
                    return animationName;
            }

            return null;
        }

        private static object FindAncestorByTypeName(DependencyObject start, string fullTypeName)
        {
            for (DependencyObject current = start; current != null; current = GetParentObject(current))
            {
                Type currentType = current.GetType();
                if (string.Equals(currentType.FullName, fullTypeName, StringComparison.Ordinal))
                    return current;
            }

            return null;
        }

        private static DependencyObject GetParentObject(DependencyObject child)
        {
            if (child == null)
                return null;

            try
            {
                DependencyObject visualParent = VisualTreeHelper.GetParent(child);
                if (visualParent != null)
                    return visualParent;
            }
            catch
            {
            }

            var frameworkElement = child as FrameworkElement;
            if (frameworkElement?.Parent != null)
                return frameworkElement.Parent;

            return LogicalTreeHelper.GetParent(child);
        }

        private static bool GetBooleanPropertyValue(object target, string propertyName)
        {
            var value = GetReadablePropertyValue(target, propertyName);
            return value is bool booleanValue && booleanValue;
        }

        private static object BuildWritableFileToolTip(FrameworkElement element)
        {
            object[] values =
            {
                element.DataContext,
                element.Tag
            };

            foreach (object value in values)
            {
                DateTime? modifiedDate = TryGetModifiedDate(value);
                if (modifiedDate.HasValue)
                    return $"Last Modified: {modifiedDate.Value:yyyy-MM-dd HH:mm:ss}";
            }

            string filePath = values
                .Select(TryGetFilePath)
                .FirstOrDefault(path => !string.IsNullOrWhiteSpace(path));

            if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
                return "Writable";

            DateTime lastWriteTime = File.GetLastWriteTime(filePath);
            return $"Last Modified: {lastWriteTime:yyyy-MM-dd HH:mm:ss}";
        }

        private static DateTime? TryGetModifiedDate(object value)
        {
            return TryGetModifiedDate(
                value,
                new HashSet<object>(ReferenceEqualityComparer.Instance),
                0);
        }

        private static DateTime? TryGetModifiedDate(object value, HashSet<object> visited, int depth)
        {
            if (value == null || depth > 3)
                return null;

            if (value is DateTime dateTime)
                return dateTime;

            Type valueType = value.GetType();
            if (!valueType.IsValueType && !visited.Add(value))
                return null;

            foreach (string propertyName in new[] { "ModifiedDate", "Date", "LastWriteTime", "LastWriteTimeUtc" })
            {
                object propertyValue = GetReadablePropertyValue(value, propertyName);
                if (propertyValue is DateTime propertyDateTime)
                    return propertyDateTime;
            }

            foreach (string propertyName in NestedPathPropertyNames)
            {
                DateTime? nestedDate = TryGetModifiedDate(
                    GetReadablePropertyValue(value, propertyName),
                    visited,
                    depth + 1);
                if (nestedDate.HasValue)
                    return nestedDate;
            }

            string filePath = TryResolveFilePath(value);
            if (!string.IsNullOrWhiteSpace(filePath) && File.Exists(filePath))
                return File.GetLastWriteTime(filePath);

            return null;
        }

        private static string TryGetFilePath(object value)
        {
            return TryGetFilePath(
                value,
                new HashSet<object>(ReferenceEqualityComparer.Instance),
                0);
        }

        private static string TryGetFilePath(object value, HashSet<object> visited, int depth)
        {
            if (value == null || depth > 3)
                return null;

            string directPath = TryResolveFilePath(value);
            if (!string.IsNullOrWhiteSpace(directPath))
                return directPath;

            if (value is IEnumerable enumerable && !(value is string))
            {
                foreach (object item in enumerable)
                {
                    string enumerablePath = TryGetFilePath(item, visited, depth + 1);
                    if (!string.IsNullOrWhiteSpace(enumerablePath))
                        return enumerablePath;
                }

                return null;
            }

            Type valueType = value.GetType();
            if (!valueType.IsValueType && !visited.Add(value))
                return null;

            foreach (string propertyName in FilePathPropertyNames)
            {
                string propertyPath = TryResolveFilePath(GetReadablePropertyValue(value, propertyName));
                if (!string.IsNullOrWhiteSpace(propertyPath))
                    return propertyPath;
            }

            foreach (string propertyName in NestedPathPropertyNames)
            {
                string nestedPath = TryGetFilePath(
                    GetReadablePropertyValue(value, propertyName),
                    visited,
                    depth + 1);
                if (!string.IsNullOrWhiteSpace(nestedPath))
                    return nestedPath;
            }

            return null;
        }

        private static string TryResolveFilePath(object value)
        {
            if (value is FileInfo fileInfo)
                return fileInfo.Exists ? fileInfo.FullName : null;

            var path = value as string;
            if (string.IsNullOrWhiteSpace(path))
                return null;

            path = path.Replace('/', Path.DirectorySeparatorChar).Trim();

            if (Path.IsPathRooted(path))
                return File.Exists(path) ? path : null;

            string tagsRoot = GetTagsRoot();
            if (string.IsNullOrWhiteSpace(tagsRoot))
                return null;

            string combinedPath = Path.Combine(
                tagsRoot,
                path.TrimStart(Path.DirectorySeparatorChar));

            return File.Exists(combinedPath) ? combinedPath : null;
        }

        private static string GetTagsRoot()
        {
            if (string.IsNullOrWhiteSpace(ProjectInfo.TagsRoot))
                ProjectInfo.Initialize();

            return ProjectInfo.TagsRoot;
        }

        private static object GetReadablePropertyValue(object target, string propertyName)
        {
            if (target == null)
                return null;

            var property = target.GetType().GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.IgnoreCase);

            if (property == null || !property.CanRead || property.GetIndexParameters().Length != 0)
                return null;

            try
            {
                return property.GetValue(target);
            }
            catch
            {
                return null;
            }
        }

        private static object GetReadableFieldValue(object target, string fieldName)
        {
            if (target == null)
                return null;

            var field = target.GetType().GetField(
                fieldName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.IgnoreCase);

            if (field == null)
                return null;

            try
            {
                return field.GetValue(target);
            }
            catch
            {
                return null;
            }
        }

        private static object GetReadableFieldValueFromHierarchy(object target, string fieldName)
        {
            if (target == null)
                return null;

            for (Type currentType = target.GetType(); currentType != null; currentType = currentType.BaseType)
            {
                var field = currentType.GetField(
                    fieldName,
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.IgnoreCase);
                if (field == null)
                    continue;

                try
                {
                    return field.GetValue(target);
                }
                catch
                {
                    return null;
                }
            }

            return null;
        }

        private static object InvokeParameterlessMethod(object target, string methodName)
        {
            if (target == null)
                return null;

            var method = target.GetType().GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.IgnoreCase,
                null,
                Type.EmptyTypes,
                null);

            if (method == null)
                return null;

            try
            {
                return method.Invoke(target, null);
            }
            catch
            {
                return null;
            }
        }

        private static string ConvertToString(object value)
        {
            return value == null
                ? null
                : value as string ?? value.ToString();
        }

        public IEnumerable<SourceControlFile> GetFileStates(string fileSpecs)
            => new[] { CreateUpToDateFile(fileSpecs) };

        public void GetLatest(IEnumerable<string> fileNames, bool force)
        {

        }

        public void SyncToChangelist(IEnumerable<string> fileNames, int changelist)
        {
            
        }

        public bool CheckOut(IEnumerable<string> fileNames, bool sync = true, bool scratch = false, bool demoteToScratchSilently = false)
        {
            return false;
        }

        public bool CheckOutNoScratch(IEnumerable<string> fileNames, bool sync = true)
        {
            return false;
        }

        public void UndoCheckOut(IEnumerable<string> fileNames)
        {

        }

        public void UndoCheckOutWithoutPrompting(IEnumerable<string> fileNames)
        {

        }

        public bool CheckIn(IEnumerable<string> fileNames)
        {
            return false;
        }

        public bool CheckIn(string changeDescription, IEnumerable<string> fileNames)
        {
            return false;
        }

        public void MakeWritable(IEnumerable<string> fileNames)
        {

        }

        public void MakeWritable(IEnumerable<string> fileNames, IEnumerable<string> subDirectoryExtensions)
        {
        }

        public void AddNewFiles(IEnumerable<string> fileNames)
        {
            
        }

        public bool Delete(IEnumerable<string> fileNames, bool scratch = false)
        {
            foreach (string fileName in fileNames)
            {
                if(File.Exists(fileName))
                    File.Delete(fileName);
            }
            return true;
        }

        public bool DeleteWithoutPrompting(string changeDescription, IEnumerable<string> fileNames, bool scratch = false)
        {
            return false;
        }

        public void ShowDiff(IEnumerable<string> fileNames)
        {
            
        }

        public void ShowHistory(IEnumerable<string> fileNames)
        {
            
        }

        public void OnlineWithoutPrompting(string changeDescription, IEnumerable<string> fileNames)
        {
            
        }

        public bool Rename(IEnumerable<SourceControlRenameFilePair> renameFiles, bool checkIn)
        {
            return false;
        }

        public void Resolve(IEnumerable<string> filenames, IChangelist.ResolveAcceptAction acceptAction)
        {
            
        }

        public void RevertUnchangedFiles(IEnumerable<string> filenames)
        {
            
        }

        private class AlwaysTrueObservable : IObservableValue<bool>
        {
            public bool Value => true;

            public IDisposable Subscribe(IObserver<bool> observer)
            {
                observer.OnNext(true);
                observer.OnCompleted();
                return new DummyDisposable();
            }
        }

        private class FakeObservable<T> : IObservable<T>
        {
            private readonly T _value;

            public FakeObservable(T value) { _value = value; }

            public IDisposable Subscribe(IObserver<T> observer)
            {
                observer.OnNext(_value);
                observer.OnCompleted();
                return new DummyDisposable();
            }
        }

        private class DummyDisposable : IDisposable
        {
            public void Dispose() { }
        }

        private sealed class ReferenceEqualityComparer : IEqualityComparer<object>
        {
            public static readonly ReferenceEqualityComparer Instance =
                new ReferenceEqualityComparer();

            public new bool Equals(object x, object y)
                => ReferenceEquals(x, y);

            public int GetHashCode(object obj)
                => RuntimeHelpers.GetHashCode(obj);
        }

    }
}
