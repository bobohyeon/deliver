# =============================================================================
# 이 파일의 책임: 의미 검색 API(RAG-04)의 HTTP 경계를 정의한다. 요청을 받아
#   서비스에 넘기고 응답 스키마로 돌려준다. 검색 로직은 두지 않는다.
# 다른 파일과의 관계: dependencies.get_project_access 로 권한을 먼저 검사하고,
#   services/search_service.py 가 실제 검색을 한다. main.py 가 이 router 를
#   include_router 로 등록한다.
#
#   권한에 get_project_access 를 쓰는 이유(get_project_editor_access 가 아님):
#   검색은 읽기이므로 VIEWER 도 할 수 있어야 한다. 그리고 이 의존성이
#   프로젝트 멤버가 아니면 PROJECT_NOT_FOUND 로 막으므로, RAG-04 판정 기준인
#   "다른 프로젝트 문서는 나오지 않는다"가 인증 단계에서 먼저 보장된다.
#   서비스의 WHERE project_id 조건은 그 위에 겹친 두 번째 방어선이다.
#
# Spring 비교: @RestController + @RequestMapping 이다. prefix 가
#   @RequestMapping("/api/projects/{project_id}") 에 해당하고, Depends 는
#   HandlerMethodArgumentResolver 나 @AuthenticationPrincipal 자리에 해당한다.
# =============================================================================

from fastapi import APIRouter, Depends

from app.dependencies import ProjectAccess, get_project_access, get_search_service
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/projects/{project_id}", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    access: ProjectAccess = Depends(get_project_access),
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """프로젝트 안에서 의미 검색을 한다.

    GET 이 아니라 POST 인 이유는 세 가지다.
      1. 질의가 문장이다. URL 에 넣으면 한글이 퍼센트 인코딩되어 길어진다.
      2. 앞으로 필터가 늘어난다 (문서 유형 · 기간 · RAG-05 하이브리드 가중치).
      3. 검색 질의가 브라우저 이력과 서버 접근 로그에 남지 않는다. 조달 문서를
         다루므로 "무엇을 찾고 있는지"가 사업 정보다.

    경로 파라미터 project_id 를 직접 쓰지 않고 access.project.id 를 쓰는 것은
    기존 라우터(analysis_router.py)와 같은 규칙이다 — 권한 검사를 통과한 값만
    서비스로 넘긴다.
    """
    # path 의 project_id 는 get_project_access 가 이미 검증했다.
    return service.search(access.project.id, request)


@router.post("/search/explain", response_model=dict)
def explain_search(
    request: SearchRequest,
    access: ProjectAccess = Depends(get_project_access),
    service: SearchService = Depends(get_search_service),
) -> dict:
    """검색 실행계획을 돌려준다 (검증용).

    리비전 0014 에서 project_id 를 역정규화한 근거가 "조건이 인덱스 스캔 단계로
    내려간다"였는데, 청크가 0행이던 동안에는 확인할 수 없었다. 이 엔드포인트로
    계획을 눈으로 본다.

    운영에 필요한 기능이 아니다. 검증이 끝나면 지우거나 관리자 전용으로 옮긴다.
    """
    return {"plan": service.explain(access.project.id, request)}
