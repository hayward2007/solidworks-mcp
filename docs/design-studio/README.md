# Design Studio 사용 가이드

SolidWorks MCP에 **조사 → 증거 → 역설계 → 대안 비교 → 사용자 검토 → 개선** 흐름을
추가한 로컬 시스템입니다. 품질 우선 모드가 기본입니다. 모델 API나 임베딩 서비스를
자동 호출하지 않으며, 기존 Claude/Codex가 설계 추론을 수행합니다.

## 설치와 실행

macOS/Linux에서는 증거·지식 검색·계산·검토를 사용할 수 있습니다.
SolidWorks 연결과 네이티브 형상 추출·수정은 SolidWorks가 설치된 Windows에서 합니다.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
sw-design doctor --mcp
sw-design demo --output ./sensor-front-example
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[cad]"
.venv\Scripts\sw-design.exe doctor --mcp
.venv\Scripts\sw-design.exe demo --output .\sensor-front-example
```

가상환경 활성화 없이 `python -m solidworks_mcp`로도 같은 CLI를 실행합니다.
데이터는 기본 `~/.solidworks-design`에 저장합니다. 프로젝트별 작업 공간을 원하면
모든 명령 앞에 `--home /절대/경로/workspace`를 넣거나 `SW_DESIGN_HOME`을 지정하세요.
로컬 DB와 CAD·대화 증거는 Git에 넣지 마세요. 저장소 안에서는 `.design-studio/`가 무시됩니다.

## Claude·Codex 연결

먼저 생성할 설정을 확인할 수 있습니다. `--apply`는 설치된 클라이언트 CLI로 등록하며,
이미 같은 이름의 서버가 있으면 덮어쓰지 않고 중단합니다. 새 클라이언트 세션에서 도구를 읽습니다.

```sh
sw-design connect --client codex
sw-design connect --client codex --apply
sw-design connect --client claude-code --apply
sw-design connect --client claude-desktop
```

Codex 등록은 해당 호스트의 Codex MCP 설정에, Claude Code는 현재 작업 폴더의 local
범위에 적용합니다. Claude Desktop은 출력된 `mcpServers` 항목을 기존 설정에 합친 뒤
앱을 완전히 종료하고 다시 실행하세요. 다른 서버와 설정을 보존해야 합니다.
공식 Codex 형식은 [OpenAI MCP 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)와
설치된 `codex mcp add --help`로 확인했습니다.

Windows의 기존 `solidworks` 서버에는 17개의 `design_*` 도구가 함께 노출됩니다.
독립 서버는 CAD 연결을 제외한 16개 도구를 제공합니다. 네이티브 서버를 새로 등록하려면
Windows에서 `sw-design connect --client codex --cad --apply`를 사용합니다.

등록 후 준비된 프로젝트를 같은 CLI에서 열 수 있습니다:

```sh
sw-design start sensor-front-demo --agent codex
sw-design start sensor-front-demo --agent claude-code
sw-design serve
# Windows 전용: 기존 CAD 서버
sw-design serve --cad
```

`start`는 설치된 에이전트를 대화형으로 실행합니다. 사용자 계정의 기존 인증·모델 설정을
사용하며, 이 저장소가 별도 모델/API 키를 선택하거나 공급하지 않습니다.

## 실제 프로젝트 조사

1. `sw-design schema`로 설계안 계약을 확인합니다. `demo`가 생성한 `brief.json`,
   `proposal-r1.json`, `proposal-r2.json`은 모든 필드를 채운 예제입니다.
   실제 모델에 사용하려면 예제 가정·증거 ID·치수를 실제 데이터로 교체합니다.
2. 정량 요구사항을 넣은 brief로 프로젝트를 만듭니다. 요구사항 필드는
   `id, metric, unit, operator(le/ge/eq), limit, tolerance, critical, rationale`입니다.
   기존 brief의 수치·단위·기준을 낮추는 설계안은 차단합니다. 요구사항 변경은 별도 프로젝트
   brief로 검토하고 이전 프로젝트를 근거로 연결하세요.
   변경 금지 치수는 선택 필드 `protected_parameters`에
   `{"mount_spacing": {"value": 60, "unit": "mm"}}`처럼 고정할 수 있습니다.
   이 검사는 선언된 파라미터를 비교하며 실제 CAD가 일치하는지는 별도 측정해야 합니다.
3. `init`이 반환한 brief artifact/evidence ID를 설계안 요구사항에 연결합니다.
4. 원본 CAD, 도면, 공급사 자료, 이미지, 대화 발췌, 측정·시험 결과를 따로 가져옵니다.
   대화에서 다른 사람이 주장한 계산은 `reported`로 기록합니다.
5. Windows의 열린 원본을 수정하지 않고 `capture`합니다. STL은 단위를 직접 지정합니다.
   STEP/SLDPRT/SLDASM은 보존만 하며, Windows에서 열어 native capture 해야 실제 형상을 읽습니다.

```sh
sw-design init walker-front --brief brief.json
sw-design import walker-front /absolute/path/baseline.SLDASM
sw-design import walker-front /absolute/path/front-view.png
sw-design evidence walker-front measured-interface.json
sw-design inspect-stl walker-front /absolute/path/model.stl --unit mm
# Windows SolidWorks가 이미 실행 중이고, 의도한 문서가 활성 상태일 때:
sw-design capture walker-front
sw-design kb context "역경사 전면 카메라 시야 공차 정비 외형"
```

증거 JSON 예시 (파일 ID는 실제 `import` 결과로 교체):

```json
{
  "kind": "measured",
  "statement": "Datum A/B 기준 센서 장착 간격 실측",
  "artifact_ids": ["a_ACTUAL_IMPORT_ID"],
  "locator": "원본 측정 JSON; active configuration Default; mm; selection Mount1/Mount2; uncertainty +/-0.02 mm",
  "data": {"metrics": {"mount_spacing": {"value": 60.0, "unit": "mm", "uncertainty": 0.02}}}
}
```

위 수치는 형식 설명용 예시입니다. 실제 측정값으로 사용하지 마세요.

## 설계안과 iteration

설계안은 단순한 프롬프트가 아니라 버전별 명세입니다. 값·단위·근거·이유가 있는 치수,
좌표계, 보호 인터페이스, 형상 구성법, 요구사항, 계산, 검사, 최소 3개 대안, 외형 기준,
공차·제조·조립·정비와 위험을 포함합니다. 스키마에서 필수 구조를 검사하고, 내용과
원본 증거의 타당성은 사람이 검토합니다. 설명란을 채웠다는 이유로 좋은 디자인으로 판정하지 않습니다.

계산 입력은 **설계안 파라미터 ID**를 참조합니다. 계산기 출력 단위와 요구 단위가 다르면
실패합니다. 측정 검사는 증거의 `data.metrics.<metric>.value/unit`을 읽습니다. PASS를
직접 입력할 수 없습니다. 등호 조건만 `tolerance`를 사용하며 안전 한계 le/ge를 느슨하게 만들지 않습니다.
측정 검사는 같은 단위의 비음수 `uncertainty`가 필수이며 최악 조건으로 여유를 줄입니다.
불확도가 없는 메쉬/CAD 요약값은 관측으로 보존하지만 기능 치수 검사를 자동 통과시키지 않습니다.
계산식·검사 코드 또는 필수 정책의 해시가 바뀌어도 이전 검토 fingerprint는 무효가 됩니다.

```sh
sw-design submit walker-front proposal.json
sw-design export walker-front r_ACTUAL_REVISION --output ./review-r1
sw-design diff walker-front r_PREVIOUS r_CURRENT
sw-design submit walker-front proposal-r2.json --parent r_CURRENT
```

검토 HTML은 외형 이미지, 치수 근거표, 계산식/가정/출력, 실제 PASS/FAIL/여유,
대안·제조·위험·증거 원장을 보여줍니다. 원본 첨부와 파일별 SHA-256 manifest도 제공합니다.
출력 디렉터리를 덮어쓰지 않습니다. export는 시점별 스냅샷이며 이후 승인 상태를 실시간 표시하지 않습니다.

**사용자가 검토한 후에만** 다음 명령으로 검토 내용을 기록합니다. 에이전트는 사용자 대신
실행하면 안 됩니다. 다음 명령은 자동으로 실행할 작업 목록이 아닙니다.

```sh
sw-design review walker-front r_CURRENT --decision approve --reviewer "검토자" --note "수치·외형·수용한 가정과 수정 범위"
sw-design handoff walker-front r_CURRENT
```

`request_changes`/`reject`는 handoff를 차단합니다. 새 revision, 변경된 저장 증거,
다른 fingerprint, 이전 revision의 승인으로는 진행할 수 없습니다. CLI 검토자명은 입력자의
선언을 기록하는 방식이며 신원 인증·전자서명이 아닙니다. 임의 shell/CAD 권한을 가진
에이전트를 보안적으로 격리하는 장치도 아닙니다.

## DB와 RAG

SQLite 테이블에 프로젝트 brief, content-addressed 파일, 증거, revision, 검토,
Markdown 섹션과 FTS5 검색 색인을 저장합니다. BM25와 한국어 키워드 확장을 사용하며
벡터 임베딩은 현재 사용하지 않습니다. 품질을 비교하기 전부터 유료 임베딩을 추가하지 않았습니다.

실제 사용자 검토를 거친 revision은 `sw-design learn 프로젝트 revision` 또는
`design_learn`으로 지식화할 수 있습니다. 치수·근거·형상·대안·외형·제조·위험을
`reviewed_case`로 저장하고 색인합니다. 예제·가정은 그대로 남으며 표준으로 승격하지 않습니다.
검토가 철회되거나 원본/계산/정책이 바뀌면 해당 사례는 활성 검색에서 제외합니다.

```sh
sw-design kb index
sw-design kb index --root /absolute/path/my-licensed-design-notes
sw-design kb search "카메라 시야 역경사" --limit 8
sw-design kb get k_ACTUAL_REFERENCE
sw-design kb context "센서 정비와 외형" --mode quality
# 선택 사항. 필수 정책은 축약하지 않으며, 생략된 원문은 다시 조회해야 합니다.
sw-design kb context "센서 정비와 외형" --mode compact
```

파일이 변경되면 재색인합니다. 이전 참조는 오류를 내고, 삭제된 노트는 재색인 후 검색에서
제거됩니다. 출처는 경로·줄 범위·전체 파일 해시·조회일·authority·적용 범위를 반환합니다.
authority는 메타데이터 선언이며 자동 검증된 인증이 아닙니다. 표준 원문·카탈로그의
적법하게 접근 가능한 부분을 사용자가 확보한 뒤 등록할 수 있습니다. 저작권이 있는 표준
전체나 수집이 금지된 공급사 DB를 자동 다운로드하지 않습니다.

주요 가이드:

- [품질 정책](../../knowledge/product-design-policy.md), [증거 계약](../../knowledge/design-evidence.md), [검토 게이트](../../knowledge/design-review.md)
- [역설계 절차](../../knowledge/reverse-engineering.md), [외형 정량화](../../knowledge/industrial-design.md)
- [카메라·역경사](../../knowledge/sensor-enclosure.md), [공차·제조·정비](../../knowledge/manufacturing-detail.md)
- [표준·원문 적용 범위](../../knowledge/standards-registry.md)
- [계산과 대안 비교를 채운 설계 예제](../../knowledge/design-examples.md)

## 검증과 현재 한계

```sh
python -m unittest solidworks_mcp.tests.test_design_studio solidworks_mcp.tests.test_setup solidworks_mcp.tests.test_gears solidworks_mcp.tests.test_topopt
sw-design doctor --mcp
python scripts/evaluate_design_retrieval.py
```

계산기는 직사각형 외팔보, 대칭 양방향 공차 누적, 핀홀 지면 단면, 역경사 패널 투영을
지원합니다. FEA·피로·광학 성능·전체 동작 레이캐스트를 대신하지 않습니다. 네이티브
capture의 면/원통/피처/치수는 관측이고 기능·공차·설계 의도는 별도로 확인해야 합니다.
렌더만 보고 제조 가능, 해석 통과, 사용자 승인 또는 제품 수준 완성을 선언하지 않습니다.

이번 개발 호스트는 macOS입니다. Windows COM은 API 문서/대체 객체 시험 범위로
확인하며, 실제 SolidWorks에서의 native capture/CAD 변경은 별도 현장 검증이 필요합니다.
