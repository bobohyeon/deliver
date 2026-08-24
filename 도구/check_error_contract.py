# =============================================================================
# 이 파일의 책임: 오류 응답과 요청 로깅의 계약(SYS-003-1)이 지켜지는지 소스만 읽어
#   검사한다. DB·컨테이너·네트워크가 필요 없다.
#
#   완료 판정: "주요 오류가 **동일한 응답 형식**과 서버 로그에 남고
#   **요청 단위 추적**이 가능하다."
#
#   무엇을 잡는가
#     (1) 오류를 내는 방법이 하나인가 — HTTPException 직접 발생이 섞이면 응답
#         형식이 갈린다(FastAPI 기본 형식은 {"detail": ...} 라 code·request_id 가 없다)
#     (2) 전역 핸들러 3종과 요청 미들웨어가 실제로 등록됐는가
#     (3) 모든 오류 응답에 request_id 가 있는가 — 본문과 헤더 양쪽
#     (4) 핸들러가 request_id 를 안전하게 꺼내는가 — 없을 때 터지면 오류 응답 자체가 사라진다
#     (5) 요청 1건당 로그 한 줄이 있는가 — 오류가 없는 요청도 흔적이 남아야 추적이 된다
#     (6) 들어온 X-Request-ID 를 검증해서 이어받는가 — 그대로 믿으면 로그 위조가 된다
#     (7) ErrorCode 에 중복·잘못된 상태코드가 없는가
#
#   왜 도구로 만드는가
#     엔드포인트는 계속 늘어난다. 사람이 한 번 훑는 방식이면 그 뒤에 추가된
#     라우터는 점검 밖에 남는다. 검사를 코드로 두면 새 엔드포인트가 생겨도
#     이것만 다시 돌리면 된다.
#
# 다른 파일과의 관계
#   도구/check_dashboard.py  같은 방식(소스 대조)의 선행 도구
#   Tasqra backend/app/core/{middleware,exceptions,error_codes,logging_config}.py
#   Tasqra backend/app/main.py · app/schemas/error.py · app/api/routes/*.py
#
# Spring 비교: ArchUnit 으로 "컨트롤러는 예외를 직접 던지지 않는다" 같은 규칙을
#   검사하는 것에 가깝다. 실행 없이 구조만 본다.
#
# 실행 방법
#   python 도구/check_error_contract.py --root C:\dev\Tesqra\Tasqra\backend
#   (--root 를 생략하면 ../Tasqra/backend 를 찾는다)
# =============================================================================

from __future__ import annotations

import argparse
import ast
import collections
import re
import sys
from pathlib import Path

failures: list[str] = []
warnings: list[str] = []


def check(name: str, ok: bool, why: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}")
    if not ok:
        failures.append(f"{name} — {why}" if why else name)


def warn(name: str, note: str) -> None:
    print(f"  주의  {name}")
    warnings.append(f"{name} — {note}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


# --- (7) ErrorCode -----------------------------------------------------------


def check_error_codes(backend: Path) -> None:
    print("\n[ErrorCode] 코드 목록")
    source = read(backend / "app" / "core" / "error_codes.py")
    if not source:
        check("error_codes.py 가 있다", False, "파일을 찾지 못했다")
        return

    entries: list[tuple[str, str, object]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Tuple):
            continue
        elts = node.value.elts
        if len(elts) < 3:
            continue
        if not (isinstance(elts[0], ast.Constant) and isinstance(elts[0].value, str)):
            continue
        name = getattr(node.targets[0], "id", "?")
        entries.append((name, elts[0].value, getattr(elts[2], "value", None)))

    print(f"    {len(entries)}개")
    check("ErrorCode 항목을 읽었다", bool(entries), "3요소 튜플을 찾지 못했다")
    if not entries:
        return

    dup_code = [c for c, n in collections.Counter(e[1] for e in entries).items() if n > 1]
    dup_name = [n for n, c in collections.Counter(e[0] for e in entries).items() if c > 1]
    check("code 문자열이 중복되지 않는다", not dup_code, f"중복: {dup_code}")
    check("멤버 이름이 중복되지 않는다", not dup_name, f"중복: {dup_name}")

    # 이름과 code 문자열을 같게 유지한다. 다르면 로그의 code 로 정의를 못 찾는다.
    mismatched = [f"{n} != {c}" for n, c, _ in entries if n != c]
    check("멤버 이름과 code 문자열이 같다", not mismatched, f"{mismatched[:5]}")

    bad_status = [
        f"{n}={s}" for n, _, s in entries
        if not (isinstance(s, int) and 400 <= s <= 599)
    ]
    check("상태코드가 400~599 다", not bad_status, f"{bad_status[:5]}")


# --- (1) 오류를 내는 방법이 하나인가 ------------------------------------------


def check_single_error_path(backend: Path) -> None:
    print("\n[오류 발생 경로] BusinessError 하나로 모였는가")
    app_dir = backend / "app"
    offenders: list[str] = []
    raise_types: collections.Counter[str] = collections.Counter()

    for path in sorted(app_dir.rglob("*.py")):
        source = read(path)
        if not source:
            continue
        rel = path.relative_to(backend).as_posix()
        if "HTTPException" in source:
            offenders.append(rel)
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            target = call.func if isinstance(call, ast.Call) else call
            name = getattr(target, "id", None) or getattr(target, "attr", None) or "?"
            raise_types[name] += 1

    check("HTTPException 을 쓰지 않는다", not offenders, f"{offenders[:5]}")

    # 라우터에서 던지는 것은 BusinessError 여야 한다. 서비스·리포지토리는
    # 표준 예외(ValueError 등)를 쓸 수 있으므로 라우터만 좁혀 본다.
    router_offenders: list[str] = []
    for path in sorted((app_dir / "api" / "routes").glob("*.py")):
        source = read(path)
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            name = getattr(target, "id", None) or getattr(target, "attr", None) or "?"
            if name not in {"BusinessError"}:
                router_offenders.append(f"{path.name}:{node.lineno} {name}")

    check(
        "라우터는 BusinessError 만 던진다",
        not router_offenders,
        f"{router_offenders[:5]}",
    )
    top = ", ".join(f"{k} {v}" for k, v in raise_types.most_common(5))
    print(f"    app 전체 raise 종류 — {top or '없음'}")


# --- (2) 등록 ----------------------------------------------------------------


def check_registration(backend: Path) -> None:
    print("\n[등록] main.py 가 실제로 붙였는가")
    source = read(backend / "app" / "main.py")
    if not source:
        check("main.py 가 있다", False, "파일을 찾지 못했다")
        return

    check("setup_logging() 을 부른다", "setup_logging()" in source)
    check(
        "RequestIdMiddleware 를 등록한다",
        "add_middleware(RequestIdMiddleware)" in source.replace(" ", ""),
    )
    for exc_type, handler in (
        ("BusinessError", "business_error_handler"),
        ("RequestValidationError", "validation_error_handler"),
        ("Exception", "unhandled_exception_handler"),
    ):
        pattern = f"add_exception_handler({exc_type},{handler})"
        check(f"{exc_type} 핸들러를 등록한다", pattern in source.replace(" ", ""))


# --- (3)(4) 오류 응답에 request_id ------------------------------------------


def check_error_response(backend: Path) -> None:
    print("\n[오류 응답] request_id 가 본문과 헤더에 있는가")
    schema = read(backend / "app" / "schemas" / "error.py")
    check(
        "ErrorResponse 에 request_id: str 이 있다",
        re.search(r"request_id\s*:\s*str", schema) is not None,
    )

    source = read(backend / "app" / "core" / "exceptions.py")
    if not source:
        check("exceptions.py 가 있다", False, "파일을 찾지 못했다")
        return

    handlers = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name.endswith("_handler")
    ]
    print(f"    핸들러 {len(handlers)}개 — {', '.join(h.name for h in handlers)}")
    check("핸들러가 3개다", len(handlers) == 3, f"{len(handlers)}개다")

    missing_header = []
    for handler in handlers:
        body = ast.get_source_segment(source, handler) or ""
        if "REQUEST_ID_HEADER" not in body and "X-Request-ID" not in body:
            missing_header.append(handler.name)
    check(
        "모든 핸들러가 X-Request-ID 헤더를 실어 보낸다",
        not missing_header,
        f"빠짐: {missing_header}",
    )

    # 직접 접근이 남아 있으면 미들웨어 이전 예외에서 핸들러가 터진다.
    #
    # 문자열로 찾지 않고 **AST 의 속성 접근만** 센다. 주석이나 문서화 문자열에
    # 적힌 `request.state.request_id` 까지 세면, 왜 위험한지 설명해 둔 주석 때문에
    # 검사가 실패한다(실제로 그렇게 한 번 틀렸다).
    direct = [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and node.attr == "request_id"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "state"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "request"
    ]
    check(
        "request.state.request_id 를 직접 읽지 않는다",
        not direct,
        f"{len(direct)}곳이 직접 읽는다(줄 {direct[:5]}) — getattr 로 감싸야 한다",
    )
    check(
        "없을 때 쓸 기본값이 있다",
        'getattr(request.state, "request_id"' in source,
        "getattr 기본값 경로를 찾지 못했다",
    )


# --- (5)(6) 요청 로깅과 이어받기 ---------------------------------------------


def check_request_logging(backend: Path) -> None:
    print("\n[요청 로깅] 요청 1건당 흔적과 id 이어받기")
    source = read(backend / "app" / "core" / "middleware.py")
    if not source:
        check("middleware.py 가 있다", False, "파일을 찾지 못했다")
        return

    check("요청 로거를 만든다", "logging.getLogger(" in source)
    check("요청 로그를 남긴다", "logger.info(" in source)
    check(
        "상태코드를 로그에 남긴다",
        "status_code" in source,
        "요청 줄에 상태코드가 없으면 404·500 을 되짚을 수 없다",
    )
    check(
        "소요 시간을 로그에 남긴다",
        "perf_counter" in source,
        "느린 요청을 찾을 수 없다",
    )
    check(
        "미처리 예외에도 요청 줄을 남긴다",
        "except Exception" in source and "raise" in source,
        "예외가 나면 요청 흔적이 사라진다",
    )
    check(
        "들어온 X-Request-ID 를 이어받는다",
        "request.headers.get(" in source,
        "화면에서 시작한 흐름을 서버 로그에서 되짚을 수 없다",
    )
    check(
        "이어받은 값을 검증한다",
        "re.compile(" in source,
        "검증 없이 로그에 넣으면 줄바꿈으로 로그를 위조할 수 있다",
    )
    check("응답 헤더에 실어 보낸다", "REQUEST_ID_HEADER" in source)

    logging_config = read(backend / "app" / "core" / "logging_config.py")
    check(
        "로그 형식에 request_id 가 있다",
        "%(request_id)s" in logging_config,
    )
    check(
        "모든 로그에 request_id 를 주입하는 필터가 있다",
        "logging.Filter" in logging_config,
    )


# --- 남은 구멍 (실패가 아니라 주의) ------------------------------------------


def check_known_gaps(backend: Path) -> None:
    print("\n[남은 구멍] 이 도구가 통과해도 추적이 끊기는 자리")
    worker = read(backend / "app" / "worker.py") or read(
        backend / "app" / "worker" / "celery_app.py"
    )
    tasks = "".join(
        read(path) for path in sorted((backend / "app").rglob("*task*.py"))
    )
    propagated = "request_id" in worker or "request_id_ctx_var" in tasks
    if not propagated:
        warn(
            "워커(Celery)에는 request_id 가 전달되지 않는다",
            "문서 처리·색인은 워커에서 돈다. 그쪽 로그는 request_id=- 로 남아"
            " 업로드 요청과 이어붙일 수 없다. 태스크 인자에 id 를 넘겨야 하고"
            " 그 파일은 재정님 담당이라 함께 정해야 한다.",
        )

    frontend = backend.parent / "frontend" / "src" / "api" / "http.js"
    http_js = read(frontend)
    if http_js and "X-Request-ID" not in http_js:
        warn(
            "화면이 X-Request-ID 를 보내지 않는다",
            "응답을 받지 못한 요청(타임아웃)은 화면과 서버를 이어붙일 수 없다.",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="오류 응답·요청 로깅 계약 검사")
    parser.add_argument("--root", help="Tasqra backend 경로")
    args = parser.parse_args()

    backend = Path(args.root) if args.root else Path(__file__).resolve().parents[2] / "Tasqra" / "backend"
    backend = backend.resolve()
    print("=" * 78)
    print(f"오류 응답·요청 로깅 계약 검사 (SYS-003-1)  대상 {backend}")
    print("=" * 78)
    if not (backend / "app").is_dir():
        print("backend/app 을 찾지 못했다. --root 로 경로를 지정해라.")
        return 2

    check_error_codes(backend)
    check_single_error_path(backend)
    check_registration(backend)
    check_error_response(backend)
    check_request_logging(backend)
    check_known_gaps(backend)

    print("\n" + "=" * 78)
    if failures:
        print(f"실패 {len(failures)}건")
        for line in failures:
            print("  - " + line)
    else:
        print("검사 통과")
    if warnings:
        print(f"\n주의 {len(warnings)}건 — 실패는 아니지만 추적이 끊기는 자리다")
        for line in warnings:
            print("  ? " + line)
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
