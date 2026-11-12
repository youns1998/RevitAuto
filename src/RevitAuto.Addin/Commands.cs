using System.Text;
using System.IO;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Microsoft.Win32;
using RevitAuto.Core;

namespace RevitAuto.Addin;

internal static class CommandSupport
{
    public static Result Run(ExternalCommandData data, Action<UIApplication, Document> action, ref string message)
    {
        if (data.Application.ActiveUIDocument is not { Document.IsFamilyDocument: false } uiDoc)
            return Result.Cancelled;
        try { action(data.Application, uiDoc.Document); return Result.Succeeded; }
        catch (OperationCanceledException) { return Result.Cancelled; }
        catch (Exception ex)
        {
            message = ex.Message;
            TaskDialog.Show("RevitAuto", ex.Message);
            return Result.Failed;
        }
    }

    public static ViewSheet[] Sheets(Document doc) => new FilteredElementCollector(doc)
        .OfClass(typeof(ViewSheet)).Cast<ViewSheet>().ToArray();

    public static void Commit(Transaction transaction)
    {
        if (transaction.Commit() != TransactionStatus.Committed)
            throw new InvalidOperationException("Revit이 변경사항을 확정하지 못했습니다. 오류를 확인하세요.");
    }
}

[Transaction(TransactionMode.Manual)]
public sealed class ImportSheetsCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData data, ref string message, ElementSet elements) =>
        CommandSupport.Run(data, (app, doc) =>
        {
            var file = new OpenFileDialog { Filter = "시트 목록 (*.csv)|*.csv", Title = "Number,Name CSV 선택" };
            if (file.ShowDialog() != true) throw new OperationCanceledException();
            IReadOnlyList<SheetSpec> plan;
            using (var input = new StreamReader(file.FileName, Encoding.UTF8, true)) plan = SheetPlans.ReadCsv(input);
            SheetPlans.Validate(plan, CommandSupport.Sheets(doc).Select(x => x.SheetNumber));
            var dialog = new PlanDialog(app, plan, null);
            if (dialog.ShowDialog() != true) throw new OperationCanceledException();
            using var transaction = new Transaction(doc, "RevitAuto: CSV 시트 일괄 생성");
            transaction.Start();
            foreach (var item in plan)
            {
                var sheet = ViewSheet.Create(doc, dialog.TitleBlockId);
                sheet.SheetNumber = item.Number;
                sheet.Name = item.Name;
            }
            CommandSupport.Commit(transaction);
            TaskDialog.Show("RevitAuto", $"시트 {plan.Count}개를 생성했습니다. 실행 취소 1회로 되돌릴 수 있습니다.");
        }, ref message);
}

[Transaction(TransactionMode.Manual)]
public sealed class PlaceViewsCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData data, ref string message, ElementSet elements) =>
        CommandSupport.Run(data, (app, doc) =>
        {
            var placed = new FilteredElementCollector(doc).OfClass(typeof(Viewport)).Cast<Viewport>()
                .Select(x => x.ViewId).ToHashSet();
            var allowed = new[] { ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.EngineeringPlan,
                ViewType.Elevation, ViewType.Section, ViewType.ThreeD, ViewType.DraftingView, ViewType.Detail };
            var views = new FilteredElementCollector(doc).OfClass(typeof(View)).Cast<View>()
                .Where(x => !x.IsTemplate && allowed.Contains(x.ViewType) && !placed.Contains(x.Id))
                .OrderBy(x => x.Name).ToArray();
            if (views.Length == 0)
                throw new InvalidOperationException("시트에 배치하지 않은 평면·입면·단면·3D·상세 뷰가 없습니다.");
            var dialog = new PlanDialog(app, null, views);
            if (dialog.ShowDialog() != true) throw new OperationCanceledException();
            var chosen = dialog.SelectedViews;
            var plan = SheetPlans.ForViews(chosen.Select(x => x.Name), CommandSupport.Sheets(doc).Select(x => x.SheetNumber));
            using var transaction = new Transaction(doc, "RevitAuto: 뷰별 시트 생성 및 배치");
            transaction.Start();
            for (var i = 0; i < chosen.Count; i++)
            {
                var sheet = ViewSheet.Create(doc, dialog.TitleBlockId);
                sheet.SheetNumber = plan[i].Number;
                sheet.Name = plan[i].Name;
                doc.Regenerate();
                if (!Viewport.CanAddViewToSheet(doc, sheet.Id, chosen[i].Id))
                    throw new InvalidOperationException($"'{chosen[i].Name}' 뷰를 배치할 수 없어 전체 작업을 취소했습니다.");
                var outline = sheet.Outline;
                var center = new XYZ((outline.Min.U + outline.Max.U) / 2, (outline.Min.V + outline.Max.V) / 2, 0);
                var viewport = Viewport.Create(doc, sheet.Id, chosen[i].Id, center);
                doc.Regenerate();
                viewport.SetBoxCenter(center);
            }
            CommandSupport.Commit(transaction);
            TaskDialog.Show("RevitAuto", $"뷰 {chosen.Count}개를 각각 새 시트에 배치했습니다. 축척과 도곽 안쪽 배치는 출력 전에 확인하세요.");
        }, ref message);
}

[Transaction(TransactionMode.ReadOnly)]
public sealed class ExportSheetsCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData data, ref string message, ElementSet elements) =>
        CommandSupport.Run(data, (_, doc) =>
        {
            var sheets = CommandSupport.Sheets(doc).OrderBy(x => x.SheetNumber, StringComparer.OrdinalIgnoreCase)
                .Select(x => new SheetSpec(x.SheetNumber, x.Name)).ToArray();
            var file = new SaveFileDialog { Filter = "CSV (*.csv)|*.csv", FileName = "sheet-register.csv", AddExtension = true, DefaultExt = ".csv" };
            if (file.ShowDialog() != true) throw new OperationCanceledException();
            using (var output = new StreamWriter(file.FileName, false, new UTF8Encoding(true))) SheetPlans.WriteCsv(output, sheets);
            TaskDialog.Show("RevitAuto", $"시트 {sheets.Length}개의 번호와 이름을 저장했습니다.\n{file.FileName}");
        }, ref message);
}
