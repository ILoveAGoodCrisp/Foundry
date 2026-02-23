using Bonobo.PluginSystem;
using Bonobo.PluginSystem.Custom;
using Bungie.Reactive;
using Bungie.Utilities;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Media.Imaging;

namespace FoundryPlugin
{
    [BonoboPlugin("Foundry Open In Blender Plugin")]
    public class OpenInBlenderPlugin : BonoboPlugin, IFileActionProvider
    {
        public OpenInBlenderPlugin(IPluginHost host) : base(host)
        {
            ProjectInfo.Initialize();
        }

        public IEnumerable<IFileAction> GetActions(IEnumerable<FileActionParameters> files)
        {
            if (!ProjectInfo.IsValid)
                yield break;

            var paths = files.Select(f => f.FileName);

            yield return new OpenInBlenderAction(paths);
        }
    }

    public class OpenInBlenderAction : IFileAction
    {
        private readonly List<string> _paths;

        private static readonly IWeakEvent<FileActionEventArgs> EmptyEvent =
            new EmptyWeakEvent<FileActionEventArgs>();

        public OpenInBlenderAction(IEnumerable<string> paths)
        {
            _paths = paths != null
                ? new List<string>(paths)
                : new List<string>();
        }

        public string Name => "OpenInBlender";
        public string DisplayName => "Open in Blender";

        public string GroupName => "Foundry";
        public float GroupPriority => 100f;
        public float PriorityInGroup => 0f;


        public bool IsEnabled => _paths.Count > 0;
        public bool IsChecked => false;
        public bool HasChildren => false;

        public IEnumerable<IFileAction> Children => Enumerable.Empty<IFileAction>();

        public IEnumerable<string> FilePaths
            => _paths ?? Enumerable.Empty<string>();


        public BitmapImage IconImage => LoadBitmap("pack://application:,,,/FoundryPlugin;component/blender.ico");

        private BitmapImage LoadBitmap(string path)
        {
            try
            {
                BitmapImage bitmapImage = new BitmapImage();
                bitmapImage.BeginInit();
                bitmapImage.UriSource = new Uri(path);
                bitmapImage.EndInit();
                return bitmapImage;
            }
            catch (Exception ex)
            {
                MessageBox.Show("Error loading image: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Hand);
                return null;
            }
        }

        public IWeakEvent<FileActionEventArgs> FileActionStarting => EmptyEvent;
        public IWeakEvent<FileActionEventArgs> FileActionFinished => EmptyEvent;

        public void Invoke()
        {
            RunBlender();
        }

        private void RunBlender()
        {
            string blenderPath = ProjectInfo.BlenderPath;
            string tagsRoot = ProjectInfo.TagsRoot;
            string dataRoot = ProjectInfo.DataRoot;

            if (string.IsNullOrWhiteSpace(blenderPath) || !File.Exists(blenderPath))
            {
                MessageBox.Show(
                    $"Blender executable not found:\n{blenderPath}",
                    "Blender Launch Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);

                return;
            }

            if (string.IsNullOrWhiteSpace(tagsRoot) ||
                string.IsNullOrWhiteSpace(dataRoot))
            {
                MessageBox.Show(
                    "Project roots are not initialized.",
                    "Blender Launch Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);

                return;
            }

            if (_paths.Count == 0)
                return;

            string firstSelection = _paths[0];

            if (string.IsNullOrWhiteSpace(firstSelection))
                return;

            string tagDirectory = Directory.Exists(firstSelection) ? firstSelection : Path.GetDirectoryName(firstSelection);

            if (string.IsNullOrWhiteSpace(tagDirectory))
                return;

            if (!tagDirectory.StartsWith(tagsRoot, StringComparison.OrdinalIgnoreCase))
                return;

            string relativePath = tagDirectory.Substring(tagsRoot.Length).TrimStart(Path.DirectorySeparatorChar);

            string dataDirectory = Path.Combine(dataRoot, relativePath);

            if (!Directory.Exists(dataDirectory))
            {
                MessageBox.Show(
                    $"Tag Data equivalent not found for:\n{firstSelection}",
                    "Blend File Not Found",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);

                return;
            }

            string blendFile = FindBlendFromSidecar(dataDirectory, dataRoot);

            if (string.IsNullOrWhiteSpace(blendFile))
            {
                MessageBox.Show(
                    $"Cannot locate blend for tag:\n{firstSelection}",
                    "Blend File Not Found",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);

                return;
            }

            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = blenderPath,
                    Arguments = $"\"{blendFile}\"",
                    UseShellExecute = false
                });
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"Failed to launch Blender:\n\n{ex.Message}",
                    "Blender Launch Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);
            }
        }

        private string FindBlendFromSidecar(string startDirectory, string dataRoot)
        {
            DirectoryInfo dir = new DirectoryInfo(startDirectory);

            while (dir != null &&
                    dir.FullName.StartsWith(dataRoot, StringComparison.OrdinalIgnoreCase))
            {
                string sidecarPath = Path.Combine(dir.FullName, dir.Name + ".sidecar.xml");

                if (File.Exists(sidecarPath))
                {
                    return ResolveBlendFromSidecar(sidecarPath, dataRoot);
                }

                dir = dir.Parent;
            }

            return null;
        }

        private string ResolveBlendFromSidecar(string sidecarPath, string currentDataDirectory)
        {
            try
            {
                var doc = System.Xml.Linq.XDocument.Load(sidecarPath);

                var sourceBlendElement =
                    doc.Root?
                        .Element("Header")?
                        .Element("SourceBlend");

                if (sourceBlendElement == null)
                    return null;

                string sourceBlend = sourceBlendElement.Value?.Trim();

                if (string.IsNullOrWhiteSpace(sourceBlend))
                    return null;

                // If a full path (i.e. not in the data dir)
                if (Path.IsPathRooted(sourceBlend))
                {
                    return File.Exists(sourceBlend) ? sourceBlend : null;
                }

                string combined = Path.Combine(currentDataDirectory, sourceBlend);

                return File.Exists(combined) ? combined : null;
            }
            catch (Exception ex)
            {
                Log.Warn($"Failed reading sidecar: {sidecarPath} - {ex.Message}");
                return null;
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