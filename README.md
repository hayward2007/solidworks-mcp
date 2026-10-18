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

## 설치: Claude에게 한 마디 · Install: just ask Claude

> **"https://github.com/hayward2007/solidworks-mcp 설치해줘"** · *"Install https://github.com/hayward2007/solidworks-mcp"*

Claude Code(Windows)는 바로 설치하고, Claude Desktop(Cowork)은 더블클릭할 설치 파일을 주고 설계 스킬 저장 카드를 띄워요. 직접 하려면 PowerShell에 이 한 줄을 붙여 넣으세요.<br>
Claude Code on Windows installs it right away; Claude Desktop (Cowork) gives you an installer to double-click and offers the design skill to save. To do it yourself, paste this line into PowerShell:

```powershell
irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1 | iex
```

끝나면 SolidWorks를 열고, Claude Desktop을 트레이 아이콘 → 종료(Quit)로 완전히 끈 뒤 다시 켜세요.<br>
Then open SolidWorks, fully quit Claude Desktop (tray icon → Quit) and start it again.

<details>
<summary><b>For Claude: how to install this repository</b></summary>

The server has to run on the user's Windows PC next to SolidWorks; never install it inside a Linux VM or a cloud container.

1. **If you can run commands on that PC** (Claude Code on Windows; from WSL call `powershell.exe`), run:

   ```
   powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1 | iex"
   ```

   It puts the code in `%USERPROFILE%\solidworks-mcp` (or updates it), creates `.venv`, installs the requirements, self-tests the server (34 tools), registers `solidworks` in Claude Desktop and in Claude Code (`claude mcp add --scope user`) and copies the skill to `~/.claude/skills/solidworks-design`. The first run takes a few minutes; success ends with `All set`.
   - If it reports `Python 3.10 or newer (64-bit) was not found`, ask the user, then install Python 3.13 with winget and continue:
     `powershell -NoProfile -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1))) -InstallPython"`
   - Other options go in the same place: `-InstallDir <path>`, `-NoClaudeDesktop`, `-NoClaudeCode`, `-NoSkill`, `-Uninstall`.
2. **If you cannot run Windows programs** (Claude Desktop / Cowork, where your shell is a Linux VM or a cloud container):
   - Download `https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/setup_windows.bat`, save it into a folder the user connected (or send it as a file) and ask them to double-click it. It runs the same installer and asks before installing Python. Pasting the PowerShell line above works too.
   - Offer the design skill: propose the contents of `skills/solidworks-design/SKILL.md` as a new skill named `solidworks-design` for the user to save. Cowork does not pass MCP server instructions to the model; this skill brings in the working rules.
3. **Afterwards** ask the user to open SolidWorks and to fully quit Claude Desktop (tray icon → Quit) and start it again; in Claude Code a new session is enough. The `solidworks` tools should then be available (`knowledge_get("agent-guide")` is a quick check). If they are not, read `setup_mcp.log` in the install folder and run the installer again while Claude Desktop is closed.

</details>

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
12. [기어 생성기](#기어-생성기)
13. [토폴로지 최적화](#토폴로지-최적화)
14. [설정 파일 config.json](#설정-파일-configjson)
15. [문제 해결](#문제-해결)
16. [업데이트와 제거](#업데이트와-제거)
17. [로드맵](#로드맵)
18. [프로젝트 구조](#프로젝트-구조)
19. [라이선스와 크레딧](#라이선스와-크레딧)

### 소개

SolidWorks MCP Server는 Claude 같은 AI 에이전트가 SolidWorks를 직접 조작하게 해 주는 [Model Context Protocol](https://modelcontextprotocol.io/) 서버예요. 메뉴를 클릭하는 대신 만들고 싶은 형상을 말로 설명하면, Claude가 SolidWorks COM API로 파트를 만들고 스케치를 그리고 피처를 추가해요.

- 도구 34개: 연결, 문서, 스케치, 피처, 유틸리티, SolidWorks API를 직접 실행하는 `execute_python`, 검증(Text-to-CAD), 설계 지식 검색, 기어 생성, 토폴로지 최적화
- 에이전트용 작업 규칙(토큰 절약, 설계 근거)이 매 세션 자동 적용돼요
- SolidWorks 2023–2025 지원, 설치 경로 자동 탐지(레지스트리)
- 단위: mm, cm, m, inch, ft (기본 mm)
- 동작 로그: `solidworks_mcp/solidworks_mcp.log`

### 원본 대비 변경 사항

| 구분 | 내용 |
|---|---|
| 설치 오류 수정 | `requirements.txt`에서 PyPI에 없는 `asyncio-compat`를 뺐어요. 이 줄 때문에 `pip install -r requirements.txt`가 항상 실패했어요. |
| 시작 오류 수정 | `mcp>=1.0.0,<2`로 고정했어요. mcp 2.x는 서버가 쓰는 `Server.list_tools()` / `call_tool()` 데코레이터를 없애서, 설치되면 서버가 `AttributeError`로 바로 꺼져요. |
| 한 줄 설치 | `install.ps1`(PowerShell 한 줄, 또는 `setup_windows.bat` 더블클릭) + `setup_mcp.py`: 코드 받기, Python 찾기(없으면 winget 설치 제안), 가상환경, 패키지, 서버 자가 진단, Claude Desktop·Claude Code 등록, 설계 스킬 설치까지 한 번에 해요. Claude에게 "설치해줘"라고 하면 대신 실행해요. |
| SolidWorks 2025 COM 호환성 | `automation/base.py`에 `_com_value()`를 추가해서 다음을 고쳤어요. `list_open_documents`("구성원이 없습니다" 오류), `get_document_info`(`'int' object is not callable` 오류), `list_features`(첫 피처 1개만 나오고 억제 상태가 항상 false). |
| 한국어 SolidWorks 지원 | `create_sketch`가 "Front Plane"만 찾아서 한국어 UI(정면/윗면/우측면)에서 실패하던 문제를 고쳤어요. 이름으로 못 찾으면 기본 평면 순서로 실제 이름을 찾아요. |
| 저장소 정리 | `.env` 제외(원본에는 API 키가 들어 있었고, 서버는 이 파일을 쓰지 않아요), `.venv/` 무시, `.bat` 파일 줄바꿈(CRLF) 고정. |
| Text-to-CAD 검증 도구 | `model_report`, `render_views`, `export_model`, `check_interference`를 추가하고, `execute_python`에 도우미 주입과 `report` 옵션을 넣었어요. |
| 설계 지식 베이스 | `knowledge/` 노트 12개와 `knowledge_search`, `knowledge_get` 도구. |
| 기어 생성기 | `gear_design`, `create_gear`: 스퍼·헬리컬·헤링본·내접·랙·직선/스파이럴 베벨·웜·웜휠을 규격 공식으로 만들고 부피와 물림 간섭으로 스스로 검증해요. |
| 토폴로지 최적화 | `topology_optimize`: ToPy를 Python 3로 옮긴 2D/3D 강성·메커니즘 최적화, 결과를 SolidWorks 파트로 만들어요. |
| 에이전트 가이드 | 작업 흐름, 토큰 절약, 근거 규칙을 서버 instructions로 매 세션 자동 적용해요. |
| 설계 스킬 | `skills/solidworks-design`: Cowork처럼 서버 instructions를 넘기지 않는 클라이언트에서도 같은 작업 규칙을 불러오는 Claude 스킬이에요. 도구 설명에도 `knowledge_get("agent-guide")` 안내를 넣었어요. |
| 출력 토큰 절감 | `execute_python` 결과 중복 제거, JSON 압축 출력(한글을 `\u` 이스케이프 없이), 트레이스백을 스크립트 부분만 남겨요. |

### 요구 사항

- Windows 10 / 11 (64비트)
- SolidWorks 2023–2025 (설치 및 라이선스 필요)
- Python 3.10 이상(64비트): python.org 설치판 또는 Python Install Manager(`py`) 모두 돼요. 없으면 설치 스크립트가 winget으로 Python 3.13을 설치해 줄 수 있어요
- Claude Desktop 또는 Claude Code
- 처음 설치할 때 인터넷 연결 (pip 패키지 다운로드, 토폴로지 최적화용 numpy·scipy 포함 약 60 MB)

검증 환경: SolidWorks 2025 (revision 33.5.0, 한국어 UI), Python 3.14.7, Claude Desktop (Windows, Microsoft Store/MSIX 설치판).

### 빠른 시작

가장 쉬운 방법은 맨 위처럼 Claude에게 설치해 달라고 하는 거예요. 직접 하려면:

1. **설치 스크립트 실행**: PowerShell에 한 줄을 붙여 넣으세요.

   ```powershell
   irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1 | iex
   ```

   코드는 `%USERPROFILE%\solidworks-mcp`에 받아요. 저장소를 직접 받았다면(`git clone https://github.com/hayward2007/solidworks-mcp.git` 또는 ZIP) 그 폴더의 **`setup_windows.bat`을 더블클릭**해도 돼요. 마지막에 `All set`이 나오면 끝이에요. 폴더 경로가 Claude 설정에 기록되니까, 나중에 폴더를 옮기면 다시 실행하세요.

2. **Claude Desktop 완전히 종료 후 다시 실행**: 작업 표시줄 오른쪽 아래 트레이(**^** 안쪽일 수 있음)의 Claude 아이콘을 우클릭해서 **종료(Quit)** 를 누르고 다시 켜세요. 창만 닫으면 백그라운드에서 계속 돌아가서 새 설정을 읽지 않아요. Claude Code는 새 세션을 시작하면 돼요.

3. **SolidWorks를 열고** Claude에게 "SolidWorks에 연결해줘"라고 말하세요.

Claude의 설정(Settings) → 개발자(Developer)에서 `solidworks` 서버가 running으로 보이면 정상이에요.

**Cowork를 쓴다면 설계 스킬도 저장하세요.** Cowork는 서버 instructions(작업 규칙)를 모델에 넘기지 않아서, `solidworks-design` 스킬이 그 규칙을 불러와요. Cowork에서 Claude에게 "https://github.com/hayward2007/solidworks-mcp 의 solidworks-design 스킬 저장해줘"라고 하면 저장 카드가 떠요. claude.ai에서는 설치 스크립트가 만든 `dist\solidworks-design.zip`을 설정 → Capabilities → Skills에서 올려도 돼요. Claude Code에는 설치 스크립트가 `~/.claude/skills`에 넣어 줘요.

### 설치 스크립트가 하는 일

1. 코드를 받아요: `%USERPROFILE%\solidworks-mcp`에 `git clone`(git이 없으면 GitHub ZIP)하고, 이미 있으면 업데이트해요. 저장소 안의 `setup_windows.bat`으로 실행하면 그 폴더를 그대로 써요.
2. 64비트 Python 3.10 이상을 찾아요: `py -0p` 목록 → `py -3` → PATH의 `python` → `%LOCALAPPDATA%\Python\pythoncore-3.*`, `%LOCALAPPDATA%\Programs\Python\Python3*`, `%ProgramFiles%\Python3*` 순서예요. numpy·scipy·pywin32 휠이 있는 3.10–3.14 중 가장 새 버전을 골라요. 없으면 winget으로 Python 3.13을 설치할지 물어봐요(`-InstallPython`이면 묻지 않고 설치).
3. 프로젝트 폴더에 가상환경 `.venv`를 만들어요 (이미 있으면 다시 써요).
4. `requirements.txt`를 설치해요 (`mcp` 1.x, `pywin32`, `python-dotenv`, `Pillow`, `numpy`, `scipy`).
5. 서버 자가 진단: Claude Desktop과 같은 방식(stdio)으로 서버를 띄워서 MCP 초기화와 도구 목록(34개)을 확인해요.
6. Claude Desktop 설정 파일에 `solidworks` 서버를 등록해요. 다른 서버와 설정은 그대로 두고, 바꾸기 전에 `claude_desktop_config.json.bak-날짜-시간` 백업을 만들어요. Microsoft Store(MSIX) 설치판의 설정 위치도 함께 갱신해요.
7. Claude Code(`claude` CLI)가 있으면 `claude mcp add --scope user`로 등록하고 설계 스킬을 `~/.claude/skills/solidworks-design`에 복사해요. Claude Desktop·claude.ai에 올릴 `dist\solidworks-design.zip`도 만들어요.
8. 화면에 나온 내용을 `setup_mcp.log`에 저장해요.

여러 번 실행해도 안전해요. 이미 등록돼 있으면 `already up to date`가 나와요. 옵션: `-InstallDir 경로`, `-InstallPython`, `-NoClaudeDesktop`, `-NoClaudeCode`, `-NoSkill`, `-Uninstall`. `setup_windows.bat`에도 그대로 넘길 수 있어요(예: `setup_windows.bat -Uninstall`).

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

짧거나 모호한 요청도 에이전트가 사양으로 정리하고, 모델을 직접 보고 재면서 빠르게 반복하게 하는 흐름이에요. 서버 instructions(`solidworks_mcp/instructions.md`)로 매 세션 자동 적용돼요(Cowork는 `solidworks-design` 스킬로).

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
| 기어 | `gear_design` | 기어 치수, 전위, 중심거리, 물림률, 간섭 경고 계산 (CAD 없이) | `kind`, `module`, `teeth` |
| 기어 | `create_gear` | 기어를 네이티브 피처로 만들고 자가 검증 (짝 기어와 물림 검사 선택) | `type`, `module`, `teeth`, `build_mate` |
| 최적화 | `topology_optimize` | 2D/3D 토폴로지 최적화 시작·확인, 결과로 파트 생성 | `problem` 또는 `tpd`, `job`, `build` |

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
| 기어 생성기 | `gear-generators.md` | create_gear 종류, 좌표계, 기본값 근거, 자가 검증, 어셈블리 배치 |
| 토폴로지 최적화 | `topology-optimization.md` | 문제 정의(mm), 기본값 근거, 결과 해석, 파트로 만들기 |
| API 레시피 | `solidworks-api.md` | 검증된 SolidWorks API 호출 (스케치, 로프트, 스윕, 패턴, 구성, 메이트, 검사, STL 불러오기) |

노트를 추가하려면 같은 형식(맨 위 `title`, `tags`, `summary`와 `## ` 섹션)으로 `knowledge/`에 `.md` 파일을 넣고 Claude를 다시 시작하세요. 수치를 넣을 때는 출처(규격 번호, 카탈로그)를 함께 적어 주세요.

### 기어 생성기

`gear_design`(계산만)과 `create_gear`(SolidWorks 네이티브 피처)로 일반적인 기어를 만들어요. 기어 종류는 OpenSCAD 라이브러리 [chrisspen/gears](https://github.com/chrisspen/gears)에 맞췄지만(헤링본 베벨과 체결 구멍 있는 랙은 제외, 유성기어는 `gear_design`으로 계산한 뒤 부품별로 생성), 그 라이브러리는 CC BY-NC-SA 3.0(비상업·동일조건)이라 코드는 쓰지 않고 규격(ISO 21771, ISO 53, Gleason/AGMA 2005, DIN 3975) 공식으로 직접 구현했어요. 사이클로이드와 하모닉 드라이브는 완제품 구매를 권해서 생성 대상에서 뺐어요.

| type | 형상 | 방식 |
|---|---|---|
| `spur`, `helical`, `herringbone` | 외접 스퍼·헬리컬·헤링본 | ISO 53 랙으로 창성한 인볼류트와 트로코이드 이뿌리, 언더컷 자동 반영 |
| `internal` | 내접(링) 기어 | 인볼류트와 원호 이뿌리 필렛 |
| `rack` | 스퍼·헬리컬 랙 | ISO 53 기준 랙, 헬리컬 랙도 끝단 직각 |
| `bevel`, `spiral_bevel` | 직선·스파이럴 베벨 | Tredgold 등가 단면 로프트와 가이드 커브, Gleason 치형 비율 |
| `worm`, `worm_wheel`, `worm_set` | ZA 웜, 웜휠 | 웜은 헬릭스 스윕, 웜휠은 목(throat)이 있는 헬리컬 근사 |

- 기본값과 근거: 압력각 20°와 ISO 53 A [std], 백래시 0.04 m [heur], 치폭 10 m [heur], 작은 피니언은 언더컷 한계 전위 x_min과 V-zero 짝 [std], 링기어 림 d_f + 6 m [heur]. 결과에 근거 태그가 함께 나와요.
- 자가 검증: SolidWorks 부피를 정확한 치형 단면적 × 치폭과 비교(보통 0.1 % 이내), 바디 1개, 재생성 오류 없음, 헬리컬은 재질 탐침으로 나선 방향까지 확인해요.
- `build_mate: true`: 짝 기어(외접은 반대 방향, 내접은 같은 방향)도 만들고 한 피치 굴리면서 임시 바디로 간섭을 재요. 측정값: 스퍼·헬리컬·헤링본·내접·랙 0 mm³, 스파이럴 베벨 0.03–0.09 mm³(Tredgold 근사), 같은 방향 헬리컬 쌍은 162 mm³로 잘못된 조합을 잡아내요.
- 좌표계: 축 +Z, z = 0 면이 정면, 이홈 하나가 +X 중심. 짝 배치와 위상은 결과의 `phase_deg`를 쓰고, 자세한 내용은 지식 베이스 `gear-generators`에 있어요.

예: "모듈 1.5, 18:36 스퍼 기어 한 쌍, 보어 8에 키홈" → `create_gear {"type": "spur", "module": 1.5, "teeth": 18, "mate_teeth": 36, "build_mate": true, "bore": 8, "keyway": true}`

### 토폴로지 최적화

`topology_optimize`는 [ToPy](https://github.com/williamhunter/topy)(MIT)를 Python 3 + scipy로 옮긴 SIMP 최적화예요. 최소 컴플라이언스(강성 최대)와 컴플라이언트 메커니즘을 2D 판재와 3D로 풀어요. 열전도와 CFD는 넣지 않았어요.

- 검증: 요소 강성 행렬이 ToPy의 SymPy 정의와 기계 정밀도로 같고, MBB 보 계산이 Sigmund 99줄 코드와 같은 값을 내요(첫 반복 1e-11, 8회 반복 1e-9).
- 문제는 mm로 정의해요: `size`, `element_size`, `thickness`, `volume_fraction`, `supports`, `loads`, `keep_out`/`keep_in`(볼트 구멍 주변은 보존, 움직이는 부품 자리는 제외), `material`. ToPy `.tpd` 파일도 그대로 받아요.
- 백그라운드 작업으로 돌고 이 호출은 최대 `wait`초 기다려요. 덜 끝났으면 `job`으로 다시 확인해요. 결과에는 반복 수, 부피율, 컴플라이언스, 하중점 변위(mm), 질량, 미리보기 이미지가 들어 있어요.
- `build: true`: 2D 결과는 밀도 0.5 등고선을 스플라인으로 그려 두께만큼 돌출해요(부피 오차 0.02 %). 3D 결과는 STL을 메시 솔리드 바디로 불러와요(다시 모델링할 때 참고용).
- 속도(측정): 2D 120 × 60 요소 약 4초, 3D 40 × 20 × 10 요소 반복당 약 0.7초.

예: 왼쪽 고정, 오른쪽 끝 중앙에 1000 N, 부피 40 %, 두께 6 mm 알루미늄 브래킷 →
`{"problem": {"size": [120, 60], "element_size": 1, "thickness": 6, "volume_fraction": 0.4, "supports": [{"edge": "left"}], "loads": [{"at": [120, 30], "force": [0, -1000]}], "material": {"E": 70000, "density": 2.7}}, "build": true}`

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
4. Claude를 끈 상태에서 설치를 한 번 더 실행해 보세요.
5. Claude의 MCP 로그를 보세요: `%APPDATA%\Claude\logs\mcp-server-solidworks.log` (MSIX 설치판은 `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\logs\`).

**`pip install -r requirements.txt`가 실패해요**: 이 저장소의 `requirements.txt`를 쓰고 있는지 확인하세요 (`asyncio-compat` 없음, `mcp<2`).

**서버가 바로 꺼지고 로그에 `'Server' object has no attribute 'list_tools'`가 있어요**: mcp 2.x가 설치된 거예요. `.venv\Scripts\python.exe -m pip install "mcp>=1,<2"`

**"구성원이 없습니다"(Member not found) 오류**: 위 [execute_python 고급 사용](#execute_python-고급-사용)의 COM 규칙을 보세요. 이 저장소의 기본 도구는 수정돼 있어요.

**연결이 안 돼요**: SolidWorks가 실행 중인지, 라이선스나 시작 대화상자가 떠 있지 않은지 확인하세요. `get_solidworks_info`로 설치가 탐지되는지 보고, 안 되면 `config.json`의 `exe_path`에 경로를 직접 넣으세요.

**폴더를 옮겼어요**: `setup_windows.bat`을 다시 실행하면 경로가 갱신돼요.

### 업데이트와 제거

- 업데이트: 설치할 때의 PowerShell 한 줄을 다시 실행하거나, 저장소에서 `git pull` 후 `setup_windows.bat`을 실행하세요 (새 패키지가 설치돼요).
- 제거: 명령 프롬프트에서 `setup_windows.bat -Uninstall`(또는 `install.ps1 -Uninstall`)을 실행하면 Claude Desktop·Claude Code 등록과 스킬을 지워요. 그다음 폴더를 삭제하세요. 설치 전 설정은 `claude_desktop_config.json.bak-*` 백업에 있어요. Claude 계정에 저장한 스킬은 Claude 설정에서 지우세요.

### 로드맵

SolidWorks 지원을 가장 먼저 해요. 진행 순서:

- [x] **Text-to-CAD 검증 루프**: `model_report`, `render_views`, `export_model`, `check_interference`, execute_python 도우미
- [x] **에이전트 가이드**: 토큰 절약 규칙과 설계 근거 규칙 (서버 instructions)
- [x] **설계 지식 베이스 1차**: 설계 정책, 기어, 베어링, 체결, 공차, 축·키, 재료, DFM, API 레시피
- [ ] **부품 DB**: KS/ISO 표준 부품 치수 표와, 사용자가 확인한 한국 미스미 품번 등록·검색 (미스미 사이트는 robots.txt와 약관이 자동 수집을 막아서 크롤링하지 않아요)
- [x] **기어 생성기**: 스퍼, 헬리컬, 헤링본, 내접, 랙, 직선·스파이럴 베벨, 웜·웜휠 (규격 공식, 부피·물림 자가 검증)
- [x] **토폴로지 최적화**: 2D/3D 강성·컴플라이언트 메커니즘 (ToPy 포팅), 2D 결과는 돌출 파트로
- [ ] **유성기어 어셈블리 자동 배치**와 3D 최적화 결과의 리모델링 보조

열해석과 CFD는 이번 범위에서 뺐어요(SOLIDWORKS Flow Simulation 결과 신뢰성 문제로 보류).

### 프로젝트 구조

```
Solidworks-MCP/
├── install.ps1                # 한 줄 설치 (irm ... | iex): 코드 받기, Python 찾기, setup_mcp.py 실행
├── setup_windows.bat          # 원클릭 설치 (더블클릭하면 install.ps1 실행)
├── setup_mcp.py               # 설치 로직: .venv, 패키지, 자가 진단, Claude Desktop·Claude Code 등록, 스킬
├── skills/solidworks-design/  # Claude 스킬: 설계 작업 규칙 (서버 instructions를 안 넘기는 Cowork 같은 클라이언트용)
├── solidworks_mcp_server.py   # MCP 서버 진입점
├── requirements.txt
├── knowledge/                 # 설계 지식 베이스 (Markdown 노트)
├── solidworks_mcp/
│   ├── server.py              # MCP 도구 정의와 처리
│   ├── instructions.md        # 매 세션 에이전트에게 주는 작업 규칙
│   ├── verification.py        # model_report, render_views, export_model, check_interference
│   ├── knowledge.py           # 지식 베이스 검색
│   ├── com.py                 # late binding COM 도우미 (val, call, arr, plane ...)
│   ├── gears/                 # 기어: geometry(인볼류트), bevel, build(SolidWorks), api(도구 인자)
│   ├── topopt/                # 토폴로지 최적화 (ToPy 포팅): problem, topology, export, run, cad
│   ├── tests/                 # 기어·최적화·설치 단위 테스트 (python -m unittest solidworks_mcp.tests.test_gears ...)
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

토폴로지 최적화 코드(`solidworks_mcp/topopt/`)는 William Hunter의 [ToPy](https://github.com/williamhunter/topy)(MIT)를 옮긴 것이고, 라이선스 전문은 `solidworks_mcp/topopt/LICENSE_TOPY.md`에 있어요. ToPy의 2D 부분은 Ole Sigmund의 99줄 코드를 바탕으로 해요. 기어 생성기는 chrisspen/gears(CC BY-NC-SA 3.0)의 코드를 쓰지 않았어요.

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
12. [Gear generators](#gear-generators)
13. [Topology optimization](#topology-optimization)
14. [Configuration (config.json)](#configuration-configjson)
15. [Troubleshooting](#troubleshooting)
16. [Updating and uninstalling](#updating-and-uninstalling)
17. [Roadmap](#roadmap)
18. [Project structure](#project-structure)
19. [License and credits](#license-and-credits)

### Overview

SolidWorks MCP Server is a [Model Context Protocol](https://modelcontextprotocol.io/) server that lets an AI agent such as Claude drive SolidWorks. Instead of clicking through menus, you describe the geometry you want and Claude builds it through the SolidWorks COM API: parts, sketches and features.

- 34 tools: connection, documents, sketches, features, utilities, `execute_python` for direct SolidWorks API access, verification (text-to-CAD), design-knowledge search, gear generation and topology optimization
- Agent working rules (token budget, design rationale) are applied automatically in every session
- SolidWorks 2023–2025, installation auto-detected from the registry
- Units: mm, cm, m, inch, ft (default mm)
- Activity log: `solidworks_mcp/solidworks_mcp.log`

### Changes from the original

| Area | Change |
|---|---|
| Install fix | Removed `asyncio-compat` from `requirements.txt`. It does not exist on PyPI, so `pip install -r requirements.txt` always failed. |
| Startup fix | Pinned `mcp>=1.0.0,<2`. mcp 2.x removed the `Server.list_tools()` / `call_tool()` decorators this server uses, so the server crashed on startup with `AttributeError`. |
| One-line install | `install.ps1` (one PowerShell line, or double-click `setup_windows.bat`) + `setup_mcp.py` get the code, find Python (or offer to install it with winget), create the virtual environment, install packages, self-test the server, register it with Claude Desktop and Claude Code and install the design skill. Ask Claude to install the repository and it runs this for you. |
| SolidWorks 2025 COM | Added `_com_value()` in `automation/base.py` and fixed `list_open_documents` ("Member not found"), `get_document_info` (`'int' object is not callable`) and `list_features` (returned only the first feature; suppression state was always false). |
| Localized SolidWorks | `create_sketch` only looked for "Front Plane", so it failed in non-English UIs (Korean: 정면/윗면/우측면). It now falls back to the default planes' actual names. |
| Repository cleanup | `.env` removed (the original contained an API key; the server does not use it), `.venv/` ignored, CRLF line endings enforced for `.bat` files. |
| Text-to-CAD verification | Added `model_report`, `render_views`, `export_model`, `check_interference`; `execute_python` gets injected helpers and a `report` option. |
| Design knowledge base | 12 notes in `knowledge/` with `knowledge_search` and `knowledge_get`. |
| Gear generators | `gear_design`, `create_gear`: spur, helical, herringbone, internal, rack, straight/spiral bevel, worm and worm wheel from the standards' formulas, self-checked by volume and mesh interference. |
| Topology optimization | `topology_optimize`: ToPy ported to Python 3 for 2D/3D stiffness and compliant-mechanism problems, results turned into SolidWorks parts. |
| Agent guide | Workflow, token rules and rationale policy are sent as MCP server instructions in every session. |
| Design skill | `skills/solidworks-design`: a Claude skill that brings the same working rules to clients that do not pass server instructions on, such as Cowork. The tool descriptions also point to `knowledge_get("agent-guide")`. |
| Fewer output tokens | No duplicated `execute_python` output, compact JSON without `\u` escapes, tracebacks trimmed to the script frames. |

### Requirements

- Windows 10 / 11 (64-bit)
- SolidWorks 2023–2025, installed and licensed
- Python 3.10 or newer (64-bit): the python.org installer or the Python Install Manager (`py`). Without one, the installer can install Python 3.13 with winget
- Claude Desktop or Claude Code
- Internet access for the first install (pip packages, about 60 MB including numpy and scipy for topology optimization)

Tested with SolidWorks 2025 (revision 33.5.0, Korean UI), Python 3.14.7 and Claude Desktop for Windows (Microsoft Store/MSIX build).

### Quick start

The easiest way is to ask Claude to install it, as shown at the top. To do it yourself:

1. **Run the installer**: paste this line into PowerShell.

   ```powershell
   irm https://raw.githubusercontent.com/hayward2007/solidworks-mcp/main/install.ps1 | iex
   ```

   The code goes to `%USERPROFILE%\solidworks-mcp`. If you downloaded the repository yourself (`git clone https://github.com/hayward2007/solidworks-mcp.git` or a ZIP), you can **double-click `setup_windows.bat`** in it instead. You are done when it prints `All set`. The folder path is written into Claude's config, so run it again if you move the folder later.

2. **Quit Claude Desktop completely and start it again**: right-click the Claude icon in the system tray (bottom-right, possibly under the **^** arrow), choose **Quit**, then start Claude again. Closing the window leaves it running in the background, and it will not read the new config. In Claude Code, start a new session.

3. **Open SolidWorks** and ask Claude: "Connect to SolidWorks".

In Claude, Settings → Developer should show the `solidworks` server as running.

**Using Cowork? Save the design skill too.** Cowork does not pass the server instructions (working rules) to the model; the `solidworks-design` skill brings them in. In Cowork, ask Claude to "save the solidworks-design skill from https://github.com/hayward2007/solidworks-mcp" and save the card it shows. On claude.ai you can upload the `dist\solidworks-design.zip` the installer writes under Settings → Capabilities → Skills. For Claude Code the installer puts the skill into `~/.claude/skills`.

### What the installer does

1. Gets the code: `git clone` into `%USERPROFILE%\solidworks-mcp` (the GitHub ZIP when git is missing), or updates an existing copy. Started from `setup_windows.bat` inside a copy of the repository, it uses that folder as it is.
2. Finds a 64-bit Python 3.10+: the `py -0p` list, `py -3`, `python` on PATH, then `%LOCALAPPDATA%\Python\pythoncore-3.*`, `%LOCALAPPDATA%\Programs\Python\Python3*` and `%ProgramFiles%\Python3*`. It picks the newest of 3.10–3.14, which numpy, scipy and pywin32 ship wheels for. Without one it offers to install Python 3.13 with winget (`-InstallPython` installs it without asking).
3. Creates a virtual environment in `.venv` inside the project folder (reuses a working one).
4. Installs `requirements.txt` (`mcp` 1.x, `pywin32`, `python-dotenv`, `Pillow`, `numpy`, `scipy`).
5. Self-test: starts the server over stdio, exactly like Claude Desktop does, and checks the MCP handshake and the tool list (34 tools).
6. Registers the `solidworks` server in Claude Desktop's config. Other servers and settings are kept, and a `claude_desktop_config.json.bak-date-time` backup is written before any change. The Microsoft Store (MSIX) config location is updated too.
7. If Claude Code (the `claude` CLI) is installed, registers the server with `claude mcp add --scope user` and copies the design skill to `~/.claude/skills/solidworks-design`. It also writes `dist\solidworks-design.zip` for uploading the skill to Claude Desktop / claude.ai.
8. Saves everything it printed to `setup_mcp.log`.

It is safe to run again; an existing registration shows `already up to date`. Options: `-InstallDir <path>`, `-InstallPython`, `-NoClaudeDesktop`, `-NoClaudeCode`, `-NoSkill`, `-Uninstall`; `setup_windows.bat` passes them on (e.g. `setup_windows.bat -Uninstall`).

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

A loop that lets the agent turn short or vague requests into a spec, then build, look and measure, and iterate quickly. It is sent to the agent in every session as the server instructions (`solidworks_mcp/instructions.md`); in Cowork the `solidworks-design` skill brings it in.

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
| Gears | `gear_design` | Gear dimensions, profile shifts, centre distance, contact ratio, interference warnings (no CAD) | `kind`, `module`, `teeth` |
| Gears | `create_gear` | Build a gear as native features and check it (optionally with its mate and a mesh check) | `type`, `module`, `teeth`, `build_mate` |
| Optimization | `topology_optimize` | Start / poll a 2D or 3D topology optimization, build the part from the result | `problem` or `tpd`, `job`, `build` |

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
| Gear generators | `gear-generators.md` | create_gear types, frames, defaults and their basis, self-checks, assembly placement |
| Topology optimization | `topology-optimization.md` | problem spec in mm, defaults and basis, reading results, turning them into parts |
| API recipes | `solidworks-api.md` | verified SolidWorks API calls (sketches, lofts, sweeps, patterns, configurations, mates, checks, STL import) |

To add a note, put a `.md` file in `knowledge/` with the same layout (`title`, `tags`, `summary` at the top, `## ` sections) and restart Claude. Give a source (standard number, catalogue) for every value.

### Gear generators

`gear_design` (numbers only) and `create_gear` (native SolidWorks features) cover the common gear types. The type list follows the OpenSCAD library [chrisspen/gears](https://github.com/chrisspen/gears) (except herringbone bevels and racks with screw holes; planetary sets are computed with `gear_design` and built part by part), but that library is CC BY-NC-SA 3.0 (non-commercial, share-alike), so none of its code is used: everything is implemented from the standards (ISO 21771, ISO 53, Gleason/AGMA 2005, DIN 3975). Cycloidal and strain-wave drives are left out (buy them as units).

| type | Geometry | Method |
|---|---|---|
| `spur`, `helical`, `herringbone` | external spur, helical, herringbone | involute and trochoidal root generated by the ISO 53 rack, undercut included |
| `internal` | internal (ring) gear | involute with a circular root fillet |
| `rack` | spur or helical rack | ISO 53 basic rack, square ends also for helical racks |
| `bevel`, `spiral_bevel` | straight or spiral bevel | Tredgold section loft with guide curves, Gleason proportions |
| `worm`, `worm_wheel`, `worm_set` | ZA worm, worm wheel | helix sweep; wheel = throated helical approximation |

- Defaults and basis: 20 deg and ISO 53 A [std], backlash 0.04 m [heur], face width 10 m [heur], small pinions get the undercut limit x_min with a V-zero mate [std], ring rim d_f + 6 m [heur]. Results carry the basis tags.
- Self-checks: SolidWorks volume against the exact tooth-section area x face width (normally within 0.1 %), one body, no rebuild errors, helix hand confirmed by probing the material.
- `build_mate: true` builds the mating gear (opposite hand external, same hand internal) and rolls the pair through one pitch with temporary bodies. Measured: spur, helical, herringbone, internal and rack pairs 0 mm³; spiral bevel 0.03-0.09 mm³ (Tredgold approximation); a same-hand helical pair shows 162 mm³, so wrong combinations are caught.
- Frames: axis +Z, z = 0 face on the Front plane, a tooth space centred on +X. Use `phase_deg` from the result to place pairs; details in the knowledge note `gear-generators`.

Example: "module 1.5, 18:36 spur pair, 8 mm bore with keyway" -> `create_gear {"type": "spur", "module": 1.5, "teeth": 18, "mate_teeth": 36, "build_mate": true, "bore": 8, "keyway": true}`

### Topology optimization

`topology_optimize` is a SIMP optimizer ported from [ToPy](https://github.com/williamhunter/topy) (MIT) to Python 3 + scipy: minimum compliance (maximum stiffness) and compliant mechanisms, 2D plates and 3D. Heat conduction and CFD are not included.

- Verification: the element matrices equal ToPy's SymPy definitions to machine precision, and the MBB beam reproduces Sigmund's 99-line code (first iteration to 1e-11, eight iterations to 1e-9).
- Problems are given in mm: `size`, `element_size`, `thickness`, `volume_fraction`, `supports`, `loads`, `keep_out` / `keep_in` (keep material around bolt holes, clear space for moving parts), `material`. ToPy `.tpd` files are accepted as they are.
- Runs as a background job; the call waits up to `wait` s, then poll with `job`. Results include iterations, volume fraction, compliance, load-point displacement (mm), mass and a preview image.
- `build: true`: a 2D result becomes splines along the 0.5-density contour extruded by the thickness (volume error 0.02 %); a 3D result is imported from STL as a mesh solid body (reference for remodelling).
- Speed (measured): 2D 120 x 60 elements about 4 s; 3D 40 x 20 x 10 elements about 0.7 s per iteration.

Example: left edge fixed, 1000 N at the middle of the right end, 40 % volume, 6 mm aluminium bracket ->
`{"problem": {"size": [120, 60], "element_size": 1, "thickness": 6, "volume_fraction": 0.4, "supports": [{"edge": "left"}], "loads": [{"at": [120, 30], "force": [0, -1000]}], "material": {"E": 70000, "density": 2.7}}, "build": true}`

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
4. Run the installer once more while Claude is closed.
5. Read Claude's MCP log: `%APPDATA%\Claude\logs\mcp-server-solidworks.log` (MSIX build: `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\logs\`).

**`pip install -r requirements.txt` fails**: make sure you are using this repository's `requirements.txt` (no `asyncio-compat`, `mcp<2`).

**The server exits immediately and the log shows `'Server' object has no attribute 'list_tools'`**: mcp 2.x got installed. Run `.venv\Scripts\python.exe -m pip install "mcp>=1,<2"`.

**"Member not found" errors**: see the COM rules in [Advanced: execute_python](#advanced-execute_python). The built-in tools in this repository are already fixed.

**It can't connect**: check that SolidWorks is running and that no license or startup dialog is open. Run `get_solidworks_info` to see whether the installation is detected; if not, set `exe_path` in `config.json`.

**You moved the folder**: run `setup_windows.bat` again to update the paths.

### Updating and uninstalling

- Update: run the PowerShell line again, or `git pull` in your copy and run `setup_windows.bat` (installs new packages).
- Uninstall: run `setup_windows.bat -Uninstall` (or `install.ps1 -Uninstall`) in a command prompt; it removes the Claude Desktop and Claude Code registrations and the skill. Then delete the folder. Your pre-install config is in the `claude_desktop_config.json.bak-*` backup. A skill saved in your Claude account is removed in Claude's settings.

### Roadmap

SolidWorks support comes first. Order of work:

- [x] **Text-to-CAD verification loop**: `model_report`, `render_views`, `export_model`, `check_interference`, execute_python helpers
- [x] **Agent guide**: token rules and design-rationale rules (server instructions)
- [x] **Design knowledge base v1**: design policy, gears, bearings, fasteners, fits, shafts and keys, materials, DFM, API recipes
- [ ] **Parts database**: KS/ISO standard part tables plus MISUMI Korea part numbers registered by the user (the MISUMI site's robots.txt and terms forbid automated collection, so it is not crawled)
- [x] **Gear generators**: spur, helical, herringbone, internal, rack, straight and spiral bevel, worm and worm wheel (standard formulas, self-checked volume and mesh)
- [x] **Topology optimization**: 2D/3D stiffness and compliant mechanisms (ToPy port), 2D results as extruded parts
- [ ] **Planetary assembly placement** and help with remodelling 3D optimization results

Thermal and CFD studies are out of scope for now (SOLIDWORKS Flow Simulation results were not trusted enough).

### Project structure

```
Solidworks-MCP/
├── install.ps1                # one-line installer (irm ... | iex): gets the code, finds Python, runs setup_mcp.py
├── setup_windows.bat          # one-click installer (double-click; runs install.ps1)
├── setup_mcp.py               # installer logic: .venv, packages, self-test, Claude Desktop and Claude Code registration, skill
├── skills/solidworks-design/  # Claude skill: design working rules (for clients such as Cowork that do not pass server instructions on)
├── solidworks_mcp_server.py   # MCP server entry point
├── requirements.txt
├── knowledge/                 # design knowledge base (Markdown notes)
├── solidworks_mcp/
│   ├── server.py              # MCP tool definitions and handlers
│   ├── instructions.md        # working rules sent to the agent in every session
│   ├── verification.py        # model_report, render_views, export_model, check_interference
│   ├── knowledge.py           # knowledge base search
│   ├── com.py                 # late-binding COM helpers (val, call, arr, plane, ...)
│   ├── gears/                 # gears: geometry (involute), bevel, build (SolidWorks), api (tool arguments)
│   ├── topopt/                # topology optimization (ToPy port): problem, topology, export, run, cad
│   ├── tests/                 # gear, optimizer and installer unit tests (python -m unittest solidworks_mcp.tests.test_gears ...)
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

The topology optimization code (`solidworks_mcp/topopt/`) is a port of [ToPy](https://github.com/williamhunter/topy) by William Hunter (MIT); the full license is in `solidworks_mcp/topopt/LICENSE_TOPY.md`. ToPy's 2D part is based on Ole Sigmund's 99-line code. The gear generators do not use code from chrisspen/gears (CC BY-NC-SA 3.0).
