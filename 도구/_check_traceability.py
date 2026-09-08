#!/usr/bin/env python3
# =============================================================================
# 이 파일의 책임: 요구사항정의서와 최신 v5 기능명세서의 추적 관계를 검증한다.
#   (1) 요구사항 ID 수·연속성·검증 방법, (2) 최신 3단 기능 ID의 추적 누락,
#   (3) 확정 범위에서 제외한 구현의 기록, (4) 핵심 범위 결정 문구를 확인한다.
# 다른 파일과의 관계: 관리/요구사항정의서.md와 관리/기능명세서.md를 읽기만 한다.
# Spring 비교: ArchUnit처럼 문서 구조와 참조 무결성을 자동 검사하는 문서 단위테스트다.
# =============================================================================

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "관리" / "기능명세서.md"
REQ = ROOT / "관리" / "요구사항정의서.md"

REQ_PREFIXES = ["SFR", "SYR", "DAR", "SIR", "PER", "SER", "QUR", "TER", "COR"]
OUT_OF_SCOPE_IMPLEMENTATIONS = {"TSK-002-1", "TSK-002-2", "AMT-004-3"}
FEATURE_ID = r"[A-Z]+-\d{3}(?:-\d+)?"
failures: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def section(text: str, start: str, end: Optional[str] = None) -> str:
    if start not in text:
        fail(f"'{start}' 절이 없다")
        return ""
    result = text.split(start, 1)[1]
    return result.split(end, 1)[0] if end and end in result else result


for path in (SPEC, REQ):
    if not path.exists():
        print(f"[중단] 파일이 없다: {path}")
        sys.exit(1)

spec_text = SPEC.read_text(encoding="utf-8")
req_text = REQ.read_text(encoding="utf-8")

# 기능명세 표의 첫 칸만 정의로 센다. 본문·부록의 ID 인용은 제외한다.
defined = {
    match.group(1)
    for line in spec_text.splitlines()
    if (match := re.match(rf"\|\s*`({FEATURE_ID})`\s*\|", line))
}
if len(defined) != 97:
    fail(f"최신 기능명세 정의 수 {len(defined)} != 97")
if OUT_OF_SCOPE_IMPLEMENTATIONS - defined:
    fail(f"범위 제외 구현이 기능명세 활성 표에 없다: {sorted(OUT_OF_SCOPE_IMPLEMENTATIONS - defined)}")

scope_features = defined - OUT_OF_SCOPE_IMPLEMENTATIONS
notes.append(
    f"기능명세 {len(defined)}건 = 요구사항 범위 {len(scope_features)}건"
    f" + 최신 결정 제외 {len(OUT_OF_SCOPE_IMPLEMENTATIONS)}건"
)

# 요구사항 정의 행은 추적표 앞의 본문 표에서만 수집한다.
definition_text = req_text.split("## 8. 요구사항 추적표", 1)[0]
row_ids = re.findall(r"^\|\s*`((?:SFR|SYR|DAR|SIR|PER|SER|QUR|TER|COR)-\d{2})`\s*\|", definition_text, re.M)
counts = Counter(item.split("-")[0] for item in row_ids)
duplicates = sorted(item for item, count in Counter(row_ids).items() if count != 1)
if duplicates:
    fail(f"요구사항 정의 행이 중복됐다: {duplicates}")

for prefix in REQ_PREFIXES:
    numbers = sorted(int(item.split("-")[1]) for item in row_ids if item.startswith(prefix + "-"))
    if not numbers:
        fail(f"{prefix} 요구사항이 없다")
        continue
    missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    if missing:
        fail(f"{prefix} 번호가 비어 있다: {missing}")
    declared = re.search(rf"\|\s*`{prefix}`\s*\|[^|]*\|\s*(\d+)\s*\|", req_text)
    if not declared or int(declared.group(1)) != len(numbers):
        fail(f"0절 {prefix} 건수와 실제 정의 행 수가 다르다")

if len(row_ids) != 92 or counts["SFR"] != 48:
    fail(f"요구사항 수가 예상과 다르다: 전체 {len(row_ids)}, SFR {counts['SFR']}")
notes.append(
    "요구사항 92건 = " + " + ".join(f"{prefix} {counts[prefix]}" for prefix in REQ_PREFIXES)
)

# 검증 방법은 제약사항(COR)을 제외한 모든 요구사항 행의 마지막 칸에 있어야 한다.
blank_verification: list[str] = []
for line in definition_text.splitlines():
    match = re.match(r"^\|\s*`((?:SFR|SYR|DAR|SIR|PER|SER|QUR|TER)-\d{2})`\s*\|", line)
    if not match:
        continue
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if not cells[-1].strip("- "):
        blank_verification.append(match.group(1))
if blank_verification:
    fail(f"검증 방법이 빈 요구사항: {blank_verification}")

# 최신 추적표의 3단 ID가 요구사항 범위 기능 94건을 빠짐없이 덮는지 확인한다.
trace = section(req_text, "### 8.1", "### 8.3")
trace_ids = set(re.findall(rf"`({FEATURE_ID})`", trace))
mapped_scope = trace_ids - OUT_OF_SCOPE_IMPLEMENTATIONS
if scope_features - mapped_scope:
    fail(f"요구사항 추적표에 빠진 기능: {sorted(scope_features - mapped_scope)}")
if mapped_scope - scope_features:
    fail(f"요구사항 추적표가 없는 기능을 참조한다: {sorted(mapped_scope - scope_features)}")
notes.append(f"추적표 고유 기능 {len(mapped_scope)}건 (요구사항 범위와 일치)")

excluded = section(req_text, "### 8.3", "## 9.")
if OUT_OF_SCOPE_IMPLEMENTATIONS - set(re.findall(rf"`({FEATURE_ID})`", excluded)):
    fail("8.3절에 최신 결정으로 제외한 구현이 모두 남아 있지 않다")

# 사용자가 이번 보완에서 확정한 핵심 경계를 내용으로도 확인한다.
required_phrases = {
    "액션아이템과 AI 태스크 제안 분리": "액션아이템 추출(`SFR-20`)은 분석 기능으로 유지",
    "AI 태스크 제안 제외": "AI 태스크 제안과 검토",
    "인수인계 문서 제외": "인수인계 문서 자동 생성은 범위에서 제외",
    "산출물 네 종류": "주간 보고서 · 프로젝트 현황 · 결정사항 로그(대장) · 회의 안건",
    "금액 유효 스냅샷": "직전 검토 완료 분석을 유효 스냅샷으로 유지",
    "VIEWER 금액 제한": "`VIEWER`는 화면 메뉴와 서버 요청 모두 차단",
}
for label, phrase in required_phrases.items():
    if phrase not in req_text:
        fail(f"핵심 결정 문구 누락: {label}")

print("=" * 70)
print("요구사항 추적 검증")
print("=" * 70)
for note in notes:
    print(f"  {note}")
print("-" * 70)
if failures:
    print(f"실패 {len(failures)}건")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)
print("통과 — 요구사항 ID·최신 기능 추적·제외 범위가 일치한다")
