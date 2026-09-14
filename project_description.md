1. Project Overview

Where-Is-It AI is an AI-powered object location tracking and memory assistance system designed to help users find misplaced belongings in their homes or offices.
Instead of requiring users to manually register and track every item, the system uses CCTV or home camera footage and AI-based object recognition to automatically detect objects, record their locations, and track changes over time.
The system aims to answer not only:
"Where is my object?"
but also:
"Where was it last seen?"
"When did it disappear?"
"What happened around that time?"
"Where should I look for it now?"

2. Problem Definition
   
People frequently lose or misplace everyday objects such as wallets, keys, phones, glasses, remote controls, and other personal belongings.
This can happen for several reasons:
The user forgets where they placed an object.
Someone else moves the object.
A pet moves or knocks over the object.
The object falls from its original location.
The user does not remember when or where the object was last seen.
This problem can be particularly challenging for people experiencing memory difficulties, but it can also happen to anyone in their daily life.
Existing object-tracking solutions often require users to attach a physical tracking device or manually register an object. Where-Is-It AI aims to provide a more passive solution using cameras and AI-based visual recognition.

3. Proposed Solution

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

4. Example Scenario
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


