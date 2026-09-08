#!/usr/bin/env python3
# =============================================================================
# 이 파일의 책임: 요구사항정의서와 기능명세서가 서로 어긋났는지 자동으로 잡아낸다.
#   (1) 기능명세서의 유효 기능 ID 전부가 요구사항 하나에 붙어 있는지
#   (2) 요구사항정의서가 존재하지 않는 기능 ID 를 참조하고 있지 않은지
#   (3) 추적표에 손으로 적은 "기능 수" 가 실제 개수와 맞는지
#   (4) 요구사항 ID 번호가 중간에 비지 않았는지
# 다른 파일과의 관계: 관리/기능명세서.md 와 관리/요구사항정의서.md 를 읽기만 한다.
#   두 문서를 고친 뒤 이 스크립트를 돌리는 것이 커밋 전 절차다.
# Spring 비교: 문서용 단위테스트다. ArchUnit 이 코드 구조 규칙을 테스트로 굳히듯,
#   이건 문서 사이의 참조 무결성을 테스트로 굳힌다. 실패 시 종료코드 1 을 반환하므로
#   CI 나 pre-commit 훅에 그대로 걸 수 있다.
# =============================================================================

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "관리" / "기능명세서.md"
REQ = ROOT / "관리" / "요구사항정의서.md"

# 폐기된 기능. 요구사항에 붙지 않는 것이 정상이다. 번호는 재사용하지 않는다.
DISCARDED = {"ANL-04", "ANL-13", "AMT-04", "AMT-05", "AMT-10", "VIS-08"}

# 기능명세서 SYS 영역은 화면 기능이 아니라 시스템이 갖춰야 할 성질이라
# SFR 이 아닌 비기능 요구사항으로 옮겼다. 추적표 8.2 절에서 대응을 관리한다.
NONFUNCTIONAL_AREA = "SYS"

REQ_PREFIXES = ["SFR", "SYR", "DAR", "SIR", "PER", "SER", "QUR", "TER", "COR"]

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def expand(cell: str) -> set[str]:
    """`REV-08`~`15` 같은 범위 표기를 개별 ID 로 펼친다."""
    out: set[str] = set()
    pattern = r"`([A-Z]+)-(\d{2})`(?:\s*~\s*`?(?:[A-Z]+-)?(\d{2})`?)?"
    for area, start, end in re.findall(pattern, cell):
        for i in range(int(start), int(end or start) + 1):
            out.add(f"{area}-{i:02d}")
    return out


def table_rows(section: str, first_col: str) -> list[list[str]]:
    """마크다운 표에서 첫 칸이 지정 패턴인 행만 셀 배열로 돌려준다."""
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and re.search(first_col, cells[0]):
            rows.append(cells)
    return rows


def slice_between(text: str, start: str, end: str) -> str:
    if start not in text:
        fail(f"요구사항정의서에 '{start}' 절이 없다")
        return ""
    part = text.split(start, 1)[1]
    return part.split(end, 1)[0] if end in part else part


# --- 읽기 -------------------------------------------------------------------
for path in (SPEC, REQ):
    if not path.exists():
        print(f"[중단] 파일이 없다: {path}")
        sys.exit(1)

spec_text = SPEC.read_text(encoding="utf-8")
req_text = REQ.read_text(encoding="utf-8")

# --- 1. 기능명세서에서 정의된 기능 ID 수집 -----------------------------------
# 표 행의 첫 칸이 `XXX-00` 인 것만 정의로 본다. 본문 인용은 세지 않는다.
defined = {
    m.group(1)
    for line in spec_text.splitlines()
    if (m := re.match(r"\|\s*`([A-Z]+-\d{2})`\s*\|", line))
}
unknown_discarded = DISCARDED - defined
if unknown_discarded:
    fail(f"폐기 목록에 있으나 기능명세서에 정의가 없다: {sorted(unknown_discarded)}")

valid = defined - DISCARDED
sys_ids = {i for i in valid if i.startswith(NONFUNCTIONAL_AREA + "-")}
expected = valid - sys_ids

notes.append(f"기능명세서 정의 {len(defined)}건 = 유효 {len(valid)}건 + 폐기 {len(defined & DISCARDED)}건")

# --- 2. 요구사항 ID 번호 연속성 ---------------------------------------------
req_counts: dict[str, int] = {}
for prefix in REQ_PREFIXES:
    nums = sorted({int(n) for n in re.findall(rf"`{prefix}-(\d{{2}})`", req_text)})
    req_counts[prefix] = len(nums)
    if not nums:
        fail(f"{prefix} 요구사항이 하나도 없다")
        continue
    missing = set(range(1, max(nums) + 1)) - set(nums)
    if missing:
        fail(f"{prefix} 번호가 비어 있다: {sorted(missing)}")

total_req = sum(req_counts.values())
notes.append(
    "요구사항 " + str(total_req) + "건 = "
    + " + ".join(f"{p} {req_counts[p]}" for p in REQ_PREFIXES)
)

# 0절 구분표에 적어둔 건수가 실제와 맞는지
for prefix, label in [("SFR", "기능 요구사항")]:
    m = re.search(rf"\|\s*`{prefix}`\s*\|[^|]*\|\s*(\d+)\s*\|", req_text)
    if m and int(m.group(1)) != req_counts[prefix]:
        fail(f"0절 표의 {prefix} 건수 {m.group(1)} != 실제 {req_counts[prefix]}")

# --- 3. 추적표 8.1 — 기능 요구사항 대응 --------------------------------------
sec81 = slice_between(req_text, "### 8.1", "### 8.2")
mapped: set[str] = set()
seen_sfr: set[str] = set()

for cells in table_rows(sec81, r"`SFR-\d{2}`"):
    sfr = re.search(r"`(SFR-\d{2})`", cells[0]).group(1)
    if sfr in seen_sfr:
        fail(f"추적표에 {sfr} 행이 두 번 있다")
    seen_sfr.add(sfr)

    if len(cells) < 3:
        fail(f"{sfr} 행에 칸이 부족하다")
        continue

    ids = expand(cells[1])
    if not ids:
        fail(f"{sfr} 에 대응 기능 ID 가 없다")
    overlap = ids & mapped
    if overlap:
        fail(f"{sfr} 이 다른 요구사항과 기능을 겹쳐 잡았다: {sorted(overlap)}")

    if cells[2].strip().isdigit() and int(cells[2]) != len(ids):
        fail(f"{sfr} 기능 수 선언 {cells[2]} != 실제 {len(ids)}")

    mapped |= ids

missing_sfr = seen_sfr ^ {f"SFR-{i:02d}" for i in range(1, req_counts['SFR'] + 1)}
if missing_sfr:
    fail(f"추적표 행과 SFR 정의가 어긋난다: {sorted(missing_sfr)}")

untracked = expected - mapped
if untracked:
    fail(f"요구사항에 붙지 않은 기능 {len(untracked)}건: {sorted(untracked)}")

phantom = mapped - expected
if phantom:
    fail(f"존재하지 않는 기능을 참조한다 {len(phantom)}건: {sorted(phantom)}")

# 소계 표기 확인
m = re.search(r"\*\*소계\*\*\s*\|\s*\*\*(\d+)\*\*", sec81)
if not m:
    fail("추적표 8.1 에 소계 행이 없다")
elif int(m.group(1)) != len(mapped):
    fail(f"8.1 소계 표기 {m.group(1)} != 실제 {len(mapped)}")

# --- 4. 추적표 8.2 — SYS 영역 대응 ------------------------------------------
sec82 = slice_between(req_text, "### 8.2", "### 8.3")
sys_mapped = set(re.findall(r"`(SYS-\d{2})`", sec82))
if sys_ids - sys_mapped:
    fail(f"8.2 에 빠진 SYS 기능: {sorted(sys_ids - sys_mapped)}")
if sys_mapped - sys_ids:
    fail(f"8.2 가 없는 SYS 기능을 참조한다: {sorted(sys_mapped - sys_ids)}")

# 8.2 가 참조하는 비기능 요구사항 ID 가 실제로 정의돼 있는지
for rid in set(re.findall(r"`((?:SYR|DAR|SIR|PER|SER|QUR|TER|COR)-\d{2})`", sec82)):
    prefix, num = rid.split("-")
    if int(num) > req_counts.get(prefix, 0):
        fail(f"8.2 가 정의되지 않은 요구사항 {rid} 를 참조한다")

# --- 5. 추적표 8.3 — 폐기 기능 ----------------------------------------------
sec83 = req_text.split("### 8.3", 1)[1].split("\n## ", 1)[0] if "### 8.3" in req_text else ""
listed_discarded = set(re.findall(r"`([A-Z]+-\d{2})`", sec83))
if DISCARDED - listed_discarded:
    fail(f"8.3 에 빠진 폐기 기능: {sorted(DISCARDED - listed_discarded)}")

# --- 6. 총합 ----------------------------------------------------------------
total = len(mapped) + len(sys_mapped)
if total != len(valid):
    fail(f"추적 합계 {len(mapped)} + {len(sys_mapped)} = {total} != 유효 기능 {len(valid)}")
else:
    notes.append(f"추적 합계 {len(mapped)} + {len(sys_mapped)} = {total} (유효 기능 수와 일치)")

# --- 7. 검증 방법 빈칸 (TER-01) ---------------------------------------------
blank = 0
for section in ["## 3.", "### 4."]:
    pass
for cells in table_rows(req_text, r"`(?:SFR|SYR|DAR|SIR|PER|SER|QUR|TER)-\d{2}`"):
    if len(cells) >= 2 and not cells[-1].strip("- "):
        blank += 1
if blank:
    fail(f"검증 방법이 빈 요구사항 {blank}건 (TER-01 위반)")

# --- 출력 -------------------------------------------------------------------
print("=" * 70)
print("요구사항 추적 검증")
print("=" * 70)
for n in notes:
    print(f"  {n}")
print("-" * 70)
if failures:
    print(f"실패 {len(failures)}건")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("통과 — 두 문서가 어긋난 곳이 없다")
sys.exit(0)
