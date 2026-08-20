"""기능명세서 xlsx(원본)와 관리/기능명세서.md(설계 근거판)가 어긋났는지 검사한다.

이 파일의 책임
    기능 정의가 두 곳에 있다 — 구글 스프레드시트에서 내려받은 `.xlsx` 가 원본이고
    `관리/기능명세서.md` 는 거기에 설계 근거를 얹은 것이다. **원본이 바뀌면 md 가
    조용히 낡는다.** 그 어긋남을 사람이 눈으로 찾지 않게 한다.

    검사하는 것 넷 —
      ① 기능 수
      ② xlsx 에만 있는 ID (= md 에 아직 안 옮긴 신규 기능)
      ③ md 에만 있는 ID (= xlsx 에서 지웠는데 md 에 남은 것)
      ④ 양쪽 다 있는 ID 의 상태·우선순위·담당 불일치

    **어느 쪽이 맞는지는 이 도구가 판단하지 않는다.** xlsx 가 원본이지만 사람이
    손으로 갱신하므로 머지된 PR 을 못 따라간다. 2026-08-20 첫 실행에서 `DSH-001`·
    `SRH-002-3` 두 건이 걸렸고, 코드를 확인해 보니 **xlsx 쪽이 낡은 것**이었다
    (8/19 에 PR #32·#34·#36 이 머지됐고 xlsx 는 8/18 기준이다).
    어긋남을 찾는 것이 이 도구의 일이고, 판정은 코드가 한다.

다른 파일과의 관계
    입력  산출물/기능명세서_v5_세분화.xlsx   ← 구글시트에서 내려받아 덮어쓴다
          관리/기능명세서.md                 ← 설계 근거가 들어 있는 쪽
    의존  도구/xlsx_read.py (같은 폴더)      ← xlsx 파싱을 재사용한다
    이 도구는 **읽기만 한다.** md 를 고치지 않는다 — 설계 근거를 기계가 덮어쓰면
    사람이 쓴 맥락이 날아간다. 무엇을 고쳐야 하는지만 알려 준다.

Spring 비교
    Flyway 의 `validate` 자리다. 스키마를 고치는 `migrate` 가 아니라, 적용된 것과
    적어 둔 것이 어긋났는지만 보고 실패시킨다. 그래서 종료 코드를 쓴다 —
    어긋나면 `1`, 같으면 `0`.

사용법
    python spec_sync.py
    python spec_sync.py --xlsx <경로> --md <경로>
    python spec_sync.py --quiet        # 어긋난 것만
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xlsx_read import read_sheet  # noqa: E402  같은 폴더의 도구를 재사용한다

ID_RE = re.compile(r"[A-Z]{3,4}-\d{3}(?:-\d)?")
HERE = Path(__file__).resolve().parent.parent          # 레포 루트
DEFAULT_MD = HERE / "관리" / "기능명세서.md"

# .xlsm(매크로 포함)도 그대로 읽힌다 — 컨테이너가 같은 OOXML 이고, 다른 것은
# vbaProject.bin 과 [Content_Types].xml 뿐이라 시트 XML 구조가 동일하다.
# 2026-08-20 에 실제 .xlsm 을 만들어 검증했다. 추출 결과가 바이트까지 같았다.
SPEC_CANDIDATES = (
    HERE / "산출물" / "기능명세서_v5_세분화.xlsx",
    HERE / "산출물" / "기능명세서_v5_세분화.xlsm",
    HERE / "산출물" / "기능명세서.xlsx",
    HERE / "산출물" / "기능명세서.xlsm",
)


def find_spec() -> Path:
    """확장자를 가리지 않고 먼저 있는 것을 쓴다."""
    for p in SPEC_CANDIDATES:
        if p.exists():
            return p
    raise SystemExit(
        "기능명세서 파일을 못 찾았다. 찾아본 곳:\n  "
        + "\n  ".join(str(p.relative_to(HERE)) for p in SPEC_CANDIDATES)
        + "\n--xlsx 로 직접 지정할 수 있다."
    )

# md 의 상태 칸에 쓰이는 표기를 xlsx 표기로 맞춘다. **굵게** 가 섞여 있다.
STATUS = ("구현됨", "부분 구현", "미구현", "검토중", "미결")
OWNERS = ("최재정, 김보현", "박세현, 김보현", "최재정", "김보현", "박세현")


def from_xlsx(path: Path) -> dict[str, dict[str, str]]:
    """{ID: {상태·우선순위·담당·기능명}}. 머리 행을 '기능 ID' 로 찾는다."""
    _, rows = read_sheet(path, 1)
    head_at = next(
        (i for i, r in enumerate(rows) if r and r[0].strip() == "기능 ID"), None
    )
    if head_at is None:
        raise SystemExit(f"'기능 ID' 머리 행을 못 찾았다: {path}")
    col = {h.strip(): i for i, h in enumerate(rows[head_at]) if h.strip()}
    need = ("기능 ID", "기능명", "상태", "우선순위", "담당")
    missing = [k for k in need if k not in col]
    if missing:
        raise SystemExit(f"열이 없다: {missing}")

    out: dict[str, dict[str, str]] = {}
    for r in rows[head_at + 1:]:
        if not any(c.strip() for c in r):
            continue
        fid = r[col["기능 ID"]].strip()
        if not ID_RE.fullmatch(fid):
            continue
        out[fid] = {k: r[col[k]].strip() for k in need[1:]}
    return out


def from_md(path: Path) -> dict[str, dict[str, str]]:
    """md 표에서 ID 와 `구현됨 · P1 · 김보현` 꼴의 칸을 읽는다.

    ID 매핑표(옛 ID -> v5 ID)의 행은 상태 칸이 없어 자연히 걸러진다.
    """
    out: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = ID_RE.fullmatch(cells[0].strip("` *"))
        if not m:
            continue
        fid = cells[0].strip("` *")
        for c in cells[1:]:
            flat = c.replace("*", "").replace("`", "")
            parts = [p.strip() for p in flat.split("·")]
            st = next((p for p in parts if p in STATUS), None)
            pr = next((p for p in parts if re.fullmatch(r"P[0-3]", p)), None)
            if st and pr:
                ow = next((o for o in OWNERS if o in flat), "")
                out[fid] = {"상태": st, "우선순위": pr, "담당": ow}
                break
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="기능명세서 xlsx·xlsm 과 md 의 어긋남 검사")
    p.add_argument("--xlsx", type=Path, help="생략하면 산출물/ 에서 자동으로 찾는다")
    p.add_argument("--md", type=Path, default=DEFAULT_MD)
    p.add_argument("--quiet", action="store_true", help="어긋난 것만 찍는다")
    a = p.parse_args()

    if a.xlsx is None:
        a.xlsx = find_spec()
        print(f"원본: {a.xlsx.relative_to(HERE)}\n")

    for f in (a.xlsx, a.md):
        if not f.exists():
            raise SystemExit(f"파일이 없다: {f}")

    x, m = from_xlsx(a.xlsx), from_md(a.md)
    only_x = sorted(set(x) - set(m))
    only_m = sorted(set(m) - set(x))
    diff = []
    for fid in sorted(set(x) & set(m)):
        for k in ("상태", "우선순위"):
            if x[fid][k] != m[fid][k]:
                diff.append((fid, k, x[fid][k], m[fid][k]))
        if m[fid]["담당"] and x[fid]["담당"] != m[fid]["담당"]:
            diff.append((fid, "담당", x[fid]["담당"], m[fid]["담당"]))

    if not a.quiet:
        print(f"xlsx {len(x)}건 · md {len(m)}건\n")
        for label, key in (("상태", "상태"), ("우선순위", "우선순위"), ("담당", "담당")):
            c = collections.Counter(v[key] for v in x.values())
            print(f"[{label}] " + " · ".join(f"{k} {n}" for k, n in c.most_common()))
        print()

    bad = bool(only_x or only_m or diff)

    if only_x:
        print(f"⚠ xlsx 에만 있다 — md 에 옮겨야 한다 ({len(only_x)}건)")
        for fid in only_x:
            v = x[fid]
            print(f"   {fid}  {v['기능명']}  ({v['상태']} · {v['우선순위']} · {v['담당']})")
        print()
    if only_m:
        print(f"⚠ md 에만 있다 — xlsx 에서 지웠거나 ID 가 바뀌었다 ({len(only_m)}건)")
        for fid in only_m:
            print(f"   {fid}  (md: {m[fid]['상태']} · {m[fid]['우선순위']})")
        print()
    if diff:
        print(f"⚠ 값이 어긋난다 ({len(diff)}건)")
        for fid, k, xv, mv in diff:
            print(f"   {fid}  {k}:  xlsx '{xv}'  vs  md '{mv}'")
        print("   → 어느 쪽이 맞는지 이 도구는 모른다. **코드로 확인한다.**")
        print("      xlsx 는 사람이 손으로 갱신하므로 머지된 PR 을 못 따라간다.")
        print("      실제로 2026-08-20 에 DSH-001·SRH-002-3 이 그랬다 — xlsx 가 낡았다.")
        print()

    if not bad:
        print(f"✅ 어긋난 것이 없다. {len(x)}건이 양쪽에서 같다.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
