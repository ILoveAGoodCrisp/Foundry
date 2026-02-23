using Bonobo.PluginSystem;
using Bonobo.PluginSystem.Custom;
using Corinth.Utilities;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Media.Imaging;

namespace FoundryPlugin
{
    [BonoboPlugin("Foundry Copy Relative Path Plugin")]
    public class CopyRelativePathPlugin : BonoboPlugin, IFileActionProvider
    {
        public CopyRelativePathPlugin(IPluginHost host) : base(host)
        {
            
        }

        public IEnumerable<IFileAction> GetActions(IEnumerable<FileActionParameters> files)
        {
            if (!ProjectInfo.IsValid)
                yield break;

            var paths = files.Select(f => f.FileName);

            yield return new CopyRelativePathAction(paths);
        }

        public class CopyRelativePathAction : IFileAction
        {
            private readonly List<string> _paths;

            private static readonly IWeakEvent<FileActionEventArgs> EmptyEvent =
                new EmptyWeakEvent<FileActionEventArgs>();

            public CopyRelativePathAction(IEnumerable<string> paths)
            {
                _paths = paths != null
                    ? new List<string>(paths)
                    : new List<string>();
            }

            public string Name => "CopyRelativePath";
            public string DisplayName => "Copy Relative Path";

            public string GroupName => "Foundry";
            public float GroupPriority => 100f;
            public float PriorityInGroup => 1f;


            public bool IsEnabled => _paths.Count > 0;
            public bool IsChecked => false;
            public bool HasChildren => false;

            public IEnumerable<IFileAction> Children => Enumerable.Empty<IFileAction>();

            public IEnumerable<string> FilePaths
                => _paths ?? Enumerable.Empty<string>();

            public IWeakEvent<FileActionEventArgs> FileActionStarting => EmptyEvent;
            public IWeakEvent<FileActionEventArgs> FileActionFinished => EmptyEvent;

            BitmapImage IFileAction.IconImage => null;

            public void Invoke()
            {
                GetRelativePath();
            }

            private void GetRelativePath()
            {
                string tagsRoot = ProjectInfo.TagsRoot;

                if (_paths.Count == 0)
                    return;

                string firstSelection = _paths[0];

                if (string.IsNullOrWhiteSpace(firstSelection))
                    return;

                string relativePath = firstSelection.Substring(tagsRoot.Length).TrimStart(Path.DirectorySeparatorChar);

                Clipboard.SetText(relativePath);
            }

        }

            private class EmptyWeakEvent<T> : IWeakEvent<T>
            {
                public IDisposable Subscribe(IObserver<T> observer)
                {
                    return new DummyDisposable();
                }

                public void Subscribe(Action<T> action)
                {
                }

                public void Unsubscribe(Action<T> action)
                {
                }

                private class DummyDisposable : IDisposable
                {
                    public void Dispose() { }
                }
            }
        }

    }