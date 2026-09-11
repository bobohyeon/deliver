# =============================================================================
# 이 파일의 책임: AmountItem 모델과 리비전 0015 가 실제로 동작하는지 확인한다.
#   모델을 만들 때 문법과 스키마 대조만 했고 한 번도 INSERT·SELECT 해 보지
#   않았다. 특히 CHECK 제약이 잘못된 값을 실제로 거부하는지 확인해야 한다 —
#   제약을 선언해 두고 동작하지 않으면 없는 것과 같다.
#
#   확인 항목
#     1. 모델로 조회가 되는가 (관계 · 프로퍼티 포함)
#     2. line_total 프로퍼티가 DB 계산과 같은가
#     3. ck_amount_unit_price 가 음수 단가를 거부하는가
#     4. ck_amount_category 가 목록 밖 값을 거부하는가
#     5. ck_amount_decision 이 목록 밖 값을 거부하는가
#     6. nullable 컬럼에 NULL 을 넣을 수 있는가 (비율 산정 항목)
#
# 다른 파일과의 관계: 도구/seed_amount_test.sql 이 먼저 실행되어 있어야 한다.
#   Tasqra 의 app/models/amount.py 를 검사한다.
# Spring 비교: @DataJpaTest 로 엔티티 매핑과 제약을 확인하는 것에 해당한다.
#   여기서는 실제 컨테이너의 DB 를 쓰므로 통합 테스트에 가깝다.
#
# 실행 방법 (PowerShell, Tasqra 폴더에서)
#   docker compose cp C:\dev\deliver\도구\check_amount_model.py api:/tmp/am.py
#   docker compose exec api python /tmp/am.py
# =============================================================================

import sys

sys.path.insert(0, "/app")

from decimal import Decimal  # noqa: E402

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.amount import AmountItem  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASS.append(name)
        print(f"  OK   {name}" + (f" — {detail}" if detail else ""))
        return
    FAIL.append(name + (f" — {detail}" if detail else ""))
    print(f"  실패 {name}" + (f" — {detail}" if detail else ""))


def expect_rejected(db, name: str, sql: str, params: dict) -> None:
    """제약이 거부해야 하는 INSERT. 통과하면 제약이 동작하지 않는 것이다."""
    savepoint = db.begin_nested()
    try:
        db.execute(text(sql), params)
        db.flush()
        savepoint.rollback()
        check(name, False, "거부되지 않았다 — 제약이 동작하지 않는다")
    except IntegrityError as exc:
        savepoint.rollback()
        message = str(exc.orig).split("\n")[0][:70]
        check(name, True, message)
    except Exception as exc:  # noqa: BLE001
        savepoint.rollback()
        check(name, False, f"예상 못 한 오류 {type(exc).__name__}: {exc}")


def main() -> None:
    with SessionLocal() as db:
        print("=" * 74)
        print("1. 모델로 조회")
        print("=" * 74)

        items = list(db.execute(select(AmountItem).order_by(AmountItem.id)).scalars())
        check("금액 항목이 있다", bool(items), f"{len(items)}건")
        if not items:
            raise SystemExit("seed_amount_test.sql 을 먼저 돌려라.")

        by_name: dict[str, list[AmountItem]] = {}
        for item in items:
            by_name.setdefault(item.item_name, []).append(item)

        print(f"\n  항목별 건수: "
              + " · ".join(f"{k} {len(v)}" for k, v in sorted(by_name.items())))

        # 관계가 실제로 로딩되는가
        first = items[0]
        check("document 관계가 로딩된다", first.document is not None,
              getattr(first.document, "filename", "?"))
        check("analysis 관계가 로딩된다", first.analysis is not None,
              getattr(first.analysis, "analyzer_type", "?"))
        check("is_pending 프로퍼티", first.is_pending is True, f"decision={first.decision}")

        print()
        print("=" * 74)
        print("2. line_total 프로퍼티 vs DB 계산")
        print("=" * 74)
        mismatch = []
        for item in items:
            db_value = db.execute(
                text("SELECT quantity * unit_price FROM amount_items WHERE id = :i"),
                {"i": item.id},
            ).scalar()
            if item.line_total != db_value:
                mismatch.append((item.item_name, item.line_total, db_value))
        check("line_total 이 DB 계산과 같다", not mismatch, str(mismatch[:2]))

        ratio_items = [i for i in items if i.unit_price is None]
        check("비율 산정 항목은 line_total 이 None",
              all(i.line_total is None for i in ratio_items),
              f"{len(ratio_items)}건 (제경비·기술료·부가세)")

        # 일부러 심어 둔 불일치를 잡는가
        planted = [i for i in items
                   if i.item_name == "중급기술자" and i.line_total is not None
                   and i.line_total != i.amount]
        check("심어 둔 검산 불일치를 찾았다", len(planted) == 1,
              f"차이 {planted[0].line_total - planted[0].amount:,}" if planted else "못 찾음")

        print()
        print("=" * 74)
        print("3. CHECK 제약이 잘못된 값을 거부하는가")
        print("=" * 74)
        base = ("INSERT INTO amount_items (document_id, analysis_id, item_name, "
                "reason, source_text_revision, {col}) VALUES "
                "(:doc, :ana, '제약시험', '제약이 거부해야 한다', 1, {val})")
        args = {"doc": first.document_id, "ana": first.analysis_id}

        expect_rejected(db, "ck_amount_unit_price — 음수 단가를 거부",
                        base.format(col="unit_price", val="-1"), args)
        expect_rejected(db, "ck_amount_category — 목록 밖 값을 거부",
                        base.format(col="category", val="'NOT_A_CATEGORY'"), args)
        expect_rejected(db, "ck_amount_decision — 목록 밖 값을 거부",
                        base.format(col="decision", val="'MAYBE'"), args)
        expect_rejected(db, "ck_amount_period — period_from > period_to 를 거부",
                        base.format(col="period_from, period_to",
                                    val="'2026-12-31', '2026-01-01'"), args)

        print()
        print("=" * 74)
        print("4. 허용되어야 하는 값은 통과하는가")
        print("=" * 74)
        savepoint = db.begin_nested()
        try:
            row = AmountItem(
                document_id=first.document_id, analysis_id=first.analysis_id,
                item_name="허용시험", reason="비율 산정 항목처럼 수량·단가가 없다",
                source_text_revision=1,
                # nullable 컬럼을 전부 비운다
                category=None, quantity=None, unit=None, unit_price=None, amount=None,
            )
            db.add(row)
            db.flush()
            check("수량·단가·원가구분이 NULL 이어도 저장된다", True,
                  f"id={row.id} · line_total={row.line_total}")
            check("currency 기본값이 KRW", row.currency == "KRW", str(row.currency))
            check("decision 기본값이 PENDING", row.decision == "PENDING", str(row.decision))
            savepoint.rollback()
        except Exception as exc:  # noqa: BLE001
            savepoint.rollback()
            check("nullable 컬럼 저장", False, f"{type(exc).__name__}: {exc}")

        savepoint = db.begin_nested()
        try:
            db.execute(text(base.format(col="unit_price", val="0")), args)
            db.flush()
            check("단가 0 은 허용된다 (무상 제공 항목)", True)
            savepoint.rollback()
        except Exception as exc:  # noqa: BLE001
            savepoint.rollback()
            check("단가 0 허용", False, f"{type(exc).__name__}: {exc}")

        print()
        print("=" * 74)
        print("5. 같은 항목의 프로젝트별 단가 (SRH-002-3 의 재료)")
        print("=" * 74)
        rows = db.execute(text("""
            SELECT ai.item_name, p.name, ai.unit_price
            FROM amount_items ai
            JOIN documents d ON d.id = ai.document_id
            JOIN projects p ON p.id = d.project_id
            WHERE ai.unit_price IS NOT NULL
            ORDER BY ai.item_name, ai.unit_price DESC
        """)).all()
        for name, project, price in rows:
            print(f"  {name:<10} {project[:28]:<30} {int(price):>12,}")
        names = {r[0] for r in rows}
        multi = [n for n in names
                 if len({r[1] for r in rows if r[0] == n}) > 1]
        check("두 프로젝트에 걸친 항목이 있다 (단가 비교가 성립)", bool(multi),
              f"{sorted(multi)}")

        db.rollback()  # 시험용 INSERT 를 남기지 않는다

    print()
    print("=" * 74)
    if FAIL:
        print(f"  실패 {len(FAIL)}건 · 통과 {len(PASS)}건\n")
        for line in FAIL:
            print("  x " + line)
        raise SystemExit(1)
    print(f"  통과 {len(PASS)}건 — AmountItem 모델과 리비전 0015 가 동작한다")


if __name__ == "__main__":
    main()
