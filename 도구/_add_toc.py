# -*- coding: utf-8 -*-
"""마크다운 산출물에 목차를 넣는다. 이미 있으면 갈아끼운다.

이 파일의 책임
    제목(h2·h3)을 훑어 GitHub 앵커 규칙으로 링크 목록을 만들고, 첫 h2 앞에
    끼운다. `<!-- 목차 시작 -->` · `<!-- 목차 끝 -->` 사이만 건드리므로
    여러 번 돌려도 목차가 겹쳐 쌓이지 않는다. 본문은 한 글자도 고치지 않는다.

다른 파일과의 관계
    `관리/*.md` 산출물을 대상으로 한다. `_md2html.py` 가 같은 마크다운을
    인쇄용 HTML 로 바꾸는데, 그쪽은 제목을 <h2> 로만 옮기고 목차는 안 만든다.
    그래서 목차는 원본 마크다운에 심어 두 경로(GitHub·HTML)에 함께 나오게 한다.

Spring 비교
    소스를 읽어 문서를 만들어 붙이는 빌드 후처리다. Maven 의 site 플러그인이
    프로젝트에서 보고서를 뽑아 얹는 자리와 같다. 원본을 훼손하지 않도록
    표시(마커) 구간만 다시 쓰는 방식은 JPA 의 `@Generated` 컬럼처럼
    "손으로 쓴 곳"과 "도구가 쓴 곳"을 나눠 두는 것과 통한다.
"""
import re
import sys
import unicodedata
from pathlib import Path

BEGIN = "<!-- 목차 시작 -->"
END = "<!-- 목차 끝 -->"

# 목차에 넣을 제목 깊이. h1 은 문서 이름이므로 뺀다.
# h4 까지 넣으면 결과서가 130줄을 넘겨 오히려 찾기 어려워진다.
LEVELS = (2, 3)


def slug(text: str) -> str:
    """제목을 GitHub 이 붙이는 앵커 이름으로 바꾼다.

    GitHub 은 마크다운을 HTML 로 만든 뒤 글자만 남겨 앵커를 만든다. 그래서
    `코드` 와 **굵게** 표시는 사라지고 안쪽 글자만 남는다. 그다음 소문자로
    내리고, 구두점과 기호를 지우고, 공백을 붙임표로 바꾼다.
    가운뎃점(·)과 줄표(—)는 지워지지만 붙임표(-)와 밑줄(_)은 남는다.
    """
    # 인라인 표시를 벗긴다. 링크는 보이는 글자만 남긴다.
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)

    text = text.strip().lower()

    kept = []
    for ch in text:
        if ch in "-_":
            kept.append(ch)
            continue
        # P* 는 구두점, S* 는 기호다. 둘 다 앵커에서 빠진다.
        if unicodedata.category(ch)[0] in ("P", "S"):
            continue
        kept.append(ch)

    return "".join(kept).replace(" ", "-")


def headings(lines: list[str]) -> list[tuple[int, str, int]]:
    """(깊이, 제목, 줄번호) 목록을 만든다. 코드블록 안과 목차 구간 안은 제목이 아니다.

    결과서 안에 코드블록으로 감싼 `## 1~1행` 예시가 있다. 렌더링될 때는
    제목이 아니므로 앵커도 생기지 않는다. 울타리(```)를 세어 걸러낸다.

    목차 구간(BEGIN~END)도 건너뛴다. 이 구간에는 도구가 넣은 `## 목차` 제목이
    들어 있어서, 걸러내지 않으면 두 번째 실행부터 목차가 자기 자신을 항목으로
    넣어 `- [목차](#목차)` 가 생긴다. 실제로 그렇게 새는 것을 확인해 고쳤다.
    """
    found = []
    fence = None
    in_toc = False
    for number, line in enumerate(lines):
        stripped = line.strip()

        # 목차 구간은 도구가 쓴 자리다. 훑을 대상이 아니다.
        if stripped == BEGIN:
            in_toc = True
            continue
        if stripped == END:
            in_toc = False
            continue
        if in_toc:
            continue

        # 울타리는 ``` 와 ~~~ 두 가지다. 같은 문자로만 닫힌다.
        mark = re.match(r"(`{3,}|~{3,})", stripped)
        if mark:
            token = mark.group(1)[0]
            if fence is None:
                fence = token
            elif fence == token:
                fence = None
            continue
        if fence is not None:
            continue

        head = re.match(r"(#{1,6})\s+(.+)", stripped)
        if head and len(head.group(1)) in LEVELS:
            found.append((len(head.group(1)), head.group(2).strip(), number))
    return found


def build_toc(items: list[tuple[int, str, int]]) -> list[str]:
    """링크 목록을 만든다. 같은 앵커가 겹치면 GitHub 처럼 -1, -2 를 붙인다."""
    seen: dict[str, int] = {}
    top = min(depth for depth, _, _ in items)
    out = [BEGIN, "", "## 목차", ""]

    for depth, title, _ in items:
        anchor = slug(title)
        if anchor in seen:
            seen[anchor] += 1
            anchor = f"{anchor}-{seen[anchor]}"
        else:
            seen[anchor] = 0

        # 표시 글자에서는 굵게만 벗긴다. `코드` 는 남겨 두는 편이 눈에 띈다.
        label = re.sub(r"\*\*([^*]*)\*\*", r"\1", title)
        out.append(f"{'  ' * (depth - top)}- [{label}](#{anchor})")

    out += ["", END]
    return out


def apply(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    items = headings(lines)
    if not items:
        return "제목 없음 — 건너뜀"

    toc = build_toc(items)

    # 이미 있으면 그 구간만 갈아끼운다.
    if BEGIN in text and END in text:
        start = next(i for i, l in enumerate(lines) if l.strip() == BEGIN)
        stop = next(i for i, l in enumerate(lines) if l.strip() == END)
        new_lines = lines[:start] + toc + lines[stop + 1:]
        note = f"목차 갱신 · 항목 {len(items)}"
    else:
        # 첫 제목 바로 앞에 넣는다. 그 위의 머리글(문서번호·작성자)은 그대로 둔다.
        at = items[0][2]
        # 제목 직전의 구분선(---)이 있으면 그 앞에 넣어 구분선이 목차를 감싸게 한다.
        back = at
        while back - 1 >= 0 and not lines[back - 1].strip():
            back -= 1
        if back - 1 >= 0 and re.fullmatch(r"-{3,}", lines[back - 1].strip()):
            at = back - 1
        new_lines = lines[:at] + toc + ["", "---", ""] + lines[at:]
        note = f"목차 삽입 · 항목 {len(items)}"

    path.write_text("\n".join(new_lines), encoding="utf-8")
    return note


if __name__ == "__main__":
    targets = [Path(p) for p in sys.argv[1:]]
    if not targets:
        targets = sorted(Path("관리").glob("RAG_임베딩모델_*.md"))

    for target in targets:
        print(f"{apply(target):<20} {target}")
