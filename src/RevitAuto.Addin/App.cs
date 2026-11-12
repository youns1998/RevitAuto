using System.Reflection;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace RevitAuto.Addin;

public sealed class App : IExternalApplication
{
    public Result OnStartup(UIControlledApplication app)
    {
        const string tab = "RevitAuto";
        try { app.CreateRibbonTab(tab); }
        catch (Autodesk.Revit.Exceptions.ArgumentException) { /* Another add-in already created the tab. */ }
        var panel = app.CreateRibbonPanel(tab, "도면 자동화");
        Add<ImportSheetsCommand>(panel, "ImportSheets", "CSV 시트\n일괄 생성", "CSV의 번호와 이름을 미리 확인하고 시트를 일괄 생성합니다.", "S", Colors.SeaGreen);
        Add<PlaceViewsCommand>(panel, "PlaceViews", "뷰 → 시트\n자동 배치", "선택한 뷰마다 새 시트를 만들고 중앙에 배치합니다.", "V", Colors.SteelBlue);
        Add<ExportSheetsCommand>(panel, "ExportSheets", "시트 목록\n내보내기", "현재 모델의 시트 번호와 이름을 UTF-8 CSV로 저장합니다.", "C", Colors.DarkGoldenrod);
        return Result.Succeeded;
    }

    public Result OnShutdown(UIControlledApplication app) => Result.Succeeded;

    private static void Add<T>(RibbonPanel panel, string id, string label, string tooltip, string glyph, System.Windows.Media.Color color)
    {
        var data = new PushButtonData(id, label, Assembly.GetExecutingAssembly().Location, typeof(T).FullName!);
        var button = (PushButton)panel.AddItem(data);
        button.ToolTip = tooltip;
        button.AvailabilityClassName = typeof(ProjectAvailable).FullName;
        var visual = new DrawingVisual();
        using (var dc = visual.RenderOpen())
        {
            dc.DrawRoundedRectangle(new SolidColorBrush(color), null, new Rect(0, 0, 32, 32), 5, 5);
            var text = new System.Windows.Media.FormattedText(glyph, System.Globalization.CultureInfo.InvariantCulture,
                FlowDirection.LeftToRight, new Typeface("Segoe UI"), 22, Brushes.White, 1);
            dc.DrawText(text, new System.Windows.Point((32 - text.Width) / 2, 1));
        }
        var bitmap = new RenderTargetBitmap(32, 32, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(visual);
        bitmap.Freeze();
        button.LargeImage = bitmap;
    }
}

public sealed class ProjectAvailable : IExternalCommandAvailability
{
    public bool IsCommandAvailable(UIApplication app, CategorySet categories) =>
        app.ActiveUIDocument is { Document.IsFamilyDocument: false };
}
