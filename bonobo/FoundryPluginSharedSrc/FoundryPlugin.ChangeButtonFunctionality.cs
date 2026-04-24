using Bonobo.PluginSystem;
using Bonobo.PluginSystem.Custom;
#if CORINTH_RUNTIME
using Corinth.Reactive;
#else
using Bungie.Reactive;
#endif
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
using System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

namespace FoundryPlugin
{
    public partial class FoundryPlugin
    {
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

        private static readonly HashSet<string> HiddenXboxControlTexts =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "Quick Preview",
                "Usurp Preview",
                "Use Live Mode",
                "Xsync",
                "XSync this tag on success",
                "Xsync this tag on success",
                "Connect",
                "Reboot",
                "Reboot to Game",
                "Screenshot",
                "Xbox",
                "Xbox 360"
            };

        private static bool _renderModelDropButtonsInstalled;
        private static bool _xboxUiCleanupInstalled;
        private static readonly HashSet<int> PendingXboxUiCleanupRoots =
            new HashSet<int>();

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

        private static void InstallXboxUiCleanup()
        {
            if (_xboxUiCleanupInstalled)
                return;

            EventManager.RegisterClassHandler(
                typeof(FrameworkElement),
                FrameworkElement.LoadedEvent,
                new RoutedEventHandler(OnPotentialXboxUiElementLoaded),
                true);

            _xboxUiCleanupInstalled = true;
        }

        private static void OnRenderModelDropButtonClick(object sender, RoutedEventArgs e)
        {
            var button = sender as ButtonBase;
            if (button == null)
                return;

            if (ShouldHideXboxUiElement(button))
            {
                HideXboxUiElement(button);
                e.Handled = true;
                return;
            }

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

        private static void OnPotentialXboxUiElementLoaded(object sender, RoutedEventArgs e)
        {
            var element = sender as FrameworkElement;
            if (element == null)
                return;

            ScheduleXboxUiCleanupSweep(element);
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

        private static bool ShouldHideXboxUiElement(FrameworkElement element)
        {
            string elementText = GetFrameworkElementText(element);
            if (string.IsNullOrWhiteSpace(elementText))
                return false;

            if (HiddenXboxControlTexts.Contains(elementText))
                return true;

            if (elementText.Equals("Status:", StringComparison.OrdinalIgnoreCase) ||
                elementText.Equals("Time:", StringComparison.OrdinalIgnoreCase))
                return true;

            if (elementText.StartsWith("Elapsed Time:", StringComparison.OrdinalIgnoreCase))
                return true;

            if (elementText.IndexOf("Xbox", StringComparison.OrdinalIgnoreCase) >= 0 &&
                (element is TextBlock || element is ContentControl))
                return true;

            return false;
        }

        private static string GetButtonText(ButtonBase button)
        {
            return GetMenuHeaderText(GetReadablePropertyValue(button, "Content"));
        }

        private static string GetFrameworkElementText(FrameworkElement element)
        {
            if (element == null)
                return string.Empty;

            if (element is TextBlock textBlock)
                return NormalizeMenuHeader(textBlock.Text);

            if (element is HeaderedContentControl headeredContentControl)
                return GetMenuHeaderText(headeredContentControl.Header);

            if (element is HeaderedItemsControl headeredItemsControl)
                return GetMenuHeaderText(headeredItemsControl.Header);

            if (element is ContentControl contentControl)
                return GetMenuHeaderText(contentControl.Content);

            object text = GetReadablePropertyValue(element, "Text");
            if (text != null)
                return NormalizeMenuHeader(ConvertToString(text));

            object header = GetReadablePropertyValue(element, "Header");
            if (header != null)
                return GetMenuHeaderText(header);

            object content = GetReadablePropertyValue(element, "Content");
            if (content != null)
                return GetMenuHeaderText(content);

            return string.Empty;
        }

        private static void HideXboxUiElement(FrameworkElement element)
        {
            if (element == null)
                return;

            if (element is ToggleButton toggleButton)
                toggleButton.IsChecked = false;

            DependencyObject parent = GetParentObject(element);
            RemoveOrCollapseElement(element);
            CollapseEmptyAncestorContainers(parent);
        }

        private static void ScheduleXboxUiCleanupSweep(FrameworkElement sourceElement)
        {
            FrameworkElement cleanupRoot = FindXboxUiCleanupRoot(sourceElement);
            if (cleanupRoot == null)
                return;

            int cleanupRootId = RuntimeHelpers.GetHashCode(cleanupRoot);
            if (!PendingXboxUiCleanupRoots.Add(cleanupRootId))
                return;

            cleanupRoot.Dispatcher.BeginInvoke(
                new Action(() =>
                {
                    PendingXboxUiCleanupRoots.Remove(cleanupRootId);
                    RemoveXboxUiFromSubtree(cleanupRoot);

                    cleanupRoot.Dispatcher.BeginInvoke(
                        new Action(() => RemoveXboxUiFromSubtree(cleanupRoot)),
                        DispatcherPriority.ApplicationIdle);
                }),
                DispatcherPriority.Loaded);
        }

        private static FrameworkElement FindXboxUiCleanupRoot(FrameworkElement element)
        {
            Window window = Window.GetWindow(element);
            if (window != null)
                return window;

            for (DependencyObject current = element; current != null; current = GetParentObject(current))
            {
                if (current is UserControl userControl)
                    return userControl;

                if (current is ContentPresenter contentPresenter)
                    return contentPresenter;
            }

            return element;
        }

        private static void RemoveXboxUiFromSubtree(DependencyObject root)
        {
            if (root == null)
                return;

            var pending = new Stack<DependencyObject>();
            var visited = new HashSet<object>(ReferenceEqualityComparer.Instance);
            pending.Push(root);

            while (pending.Count > 0)
            {
                DependencyObject current = pending.Pop();
                if (current == null || !visited.Add(current))
                    continue;

                if (current is FrameworkElement frameworkElement &&
                    ShouldHideXboxUiElement(frameworkElement))
                {
                    HideXboxUiElement(frameworkElement);
                    continue;
                }

                foreach (DependencyObject child in EnumerateChildObjects(current).ToList())
                    pending.Push(child);
            }
        }

        private static void RemoveOrCollapseElement(FrameworkElement element)
        {
            if (element == null)
                return;

            if (TryRemoveElementFromParent(element))
                return;

            element.Visibility = Visibility.Collapsed;
            element.IsEnabled = false;
            element.Focusable = false;
        }

        private static bool TryRemoveElementFromParent(FrameworkElement element)
        {
            DependencyObject parent = GetParentObject(element);
            if (parent == null)
                return false;

            if (parent is Panel panel && panel.Children.Contains(element))
            {
                panel.Children.Remove(element);
                return true;
            }

            if (parent is Decorator decorator && ReferenceEquals(decorator.Child, element))
            {
                decorator.Child = null;
                return true;
            }

            if (parent is ContentPresenter contentPresenter &&
                ReferenceEquals(contentPresenter.Content, element))
            {
                contentPresenter.Content = null;
                return true;
            }

            if (parent is ContentControl contentControl &&
                !ReferenceEquals(contentControl, element) &&
                ReferenceEquals(contentControl.Content, element))
            {
                contentControl.Content = null;
                return true;
            }

            if (parent is ItemsControl itemsControl && itemsControl.Items.Contains(element))
            {
                itemsControl.Items.Remove(element);
                return true;
            }

            return false;
        }

        private static void CollapseEmptyAncestorContainers(DependencyObject start)
        {
            for (DependencyObject current = start; current != null; current = GetParentObject(current))
            {
                if (!(current is FrameworkElement frameworkElement))
                    continue;

                if (!IsEffectivelyEmptyContainer(frameworkElement))
                    break;

                frameworkElement.Visibility = Visibility.Collapsed;
                frameworkElement.IsEnabled = false;
            }
        }

        private static bool IsEffectivelyEmptyContainer(FrameworkElement element)
        {
            if (element == null || element is ButtonBase || element is TextBlock)
                return false;

            if (element is Panel panel)
                return panel.Children.OfType<UIElement>().All(IsCollapsedOrNull);

            if (element is Decorator decorator)
                return IsCollapsedOrNull(decorator.Child);

            if (element is ContentPresenter contentPresenter)
                return IsCollapsedOrNull(contentPresenter.Content as UIElement);

            if (element is ContentControl contentControl)
            {
                if (contentControl.Content is UIElement childElement)
                    return IsCollapsedOrNull(childElement);

                return string.IsNullOrWhiteSpace(GetMenuHeaderText(contentControl.Content));
            }

            if (element is ItemsControl itemsControl)
                return itemsControl.Items.OfType<UIElement>().All(IsCollapsedOrNull);

            return false;
        }

        private static bool IsCollapsedOrNull(UIElement element)
        {
            return element == null || element.Visibility != Visibility.Visible;
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
    }
}
