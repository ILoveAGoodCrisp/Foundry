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
        private static readonly Brush ThemeWindowBrush = CreateFrozenBrush(0x1F, 0x1F, 0x1F);
        private static readonly Brush ThemePanelBrush = CreateFrozenBrush(0x24, 0x24, 0x24);
        private static readonly Brush ThemeBlockBrush = CreateFrozenBrush(0x2A, 0x2A, 0x2A);
        private static readonly Brush ThemeHeaderBrush = CreateFrozenBrush(0x31, 0x31, 0x31);
        private static readonly Brush ThemeControlBrush = CreateFrozenBrush(0x38, 0x38, 0x38);
        private static readonly Brush ThemeInputBrush = CreateFrozenBrush(0x2E, 0x2E, 0x2E);
        private static readonly Brush ThemePressedBrush = CreateFrozenBrush(0x4C, 0x78, 0xC2);
        private static readonly Brush ThemeBorderBrush = CreateFrozenBrush(0x4A, 0x4A, 0x4A);
        private static readonly Brush ThemeTextBrush = CreateFrozenBrush(0xE8, 0xE8, 0xE8);
        private static readonly Brush ThemeMutedTextBrush = CreateFrozenBrush(0xB8, 0xB8, 0xB8);
        private static readonly Brush ThemeAccentBrush = CreateFrozenBrush(0x63, 0x91, 0xE6);
        private static readonly Brush ThemeTealBrush = CreateFrozenBrush(0x4E, 0xC9, 0xB0);
        private static readonly Brush ThemeOrangeBrush = CreateFrozenBrush(0xD1, 0x9A, 0x66);
        private static readonly Brush ThemeGreyHighlightBrush = CreateFrozenBrush(0x4A, 0x4A, 0x4A);
        private static readonly Thickness ThemeButtonPadding = new Thickness(8, 2, 8, 2);

        private static bool _windowThemeRefreshInstalled;
        private static BitmapImage _bonoboSplashImage;
        private static string _bonoboSplashImagePath;

        private enum ThemeSurfaceKind
        {
            Default,
            Header,
            Block,
            Field
        }

        private static void SuppressSourceControlStyles()
        {
            var application = Application.Current;
            if (application == null)
                return;

            ApplyApplicationStyleOverrides(application);
            application.Dispatcher.BeginInvoke(
                new Action(() => ApplyApplicationStyleOverrides(application)),
                DispatcherPriority.ApplicationIdle);
        }

        private static void InstallWindowThemeRefresh()
        {
            if (_windowThemeRefreshInstalled)
                return;

            EventManager.RegisterClassHandler(
                typeof(FrameworkElement),
                FrameworkElement.LoadedEvent,
                new RoutedEventHandler(OnFrameworkElementLoaded),
                true);

            EventManager.RegisterClassHandler(
                typeof(Window),
                FrameworkElement.LoadedEvent,
                new RoutedEventHandler(OnWindowLoaded),
                true);

            _windowThemeRefreshInstalled = true;
        }

        private static void ApplyApplicationStyleOverrides(Application application)
        {
            ApplySourceControlStyleOverrides(application);

            if (EnableCustomTheme)
                ApplyDarkThemeOverrides(application);
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

        private static void ApplyDarkThemeOverrides(Application application)
        {
            if (application.Resources == null)
                return;

            ApplyDarkSystemColorOverrides(application.Resources);
            ApplyDarkBungieResourceOverrides(application);
            ApplyDarkControlStyles(application.Resources);

            foreach (Window window in application.Windows.OfType<Window>())
                ApplyDarkThemeToWindow(window);
        }

        private static void ApplyDarkSystemColorOverrides(ResourceDictionary resources)
        {
            resources[SystemColors.WindowBrushKey] = ThemeWindowBrush;
            resources[SystemColors.WindowTextBrushKey] = ThemeTextBrush;
            resources[SystemColors.ControlBrushKey] = ThemeControlBrush;
            resources[SystemColors.ControlTextBrushKey] = ThemeTextBrush;
            resources[SystemColors.ControlDarkBrushKey] = ThemeBorderBrush;
            resources[SystemColors.ControlDarkDarkBrushKey] = ThemeBorderBrush;
            resources[SystemColors.ControlLightBrushKey] = ThemeHeaderBrush;
            resources[SystemColors.ControlLightLightBrushKey] = ThemeHeaderBrush;
            resources[SystemColors.GrayTextBrushKey] = ThemeMutedTextBrush;
            resources[SystemColors.HighlightBrushKey] = ThemePressedBrush;
            resources[SystemColors.HighlightTextBrushKey] = ThemeTextBrush;
            resources[SystemColors.InactiveSelectionHighlightBrushKey] = ThemePressedBrush;
            resources[SystemColors.InactiveSelectionHighlightTextBrushKey] = ThemeTextBrush;
            resources[SystemColors.HotTrackBrushKey] = ThemeAccentBrush;
            resources[SystemColors.InfoBrushKey] = ThemeBlockBrush;
            resources[SystemColors.InfoTextBrushKey] = ThemeTextBrush;
            resources[SystemColors.MenuBrushKey] = ThemePanelBrush;
            resources[SystemColors.MenuTextBrushKey] = ThemeTextBrush;
        }

        private static void ApplyDarkBungieResourceOverrides(Application application)
        {
            SetResourceByStaticField(application, GetColorResourcesType(), "DefaultGroupBorderBrushKey", ThemeBorderBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "DefaultCustomGroupBorderBrushKey", ThemeBorderBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "DefaultFocusedTabBackgroundBrushKey", ThemePressedBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "HaloDarkBlueColorKey", ThemeWindowBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "HaloMediumBlueColorKey", ThemeAccentBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "HaloOrangeHighlightColorKey", ThemeOrangeBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "HaloTealHighlightColorKey", ThemeTealBrush);
            SetResourceByStaticField(application, GetColorResourcesType(), "HaloGreyHighlightColorKey", ThemeGreyHighlightBrush);
        }

        private static void ApplyDarkControlStyles(ResourceDictionary resources)
        {
            resources[typeof(Window)] = CreateStyle(
                typeof(Window),
                new Setter(Window.BackgroundProperty, ThemeWindowBrush),
                new Setter(Window.ForegroundProperty, ThemeTextBrush));

            resources[typeof(Border)] = CreateStyle(
                typeof(Border),
                new Setter(Border.BackgroundProperty, ThemeBlockBrush),
                new Setter(Border.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(Grid)] = CreateStyle(
                typeof(Grid),
                new Setter(Panel.BackgroundProperty, ThemeWindowBrush));

            resources[typeof(DockPanel)] = CreateStyle(
                typeof(DockPanel),
                new Setter(Panel.BackgroundProperty, ThemeWindowBrush));

            resources[typeof(StackPanel)] = CreateStyle(
                typeof(StackPanel),
                new Setter(Panel.BackgroundProperty, ThemeWindowBrush));

            resources[typeof(WrapPanel)] = CreateStyle(
                typeof(WrapPanel),
                new Setter(Panel.BackgroundProperty, ThemeWindowBrush));

            resources[typeof(Canvas)] = CreateStyle(
                typeof(Canvas),
                new Setter(Panel.BackgroundProperty, ThemeWindowBrush));

            resources[typeof(TextBlock)] = CreateStyle(
                typeof(TextBlock),
                new Setter(TextBlock.ForegroundProperty, ThemeTextBrush));

            resources[typeof(TextBox)] = CreateStyle(
                typeof(TextBox),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(TextBoxBase.SelectionBrushProperty, ThemePressedBrush),
                new Setter(TextBoxBase.SelectionTextBrushProperty, ThemeTextBrush),
                new Setter(TextBoxBase.CaretBrushProperty, ThemeTextBrush));

            resources[typeof(RichTextBox)] = CreateStyle(
                typeof(RichTextBox),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(TextBoxBase.SelectionBrushProperty, ThemePressedBrush),
                new Setter(TextBoxBase.SelectionTextBrushProperty, ThemeTextBrush),
                new Setter(TextBoxBase.CaretBrushProperty, ThemeTextBrush));

            resources[typeof(Label)] = CreateStyle(
                typeof(Label),
                new Setter(Control.ForegroundProperty, ThemeTextBrush));

            resources[typeof(Button)] = CreateStyle(
                typeof(Button),
                new Setter(Control.BackgroundProperty, ThemeControlBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(Control.FocusVisualStyleProperty, null),
                new Setter(Control.PaddingProperty, ThemeButtonPadding));

            resources[typeof(ToggleButton)] = CreateStyleWithTrigger(
                typeof(ToggleButton),
                ToggleButton.IsCheckedProperty,
                true,
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemeControlBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                    new Setter(Control.FocusVisualStyleProperty, null),
                    new Setter(Control.PaddingProperty, ThemeButtonPadding)
                },
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePressedBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeAccentBrush)
                });

            resources[typeof(CheckBox)] = CreateStyle(
                typeof(CheckBox),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush));

            resources[typeof(RadioButton)] = CreateStyle(
                typeof(RadioButton),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush));

            resources[typeof(TextBoxBase)] = CreateStyle(
                typeof(TextBoxBase),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(TextBoxBase.SelectionBrushProperty, ThemePressedBrush),
                new Setter(TextBoxBase.SelectionTextBrushProperty, ThemeTextBrush),
                new Setter(TextBoxBase.CaretBrushProperty, ThemeTextBrush));

            resources[typeof(PasswordBox)] = CreateStyle(
                typeof(PasswordBox),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(PasswordBox.CaretBrushProperty, ThemeTextBrush));

            resources[typeof(ComboBox)] = CreateStyle(
                typeof(ComboBox),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(Control.FocusVisualStyleProperty, null));

            resources[typeof(ComboBoxItem)] = CreateStyleWithTrigger(
                typeof(ComboBoxItem),
                ComboBoxItem.IsSelectedProperty,
                true,
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePanelBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemePanelBrush)
                },
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePressedBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeAccentBrush)
                });

            resources[typeof(ListBox)] = CreateStyle(
                typeof(ListBox),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(ListBoxItem)] = CreateStyleWithTrigger(
                typeof(ListBoxItem),
                ListBoxItem.IsSelectedProperty,
                true,
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePanelBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemePanelBrush)
                },
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePressedBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeAccentBrush)
                });

            resources[typeof(ListView)] = CreateStyle(
                typeof(ListView),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(ListViewItem)] = CreateStyleWithTrigger(
                typeof(ListViewItem),
                ListViewItem.IsSelectedProperty,
                true,
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePanelBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemePanelBrush)
                },
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePressedBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeAccentBrush)
                });

            resources[typeof(TreeView)] = CreateStyle(
                typeof(TreeView),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(TreeViewItem)] = CreateStyleWithTrigger(
                typeof(TreeViewItem),
                TreeViewItem.IsSelectedProperty,
                true,
                new[]
                {
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BackgroundProperty, ThemePanelBrush),
                    new Setter(Control.BorderBrushProperty, ThemePanelBrush)
                },
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePressedBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeAccentBrush)
                });

            resources[typeof(Menu)] = CreateStyle(
                typeof(Menu),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush));

            resources[typeof(MenuItem)] = CreateStyleWithTrigger(
                typeof(MenuItem),
                MenuItem.IsHighlightedProperty,
                true,
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePanelBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemePanelBrush)
                },
                new[]
                {
                    new Setter(Control.BackgroundProperty, ThemePressedBrush),
                    new Setter(Control.ForegroundProperty, ThemeTextBrush),
                    new Setter(Control.BorderBrushProperty, ThemeAccentBrush)
                });

            resources[typeof(ContextMenu)] = CreateStyle(
                typeof(ContextMenu),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(ToolTip)] = CreateStyle(
                typeof(ToolTip),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(TabControl)] = CreateStyle(
                typeof(TabControl),
                new Setter(Control.BackgroundProperty, ThemeWindowBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(TabItem)] = CreateStyle(
                typeof(TabItem),
                new Setter(Control.BackgroundProperty, ThemeHeaderBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(Control.FocusVisualStyleProperty, null));

            resources[typeof(GroupBox)] = CreateStyle(
                typeof(GroupBox),
                new Setter(Control.BackgroundProperty, ThemeBlockBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(Expander)] = CreateStyle(
                typeof(Expander),
                new Setter(Control.BackgroundProperty, ThemeBlockBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(StatusBar)] = CreateStyle(
                typeof(StatusBar),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            resources[typeof(ScrollViewer)] = CreateStyle(
                typeof(ScrollViewer),
                new Setter(Control.BackgroundProperty, ThemePanelBrush));

            resources[typeof(DataGrid)] = CreateStyle(
                typeof(DataGrid),
                new Setter(Control.BackgroundProperty, ThemeControlBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush),
                new Setter(DataGrid.GridLinesVisibilityProperty, DataGridGridLinesVisibility.Horizontal),
                new Setter(DataGrid.HorizontalGridLinesBrushProperty, ThemeBorderBrush),
                new Setter(DataGrid.VerticalGridLinesBrushProperty, ThemeBorderBrush),
                new Setter(DataGrid.RowBackgroundProperty, ThemeControlBrush),
                new Setter(DataGrid.AlternatingRowBackgroundProperty, ThemePanelBrush),
                new Setter(DataGrid.HeadersVisibilityProperty, DataGridHeadersVisibility.All));

            resources[typeof(DataGridCell)] = CreateStyle(
                typeof(DataGridCell),
                new Setter(Control.BackgroundProperty, ThemeControlBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            TryAddImplicitStyle(
                resources,
                GetBungieWpfType("SearchBox"),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            TryAddImplicitStyle(
                resources,
                GetBungieWpfType("SliderBox"),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            TryAddImplicitStyle(
                resources,
                GetBungieWpfType("ReferenceBlock"),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            TryAddImplicitStyle(
                resources,
                GetBungieWpfType("ReferenceBox"),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            TryAddImplicitStyle(
                resources,
                GetBungieWpfType("SurrogateTextBox"),
                new Setter(Control.BackgroundProperty, ThemeInputBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));

            TryAddImplicitStyle(
                resources,
                GetBungieWpfType("ViewSelector"),
                new Setter(Control.BackgroundProperty, ThemePanelBrush),
                new Setter(Control.ForegroundProperty, ThemeTextBrush),
                new Setter(Control.BorderBrushProperty, ThemeBorderBrush));
        }

        private static void ApplyDarkThemeToWindow(Window window)
        {
            if (window == null)
                return;

            window.Background = ThemeWindowBrush;
            window.Foreground = ThemeTextBrush;

            ApplyDarkThemeToVisualTree(window);
            window.Dispatcher.BeginInvoke(
                new Action(() => ApplyDarkThemeToVisualTree(window)),
                DispatcherPriority.ApplicationIdle);
        }

        private static void OnWindowLoaded(object sender, RoutedEventArgs e)
        {
            var application = Application.Current;
            if (application == null)
                return;

            ApplyApplicationStyleOverrides(application);

            if (EnableCustomTheme)
                ApplyDarkThemeToWindow(sender as Window);
        }

        private static void OnFrameworkElementLoaded(object sender, RoutedEventArgs e)
        {
            if (!EnableCustomTheme)
                return;

            var element = sender as DependencyObject;
            if (element == null)
                return;

            ApplyDarkThemeToVisualTree(element);
        }

        private static void ApplyDarkThemeToVisualTree(DependencyObject root)
        {
            if (root == null)
                return;

            ApplyDarkThemeToVisualTree(
                root,
                new HashSet<DependencyObject>());
        }

        private static void ApplyDarkThemeToVisualTree(
            DependencyObject current,
            HashSet<DependencyObject> visited)
        {
            if (current == null || !visited.Add(current))
                return;

            ApplyDarkThemeToElement(current);

            foreach (DependencyObject child in EnumerateChildObjects(current))
                ApplyDarkThemeToVisualTree(child, visited);
        }

        private static IEnumerable<DependencyObject> EnumerateChildObjects(DependencyObject parent)
        {
            int visualChildrenCount = 0;
            try
            {
                visualChildrenCount = VisualTreeHelper.GetChildrenCount(parent);
            }
            catch
            {
            }

            for (int index = 0; index < visualChildrenCount; index++)
                yield return VisualTreeHelper.GetChild(parent, index);

            foreach (object child in LogicalTreeHelper.GetChildren(parent).OfType<object>())
            {
                var dependencyObject = child as DependencyObject;
                if (dependencyObject != null)
                    yield return dependencyObject;
            }

            var frameworkElement = parent as FrameworkElement;
            if (frameworkElement?.ContextMenu != null)
                yield return frameworkElement.ContextMenu;
        }

        private static void ApplyDarkThemeToElement(DependencyObject element)
        {
            var image = element as Image;
            if (image != null)
            {
                TryApplyBonoboSplashImage(image);
                return;
            }

            ThemeSurfaceKind surfaceKind = GetThemeSurfaceKind(element);
            ApplyCustomBrushProperties(element, surfaceKind);

            var shape = element as System.Windows.Shapes.Shape;
            if (shape != null)
            {
                ApplyGlyphTheme(shape, element);
                return;
            }

            if (element is Border border)
            {
                if (ShouldKeepTransparentBackground(border))
                    border.Background = Brushes.Transparent;
                else if (surfaceKind != ThemeSurfaceKind.Default || ShouldUseDarkBackground(border.Background))
                    border.Background = GetSurfaceBrush(surfaceKind, ThemeBlockBrush);

                border.BorderBrush = ThemeBorderBrush;
            }

            if (element is Panel panel)
            {
                if (!ShouldKeepTransparentBackground(panel) &&
                    (surfaceKind != ThemeSurfaceKind.Default || ShouldUseDarkBackground(panel.Background)))
                    panel.Background = surfaceKind == ThemeSurfaceKind.Field
                        ? ThemePanelBrush
                        : GetSurfaceBrush(surfaceKind, ThemeWindowBrush);
            }

            if (element is TextBlock textBlock)
                textBlock.Foreground = ThemeTextBrush;

            if (element is TextElement textElement)
                textElement.Foreground = ThemeTextBrush;

            if (element is TextBoxBase textBoxBase)
            {
                textBoxBase.Background = ThemeInputBrush;
                textBoxBase.Foreground = ThemeTextBrush;
                textBoxBase.BorderBrush = ThemeBorderBrush;
                textBoxBase.SelectionBrush = ThemePressedBrush;
                textBoxBase.SelectionTextBrush = ThemeTextBrush;
                textBoxBase.CaretBrush = ThemeTextBrush;
            }

            var passwordBox = element as PasswordBox;
            if (passwordBox != null)
            {
                passwordBox.Background = ThemeInputBrush;
                passwordBox.Foreground = ThemeTextBrush;
                passwordBox.BorderBrush = ThemeBorderBrush;
                passwordBox.CaretBrush = ThemeTextBrush;
            }

            var control = element as Control;
            if (control == null)
                return;

            control.Foreground = ThemeTextBrush;

            if (control is Label)
            {
                control.Background = Brushes.Transparent;
                return;
            }

            if (ApplyAccentSelectionTheme(control))
                return;

            if (control is ButtonBase)
            {
                control.Background = IsTopBarElement(control) ? ThemeInputBrush : ThemeControlBrush;
                control.BorderBrush = ThemeBorderBrush;
                return;
            }

            if (control is Menu || control is MenuItem || control is ContextMenu || control is ToolTip)
            {
                control.Background = ThemePanelBrush;
                control.BorderBrush = ThemeBorderBrush;
                return;
            }

            if (control is TreeView || control is ListView || control is ListBox || control is DataGrid)
            {
                control.Background = ThemePanelBrush;
                control.BorderBrush = ThemeBorderBrush;
                return;
            }

            if (control is GroupBox || control is Expander || control is StatusBar || control is TabControl || control is TabItem)
            {
                control.Background = control is TabControl
                    ? ThemeWindowBrush
                    : ThemeHeaderBrush;
                control.BorderBrush = ThemeBorderBrush;
                return;
            }

            if (control is ComboBox)
            {
                control.Background = IsTopBarElement(control) ? ThemeWindowBrush : ThemeInputBrush;
                control.BorderBrush = ThemeBorderBrush;
                return;
            }

            if (control is ScrollViewer)
            {
                control.Background = ThemePanelBrush;
                return;
            }

            if (surfaceKind != ThemeSurfaceKind.Default || ShouldUseDarkBackground(control.Background))
                control.Background = GetSurfaceBrush(surfaceKind, ThemeWindowBrush);

            control.BorderBrush = ThemeBorderBrush;
        }

        private static bool ShouldUseDarkBackground(Brush brush)
        {
            if (brush == null)
                return true;

            if (TryGetBrushLightness(brush, out double lightness))
                return lightness > 0.42;

            return true;
        }

        private static bool ShouldUseLightForeground(Brush brush)
        {
            if (brush == null)
                return true;

            if (TryGetBrushLightness(brush, out double lightness))
                return lightness < 0.7;

            return true;
        }

        private static bool TryGetBrushLightness(Brush brush, out double lightness)
        {
            var solidColorBrush = brush as SolidColorBrush;
            if (solidColorBrush != null)
            {
                lightness = GetPerceivedLightness(solidColorBrush.Color);
                return true;
            }

            var gradientBrush = brush as GradientBrush;
            if (gradientBrush != null && gradientBrush.GradientStops.Count > 0)
            {
                lightness = gradientBrush.GradientStops
                    .Average(stop => GetPerceivedLightness(stop.Color));
                return true;
            }

            lightness = 0;
            return false;
        }

        private static double GetPerceivedLightness(Color color)
        {
            return ((0.299 * color.R) + (0.587 * color.G) + (0.114 * color.B)) / 255.0;
        }

        private static Type GetIconResourcesType()
        {
            return Type.GetType("Bungie.UI.Wpf.IconResources, Bungie.Core.Wpf")
                ?? Type.GetType("Corinth.UI.Wpf.IconResources, Corinth.Core.Wpf");
        }

        private static Type GetColorResourcesType()
        {
            return Type.GetType("Bungie.UI.Wpf.ColorResources, Bungie.Core.Wpf")
                ?? Type.GetType("Corinth.UI.Wpf.ColorResources, Corinth.Core.Wpf");
        }

        private static Type GetButtonResourcesType()
        {
            return Type.GetType("Bungie.UI.Wpf.ButtonResources, Bungie.Core.Wpf")
                ?? Type.GetType("Corinth.UI.Wpf.ButtonResources, Corinth.Core.Wpf");
        }

        private static Type GetBungieWpfType(string shortTypeName)
        {
            if (string.IsNullOrWhiteSpace(shortTypeName))
                return null;

            return Type.GetType($"Bungie.UI.Wpf.{shortTypeName}, Bungie.Core.Wpf")
                ?? Type.GetType($"Corinth.UI.Wpf.{shortTypeName}, Corinth.Core.Wpf");
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

        private static void SetResourceByStaticField(
            Application application,
            Type resourceOwnerType,
            string fieldName,
            object value)
        {
            if (application?.Resources == null || resourceOwnerType == null)
                return;

            object key = GetStaticFieldValue(resourceOwnerType, fieldName);
            if (key != null)
                application.Resources[key] = value;
        }

        private static Style CreateStyle(Type targetType, params Setter[] setters)
        {
            var style = new Style(targetType);
            foreach (Setter setter in setters)
                style.Setters.Add(setter);

            return style;
        }

        private static Style CreateStyleWithTrigger(
            Type targetType,
            DependencyProperty property,
            object value,
            Setter[] baseSetters,
            Setter[] triggerSetters)
        {
            var style = CreateStyle(targetType, baseSetters);
            var trigger = new Trigger
            {
                Property = property,
                Value = value
            };

            foreach (Setter setter in triggerSetters)
                trigger.Setters.Add(setter);

            style.Triggers.Add(trigger);
            return style;
        }

        private static void TryAddImplicitStyle(ResourceDictionary resources, Type targetType, params Setter[] setters)
        {
            if (resources == null || targetType == null)
                return;

            resources[targetType] = CreateStyle(targetType, setters);
        }

        private static ThemeSurfaceKind GetThemeSurfaceKind(DependencyObject element)
        {
            var frameworkElement = element as FrameworkElement;
            string typeName = element?.GetType().Name ?? string.Empty;
            string elementName = frameworkElement?.Name ?? string.Empty;

            if (ContainsThemeHint(typeName, elementName, "Header", "Caption", "Status", "Toolbar", "Tab", "ViewSelector"))
                return ThemeSurfaceKind.Header;

            if (ContainsThemeHint(
                typeName,
                elementName,
                "TagField",
                "Field",
                "Editor",
                "SearchBox",
                "SliderBox",
                "TextBox",
                "ReferenceBox",
                "ReferenceBlock",
                "SurrogateTextBox",
                "ColorHexBox",
                "ComboBox"))
                return ThemeSurfaceKind.Field;

            if (ContainsThemeHint(typeName, elementName, "Block", "Struct", "Group", "Section", "Expander"))
                return ThemeSurfaceKind.Block;

            return ThemeSurfaceKind.Default;
        }

        private static bool ContainsThemeHint(string typeName, string elementName, params string[] hints)
        {
            foreach (string hint in hints)
            {
                if (!string.IsNullOrEmpty(typeName) && typeName.IndexOf(hint, StringComparison.OrdinalIgnoreCase) >= 0)
                    return true;

                if (!string.IsNullOrEmpty(elementName) && elementName.IndexOf(hint, StringComparison.OrdinalIgnoreCase) >= 0)
                    return true;
            }

            return false;
        }

        private static Brush GetSurfaceBrush(ThemeSurfaceKind surfaceKind, Brush fallback)
        {
            switch (surfaceKind)
            {
                case ThemeSurfaceKind.Header:
                    return ThemeHeaderBrush;
                case ThemeSurfaceKind.Block:
                    return ThemeBlockBrush;
                case ThemeSurfaceKind.Field:
                    return ThemeInputBrush;
                default:
                    return fallback;
            }
        }

        private static void ApplyCustomBrushProperties(DependencyObject element, ThemeSurfaceKind surfaceKind)
        {
            Brush foreground = TryGetBrushPropertyValue(element, "Foreground");
            if (ShouldUseLightForeground(foreground))
                TrySetBrushPropertyValue(element, "Foreground", ThemeTextBrush);

            if (ShouldKeepTransparentBackground(element))
            {
                TrySetBrushPropertyValue(element, "Background", Brushes.Transparent);
                return;
            }

            Brush background = TryGetBrushPropertyValue(element, "Background");
            if (surfaceKind != ThemeSurfaceKind.Default || ShouldUseDarkBackground(background))
                TrySetBrushPropertyValue(element, "Background", GetSurfaceBrush(surfaceKind, ThemeWindowBrush));

            if (TryGetBrushPropertyValue(element, "BorderBrush") != null || HasBrushProperty(element, "BorderBrush"))
                TrySetBrushPropertyValue(element, "BorderBrush", ThemeBorderBrush);
        }

        private static void ApplyGlyphTheme(System.Windows.Shapes.Shape shape, DependencyObject element)
        {
            if (shape == null || element == null)
                return;

            if (HasAncestorTypeName(element, "TabItem"))
            {
                if (TryGetBrushLightness(shape.Stroke, out double tabStrokeLightness) && tabStrokeLightness > 0.65)
                    shape.Stroke = ThemeBorderBrush;

                if (TryGetBrushLightness(shape.Fill, out double tabFillLightness) && tabFillLightness > 0.75)
                    shape.Fill = ThemeHeaderBrush;
            }

            if (HasAncestorTypeName(element, "CheckBox", "RadioButton"))
            {
                bool isChecked = HasCheckedAncestorTypeName(element, "CheckBox", "RadioButton");

                if (shape is System.Windows.Shapes.Path ||
                    shape is System.Windows.Shapes.Polyline ||
                    shape is System.Windows.Shapes.Line)
                {
                    Brush glyphBrush = isChecked ? ThemeAccentBrush : ThemeTextBrush;
                    shape.Fill = glyphBrush;
                    shape.Stroke = glyphBrush;
                }
                else
                {
                    if (shape.Fill == null || ShouldUseDarkBackground(shape.Fill))
                        shape.Fill = ThemeInputBrush;

                    shape.Stroke = isChecked ? ThemeAccentBrush : ThemeBorderBrush;
                }

                return;
            }

            if (HasAncestorTypeName(element, "ToggleButton") &&
                HasAncestorTypeName(element, "Expander", "TreeViewItem", "GroupBox"))
            {
                shape.Fill = ThemeTextBrush;
                shape.Stroke = ThemeTextBrush;
            }
        }

        private static bool HasBrushProperty(object target, string propertyName)
        {
            return target?.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public) != null;
        }

        private static Brush TryGetBrushPropertyValue(object target, string propertyName)
        {
            var property = target?.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
            if (property == null || !typeof(Brush).IsAssignableFrom(property.PropertyType) || !property.CanRead)
                return null;

            try
            {
                return property.GetValue(target, null) as Brush;
            }
            catch
            {
                return null;
            }
        }

        private static void TrySetBrushPropertyValue(object target, string propertyName, Brush value)
        {
            var property = target?.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
            if (property == null || !typeof(Brush).IsAssignableFrom(property.PropertyType) || !property.CanWrite)
                return;

            try
            {
                property.SetValue(target, value, null);
            }
            catch
            {
            }
        }

        private static bool ApplyAccentSelectionTheme(Control control)
        {
            if (control == null || control is CheckBox || control is RadioButton)
                return false;

            bool isSelected = GetBooleanPropertyValue(control, "IsSelected");
            bool isHighlighted = GetBooleanPropertyValue(control, "IsHighlighted");

            if (control is ToggleButton toggleButton && toggleButton.IsChecked == true)
            {
                control.Background = ThemePressedBrush;
                control.BorderBrush = ThemeAccentBrush;
                control.Foreground = ThemeTextBrush;
                return true;
            }

            if (!isSelected && !isHighlighted)
                return false;

            if (!IsAccentSelectionCandidate(control))
                return false;

            control.Background = ThemePressedBrush;
            control.BorderBrush = ThemeAccentBrush;
            control.Foreground = ThemeTextBrush;
            return true;
        }

        private static bool IsAccentSelectionCandidate(Control control)
        {
            if (control is ComboBoxItem ||
                control is ListBoxItem ||
                control is ListViewItem ||
                control is TreeViewItem ||
                control is MenuItem ||
                control is TabItem)
                return true;

            string typeName = control.GetType().Name;
            return typeName.IndexOf("Selector", StringComparison.OrdinalIgnoreCase) >= 0 ||
                typeName.IndexOf("Option", StringComparison.OrdinalIgnoreCase) >= 0 ||
                typeName.EndsWith("Item", StringComparison.OrdinalIgnoreCase);
        }

        private static bool ShouldKeepTransparentBackground(DependencyObject element)
        {
            if (element == null)
                return false;

            if (element is Label || element is TextBlock || element is TextElement || element is AccessText)
                return true;

            var border = element as Border;
            if (border != null && IsTextLikeElement(border.Child as DependencyObject))
                return true;

            var panel = element as Panel;
            if (panel != null && panel.Children.Count > 0 && panel.Children.OfType<DependencyObject>().All(IsTextLikeElement))
                return true;

            string typeName = element.GetType().Name;
            string elementName = (element as FrameworkElement)?.Name ?? string.Empty;
            return ContainsThemeHint(typeName, elementName, "Label", "FieldName", "DisplayName", "Caption", "NameText");
        }

        private static bool IsTextLikeElement(DependencyObject element)
        {
            return element is Label ||
                element is TextBlock ||
                element is TextElement ||
                element is AccessText;
        }

        private static bool HasAncestorTypeName(DependencyObject element, params string[] typeNames)
        {
            for (DependencyObject current = GetParentObject(element); current != null; current = GetParentObject(current))
            {
                string currentTypeName = current.GetType().Name;
                foreach (string typeName in typeNames)
                {
                    if (currentTypeName.IndexOf(typeName, StringComparison.OrdinalIgnoreCase) >= 0)
                        return true;
                }
            }

            return false;
        }

        private static bool HasCheckedAncestorTypeName(DependencyObject element, params string[] typeNames)
        {
            for (DependencyObject current = GetParentObject(element); current != null; current = GetParentObject(current))
            {
                string currentTypeName = current.GetType().Name;
                foreach (string typeName in typeNames)
                {
                    if (currentTypeName.IndexOf(typeName, StringComparison.OrdinalIgnoreCase) >= 0)
                        return GetBooleanPropertyValue(current, "IsChecked");
                }
            }

            return false;
        }

        private static bool IsTopBarElement(FrameworkElement element)
        {
            if (element == null)
                return false;

            double height = ResolveDimension(element.ActualHeight, element.Height);
            if (height > 34)
                return false;

            if (TryGetElementPositionRelativeToWindow(element, out Point position))
                return position.Y < 160;

            return false;
        }

        private static bool TryGetElementPositionRelativeToWindow(FrameworkElement element, out Point position)
        {
            position = new Point();
            if (element == null)
                return false;

            Window window = Window.GetWindow(element);
            if (window == null)
                return false;

            try
            {
                position = element.TransformToAncestor(window).Transform(new Point(0, 0));
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static double ResolveDimension(double actual, double declared)
        {
            if (!double.IsNaN(actual) && actual > 0)
                return actual;

            if (!double.IsNaN(declared) && declared > 0)
                return declared;

            return 0;
        }

        private static void TryApplyBonoboSplashImage(Image image)
        {
            if (!IsLikelyBonoboSplashImage(image))
                return;

            BitmapImage splashImage = GetBonoboSplashImage();
            if (splashImage == null || ReferenceEquals(image.Source, splashImage))
                return;

            image.Source = splashImage;
        }

        private static bool IsLikelyBonoboSplashImage(Image image)
        {
            if (image == null)
                return false;

            if (TryGetImageSourceUri(image.Source, out string sourceUri) &&
                sourceUri.IndexOf("splash", StringComparison.OrdinalIgnoreCase) >= 0)
                return true;

            double width = ResolveDimension(image.ActualWidth, image.Width);
            double height = ResolveDimension(image.ActualHeight, image.Height);
            if (width < 24 || height < 24)
                return false;

            if (!TryGetElementPositionRelativeToWindow(image, out Point position))
                return false;

            return position.X < 160 && position.Y < 160;
        }

        private static bool TryGetImageSourceUri(ImageSource imageSource, out string sourceUri)
        {
            sourceUri = null;

            var bitmapImage = imageSource as BitmapImage;
            if (bitmapImage?.UriSource == null)
                return false;

            sourceUri = bitmapImage.UriSource.ToString();
            return !string.IsNullOrWhiteSpace(sourceUri);
        }

        private static BitmapImage GetBonoboSplashImage()
        {
            string splashPath = ResolveBonoboSplashImagePath();
            if (string.IsNullOrWhiteSpace(splashPath))
                return null;

            if (_bonoboSplashImage != null &&
                string.Equals(_bonoboSplashImagePath, splashPath, StringComparison.OrdinalIgnoreCase))
                return _bonoboSplashImage;

            var bitmapImage = new BitmapImage();
            bitmapImage.BeginInit();
            bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
            bitmapImage.UriSource = new Uri(splashPath, UriKind.Absolute);
            bitmapImage.EndInit();

            if (bitmapImage.CanFreeze)
                bitmapImage.Freeze();

            _bonoboSplashImage = bitmapImage;
            _bonoboSplashImagePath = splashPath;
            return _bonoboSplashImage;
        }

        private static string ResolveBonoboSplashImagePath()
        {
            string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string[] candidatePaths =
            {
                Path.Combine(baseDirectory, "splash.png"),
                Path.Combine(baseDirectory, "splash.jpg"),
                Path.Combine(baseDirectory, "splash.jpeg")
            };

            return candidatePaths.FirstOrDefault(File.Exists);
        }

        private static Brush CreateFrozenBrush(byte red, byte green, byte blue)
        {
            var brush = new SolidColorBrush(Color.FromRgb(red, green, blue));
            if (brush.CanFreeze)
                brush.Freeze();

            return brush;
        }
    }
}
