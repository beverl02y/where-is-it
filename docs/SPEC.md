# Where-Is-It AI --- Specification v1

## 1. Problem Definition

**People who frequently misplace everyday belongings have difficulty in 
quickly determining where an item was last placed or seen, causing
repeated searching, stress, and wasted time when they need the item.**


## 2. Target Users and Non-Target Users

### 2.1 Primary Target Users

The primary target users are **university students who repeatedly have difficulties in 
finding everyday belongings inside their room**.

This version focuses especially on small or frequently used objects
such as:

-   Glasses
-   Wallet
-   Cards
-   Earphones
-   Phone
-   Charger

The system is particularly relevant to users who:

-   Often forget where they placed an object.
-   Check the same usual locations repeatedly.
-   Need to find an object quickly before leaving home, going to class,
    or going to work.
-   Want more specific indoor location information than existing finder
    applications provide.
-   Want to know where and when an object was last detected.

### 2.2 Non-Target Users

This version does not primarily target:

-   Users trying to find belongings lost outside the camera-covered
    environment and trying to track stolen objects over long distances.
-   Large-scale public lost-and-found services.
-   Family users who need to manage the belongings of multiple people
-   Business users who need to manage many objects or equipment in offices or facilities


This project only focuses on **indoor object finding using available camera
evidence**. It is not intended to replace GPS/Bluetooth tracking devices
or public lost-and-found systems.


## 3. Evidence from User Interviews

Ten participants were interviewed about their experiences with misplaced
belongings. All ten participants reported experiencing difficulty
finding personal items. The interviews revealed several recurring
patterns that define the initial requirements of the system.

### 3.1 Difficulty Finding Small Everyday Objects

Participants frequently mentioned difficulty finding small everyday
belongings such as glasses, cards, earphones, phones, chargers,
documents, and hair ties.

Based on this finding, the first version focuses on detecting a limited
set of common objects:

-   Glasses
-   Wallet
-   Card
-   Earphones
-   Phone
-   Charger
-   hairtie 

log 1, 7, 8, 9 (hairtie) and log 1, 6, 7, 10 (card)

### 3.2 Missing Objects Are Usually Noticed When Needed

Many participants noticed that an object was missing when they needed to
use it. eg; 
- preparing to go to class (log 10)
- going to work (log 3)
- going outside (log 7)
- performing another activity that required the object (log 1,2,4,5,6,8,9)

Searching during these situations can be stressful because the user may
be in a hurry. Therefore, the system should allow the user to search
quickly using natural language.

**Example**

> **User:** Where are my glasses?\
> **System:** Your glasses were last seen beside the bed at 8:30 AM.

### 3.3 Users Search Usual Locations First

Participants commonly checked the location where they normally kept an
object before searching elsewhere. Common locations included desks,
beds, tables, cupboards, and bags.  (log (1-6))

When the object was not in its usual location, users had to search
multiple possible places. Therefore, the system should save an object's
detected location so that the user does not need to manually search
every possible place.


### 3.4 Limitations of Existing Finder Applications

Some participants had experience using Apple Find My or Samsung Find My
Device. These services could help indicate that an item was nearby, but
participants still had difficulty identifying the object's specific
indoor location. log(1, 9, 6)

The camera-based system therefore aims to provide more specific
room-level information based on visual evidence.

### 3.5 Importance of Last-Seen Location and Time

Several participants found missing objects by remembering where they had
last used or seen them (log 3, 6, 7, 8, 9, 10). Therefore, the system should store:

-   Object name
-   Last detected location
-   Last detected time

### 3.6 Camera Visibility and Evidence Limitations

A camera cannot detect every object at all times. An object may be
inside a bag, drawer, or cupboard, under clothes, or outside the
camera's field of view. (log 1-6)

Therefore, the system must not guess an object's location when there is
no reliable camera evidence. Confirmed detections should be presented as
facts, while uncertain information should be clearly presented as a
possibility.


## 4. Solution and MVP Scope

### 4.1 Core Function

**Where-Is-It AI** is a camera-based AI assistant that helps users
locate misplaced belongings. The system detects supported objects from
indoor camera images, stores their detected location and time, and
allows the user to ask where an object is using natural language.

The system follows a simple principle:

> **Detect → Save → Search → Explain**

When an object is visible, the system records where and when it was
detected. When the user asks for the object, the system first checks the
most recent camera information. If the object is not currently visible,
it searches historical records and reports the last confirmed location.

### 4.2 MVP Features

The first version includes the following core features:

1.  **Object Detection**\
    Detect supported everyday objects from camera images.

2.  **Location Recording**\
    Save the object name, detected location, timestamp, and
    detection confidence.

3.  **Natural-Language Search**\
    Allow the user to ask questions such as:

    -   "Where are my glasses?"
    -   "Where is my wallet?"

4.  **Current Location Search**\
    Search the most recent camera records for the requested object.

5.  **Last-Seen Search**\
    If the object is not currently visible, return its most recent
    confirmed location and time.

6.  **Confidence-Based Response**\
    Clearly distinguish between confirmed detections and uncertain
    possibilities.

7.  **Safe Failure**\
    If there is not enough evidence or if the confedience level is under 75%, tell the user that the object could
    not be found instead of guessing.

### 4.3 MVP Object Scope

The initial supported object classes are:

-   Glasses
-   Wallet
-   Card
-   Earphones
-   Phone
-   Charger
-   Hairtie

Additional objects can be added after the first version is tested.

### 4.4 Out of Scope for v1

The following functions are not required for the first version:

- Multiple-camera support
- Cross-room object tracking
- Predictive search
- Smart-home integration
- Speech interaction
- User preference learning
- Improved contextual analysis

## 5User Interface

For v1, the user interacts with Where-Is-It AI through a simple text-based interface.

#### Input

The user enters a natural-language question about the location of an
object.

Examples:

> "Where are my glasses?"

> "Where is my wallet?"

The system identifies the requested object and searches the available
camera records.

#### Output

The system returns a text response containing the available location
information.

Depending on the available evidence, the response may include:

- Current detected location
- Last-seen location
- Last-seen time
- Detection confidence
- Search suggestion when appropriate
- A message explaining that no reliable record is available

Example:

> Your glasses were last seen on the bedside table at 2:


## 6. Acceptance Criteria

The following criteria define the conditions that should be satisfied
for the first version of Where-Is-It AI to be considered successful.

### 6.1 Functional Acceptance Criteria

  -----------------------------------------------------------------------
  ID                      Function                Acceptance Criterion
  ----------------------- ----------------------- -----------------------
  AC-01                   Object Detection        The system can detect
                                                  the supported v1
                                                  objects from the single
                                                  camera records.

  AC-02                   Natural-Language Search The user can search for
                                                  an object using a
                                                  simple question such as
                                                  "Where are my glasses?"

  AC-03                   Current Detection       If an object is
                                                  currently visible with
                                                  at least 75%
                                                  confidence, the system
                                                  returns its detected
                                                  location, time, and
                                                  confidence.

  AC-04                   Historical Search       If the object is not
                                                  currently visible, the
                                                  system searches the
                                                  historical detection
                                                  records.

  AC-05                   Last-Seen Information   If a reliable
                                                  historical record
                                                  exists, the system
                                                  returns the object's
                                                  last confirmed location
                                                  and time.

  AC-06                   Contextual Suggestion   If useful contextual
                                                  evidence exists, the
                                                  system may provide a
                                                  possible search area
                                                  while clearly
                                                  indicating that it is
                                                  not a confirmed
                                                  location.
  -----------------------------------------------------------------------

### 6.2 Error and Uncertainty Handling

The system should handle unavailable or uncertain information without
presenting guesses as facts.

  -----------------------------------------------------------------------
  Situation                           Expected Behavior
  ----------------------------------- -----------------------------------
  Detection confidence is below 75%   Do not present the detection as a
                                      confirmed location.

  No current detection exists         Search historical records.

  No reliable current or historical   Inform the user that the object
  record exists                       could not be found in the available
                                      camera records.

  Object name is ambiguous            Ask the user to clarify the
                                      requested object.

  Object is outside the camera view   Explain that there is not enough
                                      camera evidence to determine its
                                      location.

  Contextual evidence is uncertain    Present the result only as a
                                      possibility, not a confirmed fact.
  -----------------------------------------------------------------------

The system must not claim 100% certainty from visual detection or accuse
a person or pet of moving an object.

### 6.3 Quantitative Acceptance Criteria

The following values are initial targets for evaluating v1:

  Metric                                                 Target
  ---------------------------------------------- --------------
  Minimum confirmed detection confidence                  ≥ 75%
  Common-object detection accuracy                       \> 90%
  False positive rate                                     \< 5%
  Current image search time                        \< 2 seconds
  Total response time                              \< 6 seconds
  Queries needed when reliable evidence exists              ≤ 2
  False-certainty rate                                    \< 2%

These values are initial targets and may be adjusted after
implementation and user testing.