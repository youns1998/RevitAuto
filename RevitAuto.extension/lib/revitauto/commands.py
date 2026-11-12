# -*- coding: utf-8 -*-
"""Revit API operations. Imported only inside a pyRevit command context."""
from __future__ import unicode_literals

from pyrevit import DB, forms, revit, script
from revitauto.sheets import for_views, read_csv_file, validate


def run(command):
    doc = revit.doc
    if doc is None or doc.IsFamilyDocument:
        forms.alert('Revit 프로젝트를 먼저 여세요.', title='RevitAuto')
        return
    try:
        command(doc)
    except Exception as error:
        script.get_logger().exception('RevitAuto command failed')
        forms.alert('작업을 완료하지 못했습니다.\n{}'.format(error), title='RevitAuto')


def _sheets(doc):
    return list(DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet))


def _validate_revit_names(plan):
    for item in plan:
        if not DB.NamingUtils.IsValidName(item.name):
            raise ValueError("시트 '{}'의 이름에 Revit에서 허용하지 않는 문자가 있습니다: {}".format(item.number, item.name))


def _titleblock(doc):
    options = {'도곽 없이 생성': DB.ElementId.InvalidElementId}
    for symbol in DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_TitleBlocks):
        name = symbol.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
        options['{} : {}'.format(symbol.FamilyName, name)] = symbol.Id
    choice = forms.SelectFromList.show(sorted(options), title='도곽 선택', button_name='다음')
    return options[choice] if choice is not None else None


def _confirm(plan):
    preview = '\n'.join('{}  |  {}'.format(x.number, x.name) for x in plan[:25])
    if len(plan) > 25:
        preview += '\n외 {}개'.format(len(plan) - 25)
    return forms.alert('{}개 시트를 생성합니다.\n\n{}\n\n진행할까요?'.format(len(plan), preview),
                       title='RevitAuto · 생성 미리보기', ok=False, yes=True, no=True)


def _change(doc, name, action):
    """One explicit transaction: no partial sheets after operation errors."""
    transaction = DB.Transaction(doc, name)
    try:
        if transaction.Start() != DB.TransactionStatus.Started:
            raise RuntimeError('Revit 변경 작업을 시작할 수 없습니다.')
        options = transaction.GetFailureHandlingOptions()
        options.SetClearAfterRollback(True)
        transaction.SetFailureHandlingOptions(options)
        action()
        if transaction.Commit() != DB.TransactionStatus.Committed:
            raise RuntimeError('Revit이 변경을 확정하지 못했습니다. Revit 오류 창을 확인하세요.')
    except Exception:
        if transaction.GetStatus() == DB.TransactionStatus.Started:
            transaction.RollBack()
        raise
    finally:
        transaction.Dispose()


def import_sheets(doc):
    path = forms.pick_file(file_ext='csv', title='이름 한 열 또는 Number,Name CSV 선택')
    if not path:
        return
    existing = [x.SheetNumber for x in _sheets(doc)]
    plan = validate(read_csv_file(path, existing), existing)
    _validate_revit_names(plan)
    titleblock = _titleblock(doc)
    if titleblock is None or not _confirm(plan):
        return

    def create():
        for item in plan:
            sheet = DB.ViewSheet.Create(doc, titleblock)
            sheet.SheetNumber, sheet.Name = item.number, item.name

    _change(doc, 'RevitAuto: CSV 시트 일괄 생성', create)
    forms.alert('시트 {}개를 생성했습니다. 실행 취소 1회로 되돌릴 수 있습니다.'.format(len(plan)), title='RevitAuto')


def place_views(doc):
    placed = set(x.ViewId.Value for x in DB.FilteredElementCollector(doc).OfClass(DB.Viewport))
    allowed = (DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan,
               DB.ViewType.Elevation, DB.ViewType.Section, DB.ViewType.ThreeD,
               DB.ViewType.DraftingView, DB.ViewType.Detail)
    candidates = [x for x in DB.FilteredElementCollector(doc).OfClass(DB.View)
                  if not x.IsTemplate and x.ViewType in allowed and x.Id.Value not in placed]
    if not candidates:
        forms.alert('시트에 배치하지 않은 평면·입면·단면·3D·상세 뷰가 없습니다.', title='RevitAuto')
        return
    chosen = forms.SelectFromList.show(sorted(candidates, key=lambda x: x.Name), name_attr='Name',
                                       title='시트에 배치할 뷰 선택', multiselect=True, button_name='다음')
    if not chosen:
        return
    plan = for_views([x.Name for x in chosen], [x.SheetNumber for x in _sheets(doc)])
    _validate_revit_names(plan)
    titleblock = _titleblock(doc)
    if titleblock is None or not _confirm(plan):
        return

    def create():
        for view, item in zip(chosen, plan):
            sheet = DB.ViewSheet.Create(doc, titleblock)
            sheet.SheetNumber, sheet.Name = item.number, item.name
            doc.Regenerate()
            if not DB.Viewport.CanAddViewToSheet(doc, sheet.Id, view.Id):
                raise ValueError("'{}' 뷰를 배치할 수 없어 전체 작업을 취소했습니다.".format(view.Name))
            outline = sheet.Outline
            center = DB.XYZ((outline.Min.U + outline.Max.U) / 2.0,
                            (outline.Min.V + outline.Max.V) / 2.0, 0)
            viewport = DB.Viewport.Create(doc, sheet.Id, view.Id, center)
            doc.Regenerate()
            viewport.SetBoxCenter(center)

    _change(doc, 'RevitAuto: 뷰별 시트 생성 및 배치', create)
    forms.alert('뷰 {}개를 새 시트에 배치했습니다. 출력 전 축척과 도곽 여백을 확인하세요.'.format(len(chosen)), title='RevitAuto')


def export_sheets(doc):
    import os
    import shutil
    import tempfile
    from revitauto.reports import ExportCancelled, write_bundle
    from revitauto.revit_report import SnapshotCollector, export_pdf

    options = dict(('{} · {}'.format(x.SheetNumber, x.Name), x) for x in _sheets(doc))
    if not options:
        forms.alert('내보낼 시트가 없습니다.', title='RevitAuto')
        return
    selected = forms.SelectFromList.show(sorted(options), title='상세정보를 내보낼 시트 선택',
                                        multiselect=True, button_name='다음')
    if not selected:
        return
    sheets = [options[label] for label in selected]
    modes = ['CSV·JSON 상세정보', 'CSV·JSON 상세정보 + 시트 PDF']
    mode = forms.CommandSwitchWindow.show(modes, message='내보낼 형식을 선택하세요.')
    if mode is None:
        return
    path = forms.save_file(file_ext='zip', default_name='revit-sheet-details.zip', title='시트·뷰 상세정보 저장')
    if not path:
        return
    temporary = tempfile.mkdtemp(prefix='.revitauto-pdf-', dir=os.path.dirname(os.path.abspath(path)))
    try:
        with forms.ProgressBar(title='시트 상세정보 수집 {value}/{max_value}', cancellable=True) as progress:
            def tick(current, total):
                progress.update_progress(current, total)
                return not progress.cancelled
            collector = SnapshotCollector(doc, tick)
            snapshot = collector.snapshot(sheets)
            if progress.cancelled:
                raise ExportCancelled()
            pdf_path, pdf_status = None, 'not_requested'
            if mode == modes[1]:
                try:
                    pdf_path = export_pdf(doc, sheets, temporary)
                    pdf_status = 'included'
                except Exception as error:
                    collector.issue('export', 'PDF', 'pdf', error)
                    pdf_status = 'failed_see_issues'
            if progress.cancelled:
                raise ExportCancelled()
            manifest = write_bundle(path, snapshot, pdf_path, pdf_status)
        issue_count = manifest['counts']['issues']
        message = '시트 {}개 · 뷰 {}개 · 요소 {}개를 저장했습니다.\n{}'.format(
            len(snapshot['sheets']), len(snapshot['views']), len(snapshot['elements']), path)
        if issue_count:
            message += '\n읽지 못한 항목 {}건이 있습니다. ZIP 안의 issues.csv를 확인하세요.'.format(issue_count)
        forms.alert(message, title='RevitAuto')
    except ExportCancelled:
        forms.alert('내보내기를 취소했습니다.', title='RevitAuto')
    finally:
        shutil.rmtree(temporary)
