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
    [BonoboPlugin("Foundry Plugin", Priority = InitializationPriority.Normal)]
    public partial class FoundryPlugin :
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


        private static readonly bool EnableCustomTheme = false; // DISABLE/ENABLE THEME

        private static bool _sourceControlToolTipsInstalled;

        public FoundryPlugin(IPluginHost host)
            : base(host)
        {
            ProjectInfo.Initialize();
            InstallSourceControlToolTipOverride();
            InstallContextMenuCleanup();
            InstallRenderModelDropButtonOverride();
            InstallXboxUiCleanup();
            SuppressSourceControlStyles();

            if (EnableCustomTheme)
                InstallWindowThemeRefresh();
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
                SourceControlFileState.UpToDate,
                false,
                EmptyClientList,
                EmptyClientList,
                true);
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
