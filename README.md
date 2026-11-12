# RevitAuto

Revit에서 반복하는 시트 생성과 뷰 배치를 줄이는 C# 도면 자동화 애드인입니다. 2층 단독주택의 CAD 도면을 Revit 모델과 시트로 옮기는 학습 과정에서, 시트 번호·이름 입력과 뷰 배치를 묶어 실행하도록 만들었습니다.

Revit 2026 / Windows / .NET 8을 대상으로 합니다. **Revit 2026 API를 참조한 Release 빌드(경고 0·오류 0)와 Core 자동 검사 17개를 확인했습니다. Revit 내부 리본 로딩과 실제 모델 변경은 아직 검증하지 않았습니다.**

## 리본 기능

설치 후 Revit을 시작하고 프로젝트를 열면 `RevitAuto → 도면 자동화` 패널에서 실행합니다.

| 버튼 | 입력과 동작 |
| --- | --- |
| CSV 시트 일괄 생성 | `Number,Name` CSV를 읽고 번호·이름 미리보기와 도곽 선택 후 시트를 생성합니다. 빈 값·중복·기존 번호 충돌을 생성 전에 검사합니다. |
| 뷰 → 시트 자동 배치 | 미배치 평면·천장·구조 평면·입면·단면·3D·드래프팅·상세 뷰 중 여러 개를 선택합니다. 뷰마다 새 시트를 만들고 중앙에 배치합니다. 기존 번호를 건너뛰며 `RA-001`부터 번호를 배정합니다. |
| 시트 목록 내보내기 | 현재 프로젝트의 시트 번호·이름(자리표시자 시트 포함)을 번호 순으로 UTF-8 BOM CSV에 저장합니다. 모델은 변경하지 않습니다. |

시트 생성과 뷰 배치는 각각 하나의 Revit Transaction으로 처리합니다. 확정 전 오류가 발생하면 해당 명령의 변경 전체를 취소하고, 정상 완료 후에는 실행 취소 1회로 되돌릴 수 있습니다. 기존 시트를 수정하거나 덮어쓰지 않습니다. 프로젝트가 열리지 않았거나 패밀리 편집 중이면 버튼을 사용할 수 없습니다.

## 빌드와 설치

Revit 2026과 .NET 8 SDK가 설치된 Windows에서 실행합니다. NuGet 외부 패키지는 필요하지 않으며 Autodesk API DLL은 저장소에 포함하지 않습니다.

```powershell
git clone https://github.com/youns1998/RevitAuto.git
cd RevitAuto
dotnet build RevitAuto.sln -c Release
dotnet run --project tests/RevitAuto.Checks -c Release
powershell -ExecutionPolicy Bypass -File scripts/install-addin.ps1
```

기본 API 경로는 `C:\Program Files\Autodesk\Revit 2026`입니다. 설치 위치가 다르면 빌드 시 지정합니다.

```powershell
dotnet build RevitAuto.sln -c Release '-p:RevitInstallDir=D:\Autodesk\Revit 2026'
```

설치 스크립트는 현재 사용자의 `%APPDATA%\Autodesk\Revit\Addins\2026`에 `Youns.RevitAuto.addin`(Application 형식)과 `Youns.RevitAuto` 폴더의 두 DLL을 설치합니다. Revit을 닫고 설치한 뒤 다시 시작하세요. 설치 경로만 바꾸어 매니페스트를 검증하려면 `-DestinationDirectory .local/addins`를 사용할 수 있습니다.

제거하려면 Revit을 닫고 위의 `Youns.RevitAuto.addin` 파일과 `Youns.RevitAuto` 폴더를 삭제합니다.

## 단독주택 시트 예제

[samples/house-sheets.csv](samples/house-sheets.csv)를 CSV 시트 일괄 생성 버튼에서 선택합니다.

```csv
Number,Name
A101,1층 평면도
A102,2층 평면도
A201,남측 입면도
A202,북측 입면도
A301,주단면도
```

미리보기에서 도곽 유형을 고르고 생성하면 예제 시트 5개가 만들어집니다. 도곽이 없으면 ‘도곽 없이 생성’을 선택할 수 있습니다. 이미 같은 번호가 있으면 전체 작업을 중단하므로 CSV 번호를 바꾸어 다시 실행합니다. 예제는 시트 목록이며 RVT 모델이나 완성 도면을 생성하지 않습니다.

CSV는 UTF-8 형식을 사용하며 쉼표와 따옴표가 들어간 이름은 표준 CSV 인용을 지원합니다. 번호·이름의 줄바꿈은 허용하지 않습니다. 내보낼 때 `=`, `+`, `-`, `@`로 시작하는 값에는 스프레드시트 수식 실행을 막는 작은따옴표를 붙입니다. 해당 값은 다시 가져올 때 원래 이름과 다를 수 있습니다. 일반 번호·이름은 같은 CSV 형식으로 다시 사용할 수 있지만, 기존 프로젝트에 그대로 가져오면 중복 번호 검사로 중단됩니다.

## 검증

Core 검사는 Revit 없이도 실행하며 다음을 확인합니다.

- 한글·BOM·쉼표·따옴표·공백 처리와 CSV 왕복 변환
- 잘못된 헤더·열 개수·빈 값·줄바꿈·손상된 따옴표 거부
- 대소문자를 구분하지 않는 중복과 기존 시트 번호 충돌
- 기존 번호를 피하는 자동 시트 번호 배정과 CSV 수식 문자 보호

Core 검사는 `dotnet run --project tests/RevitAuto.Checks -c Release`로 실행합니다. Autodesk API를 사용하는 전체 빌드는 로컬 Revit 설치가 필요합니다.

실제 Revit에서 확인할 항목은 [docs/manual-checks.md](docs/manual-checks.md)에 정리했습니다. 이 문서는 검사 절차이며 실행 완료 기록이 아닙니다. 뷰 배치는 시트 중앙을 기준으로 하며 축척 자동 조절, 도곽 여백·범례·스케줄 배치, PDF 일괄 출력은 구현하지 않았습니다. 출력 전에 뷰 크기와 제목 위치를 확인하세요.

## 구조

```text
src/RevitAuto.Core       CSV 읽기·쓰기, 시트 검증, 번호 배정
src/RevitAuto.Addin      IExternalApplication 리본, WPF 미리보기, Revit 명령
tests/RevitAuto.Checks   외부 패키지 없는 Core 검사 17개
samples                 단독주택 시트 목록 예제
scripts                 현재 사용자용 애드인 설치
```

설계 결과물은 [건축 포트폴리오의 2층 단독주택](https://youns1998.github.io/portfolioCAD/projects/detail.html?project=two-story-house&document=house-revit-sheets)에서 볼 수 있습니다. 이 저장소의 코드는 시트 작업 자동화 학습용이며, 공개한 Revit 시트를 이 코드로 생성했다는 의미는 아닙니다.

구현에 참고한 Autodesk 문서: [리본 패널과 애드인 등록](https://help.autodesk.com/cloudhelp/2025/ITA/Revit-API/files/Revit_API_Developers_Guide/Introduction/Getting_Started/Revit_API_Revit_API_Developers_Guide_Introduction_Getting_Started_Walkthrough_Add_Hello_World_Ribbon_Panel_html.html), [ViewSheet.Create](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/bc9e8be3-f3fd-97c2-2709-1d6eea3db775.htm).
