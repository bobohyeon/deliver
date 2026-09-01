# Tasqra 프론트 리디자인 전달

## 기준

- 대상 레포: `ParkSehyeon1009/Tasqra`
- 대상 브랜치: `fix/document-type-user-correction`
- 기준 커밋: `32eabfc4caf4582f173887d71a59fe4dfbb4e360`
- 최초 패치: `frontend-redesign-portfolio-dashboard.patch`
- 1차 교정 전체 패치: `frontend-redesign-portfolio-dashboard-v2.patch`
- 최신 후속 교정 전체 패치: `frontend-redesign-portfolio-dashboard-v3.patch`

## v2 포함 내용

- 공개 랜딩을 `tasqra_landing_mainhero_v2.html`과 같은 구조·문구·완성 hero 이미지로 교정
- 전역 `/projects` 대시보드에도 공통 프로젝트 사이드바 표시
- 프로젝트 ID별로 고정된 5가지 색 표식을 사이드바와 목록에 동일 적용
- 산출물 미리보기 영역을 처음부터 표시하고, 내용이 없으면 서버 사유를 화면에 표시
- 검색·금액·산출물 탭이 무관한 문서/멤버 로딩을 기다리지 않도록 교정
- 공개 랜딩·로그인·회원가입 및 프로젝트 내부 반응형 디자인
- 기존 테마 프리셋과 CSS 변수 구조 보존
- 신규 문서 유형 8종 및 레거시 `BILLING` → `ETC` 읽기 호환
- 프로젝트 수에 비례하던 대시보드 요청을 단일 포트폴리오 집계 API로 변경

## v3 추가 교정

- LLM 개요 생성 중인 산출물 미리보기에 원형 로딩 표시와 예상 대기 안내 추가
- 산출물 표의 문서 유형을 `RFP`·`REPORT` 코드 대신 한국어 카테고리명으로 표시
- 전역 프로젝트 목록에 `진행 중`·`보관됨` 상태 토글과 상태별 색 적용
- 메인 대시보드와 사이드바의 프로젝트명 크기를 2px 확대
- 문서 목록의 `추가 문서가 있나요?` 안내 섹션 제거
- 문서 유형 8종과 미분류 배지에 서로 다른 색 적용

이미 v2 패치를 적용한 작업 트리에서는 v2를 역적용한 뒤 v3 전체 패치를 적용한다. 팀 레포의 커밋과 푸시는 사용자가 검증 후 직접 수행한다.
