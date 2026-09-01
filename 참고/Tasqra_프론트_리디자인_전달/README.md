# Tasqra 프론트 리디자인 전달

## 기준

- 대상 레포: `ParkSehyeon1009/Tasqra`
- 대상 브랜치: `fix/document-type-user-correction`
- 기준 커밋: `32eabfc4caf4582f173887d71a59fe4dfbb4e360`
- 패치: `frontend-redesign-portfolio-dashboard.patch`

## 포함 내용

- 공개 랜딩·로그인·회원가입 화면 리디자인
- 로그인 직후 실제 데이터 기반 전역 프로젝트 대시보드
- 프로젝트 내부 화면의 통일된 반응형 디자인
- 기존 테마 프리셋과 CSS 변수 구조 보존
- 신규 문서 유형 8종 및 레거시 `BILLING` → `ETC` 읽기 호환
- 프로젝트 수에 비례하던 대시보드 요청을 단일 포트폴리오 집계 API로 변경

적용과 검증 명령은 전달 채팅의 PowerShell 명령을 사용한다. 팀 레포의 커밋과 푸시는 사용자가 검증 후 직접 수행한다.
