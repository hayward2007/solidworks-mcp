# SolidWorks MCP Server 🔧

**Claude에서 자연어로 SolidWorks를 조작하는 MCP 서버**
**Control SolidWorks from Claude with natural language (Model Context Protocol)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![SolidWorks 2023-2025](https://img.shields.io/badge/SolidWorks-2023--2025-red.svg)](https://www.solidworks.com/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

**[한국어](#한국어) · [English](#english)**

> 이 저장소는 [alisamsam/Solidworks-MCP](https://github.com/alisamsam/Solidworks-MCP) (MIT, Samsaam Ali Baig)를 바탕으로 Windows 원클릭 설치, SolidWorks 2025 COM 호환성 수정, 한국어 SolidWorks 지원을 더한 버전입니다.
>
> Based on [alisamsam/Solidworks-MCP](https://github.com/alisamsam/Solidworks-MCP) (MIT, Samsaam Ali Baig), with a one-click Windows installer, SolidWorks 2025 COM fixes and support for localized (e.g. Korean) SolidWorks.

---

## 한국어

### 목차

1. [소개](#소개)
2. [원본 대비 변경 사항](#원본-대비-변경-사항)
3. [요구 사항](#요구-사항)
4. [빠른 시작](#빠른-시작)
5. [설치 스크립트가 하는 일](#설치-스크립트가-하는-일)
6. [수동 설정](#수동-설정)
7. [사용 방법](#사용-방법)
8. [Text-to-CAD 작업 흐름](#text-to-cad-작업-흐름)
9. [도구 목록](#도구-목록)
10. [execute_python 고급 사용](#execute_python-고급-사용)
11. [설계 지식 베이스](#설계-지식-베이스)
12. [설정 파일 config.json](#설정-파일-configjson)
13. [문제 해결](#문제-해결)
14. [업데이트와 제거](#업데이트와-제거)
15. [로드맵](#로드맵)
16. [프로젝트 구조](#프로젝트-구조)
17. [라이선스와 크레딧](#라이선스와-크레딧)

### 소개

SolidWorks MCP Server는 Claude 같은 AI 에이전트가 SolidWorks를 직접 조작하게 해 주는 [Model Context Protocol](https://modelcontextprotocol.io/) 서버예요. 메뉴를 클릭하는 대신 만들고 싶은 형상을 말로 설명하면, Claude가 SolidWorks COM API로 파트를 만들고 스케치를 그리고 피처를 추가해요.

- 도구 31개: 연결, 문서, 스케치, 피처, 유틸리티, SolidWorks API를 직접 실행하는 `execute_python`, 검증(Text-to-CAD), 설계 지식 검색
- 에이전트용 작업 규칙(토큰 절약, 설계 근거)이 매 세션 자동 적용돼요
- SolidWorks 2023–2025 지원, 설치 경로 자동 탐지(레지스트리)
- 단위: mm, cm, m, inch, ft (기본 mm)
- 동작 로그: `solidworks_mcp/solidworks_mcp.log`

### 원본 대비 변경 사항

| 구분 | 내용 |
|---|---|
| 설치 오류 수정 | `requirements.txt`에서 PyPI에 없는 `asyncio-compat`를 뺐어요. 이 줄 때문에 `pip install -r requirements.txt`가 항상 실패했어요. |
| 시작 오류 수정 | `mcp>=1.0.0,<2`로 고정했어요. mcp 2.x는 서버가 쓰는 `Server.list_tools()` / `call_tool()` 데코레이터를 없애서, 설치되면 서버가 `AttributeError`로 바로 꺼져요. |
| 원클릭 설치 | `setup_windows.bat` + `setup_mcp.py`: 가상환경 생성, 패키지 설치, 서버 자가 진단, Claude Desktop 자동 등록까지 한 번에 해요. |
| SolidWorks 2025 COM 호환성 | `automation/base.py`에 `_com_value()`를 추가해서 다음을 고쳤어요. `list_open_documents`("구성원이 없습니다" 오류), `get_document_info`(`'int' object is not callable` 오류), `list_features`(첫 피처 1개만 나오고 억제 상태가 항상 false). |
| 한국어 SolidWorks 지원 | `create_sketch`가 "Front Plane"만 찾아서 한국어 UI(정면/윗면/우측면)에서 실패하던 문제를 고쳤어요. 이름으로 못 찾으면 기본 평면 순서로 실제 이름을 찾아요. |
| 저장소 정리 | `.env` 제외(원본에는 API 키가 들어 있었고, 서버는 이 파일을 쓰지 않아요), `.venv/` 무시, `.bat` 파일 줄바꿈(CRLF) 고정. |
| Text-to-CAD 검증 도구 | `model_report`, `render_views`, `export_model`, `check_interference`를 추가하고, `execute_python`에 도우미 주입과 `report` 옵션을 넣었어요. |
| 설계 지식 베이스 | `knowledge/` 노트 10개와 `knowledge_search`, `knowledge_get` 도구. |
| 에이전트 가이드 | 작업 흐름, 토큰 절약, 근거 규칙을 서버 instructions로 매 세션 자동 적용해요. |
| 출력 토큰 절감 | `execute_python` 결과 중복 제거, JSON 압축 출력(한글을 `\u` 이스케이프 없이), 트레이스백을 스크립트 부분만 남겨요. |

### 요구 사항

- Windows 10 / 11 (64비트)
- SolidWorks 2023–2025 (설치 및 라이선스 필요)
- Python 3.10 이상: python.org 설치판 또는 Python Install Manager(`py`) 모두 돼요
- Claude Desktop 또는 Claude Code
- 처음 설치할 때 인터넷 연결 (pip 패키지 다운로드)

검증 환경: SolidWorks 2025 (revision 33.5.0, 한국어 UI), Python 3.14.7, Claude Desktop (Windows, Microsoft Store/MSIX 설치판).

### 빠른 시작

1. **저장소 받기**

   ```powershell
   git clone https://github.com/hayward2007/solidworks-mcp.git
   cd solidworks-mcp
   ```

   ZIP으로 받아서 압축을 풀어도 돼요. 폴더 경로가 Claude 설정에 기록되니까, 나중에 폴더를 옮기면 설치를 다시 실행하세요.

2. **Claude Desktop 완전히 종료**: 작업 표시줄 오른쪽 아래 트레이(**^** 안쪽일 수 있음)의 Claude 아이콘을 우클릭해서 **종료(Quit)** 를 누르세요. 창만 닫으면 백그라운드에서 계속 돌아가서 새 설정을 읽지 않아요.

3. **`setup_windows.bat` 더블클릭** (또는 터미널에서 `py setup_mcp.py`). Claude가 아직 실행 중이면 스크립트가 종료하라고 알려 줘요. 마지막에 `All set`이 나오면 끝이에요.

4. **SolidWorks를 열고 Claude Desktop 실행** → Claude에게 "SolidWorks에 연결해줘"라고 말하세요.

Claude의 설정(Settings) → 개발자(Developer)에서 `solidworks` 서버가 running으로 보이면 정상이에요.

### 설치 스크립트가 하는 일

1. Python 3.10 이상을 찾아요: `py` 런처 → PATH의 `python` → `%LOCALAPPDATA%\Python\pythoncore-3.*`, `%LOCALAPPDATA%\Programs\Python\Python3*`, `%ProgramFiles%\Python3*` 순서.
2. 프로젝트 폴더에 가상환경 `.venv`를 만들어요 (이미 있으면 다시 써요).
3. `requirements.txt`를 설치해요 (`mcp` 1.x, `pywin32`, `python-dotenv`, `Pillow`).
4. 서버 자가 진단: Claude Desktop과 같은 방식(stdio)으로 서버를 띄워서 MCP 초기화와 도구 목록을 확인해요.
5. Claude Desktop 설정 파일에 `solidworks` 서버를 등록해요. 다른 서버와 설정은 그대로 두고, 바꾸기 전에 `claude_desktop_config.json.bak-날짜-시간` 백업을 만들어요. Microsoft Store(MSIX) 설치판의 설정 위치도 함께 갱신해요.
6. 화면에 나온 내용을 `setup_mcp.log`에 저장해요.

여러 번 실행해도 안전해요. 이미 등록돼 있으면 `already up to date`가 나와요.

### 수동 설정

#### 1) 패키지 설치

```powershell
cd C:\경로\Solidworks-MCP
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

#### 2) Claude Desktop

Claude → 설정 → 개발자 → **설정 편집(Edit Config)** 으로 열리는 `claude_desktop_config.json`의 `mcpServers`에 추가하세요.

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "C:\\경로\\Solidworks-MCP\\.venv\\Scripts\\python.exe",
      "args": ["C:\\경로\\Solidworks-MCP\\solidworks_mcp_server.py"]
    }
  }
}
```

설정 파일 위치:

- 일반 설치: `%APPDATA%\Claude\claude_desktop_config.json`
- Microsoft Store/MSIX 설치: `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`

`"command": "python"` 대신 `.venv` 안의 `python.exe` 전체 경로를 쓰는 이유: PATH의 `python`이 Microsoft Store 별칭이거나 패키지가 없는 다른 버전일 수 있어서예요. 저장한 뒤에는 Claude를 트레이에서 완전히 종료하고 다시 실행하세요.

#### 3) Claude Code

```powershell
claude mcp add --scope user solidworks -- "C:\경로\Solidworks-MCP\.venv\Scripts\python.exe" "C:\경로\Solidworks-MCP\solidworks_mcp_server.py"
claude mcp list
```

### 사용 방법

1. SolidWorks를 먼저 열어 두세요. 꺼져 있으면 `connect_solidworks`가 직접 실행하고 최대 120초 기다려요.
2. Claude에게 평소 말투로 요청하세요. 길이는 따로 말하지 않으면 mm예요.

예시:

- "SolidWorks에 연결해줘"
- "새 파트를 만들고, 윗면에 반지름 30mm 원을 그려서 15mm 돌출해줘"
- "정면에 100×50mm 사각형을 그리고 20mm 돌출한 다음, 가운데에 지름 10mm 구멍을 관통 컷해줘"
- "피처 목록 보여줘" / "열린 문서 목록 보여줘" / "현재 문서 정보 알려줘"
- "C:\작업\bracket.SLDPRT로 저장해줘"
- "execute_python으로 현재 파트의 부피와 질량을 계산해줘"

Claude는 보통 `create_sketch` → `draw_*` → `close_sketch` → `extrude_sketch` 순서로 도구를 써요. 스케치가 열린 채로 남으면 `get_sketch_status`로 상태를 확인할 수 있어요.

### Text-to-CAD 작업 흐름

짧거나 모호한 요청도 에이전트가 사양으로 정리하고, 모델을 직접 보고 재면서 빠르게 반복하게 하는 흐름이에요. 서버 instructions(`solidworks_mcp/instructions.md`)로 매 세션 자동 적용돼요.

1. **사양 정리**: 목적, 크기, 연결부, 하중·동작, 공정·재료를 10줄 이내로 정리해요. 모든 수치에 근거를 붙여요. 순서는 [req] 요구 사항·기존 형상 > [std] 규격 > [calc] 계산 > [cat] 카탈로그·확인된 미스미 품번 > [dfm] 공정 규칙 > [heur] 경험칙 > [neutral] 근거가 없을 때의 중립값(대칭, 1:1, 같은 간격, R10 표준수, 정수 mm)이에요.
2. **필요한 지식만 조회**: `knowledge_search`로 찾고 `knowledge_get`으로 한 섹션만 읽어요.
3. **단계별 모델링**: 단계마다 `execute_python` 한 번, 파라미터는 스크립트 맨 위에 둬요.
4. **매 단계 검증**: `model_report`(오류·바디·치수·질량, 약 200토큰). 중요한 단계에서만 `render_views`(2×2 이미지 약 800토큰). 어셈블리는 `check_interference`.
5. **품질 게이트**: 재생성 오류 없음, 의도한 바디 수, 사양 치수 일치, 의도치 않은 간섭 없음, 공정 규칙 충족. 통과해야 다음 단계로 넘어가요.
6. **짧은 보고**: 핵심 치수와 근거, 검증 수치, 다음 선택지 최대 3개.

토큰 절약 요약: 작은 호출 여러 번 대신 단계당 스크립트 하나, 큰 데이터는 출력하지 않기, 이미지는 마일스톤에서만 작게, 다시 쓸 코드는 `store`에 저장, 검증된 API 레시피(`knowledge_get("solidworks-api")`) 사용. 자세한 내용은 [knowledge/agent-guide.md](knowledge/agent-guide.md), 근거 규칙은 [knowledge/design-policy.md](knowledge/design-policy.md)에 있어요.

### 도구 목록

길이 인자가 있는 도구는 모두 선택 인자 `unit`(mm, cm, m, inch, ft)을 받아요. 비우면 기본 단위(기본 mm)를 써요.

| 분류 | 도구 | 하는 일 | 주요 인자 |
|---|---|---|---|
| 연결 | `connect_solidworks` | 실행 중인 SolidWorks에 연결 (꺼져 있으면 실행) | - |
| 연결 | `get_solidworks_info` | 설치 정보 (버전, 경로, 템플릿) | - |
| 문서 | `create_new_part` | 새 파트 | - |
| 문서 | `create_new_assembly` | 새 어셈블리 | - |
| 문서 | `open_document` | 파일 열기 | `filepath` (필수) |
| 문서 | `save_document` | 저장 (경로를 주면 다른 이름으로 저장) | `filepath` |
| 문서 | `close_document` | 활성 문서 닫기 | `save` (기본 false) |
| 문서 | `get_document_info` | 활성 문서 이름, 경로, 종류 | - |
| 문서 | `list_open_documents` | 열린 문서 목록 | - |
| 스케치 | `create_sketch` | 기본 평면에 스케치 시작 | `plane`: Front / Top / Right (= 정면 / 윗면 / 우측면) |
| 스케치 | `create_sketch_on_face` | 3D 좌표로 고른 면 위에 스케치 | `x`, `y`, `z` |
| 스케치 | `draw_line` | 선 | `x1`, `y1`, `x2`, `y2` |
| 스케치 | `draw_circle` | 원 | `x`, `y`, `radius` |
| 스케치 | `draw_rectangle` | 두 모서리로 사각형 | `x1`, `y1`, `x2`, `y2` |
| 스케치 | `draw_arc` | 중심·반지름·시작/끝 각도(°)로 호 | `cx`, `cy`, `radius`, `start_angle`, `end_angle` |
| 스케치 | `draw_polygon` | 정다각형 | `cx`, `cy`, `radius`, `sides` |
| 스케치 | `close_sketch` | 스케치 종료 | - |
| 스케치 | `get_sketch_status` | 스케치 상태 진단 | - |
| 피처 | `extrude_sketch` | 돌출 보스 | `depth`, `both_directions` |
| 피처 | `cut_extrude` | 돌출 컷 | `depth`, `through_all`, `both_directions` |
| 피처 | `fillet_edges` | 선택한 모서리에 필렛 | `radius` |
| 피처 | `chamfer_edges` | 선택한 모서리에 모따기 | `distance`, `angle` |
| 피처 | `list_features` | 피처 트리 목록 (이름, 종류, 억제 여부) | - |
| 유틸 | `set_units` | 기본 단위 변경 | `unit`: mm / cm / m / inch |
| 유틸 | `execute_python` | SolidWorks API를 쓰는 Python 코드 실행 (도우미 주입) | `code`, `report` |
| 검증 | `model_report` | 활성 문서 요약: 재생성 오류, 피처, 바디, 경계 상자(mm), 부피, 질량, 재질 | - |
| 검증 | `render_views` | 표준 뷰를 작은 라벨 이미지 하나로 (스케치·평면 숨김, 사용자 뷰 복원) | `views`, `size`(기본 384), `hide_references` |
| 검증 | `export_model` | STEP, STL, 3MF, IGES, Parasolid 등으로 사본 저장 | `format`(기본 step), `path` |
| 검증 | `check_interference` | 어셈블리 부품 사이 간섭 부피(mm³) | - |
| 지식 | `knowledge_search` | 설계 지식 베이스 검색 (한글·영어 키워드) | `query`, `limit` |
| 지식 | `knowledge_get` | 섹션 하나, 주제 전체, 또는 `index` | `id` |

`fillet_edges`와 `chamfer_edges`는 모서리가 먼저 선택돼 있어야 해요. SolidWorks에서 직접 고르거나 `execute_python`으로 선택하세요.

### execute_python 고급 사용

기본 도구로 안 되는 작업(로프트, 패턴, 어셈블리 메이트, 질량 특성, 이미지 저장 등)은 `execute_python`으로 SolidWorks API를 직접 쓸 수 있어요.

- 쓸 수 있는 변수: `sw`(SldWorks.Application), `doc`(활성 문서), `automation`(서버의 SolidWorksAutomation 객체), `win32com`, `pythoncom`, `math`, `os`, `json`
- 주입되는 도우미: `val`, `call`, `arr`, `strings`, `byref_int`, `byref_bool`, `select`(SelectByID2), `plane("front"/"top"/"right")`(한국어 평면 이름 자동), `feats()`, `feat(이름)`, `active()`, `report()`, `render(뷰)`, `store`(호출 사이에 유지되는 dict), `mm`(0.001), `deg`(π/180)
- `print()` 출력과 `result` 변수 값이 결과로 돌아와요. `report: true`로 부르면 실행 뒤 모델 요약이 붙고, `render()`는 이미지를 결과에 붙여요.
- 코드는 이 PC에서 그대로 실행되니까, 믿을 수 있는 요청에만 쓰세요.

SolidWorks 2025는 late binding으로 연결돼서 COM 호출에 주의할 점이 있어요.

1. **인자 없는 멤버는 접근하는 순간 실행돼요.** `GetTitle`, `GetType`, `FirstFeature`, `GetNextFeature`, `GetFirstDocument` 같은 멤버 뒤에 `()`를 붙이면 "구성원이 없습니다"(member not found)나 `'int' object is not callable` 오류가 나요.
2. **인자 있는 메서드가 엉뚱하게 실행되면** 호출 전에 `obj._FlagAsMethod("메서드이름")`을 부르세요.
3. **숫자 배열 인자**는 `win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, 값목록)`으로 넘기세요.
4. **한국어 SolidWorks**에서는 기본 평면과 원점 이름이 `정면`, `윗면`, `우측면`, `원점`이에요. 표준 뷰는 이름 대신 번호를 쓰세요. 예: `doc.ShowNamedView2("", 7)` (등각 보기).

```python
P = dict(w=60.0, h=40.0, t=8.0)          # w, h [req]; t [neutral, R10]
sm = doc.SketchManager
select(doc, plane("top"), "PLANE")       # 한국어 UI에서도 "윗면"을 찾아요
call(sm, "InsertSketch", True)
call(sm, "CreateCenterRectangle", 0, 0, 0, P["w"] / 2 * mm, P["h"] / 2 * mm, 0)
call(sm, "InsertSketch", True)
result = report()                        # 오류, 바디, 경계 상자, 질량
```

### 설계 지식 베이스

에이전트가 `knowledge/` 폴더의 Markdown 노트를 검색해서 써요. 토큰을 아끼려고 본문은 영어로 쓰고, 한글 키워드는 태그와 검색 사전으로 연결했어요.

| 주제 | 파일 | 내용 |
|---|---|---|
| 에이전트 가이드 | `agent-guide.md` | 작업 흐름, 토큰 절약, 품질 게이트, 보고 형식 |
| 설계 정책 | `design-policy.md` | 근거 순서, 중립 기본값(대칭·1:1·표준수), 안전율, 형상 기본값 |
| 기어 | `gears.md` | 종류 선정, 스퍼·헬리컬·베벨·스파이럴 베벨·웜·유성 공식, 강도, 검증된 모델링 방법 |
| 베어링 | `bearings.md` | 종류, 68xx·69xx·60xx·62xx 치수, 수명, 끼워맞춤, 숄더 |
| 체결 | `fasteners.md` | 피치·탭 드릴, ISO 273 구멍, 카운터보어, 체결 길이, 토크, 핀 |
| 공차 | `fits-tolerances.md` | ISO 286 끼워맞춤 값, IT 등급, ISO 2768, 3D 프린팅 공차 |
| 축·키 | `shafts-keys.md` | 축 설계식, 키 치수, 스냅링 홈, D컷 |
| 재료 | `materials.md` | 금속·플라스틱·3D 프린팅 재료 물성 |
| DFM | `dfm.md` | 가공, 판금, 사출, FDM·SLA·SLS 규칙 |
| API 레시피 | `solidworks-api.md` | 검증된 SolidWorks API 호출 (스케치, 로프트, 패턴, 구성, 메이트, 검사) |

노트를 추가하려면 같은 형식(맨 위 `title`, `tags`, `summary`와 `## ` 섹션)으로 `knowledge/`에 `.md` 파일을 넣고 Claude를 다시 시작하세요. 수치를 넣을 때는 출처(규격 번호, 카탈로그)를 함께 적어 주세요.

### 설정 파일 config.json

`solidworks_mcp/config.json`을 고치면 코드를 건드리지 않고 동작을 바꿀 수 있어요. 바꾼 뒤에는 Claude를 다시 시작하세요.

| 키 | 기본값 | 설명 |
|---|---|---|
| `exe_path` | `"auto"` | `SLDWORKS.exe` 경로, `auto`면 레지스트리에서 찾음 |
| `part_template`, `assembly_template`, `drawing_template` | `"auto"` | 새 문서 템플릿 경로 |
| `startup_timeout` | `120` | SolidWorks 실행을 기다리는 시간(초) |
| `connection_retry_interval` | `5` | 연결 재시도 간격(초) |
| `max_retries` | `3` | 연결 재시도 횟수 |
| `default_unit` | `"mm"` | 기본 길이 단위 |
| `log_level` | `"INFO"` | 로그 수준 (DEBUG, INFO, WARNING, ERROR) |
| `log_file` | `"solidworks_mcp.log"` | 로그 파일 이름 (`solidworks_mcp` 폴더 안) |
| `default_extrude_depth`, `default_fillet_radius`, `default_chamfer_distance`, `default_circle_radius` | `10`, `2`, `2`, `25` | 인자를 생략했을 때 쓰는 값(mm) |

### 문제 해결

**Claude에 SolidWorks 도구가 안 보여요**

1. Claude를 트레이 아이콘 → 종료(Quit)로 완전히 끄고 다시 실행하세요.
2. 설정 → 개발자에서 `solidworks` 상태를 확인하세요.
3. `setup_mcp.log`에서 `could not update` 같은 메시지가 있는지 보세요.
4. Claude의 MCP 로그를 보세요: `%APPDATA%\Claude\logs\mcp-server-solidworks.log` (MSIX 설치판은 `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\logs\`).

**`pip install -r requirements.txt`가 실패해요**: 이 저장소의 `requirements.txt`를 쓰고 있는지 확인하세요 (`asyncio-compat` 없음, `mcp<2`).

**서버가 바로 꺼지고 로그에 `'Server' object has no attribute 'list_tools'`가 있어요**: mcp 2.x가 설치된 거예요. `.venv\Scripts\python.exe -m pip install "mcp>=1,<2"`

**"구성원이 없습니다"(Member not found) 오류**: 위 [execute_python 고급 사용](#execute_python-고급-사용)의 COM 규칙을 보세요. 이 저장소의 기본 도구는 수정돼 있어요.

**연결이 안 돼요**: SolidWorks가 실행 중인지, 라이선스나 시작 대화상자가 떠 있지 않은지 확인하세요. `get_solidworks_info`로 설치가 탐지되는지 보고, 안 되면 `config.json`의 `exe_path`에 경로를 직접 넣으세요.

**폴더를 옮겼어요**: `setup_windows.bat`을 다시 실행하면 경로가 갱신돼요.

### 업데이트와 제거

- 업데이트: `git pull` 후 `setup_windows.bat`을 다시 실행하세요 (새 패키지가 설치돼요).
- 제거: Claude 설정 파일에서 `solidworks` 항목을 지우고 `.venv` 폴더를 삭제하세요. 설치 전 설정은 `claude_desktop_config.json.bak-*` 백업에 있어요.

### 로드맵

SolidWorks 지원을 가장 먼저 해요. 진행 순서:

- [x] **Text-to-CAD 검증 루프**: `model_report`, `render_views`, `export_model`, `check_interference`, execute_python 도우미
- [x] **에이전트 가이드**: 토큰 절약 규칙과 설계 근거 규칙 (서버 instructions)
- [x] **설계 지식 베이스 1차**: 설계 정책, 기어, 베어링, 체결, 공차, 축·키, 재료, DFM, API 레시피
- [ ] **부품 DB**: KS/ISO 표준 부품 치수 표와, 사용자가 확인한 한국 미스미 품번 등록·검색 (미스미 사이트는 robots.txt와 약관이 자동 수집을 막아서 크롤링하지 않아요)
- [ ] **기어 생성기**: 스퍼, 헬리컬, 베벨, 스파이럴 베벨 (파라미터 기반)
- [ ] **최적화**: 토폴로지 최적화, 열·CFD 해석 (SOLIDWORKS Simulation, Flow Simulation API)

### 프로젝트 구조

```
Solidworks-MCP/
├── setup_windows.bat          # 원클릭 설치 (더블클릭)
├── setup_mcp.py               # 설치 로직: .venv, 패키지, 자가 진단, Claude 등록
├── solidworks_mcp_server.py   # MCP 서버 진입점
├── requirements.txt
├── knowledge/                 # 설계 지식 베이스 (Markdown 노트)
├── solidworks_mcp/
│   ├── server.py              # MCP 도구 정의와 처리
│   ├── instructions.md        # 매 세션 에이전트에게 주는 작업 규칙
│   ├── verification.py        # model_report, render_views, export_model, check_interference
│   ├── knowledge.py           # 지식 베이스 검색
│   ├── com.py                 # late binding COM 도우미 (val, call, arr, plane ...)
│   ├── config.py, config.json # 설정
│   ├── constants.py           # SolidWorks 상수
│   ├── automation/            # base(연결), documents, sketches, features
│   └── utils/                 # 단위 변환, SolidWorks 설치 탐지
├── scripts/                   # 원본 프로젝트의 VBS 예제
├── solidworks_com.py, solidworks_simulation.py   # 원본 프로젝트의 이전 버전 스크립트
└── DEVELOPMENT_ROADMAP.md     # 원본 프로젝트의 개발 계획
```

### 라이선스와 크레딧

MIT 라이선스예요 ([LICENSE](LICENSE)). 원본 프로젝트: [alisamsam/Solidworks-MCP](https://github.com/alisamsam/Solidworks-MCP), Samsaam Ali Baig. 원본 저작권 표시와 라이선스 문구를 유지해 주세요.

---

## English

### Contents

1. [Overview](#overview)
2. [Changes from the original](#changes-from-the-original)
3. [Requirements](#requirements)
4. [Quick start](#quick-start)
5. [What the installer does](#what-the-installer-does)
6. [Manual setup](#manual-setup)
7. [Usage](#usage)
8. [Text-to-CAD workflow](#text-to-cad-workflow)
9. [Tool reference](#tool-reference)
10. [Advanced: execute_python](#advanced-execute_python)
11. [Design knowledge base](#design-knowledge-base)
12. [Configuration (config.json)](#configuration-configjson)
13. [Troubleshooting](#troubleshooting)
14. [Updating and uninstalling](#updating-and-uninstalling)
15. [Roadmap](#roadmap)
16. [Project structure](#project-structure)
17. [License and credits](#license-and-credits)

### Overview

SolidWorks MCP Server is a [Model Context Protocol](https://modelcontextprotocol.io/) server that lets an AI agent such as Claude drive SolidWorks. Instead of clicking through menus, you describe the geometry you want and Claude builds it through the SolidWorks COM API: parts, sketches and features.

- 31 tools: connection, documents, sketches, features, utilities, `execute_python` for direct SolidWorks API access, verification (text-to-CAD) and design-knowledge search
- Agent working rules (token budget, design rationale) are applied automatically in every session
- SolidWorks 2023–2025, installation auto-detected from the registry
- Units: mm, cm, m, inch, ft (default mm)
- Activity log: `solidworks_mcp/solidworks_mcp.log`

### Changes from the original

| Area | Change |
|---|---|
| Install fix | Removed `asyncio-compat` from `requirements.txt`. It does not exist on PyPI, so `pip install -r requirements.txt` always failed. |
| Startup fix | Pinned `mcp>=1.0.0,<2`. mcp 2.x removed the `Server.list_tools()` / `call_tool()` decorators this server uses, so the server crashed on startup with `AttributeError`. |
| One-click setup | `setup_windows.bat` + `setup_mcp.py` create the virtual environment, install packages, self-test the server and register it with Claude Desktop. |
| SolidWorks 2025 COM | Added `_com_value()` in `automation/base.py` and fixed `list_open_documents` ("Member not found"), `get_document_info` (`'int' object is not callable`) and `list_features` (returned only the first feature; suppression state was always false). |
| Localized SolidWorks | `create_sketch` only looked for "Front Plane", so it failed in non-English UIs (Korean: 정면/윗면/우측면). It now falls back to the default planes' actual names. |
| Repository cleanup | `.env` removed (the original contained an API key; the server does not use it), `.venv/` ignored, CRLF line endings enforced for `.bat` files. |
| Text-to-CAD verification | Added `model_report`, `render_views`, `export_model`, `check_interference`; `execute_python` gets injected helpers and a `report` option. |
| Design knowledge base | 10 notes in `knowledge/` with `knowledge_search` and `knowledge_get`. |
| Agent guide | Workflow, token rules and rationale policy are sent as MCP server instructions in every session. |
| Fewer output tokens | No duplicated `execute_python` output, compact JSON without `\u` escapes, tracebacks trimmed to the script frames. |

### Requirements

- Windows 10 / 11 (64-bit)
- SolidWorks 2023–2025, installed and licensed
- Python 3.10 or newer: the python.org installer or the Python Install Manager (`py`)
- Claude Desktop or Claude Code
- Internet access for the first install (pip packages)

Tested with SolidWorks 2025 (revision 33.5.0, Korean UI), Python 3.14.7 and Claude Desktop for Windows (Microsoft Store/MSIX build).

### Quick start

1. **Get the code**

   ```powershell
   git clone https://github.com/hayward2007/solidworks-mcp.git
   cd solidworks-mcp
   ```

   A ZIP download works too. The folder path is written into Claude's config, so run the installer again if you move the folder later.

2. **Quit Claude Desktop completely**: right-click the Claude icon in the system tray (bottom-right, possibly under the **^** arrow) and choose **Quit**. Closing the window leaves it running in the background, and it will not read the new config.

3. **Double-click `setup_windows.bat`** (or run `py setup_mcp.py` in a terminal). If Claude is still running, the script asks you to quit it. You are done when it prints `All set`.

4. **Open SolidWorks, start Claude Desktop**, and ask Claude: "Connect to SolidWorks".

In Claude, Settings → Developer should show the `solidworks` server as running.

### What the installer does

1. Finds Python 3.10+: the `py` launcher, then `python` on PATH, then `%LOCALAPPDATA%\Python\pythoncore-3.*`, `%LOCALAPPDATA%\Programs\Python\Python3*` and `%ProgramFiles%\Python3*`.
2. Creates a virtual environment in `.venv` inside the project folder (reuses a working one).
3. Installs `requirements.txt` (`mcp` 1.x, `pywin32`, `python-dotenv`, `Pillow`).
4. Self-test: starts the server over stdio, exactly like Claude Desktop does, and checks the MCP handshake and the tool list.
5. Registers the `solidworks` server in Claude Desktop's config. Other servers and settings are kept, and a `claude_desktop_config.json.bak-date-time` backup is written before any change. The Microsoft Store (MSIX) config location is updated too.
6. Saves everything it printed to `setup_mcp.log`.

It is safe to run again; an existing registration shows `already up to date`.

### Manual setup

#### 1) Install the packages

```powershell
cd C:\path\to\Solidworks-MCP
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

#### 2) Claude Desktop

Open Claude → Settings → Developer → **Edit Config** and add this under `mcpServers` in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "C:\\path\\to\\Solidworks-MCP\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\Solidworks-MCP\\solidworks_mcp_server.py"]
    }
  }
}
```

Config file locations:

- Standard install: `%APPDATA%\Claude\claude_desktop_config.json`
- Microsoft Store/MSIX install: `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`

Use the full path to the `.venv` interpreter rather than `"command": "python"`: `python` on PATH may be the Microsoft Store alias or a different Python without the packages. After saving, quit Claude from the tray and start it again.

#### 3) Claude Code

```powershell
claude mcp add --scope user solidworks -- "C:\path\to\Solidworks-MCP\.venv\Scripts\python.exe" "C:\path\to\Solidworks-MCP\solidworks_mcp_server.py"
claude mcp list
```

### Usage

1. Open SolidWorks first. If it is not running, `connect_solidworks` starts it and waits up to 120 seconds.
2. Ask Claude in plain language. Lengths are in mm unless you say otherwise.

Examples:

- "Connect to SolidWorks"
- "Create a new part, draw a 30 mm radius circle on the Top plane and extrude it 15 mm"
- "Draw a 100 × 50 mm rectangle on the Front plane, extrude it 20 mm, then cut a 10 mm hole through the center"
- "List the features" / "List open documents" / "Show the active document info"
- "Save it as C:\work\bracket.SLDPRT"
- "Use execute_python to compute the volume and mass of this part"

Claude typically chains `create_sketch` → `draw_*` → `close_sketch` → `extrude_sketch`. If a sketch is left open, `get_sketch_status` shows its state.

### Text-to-CAD workflow

A loop that lets the agent turn short or vague requests into a spec, then build, look and measure, and iterate quickly. It is sent to the agent in every session as the server instructions (`solidworks_mcp/instructions.md`).

1. **Spec**: purpose, envelope, interfaces, loads/motion, process and material in at most ~10 lines. Every number gets a basis, in this order: [req] requirement or existing geometry > [std] standard > [calc] calculation > [cat] catalogue or user-verified MISUMI part > [dfm] process rule > [heur] rule of thumb > [neutral] a neutral value when nothing else applies (symmetry, 1:1, equal spacing, R10 preferred numbers, whole mm).
2. **Look up only what is needed**: `knowledge_search`, then `knowledge_get` for one section.
3. **Build in stages**: one `execute_python` call per stage, parameters at the top of the script.
4. **Verify every stage**: `model_report` (errors, bodies, box, mass; about 200 tokens), `render_views` only at milestones (2×2 image about 800 tokens), `check_interference` for assemblies.
5. **Quality gate**: no rebuild errors, intended body count, dimensions match the spec, no unintended interference, process rules met, before moving on.
6. **Short report**: key dimensions with their basis, check numbers, at most 3 next options.

Token rules in short: one script per stage instead of many small calls, never print large data, small images only at milestones, keep reusable code in `store`, use the verified recipes (`knowledge_get("solidworks-api")`). Details: [knowledge/agent-guide.md](knowledge/agent-guide.md); rationale rules: [knowledge/design-policy.md](knowledge/design-policy.md).

### Tool reference

Every tool that takes lengths also accepts an optional `unit` (mm, cm, m, inch, ft); when omitted, the default unit (mm) is used.

| Category | Tool | What it does | Main arguments |
|---|---|---|---|
| Connection | `connect_solidworks` | Connect to the running SolidWorks (starts it if needed) | - |
| Connection | `get_solidworks_info` | Installation info (version, path, templates) | - |
| Documents | `create_new_part` | New part | - |
| Documents | `create_new_assembly` | New assembly | - |
| Documents | `open_document` | Open a file | `filepath` (required) |
| Documents | `save_document` | Save (Save As when a path is given) | `filepath` |
| Documents | `close_document` | Close the active document | `save` (default false) |
| Documents | `get_document_info` | Active document name, path and type | - |
| Documents | `list_open_documents` | Open documents | - |
| Sketches | `create_sketch` | Start a sketch on a default plane | `plane`: Front / Top / Right |
| Sketches | `create_sketch_on_face` | Sketch on the face found at a 3D point | `x`, `y`, `z` |
| Sketches | `draw_line` | Line | `x1`, `y1`, `x2`, `y2` |
| Sketches | `draw_circle` | Circle | `x`, `y`, `radius` |
| Sketches | `draw_rectangle` | Rectangle from two corners | `x1`, `y1`, `x2`, `y2` |
| Sketches | `draw_arc` | Arc from center, radius and start/end angles (°) | `cx`, `cy`, `radius`, `start_angle`, `end_angle` |
| Sketches | `draw_polygon` | Regular polygon | `cx`, `cy`, `radius`, `sides` |
| Sketches | `close_sketch` | Exit the active sketch | - |
| Sketches | `get_sketch_status` | Sketch diagnostics | - |
| Features | `extrude_sketch` | Boss-extrude | `depth`, `both_directions` |
| Features | `cut_extrude` | Cut-extrude | `depth`, `through_all`, `both_directions` |
| Features | `fillet_edges` | Fillet the selected edges | `radius` |
| Features | `chamfer_edges` | Chamfer the selected edges | `distance`, `angle` |
| Features | `list_features` | Feature tree (name, type, suppressed) | - |
| Utilities | `set_units` | Change the default unit | `unit`: mm / cm / m / inch |
| Utilities | `execute_python` | Run Python with SolidWorks API access (helpers injected) | `code`, `report` |
| Verification | `model_report` | Active document summary: rebuild errors, features, bodies, bounding box (mm), volume, mass, material | - |
| Verification | `render_views` | One small labelled image of standard views (sketches/planes hidden, user's view restored) | `views`, `size` (default 384), `hide_references` |
| Verification | `export_model` | Save a copy as STEP, STL, 3MF, IGES, Parasolid, ... | `format` (default step), `path` |
| Verification | `check_interference` | Interference volumes (mm³) between assembly components | - |
| Knowledge | `knowledge_search` | Search the design knowledge base (Korean or English keywords) | `query`, `limit` |
| Knowledge | `knowledge_get` | One section, a whole topic, or `index` | `id` |

`fillet_edges` and `chamfer_edges` work on edges that are already selected; select them in SolidWorks or with `execute_python`.

### Advanced: execute_python

For anything the basic tools do not cover (lofts, patterns, assembly mates, mass properties, image export, ...) use `execute_python` to call the SolidWorks API directly.

- Available names: `sw` (SldWorks.Application), `doc` (active document), `automation` (the server's SolidWorksAutomation object), `win32com`, `pythoncom`, `math`, `os`, `json`
- Injected helpers: `val`, `call`, `arr`, `strings`, `byref_int`, `byref_bool`, `select` (SelectByID2), `plane("front"/"top"/"right")` (localized plane names), `feats()`, `feat(name)`, `active()`, `report()`, `render(views)`, `store` (a dict kept between calls), `mm` (0.001), `deg` (π/180)
- Whatever you `print()` and the value of `result` are returned. With `report: true` the model report is appended; `render()` attaches an image.
- The code runs as-is on this PC, so only use it with requests you trust.

SolidWorks 2025 is reached through late binding, which has a few COM pitfalls:

1. **Zero-argument members run as soon as you access them.** Adding `()` after members such as `GetTitle`, `GetType`, `FirstFeature`, `GetNextFeature` or `GetFirstDocument` raises "Member not found" or `'int' object is not callable`.
2. **If a method that takes arguments misbehaves**, call `obj._FlagAsMethod("MethodName")` before calling it.
3. **Pass numeric arrays** as `win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values)`.
4. **Localized SolidWorks** uses localized names for the default planes and origin (Korean: `정면`, `윗면`, `우측면`, `원점`). Use view IDs instead of view names, for example `doc.ShowNamedView2("", 7)` for isometric.

```python
P = dict(w=60.0, h=40.0, t=8.0)          # w, h [req]; t [neutral, R10]
sm = doc.SketchManager
select(doc, plane("top"), "PLANE")       # also finds the localized Top plane
call(sm, "InsertSketch", True)
call(sm, "CreateCenterRectangle", 0, 0, 0, P["w"] / 2 * mm, P["h"] / 2 * mm, 0)
call(sm, "InsertSketch", True)
result = report()                        # errors, bodies, box, mass
```

### Design knowledge base

The agent searches the Markdown notes in `knowledge/`. Notes are written in English to save tokens; Korean keywords are linked through tags and a search dictionary.

| Topic | File | Contents |
|---|---|---|
| Agent guide | `agent-guide.md` | workflow, token rules, quality gate, report format |
| Design policy | `design-policy.md` | basis ladder, neutral defaults (symmetry, 1:1, preferred numbers), safety factors, geometry defaults |
| Gears | `gears.md` | type selection; spur, helical, bevel, spiral bevel, worm, planetary formulas; strength; verified modeling recipe |
| Bearings | `bearings.md` | types, 68xx/69xx/60xx/62xx dimensions, life, fits, shoulders |
| Fasteners | `fasteners.md` | pitches and tap drills, ISO 273 holes, counterbores, engagement, torque, pins |
| Fits and tolerances | `fits-tolerances.md` | ISO 286 fit values, IT grades, ISO 2768, 3D printing allowances |
| Shafts and keys | `shafts-keys.md` | shaft sizing, key dimensions, retaining ring grooves, D-cuts |
| Materials | `materials.md` | metals, plastics and 3D printing materials |
| DFM | `dfm.md` | machining, sheet metal, injection moulding, FDM/SLA/SLS rules |
| API recipes | `solidworks-api.md` | verified SolidWorks API calls (sketches, lofts, patterns, configurations, mates, checks) |

To add a note, put a `.md` file in `knowledge/` with the same layout (`title`, `tags`, `summary` at the top, `## ` sections) and restart Claude. Give a source (standard number, catalogue) for every value.

### Configuration (config.json)

Edit `solidworks_mcp/config.json` to change behavior without touching code, then restart Claude.

| Key | Default | Description |
|---|---|---|
| `exe_path` | `"auto"` | Path to `SLDWORKS.exe`; `auto` reads the registry |
| `part_template`, `assembly_template`, `drawing_template` | `"auto"` | Templates for new documents |
| `startup_timeout` | `120` | Seconds to wait for SolidWorks to start |
| `connection_retry_interval` | `5` | Seconds between connection retries |
| `max_retries` | `3` | Connection retries |
| `default_unit` | `"mm"` | Default length unit |
| `log_level` | `"INFO"` | DEBUG, INFO, WARNING or ERROR |
| `log_file` | `"solidworks_mcp.log"` | Log file name (inside `solidworks_mcp`) |
| `default_extrude_depth`, `default_fillet_radius`, `default_chamfer_distance`, `default_circle_radius` | `10`, `2`, `2`, `25` | Values used when an argument is omitted (mm) |

### Troubleshooting

**The SolidWorks tools don't show up in Claude**

1. Quit Claude from the tray icon (Quit) and start it again.
2. Check the `solidworks` server under Settings → Developer.
3. Look for `could not update` messages in `setup_mcp.log`.
4. Read Claude's MCP log: `%APPDATA%\Claude\logs\mcp-server-solidworks.log` (MSIX build: `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\logs\`).

**`pip install -r requirements.txt` fails**: make sure you are using this repository's `requirements.txt` (no `asyncio-compat`, `mcp<2`).

**The server exits immediately and the log shows `'Server' object has no attribute 'list_tools'`**: mcp 2.x got installed. Run `.venv\Scripts\python.exe -m pip install "mcp>=1,<2"`.

**"Member not found" errors**: see the COM rules in [Advanced: execute_python](#advanced-execute_python). The built-in tools in this repository are already fixed.

**It can't connect**: check that SolidWorks is running and that no license or startup dialog is open. Run `get_solidworks_info` to see whether the installation is detected; if not, set `exe_path` in `config.json`.

**You moved the folder**: run `setup_windows.bat` again to update the paths.

### Updating and uninstalling

- Update: `git pull`, then run `setup_windows.bat` again (installs new packages).
- Uninstall: remove the `solidworks` entry from Claude's config and delete the `.venv` folder. Your pre-install config is in the `claude_desktop_config.json.bak-*` backup.

### Roadmap

SolidWorks support comes first. Order of work:

- [x] **Text-to-CAD verification loop**: `model_report`, `render_views`, `export_model`, `check_interference`, execute_python helpers
- [x] **Agent guide**: token rules and design-rationale rules (server instructions)
- [x] **Design knowledge base v1**: design policy, gears, bearings, fasteners, fits, shafts and keys, materials, DFM, API recipes
- [ ] **Parts database**: KS/ISO standard part tables plus MISUMI Korea part numbers registered by the user (the MISUMI site's robots.txt and terms forbid automated collection, so it is not crawled)
- [ ] **Gear generators**: parametric spur, helical, bevel and spiral bevel gears
- [ ] **Optimization**: topology optimization, thermal and CFD studies (SOLIDWORKS Simulation and Flow Simulation APIs)

### Project structure

```
Solidworks-MCP/
├── setup_windows.bat          # one-click installer (double-click)
├── setup_mcp.py               # installer logic: .venv, packages, self-test, Claude registration
├── solidworks_mcp_server.py   # MCP server entry point
├── requirements.txt
├── knowledge/                 # design knowledge base (Markdown notes)
├── solidworks_mcp/
│   ├── server.py              # MCP tool definitions and handlers
│   ├── instructions.md        # working rules sent to the agent in every session
│   ├── verification.py        # model_report, render_views, export_model, check_interference
│   ├── knowledge.py           # knowledge base search
│   ├── com.py                 # late-binding COM helpers (val, call, arr, plane, ...)
│   ├── config.py, config.json # configuration
│   ├── constants.py           # SolidWorks constants
│   ├── automation/            # base (connection), documents, sketches, features
│   └── utils/                 # unit conversion, SolidWorks detection
├── scripts/                   # VBS examples from the original project
├── solidworks_com.py, solidworks_simulation.py   # earlier scripts from the original project
└── DEVELOPMENT_ROADMAP.md     # the original project's development plan
```

### License and credits

MIT License ([LICENSE](LICENSE)). Original project: [alisamsam/Solidworks-MCP](https://github.com/alisamsam/Solidworks-MCP) by Samsaam Ali Baig. Please keep the original copyright notice and license text.
