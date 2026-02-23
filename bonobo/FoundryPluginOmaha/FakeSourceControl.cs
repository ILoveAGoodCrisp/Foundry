using Bonobo.PluginSystem;
using Bonobo.PluginSystem.Custom;
using Bungie.Reactive;
using Corinth.Connections;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace FoundryPlugin
{
    [BonoboPlugin("Foundry Fake Source Control", Priority = InitializationPriority.Normal)]
    public class FoundryFakeSourceControl :
        BonoboPlugin,
        ISourceControlProvider,
        IAsyncSourceControlProvider,
        ISourceControlMenuProvider
    {
        private static readonly IReadOnlyList<string> CheckedOutByString =
            new List<string>() { "You" };

        private readonly Dictionary<string, DateTime> _initialWriteTimes =
            new Dictionary<string, DateTime>(StringComparer.OrdinalIgnoreCase);

        public FoundryFakeSourceControl(IPluginHost host)
            : base(host)
        {
            //System.Windows.MessageBox.Show("Fake SCM Plugin Loaded");
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

        public IEnumerable<string> GetCheckedOutClients(string fileName) => CheckedOutByString;

        public IEnumerable<string> GetFilesNotInDefaultChangelist(IEnumerable<string> fileNames) => CheckedOutByString;

        public int GetLastDepotRevision(string fileName) => 0;

        public bool IsFileOperationAvailable(
            SourceControlOperation operation,
            SourceControlFileState state,
            bool isWritable,
            string file = null)
        {
            switch (operation)
            {
                //case SourceControlOperation.CheckOut:
                //    return !isWritable;

                //case SourceControlOperation.CheckIn:
                //    return isWritable;

                //case SourceControlOperation.UndoCheckOut:
                //    return isWritable;

                //case SourceControlOperation.GetLatest:
                //    return true;

                case SourceControlOperation.Delete:
                    return true;

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
            bool isWritable = false;
            SourceControlFileState state = SourceControlFileState.UpToDate;
            bool fakeWritable = true;

            try
            {
                if (!System.IO.File.Exists(fileName))
                {
                    return new SourceControlFile(
                        fileName,
                        SourceControlFileState.NotInDepot,
                        true,
                        CheckedOutByString,
                        CheckedOutByString,
                        true);
                }

                var attributes = System.IO.File.GetAttributes(fileName);
                isWritable = !attributes.HasFlag(System.IO.FileAttributes.ReadOnly);

                var currentWriteTime = System.IO.File.GetLastWriteTimeUtc(fileName);

                if (!_initialWriteTimes.ContainsKey(fileName))
                {
                    _initialWriteTimes[fileName] = currentWriteTime;
                }

                bool modifiedThisSession =
                    _initialWriteTimes[fileName] != currentWriteTime;

                if (!isWritable)
                {
                    state = SourceControlFileState.UpToDate;
                    fakeWritable = false;
                }
                else if (modifiedThisSession)
                {
                    state = SourceControlFileState.CheckedOutOnThisClient;
                }
                else
                {
                    state = SourceControlFileState.UpToDate;
                    fakeWritable = false;
                }
            }
            catch
            {
                state = SourceControlFileState.Offline;
                isWritable = false;
            }

            return new SourceControlFile(
                fileName,
                state,
                fakeWritable,
                CheckedOutByString,
                CheckedOutByString,
                true);
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