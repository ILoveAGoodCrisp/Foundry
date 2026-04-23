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
            script = null;

            string buttonText = GetDropButtonText(button);
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

        private static bool TryBuildDropButtonToolTip(ButtonBase button, out string toolTip)
        {
            toolTip = null;

            string buttonText = GetDropButtonText(button);
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

        private static bool IsClipboardDropButtonText(string buttonText)
        {
            return buttonText.Equals("Drop Variant", StringComparison.OrdinalIgnoreCase) ||
                buttonText.Equals("Drop Permutation", StringComparison.OrdinalIgnoreCase);
        }

        private static string GetDropButtonText(ButtonBase button)
        {
            return GetMenuHeaderText(GetReadablePropertyValue(button, "Content"));
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
