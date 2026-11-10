# User Guide / 사용자 가이드 — where-is-it AI (MVP)

- [English](#english)
- [한국어](#한국어)

---

<a id="english"></a>

# English

> 2026 Fall · AI Capstone Design · MVP User Guide

---

## 1. Service Introduction

| | |
|---|---|
| **Team number** | `Group 8` |
| **Team name** | `Oilil7` |
| **Service name** | **where-is-it AI** |
| **Target users** | University students who often lose everyday items (glasses, wallet, card, earphones, etc.) **inside their own room** |

**Problem we solve**
When you need an item, you often don't remember where you last put it, so you search the same places again and again. Where-Is-It AI uses a camera in your room to tell you **where an item is now, or where it was last seen**, using only what the camera actually saw.

**How it works:** **Detect → Save → Search → Explain**
1. **Detect** – A phone in the room takes a photo at a set interval, and Gemini 3.8 Flash finds the objects in it.
2. **Save** – Each object's location (e.g. "on the desk next to the laptop"), time and confidence is saved.
3. **Search** – You ask a question such as "Where are my glasses?" in English or Korean.
4. **Explain** – You get an answer with the location, time and confidence. If there is no evidence, it says "not found" instead of guessing.

**Core features available in this MVP**
- Detection of 7 key items: glasses, wallet, card, earphones, phone, charger, hair tie (other items like "water bottle" are also detected)
- Natural-language questions in **English and Korean**
- Answer types: **Visible now / Last seen / Possibility (not confirmed) / Not found / Please clarify**
- Confidence rule: only detections at **75% or higher** are stated as facts; 100% is never shown
- **Private rooms:** each camera phone is its own room. Only phones that know that camera's **ID + PIN** can see its records
- Descriptive questions: "Where is my **black** laptop?", "my **big** one"
- AI answers from records (RAG): "What was on my desk this morning?", "Where do I usually leave my keys?"
- One-tap question buttons for the 7 key items, optional named zones, and deleting your own history

---

## 2. How to Run and Access

### 2.1 Addresses

| What | Address |
|---|---|
| Ask page (your own phone/laptop) | `https://34-56-40-29.sslip.io/` |
| Camera page (the phone that watches the room) | `https://34-56-40-29.sslip.io/camera` |
| Zone drawing page (optional) | `https://34-56-40-29.sslip.io/zones` |

### 2.2 Supported environment

- **Browser:** Chrome (Android, PC) or Safari (iPhone, Mac), recent versions. No app install needed.
- **Devices:** two devices are recommended
  - **Camera device:** a phone, a tablet (or a laptop with a webcam) that stays in the room
  - **Asking device:** your own phone or a laptop
- **HTTPS is required** for the camera page (browsers only allow the camera on HTTPS pages).

### 2.3 What you need

- A browser on two devices
- The **invite code** to set up a camera (section 5.1)

Everything runs on our live server. There is nothing to install.

---

## 3. Core Feature Walkthrough

**Your role:** a university student who keeps misplacing small items in your room.
**Goal:** set up a camera in your room, then ask "Where are my glasses?" from your own phone and get an answer based on camera evidence.

### Step 1. Set up the camera phone (about 1 minute)
1. On the camera phone, open `https://34-56-40-29.sslip.io/camera`.
2. Enter:
   - **Room name:** e.g. `Lae's room`
   - **Invite code:** `5117`
   - **PIN:** 4–6 digits you choose, e.g. `2580`
3. Press **Set up**. The page shows your **Camera ID** (e.g. `4bff35aa`). You need it to connect the asking device.

### Step 2. Start the camera 
1. Choose the interval. Use **every 10 s (live demo)** to try it now. (15 min is the lowest-cost option for everyday use. You can also choose 20 s, 1 min, 5 min or 10 min.)
2. Press **Start camera** and allow camera access.
3. Place the phone so it sees your desk or bed, plugged in and with this page open.
4. Put a few items in view: glasses, wallet, phone, earphones, etc.
5. After each photo, the status line shows what was found, e.g. `1:03:51 PM: glasses, phone (2350 ms)`.

### Step 3. Connect your own phone as an asking device 
1. On your own phone or laptop, open `https://34-56-40-29.sslip.io`.
2. Under **Connect your room first**, enter the **Camera ID** and **PIN** → **Connect**.
   (Or copy the **room link** from the camera page and open it.)

### Step 4. Ask a question
Type in the **Ask where-is-it** box and press **Ask** (or tap one of the item buttons below it). Example inputs:

| Example question | What it tests |
|---|---|
| `Where are my glasses?` | Basic search (current location) |
| `안경 어디 있어?` | Korean question → Korean answer |
| `Where is my black wallet?` | Search by appearance |
| `Where is my cable?` | Ambiguous word → asks you to clarify |
| `Where is my umbrella?` | Item never seen → safe "not found" |
| `What was on my desk this morning?` | AI answer from records (RAG) |

### Step 5. Test "last seen"
1. Move your glasses out of the camera's view (e.g. into a drawer).
2. Wait for one or two more photos, then ask `Where are my glasses?` again.
3. The answer now says where and when the glasses were **last seen**.

### Step 6 (optional). Name your own zones
1. On the camera page, press **Save test photo**.
2. Open `https://34-56-40-29.sslip.io/zones` → **Load latest camera photo**.
3. Click the corners of an area, type a name such as `on my desk` → **Finish zone** → **Save zones to server**.
4. From the next photo on, answers use your zone names.

---

## 4. Expected Results and How to Check Them

### 4.1 Answer screen
Each answer appears as a chat bubble with a **label**, a sentence, and the time and confidence.

| Label | When | Example answer |
|---|---|---|
| **Visible now** | Seen in the latest photo, ≥ 75% | "Your phone is on the desk next to the laptop — visible in the current camera view (at 1:03 PM today, 94% confidence)." |
| **Last seen** | Not visible now, but confirmed earlier | "Your glasses are not visible in the current camera view. They were last seen on the bedside table at 10:04 AM today (91% confidence)…" |
| **Possibility — not confirmed** | Only a weak detection (< 75%) | "…Possibility (not confirmed): a low-confidence detection (58%) at 12:04 PM today suggests it might be on the bed. You could check there first." |
| **Not found** | No evidence | "…I couldn't find your card in the available camera records. It may be inside a bag, drawer or cupboard…" |
| **Please clarify** | The word could mean more than one item | "Which item do you mean: your charger or your earphones?" |

Korean questions get the same labels in Korean: 지금 보임 / 마지막으로 본 곳 / 가능성 — 확인되지 않음 / 찾지 못함 / 다시 알려 주세요.
Answers written by the AI from your records are marked **"AI answer from camera records"** under the bubble.

### 4.2 How to check the result
- **Compare with the real room:** the location in the answer should match where the item actually is (or was).
- **Quick buttons:** tap an item button (glasses, wallet, …) under the Ask box to check each of the 7 key items in one tap.
- **Storage tab:** shows the number of photos stored and the time of the last photo, which tells you whether the camera is sending.
- **Privacy check (optional, needs two camera devices):** set up a second camera as another room with different items in view. Ask `Where are my glasses?` in each room (**Rooms → Switch**). Each room answers only from its own camera.

### 4.3 Trying again with different inputs
- **Different items:** move items around and wait for the next photo, then ask again.
- **Different questions:** try the examples in step 4, or your own wording ("Where did I leave my AirPods?", "충전기 어디 있어?").
- **Start fresh:** **Storage → Delete this room's history** (tap twice) removes all records; the camera keeps working.
- **Another room:** **Rooms → Add a room** with a different camera ID + PIN, then **Switch**.

---

## 5. Additional Notes for This Service

### 5.1 Accounts and access
- There is **no sign-up or login**. Access works per room, with a **camera ID + PIN**.
- **To set up your own camera** you need the **invite code**: `5117`. (If it doesn't work, contact `sywlae01@ajou.ac.kr`.)
- **5 wrong PINs** lock that camera ID for **15 minutes**.
- Forgot the PIN? Set a new one under **PIN and room link → Set PIN** on the camera page.

### 5.2 Preparation
- Nothing to prepare. Just place a few of the key items or more in front of the camera.

### 5.3 Special environment
- **No GPU needed.** Object detection runs on Google's Gemini API, so the server is a small cloud VM.
- The camera phone must stay **plugged in, with the page open and the screen on**.

### 5.4 Limitations and known issues

| Item | Details / workaround |
|---|---|
| No accounts | There is no email sign-up or login. Each room is reached with its camera ID + PIN (an earlier draft planned email accounts). |
| Out of scope | Voice questions, tracking across rooms, native apps, more than one camera per room, shared rooms |
| Hidden items | Items inside a bag or drawer, under something, or outside the view can't be seen → "Not found" or "Last seen". |
| Gemini errors | If Gemini fails (quota, network), that photo is **not saved**, so it's never read as "nothing there". The camera page shows the reason and tries again with the next photo. |
| "Visible now" changes | "Visible now" only counts the latest photos (2 min by default; longer with longer intervals). If the camera stops, answers switch to "Last seen". |
| Server address changes | The `sslip.io` address changes if the VM restarts. Phones must reconnect with the new address. We keep the VM running during the review period. |
| No camera on `http://` | The camera page only works over HTTPS. Always use the `https://` addresses in 2.1. |
| Limits | Up to 20 cameras per server. Records are deleted automatically after 30 days. Photos are analysed and discarded (not stored). |
| Cost | Normal questions are free (rule-based). AI (RAG) answers cost about $0.002–0.005 each. |

---

## 6. Review Period (Nov 11–18, 2026)

- The live server stays available **from Nov 11 to Nov 18**.
- If the address or the run steps change, this guide is updated right away. Check the **Last updated** date below.
- Questions or problems: `sywlae01@ajou.ac.kr`.

*Last updated: `2026.11.10`*

---

<a id="한국어"></a>

# 한국어

> 2026학년도 2학기 AI 캡스톤디자인 · MVP 사용자 가이드

---

## 1. 서비스 소개

| | |
|---|---|
| **팀 번호** | `Group 8` |
| **팀 이름** | `Oilil7` |
| **서비스 이름** | **where-is-it AI** |
| **대상 사용자** | **자기 방 안에서** 안경, 지갑, 카드, 이어폰 같은 물건을 자주 잃어버리는 대학생 |

**해결하려는 문제**
물건이 필요할 때 마지막에 어디 두었는지 기억나지 않아 같은 곳을 반복해서 찾게 됩니다. Where-Is-It AI는 방에 둔 카메라가 **실제로 본 것만을 근거로** 물건이 **지금 어디 있는지, 또는 마지막으로 어디서 보였는지** 알려 줍니다.

**동작 원리:** **탐지(Detect) → 저장(Save) → 검색(Search) → 설명(Explain)**
1. **탐지** – 방에 둔 휴대폰이 정해진 간격으로 사진을 찍고, Gemini 3.8 Flash가 사진 속 물건을 찾습니다.
2. **저장** – 물건의 위치("노트북 옆 책상 위"), 시간, 신뢰도를 저장합니다.
3. **검색** – "안경 어디 있어?"처럼 한국어나 영어로 질문합니다.
4. **설명** – 위치, 시간, 신뢰도와 함께 답합니다. 근거가 없으면 추측하지 않고 "찾지 못함"이라고 답합니다.

**이번 MVP에서 사용할 수 있는 핵심 기능**
- 7가지 핵심 물건 탐지: 안경, 지갑, 카드, 이어폰, 휴대폰, 충전기, 머리끈 (물병 같은 다른 물건도 탐지)
- **한국어·영어** 자연어 질문
- 답변 유형: **지금 보임 / 마지막으로 본 곳 / 가능성(확인되지 않음) / 찾지 못함 / 다시 알려 주세요**
- 신뢰도 규칙: **75% 이상**일 때만 사실로 답하고, 100%는 절대 표시하지 않음
- **방별 개인 기록:** 카메라 휴대폰 한 대가 하나의 방이며, 그 카메라의 **ID + PIN**을 아는 휴대폰만 기록을 볼 수 있음
- 생김새로 질문: "**검은색** 노트북 어디 있어?", "**큰** 거"
- 기록 기반 AI 답변(RAG): "오늘 아침 책상 위에 뭐 있었어?", "열쇠 보통 어디 둬?"
- 7가지 물건 바로 질문 버튼, 위치 이름 직접 지정(선택), 내 기록 삭제

---

## 2. 실행 및 접속 방법

### 2.1 접속 주소

| 용도 | 주소 |
|---|---|
| 질문 페이지 (내 휴대폰/노트북) | `https://34-56-40-29.sslip.io/` |
| 카메라 페이지 (방을 비추는 휴대폰) | `https://34-56-40-29.sslip.io/camera` |
| 위치 이름 지정 페이지 (선택) | `https://34-56-40-29.sslip.io/zones` |

### 2.2 지원 환경

- **브라우저:** 최신 Chrome(안드로이드, PC) 또는 Safari(아이폰, Mac). 앱 설치 불필요
- **기기:** 2대 권장
  - **카메라 기기:** 방에 고정해 둘 휴대폰, 태블릿 (또는 웹캠이 있는 노트북)
  - **질문 기기:** 내 휴대폰이나 노트북
- 카메라 페이지는 **HTTPS에서만** 동작합니다 (브라우저 보안 정책).

### 2.3 준비물

- 기기 2대의 브라우저
- 카메라 설정에 필요한 **초대 코드** (5.1 참고)

모든 기능은 운영 서버에서 동작하며, 따로 설치할 것은 없습니다.

---

## 3. 핵심 기능 체험 순서

**가정할 역할:** 방에서 작은 물건을 자주 잃어버리는 대학생
**체험 목표:** 방에 카메라를 설치한 뒤, 내 휴대폰에서 "안경 어디 있어?"라고 물어 카메라 근거에 기반한 답을 받기

### 1단계. 카메라 휴대폰 설정 (약 1분)
1. 카메라로 쓸 휴대폰에서 `https://34-56-40-29.sslip.io/camera`를 엽니다.
2. 다음을 입력합니다.
   - **방 이름:** 예) `Lae's room`
   - **초대 코드:** `5117`
   - **PIN:** 직접 정한 숫자 4–6자리, 예) `2580`
3. **Set up**을 누르면 **카메라 ID**(예: `4bff35aa`)가 표시됩니다. 질문 기기를 연결할 때 필요합니다.

### 2단계. 카메라 시작
1. 촬영 간격을 고릅니다. 바로 체험하려면 **every 10 s (live demo)** 를 선택합니다. (평소에는 비용이 가장 적은 15분 간격을 권장합니다. 20초, 1분, 5분, 10분 간격도 선택할 수 있습니다.)
2. **Start camera**를 누르고 카메라 권한을 허용합니다.
3. 책상이나 침대가 보이도록 휴대폰을 고정하고, 충전기를 꽂은 채 페이지를 켜 둡니다.
4. 안경, 지갑, 휴대폰, 이어폰 등을 화면 안에 놓습니다.
5. 사진을 보낼 때마다 상태 줄에 찾은 물건이 표시됩니다. 예) `1:03:51 PM: glasses, phone (2350 ms)`

### 3단계. 내 휴대폰을 질문 기기로 연결
1. 내 휴대폰이나 노트북에서 `https://34-56-40-29.sslip.io/`를 엽니다.
2. **Connect your room first** 아래에 **카메라 ID**와 **PIN**을 입력하고 **Connect**를 누릅니다.
   (카메라 페이지의 **방 링크(room link)** 를 복사해 열어도 됩니다.)

### 4단계. 질문하기
**Ask where-is-it** 입력창에 질문을 쓰고 **Ask**를 누릅니다 (아래 물건 버튼을 눌러도 됩니다). 예시 입력:

| 예시 질문 | 확인하는 기능 |
|---|---|
| `안경 어디 있어?` | 기본 검색 (현재 위치), 한국어 답변 |
| `Where are my glasses?` | 영어 질문 → 영어 답변 |
| `검은색 지갑 어디 있어?` | 생김새로 검색 |
| `Where is my cable?` | 뜻이 여러 개인 단어 → 다시 질문 |
| `우산 어디 있어?` | 한 번도 본 적 없는 물건 → 안전하게 "찾지 못함" |
| `오늘 아침 책상 위에 뭐 있었어?` | 기록 기반 AI 답변 (RAG) |

### 5단계. "마지막으로 본 곳" 확인
1. 안경을 카메라가 보지 못하는 곳(예: 서랍)으로 옮깁니다.
2. 사진이 한두 장 더 찍힐 때까지 기다린 뒤 `안경 어디 있어?`를 다시 묻습니다.
3. 안경이 **마지막으로 보인** 위치와 시간을 알려 줍니다.

### 6단계 (선택). 위치 이름 직접 지정
1. 카메라 페이지에서 **Save test photo**를 누릅니다.
2. `https://34-56-40-29.sslip.io/zones` → **Load latest camera photo**
3. 영역의 꼭짓점을 클릭하고 `내 책상 위` 같은 이름을 입력 → **Finish zone** → **Save zones to server**
4. 다음 사진부터 답변에 내가 지은 위치 이름이 사용됩니다.

---

## 4. 기대 결과 및 확인 방법

### 4.1 답변 화면
답변은 말풍선으로 표시되며, **라벨**, 답변 문장, 시간과 신뢰도가 함께 나옵니다.

| 라벨 | 나오는 경우 | 답변 예시 |
|---|---|---|
| **지금 보임** | 최근 사진에서 75% 이상으로 보임 | "휴대폰은 노트북 옆 책상 위에 있어요 — 지금 카메라 화면에 보여요 (오늘 오후 1:03, 신뢰도 94%)." |
| **마지막으로 본 곳** | 지금은 안 보이지만 이전에 확인됨 | "안경은 지금 카메라 화면에 보이지 않아요. 오늘 오전 10:04 침대 옆 협탁 위 위치에서 마지막으로 보였어요 (신뢰도 91%)…" |
| **가능성 — 확인되지 않음** | 약한 탐지(75% 미만)만 있음 | "…가능성 (확인되지 않음): 오늘 오후 12:04의 낮은 신뢰도 감지(58%)로 보면 충전기가 침대 위에 있을 수도 있어요. 먼저 그곳을 확인해 보세요." |
| **찾지 못함** | 근거 없음 | "…카메라 기록에서 카드를 찾지 못했어요. 가방이나 서랍, 수납장 안에 있거나…" |
| **다시 알려 주세요** | 단어가 여러 물건을 뜻할 수 있음 | "어떤 물건을 말씀하시는 건가요? 충전기, 이어폰 중에서 골라 주세요." |

영어로 물으면 같은 내용이 영어 라벨(Visible now / Last seen / Possibility — not confirmed / Not found / Please clarify)로 표시됩니다.
기록을 바탕으로 AI가 작성한 답변에는 말풍선 아래에 **"AI 답변 · 카메라 기록 기반"** 표시가 붙습니다.

### 4.2 결과 확인 방법
- **실제 방과 비교:** 답변의 위치가 물건이 실제로 있는(또는 있었던) 곳과 같은지 확인합니다.
- **바로 질문 버튼:** 입력창 아래 물건 버튼(glasses, wallet …)을 눌러 7가지 물건을 하나씩 바로 확인할 수 있습니다.
- **Storage 탭:** 저장된 사진 수와 마지막 사진 시간을 보여 줍니다. 카메라가 사진을 보내고 있는지 여기서 확인합니다.
- **개인 기록 분리 확인 (선택, 카메라 기기 2대 필요):** 두 번째 카메라를 다른 방으로 설정하고 다른 물건을 비춥니다. 각 방에서 `안경 어디 있어?`를 물으면(**Rooms → Switch**) 각 방은 자기 카메라 기록만으로 답합니다.

### 4.3 다른 입력으로 다시 실행하기
- **다른 물건:** 물건 위치를 바꾸고 다음 사진이 찍힌 뒤 다시 질문합니다.
- **다른 질문:** 4단계 예시나 자유로운 표현으로 질문합니다 ("에어팟 어디 뒀지?", "Where's my charger?").
- **처음부터 다시:** **Storage → Delete this room's history** (두 번 누르기)로 기록을 모두 지웁니다. 카메라는 계속 동작합니다.
- **다른 방:** **Rooms → Add a room**에서 다른 카메라 ID + PIN을 입력한 뒤 **Switch**를 누릅니다.

---

## 5. 서비스별 추가 안내

### 5.1 계정 / 접근 권한
- **회원가입이나 로그인은 없습니다.** 방마다 **카메라 ID + PIN**으로 접근합니다.
- **내 카메라를 설정하려면** **초대 코드**가 필요합니다: `5117` (동작하지 않으면 `sywlae01@ajou.ac.kr`로 문의)
- PIN을 **5번 틀리면** 해당 카메라 ID가 **15분간 잠깁니다.**
- PIN을 잊었으면 카메라 페이지의 **PIN and room link → Set PIN**에서 새로 정합니다.

### 5.2 사전 준비
- 따로 준비할 것은 없습니다. 핵심 물건 몇 개 또는 그 이상을 카메라 앞에 두면 됩니다.

### 5.3 전문 지식 / 특수 환경
- **GPU가 필요 없습니다.** 물건 탐지는 Google Gemini API에서 처리하므로 서버는 작은 클라우드 VM으로 충분합니다.
- 카메라 휴대폰은 **충전기를 꽂고, 페이지를 열어 둔 채, 화면이 켜진 상태**를 유지해야 합니다.

### 5.4 제한 사항 / 알려진 오류

| 항목 | 내용 / 해결 방법 |
|---|---|
| 계정 없음 | 이메일 회원가입·로그인은 없습니다. 각 방은 카메라 ID + PIN으로 접근합니다 (이전 초안에서는 이메일 계정을 계획했습니다). |
| 범위 밖 기능 | 음성 질문, 여러 방에 걸친 추적, 네이티브 앱, 방 하나에 카메라 여러 대, 방 공유 |
| 가려진 물건 | 가방·서랍 속, 다른 물건 아래, 화면 밖에 있는 물건은 볼 수 없습니다 → "찾지 못함" 또는 "마지막으로 본 곳" |
| Gemini 오류 | Gemini가 실패하면(사용량 한도, 네트워크) 그 사진은 **저장하지 않으므로** "아무것도 없음"으로 잘못 처리되지 않습니다. 카메라 페이지에 이유가 표시되고 다음 사진에서 다시 시도합니다. |
| "지금 보임" 기준 | 최근 사진(기본 2분, 촬영 간격이 길면 더 길어짐)만 "지금"으로 봅니다. 카메라가 멈추면 "마지막으로 본 곳"으로 바뀝니다. |
| 서버 주소 변경 | VM을 재시작하면 `sslip.io` 주소가 바뀌고, 휴대폰을 새 주소로 다시 연결해야 합니다. 리뷰 기간에는 VM을 계속 켜 둡니다. |
| `http://`에서 카메라 불가 | 카메라 페이지는 HTTPS에서만 동작합니다. 항상 2.1의 `https://` 주소를 사용하세요. |
| 사용 제한 | 서버당 카메라 최대 20대, 기록은 30일 후 자동 삭제, 사진은 분석 후 바로 버리며 저장하지 않음 |
| 비용 | 일반 질문은 규칙 기반이라 무료, AI(RAG) 답변은 1회 약 $0.002–0.005 |

---

## 6. 리뷰 기간 운영 (2026년 11월 11일 ~ 18일)

- **11월 11일부터 18일까지** 운영 서버를 사용 가능한 상태로 유지합니다.
- 접속 주소나 실행 방법이 바뀌면 이 가이드를 바로 갱신합니다. 아래 **최종 수정일**을 확인하세요.
- 문의 및 오류 제보: `sywlae01@ajou.ac.kr`

*최종 수정일: `2026.11.10`*
