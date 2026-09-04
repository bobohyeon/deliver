# =============================================================================
# 이 파일의 책임: JSX·JS 파일에서 빌드를 깨뜨리는 흔한 실수를 정적으로 잡는다.
#   npm 이 없거나 node_modules 를 설치할 수 없는 환경에서 vite build 대신 쓴다.
#
#   검사 항목
#     1. import 경로가 실제 파일을 가리키는가 (가장 흔한 빌드 실패 원인)
#     2. 괄호 · 중괄호 · 대괄호 균형
#     3. JSX 태그 균형
#     4. CSS 중괄호 균형
#
#   ⚠ 정규식으로 JSX 를 세면 틀린다
#     처음에 <Tag attr={x => y}/> 를 정규식으로 잡으려 했는데, 화살표 함수의
#     "=>" 안에 있는 ">" 를 태그 끝으로 오인해 self-closing 태그를 열린 태그로
#     읽었다. 그래서 여기서는 중괄호 깊이와 문자열 상태를 추적하는 스캐너를 쓴다.
#     정규식은 쓰지 않는다.
#
#   ⚠ 이 도구는 문법만 본다
#     타입 오류 · 없는 prop · 런타임 오류는 잡지 못한다. vite build 를 돌릴 수
#     있게 되면 그것을 먼저 믿는다.
#
# 다른 파일과의 관계: Tasqra/frontend 를 대상으로 돌린다. 검사기 자체가 맞는지
#   확인하려고 --all 로 기존 파일 전부를 검사할 수 있다 — 이미 머지된 파일에서
#   실패가 나오면 코드가 아니라 이 도구가 틀린 것이다.
#
# Spring 비교: 컴파일 없이 소스만 훑는 정적 분석기(Checkstyle 류)에 해당한다.
#
# 사용법
#   python check_jsx.py --root C:\dev\Tesqra\Tasqra\frontend --all
#   python check_jsx.py --root C:\dev\Tesqra\Tasqra\frontend src/features/search/SearchView.jsx
# =============================================================================

from __future__ import annotations

import argparse
import pathlib
import sys

VOID_TAGS = {
    "br", "hr", "img", "input", "meta", "link", "source", "area",
    "base", "col", "embed", "track", "wbr",
}

RESOLVE_SUFFIXES = ("", ".js", ".jsx", ".ts", ".tsx", ".css", ".json")
RESOLVE_INDEX = ("index.js", "index.jsx", "index.ts", "index.tsx")

# 이 문자 뒤에 오는 '/' 는 나눗셈이 아니라 정규식의 시작이다.
# 예: disposition.match(/filename="?([^";]+)"?/i)
#   여기서 '(' 다음의 '/' 를 나눗셈으로 보면 정규식 안의 '"' 를 문자열 시작으로
#   읽어 뒤쪽 구조가 전부 어긋난다. 실제로 api/document.js 에서 오탐이 났다.
# '<' 와 '>' 는 넣지 않는다. JSX 에서 </div> 의 '/' 가 '<' 뒤에 오므로,
# '<' 를 넣으면 모든 닫는 태그를 정규식 시작으로 오인해 그 뒤를 통째로 지운다.
# 실제로 그렇게 해서 기존 파일 45개가 실패로 잡혔다.
# 대가로 `a > /re/` 같은 표현은 못 잡지만 그런 코드는 사실상 없다.
# '}' 도 넣지 않는다. JSX 에서 attr={expr}/> 가 가장 흔한 형태이고, 그 '/' 앞이
# '}' 이므로 넣으면 self-closing 태그를 정규식으로 오인한다.
REGEX_PRECEDERS = set("(,=:[!&|?;+*~^%")
REGEX_KEYWORDS = {
    "return", "typeof", "case", "in", "of", "new", "delete",
    "void", "throw", "do", "else", "yield", "await",
}


def is_void_tag(name: str) -> bool:
    """닫는 태그가 필요 없는 HTML 요소인가.

    JSX 규칙: 소문자로 시작하면 DOM 요소, 대문자로 시작하면 React 컴포넌트다.
    이 구분을 빠뜨리면 react-router 의 <Link> 가 HTML 의 <link> 로 오인되어
    자기닫는 태그로 취급된다. 실제로 그 오탐 때문에 기존 파일 5개가 실패로
    잡혔다 — <Link>...</Link> 의 짝이 어긋난 것으로 보였다.
    """
    return bool(name) and name[0].islower() and name in VOID_TAGS


def _is_regex_start(prev_char: str, prev_word: str) -> bool:
    """'/' 가 정규식의 시작인지 판단한다.

    직전 토큰만 보면 된다. 처음에는 지워진 버퍼를 뒤로 걸어가며 판단했는데,
    문자열을 공백으로 지운 뒤라 label="..."/> 의 '/' 앞이 '=' 로 보였고
    self-closing 태그를 정규식으로 오인했다. 그래서 앞으로 훑으면서 직전
    토큰을 기억하는 방식으로 바꿨다.
    """
    if not prev_char:
        return True
    if prev_word in REGEX_KEYWORDS:
        return True
    return prev_char in REGEX_PRECEDERS


# ─── 공통 스캐너 ─────────────────────────────────────────────────────────────


def strip_strings_and_comments(src: str) -> str:
    """문자열 · 주석 · 정규식 리터럴을 같은 길이의 공백으로 바꾼다.

    길이를 유지하는 이유: 오류 위치를 원본 줄 번호로 알려주려면 인덱스가
    어긋나면 안 된다. 템플릿 문자열 안의 ${...} 는 실제 코드이므로 남긴다.

    앞으로 한 번만 훑으면서 "직전 의미 있는 토큰"을 기억한다. 그것이 정규식과
    나눗셈을 구분하는 데 필요하다. 지운 뒤 뒤로 걸어가서 판단하면
    label="..."/> 처럼 문자열 다음의 '/' 를 정규식으로 오인한다.
    """
    out = list(src)
    i, n = 0, len(src)
    prev_char = ""   # 마지막 의미 있는 문자 (공백 · 주석 · 문자열 내부 제외)
    prev_word = ""   # 마지막 식별자 (return /re/ 같은 경우를 구분하려고)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]

        if c in " \t\n\r":
            i += 1
            continue

        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue

        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue

        if c in "\"'":
            quote = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == quote:
                    j += 1
                    break
                if src[j] == "\n":
                    break  # 줄을 넘는 문자열은 없다. 여기서 끊는다.
                j += 1
            blank(i, j)
            i = j
            # 문자열이 끝난 자리는 값이다. 뒤에 오는 '/' 는 나눗셈이다.
            prev_char, prev_word = '"', ""
            continue

        if c == "`":
            j = i + 1
            blank(i, i + 1)
            while j < n:
                if src[j] == "\\":
                    blank(j, min(j + 2, n))
                    j += 2
                    continue
                if src[j] == "`":
                    blank(j, j + 1)
                    j += 1
                    break
                if src.startswith("${", j):
                    # ${ ... } 안은 실제 코드다. 그대로 남긴다.
                    depth = 0
                    while j < n:
                        if src[j] == "{":
                            depth += 1
                        elif src[j] == "}":
                            depth -= 1
                            if depth == 0:
                                j += 1
                                break
                        j += 1
                    continue
                blank(j, j + 1)
                j += 1
            i = j
            prev_char, prev_word = '"', ""
            continue

        if c == "/" and _is_regex_start(prev_char, prev_word):
            # 정규식 리터럴. 문자 클래스([...]) 안에서는 '/' 를 escape 하지 않아도
            # 되므로 클래스 안팎을 구분해야 한다.
            j = i + 1
            in_class = False
            closed = False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "\n":
                    break  # 정규식은 줄을 넘지 않는다 -> 나눗셈이었다
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    closed = True
                    j += 1
                    break
                j += 1
            if closed:
                while j < n and src[j].isalpha():   # gimsuy 플래그
                    j += 1
                blank(i, j)
                i = j
                prev_char, prev_word = "x", ""     # 정규식도 값이다
                continue
            # 닫히지 않았으면 나눗셈이다. 아래로 흘려보낸다.

        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev_word = src[i:j]
            prev_char = src[j - 1]
            i = j
            continue

        prev_char, prev_word = c, ""
        i += 1

    return "".join(out)


def line_of(src: str, index: int) -> int:
    return src.count("\n", 0, index) + 1


# ─── 검사 1. import 해석 ─────────────────────────────────────────────────────


def find_imports(clean: str, original: str) -> list[tuple[str, int]]:
    """import ... from '경로' 와 import '경로' 를 찾는다.

    문자열이 비워진 clean 에서는 경로를 읽을 수 없으므로, clean 으로 위치만
    찾고 값은 original 에서 읽는다.
    """
    found: list[tuple[str, int]] = []
    i = 0
    while True:
        i = clean.find("import", i)
        if i < 0:
            break
        # 단어 경계 확인 (예: importantThing 을 걸러낸다)
        before = clean[i - 1] if i > 0 else "\n"
        after = clean[i + 6] if i + 6 < len(clean) else "\n"
        if before.isalnum() or before in "_$" or (after.isalnum() or after in "_$"):
            i += 6
            continue
        # 이 import 문이 끝나는 곳까지에서 마지막 문자열 리터럴을 찾는다.
        end = clean.find("\n", i)
        end = len(clean) if end < 0 else end
        segment = original[i:end]
        spec = None
        for quote in ("'", '"'):
            a = segment.rfind(quote)
            if a < 0:
                continue
            b = segment.rfind(quote, 0, a)
            if b >= 0:
                candidate = segment[b + 1 : a]
                if spec is None or len(candidate) > 0:
                    spec = candidate
        if spec:
            found.append((spec, line_of(original, i)))
        i = end
    return found


def resolve_import(spec: str, from_file: pathlib.Path) -> pathlib.Path | None:
    base = from_file.parent
    target = (base / spec).resolve()
    for suffix in RESOLVE_SUFFIXES:
        candidate = target if suffix == "" else target.with_name(target.name + suffix)
        if candidate.is_file():
            return candidate
    for name in RESOLVE_INDEX:
        candidate = target / name
        if candidate.is_file():
            return candidate
    return None


def check_imports(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    clean = strip_strings_and_comments(src)
    problems: list[str] = []
    for spec, line in find_imports(clean, src):
        if not spec.startswith("."):
            continue  # 패키지는 node_modules 없이 확인할 수 없다
        if resolve_import(spec, path) is None:
            problems.append(f"{path}:{line} import '{spec}' 를 찾을 수 없다")
    return problems


# ─── 검사 2. 괄호 균형 ───────────────────────────────────────────────────────


def check_brackets(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    clean = strip_strings_and_comments(src)
    pairs = {")": "(", "}": "{", "]": "["}
    stack: list[tuple[str, int]] = []
    for i, c in enumerate(clean):
        if c in "({[":
            stack.append((c, i))
        elif c in pairs:
            if not stack:
                return [f"{path}:{line_of(src, i)} 닫는 '{c}' 에 대응하는 열림이 없다"]
            opened, at = stack.pop()
            if opened != pairs[c]:
                return [
                    f"{path}:{line_of(src, i)} '{c}' 가 "
                    f"{line_of(src, at)}행의 '{opened}' 와 짝이 맞지 않는다"
                ]
    if stack:
        opened, at = stack[-1]
        return [f"{path}:{line_of(src, at)} '{opened}' 가 닫히지 않았다"]
    return []


# ─── 검사 3. JSX 태그 균형 ───────────────────────────────────────────────────


def scan_jsx_tags(src: str, clean: str) -> list[str]:
    """중괄호 깊이를 추적하며 태그를 읽는다.

    정규식을 쓰지 않는 이유가 여기 있다. attr={x => y} 의 '>' 는 태그 끝이
    아니다. 중괄호 안에 있는 '>' 는 전부 건너뛴다.
    """
    stack: list[tuple[str, int]] = []
    i, n = 0, len(clean)
    while i < n:
        if clean[i] != "<":
            i += 1
            continue
        j = i + 1
        closing = False
        if j < n and clean[j] == "/":
            closing = True
            j += 1
        # 태그 이름
        start_name = j
        while j < n and (clean[j].isalnum() or clean[j] in "._$"):
            j += 1
        name = clean[start_name:j]
        if not name or not (name[0].isalpha() or name[0] == "_"):
            # <= 나 <<, 또는 <> (Fragment) 다. Fragment 는 짝만 세도 되지만
            # 축약 Fragment(<>)는 이름이 없으므로 별도로 다룬다.
            if not closing and j < n and clean[j] == ">":
                stack.append(("<>", i))
                i = j + 1
                continue
            if closing and j < n and clean[j] == ">":
                if stack and stack[-1][0] == "<>":
                    stack.pop()
                    i = j + 1
                    continue
                return [f"{line_of(src, i)}행 닫는 </> 에 대응하는 <> 가 없다"]
            i += 1
            continue

        # 태그 끝 '>' 찾기 — 중괄호 깊이 0 에서만 인정한다.
        depth = 0
        self_close = False
        while j < n:
            c = clean[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif depth == 0 and c == ">":
                self_close = clean[j - 1] == "/"
                break
            j += 1
        if j >= n:
            return [f"{line_of(src, i)}행 <{name}> 태그가 닫히지 않았다 ('>' 없음)"]

        if closing:
            if not stack:
                return [f"{line_of(src, i)}행 닫는 </{name}> 에 대응하는 열림이 없다"]
            opened, at = stack.pop()
            if opened != name:
                return [
                    f"{line_of(src, i)}행 </{name}> 가 "
                    f"{line_of(src, at)}행의 <{opened}> 를 닫으려 한다"
                ]
        elif not self_close and not is_void_tag(name):
            stack.append((name, i))
        i = j + 1

    if stack:
        name, at = stack[-1]
        return [f"{line_of(src, at)}행 <{name}> 가 닫히지 않았다"]
    return []


def check_jsx(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    clean = strip_strings_and_comments(src)
    return [f"{path}:{p}" for p in scan_jsx_tags(src, clean)]


# ─── 검사 4. CSS ─────────────────────────────────────────────────────────────


def check_css(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    # CSS 주석만 제거한다 (// 는 CSS 주석이 아니다).
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            end = n if end < 0 else end + 2
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        i += 1
    clean = "".join(out)
    opens, closes = clean.count("{"), clean.count("}")
    if opens != closes:
        return [f"{path} 중괄호 불균형: {{ {opens}개 · }} {closes}개"]
    return []


# ─── 실행 ────────────────────────────────────────────────────────────────────


def collect(root: pathlib.Path) -> list[pathlib.Path]:
    src = root / "src"
    if not src.is_dir():
        raise SystemExit(f"src 폴더가 없다: {src}")
    files = [
        p for p in src.rglob("*")
        if p.is_file() and p.suffix in (".js", ".jsx", ".css")
    ]
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(description="JSX·JS·CSS 정적 검사 (npm 없이)")
    parser.add_argument("--root", default=".", help="frontend 폴더")
    parser.add_argument("--all", action="store_true", help="src 전체를 검사한다")
    parser.add_argument("paths", nargs="*", help="root 기준 상대 경로")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    if args.all or not args.paths:
        files = collect(root)
    else:
        files = [(root / p).resolve() for p in args.paths]

    problems: list[str] = []
    counts = {"js": 0, "css": 0}
    for path in files:
        if not path.is_file():
            problems.append(f"{path} 파일이 없다")
            continue
        if path.suffix == ".css":
            counts["css"] += 1
            problems += check_css(path)
            continue
        counts["js"] += 1
        problems += check_imports(path)
        problems += check_brackets(path)
        if path.suffix in (".jsx", ".tsx"):
            problems += check_jsx(path)

    print(f"검사한 파일 — js/jsx {counts['js']}개 · css {counts['css']}개")
    print("=" * 66)
    if problems:
        for p in problems:
            print("  실패", p)
        print()
        print(f"실패 {len(problems)}건")
        print()
        print("  이미 머지된 파일에서 실패가 나오면 코드가 아니라 이 도구가 틀린 것이다.")
        print("  --all 로 전체를 돌려 기존 파일이 통과하는지 먼저 확인하라.")
        sys.exit(1)
    print("  문제 없음")


if __name__ == "__main__":
    main()
