"""엑셀(.xlsx)을 표준 라이브러리만으로 읽어 CSV·TSV·마크다운으로 뽑는다.

이 파일의 책임
    구글 스프레드시트에서 내려받은 .xlsx 를 사람이 채팅으로 복붙하지 않고도
    읽을 수 있게 만든다. `openpyxl`·`pandas` 를 쓰지 않는다 — 샌드박스는 외부
    네트워크가 막혀 있어 설치가 불가능하다. .xlsx 는 zip 안에 XML 이 들어 있는
    표준 형식(OOXML)이므로 `zipfile` + `xml` 로 충분하다.

다른 파일과의 관계
    입력  산출물/기능명세서_v5_세분화.xlsx  (레포에 커밋되어 있다)
    출력  --to md   -> 관리/기능명세서.md 를 갱신할 때 붙여 쓰는 표
          --to csv  -> diff 가 읽히는 형식. 판본 비교에 쓴다
    도구/embed-test/ 의 도구들과 달리 이 파일은 임베딩과 무관하다. 산출물 문서
    쪽 도구다.

Spring 비교
    Apache POI 의 `WorkbookFactory.create(file)` 자리다. 다만 POI 처럼 서식·수식을
    다루지 않고 **셀의 표시값만** 읽는다. POI 의 `DataFormatter` 만 남긴 셈이다.
    의존성을 0 으로 만드는 것이 목적이므로 기능을 일부러 줄였다.

사용법
    python xlsx_read.py <파일.xlsx>                    # 시트 목록과 크기
    python xlsx_read.py <파일.xlsx> --sheet 1 --to csv
    python xlsx_read.py <파일.xlsx> --sheet 1 --to md  --out ../관리/표.md
    python xlsx_read.py <파일.xlsx> --sheet 1 --to tsv --max-col 8

.xlsm(매크로 포함)도 된다
    `.xlsm` 은 `.xlsx` 와 **같은 OOXML 컨테이너**다. 다른 것은 매크로 바이너리
    (`xl/vbaProject.bin`)가 들어 있고 `[Content_Types].xml` 의 타입이
    `macroEnabled` 로 바뀐 것뿐이다. **시트 XML 구조는 동일하다.**
    2026-08-20 에 실제 `.xlsm` 을 만들어 돌려 보고, 추출 결과가 `.xlsx` 와
    **바이트까지 같은 것**을 확인했다. `.xlsb`(바이너리 판)는 **안 된다** — 그건
    XML 이 아니라 독자 바이너리 형식이라 구조가 다르다.

주의
    숫자 서식(백분율·통화·날짜)은 **원시값**으로 나온다. `0.907` 이 엑셀 화면에
    `90.7%` 로 보이더라도 여기서는 `0.907` 이다. 표시값이 필요하면 스프레드시트
    쪽에서 텍스트로 바꿔 내보내는 것이 안전하다. 이걸 모르고 수치를 옮기면
    100배 틀린다.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _text_of(node) -> str:
    """<si> 또는 <is> 아래 흩어진 <t> 를 모두 이어 붙인다.

    셀 안에서 글자 일부만 서식이 다르면 <r><t>조각</t></r> 로 쪼개진다.
    첫 <t> 만 읽으면 글자가 잘린다 — 그래서 전부 모은다.
    """
    return "".join(t.text or "" for t in node.iter(f"{{{NS['m']}}}t"))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    """sharedStrings.xml 이 없는 파일도 있다(문자열이 셀에 직접 박힌 경우)."""
    try:
        raw = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    return [_text_of(si) for si in ET.fromstring(raw).findall("m:si", NS)]


def _sheets(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    """(시트이름, zip 내부 경로) 목록. workbook 의 순서를 그대로 지킨다."""
    rels = {
        r.get("Id"): r.get("Target")
        for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    }
    out = []
    rid = f"{{http://schemas.openxmlformats.org/officeDocument/2006/relationships}}id"
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
        target = rels.get(sh.get(rid), "")
        path = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
        out.append((sh.get("name", "?"), path))
    return out


def _col_index(ref: str) -> int:
    """A1 표기의 열 문자를 0부터의 번호로. 'A'->0, 'Z'->25, 'AA'->26."""
    letters = re.match(r"([A-Z]+)", ref or "A")
    n = 0
    for ch in (letters.group(1) if letters else "A"):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_sheet(xlsx: Path, index: int) -> tuple[str, list[list[str]]]:
    """시트 하나를 2차원 문자열 표로 읽는다. 빈 셀은 ''."""
    with zipfile.ZipFile(xlsx) as z:
        strings = _shared_strings(z)
        sheets = _sheets(z)
        if not 1 <= index <= len(sheets):
            raise SystemExit(f"시트 번호는 1~{len(sheets)} 이다 (받은 값 {index})")
        name, path = sheets[index - 1]
        root = ET.fromstring(z.read(path))

    rows: list[list[str]] = []
    for row in root.iter(f"{{{NS['m']}}}row"):
        cells: list[str] = []
        for c in row.findall("m:c", NS):
            at = _col_index(c.get("r", ""))
            while len(cells) < at:          # 빈 셀은 XML 에서 아예 빠진다
                cells.append("")
            kind = c.get("t")
            if kind == "s":                 # 공유 문자열 표의 색인
                v = c.find("m:v", NS)
                i = int(v.text) if v is not None and v.text else -1
                cells.append(strings[i] if 0 <= i < len(strings) else "")
            elif kind == "inlineStr":       # 셀에 직접 박힌 문자열
                is_ = c.find("m:is", NS)
                cells.append(_text_of(is_) if is_ is not None else "")
            else:                           # 숫자·불리언·수식 결과
                v = c.find("m:v", NS)
                cells.append((v.text or "") if v is not None else "")
        rows.append(cells)

    while rows and not any(x.strip() for x in rows[-1]):
        rows.pop()                          # 꼬리의 빈 행을 버린다
    width = max((len(r) for r in rows), default=0)
    for r in rows:
        r.extend("" for _ in range(width - len(r)))
    return name, rows


def to_markdown(rows: list[list[str]]) -> str:
    """첫 행을 머리로 쓴다. 셀 안의 | 와 줄바꿈은 표를 깨뜨리므로 바꾼다."""
    def cell(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " <br>").strip()

    if not rows:
        return ""
    head = rows[0]
    out = ["| " + " | ".join(cell(c) for c in head) + " |",
           "|" + "|".join("---" for _ in head) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join(cell(c) for c in r) + " |")
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="xlsx 를 표준 라이브러리만으로 읽는다")
    p.add_argument("xlsx", type=Path)
    p.add_argument("--sheet", type=int, help="1부터. 생략하면 시트 목록만 찍는다")
    p.add_argument("--to", choices=["csv", "tsv", "md"], default="csv")
    p.add_argument("--out", type=Path, help="생략하면 화면으로")
    p.add_argument("--max-row", type=int, help="앞에서 이만큼만")
    p.add_argument("--max-col", type=int, help="왼쪽에서 이만큼만")
    a = p.parse_args()

    if not a.xlsx.exists():
        raise SystemExit(f"파일이 없다: {a.xlsx}")

    if a.sheet is None:
        with zipfile.ZipFile(a.xlsx) as z:
            sheets = _sheets(z)
        print(f"{a.xlsx.name} — 시트 {len(sheets)}개")
        for i, (nm, _) in enumerate(sheets, 1):
            _, rows = read_sheet(a.xlsx, i)
            cols = max((len(r) for r in rows), default=0)
            print(f"  {i}. {nm}  — {len(rows)}행 x {cols}열")
        print("\n--sheet <번호> 로 내용을 뽑는다")
        return

    name, rows = read_sheet(a.xlsx, a.sheet)
    if a.max_row:
        rows = rows[: a.max_row]
    if a.max_col:
        rows = [r[: a.max_col] for r in rows]

    if a.to == "md":
        text = to_markdown(rows)
        (a.out.write_text(text + "\n", encoding="utf-8") if a.out
         else print(text))
    else:
        delim = "\t" if a.to == "tsv" else ","
        fh = (a.out.open("w", newline="", encoding="utf-8-sig") if a.out
              else sys.stdout)
        try:
            csv.writer(fh, delimiter=delim).writerows(rows)
        finally:
            if a.out:
                fh.close()

    if a.out:
        print(f"시트 '{name}' {len(rows)}행 -> {a.out}")


if __name__ == "__main__":
    main()
