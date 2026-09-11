# =============================================================================
# 이 파일의 책임: UI 목업 HTML 이 "열어 보기 전에" 깨졌는지 검사한다.
#
#   왜 필요한가
#     목업은 팀원에게 의견을 물으려고 만든다. 그런데 목업이 깨져 있으면 사람들이
#     디자인이 아니라 버그를 보고 판단한다. 실제로 v1 에서 사이드바를 접을 때
#     글씨가 잘렸는데(rail__tag 를 숨기는 규칙에서 빠뜨림 + overflow:hidden 없음),
#     그 상태로 공유했으면 "접기가 이상하다" 는 답만 돌아왔을 것이다.
#
#   무엇을 잡는가
#     (1) 태그 균형 · HTML 에서 쓴 class 가 CSS 에 있는지
#     (2) 사이드바를 접었을 때 잘릴 글씨가 있는지  ← v1 의 실제 버그
#     (3) 테마 변수가 두 테마에 대칭으로 정의됐는지 (한쪽만 있으면 전환 시 색이 깨진다)
#     (4) 정의되지 않은 var() 를 쓰는지
#     (5) 채움 강조가 하나인지 (문서·화면 공통 규칙)
#
#   무엇을 못 잡는가
#     실제로 예쁜지, 글자가 겹치는지, 브라우저별 차이. 그건 열어 봐야 한다.
#     이 검사는 "열어 보기 전에 확실히 잘못된 것" 만 본다.
#
# 다른 파일과의 관계: 도구/check_jsx.py 의 목업용 짝이다. check_jsx.py 는 실제
#   앱의 jsx·css 를 보고, 이것은 독립 HTML 목업 한 장을 본다.
#
# Spring 비교: 템플릿을 렌더링하지 않고 정적으로 검사하는 것에 해당한다.
#
# 사용법
#   python check_mockup.py 산출물\UI시안_Tasqra_v1.html
# =============================================================================

from __future__ import annotations

import argparse
import collections
import html.parser
import pathlib
import re
import sys

# 닫는 태그가 없어도 되는 것들. svg 하위 요소를 포함한다.
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
    "path", "circle", "rect", "ellipse", "stop", "line", "polygon", "polyline", "use",
}

# 사이드바에서 접혀도 남아도 되는 표시. 폭이 고정된 것만 해당한다.
KEEP_CLASSES = {"rail__text", "rail__keep"}


class TagBalance(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"줄 {self.getpos()[0]}: </{tag}> 가 여분이다")
            return
        top, line = self.stack.pop()
        if top != tag:
            self.errors.append(
                f"줄 {self.getpos()[0]}: </{tag}> 인데 열린 것은 <{top}> (줄 {line})"
            )


class RailText(html.parser.HTMLParser):
    """사이드바를 접었을 때 숨지 않는 글씨를 찾는다.

    글씨가 화면에 남으려면 조상 중 하나가 KEEP_CLASSES 를 가져야 한다.
    svg 안쪽 텍스트는 도형이라 제외한다.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.covered: list[bool] = []
        self.bad: list[tuple[str, int]] = []

    def handle_starttag(self, tag, attrs):
        classes = set((dict(attrs).get("class") or "").split())
        self.covered.append(bool(classes & KEEP_CLASSES) or tag == "svg")

    def handle_endtag(self, tag):
        if self.covered:
            self.covered.pop()

    def handle_data(self, data):
        text = data.strip()
        if text and not any(self.covered):
            self.bad.append((text[:40], self.getpos()[0]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="검사할 목업 HTML")
    args = parser.parse_args()

    path = pathlib.Path(args.path)
    if not path.exists():
        print(f"파일이 없다: {path}")
        return 2

    src = path.read_text(encoding="utf-8")
    style_match = re.search(r"<style>(.*?)</style>", src, re.S)
    if not style_match:
        print("<style> 블록을 찾지 못했다.")
        return 2
    # CSS 주석을 먼저 지운다. 이걸 안 하면 주석에 적힌 글자가 선언으로 오인된다.
    #
    # 실제로 그래서 검사가 거짓 통과했다 — .rail 블록 위에
    # "overflow:hidden 이 있어야 …" 라는 주석이 있었고, 선언을 지워도 그 주석
    # 글자가 정규식에 걸려 "있다" 로 판정됐다. class 정의 검사도 같은 함정이
    # 있다: 주석에 ".rail__text 를 붙여라" 라고 쓰면 그 클래스가 정의된 것으로
    # 세어진다. 검사기는 주석이 아니라 코드만 봐야 한다.
    style = re.sub(r"/\*.*?\*/", "", style_match.group(1), flags=re.S)
    body = src.split("</style>", 1)[1]

    failures: list[str] = []
    passed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        """detail 은 실패할 때만 보여준다.

        통과할 때도 붙이면 "통과 ... → 이렇게 고쳐라" 처럼 읽혀서 경고인지
        아닌지 헷갈린다. 실제로 처음에 그렇게 만들어서 통과가 경고처럼 보였다.
        """
        nonlocal passed
        if ok:
            passed += 1
            print(f"  통과  {name}")
            return
        print(f"  실패  {name}" + (f"\n          {detail}" if detail else ""))
        failures.append(f"{name}{(' — ' + detail) if detail else ''}")

    print(f"검사 대상: {path}")
    print("=" * 66)

    # (1) 태그 균형
    balance = TagBalance()
    balance.feed(src)
    for tag, line in balance.stack:
        balance.errors.append(f"<{tag}> 가 닫히지 않았다 (줄 {line})")
    check("태그 균형", not balance.errors, "; ".join(balance.errors[:3]))

    # (1) class 정의
    defined = set(re.findall(r"\.([a-zA-Z][\w-]*)", style))
    used: collections.Counter = collections.Counter()
    for group in re.findall(r'class="([^"]+)"', body):
        for name in group.split():
            used[name] += 1
    missing = sorted(name for name in used if name not in defined)
    check(f"class 정의 (사용 {len(used)}종)", not missing, f"CSS 에 없다: {missing}")

    # (2) 접었을 때 잘릴 글씨 — v1 의 실제 버그
    rail_match = re.search(r'<aside class="rail".*?</aside>', body, re.S)
    if rail_match is None:
        check("사이드바를 찾았다", False, "<aside class=\"rail\"> 가 없다")
    else:
        rail = rail_match.group(0)
        finder = RailText()
        finder.feed(rail)
        detail = "; ".join(f"줄 {ln}: {txt!r}" for txt, ln in finder.bad[:4])
        check(
            "접었을 때 사이드바 글씨가 모두 숨는다",
            not finder.bad,
            detail + "  → .rail__text 나 .rail__keep 을 붙여라",
        )
        check(
            ".rail 에 overflow:hidden 이 있다",
            re.search(r"\.rail\s*\{[^}]*overflow:\s*hidden", style, re.S) is not None,
            "없으면 접는 동안 글씨가 삐져나온다",
        )
        check(
            "접기 버튼이 사이드바 안에 있다",
            'id="toggle"' in rail,
            "헤더에 두면 사이드바와 따로 움직이는 것처럼 보인다",
        )

    # (3) 테마 변수 대칭
    themes = {
        name: set(re.findall(r"(--[\w-]+)\s*:", block))
        for name, block in re.findall(
            r'\[data-theme="([\w-]+)"\]\s*\{(.*?)\}', style, re.S
        )
    }
    if len(themes) < 2:
        check("테마가 둘 이상 정의됐다", False, f"찾은 테마: {sorted(themes)}")
    else:
        names = sorted(themes)
        first = themes[names[0]]
        diff = {n: sorted(themes[n] ^ first) for n in names[1:] if themes[n] ^ first}
        check(
            f"테마 변수 대칭 ({', '.join(f'{n} {len(themes[n])}개' for n in names)})",
            not diff,
            f"한쪽에만 있는 변수: {diff}",
        )

    # (4) 정의 없는 var()
    root = set(re.findall(r"(--[\w-]+)\s*:", style))
    undefined = sorted(set(re.findall(r"var\((--[\w-]+)", style)) - root)
    check("모든 var() 가 정의돼 있다", not undefined, f"정의 없음: {undefined}")

    # (5) 채움 강조는 하나만
    #
    # is-filled 표식으로 센다. 특정 클래스 이름(urgent·needs 등)으로 세면 이름을
    # 바꿀 때 검사가 조용히 무력해진다 — 실제로 카드를 개편하면서 urgent 가
    # 사라졌는데 검사는 "0개" 를 세고도 통과할 뻔했다.
    filled = len(re.findall(r'class="[^"]*\bis-filled\b', body))
    check(
        "채움 강조가 하나다",
        filled == 1,
        f"{filled}개다 — 강조가 없으면 무엇이 급한지 알 수 없고, 둘이면 우선순위가 사라진다",
    )

    # (6) 사이드바 기본은 펼침
    #
    # 접힘을 기본으로 두면 처음 들어온 사람이 아이콘만 보고 무엇인지 모른다.
    # 사용자가 접으면 그 선택은 기억한다(localStorage).
    body_tag = re.search(r"<body[^>]*>", body)
    check(
        "사이드바 기본은 펼침이다",
        body_tag is not None and "mini" not in body_tag.group(0),
        "<body> 에 mini 가 있으면 접힌 상태로 열린다",
    )

    print("=" * 66)
    total = passed + len(failures)
    if failures:
        print(f"  {total}건 중 실패 {len(failures)}건")
        return 1
    print(f"  {total}건 전부 통과")
    print()
    print("  참고 — 이 검사는 '확실히 잘못된 것' 만 본다. 실제로 읽기 좋은지는")
    print("  브라우저로 열어서 봐야 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
