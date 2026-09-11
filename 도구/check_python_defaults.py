# =============================================================================
# 이 파일의 책임: 모듈 최상위 함수의 "기본값에서 아직 정의되지 않은 이름을 쓰는"
#   실수를 잡는다. FastAPI 의 Depends(...) 패턴에서 실제로 앱을 죽인 버그다.
#
#   왜 필요한가
#     def get_search_service(repo = Depends(get_project_repository)): ...
#     기본값은 **함수를 정의하는 순간** 평가된다. 그래서 get_project_repository 가
#     파일 아래쪽에 있으면 임포트할 때 NameError 가 나고 앱이 아예 뜨지 않는다.
#
#     이것은 문법 오류가 아니다. py_compile 도 ast.parse 도 통과한다. 그래서
#     "문법 검사 통과" 를 믿고 넘겼다가 api 컨테이너가 죽었다.
#     의존성이 설치되지 않은 환경에서는 실제 import 로 확인할 수 없으므로,
#     이름 해석만 정적으로 흉내낸다.
#
#   무엇을 잡는가 / 못 잡는가
#     잡는다   — 최상위 def/class 의 기본값 · 데코레이터에서 쓰는 최상위 이름 중
#                그 지점보다 아래에서 정의된 것
#     못 잡는다 — 함수 **본문**에서 쓰는 이름(호출 시점에 평가되므로 순서 무관),
#                타입 애너테이션(from __future__ import annotations 면 지연 평가),
#                import 실패 · 순환 import · 타입 오류
#
# 다른 파일과의 관계: 도구/check_jsx.py 의 파이썬 짝이다. 둘 다 "빌드를 돌릴 수
#   없는 환경에서 빌드가 깨질 이유를 미리 찾는" 목적이다.
#
# Spring 비교: 스프링 컨텍스트를 띄우지 않고 빈 정의 순서만 검사하는 것에 가깝다.
#   실제 Spring 은 순서에 영향을 받지 않지만(프록시로 늦게 묶는다), 파이썬의
#   기본값은 즉시 평가되므로 순서가 중요하다.
#
# 사용법
#   python check_python_defaults.py C:\dev\Tesqra\Tasqra\backend\app
#   python check_python_defaults.py <파일 또는 폴더> [...]
# =============================================================================

from __future__ import annotations

import argparse
import ast
import builtins
import pathlib
import sys

BUILTINS = set(dir(builtins))


def collect_module_names(tree: ast.Module) -> dict[str, int]:
    """모듈 최상위에서 정의되는 이름 -> 정의 줄 번호."""
    names: dict[str, int] = {}

    def note(name: str, line: int) -> None:
        # 같은 이름이 여러 번 나오면 가장 이른 줄을 남긴다.
        if name and (name not in names or line < names[name]):
            names[name] = line

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            note(node.name, node.lineno)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        note(sub.id, node.lineno)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                note(node.target.id, node.lineno)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                note(alias.asname or alias.name.split(".")[0], node.lineno)
        elif isinstance(node, (ast.For, ast.While, ast.If, ast.With, ast.Try)):
            # 조건부 정의도 최상위로 본다. 정확히 따라가려면 실행이 필요하므로
            # 여기서는 "정의된다"고만 보고 줄 번호만 남긴다.
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    note(sub.name, sub.lineno)
                elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    note(sub.id, sub.lineno)
    return names


def used_names(node: ast.AST) -> list[tuple[str, int]]:
    """식에서 읽는(Load) 이름을 모은다."""
    out: list[tuple[str, int]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            out.append((sub.id, getattr(sub, "lineno", 0)))
    return out


def check_file(path: pathlib.Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno} 문법 오류 — {exc.msg}"]

    defined = collect_module_names(tree)
    problems: list[str] = []

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        # 검사 대상 식: 데코레이터 + 기본값 (둘 다 정의 시점에 평가된다)
        targets: list[tuple[str, ast.AST]] = [("데코레이터", d) for d in node.decorator_list]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for default in list(args.defaults) + [d for d in args.kw_defaults if d]:
                targets.append(("기본값", default))

        for kind, expr in targets:
            for name, line in used_names(expr):
                if name in BUILTINS:
                    continue
                at = defined.get(name)
                if at is None:
                    # 모듈에 없는 이름. import 누락일 수도 있고, 우리가 추적하지
                    # 못한 형태일 수도 있어 경고만 한다.
                    problems.append(
                        f"{path}:{line} {node.name}() 의 {kind}에서 쓰는 '{name}' 이"
                        f" 모듈 최상위에 없다 (import 누락 가능)"
                    )
                elif at > node.lineno:
                    problems.append(
                        f"{path}:{line} {node.name}() 의 {kind}에서 쓰는 '{name}' 이"
                        f" {at}행에 정의된다 — 정의보다 먼저 쓰이므로"
                        f" 임포트할 때 NameError 가 난다"
                    )
    return problems


def collect(paths: list[str]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_dir():
            files += sorted(p.rglob("*.py"))
        elif p.is_file():
            files.append(p)
        else:
            raise SystemExit(f"경로가 없다: {p}")
    return [f for f in files if "__pycache__" not in f.parts]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="최상위 기본값·데코레이터의 정방향 참조를 잡는다 (import 없이)")
    parser.add_argument("paths", nargs="+", help="파일 또는 폴더")
    args = parser.parse_args()

    files = collect(args.paths)
    problems: list[str] = []
    for path in files:
        problems += check_file(path)

    print(f"검사한 파일 {len(files)}개")
    print("=" * 66)
    if problems:
        for p in problems:
            print("  실패", p)
        print()
        print(f"실패 {len(problems)}건")
        sys.exit(1)
    print("  문제 없음")
    print()
    print("  참고 — 이 검사는 정의 순서만 본다. import 실패 · 순환 import ·")
    print("  타입 오류는 잡지 못한다. 컨테이너에서 실제로 띄워 확인하는 편이 확실하다.")


if __name__ == "__main__":
    main()
