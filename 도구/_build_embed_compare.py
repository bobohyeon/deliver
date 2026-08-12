# ─────────────────────────────────────────────────────────────────────────────
# 이 파일의 책임
#   RAG 임베딩 모델 선정 시험의 비교분석표를 XLSX 로 만든다.
#   회의에서 한 파일만 열어 "무엇을 비교했고 그래서 결론이 무엇인가" 를
#   순서대로 볼 수 있게 시트를 배치한다.
#
# 다른 파일과의 관계
#   입력  없음. 측정 결과를 이 파일 상단 상수에 박아둔다.
#         원본 수치는 도구/embed-test/results/*.csv 와 결과서 7.5절이다.
#   출력  관리/RAG_임베딩모델_비교분석표.xlsx
#   xlsx 생성 방식과 스타일은 도구/_build_wbs_v2.py 와 같다.
#   openpyxl 이 없는 환경이라 zipfile 로 OOXML 을 직접 쓴다.
#
# Spring 비교
#   Apache POI 로 XSSFWorkbook 을 직접 조립하는 것과 같다.
#   openpyxl(= POI 래퍼) 없이 zip 안의 XML 을 손으로 쓰는 것이라
#   POI 를 안 쓰고 sheet1.xml 을 StringBuilder 로 만드는 셈이다.
# ─────────────────────────────────────────────────────────────────────────────
"""RAG 임베딩 모델 비교분석표 생성. 실행: python 도구/_build_embed_compare.py"""

import pathlib
import zipfile
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "관리" / "RAG_임베딩모델_비교분석표.xlsx"

N_ALL, N_OV, N_NO = 73, 39, 34
N_CHUNK, N_DOC = 127, 5

# ── 4차 실측 (도구/embed-test 로 측정. CPU)
#    (표시명, 저장소, 차원, 계열, 한국어, 적재초, 임베딩초, 100청크초, 메모리MB)
MODELS = [
    ("KURE-v1", "nlpai-lab/KURE-v1", 1024, "bge 기반", "한국어 특화",
     6.4, 50.3, 39.58, 1534),
    ("bge-m3", "BAAI/bge-m3", 1024, "bge", "다국어",
     7.4, 51.7, 40.70, 1552),
    ("e5-large", "intfloat/multilingual-e5-large", 1024, "e5", "다국어 원본",
     35.4, 48.9, 38.51, 1456),
    ("e5-small-ko-v2", "dragonkue/multilingual-e5-small-ko-v2", 384, "e5", "한국어 튜닝",
     6.6, 4.7, 3.67, 421),
    ("e5-base", "intfloat/multilingual-e5-base", 768, "e5", "다국어 원본",
     30.6, 13.9, 10.97, 636),
]

# 맞춘 질의 개수. (R@1, R@3, R@5, R@10) · MRR
#   no_overlap  뜻으로만 찾아야 하는 질의 34개  ← 우리 판단 기준
#   overlap     글자가 겹치는 질의 39개
SCORES = {
    #                 no_overlap(34)        MRR      overlap(39)          MRR      all(73)              MRR
    "KURE-v1":       ((12, 22, 27, 29), 0.533, (25, 31, 33, 36), 0.731, (37, 53, 60, 65), 0.639),
    "bge-m3":        ((12, 19, 26, 28), 0.499, (26, 32, 32, 34), 0.745, (38, 51, 58, 62), 0.631),
    "e5-large":      ((14, 16, 23, 25), 0.492, (29, 32, 33, 34), 0.793, (43, 48, 56, 59), 0.653),
    "e5-small-ko-v2":((10, 14, 14, 24), 0.373, (27, 35, 38, 39), 0.799, (37, 49, 52, 63), 0.601),
    "e5-base":       ((8, 12, 13, 18),  0.314, (28, 30, 32, 35), 0.766, (36, 42, 45, 53), 0.555),
}

# ── API 모델. 공개 문서 기준이고 우리가 재지 않았다.
#    (모델, 제공자, 지원 차원, 최대 입력 토큰, 1M토큰 단가, 한국어, 비고)
API_MODELS = [
    ("voyage-3.5", "Voyage AI (MongoDB)", "256 · 512 · 1024(기본) · 2048",
     "32,000", "$0.06", "다국어",
     "1024 가 기본이라 컬럼을 안 바꾸고 비교할 수 있다"),
    ("voyage-3.5-lite", "Voyage AI (MongoDB)", "256 · 512 · 1024(기본) · 2048",
     "32,000", "$0.02", "다국어",
     "같은 차원에 더 싸다"),
    ("text-embedding-3-large", "OpenAI", "256~3072 임의 지정 (기본 3072)",
     "8,192", "$0.13", "다국어",
     "1024 로 줄여서 쓸 수 있다"),
    ("text-embedding-3-small", "OpenAI", "512 · 1536",
     "8,192", "$0.02", "다국어",
     "1024 를 지원하지 않는다"),
    ("gemini-embedding-2", "Google", "768 · 1536 · 3072",
     "8,192", "$0.15", "다국어",
     "1024 가 없다 · Preview · 멀티모달"),
]

# ── 판단 기준. (기준, 왜 보는가, 로컬 KURE-v1, API 모델, 우리 판단)
CRITERIA = [
    ("한국어 검색 성능", "문서가 전부 한국어다",
     "실측 27/34 로 1위", "재지 않았다",
     "실측이 있는 쪽을 택한다"),
    ("문서가 외부로 나가나", "입찰·계약 문서다",
     "안 나간다", "임베딩은 문서 전량이 나간다",
     "이것이 API 의 핵심 쟁점이다"),
    ("비용", "예산 제약",
     "0원 (CPU 시간만)", "100문서당 $0.06~0.15",
     "비용은 쟁점이 아니다. 둘 다 무시할 수준"),
    ("검색 시 외부 의존", "검색이 멈추면 기능이 죽는다",
     "없다", "질의마다 외부 호출. 지연·장애가 그대로 온다",
     "로컬이 유리하다"),
    ("최대 입력 길이", "청크가 한도를 넘으면 조용히 잘린다",
     "미실측 — 확인 필요", "8,192 ~ 32,000 (문서 기준)",
     "우리 청크는 450자라 아직 문제 없어 보이지만 재지 않았다"),
    ("차원 유연성", "컬럼을 바꾸면 재임베딩이다",
     "모델마다 고정", "임의 지정 가능 (OpenAI)",
     "1024 로 맞추면 양쪽 다 가능하다"),
    ("교체 비용", "판단이 틀렸을 때",
     "차원 같으면 재임베딩 없음", "같음",
     "1024 를 택한 이유다"),
    ("GPU 필요 여부", "우리 개발기에 GPU 가 없다",
     "CPU 로 돌아간다 (실측)", "필요 없다",
     "둘 다 문제 없다"),
    ("라이선스", "과제 제출물이다",
     "미확인 — 확인 필요", "상용 API 약관",
     "로컬 모델 라이선스를 확인해야 한다"),
]

# ── 측정 이력. (회차, 무엇을 바꿨나, 왜, 결과)
HISTORY = [
    ("1차", "모델 3개 · 질의 40개",
     "첫 측정",
     "1024 두 모델이 384 를 앞섰다. 한 모델만 맞춘 문항이 3개 있었다"),
    ("2차", "질의 40 → 73 · overlap 라벨 추가",
     "글자만 겹쳐서 맞춘 것을 걸러내야 했다",
     "no_overlap 에서 격차가 커졌다. 이 지표를 기준으로 삼기로 했다"),
    ("3차", "평가셋 5문항 삭제 · 4문항 정답 확장",
     "측정 불가 문항(정답 청크 60개 이상)과 모호 문항을 뺐다",
     "수치가 소폭 변했다. 1차 수치는 지우지 않고 병기했다"),
    ("4차", "모델 3 → 5 (e5-base 768 · e5-large 1024 추가)",
     "차원 효과와 계열 효과를 분리해야 했다",
     "차원 단조성이 깨졌다. 한국어 특화 효과가 확인됐다"),
]

# ── 남은 확인. (항목, 왜 필요한가, 지금 상태)
OPEN = [
    ("로컬 모델 라이선스", "과제 제출물에 쓸 수 있는지",
     "미확인. KURE-v1 · bge-m3 둘 다 봐야 한다"),
    ("모델 최대 입력 길이 실측", "청크가 조용히 잘리는지",
     "미확인. max_seq_length 를 찍어보면 된다"),
    ("DB 이미지 pgvector 교체", "리비전 0011 이 돌아가려면",
     "docker-compose.yml 이 postgres:16-alpine 이다. 팀 합의 필요"),
    ("requirements.txt 에 pgvector", "SQLAlchemy Vector 타입",
     "없다. 추가 필요"),
    ("KURE-v1 대 bge-m3", "기본 모델 확정",
     "R@5 1문항 차이. 평가셋을 키워야 갈린다"),
    ("API 모델 실측 (2라운드)", "다국어 API 가 한국어 특화를 이기는지",
     "안 했다. 데이터 유출 허용 여부가 선행 판단이다"),
]


# ─────────────────────────────────────────────── xlsx 유틸 (_build_wbs_v2.py 와 같다)

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
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>')


def sheet_xml(rows, widths=None, freeze=None, merges=None):
    cols = ""
    if widths:
        cols = "<cols>" + "".join(
            f'<col min="{c}" max="{c2}" width="{w}" customWidth="1"/>'
            for c, c2, w in widths) + "</cols>"

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

    mg = ""
    if merges:
        mg = (f'<mergeCells count="{len(merges)}">'
              + "".join(f'<mergeCell ref="{r}"/>' for r in merges)
              + "</mergeCells>")

    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
            f'{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16.5"/>'
            f'{cols}<sheetData>{"".join(body)}</sheetData>{mg}'
            '<pageMargins left="0.2" right="0.2" top="0.4" bottom="0.4" '
            'header="0.3" footer="0.3"/></worksheet>')


STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2">
<numFmt numFmtId="164" formatCode="0.0"/>
<numFmt numFmtId="165" formatCode="0.000"/>
</numFmts>
<fonts count="9">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="15"/><name val="맑은 고딕"/></font>
<font><b/><sz val="9"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="11"/><name val="맑은 고딕"/></font>
<font><i/><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="5">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF000000"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE0E0E0"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF6F6F6"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFC8C8C8"/></left>
<right style="thin"><color rgb="FFC8C8C8"/></right>
<top style="thin"><color rgb="FFC8C8C8"/></top>
<bottom style="thin"><color rgb="FFC8C8C8"/></bottom>
<diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="16">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="5" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="6" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="165" fontId="3" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="7" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="8" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

S_TITLE, S_HDR, S_GROUP, S_TXT, S_CEN, S_CENB = 1, 2, 3, 4, 5, 6
S_NOTE, S_SUB, S_TXTB, S_MARK = 7, 8, 9, 10
S_N1, S_N3, S_N3B, S_H2, S_ITAL = 11, 12, 13, 14, 15


def row(cells, height=None):
    return (height, cells)


def title_rows(title, subtitle):
    return [
        row([(1, title, S_TITLE)], 26),
        row([(1, subtitle, S_NOTE)], 15),
        row([]),
    ]


def hdr(labels, start=1):
    return row([(start + i, t, S_HDR) for i, t in enumerate(labels)], 30)


def section(text, ncol, start=1):
    return row([(start, text, S_GROUP)]
               + [(start + i, "", S_GROUP) for i in range(1, ncol)], 20)


# ─────────────────────────────────────────────── 시트 1. 결론

def build_conclusion():
    rows = title_rows(
        "RAG 임베딩 모델 선정 — 비교분석표",
        f"측정 4회 · 모델 5개 · 질의 {N_ALL}개 (뜻으로만 {N_NO} · 글자겹침 {N_OV}) · "
        f"청크 {N_CHUNK}개 / 문서 {N_DOC}건 · CPU 실행 · 2026-08-12")

    def kv(k, v, why, style=S_TXT):
        return row([(1, k, S_TXTB), (2, v, style), (3, why, S_SUB)], 32)

    rows += [
        section("결론 — 무엇을 정했나", 3),
        hdr(["항목", "정한 것", "근거"]),
        kv("컬럼 차원", "vector(1024)",
           "실측 최고가 1024 이고, 후보 4종 중 셋이 1024 를 지원한다"),
        kv("기본 모델", "nlpai-lab/KURE-v1 (1024)",
           "뜻으로만 찾는 질의 34개 중 27개. 5개 모델 중 1위"),
        kv("대안", "BAAI/bge-m3 (1024)",
           "차원이 같아 재임베딩 없이 바꿔 끼울 수 있다"),
        kv("탈락", "e5-small-ko-v2 (384) · e5-base (768)",
           "384 는 14개, 768 은 13개. 1024 의 절반이다"),
        kv("API 모델", "지금은 안 쓴다. 배제도 안 한다",
           "셋 다 다국어이고 한국어 성능을 재지 않았다"),
        kv("모델 확정", "보류",
           "KURE 와 bge 는 R@5 1문항 차이. 표본 34개에서 노이즈 범위"),
        row([]),

        section("그래서 왜 이 결론인가 — 근거 넷", 3),
        hdr(["번호", "확인한 것", "무엇을 뜻하나"]),
        row([(1, "1", S_CENB),
             (2, "1024 차원이 384·768 을 크게 앞섰다", S_TXTB),
             (3, "1024 는 23~27개 · 768 은 13개 · 384 는 14개. "
                 "컬럼 차원을 1024 로 두는 1차 근거다", S_TXT)], 32),
        row([(1, "2", S_CENB),
             (2, "차원이 높으면 좋다는 것은 성립하지 않는다", S_TXTB),
             (3, "384 를 768 로 두 배 올렸는데 점수가 내려갔다 (14 → 13). "
                 "top10 까지 보면 24 → 18 로 6문항 차이다. "
                 "차원은 상한만 정하고 실제 성능은 계열과 학습이 정한다", S_TXT)], 44),
        row([(1, "3", S_CENB),
             (2, "한국어 특화가 효과 있다", S_TXTB),
             (3, "차원을 1024 로 고정하고 계열만 바꾸니 "
                 "한국어 특화 27 대 다국어 원본 23 으로 4문항 차이다. "
                 "R@3 에서는 22 대 16 으로 6문항이다", S_TXT)], 44),
        row([(1, "4", S_CENB),
             (2, "그래서 다국어 API 로 갈 근거가 약해졌다", S_TXTB),
             (3, "Voyage · OpenAI · Gemini 셋 다 다국어이고 한국어 특화가 아니다. "
                 "다국어가 한국어 특화를 이기지 못한 사례를 직접 만들었으므로 "
                 "문서 전량을 외부로 보낼 근거가 약하다", S_TXT)], 44),
        row([]),

        section("주의 — 이 표를 잘못 읽는 방법", 3),
        hdr(["잘못된 읽기", "왜 틀렸나", "맞는 읽기"]),
        row([(1, "API 모델은 쓸 필요 없다", S_TXTB),
             (2, "우리는 API 를 재지 않았다. e5-large 한 개로 "
                 "다국어 전체를 판단할 수 없다. 그 모델들은 e5-large 보다 "
                 "크고 최신이다", S_TXT),
             (3, "재보지 않고 배제하는 것도 근거 없는 판단이다. "
                 "2라운드로 남긴다", S_TXT)], 44),
        row([(1, "KURE-v1 이 최고 모델이다", S_TXTB),
             (2, "bge-m3 와 1문항 차이다. R@1 에서는 e5-large 가 "
                 "14 로 1위다", S_TXT),
             (3, "top5 를 보여주는 화면이라 R@5 기준이 맞다. "
                 "1건만 보여주면 판단이 달라진다", S_TXT)], 44),
        row([(1, "384 는 나쁜 차원이다", S_TXTB),
             (2, "384 모델이 글자겹침 질의에서는 38/39 로 1위였다", S_TXT),
             (3, "차원이 아니라 용도가 다르다. 뜻으로 찾는 데 약하다", S_TXT)], 32),
        row([(1, "비용 때문에 로컬을 골랐다", S_TXTB),
             (2, "API 비용은 100문서당 $0.06~0.15 다. 무시할 수준이다", S_TXT),
             (3, "쟁점은 비용이 아니라 문서가 외부로 나가는 것이다", S_TXT)], 32),
        row([]),

        section("이 결론으로 할 수 있는 것", 3),
        hdr(["할 일", "내용", "선행 조건"]),
        kv("리비전 0011", "CREATE EXTENSION vector · document_chunks embedding vector(1024)",
           "DB 이미지를 pgvector 포함본으로 교체 (팀 합의 필요)"),
        kv("requirements.txt", "pgvector 패키지 추가",
           "SQLAlchemy 에서 Vector 타입을 쓰려면 필요하다"),
        kv("검색 API 구현", "POST /api/projects/{id}/search · mode=hybrid",
           "계약 초안은 관리/API_계약_RAG_검색_초안.md"),
        row([]),
        row([(1, "수치의 원본은 도구/embed-test/results/ 의 CSV 이고, "
                "판단 근거 전문은 관리/RAG_임베딩모델_선정_결과서.md 다.", S_ITAL)], 15),
    ]
    return sheet_xml(rows, [(1, 1, 22), (2, 2, 42), (3, 3, 64)], freeze=("A4", 0, 3))


# ─────────────────────────────────────────────── 시트 2. 실측 검색품질

def build_quality():
    rows = title_rows(
        "실측 — 검색 품질",
        f"숫자는 맞춘 질의 개수다. 뜻으로만 {N_NO}개 · 글자겹침 {N_OV}개 · 전체 {N_ALL}개. "
        "R@5 = 상위 5개 안에 정답이 있었다")

    rows += [
        row([(1, "", S_HDR), (2, "", S_HDR), (3, "", S_HDR), (4, "", S_HDR),
             (5, f"뜻으로만 찾아야 하는 질의 {N_NO}개  ← 판단 기준", S_HDR),
             (6, "", S_HDR), (7, "", S_HDR), (8, "", S_HDR), (9, "", S_HDR),
             (10, f"글자가 겹치는 질의 {N_OV}개", S_HDR),
             (11, "", S_HDR), (12, "", S_HDR), (13, "", S_HDR), (14, "", S_HDR),
             (15, f"전체 {N_ALL}개", S_HDR),
             (16, "", S_HDR), (17, "", S_HDR), (18, "", S_HDR), (19, "", S_HDR)], 22),
        hdr(["모델", "차원", "계열", "한국어",
             "R@1", "R@3", "R@5", "R@10", "MRR",
             "R@1", "R@3", "R@5", "R@10", "MRR",
             "R@1", "R@3", "R@5", "R@10", "MRR"]),
    ]

    for name, repo, dim, fam, ko, _l, _e, _s, _m in MODELS:
        no, no_mrr, ov, ov_mrr, al, al_mrr = SCORES[name]
        best = (name == "KURE-v1")
        st = S_TXTB if best else S_TXT
        cn = S_CENB if best else S_CEN
        rows.append(row(
            [(1, name, st), (2, dim, cn), (3, fam, S_CEN), (4, ko, S_CEN)]
            + [(5 + i, v, cn) for i, v in enumerate(no)] + [(9, no_mrr, S_N3B if best else S_N3)]
            + [(10 + i, v, S_CEN) for i, v in enumerate(ov)] + [(14, ov_mrr, S_N3)]
            + [(15 + i, v, S_CEN) for i, v in enumerate(al)] + [(19, al_mrr, S_N3)], 20))

    rows += [
        row([]),
        section("이 표에서 읽을 것", 4),
        hdr(["관찰", "내용"]),
        row([(1, "1위는 KURE-v1", S_TXTB),
             (2, "뜻으로만 찾는 질의에서 27/34. 2위 bge-m3 는 26, 3위 e5-large 는 23 이다", S_TXT)], 20),
        row([(1, "R@1 만 보면 순위가 뒤집힌다", S_TXTB),
             (2, "e5-large 가 14 로 1위다. 맞출 때는 1등으로 맞추고 틀릴 때는 완전히 틀린다. "
                 "우리는 top5 를 보여주므로 R@5 기준이 맞다", S_TXT)], 32),
        row([(1, "글자겹침 질의는 판단에 못 쓴다", S_TXTB),
             (2, "384 모델이 38/39 로 1위다. 질의에 쓴 단어가 청크에 그대로 있으면 "
                 "작은 모델도 맞춘다. 그래서 뜻으로만 찾는 질의를 따로 뒀다", S_TXT)], 32),
        row([(1, "768 이 384 보다 낮다", S_TXTB),
             (2, "13 대 14 다. R@10 에서는 18 대 24 로 6문항 차이다. 차원분석 시트를 본다", S_TXT)], 20),
    ]

    widths = [(1, 1, 20), (2, 2, 7), (3, 3, 11), (4, 4, 13)] + \
             [(c, c, 6.5) for c in range(5, 20)]
    return sheet_xml(rows, widths, freeze=("E5", 4, 4),
                     merges=["E4:I4", "J4:N4", "O4:S4"])


# ─────────────────────────────────────────────── 시트 3. 실측 실행비용

def build_cost():
    rows = title_rows(
        "실측 — 실행 비용 (CPU)",
        f"GPU 없이 쟀다. 청크 {N_CHUNK}개를 임베딩한 시간이다. "
        "메모리는 모델 적재 후 증가분이다")

    rows += [hdr(["모델", "차원", "적재 초", "임베딩 초",
                  "100청크당 초", "메모리 MB", "뜻으로만 R@5", "1문항당 비용"])]

    for name, repo, dim, fam, ko, load, enc, per100, mem in MODELS:
        no = SCORES[name][0]
        st = S_TXTB if name == "KURE-v1" else S_TXT
        rows.append(row([
            (1, name, st), (2, dim, S_CEN),
            (3, load, S_N1), (4, enc, S_N1), (5, per100, S_N1),
            (6, mem, S_CEN), (7, no[2], S_CENB),
            (8, round(per100 / no[2], 2), S_N1),
        ], 20))

    rows += [
        row([]),
        row([(1, "1문항당 비용 = 100청크당 초 ÷ 맞춘 개수. "
                "낮을수록 같은 성능을 싸게 얻는다는 뜻이다.", S_ITAL)], 15),
        row([]),
        section("이 표에서 읽을 것", 3),
        hdr(["관찰", "내용"]),
        row([(1, "1024 세 모델은 속도가 거의 같다", S_TXTB),
             (2, "38.5 · 39.6 · 40.7 초. 성능만 보고 골라도 된다는 뜻이다", S_TXT)], 20),
        row([(1, "384 는 11배 빠르다", S_TXTB),
             (2, "3.67 초 대 39.58 초. 메모리도 421MB 대 1,534MB 다. "
                 "성능이 절반이라 못 쓰지만, 만약 문서가 수만 건이면 다시 볼 값이다", S_TXT)], 32),
        row([(1, "768 이 좋은 중간값이었다", S_TXTB),
             (2, "10.97 초 · 636MB. 1024 의 3.5배 빠르고 메모리는 절반 이하다. "
                 "성능이 따라왔다면 좋은 타협점이었을 텐데 아니었다", S_TXT)], 32),
        row([(1, "우리 규모에서는 속도가 쟁점이 아니다", S_TXTB),
             (2, f"문서 {N_DOC}건이 {N_CHUNK}청크다. 1024 모델로 50초다. "
                 "문서 100건이면 약 17분이고 업로드 시 한 번만 하면 된다", S_TXT)], 32),
    ]

    return sheet_xml(rows, [(1, 1, 20), (2, 2, 7), (3, 3, 10), (4, 4, 11),
                            (5, 5, 13), (6, 6, 11), (7, 7, 13), (8, 8, 13)],
                     freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 시트 4. 차원 분석

def build_dimension():
    rows = title_rows(
        "차원 분석 — 흔히 보는 차원 표가 우리 실측과 맞지 않았다",
        "차원 효과와 계열 효과를 분리하려고 e5 원본 계열의 768 과 1024 를 넣었다")

    rows += [
        section("실측 — 차원 순서대로", 5),
        hdr(["차원", "모델", "계열", "한국어", "뜻으로만 R@5", "뜻으로만 R@10"]),
    ]
    for name, repo, dim, fam, ko, *_ in sorted(MODELS, key=lambda m: m[2]):
        no = SCORES[name][0]
        odd = dim == 768
        rows.append(row([
            (1, dim, S_CENB if odd else S_CEN), (2, name, S_TXTB if odd else S_TXT),
            (3, fam, S_CEN), (4, ko, S_CEN),
            (5, no[2], S_CENB if odd else S_CEN),
            (6, no[3], S_CENB if odd else S_CEN)], 20))

    rows += [
        row([]),
        row([(1, "384 를 768 로 두 배 올렸는데 R@5 가 14 에서 13 으로 내려갔다. "
                "R@10 은 24 에서 18 로 6문항 내려갔다.", S_TXTB)], 20),
        row([]),

        section("왜 이런 일이 생기나 — 세 요인이 섞여 있다", 4),
        hdr(["요인", "효과 크기", "근거", "숫자"]),
        row([(1, "모델 크기 · 계열", S_TXTB), (2, "가장 크다", S_CENB),
             (3, "같은 e5 원본 계열 안에서 768 → 1024", S_TXT),
             (4, "13 → 23 (10문항)", S_CEN)], 20),
        row([(1, "한국어 튜닝", S_TXTB), (2, "차원 2배보다 크다", S_CENB),
             (3, "384 한국어 튜닝판이 768 다국어 원본을 이겼다", S_TXT),
             (4, "14 > 13", S_CEN)], 20),
        row([(1, "차원 자체", S_TXTB), (2, "작다", S_CEN),
             (3, "같은 1024 안에서 갈린다", S_TXT),
             (4, "23 · 26 · 27", S_CEN)], 20),
        row([]),
        row([(1, "차원은 상한만 정하고 실제 성능은 계열과 학습이 정한다.", S_H2)], 22),
        row([]),

        section("그래서 컬럼 차원을 1024 로 두는 근거가 둘이다", 3),
        hdr(["근거", "내용"]),
        row([(1, "실측 최고", S_TXTB),
             (2, "1024 세 모델이 23 · 26 · 27 이고, 768 은 13, 384 는 14 다", S_TXT)], 20),
        row([(1, "후보 호환성", S_TXTB),
             (2, "후보 4종 중 셋이 1024 를 지원한다 — 로컬 한국어 모델 · Voyage(기본값) · "
                 "OpenAI large(임의 지정). Gemini 만 1024 가 없다", S_TXT)], 32),
        row([]),

        section("기각한 차원과 이유", 3),
        hdr(["차원", "기각 이유"]),
        row([(1, "384", S_TXTB), (2, "뜻으로만 찾는 질의에서 14/34. 1024 의 절반이다", S_TXT)], 20),
        row([(1, "768", S_TXTB),
             (2, "13/34 로 384 보다도 낮았다. 게다가 Voyage 와 로컬 한국어 모델을 "
                 "쓸 수 없게 된다", S_TXT)], 32),
        row([(1, "1536 · 3072", S_TXTB),
             (2, "저장 용량이 1.5~3배로 늘고, 이 차원을 내는 로컬 모델이 없다. "
                 "API 에 묶인다", S_TXT)], 32),
    ]
    return sheet_xml(rows, [(1, 1, 18), (2, 2, 22), (3, 3, 42), (4, 4, 18),
                            (5, 5, 15), (6, 6, 15)], freeze=("A4", 0, 3))


# ─────────────────────────────────────────────── 시트 5. API 모델 사양

def build_api():
    rows = title_rows(
        "API 모델 사양 — 공개 문서 기준이고 우리가 재지 않았다",
        "이 시트의 수치는 제공자 문서를 읽은 것이다. 검색 성능을 실측한 값이 아니다. "
        "실측 시트와 같은 기준으로 비교하면 안 된다")

    rows += [
        row([(1, "주의 — 아래 표에 검색 성능 열이 없는 것은 재지 않았기 때문이다. "
                "우리 문서·우리 질의로 재야 비교할 수 있다.", S_H2)], 22),
        row([]),
        hdr(["모델", "제공자", "지원 차원", "최대 입력 토큰",
             "1M 토큰 단가", "한국어", "우리 관점 비고"]),
    ]
    for m, prov, dims, maxin, price, ko, note in API_MODELS:
        first = m == "voyage-3.5"
        rows.append(row([
            (1, m, S_TXTB if first else S_TXT), (2, prov, S_TXT),
            (3, dims, S_TXT), (4, maxin, S_CEN), (5, price, S_CEN),
            (6, ko, S_CEN), (7, note, S_TXT)], 24))

    rows += [
        row([]),
        section("비교 — 로컬 실측치를 같은 축에 놓으면", 5),
        hdr(["구분", "모델", "지원 차원", "최대 입력 토큰", "비용", "한국어 실측"]),
        row([(1, "로컬 · 실측", S_TXTB), (2, "KURE-v1", S_TXTB), (3, "1024 고정", S_TXT),
             (4, "미실측", S_CEN), (5, "0원 · CPU 40초/100청크", S_TXT),
             (6, "27 / 34", S_CENB)], 24),
        row([(1, "로컬 · 실측", S_TXT), (2, "bge-m3", S_TXT), (3, "1024 고정", S_TXT),
             (4, "미실측", S_CEN), (5, "0원 · CPU 41초/100청크", S_TXT),
             (6, "26 / 34", S_CEN)], 24),
        row([(1, "API · 미실측", S_TXT), (2, "voyage-3.5", S_TXT),
             (3, "1024 기본", S_TXT), (4, "32,000", S_CEN),
             (5, "$0.06 / 1M 토큰", S_TXT), (6, "모른다", S_CEN)], 24),
        row([(1, "API · 미실측", S_TXT), (2, "text-embedding-3-large", S_TXT),
             (3, "1024 로 지정 가능", S_TXT), (4, "8,192", S_CEN),
             (5, "$0.13 / 1M 토큰", S_TXT), (6, "모른다", S_CEN)], 24),
        row([(1, "API · 미실측", S_TXT), (2, "gemini-embedding-2", S_TXT),
             (3, "768 · 1536 · 3072", S_TXT), (4, "8,192", S_CEN),
             (5, "$0.15 / 1M 토큰", S_TXT), (6, "모른다", S_CEN)], 24),
        row([]),

        section("비용이 실제로 얼마인가 — 우리 규모로 환산", 4),
        hdr(["기준", "토큰 추정", "voyage-3.5", "text-embedding-3-large"]),
        row([(1, f"문서 {N_DOC}건 (이번 시험 코퍼스)", S_TXT), (2, "약 5만 토큰", S_CEN),
             (3, "$0.003", S_CEN), (4, "$0.007", S_CEN)], 20),
        row([(1, "문서 100건", S_TXT), (2, "약 100만 토큰", S_CEN),
             (3, "$0.06", S_CEN), (4, "$0.13", S_CEN)], 20),
        row([(1, "문서 1,000건", S_TXT), (2, "약 1,000만 토큰", S_CEN),
             (3, "$0.60", S_CEN), (4, "$1.30", S_CEN)], 20),
        row([]),
        row([(1, "토큰 추정은 청크 127개 · 평균 400자 기준의 어림이다. "
                "한국어는 토크나이저에 따라 글자당 0.7~1.5 토큰으로 갈린다.", S_ITAL)], 15),
        row([(1, "비용은 쟁점이 아니다. 문서 1,000건을 다 임베딩해도 1달러 안이다.", S_H2)], 22),
        row([]),

        section("그러면 진짜 쟁점은 무엇인가", 3),
        hdr(["쟁점", "내용"]),
        row([(1, "문서가 외부로 나간다", S_TXTB),
             (2, "임베딩은 문서 전량을 보낸다. 요약은 사용자가 요청한 1건만 보내지만 "
                 "임베딩은 업로드된 모든 문서가 대상이다. 입찰·계약 문서다", S_TXT)], 32),
        row([(1, "검색할 때마다 외부 호출", S_TXTB),
             (2, "질의도 임베딩해야 한다. 네트워크 지연과 장애가 검색 기능에 그대로 온다. "
                 "로컬은 그런 의존이 없다", S_TXT)], 32),
        row([(1, "한국어 성능을 모른다", S_TXTB),
             (2, "우리 실측에서 다국어 원본이 한국어 특화에 4문항 뒤졌다. "
                 "API 모델도 다국어다. 재보지 않으면 알 수 없다", S_TXT)], 32),
        row([(1, "Gemini 멀티모달은 쓰면 안 된다", S_TXTB),
             (2, "PDF 를 직접 넣으면 사람이 고친 OCR 텍스트가 반영되지 않는다. "
                 "OCR 검수가 우리 차별점인데 그것을 무력화한다", S_TXT)], 32),
        row([]),

        section("2라운드로 남기는 것", 3),
        hdr(["순서", "무엇을", "왜 그 순서인가"]),
        row([(1, "1", S_CENB), (2, "데이터 유출 허용 여부를 팀에서 정한다", S_TXTB),
             (3, "이것이 안 되면 성능을 재도 못 쓴다", S_TXT)], 20),
        row([(1, "2", S_CENB), (2, "voyage-3.5 를 우리 질의 73개로 재본다", S_TXTB),
             (3, "1024 가 기본이라 컬럼을 안 바꾸고 비교된다", S_TXT)], 20),
        row([(1, "3", S_CENB), (2, "이겨야 얼마나 이기는지 본다", S_TXT),
             (3, "KURE 27 을 못 넘으면 볼 이유가 없다", S_TXT)], 20),
        row([]),
        row([(1, "출처 — docs.voyageai.com/docs/embeddings · "
                "developers.openai.com/api/docs/guides/embeddings · "
                "deepmind.google/models/gemini/embedding/ (2026-08 확인)", S_ITAL)], 15),
    ]
    return sheet_xml(rows, [(1, 1, 24), (2, 2, 24), (3, 3, 30), (4, 4, 15),
                            (5, 5, 20), (6, 6, 11), (7, 7, 46)], freeze=("A6", 0, 5))


# ─────────────────────────────────────────────── 시트 6. 판단 기준

def build_criteria():
    rows = title_rows(
        "판단 기준 — 무엇을 보고 골랐나",
        "성능만 본 것이 아니다. 아래 9개 축으로 보고 정했다")

    rows += [hdr(["기준", "왜 보는가", "로컬 KURE-v1", "API 모델", "우리 판단"])]
    for c, why, local, api, verdict in CRITERIA:
        rows.append(row([(1, c, S_TXTB), (2, why, S_SUB), (3, local, S_TXT),
                         (4, api, S_TXT), (5, verdict, S_TXT)], 30))

    rows += [
        row([]),
        section("기각한 선택지와 이유", 3),
        hdr(["기각한 것", "왜 기각했나"]),
        row([(1, "384 차원 모델을 쓴다", S_TXTB),
             (2, "속도가 11배 빠르지만 뜻으로 찾는 성능이 절반이다. "
                 "우리 목적이 의미 검색이다", S_TXT)], 32),
        row([(1, "768 로 컬럼을 줄인다", S_TXTB),
             (2, "저장 용량이 줄지만 실측이 384 보다도 낮았다. "
                 "Voyage 와 로컬 한국어 모델도 못 쓰게 된다", S_TXT)], 32),
        row([(1, "3072 으로 크게 잡는다", S_TXTB),
             (2, "저장이 3배로 늘고 이 차원을 내는 로컬 모델이 없다. API 에 묶인다", S_TXT)], 32),
        row([(1, "API 모델을 즉시 배제한다", S_TXTB),
             (2, "우리가 잰 다국어 모델은 e5-large 하나다. "
                 "API 모델들은 그보다 크고 최신이라 배제할 근거가 없다", S_TXT)], 32),
        row([(1, "지금 API 모델을 도입한다", S_TXTB),
             (2, "문서 전량이 외부로 나간다. 그 결정을 성능 근거 없이 할 수 없다", S_TXT)], 32),
        row([(1, "결과를 문서 단위로 묶는다", S_TXTB),
             (2, "근거 스니펫에 원문을 인용해야 하는데 문서로 묶으면 그것이 사라진다. "
                 "결과 단위는 청크로 둔다", S_TXT)], 32),
        row([(1, "임베딩을 비동기로 만든다", S_TXTB),
             (2, "작업 큐가 아직 없고 업로드·분석이 이미 동기다. 일관성을 택했다", S_TXT)], 32),
    ]
    return sheet_xml(rows, [(1, 1, 20), (2, 2, 26), (3, 3, 26), (4, 4, 34), (5, 5, 40)],
                     freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 시트 7. 측정 이력

def build_history():
    rows = title_rows(
        "측정 이력 — 네 번 재면서 무엇을 바꿨나",
        "평가셋을 고친 회차가 있다. 회차 간 수치를 그대로 비교하면 안 된다")

    rows += [hdr(["회차", "무엇을 바꿨나", "왜", "결과"])]
    for h, what, why, result in HISTORY:
        last = h == "4차"
        rows.append(row([(1, h, S_CENB), (2, what, S_TXTB if last else S_TXT),
                         (3, why, S_SUB), (4, result, S_TXT)], 40))

    rows += [
        row([]),
        section("평가셋을 어떻게 만들었나", 3),
        hdr(["단계", "내용"]),
        row([(1, "1. 문서에서 역으로 뽑았다", S_TXTB),
             (2, "도메인 지식이 없어도 되는 방법이다. 청크를 읽고 "
                 "그 청크가 답이 되는 질문을 만들었다", S_TXT)], 32),
        row([(1, "2. 일부러 다른 말로 물었다", S_TXTB),
             (2, '"입찰보증금" 을 "돈을 걸지 않고 참여할 수 있나" 로 바꿨다. '
                 "키워드 검색으로는 못 찾게 만든 것이다", S_TXT)], 32),
        row([(1, "3. 글자 겹침을 라벨로 표시했다", S_TXTB),
             (2, "질의 단어가 정답 청크에 그대로 있으면 overlap 으로 찍었다. "
                 f"{N_OV}개가 겹치고 {N_NO}개가 안 겹친다", S_TXT)], 32),
        row([(1, "4. 라벨 검사 도구를 만들었다", S_TXTB),
             (2, "도구/embed-test/check_queries.py 가 라벨이 안 맞는 행을 잡아준다. "
                 "손으로 찍은 라벨을 믿을 수 없어서다", S_TXT)], 32),
        row([]),

        section("이 측정의 한계 — 발표 때 먼저 말할 것", 3),
        hdr(["한계", "내용"]),
        row([(1, f"표본이 작다", S_TXTB),
             (2, f"뜻으로만 찾는 질의가 {N_NO}개다. 1~2문항 차이는 노이즈로 봐야 한다. "
                 "KURE 와 bge 를 못 가르는 이유다", S_TXT)], 32),
        row([(1, "청킹이 본구현이 아니다", S_TXTB),
             (2, "시험용 청킹(450자·문단 우선)으로 쟀다. 본구현 청킹이 나오면 "
                 "다시 재야 한다. 그것이 RAG-10 의 설계 목적이다", S_TXT)], 32),
        row([(1, "문서가 5건이다", S_TXTB),
             (2, f"청크 {N_CHUNK}개다. 실제 운영에서는 문서가 늘어 후보가 많아지므로 "
                 "난도가 올라간다", S_TXT)], 32),
        row([(1, "정답을 내가 정했다", S_TXTB),
             (2, "질의를 만든 사람이 정답도 찍었다. 다른 사람이 보면 다르게 찍을 문항이 있다", S_TXT)], 32),
        row([(1, "최대 입력 길이를 안 쟀다", S_TXTB),
             (2, "청크가 모델 한도를 넘으면 조용히 잘린다. 450자라 아직 문제 없어 보이지만 "
                 "확인하지 않았다", S_TXT)], 32),
    ]
    return sheet_xml(rows, [(1, 1, 9), (2, 2, 34), (3, 3, 38), (4, 4, 54)],
                     freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 시트 8. 남은 확인

def build_open():
    rows = title_rows(
        "남은 확인 — 아직 모르는 것",
        "이 표에 있는 것을 모른 채로 결론을 확정하지 않았다")

    rows += [hdr(["항목", "왜 필요한가", "지금 상태"])]
    for item, why, state in OPEN:
        rows.append(row([(1, item, S_TXTB), (2, why, S_SUB), (3, state, S_TXT)], 30))

    rows += [
        row([]),
        section("확인한 것 — 코드로 본 값이다", 3),
        hdr(["확인 대상", "결과"]),
        row([(1, "DB 이미지에 pgvector 가 있나", S_TXTB),
             (2, "없다. docker-compose.yml 이 postgres:16-alpine 이다", S_TXT)], 20),
        row([(1, "마이그레이션에 CREATE EXTENSION vector 가 있나", S_TXTB),
             (2, "없다. 리비전 0001~0009 전체를 봤다", S_TXT)], 20),
        row([(1, "requirements.txt 에 pgvector 가 있나", S_TXTB),
             (2, "없다", S_TXT)], 20),
        row([(1, "작업 큐(celery·redis)가 있나", S_TXTB),
             (2, "없다. 코드에 매치 0건이다. 그래서 임베딩도 동기로 간다", S_TXT)], 20),
        row([(1, "리비전 head 가 무엇인가", S_TXTB),
             (2, "20260812_0009 (extracted_char_sources). 보현 몫은 0010 · 0011 이다", S_TXT)], 20),
        row([(1, "CHECK 제약 명명 선례가 있나", S_TXTB),
             (2, "있다. 0009 가 ck_extracted_text_char_count 를 썼다. "
                 "ck_{테이블단수}_{컬럼} 형태를 따른다", S_TXT)], 32),
    ]
    return sheet_xml(rows, [(1, 1, 34), (2, 2, 32), (3, 3, 62)], freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 패키징

SHEETS = [
    ("결론", build_conclusion()),
    ("실측_검색품질", build_quality()),
    ("실측_실행비용", build_cost()),
    ("차원분석", build_dimension()),
    ("API모델사양", build_api()),
    ("판단기준", build_criteria()),
    ("측정이력", build_history()),
    ("남은확인", build_open()),
]

content_types = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    + "".join(
        f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(len(SHEETS)))
    + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    '</Types>')

root_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    '</Relationships>')

workbook = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets>' + "".join(
        f'<sheet name="{escape(n)}" sheetId="{i+1}" r:id="rId{i+1}"/>'
        for i, (n, _) in enumerate(SHEETS)) + '</sheets></workbook>')

wb_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + "".join(
        f'<Relationship Id="rId{i+1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i+1}.xml"/>' for i in range(len(SHEETS)))
    + f'<Relationship Id="rId{len(SHEETS)+1}" '
      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
      'Target="styles.xml"/></Relationships>')


def main():
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", STYLES)
        for i, (_, xml) in enumerate(SHEETS):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml)

    print(f"생성 완료: {OUT.relative_to(ROOT)}")
    print(f"  시트 {len(SHEETS)}개 — " + " · ".join(n for n, _ in SHEETS))
    print(f"  실측 모델 {len(MODELS)}개 · API 모델 {len(API_MODELS)}개")
    print(f"  판단 기준 {len(CRITERIA)}개 · 측정 이력 {len(HISTORY)}회 · "
          f"남은 확인 {len(OPEN)}건")
    print(f"  파일 크기: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
