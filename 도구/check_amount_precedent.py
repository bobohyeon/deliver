# =============================================================================
# 이 파일의 책임: 과거 유사 사업 단가 선례 조회(SRH-002-3)를 실제 DB 로 검증한다.
#   HTTP 를 거치지 않고 AmountPrecedentService 를 직접 부른다 — 로그인 토큰이
#   없어도 되고, 실패했을 때 어느 계층 문제인지 바로 보인다.
#   test_search_in_container.py 와 같은 방식이다.
#
#   검증 항목
#     1. 현재 프로젝트가 결과에서 빠지는가 (이 기능의 핵심)
#     2. 내가 멤버가 아닌 프로젝트가 절대 나오지 않는가 (격리)
#     3. 승인 안 된 항목(PENDING)이 선례로 쓰이지 않는가 (AMT-001-2 원칙)
#     4. 단가가 없는 항목(제경비·기술료·부가세)이 빠지는가
#     5. 중앙값·최소·최대가 맞는가
#     6. 완전일치가 부분일치보다 앞에 오는가
#     7. 없는 항목명은 빈 결과 + summary=None 인가
#
# 다른 파일과의 관계: 도구/seed_rag_test.sql 과 seed_amount_test.sql 이 먼저
#   실행되어 있어야 한다.
#
# 실행 방법 (PowerShell, Tasqra 폴더에서)
#   docker compose cp C:\dev\deliver\도구\check_amount_precedent.py api:/tmp/ap.py
#   docker compose exec api python /tmp/ap.py
# =============================================================================

import sys

sys.path.insert(0, "/app")

from decimal import Decimal  # noqa: E402

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.amount_repository import AmountRepository  # noqa: E402
from app.repositories.project_repository import ProjectRepository  # noqa: E402
from app.services.amount_precedent_service import AmountPrecedentService, median  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASS.append(name)
        print(f"  OK   {name}" + (f" — {detail}" if detail else ""))
        return
    FAIL.append(name + (f" — {detail}" if detail else ""))
    print(f"  실패 {name}" + (f" — {detail}" if detail else ""))


def main() -> None:
    with SessionLocal() as db:
        user_id = db.execute(
            text("SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1")
        ).scalar()
        if user_id is None:
            raise SystemExit("사용자가 없다. seed_rag_test.sql 을 먼저 돌려라.")

        rows = db.execute(text("""
            SELECT p.id, p.name,
                   count(ai.id) FILTER (WHERE ai.decision IN ('APPROVED','EDITED')) AS 승인,
                   count(ai.id) FILTER (WHERE ai.decision = 'PENDING') AS 대기
            FROM projects p
            LEFT JOIN documents d ON d.project_id = p.id
            LEFT JOIN amount_items ai ON ai.document_id = d.id
            WHERE p.name LIKE '[TEST]%'
            GROUP BY p.id, p.name ORDER BY p.id
        """)).all()
        print("=" * 74)
        print("0. 전제 — 프로젝트별 금액 항목")
        print("=" * 74)
        for pid, name, approved, pending in rows:
            print(f"  프로젝트 {pid}  {name[:34]:<36} 승인 {approved} · 대기 {pending}")

        my_ids = [
            p.id for p, _m in ProjectRepository(db).list_for_user(user_id)
        ]
        others = [pid for pid, *_ in rows if pid not in my_ids]
        check("내 멤버십과 남의 프로젝트가 구분된다",
              bool(my_ids) and bool(others), f"내 것 {my_ids} · 남의 것 {others}")

        service = AmountPrecedentService(db, AmountRepository(db), ProjectRepository(db))

        # 현재 사업 = 내 멤버십 중 PENDING 자료가 있는 쪽. my_ids[0] 으로 두면
        # list_for_user 의 정렬 순서에 의존하게 되어, 순서가 바뀌면 검사의 전제가
        # 조용히 뒤집힌다. 데이터에서 찾는다.
        pending_projects = [pid for pid, _n, _a, pending in rows if pending > 0]
        approved_projects = [
            pid for pid, _n, approved, _p in rows if approved > 0 and pid in my_ids
        ]
        check("PENDING 자료가 있는 프로젝트를 찾았다", bool(pending_projects),
              str(pending_projects))
        check("승인 자료가 있는 내 프로젝트를 찾았다", bool(approved_projects),
              str(approved_projects))
        if not pending_projects or not approved_projects:
            raise SystemExit("seed_amount_test.sql 을 먼저 돌려라.")
        current = pending_projects[0]
        other_mine = [pid for pid in approved_projects if pid != current]

        print()
        print("=" * 74)
        print(f"1. 현재 프로젝트 {current} 에서 '특급기술자' 선례 조회")
        print("=" * 74)
        res = service.find_precedents(
            user_id=user_id, current_project_id=current, item_name="특급기술자", limit=20
        )
        print(f"  범위 = {res.searched_project_ids}")
        for p in res.precedents:
            print(f"    프로젝트{p.project_id} {p.project_name[:22]:<24} "
                  f"{p.item_name} {int(p.unit_price):>12,} ({p.decision})")
        if res.summary:
            s = res.summary
            print(f"  요약: {s.count}건 · 최소 {int(s.min_unit_price):,} · "
                  f"중앙 {int(s.median_unit_price):,} · 최대 {int(s.max_unit_price):,}")

        found_projects = {p.project_id for p in res.precedents}
        check("현재 프로젝트가 범위에서 빠졌다", current not in res.searched_project_ids)
        check("현재 프로젝트 항목이 결과에 없다", current not in found_projects,
              f"나온 프로젝트 {sorted(found_projects)}")
        check("내가 멤버가 아닌 프로젝트가 없다",
              not (found_projects & set(others)), f"침입 {sorted(found_projects & set(others))}")
        # 격리가 깨지면 99,000,000 이 보인다 (시드가 그렇게 심어 뒀다)
        check("격리 표식(99,000,000)이 나오지 않았다",
              all(p.unit_price != Decimal("99000000") for p in res.precedents))
        check("선례가 있다", bool(res.precedents), f"{len(res.precedents)}건")
        check("단가가 없는 항목은 빠졌다",
              all(p.unit_price is not None for p in res.precedents))

        print()
        print("=" * 74)
        print("2. 승인 안 된 항목(PENDING)은 선례가 아니다")
        print("=" * 74)
        check("결과에 PENDING 이 없다",
              all(p.decision in ("APPROVED", "EDITED") for p in res.precedents),
              f"상태 {sorted({p.decision for p in res.precedents})}")
        # 반대편에서 조회하면 현재 사업(PENDING)이 범위에 들어가지만 결과에는
        # 나오지 않아야 한다. 승인 필터가 진짜로 걸리는지 보는 것이다.
        if other_mine:
            reverse = service.find_precedents(
                user_id=user_id, current_project_id=other_mine[0],
                item_name="특급기술자", limit=20,
            )
            print(f"  프로젝트 {other_mine[0]} 에서 조회 -> 범위 {reverse.searched_project_ids} · "
                  f"결과 {len(reverse.precedents)}건")
            check("PENDING 만 있는 프로젝트는 범위에 있어도 결과가 비었다",
                  current in reverse.searched_project_ids and not reverse.precedents,
                  f"결과 {[(p.project_id, p.decision) for p in reverse.precedents]}")

        print()
        print("=" * 74)
        print("3. 요약값이 맞는가")
        print("=" * 74)
        if res.precedents:
            prices = [p.unit_price for p in res.precedents]
            check("count", res.summary.count == len(prices))
            check("min", res.summary.min_unit_price == min(prices), str(min(prices)))
            check("max", res.summary.max_unit_price == max(prices), str(max(prices)))
            check("median", res.summary.median_unit_price == median(prices),
                  str(median(prices)))

        print()
        print("=" * 74)
        print("4. 완전일치가 부분일치보다 앞에 오는가")
        print("=" * 74)
        partial = service.find_precedents(
            user_id=user_id, current_project_id=current, item_name="기술자", limit=20
        )
        names = [p.item_name for p in partial.precedents]
        print(f"  '기술자' 로 조회 -> {names}")
        check("부분일치로 여러 항목이 걸린다", len(set(names)) >= 2, f"{sorted(set(names))}")

        exact = service.find_precedents(
            user_id=user_id, current_project_id=current, item_name="중급기술자", limit=20
        )
        first = exact.precedents[0].item_name if exact.precedents else None
        check("완전일치가 1위다", first == "중급기술자", f"1위 {first}")

        print()
        print("=" * 74)
        print("5. 없는 항목명")
        print("=" * 74)
        empty = service.find_precedents(
            user_id=user_id, current_project_id=current,
            item_name="존재하지않는항목명XYZ", limit=20,
        )
        check("결과가 비었다", not empty.precedents)
        check("summary 가 None 이다 (0 을 넣으면 '단가 0원'과 구별 안 됨)",
              empty.summary is None)

        db.rollback()

    print()
    print("=" * 74)
    if FAIL:
        print(f"  실패 {len(FAIL)}건 · 통과 {len(PASS)}건\n")
        for line in FAIL:
            print("  x " + line)
        raise SystemExit(1)
    print(f"  통과 {len(PASS)}건 — 단가 선례 조회(SRH-002-3)가 동작한다")


if __name__ == "__main__":
    main()
