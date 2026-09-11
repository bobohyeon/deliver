// 검색 화면의 순수 함수를 실제 소스에서 뽑아 검사한다.
//
// 왜 소스에서 뽑는가: 로직을 이 파일에 복사해 두면 "복사본"을 검사하게 되어,
// 원본이 바뀌어도 검사는 계속 통과한다. 함수 선언을 원문에서 잘라 eval 하면
// 실제 코드를 검사한다.
//
// 왜 렌더링은 검사하지 않는가: 이 샌드박스에 npm install 이 안 되어 react ·
// react-router-dom 을 불러올 수 없다. 컴포넌트는 브라우저에서 눈으로 확인한다.
//
// 사용법: node check_search_pure.mjs <Tasqra/frontend 경로>

import { readFileSync } from 'node:fs'
import { argv, exit } from 'node:process'

const root = argv[2]
if (!root) { console.error('사용법: node check_search_pure.mjs <frontend 경로>'); exit(2) }

/** 소스에서 `function 이름(...) { ... }` 를 중괄호 짝을 세어 잘라낸다. */
function cut(source, name) {
  const head = source.indexOf(`function ${name}(`)
  if (head < 0) throw new Error(`함수를 찾지 못했다: ${name}`)
  let depth = 0
  let started = false
  for (let i = head; i < source.length; i += 1) {
    const ch = source[i]
    if (ch === '{') { depth += 1; started = true }
    else if (ch === '}') {
      depth -= 1
      if (started && depth === 0) return source.slice(head, i + 1)
    }
  }
  throw new Error(`중괄호가 닫히지 않았다: ${name}`)
}

const contentTab = readFileSync(`${root}/src/features/document-detail/DocumentContentTab.jsx`, 'utf8')
const searchView = readFileSync(`${root}/src/features/search/SearchView.jsx`, 'utf8')

const { parseRange, splitRange, splitText } = await import(
  'data:text/javascript,' + encodeURIComponent(
    [cut(contentTab, 'parseRange'), cut(contentTab, 'splitRange'), cut(contentTab, 'splitText')].join('\n')
    + '\nexport { parseRange, splitRange, splitText }'
  )
)
const { groupByDocument } = await import(
  'data:text/javascript,' + encodeURIComponent(
    cut(searchView, 'groupByDocument') + '\nexport { groupByDocument }'
  )
)

let passed = 0
const failures = []
function check(label, actual, expected) {
  const a = JSON.stringify(actual)
  const b = JSON.stringify(expected)
  if (a === b) { passed += 1; return }
  failures.push(`${label}\n    받음: ${a}\n    기대: ${b}`)
}

// ---------------------------------------------------------------- parseRange
// 정상
check('정상 구간', parseRange('10', '20', 100), { from: 10, to: 20 })
check('문서 맨 앞', parseRange('0', '5', 100), { from: 0, to: 5 })
check('문서 끝까지', parseRange('90', '100', 100), { from: 90, to: 100 })
// 없음
check('파라미터 없음', parseRange(null, null, 100), null)
check('from 만 있음', parseRange('10', null, 100), null)
check('to 만 있음', parseRange(null, '20', 100), null)
// 빈 문자열 — Number('') 이 0 이라 그냥 두면 0 으로 통과해 버린다
check('빈 from', parseRange('', '20', 100), null)
check('빈 to', parseRange('10', '', 100), null)
check('공백 from', parseRange('  ', '20', 100), null)
// 숫자가 아님
check('글자', parseRange('abc', '20', 100), null)
check('소수', parseRange('1.5', '20', 100), null)
check('NaN 유발', parseRange('10', 'x', 100), null)
// 범위 위반
check('음수', parseRange('-1', '20', 100), null)
check('to == from', parseRange('10', '10', 100), null)
check('to < from', parseRange('20', '10', 100), null)
check('문서 길이 초과 (검수로 원문이 짧아진 경우)', parseRange('10', '101', 100), null)
check('빈 문서', parseRange('0', '10', 0), null)

// ---------------------------------------------------------------- splitRange
const text = '0123456789'
check('가운데 강조', splitRange(text, 3, 6), [
  { text: '012', match: false }, { text: '345', match: true }, { text: '6789', match: false },
])
check('맨 앞 강조 — 앞 조각 없음', splitRange(text, 0, 4), [
  { text: '0123', match: true }, { text: '456789', match: false },
])
check('맨 끝 강조 — 뒤 조각 없음', splitRange(text, 6, 10), [
  { text: '012345', match: false }, { text: '6789', match: true },
])
check('전체 강조', splitRange(text, 0, 10), [{ text: '0123456789', match: true }])
// 원문이 손실되지 않아야 한다
for (const [from, to] of [[0, 10], [0, 1], [9, 10], [3, 6]]) {
  check(`원문 보존 ${from}~${to}`, splitRange(text, from, to).map(p => p.text).join(''), text)
}
check('강조 조각은 정확히 하나', splitRange(text, 3, 6).filter(p => p.match).length, 1)

// ---------------------------------------------------------------- splitText
// 기존 키워드 검색이 그대로인지 (내가 건드리지 않았음을 확인)
check('키워드 없음', splitText('가나다', ''), [{ text: '가나다', match: false }])
check('키워드 일치', splitText('가나다나', '나'), [
  { text: '가', match: false }, { text: '나', match: true },
  { text: '다', match: false }, { text: '나', match: true },
])
check('정규식 특수문자', splitText('a.b.c', '.').filter(p => p.match).length, 2)

// ------------------------------------------------------------ groupByDocument
const row = (chunk_id, document_id, similarity, extra = {}) => ({
  chunk_id, document_id, similarity,
  document_filename: `doc${document_id}.pdf`,
  project_id: 1, project_name: 'P', seq: chunk_id, ...extra,
})

check('빈 결과', groupByDocument([]), [])

const grouped = groupByDocument([
  row(1, 10, 0.55), row(2, 20, 0.51), row(3, 10, 0.47), row(4, 10, 0.40), row(5, 20, 0.33),
])
check('문서 수', grouped.length, 2)
check('문서 순서는 최고 조각이 나온 순서', grouped.map(g => g.document_id), [10, 20])
check('조각이 흩어져 있어도 한 묶음으로', grouped[0].items.map(r => r.chunk_id), [1, 3, 4])
check('두 번째 문서', grouped[1].items.map(r => r.chunk_id), [2, 5])
check('파일명 옮겨짐', grouped[0].filename, 'doc10.pdf')
// 조각 하나도 잃지 않아야 한다
check('조각 총수 보존', grouped.reduce((sum, g) => sum + g.items.length, 0), 5)
// 각 묶음 안에서 서버가 준 순서(거리 오름차순)가 유지돼야 한다
check('묶음 안 유사도 내림차순', grouped[0].items.map(r => r.similarity), [0.55, 0.47, 0.40])
// 문서가 하나뿐이면 한 묶음
check('문서 하나', groupByDocument([row(1, 7, 0.9), row(2, 7, 0.8)]).length, 1)
// 문서마다 조각 하나면 묶어도 개수가 같다
check('전부 다른 문서', groupByDocument([row(1, 1, 0.9), row(2, 2, 0.8), row(3, 3, 0.7)]).length, 3)

// -------------------------------------------------------------------- 결과
console.log('='.repeat(66))
if (failures.length) {
  console.log(`  실패 ${failures.length}건 · 통과 ${passed}건\n`)
  for (const line of failures) console.log('  ✗ ' + line)
  exit(1)
}
console.log(`  통과 ${passed}건 — parseRange · splitRange · splitText · groupByDocument`)
exit(0)
