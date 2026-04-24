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
                "XDrop tag in game",
                "Diff vs Previous...",
                "Revision History"
            };

        private static readonly string[] TagFileMenuMarkers =
        {
            "Open in Tag view",
            "Open in Grid view",
            "Copy Paths"
        };

        private static readonly string[] FolderMenuMarkers =
        {
            "Get Latest",
            "Force Get Latest",
            "Check Out",
            "Scratch Check Out"
        };

        private static bool _contextMenuCleanupInstalled;

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

        private static void OnContextMenuOpened(object sender, RoutedEventArgs e)
        {
            var contextMenu = sender as ContextMenu;
            if (contextMenu == null)
                return;

            PruneSourceControlContextMenu(contextMenu);
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
    }
}
