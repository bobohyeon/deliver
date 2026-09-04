# =============================================================================
# 이 파일의 책임: 대시보드 지표(DSH-001)가 숫자를 옳게 접는지, 그리고 "조용히
#   틀릴 수 있는" 지점들이 그대로 있는지 검사한다.
#
#   왜 필요한가
#     대시보드는 틀려도 에러가 나지 않는다. 화면에 숫자가 뜨고 모양도 정상이다.
#     실제로 이 작업 전에는 문서가 21건 이상인 프로젝트에서 카드 숫자가 틀렸다
#     (목록 첫 페이지 20건만 세고 있었다). 그런 종류의 잘못은 눈으로 못 잡는다.
#
#   무엇을 잡는가
#     (1) 집계 산술 — 상태 묶기 · 총계 · 유형 분포 정렬 (실제 함수를 실행한다)
#     (2) 없음을 0 으로 바꾸지 않는지 — open_tasks 는 null 이어야 한다
#     (3) 유형 분포에서 NULL(미분류)을 빼지 않는지
#     (4) 서버와 화면이 같은 상태 묶음을 쓰는지 (양쪽 소스를 대조한다)
#     (5) 승인 대기 조건이 ix_amount_pending 부분 인덱스와 같은지
#     (6) 의존성 정의 순서 · 라우터 등록
#
#   무엇을 못 잡는가
#     SQL 이 실제로 맞는지, 인덱스를 타는지, 권한이 걸리는지. 그건 컨테이너에서
#     실제로 띄워 봐야 한다. 이 검사는 DB 없이 확인할 수 있는 것만 본다.
#
# 다른 파일과의 관계: 도구/check_amount_precedent.py 와 같은 자리다. 다만 그것은
#   컨테이너 안에서 DB 를 붙여 돌리고, 이 검사는 소스만 읽어 **의존성이 설치되지
#   않은 환경에서도** 돌아간다. sqlalchemy·pydantic 이 없으므로
#   dashboard_service.py 를 import 하지 못한다 — 그래서 순수 함수만 잘라내
#   실행한다(도구/check_search_pure.mjs 와 같은 방식).
#
# Spring 비교: 스프링 컨텍스트를 띄우지 않고 순수 계산 로직만 단위 테스트하는
#   것에 해당한다. enums.py 는 표준 라이브러리만 쓰므로 실제 값을 그대로 읽어
#   쓴다 — 상태 문자열을 검사기에 복사해 두면 그쪽이 바뀔 때 검사가 거짓으로
#   통과한다.
#
# 사용법
#   python check_dashboard.py
#   python check_dashboard.py --backend C:\dev\Tesqra\Tasqra\backend
#                             --frontend C:\dev\Tesqra\Tasqra\frontend
# =============================================================================

from __future__ import annotations

import argparse
import ast
import importlib.util
import pathlib
import re
import sys

FAILURES: list[str] = []
PASSED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}{(' — ' + detail) if detail else ''}")


def equal(name: str, actual: object, expected: object) -> None:
    check(name, actual == expected, f"기대 {expected!r} 실제 {actual!r}")


# --- 소스에서 순수 함수만 잘라내 실행 ----------------------------------------


def load_enums(backend: pathlib.Path):
    """app/models/enums.py 를 파일 경로로 직접 불러온다.

    표준 라이브러리(enum)만 쓰므로 패키지 import 없이 로드된다. 상태 문자열을
    이 검사기에 적어 두지 않는 것이 요점이다 — 적어 두면 enums.py 가 바뀔 때
    검사가 옛 값으로 통과해 버린다.
    """
    path = backend / "app" / "models" / "enums.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_tasqra_enums", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PURE_NAMES = (
    "PROCESSING_STATUSES",
    "REVIEW_PENDING_STATUSES",
    "document_counts",
    "review_pending_count",
    "_sum_of",
    "sort_type_rows",
)


def load_pure(backend: pathlib.Path, enums) -> dict:
    """dashboard_service.py 에서 순수 이름들만 뽑아 실행한다.

    모듈 전체를 import 하면 sqlalchemy·pydantic 이 없어 실패한다. 그래서 ast 로
    해당 정의만 골라 새 이름공간에서 컴파일한다. 소스를 그대로 실행하므로
    "검사기가 흉내낸 로직" 이 아니라 실제 코드가 검사된다.
    """
    path = backend / "app" / "services" / "dashboard_service.py"
    if not path.exists():
        FAILURES.append(f"파일이 없다: {path}")
        return {}
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    wanted: list[ast.stmt] = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in PURE_NAMES:
            wanted.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in PURE_NAMES:
                    wanted.append(node)
                    found.add(target.id)

    missing = set(PURE_NAMES) - found
    check(
        "dashboard_service.py 에 순수 집계 함수가 모두 있다",
        not missing,
        f"못 찾은 이름: {sorted(missing)}",
    )
    if missing:
        return {}

    namespace: dict = {
        "DocumentStatus": enums.DocumentStatus,
        "ReviewStatus": enums.ReviewStatus,
    }
    module = ast.Module(body=wanted, type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)  # noqa: S102
    return namespace


# --- (1) 집계 산술 -----------------------------------------------------------


def check_arithmetic(pure: dict, enums) -> None:
    if not pure:
        return
    document_counts = pure["document_counts"]
    review_pending_count = pure["review_pending_count"]
    sort_type_rows = pure["sort_type_rows"]
    status = enums.DocumentStatus
    review = enums.ReviewStatus

    # 문서가 하나도 없는 프로젝트. 전부 0 이어야 하고 None 이 나오면 안 된다.
    empty = document_counts({})
    equal("빈 프로젝트 총계 0", empty["total"], 0)
    equal("빈 프로젝트 처리 중 0", empty["processing"], 0)
    equal("빈 프로젝트 실패 0", empty["failed"], 0)
    check(
        "빈 프로젝트에서 None 이 아니라 0 이 나온다",
        all(value == 0 for value in empty.values()),
        f"{empty}",
    )

    # 상태별로 하나씩. 묶음이 정확히 나뉘는지.
    spread = {
        status.PENDING.value: 1,
        status.EXTRACTING.value: 2,
        status.EXTRACTED.value: 4,
        status.ANALYZING.value: 8,
        status.COMPLETED.value: 16,
        status.FAILED.value: 32,
    }
    counts = document_counts(spread)
    equal("총계는 모든 상태의 합", counts["total"], 63)
    equal("처리 중 = PENDING+EXTRACTING+ANALYZING", counts["processing"], 1 + 2 + 8)
    equal("추출 완료는 처리 중에 들어가지 않는다", counts["extracted"], 4)
    equal("처리 완료", counts["completed"], 16)
    equal("처리 실패는 따로 센다", counts["failed"], 32)
    check(
        "실패가 처리 중에 섞이지 않는다",
        counts["processing"] == 11,
        f"processing={counts['processing']}",
    )

    # 모르는 상태가 와도 총계는 맞아야 한다. enums 에 상태가 추가되고 이 파일이
    # 안 고쳐지는 상황을 흉내낸 것이다.
    with_unknown = document_counts({status.COMPLETED.value: 3, "SOMETHING_NEW": 5})
    equal("모르는 상태도 총계에 들어간다", with_unknown["total"], 8)
    equal("모르는 상태는 묶음에는 안 들어간다", with_unknown["processing"], 0)

    # OCR 검수 대기.
    equal(
        "검수 대기 = PENDING+IN_PROGRESS",
        review_pending_count(
            {
                review.NOT_REQUIRED.value: 100,
                review.PENDING.value: 3,
                review.IN_PROGRESS.value: 4,
                review.COMPLETED.value: 200,
            }
        ),
        7,
    )
    equal("검수 대기 빈 분포", review_pending_count({}), 0)

    # 유형 분포 정렬 — 많은 것부터, 미분류(None)는 맨 끝.
    rows = [("ETC", 1), (None, 99), ("RFP", 5), ("CONTRACT", 5), ("COST_SHEET", 7)]
    ordered = sort_type_rows(rows)
    equal(
        "유형 분포는 많은 순서 · 동수는 이름순 · 미분류는 맨 끝",
        ordered,
        [("COST_SHEET", 7), ("CONTRACT", 5), ("RFP", 5), ("ETC", 1), (None, 99)],
    )
    check(
        "미분류가 건수가 많아도 맨 끝이다",
        ordered[-1][0] is None,
        f"마지막={ordered[-1]!r}",
    )
    equal("유형 분포 빈 입력", sort_type_rows([]), [])
    # 정렬이 항목을 잃거나 만들지 않는지.
    equal("정렬이 칸 수를 바꾸지 않는다", len(ordered), len(rows))
    equal(
        "정렬이 합계를 바꾸지 않는다",
        sum(count for _, count in ordered),
        sum(count for _, count in rows),
    )

    # 유형 분포의 합 = 문서 수. 미분류를 빼면 이것이 깨진다.
    total_docs = document_counts({status.COMPLETED.value: 111})["total"]
    type_rows = [("RFP", 100), (None, 11)]
    equal(
        "유형 분포 합이 문서 수와 같다 (미분류 포함이라 성립)",
        sum(count for _, count in sort_type_rows(type_rows)),
        total_docs,
    )


# --- (2)~(6) 소스 대조 -------------------------------------------------------


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def check_sources(backend: pathlib.Path, frontend: pathlib.Path, pure: dict) -> None:
    schema = read(backend / "app" / "schemas" / "dashboard.py")
    repo = read(backend / "app" / "repositories" / "dashboard_repository.py")
    amount_model = read(backend / "app" / "models" / "amount.py")
    deps = read(backend / "app" / "dependencies.py")
    main = read(backend / "app" / "main.py")
    router = read(backend / "app" / "api" / "routes" / "dashboard_router.py")
    view = read(frontend / "src" / "features" / "dashboard" / "DashboardView.jsx")
    status_util = read(frontend / "src" / "utils" / "documentStatus.js")
    api = read(frontend / "src" / "api" / "dashboard.js")

    # (2) 없음을 0 으로 바꾸지 않는다.
    check(
        "open_tasks 가 int | None 이고 기본값이 None 이다",
        re.search(r"open_tasks:\s*int\s*\|\s*None\s*=\s*None", schema) is not None,
        "스키마에서 open_tasks 선언을 찾지 못했다",
    )
    check(
        "서비스가 open_tasks 를 채우지 않는다 (기본값 None 을 그대로 둔다)",
        "open_tasks=" not in read(backend / "app" / "services" / "dashboard_service.py"),
        "서비스가 open_tasks 에 값을 넣고 있다 — 모델이 생겼다면 이 검사를 고쳐라",
    )
    check(
        "화면이 open_tasks 의 null 을 0 으로 바꾸지 않는다",
        not re.search(r"open_tasks\s*\?\?\s*0", view),
        "open_tasks ?? 0 이 있다 — '할 일 없음' 으로 잘못 읽힌다",
    )
    check(
        "화면이 값 없음을 0 과 구별해 표시한다",
        "'—'" in view or '"—"' in view,
        "값이 없을 때 쓸 표시(—)를 찾지 못했다",
    )

    # (3) 유형 분포에서 미분류를 빼지 않는다.
    type_query = re.search(
        r"def count_documents_by_type.*?(?=\n    def |\Z)", repo, re.S
    )
    check("count_documents_by_type 이 있다", type_query is not None)
    if type_query:
        body = type_query.group(0)
        check(
            "유형 분포가 NULL(미분류)을 걸러내지 않는다",
            "isnot(None)" not in body and "is_not(None)" not in body,
            "document_type IS NOT NULL 필터가 생겼다 — 분포 합이 문서 수와 안 맞게 된다",
        )
        check(
            "유형 분포도 project_id 로 격리한다",
            "Document.project_id == project_id" in body,
            "프로젝트 격리 조건이 없다",
        )

    # 모든 조회가 project_id 로 격리되는지 (격리가 깨지면 남의 프로젝트가 섞인다)
    for method in (
        "count_documents_by_status",
        "count_documents_by_review_status",
        "count_documents_by_type",
        "list_recent_documents",
        "count_pending_amount_items",
    ):
        body_match = re.search(rf"def {method}\(.*?(?=\n    def |\Z)", repo, re.S)
        check(
            f"{method} 이 project_id 로 격리한다",
            body_match is not None
            and "Document.project_id == project_id" in body_match.group(0),
            "격리 조건을 찾지 못했다",
        )

    # 최근 문서 정렬이 안정적인지 (created_at 만으로는 순서가 흔들린다)
    recent = re.search(r"def list_recent_documents.*?(?=\n    def |\Z)", repo, re.S)
    if recent:
        check(
            "최근 문서 정렬에 id 보조 정렬이 있다",
            "Document.id.desc()" in recent.group(0),
            "created_at 만으로 정렬하면 동시 삽입 시 순서가 실행마다 달라진다",
        )

    # (4) 서버와 화면이 같은 상태 묶음을 쓴다.
    if pure:
        frontend_processing = re.search(
            r"\[([^\]]*?)\]\s*\.includes\(document\?\.status\)", status_util
        )
        check(
            "화면에서 '처리 중' 상태 목록을 찾았다",
            frontend_processing is not None,
            "utils/documentStatus.js 에서 상태 배열을 찾지 못했다",
        )
        if frontend_processing:
            shown = tuple(
                value.strip().strip("'\"")
                for value in frontend_processing.group(1).split(",")
                if value.strip()
            )
            equal(
                "서버 PROCESSING_STATUSES 와 화면의 처리 중 목록이 같다",
                sorted(shown),
                sorted(pure["PROCESSING_STATUSES"]),
            )

        review_used = re.findall(
            r"\[([^\]]*?)\]\s*\.includes\((?:document|item)\?*\.review_status\)",
            status_util + view,
        )
        check(
            "화면에서 검수 대기 상태 목록을 찾았다",
            bool(review_used),
            "review_status 배열을 찾지 못했다",
        )
        for group in review_used:
            shown = tuple(
                value.strip().strip("'\"")
                for value in group.split(",")
                if value.strip()
            )
            equal(
                "서버 REVIEW_PENDING_STATUSES 와 화면의 검수 대기 목록이 같다",
                sorted(shown),
                sorted(pure["REVIEW_PENDING_STATUSES"]),
            )

    # (5) 승인 대기 조건이 부분 인덱스와 같다.
    index_condition = re.search(
        r'ix_amount_pending[^)]*?postgresql_where=text\(\s*"decision = \'(\w+)\'\s*"\s*\)',
        amount_model,
        re.S,
    )
    check(
        "amount.py 에서 ix_amount_pending 조건을 찾았다",
        index_condition is not None,
        "부분 인덱스 정의를 찾지 못했다",
    )
    repo_decision = re.search(r'PENDING_DECISION\s*=\s*"(\w+)"', repo)
    check("리포지토리에 PENDING_DECISION 상수가 있다", repo_decision is not None)
    if index_condition and repo_decision:
        equal(
            "승인 대기 조건이 ix_amount_pending 부분 인덱스와 같다",
            repo_decision.group(1),
            index_condition.group(1),
        )
    check(
        "승인 대기를 세는 이름이 대상을 밝히고 있다",
        "pending_amount_items" in schema,
        "pending_suggestions 처럼 뭉뚱그리면 decisions·schedule_items 가 이미 세어진 것으로 오해된다",
    )

    # (6) 의존성 정의 순서 · 라우터 등록.
    repo_at = deps.find("def get_dashboard_repository(")
    service_at = deps.find("def get_dashboard_service(")
    check("get_dashboard_repository 가 정의돼 있다", repo_at != -1)
    check("get_dashboard_service 가 정의돼 있다", service_at != -1)
    if repo_at != -1 and service_at != -1:
        check(
            "get_dashboard_repository 가 get_dashboard_service 보다 위에 있다",
            repo_at < service_at,
            "Depends 기본값은 정의 시점에 평가된다 — 순서가 뒤면 NameError 로 앱이 안 뜬다",
        )
    check(
        "main.py 가 dashboard_router 를 등록한다",
        "dashboard_router" in main and "include_router(dashboard_router.router)" in main,
        "라우터를 등록하지 않으면 404 가 난다",
    )
    check(
        "라우터가 프로젝트 하위 경로에 있다",
        'prefix="/api/projects/{project_id}"' in router,
        "get_project_access 가 경로의 project_id 를 읽으므로 prefix 에 있어야 한다",
    )
    check(
        "라우터가 멤버 권한(get_project_access)을 요구한다",
        "get_project_access" in router,
        "권한 의존성이 없으면 남의 프로젝트 현황이 보인다",
    )
    check(
        "화면이 서버 집계를 부른다",
        "getDashboard" in view and "/dashboard" in api,
        "api/dashboard.js 연결을 찾지 못했다",
    )
    # 화면에서 지표를 다시 세는 코드가 돌아오지 않게 막는다.
    #
    # 정규식으로 괄호 안을 훑으려 하면 includes(d.status) 처럼 괄호가 겹칠 때
    # 놓친다(실제로 처음에 그렇게 써서 이 검사가 거짓으로 통과했다). 그래서
    # 줄 단위로 세 조건이 한 줄에 같이 있는지만 본다 — 세는 코드는 한 줄로
    # 쓰이기 때문이다.
    #
    # documents 를 filter 하는 것 자체는 막지 않는다. "OCR 확인 필요" 목록의
    # 항목을 고르는 데 쓰고 있고 그건 세는 것이 아니다. .length 까지 붙어
    # 숫자가 되는 경우만 걸러낸다.
    recount = [
        line.strip()
        for line in view.splitlines()
        if "documents.filter(" in line and ".length" in line and "status" in line
    ]
    check(
        "화면이 지표를 documents.filter(...).length 로 다시 세지 않는다",
        not recount,
        f"화면에서 세면 목록 첫 페이지(20건)만 세는 문제가 되돌아온다: {recount[:1]}",
    )


def main() -> int:
    here = pathlib.Path(__file__).resolve()
    guess = here.parent.parent.parent / "Tasqra"
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=str(guess / "backend"))
    parser.add_argument("--frontend", default=str(guess / "frontend"))
    args = parser.parse_args()

    backend = pathlib.Path(args.backend)
    frontend = pathlib.Path(args.frontend)
    if not backend.exists():
        print(f"backend 경로가 없다: {backend}")
        print("--backend 로 지정하라.")
        return 2

    enums = load_enums(backend)
    if enums is None:
        print("app/models/enums.py 를 찾지 못했다.")
        return 2

    pure = load_pure(backend, enums)
    check_arithmetic(pure, enums)
    check_sources(backend, frontend, pure)

    print(f"검사 {PASSED + len(FAILURES)}건")
    print("=" * 66)
    for failure in FAILURES:
        print(f"  실패 {failure}")
    if FAILURES:
        print(f"\n실패 {len(FAILURES)}건")
        return 1
    print("  문제 없음")
    print()
    print("  참고 — 이 검사는 DB 를 붙이지 않는다. SQL 이 실제로 맞는지 · 인덱스를")
    print("  타는지 · 권한이 걸리는지는 컨테이너에서 확인해야 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
