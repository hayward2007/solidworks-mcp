# Design Studio v0.1 검증 보고

검증일: 2026-10-21 (Asia/Seoul). 개발 호스트: macOS arm64, Python 3.12.13,
SQLite 3.51.0, MCP Python SDK 1.30.0.

## 구현과 실제 확인

- CLI `sw-design` 및 `python -m solidworks_mcp` 설치·실행.
- 독립 MCP 프로세스 initialize / tools/list / tools/call: **16개 도구** 확인.
  잘못된 요청 후에도 같은 MCP 세션에서 정상 호출 가능.
- 기존 native 서버는 대체 COM 객체를 사용한 계약 시험에서 **기존 34개 + 새 17개 = 51개**
  도구 및 design 계산 dispatch 확인. 이는 실제 Windows COM 시험이 아님.
- 현재 호스트의 Codex에 `solidworks-design` stdio 서버 전역 등록.
  Claude Code는 이 저장소 local 범위에 등록 후 **Connected** 상태 확인.
  새 에이전트 세션에서 도구를 불러와야 함.
- 지식 **21개 노트 / 110개 섹션** SQLite FTS5 색인. 한국어 확장·BM25 검색.
  직접 작성한 9개 문서 라우팅 질의는 모두 top 8 안에 기대 문서가 있었음.
  작은 관련성 smoke set이며 의미 검색/생성 품질 또는 토큰 절감의 벤치마크가 아님.
- 휠 빌드 후 저장소 밖 임시 폴더에 풀어 실행. bundled knowledge 21개/110섹션,
  MCP 16개와 실패→통과 예제 실행을 확인. 개발 checkout으로 우회하지 않는 import 경로 확인.
- `pip check`: 의존성 충돌 없음. `git diff --check`: 공백 오류 없음.

## 테스트

```text
python -m unittest \
  solidworks_mcp.tests.test_design_studio \
  solidworks_mcp.tests.test_setup \
  solidworks_mcp.tests.test_gears \
  solidworks_mcp.tests.test_topopt -q

Ran 61 tests
OK
```

주요 검증: 독립적인 수치 기대값, 잘못된 단위/비유한 수치, 공차·불확도의 최악조건,
한영 검색, 수정·삭제된 지식의 갱신, 원본 보존/해시 손상, 프로젝트 격리, 요구사항 완화
및 보호 치수 변경 차단, 실패 게이트, 이전 revision 승인·승인 철회·계산 가정 변경,
검토 전 handoff/학습 차단, 승인 사례 지식화 후 철회 시 RAG 제외, CLI 오류와 원자적
프로젝트 초기화, HTML escape/CSP/첨부 manifest, native 추출 API 계약.

## 구체적인 예제 결과

가정: 20 N 끝단 하중, 60 x 25 mm 직사각형 이상 외팔보,
E=69000 MPa, 항복=240 MPa, 밀도=2700 kg/m3. 실제 로봇 치수/재료/하중의 실측이 아님.

| 지표 | 3 mm baseline | 4 mm 제안 | 예제 기준 |
|---|---:|---:|---:|
| 끝단 처짐 | 0.371014 mm | 0.156522 mm | <=0.3 mm |
| 굽힘 응력 | 32 MPa | 18 MPa | <=60 MPa |
| 보 단품 질량 | 12.15 g | 16.20 g | 비교 지표 |
| 항복 안전율 | 7.5 | 13.3333 | >=2.5 |

3 mm revision의 실제 자동 게이트 실패와 4 mm revision의 통과를 보존했습니다.
추가 revision에서는 같은 계산 파라미터를 유지하며 도해의 치수/라벨 배치를 개선했습니다.
HTML 보고서를 브라우저에서 열어 이미지·표·검토 상태 표시를 확인했습니다.
원본 파일, proposal, evaluation, 전체 정밀도 수치, SHA-256 manifest를 함께 보존합니다.
**사용자 검토 기록은 생성하지 않았습니다.**

## Windows 실기 검증 (2026-10-23)

환경: Windows, SOLIDWORKS 2025 (한국어 UI), Python 3.14.7 (기본 인코딩 cp949), MCP Python SDK 1.30.0, SQLite 3.50.4.

- Windows native 서버를 새 프로세스(stdio)로 실행해 initialize / tools/list에서 **51개 도구**와 새 instructions를 확인.
  `design_calculate`(외팔보 결과가 손계산과 일치), `design_context`(quality), `design_schema`, 한국어 `knowledge_search` 호출 확인.
- 실제 COM으로 `design_capture` 확인. 임시 파트(60 x 40 x 10 mm, 지름 10 mm 관통 구멍)에서 피처 19개, D1 = 0.010 m,
  면 7개(평면 6, 원통 r = 5 mm), 면적 합 = 보고 면적, 부피 23,214.6 mm3(해석값과 일치), extraction issue 없음.
  새 서버 프로세스에서 `design_project` 다음 `design_capture`로 AISI 1020 블록의 질량 0.1896 kg, 밀도 7900 kg/m3를 기록.
- 이 검증에서 고친 문제:
  - `model_report` 질량·밀도: `IMassProperty`에서 Volume이나 SurfaceArea를 먼저 읽으면 Mass와 Density가
    밀도 1 kg/m3 기준으로 나옴(AISI 1020 블록 0.1896 kg이 0.00002 kg으로 보고됨). Mass와 Density를 먼저 읽도록 고침
    (`verification.mass_properties`). `model_report`, `execute_python`의 `report()`, `design_capture` metrics가 모두 이 값을 씀.
  - `design_capture`를 SolidWorks 연결 전에 부르면 열린 문서가 있어도 "no active SolidWorks document"로 실패하던 문제:
    다른 native 도구처럼 먼저 연결함.
  - 테스트 1개가 UTF-8 HTML 보고서를 기본 인코딩으로 읽어 한글 Windows(cp949)에서 실패: `encoding="utf-8"` 지정.
- 단위 테스트 62개 OK (Windows 전용 `test_verification` 포함; 설치 테스트 1개는 Windows에서 의도적으로 건너뜀).

### capture 지표 불확도 (2026-10-23)

- `design_capture` 지표마다 `uncertainty`(같은 단위)와 `uncertainty_basis`를 기록하도록 고침. 이전에는 불확도가 없어
  체크에 바로 쓸 수 없었고, 같은 값을 불확도와 함께 evidence로 다시 기록해야 했음.
- 외곽 치수는 `IBody2.GetExtremePoint`로 구한 꽉 맞는 값(부품 좌표 → 어셈블리 좌표 변환). 차동기어 어셈블리에서
  `GetBox`는 184.096 × 81.42 × 118.124 mm, 꽉 맞는 값은 183.886 × 81.42 × 117.695 mm. 크로스핀 지름 7.9955는
  7.995 ± 0.00052로 나옴(`GetPartBox`는 7.996).
- 질량특성 수치 하한을 실측으로 정함. 와셔 두 개(평면·원통, 직선·원 모서리)는 닫힌식과 5e-16 이내로 일치.
  지름 8 핀에 지름 3 교차 구멍(교차 모서리)은 체적 -4.8e-6, 면적 -7.8e-6 / -1.8e-5로 어긋남.
  그래서 직선·원·타원 모서리만 있는 해석 형상은 1e-8 × 값, 그 외는 1e-4 × 값 + 보고 자리수 절반.
- 개수 지표(rebuild_errors, solid_bodies, components, mates)는 정확값(불확도 0). 어셈블리에서 경량화·미해결
  부품이 있으면 capture가 incomplete로 표시되고, 근사 박스는 `uncertainty: null`이라 체크에 쓸 수 없음.
- 테스트 38개(design studio + verification) OK. execute_python에서 테스트를 돌릴 때는 `stdin=subprocess.DEVNULL`로
  띄워야 함: MCP 서버의 stdio 파이프를 물려받으면 CLI 테스트가 멈춤.

## 아직 검증하지 않은 범위

- 사용자 원본 부품·어셈블리의 native capture(어셈블리 components 추출 포함), 형상 수정, 어셈블리 검증.
  임시 파트 capture는 위의 Windows 실기 검증 참조.
- 원본 Walker 전체 CAD, 회사 원본 문서와 계산 코드의 재검증.
- 실제 제품의 구조·진동·피로·열·전장·센서 성능, 제조/조립/정비성, 사용자 외형 승인.
- 실제 Claude/Codex 모델이 제품 설계 한 건을 끝까지 수행하는 생성 품질 및 토큰/비용 비교.
- 일반 벡터 임베딩 검색. 현재 구현은 출처를 가진 lexical RAG임.

이 결과는 로컬 설계 시스템의 작동과 데이터/검토 규칙을 검증한 것입니다.
특정 설계가 제품 수준으로 검증·승인되었다는 의미가 아닙니다.
