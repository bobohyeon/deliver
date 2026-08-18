# -*- coding: utf-8 -*-
"""팀 기능명세서 v5(세분화 판)를 v4 레이아웃 그대로 xlsx 로 만든다.

이 파일의 책임: 팀 스프레드시트의 세분화 기능 목록(112행)에 2026-08-18 확인분을
  반영해 xlsx 한 장으로 만든다. v4 원본과 같은 레이아웃(제목 2행 + 빈 행 +
  헤더 4행 + 데이터 5행부터, 11열, 상태·우선순위 드롭다운)을 쓴다.
다른 파일과의 관계: 도구/_build_feature_spec.py 는 내 내부 정본(두 자리 체계
  RAG-01 등 136건)을 뽑는다. 이 파일은 팀 공유용 세 자리 체계(RAG-001-3 등)다.
  둘은 입도가 다른 별개 문서이므로 데이터를 공유하지 않는다.
Spring 비교: 없음 — 순수 문서 생성 스크립트다.

openpyxl 이 없고 PyPI 도 막힌 환경이라 xlsx(zip + OOXML)를 직접 쓴다.
xlsx 유틸과 스타일은 _build_feature_spec.py 와 같은 방식이다. 지금은 복사해
뒀고, 세 번째 사용처가 생기면 도구/_xlsx.py 로 빼는 것이 맞다.

사용:
    python3 도구/_build_feature_spec_v5.py
"""

import pathlib
import zipfile
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "산출물" / "기능명세서_v5_세분화.xlsx"

TITLE = "Tasqra 기능명세서 v5"
SUBTITLE = ("적용 페이지별 사용자 기능 중심 명세 · v4 의 상위 기능을 담당·상태가 갈리는 "
            "단위로 세분화 · 2026-08-18 구현 확인분 반영")

HEADER = ["기능 ID", "영역", "적용 페이지", "기능명", "기능 설명 및 포함 범위",
          "상태", "우선순위", "담당", "선행 기능", "완료 판정 기준", "비고"]

# 열 너비. v4 화면 비율에서 잰 값이다.
WIDTHS = [(1, 11), (2, 11), (3, 13), (4, 17), (5, 42),
          (6, 9), (7, 10), (8, 11), (9, 14), (10, 44), (11, 22)]

STATUSES = ["미구현", "부분 구현", "구현됨", "검토중", "미결"]
PRIORITIES = ["P0", "P1", "P2", "P3"]
OWNERS = {"최재정", "김보현", "박세현", "미정",
          "최재정, 김보현", "박세현, 김보현", "최재정, 박세현, 김보현"}

# 각 열의 스타일 번호. STYLES 의 cellXfs 순서를 가리킨다.
#   5 = 가운데 정렬(테두리)  ·  9 = 굵게 + 위 정렬 + 줄바꿈  ·  4 = 위 정렬 + 줄바꿈
COL_STYLE = [5, 5, 5, 9, 4, 5, 5, 5, 5, 4, 4]

# ─────────────────────────────────────────────────────────── 기능 데이터
# 탭으로 구분한다. 필드 안에 탭이 없어야 하며 아래 check() 가 검사한다.
# 열 순서는 HEADER 와 같다.
ROWS = """
AUTH-001	계정·권한	회원가입	회원가입 및 계정 생성	로그인 ID, 이메일, 표시 이름, 비밀번호를 입력해 계정을 생성한다.	구현됨	P0	최재정	-	유효한 정보로 계정이 생성되며 중복 ID·이메일과 잘못된 입력은 명확한 오류로 차단된다.	비밀번호는 해시로만 저장한다.
AUTH-002-1	계정·권한	로그인	로그인	아이디·비밀번호로 인증하고 access·refresh 토큰을 발급한다.	구현됨	P0	최재정	AUTH-001	올바른 계정으로 로그인되며 틀린 자격은 401을 반환한다.	
AUTH-002-2	계정·권한	로그인	내 정보 조회	유효 토큰으로 본인 정보를 반환한다.	구현됨	P0	최재정	AUTH-002-1	만료·무효 토큰은 401을 반환한다.	
AUTH-002-3	계정·권한	로그인	토큰 갱신	refresh 토큰으로 access 토큰을 재발급한다.	구현됨	P0	최재정	AUTH-002-1	유효한 refresh만 갱신되고 만료 시 재로그인으로 유도된다.	리비전 0004 refresh_tokens
AUTH-002-4	계정·권한	로그인	로그아웃	현재 세션의 refresh 토큰을 무효화한다.	구현됨	P0	최재정	AUTH-002-1	로그아웃 후 해당 refresh 토큰은 재사용할 수 없다.	revoked_at 기록
AUTH-003	계정·권한	로그인	SSO 로그인	외부 통합 인증을 이용해 계정으로 로그인한다.	미구현	P3	최재정	-	지원 SSO 공급자로 인증한 사용자가 정상 로그인되고 계정 연결 상태가 유지된다.	후순위 기능
PRJ-001-1	프로젝트	프로젝트 목록	프로젝트 생성	새 프로젝트를 생성한다.	구현됨	P0	최재정	AUTH-002-1	생성자가 자동으로 OWNER 멤버로 등록된다.	
PRJ-001-2	프로젝트	프로젝트 목록	내 프로젝트 목록 조회	내가 참여한 프로젝트만 조회한다.	구현됨	P0	최재정	PRJ-001-1	내가 멤버인 프로젝트만 표시된다.	
PRJ-002-1	프로젝트	프로젝트 목록	받은 초대 목록 조회	받은 초대의 프로젝트·초대자·역할·상태를 조회한다.	구현됨	P1	최재정	AUTH-002-1	현재 사용자에게 온 초대만 표시된다.	
PRJ-002-2	프로젝트	프로젝트 목록	초대 수락	받은 초대를 수락한다.	구현됨	P1	최재정	PRJ-002-1	수락한 사용자는 해당 프로젝트 멤버가 된다.	
PRJ-002-3	프로젝트	프로젝트 목록	초대 거절	받은 초대를 거절한다.	구현됨	P1	최재정	PRJ-002-1	거절한 초대는 상태 이력으로 보존된다.	
PRJ-003-1	프로젝트	프로젝트 설정·멤버	프로젝트 정보 수정	프로젝트 이름·설명 등 상세 정보를 수정한다.	구현됨	P0	최재정	PRJ-001-1	EDITOR 이상만 수정 가능하고 VIEWER는 403을 받는다.	
PRJ-003-2	프로젝트	프로젝트 설정·멤버	프로젝트 상태 변경	진행 중·보관됨 상태를 변경한다.	구현됨	P0	최재정	PRJ-001-1	보관 시 목록에서 구분 표시되고 문서는 유지된다.	projects.status
PRJ-003-3	프로젝트	프로젝트 설정·멤버	프로젝트 삭제	프로젝트를 삭제한다.	구현됨	P0	최재정	PRJ-001-1	OWNER만 가능하며 문서·태스크가 함께 정리된다.	
PRJ-004-1	프로젝트	프로젝트 설정·멤버	멤버 초대	이메일과 역할을 지정해 멤버를 초대한다.	부분 구현	P0	최재정	PRJ-001-1	이미 멤버면 409를 반환한다.	TOCTOU: 유니크 제약으로 체크·실행 일원화
PRJ-004-2	프로젝트	프로젝트 설정·멤버	초대 취소	보낸 초대를 취소한다.	부분 구현	P0	최재정	PRJ-004-1	OWNER만 취소할 수 있고 취소 후 재사용되지 않는다.	
PRJ-004-3	프로젝트	프로젝트 설정·멤버	멤버 역할 변경	멤버의 OWNER/EDITOR/VIEWER 역할을 변경한다.	부분 구현	P0	최재정	PRJ-004-1	역할별 허용 동작 표대로 권한이 즉시 반영된다.	금액 열람 권한은 AMT-003-1과 함께 정책 확정 필요
PRJ-004-4	프로젝트	프로젝트 설정·멤버	멤버 제외	프로젝트에서 멤버를 제외한다.	부분 구현	P0	최재정	PRJ-004-1	제외된 사용자는 즉시 프로젝트 범위 밖 데이터에 접근할 수 없다.	
PRJ-004-5	프로젝트	프로젝트 설정·멤버	최근 초대 사용자 재선택	최근에 초대했던 사용자를 목록에서 다시 선택한다.	부분 구현	P2	최재정	PRJ-004-1	최근 초대 이력이 선택 목록에 노출된다.	UX 편의 기능
DSH-001	가시성	대시보드	프로젝트 핵심 현황	문서 수, 처리 중 문서, 열린 태스크, 승인 대기, 문서 유형 분포, 최근 문서를 요약한다.	미구현	P1	김보현	PRJ-001-1	최신 데이터가 지표·목록에 반영되고 각 항목에서 관련 화면으로 이동할 수 있다.	
DSH-002	가시성	대시보드	승인 대기 및 활동 타임라인	승인 대기 제안, 이번 주 활동, 제안 종류별 채택률, 프로젝트 활동 이력을 보여준다.	미구현	P1	김보현	DSH-001	승인 대기 건수·활동 이력이 종류·시각별로 표시되고 관련 화면으로 이동할 수 있다.	v4 에서 이 행의 열이 한 칸 밀려 있었다(선행 기능 칸에 완료 판정 기준이 들어감). 바로잡았다
DOC-001	문서 입력·처리	문서 목록·업로드	파일 업로드 및 안전성 검증	PDF·DOCX·HWPX·JPG·PNG 파일을 다중 업로드하고 형식·크기·빈 파일·페이지·문자 제한·중복(SHA-256)·파일명 안전성을 검증한다.	부분 구현	P0	최재정	PRJ-001-1	유효한 파일만 등록되고 실패 파일은 원인별 오류를 표시하며 내부 저장명 충돌·경로 조작이 없다.	기본 최대 크기 20MB. 중복검사 해시는 SHA-256
DOC-002	문서 입력·처리	문서 목록·업로드	문서 추출·OCR 및 추출 전략	형식·전략에 따라 텍스트 레이어·OCR·하이브리드 추출기를 선택하고 방법을 기록한다.	부분 구현	P0	최재정	DOC-001	AUTO·TEXT_ONLY·TEXT_WITH_IMAGE_OCR 전략과 실제 추출 방법이 기록된다.	DOCX·HWPX 포함, 이미지 OCR 포함
DOC-003-1	문서 입력·처리	문서 목록·업로드	처리 모드 선택	업로드 시 일반·검수·일괄 모드를 선택한다.	미구현	P0	최재정	DOC-001	모드가 저장되고 기본값은 일반이며 검수 모드는 검수 대기 상태로 시작한다.	
DOC-003-2	문서 입력·처리	문서 목록·업로드	비동기 처리 및 진행 상태 조회	업로드를 비동기 큐로 실행하고 단계별 진행·오류를 표시한다.	부분 구현	P0	최재정	DOC-003-1, SYS-002-2	업로드 요청이 즉시 문서 ID를 반환하고 처리 단계·완료·실패 상태를 지속 확인할 수 있다.	큐 실행과 상태·오류 기록은 동작한다(documents.status, processing_error). 남은 것은 DOC-003-1 모드 연동
DOC-004-1	문서 입력·처리	문서 목록·업로드	문서 목록·필터 조회	프로젝트 문서 목록을 페이징 조회하고 유형·처리상태로 필터링한다.	부분 구현	P0	최재정	PRJ-001-1	현재 프로젝트 문서만 표시되고 필터가 정상 동작하며 조회 성능이 문서 수에 비례해 악화되지 않는다.	성능 판정 기준 미달 — N+1 3곳. (1) _build_list_row 가 get_latest_by_type 을 문서마다 2회 + active_ocr_char_count 로 extracted_text 지연로딩, size=20 에 약 62쿼리 (2)(3) document_router 51·84행과 _ordered_ocr_elements 의 page.elements. 처방: IN 배치 + joinedload / selectinload
DOC-004-2	문서 입력·처리	문서 목록·업로드	문서 유형 지정·자동 판별	업로드 시 문서 유형을 지정하거나 자동 판별한다.	부분 구현	P1	최재정	DOC-001	9종 문서 유형과 유형 출처(사용자/AI/AI수정)가 저장된다.	
DOC-005-1	문서 입력·처리	문서 상세	문서 원문·메타정보 조회	요약, 추출 원문, 추출 방식, OCR 엔진, 페이지·글자 수, 신뢰도, 처리 시간을 조회하고 본문을 검색·복사한다.	부분 구현	P0	최재정	DOC-002	문서의 원문과 처리 메타정보가 정확히 표시되고 본문 검색·복사가 정상 동작한다.	
DOC-005-2	문서 입력·처리	문서 상세	원본·요약 다운로드	업로드 당시 원본 파일과 요약본을 다운로드한다.	부분 구현	P0	최재정	DOC-005-1	업로드 당시 파일명으로 원본·요약 다운로드가 정상 동작한다.	
DOC-006-1	문서 입력·처리	문서 상세	문서 삭제	문서를 삭제한다.	부분 구현	P0	최재정	DOC-005-1	하위 데이터(추출텍스트·분석·OCR요소·금액·결정·일정)가 함께 정리된다.	cascade
DOC-006-2	문서 입력·처리	문서 상세	재분석 실행	문서를 다시 분석한다.	부분 구현	P1	최재정	DOC-005-1, ANL-003-2	재분석 결과가 기존 이력을 덮어쓰지 않고 새 행으로 쌓인다.	analyses 1:N
DOC-006-3	문서 입력·처리	문서 상세	문서 버전 이력·변경점 비교	문서 변경 버전을 누적해 과거 결과와 비교한다.	미구현	P3	최재정	DOC-006-1	이전 버전과의 변경점을 확인할 수 있다.	후순위
BAT-001-1	일괄 처리	일괄 처리	다중 파일 업로드	여러 파일을 한 번에 등록한다.	미구현	P1	최재정	DOC-001	파일별 성공·실패가 독립적으로 기록된다.	브라우저 순차 호출로 데모 충분
BAT-001-2	일괄 처리	일괄 처리	처리 대기열 조회	파일별 대기·처리중·검수필요·완료·실패 상태와 실패 사유를 표시한다.	미구현	P1	최재정	BAT-001-1	사용자가 전체 처리 현황을 확인할 수 있다.	
BAT-002-1	일괄 처리	일괄 처리	서버 일괄 작업 실행·복구	브라우저 종료와 무관하게 배치를 실행하고 중단 후 복구한다.	미구현	P2	최재정	DOC-003-2	서버 작업이 중단 후에도 복구되며 진행률이 자원 한도 안에서 갱신된다.	batch_jobs / batch_items. OCR Worker 수 제한 포함
BAT-002-2	일괄 처리	일괄 처리	실패 재시도	실패한 항목만 재시도한다.	미구현	P2	최재정	BAT-002-1	실패 항목만 독립적으로 재시도할 수 있다.	
BAT-002-3	일괄 처리	일괄 처리	실시간 진행률 (SSE)	일괄 처리 진행률을 실시간으로 표시한다.	미구현	P2	최재정	BAT-002-1	진행률이 실시간으로 갱신된다.	
BAT-002-4	일괄 처리	일괄 처리	로컬 폴더 자동 감시	지정 폴더에 파일이 추가되면 자동으로 업로드한다.	미구현	P3	최재정	BAT-002-1	감시 폴더에 파일 추가 시 자동 등록된다.	별도 설치형. 후순위·범위 밖 가능성
REV-001-1	OCR 검수	OCR 검수	OCR 박스 표시 및 신뢰도 구분	페이지 이미지 위에 OCR 박스를 표시하고 신뢰도별로 구분한다.	부분 구현	P1	최재정	DOC-002	확대·축소와 무관하게 박스가 정확히 표시되고 신뢰도 구간이 시각적으로 구분된다.	박스·신뢰도 조회 API(GET review)와 화면은 있다. 신뢰도 구간 시각 구분은 미확인
REV-001-2	OCR 검수	OCR 검수	낮은 신뢰도 요소 모아보기	임계치 미만 박스만 순회하며 검수한다.	미구현	P1	최재정	REV-001-1	낮은 신뢰도 박스만 목록으로 순회할 수 있다.	
REV-002-1	OCR 검수	OCR 검수	박스 텍스트 수정	OCR 박스의 텍스트를 수정한다.	구현됨	P1	최재정	REV-001-1	수정 후 original_text는 보존되고 text만 바뀐다.	
REV-002-2	OCR 검수	OCR 검수	박스 이동·크기 조정	박스 위치·크기를 조정한다.	미구현	P2	최재정	REV-002-1	크기만 바꾸면 텍스트는 유지된다.	
REV-002-3	OCR 검수	OCR 검수	박스 생성·삭제·복원	박스를 새로 만들거나 논리 삭제·복원한다.	미구현	P2	최재정	REV-002-1	삭제는 논리 삭제로 처리되고 복원할 수 있다.	
REV-002-4	OCR 검수	OCR 검수	박스 병합·분리	여러 박스를 합치거나 하나를 나눈다.	미구현	P2	최재정	REV-002-2	병합·분리 후에도 원본과 수정값이 보존된다.	
REV-002-5	OCR 검수	OCR 검수	선택 영역 재OCR	선택한 영역을 다시 OCR 처리한다.	미구현	P2	최재정	REV-002-1	사용자 확인 후에만 재OCR 결과가 반영된다. source=RE_OCR	
REV-003-1	OCR 검수	OCR 검수	단락 지정·병합·분리	OCR 요소의 단락을 지정·병합·분리한다.	미구현	P2	최재정	REV-001-1	OCR 재실행 없이 단락 구조가 반영된다.	
REV-003-2	OCR 검수	OCR 검수	읽기 순서 변경	요소의 읽기 순서를 수동으로 바꾼다.	미구현	P2	최재정	REV-003-1	사용자 지정 순서가 자동 결과(XY-Cut)를 덮지 않는다.	지정순서 > 지정단락 > XY-Cut — RAG-001-1 청킹 입력 순서와 직결
REV-003-3	OCR 검수	OCR 검수	표 행·열 구조 보정	표의 행·열 구조를 수동으로 보정한다.	미구현	P3	최재정	REV-003-1	보정된 표 구조가 텍스트 재조립에 반영된다.	후순위
REV-004-1	OCR 검수	OCR 검수	검수 완료 처리	검수를 완료하고 확정 텍스트를 재조립한다.	구현됨	P1	최재정	REV-002-1	완료 시 is_confirmed=true, 확정자·시각·리비전이 기록되고 텍스트가 같은 트랜잭션에서 갱신된다.	offset 기록 불필요. 완료 직후 RAG-001-3 재인덱싱이 큐에 걸린다
REV-004-2	OCR 검수	OCR 검수	수정 이력 조회·되돌리기	OCR 수정 이력을 조회하고 이전 버전으로 되돌린다.	부분 구현	P2	최재정	REV-002-1	ocr_element_revisions로 이력이 남고 되돌리기가 가능하다.	이력 조회(GET history)는 있고 되돌리기는 미확인
REV-004-3	OCR 검수	OCR 검수	분석 제외·복원	특정 OCR 요소를 분석 대상에서 제외하거나 복원한다.	구현됨	P1	최재정	REV-001-1	제외된 요소는 확정 텍스트·분석에 포함되지 않으며 복원 시 다시 포함된다.	is_excluded 컬럼
REV-004-4	OCR 검수	OCR 검수	동시 수정 충돌 방지	같은 박스를 동시에 수정하면 충돌을 차단한다.	구현됨	P1	최재정	REV-002-1	같은 박스를 두 사용자가 수정하면 나중 요청이 409를 받는다.	ocr_elements.version
REV-004-5	OCR 검수	OCR 검수	분석 결과 최신성 표시	OCR 확정 후 분석이 오래됐음을 사용자에게 알린다.	미구현	P1	최재정	REV-004-1	OCR을 고친 뒤 화면에 '분석을 다시 실행해 주세요' 배너가 표시된다.	v4 누락분 보완. 판정 재료는 이미 있다 — extracted_texts.text_version, documents.ocr_revision, analyses 의 ocr_revision 을 대조하면 된다. 청크도 같은 방식(ix_chunk_stale)을 쓴다
ANL-001-1	분석	문서 상세·분석	문서 요약	문서를 요약한다.	부분 구현	P0	박세현	DOC-002	요약문과 토큰·지연시간이 함께 기록된다.	
ANL-001-2	분석	문서 상세·분석	문서 유형 분류	문서를 지정된 문서 유형으로 자동 분류한다.	부분 구현	P0	박세현	DOC-004-2	분류 결과와 판단 근거(reason)가 함께 생성된다. 사용자 지정 유형은 자동 분류로 덮어쓰지 않는다.	
ANL-002-1	분석	문서 상세·분석	액션 아이템 추출	문서에서 액션 아이템을 구조화해 추출한다.	미구현	P1	박세현	ANL-001-1	정의된 스키마의 배열이 생성되고 근거·확신도가 함께 붙는다. 문서에 없는 값은 만들지 않는다.	
ANL-002-2	분석	문서 상세·분석	결정사항 추출	회의록 등에서 결정된 사항을 추출한다.	미구현	P1	박세현	ANL-001-1	결론이 안 난 항목은 PENDING으로 남아 회의 안건 재료가 된다.	DLV-003-2의 재료
ANL-002-3	분석	문서 상세·분석	일정·기한 추출	문서의 날짜·기한을 추출한다.	미구현	P1	박세현	ANL-001-1	날짜 형식을 원문과 대조해 정확도를 측정할 수 있다.	DLV-002-1·DLV-002-2의 재료
ANL-003-1	분석	문서 상세·분석	분석 진행률 표시	분석기별 진행 상태를 표시한다.	부분 구현	P1	박세현	ANL-001-1	분석기가 추가돼도 진행률 표시 로직(화면 코드)을 고치지 않는다.	
ANL-003-2	분석	문서 상세·분석	분석 이력·버전 조회	재분석 결과와 모델·프롬프트 버전, 실행 메타정보를 기록·조회한다.	부분 구현	P0	박세현	ANL-001-1	최신·과거 결과가 구분 조회되고 어느 OCR 리비전으로 분석했는지 함께 기록된다.	v4 누락분 보완 — ocr_revision 추적 명시
ANL-004-1	분석	문서 상세·분석	LLM 재시도·폴백	일시 실패 시 재시도하고 지속 실패 시 대체 모델을 쓴다.	미구현	P2	박세현	ANL-001-1	일시 오류는 재시도되고 지속 실패는 대체 경로로 처리된다.	재시도·폴백의 유일한 소유 항목 (SYS-003에는 포함하지 않음)
ANL-004-2	분석	문서 상세·분석	평가셋 기반 정확도 측정	동일 평가셋으로 모델·프롬프트별 정확도를 측정한다.	미구현	P1	김보현	ANL-002-1	정답 데이터와 대조한 정확도가 수치로 나오고 모델·프롬프트를 바꿔도 같은 자로 잰다.	박세현님 모델 비교에 직접 사용
ANL-004-3	분석	문서 상세·분석	교정 분석기	문서의 오탈자·비문을 교정한다.	미구현	P3	박세현	ANL-001-1	교정 전/후가 함께 표시된다.	후순위
ANL-004-4	분석	문서 상세·분석	번역 분석기	문서를 다른 언어로 번역한다.	미구현	P3	박세현	ANL-001-1	번역 결과가 원문과 함께 표시된다.	후순위
TSK-001-1	태스크·협업	칸반 보드	태스크 CRUD	제목·설명·담당자·기한·상태를 가진 태스크를 생성·조회·수정·삭제한다.	미구현	P1	최재정	PRJ-001-1	사람이 태스크를 직접 만들고 수정·삭제할 수 있다.	
TSK-001-2	태스크·협업	칸반 보드	칸반 상태 변경	3열 칸반에서 드래그로 상태를 변경한다.	미구현	P1	최재정	TSK-001-1	드래그로 상태가 바뀌고 완료 시 completed_at이 정확히 기록된다.	completed_at은 DLV-002-1 필수 입력
TSK-002-1	태스크·협업	칸반 보드	AI 제안 승인	AI 제안을 승인해 태스크로 확정한다.	미구현	P1	김보현	ANL-002-1	승인해야 등록되고, 승인 전에는 보드에 나타나지 않는다.	자동 등록 금지 원칙
TSK-002-2	태스크·협업	칸반 보드	AI 제안 거절	AI 제안을 거절한다.	미구현	P1	김보현	ANL-002-1	거절한 제안은 다시 뜨지 않고 거절 사실이 기록된다.	채택률 지표의 원천
TSK-002-3	태스크·협업	칸반 보드	AI 제안 수정	승인 전 AI 제안 내용을 수정한다.	미구현	P1	김보현	ANL-002-1	수정 후 값으로 태스크가 확정된다.	
TSK-002-4	태스크·협업	칸반 보드	일괄 승인	문서 단위로 여러 제안을 한 번에 승인한다.	미구현	P1	김보현	TSK-002-1	문서 단위로 다건 제안이 한 번에 승인된다.	
TSK-003-1	태스크·협업	칸반 보드	출처·판단 근거 표시	태스크에 출처 문서 링크와 AI 판단 근거를 표시한다.	미구현	P2	최재정, 김보현	TSK-001-1	출처 문서 링크와 reason이 함께 보인다.	원문 위치 하이라이트는 SRH-002-2에서 이미 구현됐다 — 같은 방식(content_start·content_end + ?from=&to=)을 재사용할 수 있다
TSK-003-2	태스크·협업	칸반 보드	AI 생성 배지·필터	AI 생성 태스크를 구분하고 필터링한다.	미구현	P2	최재정, 김보현	TSK-001-1	AI생성만·기한임박·출처문서별 필터가 정상 동작한다.	
TSK-003-3	태스크·협업	칸반 보드	활동 기록 조회	프로젝트 내 주요 변경을 활동 이력으로 조회한다.	미구현	P2	최재정, 김보현	TSK-001-1	주요 변경이 활동 이력에 남는다.	activity_logs
TSK-003-4	태스크·협업	칸반 보드	외부 알림	이메일·Slack으로 알림을 보낸다.	미구현	P3	최재정	TSK-003-3	설정된 채널로 알림이 발송된다.	후순위
AMT-001-1	금액	프로젝트 금액	금액 항목 추출	문서에서 항목명·수량·단위·단가·금액·원가구분·근거를 추출한다.	미구현	P1	박세현, 김보현	ANL-002-1	계약 스키마에 맞는 값만 저장되고 문서에 없는 값은 비운다.	LLM은 추출만
AMT-001-2	금액	프로젝트 금액	금액 항목 승인·수정	추출된 금액 항목을 사용자가 승인하거나 수정한다.	미구현	P1	박세현, 김보현	AMT-001-1	승인 전에는 어디에도 반영되지 않고 수정 전/후 값이 보존된다.	
AMT-002-1	금액	프로젝트 금액	금액 계산·합계 검증	수량×단가로 항목 금액을 계산하고 문서 합계와 대조한다.	미구현	P1	김보현	AMT-001-2	동일 입력에 동일 계산 결과가 나오고 불일치 금액이 표시된다.	계산은 코드가 수행. 결정론적
AMT-002-2	금액	프로젝트 금액	프로젝트 금액 집계	여러 문서의 금액을 프로젝트 단위로 모은다.	미구현	P1	김보현	AMT-002-1	같은 입력이면 항상 같은 집계 결과가 나온다.	단위테스트로 확인
AMT-003-1	금액	프로젝트 금액	금액 열람 권한 적용	역할에 따라 금액 열람을 제한한다.	미구현	P2	김보현	PRJ-004-3	허용된 사용자만 금액을 조회할 수 있다.	VIEWER 노출 정책 확정 필요 — 미결
AMT-003-2	금액	프로젝트 금액	프로젝트 금액 현황 조회	계약금액·변경 증감·집행률·잔액을 프로젝트 단위로 보여준다.	미구현	P2	김보현	AMT-002-2	현황 수치가 정확히 집계돼 표시된다.	
AMT-003-3	금액	프로젝트 금액	계산식·산출 근거 표시	금액마다 계산식과 출처 문서·원문 근거를 표시한다.	미구현	P1	김보현	AMT-002-1	각 금액의 계산식과 원문 근거로 이동할 수 있다.	
AMT-004-1	금액	프로젝트 금액	근거 변경 탐지 및 재계산	근거 문서가 변경되면 영향받은 값을 다시 추출·계산한다.	미구현	P2	김보현	AMT-002-1	변경된 필드만 재계산되고 모델 재학습은 없다.	
AMT-004-2	금액	프로젝트 금액	계산 버전·변경 이력 저장	변경 전후 값과 차액을 저장한다.	미구현	P2	김보현	AMT-004-1	계산 버전과 차액이 추적된다.	
AMT-004-3	금액	프로젝트 금액	불일치 태스크 제안	합계 불일치 시 태스크를 제안한다.	미구현	P1	김보현	AMT-002-1, TSK-002-1	불일치 시 승인형 태스크 제안 카드가 생기고 자동 등록은 하지 않는다.	
DLV-001-1	산출물	산출물	산출물 조건 선택	산출물 유형·기간·출력 형식(XLSX·HTML·MD)을 선택한다.	미구현	P1	김보현	PRJ-001-1	형식을 고르지 않으면 생성 버튼이 비활성화된다.	
DLV-001-2	산출물	산출물	생성 대상 미리보기	생성 전 대상 문서·태스크·결정·기한·금액·승인대기 건수를 확인한다.	미구현	P1	김보현	DLV-001-1	LLM 호출 전에 건수가 보이고 대상이 없으면 생성이 방지된다.	빈 보고서 방지 + 비용 절약
DLV-002-1	산출물	산출물	주간 보고서 생성	선택 기간의 문서·태스크·결정·기한·금액 변동을 보고서로 만든다.	미구현	P1	김보현	DLV-001-2, TSK-001-2	개요·문서목록·태스크·결정·기한·금액변동이 한 파일로 나온다. LLM 호출은 개요 1회.	tasks.completed_at 필수
DLV-002-2	산출물	산출물	프로젝트 현황 한 장 생성	일정·태스크·결정·금액 현재 상태를 한 페이지로 만든다.	미구현	P2	김보현	DLV-001-2	현재 상태가 한 페이지 요약으로 생성된다.	
DLV-002-3	산출물	산출물	인수인계 문서 생성	프로젝트 종료 시 전체 누적 내용을 인수인계 문서로 만든다.	미구현	P3	김보현	DLV-002-2	프로젝트 전체 누적 내용이 하나의 문서로 생성된다.	후순위
DLV-003-1	산출물	산출물	결정사항 대장 생성	결정 내용·결정일·출처·상태(확정/미결/뒤집힘)를 표로 만든다.	미구현	P1	김보현	DLV-001-2, ANL-002-2	결정 상태별로 표가 정확히 생성된다.	
DLV-003-2	산출물	산출물	다음 회의 안건 생성	미결(PENDING) 결정만 모아 회의 안건을 만든다.	미구현	P1	김보현	DLV-003-1	PENDING 상태 항목만 안건으로 생성된다.	DLV-003-1의 부산물
DLV-003-3	산출물	산출물	생성 이력·다운로드	만든 산출물을 목록으로 보고 다시 내려받는다.	미구현	P1	김보현	DLV-002-1	생성된 산출물이 이력으로 남고 재다운로드할 수 있다.	deliverables 테이블
DLV-003-4	산출물	산출물	갱신 필요 판정	생성 후 원천 데이터가 늘면 다시 만들기를 안내한다.	미구현	P1	김보현	DLV-003-3	생성 후 대상이 추가되면 갱신 필요 표시가 뜬다.	source_counts_json 스냅샷 비교
SRH-001	검색·근거	통합 검색	의미 검색	내가 멤버인 프로젝트 범위에서 벡터 의미 검색을 제공한다. 범위는 내 멤버십 전체와 특정 프로젝트 중에서 고른다.	구현됨	P1	김보현	RAG-001-2	의미기반 질의가 관련 조각을 찾고, 내가 멤버가 아닌 프로젝트 문서는 어떤 경우에도 결과에 나오지 않는다. 문서를 열었다 돌아와도 검색 결과가 유지된다.	POST /api/search. 키워드·하이브리드는 SRH-003·SRH-004로 분리했다. '다른 프로젝트 문서 제외'는 '내가 멤버가 아닌 프로젝트 제외'로 읽는다 — 그래야 SRH-002-3과 모순되지 않는다
SRH-002-1	검색·근거	통합 검색	검색 결과 재순위	검색 결과를 관련도에 따라 재정렬한다.	미구현	P3	김보현	SRH-001	재정렬된 순서로 결과가 표시된다.	후순위
SRH-002-2	검색·근거	통합 검색	근거 스니펫 연결	검색·응답 결과마다 출처 문서와 원문 인용을 연결한다.	구현됨	P1	김보현	SRH-001	결과마다 출처 문서와 인용 근거가 표시되고, 조각을 누르면 원문의 해당 위치로 이동해 강조된다.	응답의 content_start·content_end 를 쓴다(서버 변경 없음). 원문이 검수로 수정되면 좌표가 어긋날 수 있다 — 길이를 벗어난 경우는 걸러내지만 내용만 바뀐 경우는 못 잡는다. 응답에 text_version 을 더하면 해결(미결)
SRH-002-3	검색·근거	통합 검색	유사 사업 단가 선례 검색	과거 유사 사업 문서에서 같은 항목의 단가를 찾는다.	미구현	P2	김보현	SRH-001	과거 사업의 단가가 출처와 함께 표시된다.	비용추계의 근거 — 도메인을 좁힌 이유. 검색 API 변경은 필요 없다. project_ids 에 (내 멤버십 − 현재 프로젝트)를 넘기면 된다 — _resolve_scope 가 부분집합을 받는다
SRH-003	검색·근거	통합 검색	키워드 검색	고유명사·숫자·문서번호처럼 정확한 문자열로 문서와 조각을 찾는다.	미구현	P1	김보현	RAG-001-1	고유 문자열이 의미 검색에서 누락돼도 키워드 검색으로 찾힌다.	SRH-001에서 분리. 의미 검색은 고유명사·숫자에 약하다. 문서 목록의 q 필터(ilike)와는 다른 기능 — 조각 단위로 찾아야 근거 인용이 된다
SRH-004	검색·근거	통합 검색	키워드·의미 결합(하이브리드)	키워드 결과와 의미 검색 결과를 하나의 순위로 합친다.	미구현	P2	김보현	SRH-001, SRH-003	두 방식 중 한쪽만 찾아내는 질의도 결합 결과에서 상위에 나온다.	결합 방식(RRF 등) 미정. SRH-002-1 재순위와 같이 검토할 것
CHAT-001	검색·근거	문서 챗봇	문서 기반 질의응답	접근 가능한 문서를 검색해 질문에 답하고 근거를 제공한다.	미구현	P3	김보현	SRH-001	답변마다 근거 문서와 원문 인용이 표시되고 권한 밖 문서는 제외된다.	검색 범위 정책은 SRH-001에서 확정됐다(project_ids, 멤버 아닌 프로젝트는 404). 그 규칙을 그대로 재사용한다
REC-001	AI 추천	AI 추천	액션 태스크 추천 및 프로젝트 갭 분석	프로젝트 문서·업무 흐름을 분석해 놓친 작업과 부족한 내용을 근거와 함께 제안한다.	검토중	P2	박세현	RAG-002-1, TSK-002-1	추천마다 근거·출처가 표시되고 사용자가 승인한 제안만 태스크가 된다.	프롬프트+RAG 방식 우선 검증. 선행인 RAG-002-1(컨텍스트 조립)은 김보현 담당이므로 그것이 끝난 뒤 착수
SYS-001-1	공통·기반	공통·백엔드	인증 미들웨어	모든 보호 API에 사용자 인증을 적용한다.	구현됨	P0	최재정	AUTH-002-1	토큰 없이 보호된 엔드포인트 호출 시 401을 받는다.	get_current_user. 라우터마다 개별 검사하면 누락된다
SYS-001-2	공통·기반	공통·백엔드	프로젝트 스코프 강제	역할 권한과 프로젝트 경계를 서버 계층에서 강제한다.	구현됨	P0	최재정	PRJ-001-1	다른 프로젝트의 식별자를 직접 입력해도 404를 받는다.	리포지토리 계층에서 차단
SYS-002-1	공통·기반	공통·백엔드	Alembic 마이그레이션	DB 스키마 변경을 마이그레이션으로 관리한다.	구현됨	P0	김보현	-	create_all() 의존 없이 컬럼 추가가 데이터 유실 없이 반영된다.	리비전 0001~0014. api 컨테이너가 기동 시 alembic upgrade head 를 돌린다
SYS-002-2	공통·기반	공통·백엔드	비동기 작업 큐	Celery·Redis로 백그라운드 작업을 처리한다.	구현됨	P0	최재정	SYS-002-1	워커가 죽어도 작업이 큐에 남고 재시작 시 이어진다.	태스크 documents.extract · chunks.build. 큐에는 정수 인자만 실리고 워커가 DB 를 다시 읽는다 — 그래서 넣는 쪽이 커밋을 먼저 해야 한다
SYS-002-3	공통·기반	공통·백엔드	영속 파일 저장소	S3·MinIO 계열로 파일을 저장한다.	미구현	P1	최재정	-	컨테이너 재기동 후에도 파일이 유지된다.	산출물 파일도 같은 곳에 둔다
SYS-002-4	공통·기반	공통·백엔드	임베딩 모델 서빙 경로 확정	청킹·검색이 쓸 임베딩 모델을 어디서 실행할지 정하고 배포에 반영한다.	미결	P1	김보현	RAG-001-2	개발·배포 양쪽에서 같은 모델·차원으로 임베딩되고, 모델 이름이 document_chunks.embedding_model 과 일치한다.	현재는 호스트에서 embed_server.py 를 띄워 쓴다(개발 전용, 포트 8900). 컨테이너에 sentence-transformers 를 넣지 않기로 결정 — api·worker 각 2.3GB 로 가용 메모리를 넘는다. 모델을 바꾸면 전체 재청킹이 필요하다
SYS-003-1	공통·기반	공통·백엔드	오류코드 체계·요청 로깅	일관된 오류코드와 request_id 로그를 제공한다. (LLM 재시도·폴백은 ANL-004-1이 전담)	부분 구현	P0	최재정, 김보현	-	주요 오류가 동일한 응답 형식과 서버 로그에 남고 요청 단위 추적이 가능하다.	
SYS-003-2	공통·기반	공통·백엔드	API 호출 쿼터	프로젝트별 API 호출량을 제한한다.	미구현	P2	박세현	-	월 한도 초과 시 요청이 차단된다.	TOCTOU: 원자적 UPDATE로 체크·실행 일원화
SYS-003-3	공통·기반	공통·백엔드	로컬 sLLM 옵션	OpenAI 대신 로컬 모델을 선택적으로 쓴다.	미구현	P3	박세현	-	AI_PROVIDER 설정으로 로컬 모델 사용이 전환된다.	모델 선정 후 진행
RAG-001-1	검색·근거	공통·백엔드	텍스트 정규화·청킹	확정 텍스트를 정규화하고 청크로 자른다.	구현됨	P1	김보현	REV-004-1	element_type으로 단락을 묶고 토큰 수 기준으로 자르며 표는 행 단위를 유지한다.	CHARS_PER_TOKEN(실측 1.89)이 세 값과 곱해진다 — MAX_TOKENS(최대 글자), MIN_TOKENS(흡수 기준), OVERLAP_TOKENS(겹침 글자). 비율만 고치면 세 정책이 같이 변한다. 2026-08-18에 1.2→1.89로만 고쳐서 흡수 기준이 58자→91자로 넓어져 짧은 절이 삼켜지고 검색 정답이 1위→2위로 밀렸다. MIN_TOKENS를 48→30으로 같이 내려 해결. 도구/check_chunking.py 가 조각 경계를 대조해 이 회귀를 막는다
RAG-001-2	검색·근거	공통·백엔드	임베딩 생성·벡터 인덱스 저장	청크를 임베딩으로 변환해 pgvector에 저장한다.	구현됨	P1	김보현	RAG-001-1, SYS-002-1	청크마다 모델·차원·출처가 기록되고 프로젝트 범위 인덱스가 유지된다.	모델을 바꾸면 전체 재청킹이 필수다. 검색이 WHERE embedding_model = 현재 모델로 걸리므로, 안 하면 검색 결과가 조용히 0건이 된다. 실제 모델 dragonkue/BGE-m3-ko · 1024차원
RAG-001-3	검색·근거	공통·백엔드	검수 확정 시 재인덱싱	OCR 수정 후 해당 문서를 다시 인덱싱한다.	구현됨	P1	김보현	RAG-001-2, REV-004-1	OCR을 고치면 청크가 재임베딩되고 낡은 벡터로 검색되지 않는다. 본문이 바뀌지 않은 검수 완료는 재임베딩을 건너뛴다. 본문이 비면 기존 청크를 지운다.	검수 완료 라우터에서 트랜잭션 커밋 후 큐에 넣는다(안에서 넣으면 워커가 커밋 전 본문을 읽는다). 큐 등록 실패는 삼키고 ChunkRepository.stale_document_ids()로 복구한다. 건너뛰기 0.010초 vs 재청킹 0.62~1.08초
RAG-002-1	검색·근거	공통·백엔드	프롬프트 컨텍스트 조립	토큰 예산 안에서 관련 청크를 조립한다.	미구현	P1	김보현	RAG-001-2	긴 문서에서도 컨텍스트 한도를 넘지 않는다.	겹침이 길어지면 인접 조각이 겹치는 내용을 또 담아 예산을 낭비한다. OVERLAP_TOKENS 조정과 함께 볼 것
RAG-002-2	검색·근거	공통·백엔드	검색 품질 측정	동일 질의셋으로 검색 적중률을 반복 측정한다.	부분 구현	P2	김보현	RAG-001-2	같은 질의셋으로 청킹·임베딩 변경 효과를 비교할 수 있다.	도구/embed-test/ir_eval.py(질의 133건, accuracy@1·map@100·ndcg@10·recall@5) + 도구/check_rag04_quality.py(순위 회귀 3건). 청킹 값을 바꿀 때 필수 — 값만 고치고 안 재면 회귀를 놓친다(실제로 겪음)
"""


# ─────────────────────────────────────────────── xlsx 유틸
def col_letter(idx):
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_xml(row, col, value, style=0):
    ref = f"{col_letter(col)}{row}"
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>')


def sheet_xml(rows, widths=None, freeze=None, autofilter=None, validations=""):
    cols = ""
    if widths:
        cols = "<cols>" + "".join(
            f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>'
            for c, w in widths) + "</cols>"

    body = []
    for rnum, (height, cells) in enumerate(rows, start=1):
        h = f' ht="{height}" customHeight="1"' if height else ""
        cs = "".join(cell_xml(rnum, c, v, s) for c, v, s in cells)
        body.append(f'<row r="{rnum}"{h}>{cs}</row>')

    pane = ""
    if freeze:
        top_left, xsplit, ysplit = freeze
        pane = (f'<pane xSplit="{xsplit}" ySplit="{ysplit}" topLeftCell="{top_left}" '
                f'activePane="bottomRight" state="frozen"/>')

    af = f'<autoFilter ref="{autofilter}"/>' if autofilter else ""

    # 순서가 스키마로 정해져 있다 — sheetData, autoFilter, dataValidations, pageMargins.
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
            f'{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16.5"/>'
            f'{cols}<sheetData>{"".join(body)}</sheetData>{af}{validations}'
            '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" '
            'header="0.3" footer="0.3"/>'
            '</worksheet>')


def dropdown(ref, options):
    """목록 드롭다운. v4 의 상태·우선순위 열에 걸려 있던 것과 같은 것이다."""
    formula = '"' + ",".join(options) + '"'
    return (f'<dataValidation type="list" allowBlank="1" showInputMessage="1" '
            f'showErrorMessage="1" sqref="{ref}">'
            f'<formula1>{escape(formula)}</formula1></dataValidation>')


STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="6">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="15"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="4">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF000000"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF6F6F6"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFC0C0C0"/></left>
<right style="thin"><color rgb="FFC0C0C0"/></right>
<top style="thin"><color rgb="FFC0C0C0"/></top>
<bottom style="thin"><color rgb="FFC0C0C0"/></bottom>
<diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="10">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="5" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                 '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                 '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                 '</Types>')

ROOT_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
             '</Relationships>')

WORKBOOK = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="기능명세" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>')

WB_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
           '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
           '</Relationships>')


# ─────────────────────────────────────────────── 검사
def parse():
    out = []
    for lineno, line in enumerate(ROWS.strip("\n").split("\n"), start=1):
        if not line.strip():
            continue
        out.append((lineno, line.split("\t")))
    return out


def check(rows):
    """붙여넣기 전에 사람이 못 보는 오류를 잡는다.

    v4 의 DSH-002 는 열이 한 칸 밀려서 선행 기능 칸에 완료 판정 기준이 들어가
    있었다. 눈으로는 안 보인다. 칸 수와 값의 종류를 세면 잡힌다.
    """
    problems = []
    ids = []
    n = len(HEADER)

    for lineno, cells in rows:
        rid = cells[0] if cells else "(빈 줄)"
        if len(cells) != n:
            problems.append(f"{rid}: 칸이 {len(cells)}개다 ({n}개여야 한다) — 줄 {lineno}")
            continue
        ids.append(rid)
        status, priority, owner, deps = cells[5], cells[6], cells[7], cells[8]
        if status not in STATUSES:
            problems.append(f"{rid}: 상태 '{status}' 는 목록에 없다 {STATUSES}")
        if priority not in PRIORITIES:
            problems.append(f"{rid}: 우선순위 '{priority}' 가 이상하다")
        if owner not in OWNERS:
            problems.append(f"{rid}: 담당 '{owner}' 가 이상하다")
        # 선행 기능 칸에 문장이 들어가는 사고를 잡는다.
        if len(deps) > 40 or deps.endswith("다.") or " " in deps.replace(", ", ""):
            problems.append(f"{rid}: 선행 기능 칸이 ID 목록이 아니다 -> '{deps[:40]}'")

    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        problems.append(f"기능 ID 중복: {sorted(duplicates)}")

    known = set(ids)
    for lineno, cells in rows:
        if len(cells) != n:
            continue
        deps = cells[8].strip()
        if deps in ("", "-"):
            continue
        for dep in [d.strip() for d in deps.split(",")]:
            if dep and dep not in known:
                problems.append(f"{cells[0]}: 선행 기능 '{dep}' 가 목록에 없다")
    return problems


# ─────────────────────────────────────────────── 생성
def build(rows):
    sheet = []
    # 1행 제목 · 2행 부제 · 3행 빈 줄 · 4행 헤더 · 5행부터 데이터 (v4 와 같다)
    sheet.append((26, [(1, TITLE, 1)]))
    sheet.append((30, [(1, SUBTITLE, 7)]))
    sheet.append((6, []))
    sheet.append((30, [(c, name, 2) for c, name in enumerate(HEADER, start=1)]))

    for _lineno, cells in rows:
        sheet.append((None, [(c, v, COL_STYLE[c - 1]) for c, v in enumerate(cells, start=1)]))

    last = len(sheet)
    validations = ('<dataValidations count="2">'
                   + dropdown(f"F5:F{last}", STATUSES)
                   + dropdown(f"G5:G{last}", PRIORITIES)
                   + '</dataValidations>')

    return sheet_xml(sheet, widths=WIDTHS, freeze=("A5", 0, 4),
                     autofilter=f"A4:K{last}", validations=validations)


def main():
    rows = parse()
    problems = check(rows)
    if problems:
        print(f"검사 실패 {len(problems)}건 — 파일을 만들지 않는다\n")
        for p in problems:
            print("  x " + p)
        raise SystemExit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels", WB_RELS)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/worksheets/sheet1.xml", build(rows))

    counts = {}
    for _l, c in rows:
        counts[c[5]] = counts.get(c[5], 0) + 1
    print(f"  {OUT.relative_to(ROOT)}")
    print(f"  기능 {len(rows)}건 · {OUT.stat().st_size:,} bytes")
    print("  상태별 " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
