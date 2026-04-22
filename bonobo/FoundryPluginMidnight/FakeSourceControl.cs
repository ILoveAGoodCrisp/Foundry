using Bonobo.PluginSystem;
using Bonobo.PluginSystem.Custom;
using Corinth.Reactive;
using Corinth.Connections;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows;
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
        private static readonly IReadOnlyList<string> EmptyClientList =
            new List<string>();

        public FoundryFakeSourceControl(IPluginHost host)
            : base(host)
        {
            //System.Windows.MessageBox.Show("Fake SCM Plugin Loaded");
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
                SourceControlFileState.UpToDate,
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

    }
}
