using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using RevitAuto.Core;
using ComboBox = System.Windows.Controls.ComboBox;

namespace RevitAuto.Addin;

internal sealed class PlanDialog : Window
{
    private readonly ComboBox titleBlocks = new() { DisplayMemberPath = "Label", Margin = new Thickness(0, 8, 0, 12) };
    private readonly ListBox rows = new() { SelectionMode = SelectionMode.Extended, MinHeight = 160 };
    private sealed record TitleBlockChoice(ElementId Id, string Label);
    private sealed record ViewChoice(View View) { public override string ToString() => $"{View.Name} · {View.ViewType}"; }
    public ElementId TitleBlockId => ((TitleBlockChoice)titleBlocks.SelectedItem).Id;
    public IReadOnlyList<View> SelectedViews => rows.SelectedItems.Cast<ViewChoice>().Select(x => x.View).ToArray();

    public PlanDialog(UIApplication app, IReadOnlyList<SheetSpec>? plan, IReadOnlyList<View>? views)
    {
        Title = plan is null ? "뷰를 새 시트에 배치" : "CSV 시트 생성 미리보기";
        Width = 600;
        Height = 520;
        MinWidth = 440;
        MinHeight = 400;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        new WindowInteropHelper(this).Owner = app.MainWindowHandle;
        var root = new DockPanel { Margin = new Thickness(20) };
        Content = root;
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        DockPanel.SetDock(buttons, Dock.Bottom);
        root.Children.Add(buttons);
        var cancel = new Button { Content = "취소", Width = 85, Margin = new Thickness(8), IsCancel = true };
        var create = new Button { Content = "생성", Width = 100, Margin = new Thickness(8), IsDefault = true };
        buttons.Children.Add(cancel);
        buttons.Children.Add(create);
        create.Click += (_, _) =>
        {
            if (plan is null && rows.SelectedItems.Count == 0)
            { MessageBox.Show(this, "배치할 뷰를 선택하세요."); return; }
            DialogResult = true;
        };
        var heading = new StackPanel();
        DockPanel.SetDock(heading, Dock.Top);
        root.Children.Add(heading);
        heading.Children.Add(new TextBlock
        {
            Text = plan is null
                ? "Ctrl / Shift로 여러 뷰를 선택하세요. 뷰마다 새 시트가 생성됩니다."
                : $"{plan.Count}개 시트를 생성합니다. 번호와 이름을 확인하세요.",
            TextWrapping = TextWrapping.Wrap
        });
        heading.Children.Add(new TextBlock { Text = "도곽 유형", Margin = new Thickness(0, 12, 0, 0) });
        heading.Children.Add(titleBlocks);
        titleBlocks.Items.Add(new TitleBlockChoice(ElementId.InvalidElementId, "도곽 없이 생성"));
        foreach (var symbol in new FilteredElementCollector(app.ActiveUIDocument.Document)
                     .OfCategory(BuiltInCategory.OST_TitleBlocks).OfClass(typeof(FamilySymbol))
                     .Cast<FamilySymbol>().OrderBy(x => x.FamilyName).ThenBy(x => x.Name))
            titleBlocks.Items.Add(new TitleBlockChoice(symbol.Id, $"{symbol.FamilyName} : {symbol.Name}"));
        titleBlocks.SelectedIndex = titleBlocks.Items.Count > 1 ? 1 : 0;
        if (plan is not null)
        {
            rows.SelectionMode = SelectionMode.Single;
            foreach (var sheet in plan) rows.Items.Add($"{sheet.Number}    {sheet.Name}");
        }
        else foreach (var view in views!) rows.Items.Add(new ViewChoice(view));
        root.Children.Add(rows);
    }
}
