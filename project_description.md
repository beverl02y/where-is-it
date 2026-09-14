##1. Project Overview

Where-Is-It AI is an AI-powered object location tracking and memory assistance system designed to help users find misplaced belongings in their homes or offices.
Instead of requiring users to manually register and track every item, the system uses CCTV or home camera footage and AI-based object recognition to automatically detect objects, record their locations, and track changes over time.
The system aims to answer not only:
**"Where is my object?"**
but also:
**"Where was it last seen?"
"When did it disappear?"
"What happened around that time?"
"Where should I look for it now?"**

##2. Problem Definition
   
People frequently lose or misplace everyday objects such as wallets, keys, phones, glasses, remote controls, and other personal belongings.
This can happen for several reasons:
The user forgets where they placed an object.
Someone else moves the object.
A pet moves or knocks over the object.
The object falls from its original location.
The user does not remember when or where the object was last seen.
This problem can be particularly challenging for people experiencing memory difficulties, but it can also happen to anyone in their daily life.
Existing object-tracking solutions often require users to attach a physical tracking device or manually register an object. Where-Is-It AI aims to provide a more passive solution using cameras and AI-based visual recognition.

##3. Proposed Solution

Where-Is-It AI connects to CCTV or home cameras installed in a user's home or office.
The system periodically captures images from the camera and uses an AI object recognition model to identify objects in each image.
For example:
Camera
   ↓
Periodic Image Capture
   ↓
Object Detection
   ↓
Object Identification
   ↓
Location & Timestamp Recording
   ↓
Historical Object Database
   ↓
AI Search & Reasoning
   ↓
User Response

The system stores information such as:
Object name
Detected location
Timestamp
Camera ID
Detection confidence
Surrounding objects
Changes in object position
The recorded information can then be used to search for objects and reconstruct their recent movement history.

##4. Example Scenario
User Query
"Where is my wallet?"

Case 1: Object Currently Detected
The system searches the most recent image.
If the wallet is detected:
Wallet
Location: Living room table
Time: 13:00
Confidence: 94%

The AI responds:
"Your wallet is on the living room table."

Case 2: Object Is No Longer Detected
If the wallet is not found in the latest image, the system searches previous records.
For example:
13:00 → Wallet not detected
12:45 → Wallet detected
12:30 → Wallet detected

The system determines that the wallet was last confirmed at 12:45.
The AI responds:
"Your wallet was last seen on the table next to the sofa 30 minutes ago. Its location has not been confirmed since then."

Case 3: Contextual Analysis
The system can also analyze other objects or entities that appeared around the same time.
For example:
12:30
Wallet → On table

12:45
Cat → Near table
Wallet → No longer detected

The AI can use this temporal and contextual information to suggest a possible search area.
For example:
"Your wallet was last seen on the table 30 minutes ago. It was no longer visible afterward, and a cat was detected near the table around that time. The wallet may have fallen under or around the table. Please check the area around the table and sofa."
Important: Such explanations are treated as possibilities rather than confirmed facts.



##KOREAN 

1. 프로젝트 개요
Where-Is-It AI는 사용자가 집이나 사무실에서 잃어버리거나 잘못 둔 물건을 찾을 수 있도록 도와주는 AI 기반 물건 위치 추적 및 기억 보조 시스템입니다.
사용자가 모든 물건을 직접 등록하고 추적해야 하는 기존 방식과 달리, Where-Is-It AI는 CCTV 또는 Home Camera의 영상과 AI 기반 객체 인식 기술을 활용하여 물건을 자동으로 인식하고, 물건의 위치를 기록하며, 시간에 따른 위치 변화를 추적합니다.
이 시스템은 단순히 다음과 같은 질문에 답하는 것을 넘어:
"내 물건이 어디에 있지?"
다음과 같은 질문까지 해결하는 것을 목표로 합니다.
"마지막으로 어디에서 확인되었지?"
"언제 사라졌지?"
"그때 주변에서 무슨 일이 있었지?"
"지금 어디를 찾아보는 것이 좋을까?"

2. 문제 정의
사람들은 일상생활에서 지갑, 열쇠, 휴대폰, 안경, 리모컨 등의 물건을 자주 잃어버리거나 어디에 두었는지 기억하지 못하는 경우가 있습니다. 이러한 문제는 다음과 같은 다양한 상황에서 발생할 수 있습니다.
사용자가 물건을 어디에 두었는지 기억하지 못하는 경우, 다른 사람이 물건을 다른 장소로 옮긴 경우, 반려동물이 물건을 움직이거나 떨어뜨린 경우, 물건이 원래 위치에서 떨어진 경우, 사용자가 물건을 마지막으로 언제, 어디에서 보았는지 기억하지 못하는 경우
이러한 문제는 기억력에 어려움을 겪는 사람들에게 특히 더 큰 어려움이 될 수 있지만, 일상생활에서 누구에게나 발생할 수 있는 문제입니다.
기존의 물건 추적 솔루션은 사용자가 물건에 물리적인 추적 장치를 부착하거나, 각 물건을 직접 등록해야 하는 경우가 많습니다. Where-Is-It AI는 카메라와 AI 기반 시각 인식 기술을 활용하여 사용자의 별도 조작을 최소화하는 수동 개입이 적은 물건 추적 방식을 제공하고자 합니다.

3. 제안 솔루션
Where-Is-It AI는 사용자의 집이나 사무실에 설치된 CCTV 또는 Home Camera와 연결됩니다.
시스템은 카메라 화면을 일정한 시간 간격으로 캡처하고, AI 객체 인식 모델을 사용하여 각 이미지에 나타나는 물건을 식별합니다.
예를 들어, 전체적인 처리 과정은 다음과 같습니다.
카메라
   ↓
주기적인 이미지 캡처
   ↓
객체 탐지
   ↓
객체 식별
   ↓
위치 및 시간 정보 기록
   ↓
과거 객체 정보 데이터베이스
   ↓
AI 검색 및 추론
   ↓
사용자 응답

시스템은 다음과 같은 정보를 저장할 수 있습니다.
물건의 이름
탐지된 위치
탐지 시간
카메라 ID
탐지 신뢰도
주변에 존재하는 객체
시간에 따른 물건의 위치 변화
저장된 정보를 활용하여 사용자가 찾고 있는 물건을 검색하고, 해당 물건의 최근 이동 경로와 위치 변화를 파악할 수 있습니다.

4. 예시 시나리오
사용자 질문
"내 지갑 어디 있어?"
Case 1: 현재 물건이 탐지되는 경우
시스템은 가장 최근에 촬영된 이미지를 검색합니다.
지갑이 탐지되었다면:
물건: 지갑
위치: 거실 테이블
시간: 13:00
탐지 신뢰도: 94%

AI는 다음과 같이 응답할 수 있습니다.
"지갑은 거실 테이블 위에 있습니다."

Case 2: 현재 물건이 더 이상 탐지되지 않는 경우
가장 최근 이미지에서 지갑이 발견되지 않는다면, 시스템은 이전에 저장된 기록까지 검색 범위를 확장합니다.
예를 들어:
13:00 → 지갑 탐지되지 않음
12:45 → 지갑 탐지됨
12:30 → 지갑 탐지됨

시스템은 지갑이 12:45에 마지막으로 확인된 것으로 판단합니다.
AI는 다음과 같이 응답할 수 있습니다.
"지갑은 30분 전까지 소파 옆 테이블 위에서 확인되었습니다. 이후에는 위치가 확인되지 않았습니다."

Case 3: 주변 상황을 함께 분석하는 경우
시스템은 물건 자체의 위치뿐만 아니라, 해당 시간대에 주변에 나타난 다른 객체나 개체의 움직임도 분석할 수 있습니다.
예를 들어:
12:30
지갑 → 테이블 위

12:45
고양이 → 테이블 주변
지갑 → 더 이상 탐지되지 않음

AI는 이러한 시간적 정보와 주변 상황에 대한 정보를 종합하여 사용자가 물건을 찾을 가능성이 높은 장소를 제안할 수 있습니다.
예를 들어:
"지갑은 30분 전까지 테이블 위에서 확인되었습니다. 이후에는 지갑이 더 이상 보이지 않았으며, 해당 시간대에 고양이가 테이블 주변에서 확인되었습니다. 지갑이 테이블 아래나 주변으로 떨어졌을 가능성이 있으니 테이블과 소파 주변을 확인해 보세요."
중요: 이러한 설명은 AI가 확인한 사실이 아니라 가능성을 바탕으로 한 추론이며, 확정된 사실로 사용자에게 전달되어서는 안 됩니다.


