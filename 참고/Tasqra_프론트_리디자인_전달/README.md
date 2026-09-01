# Tasqra 프론트 리디자인 전달

## 기준

- 대상 레포: `ParkSehyeon1009/Tasqra`
- 대상 브랜치: `fix/document-type-user-correction`
- 기준 커밋: `32eabfc4caf4582f173887d71a59fe4dfbb4e360`
- 최초 패치: `frontend-redesign-portfolio-dashboard.patch`
- 교정 반영 전체 패치: `frontend-redesign-portfolio-dashboard-v2.patch`

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

이미 최초 패치를 적용한 작업 트리에서는 최초 패치를 역적용한 뒤 v2 전체 패치를 적용한다. 팀 레포의 커밋과 푸시는 사용자가 검증 후 직접 수행한다.
