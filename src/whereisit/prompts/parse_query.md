# Where-Is-It AI 파싱 프롬프트 — parse_query.md (강의 3 산출물)

| 항목 | 값 |
|---|---|
| prompt_version | 1 |
| 짝이 되는 스키마 | `src/whereisit/schemas/query.schema.json` |
| 읽는 코드 | `src/whereisit/parser.py` — `<!-- prompt:start -->`와 `<!-- prompt:end -->` 사이만 읽어 system 프롬프트로 보낸다 |

## 시스템 프롬프트 (모델에 전송되는 부분)

<!-- prompt:start -->
너는 Where-Is-It AI의 질문 파서다. 사용자가 물건을 찾으며 한 말을 주어진 JSON 스키마에 정확히 맞는 객체 하나로 바꾼다. 물건이 어디 있는지는 답하지 않는다 — 위치는 카메라 탐지 기록이 정한다.

규칙:
- 발화에 명시되지 않은 값은 추측하지 않는다. 각 Query에는 두 키를 항상 쓰고, objectName을 정할 수 없으면 null로 둔다.
- questionText에는 사용자 발화를 한 글자도 바꾸지 않고 그대로 쓴다. 요약, 번역, 맞춤법 수정을 하지 않는다.
- objectName에는 사용자가 찾는 물건을 가리키는 말을 발화에 나온 단어 그대로 쓴다. 물건 이름과 그 물건의 겉모습 표현(색, 재질, 브랜드, 모양)만 남기고, "그", "저", "내", "룸메이트"처럼 가리키거나 주인을 나타내는 말은 뺀다.
- objectName을 번역하거나 다른 말로 바꾸거나 표현을 덧붙이지 않는다. "폰"은 "폰"으로 쓰고, 발화에 없는 색이나 브랜드를 붙이지 않는다.
- 물건 이름이 없으면("그거", "그 까만 거") 그 Query의 objectName은 null이다. 어떤 물건인지 추측하지 않는다.
- 찾는 물건 하나마다 queries 배열에 Query를 하나씩 만들고, 발화에 나온 순서대로 넣는다("폰이랑 지갑" → Query 2개).
- 같은 발화에서 나온 Query는 모두 같은 questionText를 갖는다. urgency, checkedPlaces, lastUsedPlace가 모든 물건에 해당하는 것이 분명하면 모든 Query에 넣고, 한 물건에만 해당하는 것이 분명하면 그 Query에만 넣는다.
- questionType: "어디 있어" → current_location, "마지막으로 언제 봤어" → last_seen, "언제 없어졌어" → disappeared_when, "그 주변에서 무슨 일이 있었어" → nearby_context, "어디를 찾아봐야 해" → where_to_look. 분명하지 않으면 생략한다.
- urgency: "늦었어", "지금 나가야 돼" 같은 표현이면 high, "급한 건 아닌데" 같은 표현이면 low. 그 밖에는 생략한다.
- checkedPlaces: 사용자가 이미 찾아봤다고 말한 곳을 발화에 나온 말 그대로 쓴다. lastUsedPlace: 마지막으로 쓰거나 둔 곳을 발화에 나온 말 그대로 쓴다. 말하지 않은 장소는 넣지 않는다.
- 그 물건이 시스템에 있는지는 판단하지 않는다. 처음 듣는 물건도 발화에 나온 대로 쓴다.
- 출력은 JSON 객체 하나만 쓴다. 설명, 코드 펜스, 주석을 붙이지 않는다.

예시 1
입력: 까만 지갑 어디 있지?
출력: {"queries":[{"questionText":"까만 지갑 어디 있지?","objectName":"까만 지갑" "questionType":"current_location"}]}

예시 2
입력: 아 그거 어디 갔지
출력: {"queries":[{"questionText":"아 그거 어디 갔지","objectName":null}]}

Example 3
Input: I'm late, where are my phone and black wallet? Not on the desk.
Output: {"queries":[{"questionText":"I'm late, where are my phone and black wallet? Not on the desk.","objectName":"phone","questionType":"current_location","urgency":"high","checkedPlaces":["desk"]},{"questionText":"I'm late, where are my phone and black wallet? Not on the desk.","objectName":"black wallet","questionType":"current_location","urgency":"high","checkedPlaces":["desk"]}]}
<!-- prompt:end -->

## 필드 → 함수 인자 (하드/소프트)

입력: "나 수업 늦었는데 까만 지갑 어디 있지? 책상엔 없어. 어젯밤에 침대위에 뒀던 것 같은데"
출력으로 뽑을 구조: `questionText`, `objectName`, `questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace`. 찾는 물건이 둘 이상이면 물건마다 Query를 하나씩 만들어 queries 배열에 담는다(`Query asksAbout Object`가 `many:1`이므로 Query 하나는 Object 하나만 가리킨다).

| 필드 | 어느 함수의 어느 인자로 가는가 | 하드/소프트 |
|---|---|---|
| `objectName` | `Query asksAbout Object` — AI가 등록한 `Object.name`, `Object.category`와 대조해 대상 Object를 확정 → `Object has Detection`으로 그 Object의 탐지만 가져온다 → rule 1(`confidence > 70%`) 적용 | **하드**. 확정된 Object가 아닌 Object의 Detection은 Response 근거가 될 수 없다. 수집 필수 — null이면 탐지 조회를 하지 않고 되묻는다 |
| `questionText` | `Query produces Response` — `Response.answer`를 만들 때 사용자의 원래 질문으로 쓴다 | 랭킹 미사용. 원문 보존용. Literal Input |
| `queries` | 각 Query가 따로 `Query asksAbout Object` → `Query produces Response`를 거친다 — Query 하나당 Response 하나 | 하드 |
| `questionType` | rule 2의 시작 단계를 정한다. `current_location` → ① 현재 탐지 → `location_or_last_seen` / `last_seen`, `disappeared_when` → ② 이력(`Detection.timestamp`) → `location_or_last_seen` / `nearby_context` → ③ `Detection coOccursWith ContextEvent` → `possibility_suggestion` / `where_to_look` → ③ + rule 3 → `possibility_suggestion`. 생략이면 rule 2 순서 그대로(①→②→③) | 소프트. 순서만 바꾸고 탐지를 빼지 않는다 |
| `urgency` | `Query produces Response` — `Response.answer`의 길이. high면 `location_or_last_seen` 한 줄, low면 Response 항목 전부. 어느 쪽이든 rule 3의 `fact_vs_possibility_disclaimer`는 빼지 않는다 | 랭킹 미사용. 응답 형식 인자 |
| `checkedPlaces` | rule 2 ①② — 확정된 `Detection.location`과 대조. 일치해도 탐지를 버리지 않고, rule 3에 따라 "탐지 위치(사실) + 다른 물건에 가려졌을 가능성"으로 답한다 | 소프트. 찾아본 곳에서 가려진 채 발견된 사례(로그 2, 6, 10) |
| `lastUsedPlace` | rule 2 ③ + rule 3 — 사용자의 기억이므로 `possibility_suggestion`에만 쓰고 `location_or_last_seen`에는 쓰지 않는다. rule 1(`confidence > 70%`)을 넘는 탐지가 없을 때만 쓴다 | 소프트. 예상 위치와 실제 위치가 어긋난 사례(로그 4, 9) |

## 스키마 설계 메모

- **물건 여럿은 Query 여럿으로 푼다.** 온톨로지에서 `Query asksAbout Object`는 many:1, `Query produces Response`는 1:1이다. `objectName`을 배열로 바꾸면 이 관계가 바뀌므로, 물건마다 Query를 하나씩 만들어 최상위 `queries` 배열에 담는다. `queries`는 온톨로지 속성이 아닌 겉봉투이고 `minItems: 1`이다 — 물건을 말하지 않은 발화도 `objectName: null`인 Query 하나로 나온다. 같은 발화에서 나온 Query는 모두 같은 `questionText`를 갖는다.
- **프로퍼티는 온톨로지 `Query`의 여섯 속성과 같다.** `questionText`, `objectName`, `questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace`. 온톨로지를 고치면 스키마를 같은 커밋에서 고친다. 주인 구별("룸메이트 거 말고")은 카메라가 알 수 없는 정보라 `Object`에도 속성이 필요하므로 v2로 미룬다.
- **required = `questionText`, `objectName`.** 원문과 찾는 물건이 없으면 Query가 성립하지 않는다. `questionText`는 항상 존재하므로 null을 허용하지 않고, `objectName`은 모를 수 있으므로 `["string", "null"]`로 열었다. `{"questionText":"아 그거 어디 갔지","objectName":null}`이 검증을 통과해야 애플리케이션이 되묻는다.
- **null과 생략.** required 두 키는 모르면 null, 나머지 네 키(`questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace`)는 발화에 없으면 키 자체를 생략한다. 빈 배열도 생략으로 통일하려고 `checkedPlaces`에 `minItems: 1`을 걸었다.
- **enum은 닫힌 집합에만.** `questionType`은 온톨로지 purpose가 정한 다섯 질문(`current_location`, `last_seen`, `disappeared_when`, `nearby_context`, `where_to_look`)이고, `urgency`는 `high`/`low` 두 값이라 enum을 걸었다. 판단할 수 없으면 억지로 고르지 않고 생략한다.
- **`objectName`에 enum을 걸지 않은 이유.** `Object.name`은 AI가 감지하며 붙이는 설명형 이름("black wallet")이라 닫힌 집합이 아니다. 닫히지 않은 값에 enum을 걸면 모델이 가장 가까운 값에 욱여넣는다 — 인터뷰의 불안 요인("다른 지갑을 보고 지갑이 테이블에 있다고 말함")이 바로 이 억지 매핑이다. 대신 `objectName`을 발화에 나온 단어로만 만들게 해서 환각을 막고, 등록된 Object와의 대조는 `Query asksAbout Object`에서 한다.
- **장소 필드에 enum을 걸지 않은 이유.** `checkedPlaces`, `lastUsedPlace`는 `Detection.location`과 대조되지만, 그 값 목록이 아직 정해지지 않았다. 사용자 표현을 그대로 받고 대조는 rule 2 단계에서 한다. 목록이 확정되면 주입 + 후처리 대조를 검토한다.
- **겉모습 표현을 남기고 주인 표현을 빼는 이유.** AI가 붙이는 이름에는 색·재질 같은 겉모습이 들어가므로 "까만"은 같은 종류 물건 여럿을 가르는 데 쓰인다. "내", "룸메이트"는 카메라가 알 수 없는 정보라 대조에 도움이 안 되고 오히려 방해한다.
- **`additionalProperties: false`.** 최상위와 `Query` 양쪽에 건다. 파서가 `"location": "침대"`처럼 위치를 직접 답하거나 `Object`의 속성(`category`)을 끌어오는 것을 막는다. 모델의 추측이 `Detection`을 대신하면 rule 3(확인된 사실과 가능성의 구분)이 무너진다.

## 실패 모드 점검표

| # | 실패 모드 | 점검 입력 | 어디서 잡히나 | 그다음 |
|---|---|---|---|---|
| 1 | (정상) | "나 수업 늦었는데 까만 지갑 어디 있지? 책상엔 없어. 어젯밤에 침대 위에 뒀던 것 같은데" | Query 1개. 스키마 통과, 후처리 통과, `Query asksAbout Object`에서 `"black wallet"` 하나와 일치 | `Object has Detection` → rule 1~3 → `Query produces Response`. urgency high이므로 `locationOrLastSeen` 한 줄 + `factVsPossibilityDisclaimer` |
| 2 | 정보 부족 | "아 그거 어디 갔지" | 스키마 통과(null 허용). 필수 조건 검사에서 `objectName`이 null | 모델을 다시 부르지 않고 "어떤 물건을 찾을까요?"라고 되묻는다 |
| 3 | 모호한 값(일치하는 Object가 여럿) | "지갑 어디 있어?" | 파서·스키마·후처리 통과. `Query asksAbout Object`에서 `"black wallet"`, `"brown leather wallet"` 두 개와 일치 | 하나를 골라 답하지 않는다. "검은 지갑과 갈색 가죽 지갑 중 어느 것인가요?"처럼 등록된 이름으로 후보를 보여 주고 되묻는다 |
| 4 | 범위 위반 | 출력에 `"objectName": ""`, `"questionText": null`, `"questionType": "where"`, `"urgency": "medium"`, `"checkedPlaces": []` | 스키마 `minLength` / 타입 / `enum` / `minItems` 위반 → 검증 실패 | 오류 메시지를 붙여 재요청(최대 2회) |
| 5 | 등록되지 않은 물건 | "라이터 어디 뒀더라" | 파서는 규칙대로 `"라이터"`를 내고 스키마·후처리 통과. `Query asksAbout Object`에서 일치하는 Object 0개 | "카메라가 아직 라이터를 감지해 등록한 적이 없어요"라고 알린다. 비슷한 다른 물건의 위치를 대신 알려 주지 않는다 |
| 6 | objectName 변형(번역·덧붙임) | "폰 어디 있지" → 출력 `"objectName": "black smartphone"` | 후처리에서 objectName의 단어가 모두 `questionText`에 있는지 검사 → "black", "smartphone"이 없음 | 재요청(최대 2회). 재요청 한도를 넘으면 2번과 같은 되묻기 — 모델이 지어낸 "black"으로 대조하면 엉뚱한 Object가 확정될 수 있다 |
| 7 | 장소 환각 | "폰 어디 있지" → 출력 `"checkedPlaces": ["책상"]` 또는 `"lastUsedPlace": "가방"` | 후처리에서 장소 표현이 `questionText`에 있는지 검사 → 없음 | 재요청하지 않고 그 키를 지운다. 두 필드는 생략 가능한 소프트 필드라 지워도 처리가 멈추지 않는다 — 지어낸 장소가 `possibilitySuggestion`에 들어가는 것보다 낫다 |
| 8 | 원문 변형 | 출력의 `questionText`가 요약·번역된 문장이거나, 같은 발화의 Query끼리 `questionText`가 다름 | 후처리에서 실제 입력과 문자열 비교 → 불일치 | 재요청하지 않고 모든 Query의 `questionText`를 실제 입력으로 덮어쓴다(값을 코드가 이미 알고 있으므로) |
| 9 | 스키마에 없는 키 / 봉투 누락 | 출력에 `"location": "침대"`, `"category": "wallet"` / `queries` 없이 Query 하나만 출력 | `additionalProperties: false`, 최상위 `required: ["queries"]` → 검증 실패 | 오류 메시지를 붙여 재요청(최대 2회). 모델이 적은 위치는 어디에도 쓰지 않는다 |
| 10 | JSON 아님 또는 절단 | 모델이 "지갑은 보통 책상 위에 있어요"처럼 문장으로 답함 / `stop_reason`이 `max_tokens` | 응답 상태 확인과 JSON 파싱 실패 | 재요청(최대 2회) |
| 11 | 물건 둘 이상(정상) | "폰이랑 까만 지갑 어디 있어?" | Query 2개. 스키마·후처리 통과 | 각 Query가 따로 `Query asksAbout Object` → `Query produces Response`를 거친다. 답은 물건별로 나눠 한 번에 보여 준다 |
| 12 | 물건 둘 중 하나만 해결 | "폰이랑 그거 어디 있어?" / "폰이랑 라이터 어디 있어?" | Query 2개 중 하나가 `objectName` null(필수 조건 검사) 또는 `Query asksAbout Object` 일치 0개 | 해결된 물건은 바로 답하고, 나머지만 되묻거나(2번) 등록 없음을 알린다(5번). 하나가 막혔다고 전체를 멈추지 않는다 |
| 13 | Query 누락·중복 | "폰이랑 지갑" → Query 1개만 / 같은 objectName의 Query 2개 | 후처리: 같은 objectName 중복 검사 → 하나로 합침. 누락은 파서 출력만으로 잡히지 않음 | 중복은 코드가 합친다. 누락 대비로 답의 첫 줄에 찾은 물건 목록("휴대폰을 찾았어요")을 되비춰 사용자가 빠진 물건을 알아챌 수 있게 한다 |

- **재요청하는 오류 유형**: 형식 오류(4 범위 위반, 9 스키마에 없는 키·봉투 누락, 10 JSON 아님·절단)와 6 objectName 변형. 정보 부족·모호함(2, 3, 5, 12)은 재요청하지 않고 되묻고, 원문 변형(8)과 중복(13)은 코드가 고치며, 장소 환각(7)은 키를 지운다 

- **재요청 횟수**: 2회

- **초과 시 폴백 동작**: 3회 연속 실패하면 파싱을 포기하고 "찾는 물건 이름만 다시 말해 주세요"라고 되묻는다. 추측한 값으로 탐지 조회를 진행하지 않는다.


## 점검 실행 기록

점검 입력을 실제 모델로 돌린 결과를 적는다. 한 행당 모델 ID, `prompt_version`, 스키마 커밋을 함께 적는다.

| # | 모델 ID | prompt_version | 스키마 커밋 | 실제 출력 | 기대대로 잡혔나 |
|---|---|---|---|---|---|
| 1 |  | 1 |  |  |  |
| 2 |  | 1 |  |  |  |
| 3 |  | 1 |  |  |  |
| 5 |  | 1 |  |  |  |
| 10 |  | 1 |  |  |  |

(4, 6, 7, 8, 9는 모델 출력이 아니라 해당 출력을 검증기와 후처리에 직접 넣어 확인한다. 3, 5, 12는 *Query asksAbout Object* 대조까지 돌려야 확인된다.)

## 변경 이력

- 
