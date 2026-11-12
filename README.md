# RevitAuto

**Revit의 시트 작성과 도면 정보 정리를 돕는 Python 플러그인입니다.**

이름 목록으로 시트를 만들고, 뷰를 새 시트에 배치하고, 시트 내부 정보까지 CSV·JSON으로 묶어 저장합니다. [pyRevit](https://github.com/pyrevitlabs/pyRevit)을 통해 리본에서 실행합니다.

## 한눈에 보는 구조

```mermaid
flowchart LR
    A["CSV 이름 목록"] --> B["sheets.py<br/>번호 배정 · 입력 검사"]
    B --> C["리본 · commands.py"]
    C --> D["Revit API<br/>시트 생성 · 뷰 배치"]
    E[("Revit 프로젝트")] --> F["revit_report.py<br/>시트 → 뷰 → 요소·파라미터 수집"]
    C --> F
    F --> G["reports.py<br/>CSV·JSON ZIP 저장"]
    F --> H["시트 PDF · 선택"]
    H --> G
    D --> E
```

## 리본의 세 기능

| 버튼 | 사용 방법 | 결과 |
| --- | --- | --- |
| CSV 시트 일괄 생성 | 이름 목록 또는 번호·이름 CSV 선택 → 도곽 선택 → 미리보기 | 번호와 이름이 입력된 빈 시트 |
| 뷰 → 시트 자동 배치 | 미배치 뷰 선택 → 도곽 선택 → 미리보기 | 뷰마다 새 시트 1개, 중앙에 뷰 배치 |
| 시트·뷰 상세정보 내보내기 | 시트 선택 → PDF 포함 여부 선택 → ZIP 저장 | 시트·뷰·요소·주석·파라미터 CSV와 JSON, 선택한 경우 시트 PDF |

생성 명령은 각각 실행 취소 1회로 되돌릴 수 있습니다. 내보내기는 모델을 수정하지 않습니다. 앞의 두 버튼은 서로 다른 새 시트를 만듭니다. CSV로 만든 빈 시트를 뷰 배치 버튼이 채우는 구조는 아닙니다.

## 설치·업데이트

대상은 **Windows · Revit 2026 · Revit 2026을 지원하는 pyRevit**입니다. pyRevit의 IronPython 엔진을 사용하며 별도 C# 빌드나 pip 설치는 필요하지 않습니다.

1. [pyRevit](https://github.com/pyrevitlabs/pyRevit/releases)을 설치하고 Revit 2026에 연결합니다.
2. 저장소를 내려받고 설치 명령을 실행합니다.
3. 작업을 저장한 뒤 Revit을 완전히 종료하고 다시 실행합니다. **RevitAuto → 도면 자동화**가 나타납니다.

```powershell
git clone https://github.com/youns1998/RevitAuto.git
cd RevitAuto
powershell -ExecutionPolicy Bypass -File scripts/install-extension.ps1
```

업데이트는 저장소에서 `git pull` 후 설치 명령을 다시 실행합니다. 설치 위치는 `%APPDATA%\pyRevit\Extensions\RevitAuto.extension`입니다. 다른 위치를 쓸 때는 pyRevit Settings의 확장 검색 경로에 그 상위 폴더를 등록합니다.

이전 C# 버전을 설치했다면 Revit을 닫고 `%APPDATA%\Autodesk\Revit\Addins\2026`의 `Youns.RevitAuto.addin`과 `Youns.RevitAuto` 폴더를 제거한 뒤 전환하세요.

## 이름만 적어서 시트 만들기

[samples/names-only.csv](samples/names-only.csv)를 ‘CSV 시트 일괄 생성’에서 선택합니다.

```csv
Name
1층 평면도
2층 평면도
남측 입면도
```

이름 한 열·3행을 읽어 빈 시트 3장을 만듭니다. `Name` 머리글은 생략할 수 있고 `이름`, `시트명`도 지원합니다. 번호는 기존 번호를 피해서 `A-001`, `A-002` 순으로 자동 부여합니다. 생성 전 미리보기에서 번호·이름을 확인합니다.

번호까지 정하려면 [samples/house-sheets.csv](samples/house-sheets.csv)처럼 두 열을 사용합니다.

```csv
Number,Name
A101,1층 평면도
A102,2층 평면도
```

CSV는 **UTF-8**로 저장합니다. 이미 같은 번호가 있으면 생성하지 않습니다. 도곽은 선택한 유형을 공통 적용하며, ‘도곽 없이 생성’도 선택할 수 있습니다.

## 뷰 자동 배치

뷰마다 별도 새 시트를 만들고 `RA-001`부터 충돌 없이 번호를 붙입니다. 평면·천장·구조 평면·입면·단면·3D·드래프팅·상세 뷰 중 미배치 뷰를 선택할 수 있습니다.

`{3D}`처럼 시트 이름에 사용할 수 없는 문자는 새 시트 이름에서 정리합니다. 원래 뷰 이름은 유지합니다. 중앙 배치만 자동화하므로 출력 전 축척과 도곽 여백을 확인하세요.

## 상세정보 내보내기

내보낼 시트를 여러 개 선택하고 ZIP 파일을 저장합니다. ‘CSV·JSON 상세정보 + 시트 PDF’를 선택하면 같은 ZIP에 PDF도 넣습니다.

| 파일 | 내용 |
| --- | --- |
| `sheets.csv` | 시트 번호·이름·도곽·개정 번호 |
| `views.csv`, `placements.csv` | 뷰 유형·축척·레벨·템플릿·자르기 영역·배치 위치 |
| `elements.csv`, `view_elements.csv` | 요소·주석의 ID, 유형, 위치, 텍스트, 치수와 뷰의 관계 |
| `types.csv`, `materials.csv` | 요소 유형·패밀리와 재료 정보 |
| `parameters.csv` | 읽을 수 있는 인스턴스·유형 파라미터의 원시 값·표시 값·단위 |
| `revisions.csv`, `schedule_cells.csv` | 개정 상세와 배치된 일람표의 표 내용 |
| `documents.csv` | 프로젝트와 직접 연결된 로드된 모델의 정보 |
| `snapshot.json`, `manifest.json` | 전체 관계 데이터와 출력 범위·개수 |
| `issues.csv` | 읽지 못한 항목과 원인 |
| `sheets.pdf` | 선택한 경우 도면의 시각적 출력 |

CSV는 Excel에서 비교하고, JSON은 요소별 상세 값을 프로그램에서 재사용할 때 사용합니다. 관계는 `host:요소ID`, `link:링크ID:요소ID` 키로 연결됩니다. 원시 길이·면적 값 등은 Revit 내부 단위이므로 표시 값과 단위 ID를 함께 확인합니다.

이 출력은 선택한 시트의 정보를 읽는 보고서이며 RVT 전체 백업이 아닙니다. API가 반환하는 뷰 요소 후보에는 가려진 요소나 자르기 영역 밖 요소가 포함될 수 있습니다. 전체 솔리드·메시, 외부 파일 자체, 중첩 링크와 렌더링 재료 자산은 포함하지 않습니다. 읽기 실패나 PDF 실패는 `issues.csv`와 완료 메시지에 표시합니다. [출력 형식과 범위](docs/export-format.md)를 참고하세요.

## 검증과 실습

`python scripts/check.py`로 모델을 열지 않고 CSV·자동 번호·출력 ZIP·수집 관계를 검사합니다. Python 3 검사 53개 중 52개 통과·CLR 전용 1개 제외, 설치된 pyRevit의 IronPython 2.7.12 엔진에서 한글·ZIP 회귀 검사 19개 통과를 확인했습니다. Revit 수집·트랜잭션 검사는 대체 API 검사이며 **실제 모델의 상세정보 수집과 PDF 출력은 아직 확인하지 않았습니다.**

[사본으로 실습하는 순서](docs/first-practice.md) · [수동 확인 항목](docs/manual-checks.md) · [설계 결과물](https://youns1998.github.io/portfolioCAD/projects/detail.html?project=two-story-house&document=house-revit-sheets)

참고: [pyRevit 확장 구조](https://docs.pyrevitlabs.io/extensions/), [Revit 뷰 요소 수집의 범위](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/6359776d-915e-f8a2-4147-b31024671ee1.htm).
