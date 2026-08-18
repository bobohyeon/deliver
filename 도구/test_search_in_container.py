# =============================================================================
# 이 파일의 책임: 의미 검색(RAG-04 = SRH-001)을 실제 DB 로 검증한다.
#   HTTP 를 거치지 않고 SearchService 를 직접 부른다. 로그인 토큰이 없어도
#   되고, 실패했을 때 어느 계층 문제인지 바로 보인다.
#
#   왜 컨테이너 안에서 돌리는가: sqlalchemy · pydantic · pgvector 가 필요하다.
#   개발 샌드박스에는 없어서 문법 검사만 했다.
#
#   검증 항목
#     1. 범위 없음(None)  -> 내가 멤버인 프로젝트만. 남의 프로젝트(3)는 제외
#     2. 범위 [1]         -> 프로젝트 1 결과만
#     3. 범위 [3]         -> 404 PROJECT_NOT_FOUND (멤버가 아니다)
#     4. 범위 [1, 2]      -> 두 프로젝트가 함께
#     5. 격리            -> 어떤 경우에도 project_id=3 이 결과에 없다
#     6. document_id 지정 -> 그 문서 청크만
#     7. min_similarity  -> 임계값 아래가 잘린다
#     8. 응답 필드        -> project_name · snippet · content 구간
#     9. 실행계획         -> = 와 IN 의 계획을 나란히 출력
#
# 다른 파일과의 관계: 도구/seed_rag_test.sql 로 넣은 자료를 전제로 한다.
#   프로젝트 3개(A·B 는 내 멤버십, C 는 남의 것)와 문서 4개가 있어야 한다.
#
# 실행 방법 (PowerShell)
#   docker compose cp C:\dev\deliver\도구\test_search_in_container.py api:/tmp/t.py
#   docker compose exec api python /tmp/t.py
# =============================================================================

import sys

# 컨테이너의 앱은 /app 에 있다. /tmp 에서 실행하므로 직접 넣어 준다.
sys.path.insert(0, "/app")

from app.db.session import SessionLocal  # noqa: E402
from app.core.exceptions import BusinessError  # noqa: E402
from app.embedding.fake_client import FakeEmbeddingClient  # noqa: E402
from app.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.repositories.project_repository import ProjectRepository  # noqa: E402
from app.schemas.search import SearchRequest  # noqa: E402
from app.services.search_service import SearchService  # noqa: E402
from sqlalchemy import text  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
        print(f"  OK   {name}")
        return
    message = name + (f" — {detail}" if detail else "")
    FAIL.append(message)
    print(f"  실패 {message}")


def main() -> None:
    with SessionLocal() as db:
        # ── 전제 확인 ────────────────────────────────────────────────────────
        print("=" * 72)
        print("0. 전제 — 자료가 있는가")
        print("=" * 72)

        user_id = db.execute(
            text("SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1")
        ).scalar()
        if user_id is None:
            raise SystemExit("사용자가 없다. seed_rag_test.sql 을 먼저 돌려라.")
        print(f"  검색 주체 user_id = {user_id}")

        rows = db.execute(
            text(
                "SELECT project_id, count(*) FROM document_chunks "
                "GROUP BY 1 ORDER BY 1"
            )
        ).all()
        counts = {int(r[0]): int(r[1]) for r in rows}
        print(f"  프로젝트별 청크 = {counts}")
        if not counts:
            raise SystemExit("청크가 없다. build_chunks_task 를 먼저 돌려라.")

        member_ids = sorted(
            int(r[0])
            for r in db.execute(
                text("SELECT project_id FROM project_members WHERE user_id = :u"),
                {"u": user_id},
            ).all()
        )
        print(f"  내 멤버십 프로젝트 = {member_ids}")

        outsider = sorted(set(counts) - set(member_ids))
        print(f"  내 멤버십이 아닌데 청크가 있는 프로젝트 = {outsider}")
        if not outsider:
            print()
            print("  ⚠ 격리를 검증할 수 없다. 남의 프로젝트에 청크가 없다.")
            print("    seed_rag_test.sql 의 프로젝트 C 를 청킹했는지 확인하라:")
            print("    build_chunks_task.apply(args=[3, 4])")

        service = SearchService(
            db=db,
            chunk_repository=ChunkRepository(db),
            project_repository=ProjectRepository(db),
            embedding_client=FakeEmbeddingClient(),
        )

        # ── 1. 범위 없음 = 내 멤버십 전체 ────────────────────────────────────
        print()
        print("=" * 72)
        print("1. project_ids = None -> 내가 멤버인 전체")
        print("=" * 72)
        res = service.search(user_id, SearchRequest(query="대금은 언제 주나요", limit=50))
        print(f"  searched_project_ids = {res.searched_project_ids}")
        print(f"  결과 {res.total}건 · 모델 {res.embedding_model} · {res.took_ms}ms")
        check("범위가 내 멤버십과 같다", res.searched_project_ids == member_ids,
              f"{res.searched_project_ids} != {member_ids}")
        got = sorted({r.project_id for r in res.results})
        check("결과 프로젝트가 멤버십 안에 있다", set(got) <= set(member_ids), f"결과={got}")
        for pid in outsider:
            check(f"남의 프로젝트 {pid} 가 결과에 없다",
                  all(r.project_id != pid for r in res.results),
                  f"{pid} 가 나왔다")

        # ── 2. 특정 프로젝트만 ───────────────────────────────────────────────
        print()
        print("=" * 72)
        print(f"2. project_ids = [{member_ids[0]}] -> 그 프로젝트만")
        print("=" * 72)
        one = member_ids[0]
        res1 = service.search(
            user_id, SearchRequest(query="대금 지급", project_ids=[one], limit=50)
        )
        print(f"  결과 {res1.total}건 · 범위 {res1.searched_project_ids}")
        check("범위가 요청과 같다", res1.searched_project_ids == [one])
        check("결과가 그 프로젝트뿐이다",
              all(r.project_id == one for r in res1.results),
              f"{sorted({r.project_id for r in res1.results})}")
        check("결과 수가 전체보다 적거나 같다", res1.total <= res.total,
              f"{res1.total} > {res.total}")

        # ── 3. 멤버가 아닌 프로젝트 요청 ─────────────────────────────────────
        print()
        print("=" * 72)
        print("3. 멤버가 아닌 프로젝트를 요청하면 막히는가")
        print("=" * 72)
        if outsider:
            target = outsider[0]
            try:
                service.search(user_id, SearchRequest(query="대금", project_ids=[target]))
                check(f"프로젝트 {target} 요청이 거부된다", False, "통과되어 버렸다")
            except BusinessError as exc:
                # ErrorCode 가 Enum 이든 tuple 값을 갖든 이름은 str 에 들어간다.
                code = str(exc.error_code)
                print(f"  BusinessError: {code}")
                check(f"프로젝트 {target} 요청이 PROJECT_NOT_FOUND 로 막힌다",
                      "PROJECT_NOT_FOUND" in code, code)
            # 내 것과 남의 것을 섞어도 막혀야 한다
            try:
                service.search(
                    user_id, SearchRequest(query="대금", project_ids=[one, target])
                )
                check("내 것과 남의 것을 섞으면 거부된다", False, "통과되어 버렸다")
            except BusinessError:
                check("내 것과 남의 것을 섞으면 거부된다", True)
        else:
            print("  남의 프로젝트가 없어 건너뜀")

        # 존재하지도 않는 큰 id
        try:
            service.search(user_id, SearchRequest(query="대금", project_ids=[999999]))
            check("없는 프로젝트 id 는 거부된다", False, "통과되어 버렸다")
        except BusinessError:
            check("없는 프로젝트 id 는 거부된다", True)

        # ── 4. 여러 프로젝트 ────────────────────────────────────────────────
        if len(member_ids) >= 2:
            print()
            print("=" * 72)
            print(f"4. project_ids = {member_ids} -> IN 조건")
            print("=" * 72)
            res2 = service.search(
                user_id, SearchRequest(query="계약 기간", project_ids=member_ids, limit=50)
            )
            print(f"  결과 {res2.total}건 · 프로젝트 {sorted({r.project_id for r in res2.results})}")
            check("범위 전체를 지정한 결과가 None 과 같다", res2.total == res.total,
                  f"{res2.total} != {res.total}")

        # ── 5. 응답 필드 ────────────────────────────────────────────────────
        print()
        print("=" * 72)
        print("5. 응답 필드 (RAG-08 근거 스니펫)")
        print("=" * 72)
        if res.results:
            item = res.results[0]
            print(f"  chunk_id={item.chunk_id} doc={item.document_id} seq={item.seq}")
            print(f"  project = {item.project_id} · {item.project_name}")
            print(f"  similarity = {item.similarity}")
            print(f"  char_count = {item.char_count} · content = {item.content_start}~{item.content_end}")
            print(f"  snippet = {item.snippet[:70]}")
            check("project_name 이 비어 있지 않다", bool(item.project_name))
            check("document_filename 이 비어 있지 않다", bool(item.document_filename))
            check("snippet 에 줄바꿈이 없다", "\n" not in item.snippet)
            check("similarity 가 -1~1 범위", -1.0001 <= item.similarity <= 1.0001,
                  str(item.similarity))
            check("snippet 길이가 상한 이내",
                  len(item.snippet) <= 240, str(len(item.snippet)))
            bad = [r.seq for r in res.results
                   if (r.content_start is None) != (r.content_end is None)]
            check("content 구간은 둘 다 있거나 둘 다 없다", not bad, str(bad))
        else:
            check("결과가 하나라도 있다", False, "청크가 없거나 조건이 너무 좁다")

        # ── 6. document_id 지정 ─────────────────────────────────────────────
        print()
        print("=" * 72)
        print("6. document_id 로 한 문서 안에서만")
        print("=" * 72)
        if res.results:
            doc = res.results[0].document_id
            res3 = service.search(
                user_id, SearchRequest(query="대금", document_id=doc, limit=50)
            )
            print(f"  document_id={doc} -> {res3.total}건")
            check("그 문서 청크만 나온다",
                  all(r.document_id == doc for r in res3.results),
                  f"{sorted({r.document_id for r in res3.results})}")

        # ── 7. min_similarity ───────────────────────────────────────────────
        print()
        print("=" * 72)
        print("7. min_similarity 로 자르기")
        print("=" * 72)
        res4 = service.search(
            user_id, SearchRequest(query="대금", limit=50, min_similarity=0.99)
        )
        print(f"  min_similarity=0.99 -> {res4.total}건 (가짜 임베더라 0 근처이므로 적어야 한다)")
        check("임계값이 실제로 자른다", res4.total <= res.total,
              f"{res4.total} > {res.total}")
        check("남은 결과는 모두 임계값 이상",
              all(r.similarity >= 0.99 for r in res4.results))

        # ── 8. 빈 목록은 거부 ───────────────────────────────────────────────
        print()
        print("=" * 72)
        print("8. project_ids = [] 는 스키마에서 거부되는가")
        print("=" * 72)
        try:
            SearchRequest(query="대금", project_ids=[])
            check("빈 목록은 거부된다", False, "통과되어 버렸다")
        except Exception as exc:
            print(f"  {type(exc).__name__}")
            check("빈 목록은 거부된다", True)

        # ── 9. 실행계획 ─────────────────────────────────────────────────────
        print()
        print("=" * 72)
        print("9. 실행계획 — 리비전 0014 검증")
        print("=" * 72)
        print()
        print(f"--- 단일 프로젝트 (= {one}) ---")
        print(service.explain(user_id, SearchRequest(query="대금", project_ids=[one], limit=5)))
        if len(member_ids) >= 2:
            print()
            print(f"--- 여러 프로젝트 (IN {member_ids}) ---")
            print(service.explain(user_id, SearchRequest(query="대금", project_ids=member_ids, limit=5)))

        db.rollback()

    print()
    print("=" * 72)
    print(f"검사 {len(PASS)}개 통과 · 실패 {len(FAIL)}개")
    print("=" * 72)
    for f in FAIL:
        print("  -", f)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
