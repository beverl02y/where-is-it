# PROBLEM

## 1. One-Sentence Problem Definition

University students who cannot remember where they last used or placed an everyday belonging may spend about 5–15 minutes searching several places when they need it, causing stress and a risk of being late.


## 2. Target and Non-Target Users

### 2.1 Primary Target Users
The primary target users are **university students who repeatedly have difficulties in finding everyday belongings inside their room**.

The supported v1 item classes and their canonical names are defined in `ontology.yaml`. This document refers to that shared definition instead of maintaining a separate item list.

The system is particularly relevant to users who:
-   Often forget where they placed an object.
-   Check the same usual locations repeatedly.
-   Need to find an object quickly before leaving home, going to class,
    or going to work.
-   Want more specific indoor location information than existing finder
    applications provided.
-   Want to know where and when an object was last detected.


### Non-Target Users

- Family users who need to manage the belongings of multiple people
- Business users who need to manage many objects or equipment in offices or facilities



## 3. Evidence from User Interviews

The supplied interview records contain responses from ten participants. The following evidence includes quotations with log and question numbers so that each claim can be checked against the source.

The interviews showed several recurring patterns.

### 3.1 Difficulty Finding Small Everyday Objects

Participants described specific situations in which they could not find everyday belongings.

- **Log 1, Q4:** "I noticed that I could not find my card wallet when I needed it before making a payment."

- **Log 3, Q3:** "A recent example was when I could not find my phone before going to work."

- **Log 6, Q4:** "I was about to go to class and wanted to bring my AirPods, but they were not in the usual place."

- **Log 8, Q3:** "One example was when I could not find my hair tie before taking a shower."

- **Log 10, Q3:** "A few days ago, I could not find my glasses before going to class."

Other item types were mentioned in the category questions:

- **Log 10, Q2:** "I usually have difficulty finding my glasses, charger, and student card."

Source: `interview_answers.md`, Participants 1, 3, 6, 8, and 10.

These responses help identify relevant item types for the project. Whether the camera can reliably recognize them must be evaluated separately.


### 3.2 Missing Objects Are Noticed When Needed

Several participants described noticing that an item was missing when they needed to use it or were preparing to leave.

- **Log 1, Q4:** "I noticed that I could not find my card wallet when I needed it before making a payment."

- **Log 6, Q4:** "I was about to go to class and wanted to bring my AirPods, but they were not in the usual place."

- **Log 10, Q4:** "I noticed that I could not find them when I was getting ready to leave."

One participant also described the pressure caused by searching while in a hurry:

- **Log 10, Q8:** "It took around 10 minutes. I was in a hurry, so I became stressed because I could not find them quickly."

Source: `interview_answers.md`, Participants 1, 6, and 10.

These accounts show that searching sometimes interrupted another activity or preparations to leave. Whether the proposed system reduces this search time and pressure needs to be tested.


### 3.3 Users Search Usual Locations First

Several participants began by checking where they normally kept the item.

- **Log 1, Q5:** "I checked my bag first because I usually put it there."

- **Log 6, Q5:** "I checked the table first because that is where I usually put them."

- **Log 10, Q5:** "I checked my desk first because that is where I usually put my glasses."

When the item was not there, participants described searching other places.

- **Log 6, Q6:** "After that, I checked my bag because I thought I might have put them there."

- **Log 10, Q6:** "After that, I checked my bed, bedside table, and bag."

Source: `interview_answers.md`, Participants 1, 6, and 10.

These accounts show a search pattern that starts at the usual storage place and expands to other possible locations when the item is not found.


### 3.4 Limitations of Existing Finder Applications

Two participants reported that finder services helped indicate that an item was nearby but did not identify its exact indoor location.

- **Log 6, Q8:** "Find My Device only shows the general location on a map, but I already know the item is nearby. I need more detailed information."

- **Log 9, Q7:** "It helped, but it only showed that the earbuds were nearby and did not show the exact location."

Source: `interview_answers.md`, Participants 6 and 9.

These accounts suggest that knowing an item is nearby may not be enough when searching for its specific location inside a room.


### 3.5 Importance of the Last-Seen Location

Three participants described finding an item by remembering where they had previously used it.

- **Log 1, Q9:** "I found the card wallet at a copy shop because that was the last place where I used it."

- **Log 6, Q9:** "I finally found the AirPods in a bag under the pillow. I checked the bed because that was where I had used them before."

- **Log 10, Q9:** "I finally found the glasses beside my bed under some clothes. I remembered that I had used them on the bed the previous night."

Source: `interview_answers.md`, Participants 1, 6, and 10.

These accounts suggest that remembering the last-used location can help narrow a search. Whether camera-recorded last-seen information provides a similar benefit remains a hypothesis to be tested.


### 3.6 Visibility Can Affect Whether an Object Is Easy to Find

Some participants described objects being covered by other things or placed inside a bag.

- **Log 2, Q3:** "Documents are difficult to find because they are thin and can easily be hidden under other things."

- **Log 6, Q9:** "I finally found the AirPods in a bag under the pillow."

- **Log 10, Q9:** "I finally found the glasses beside my bed under some clothes."

Source: `interview_answers.md`, Participants 2, 6, and 10.

These accounts show that objects can be difficult to notice when they are covered or hidden.

For the camera-based solution, an object fully hidden from the camera cannot be visually confirmed from that image. If an earlier reliable record exists, the system can report its last recorded location and time without claiming that it is still there.


## 4. Falsification Conditions

### 4.2 Solution Hypothesis

Hypothesis: showing an item's recorded last-seen location and time helps users choose where to search first and reduces their search time.

Test this with five target users. Each participant completes two comparable item-search tasks: one without the system and one with the system. Use different placements and alternate the task order to reduce practice effects.

Record the search time, whether the item was found, and whether the participant first searched the location shown by the system. Apply the same 180-second limit to both tasks. Record an unsuccessful search as 180 seconds and retain its failure status.

Reject or revise the solution hypothesis if either condition occurs:

- Fewer than four of five participants first search the location shown by the system.
- The median search-time reduction is below 30%.

Calculate each participant's reduction as:
(baseline search time - system-assisted search time) / baseline search time × 100.

A baseline time must be greater than zero. If fewer than five participants have valid measurements for both tasks, report INCONCLUSIVE.

These thresholds are proposed rules for a future test. The test has not yet been conducted, and no improvement is claimed.

### 4.2 Solution Hypothesis

The solution hypothesis should be reconsidered if users are given the last-seen location and time of an item but still do not use that information and instead search multiple locations from the beginning.

The hypothesis should also be reconsidered if the provided last-seen information does not help users reduce their search effort.


## 5. Definition of Success

Success will be evaluated using observable behavior during the test described in Section 4.2.

For each participant, record:

| Indicator | What to record |
|---|---|
| Checking the information | Whether the participant reads the last-seen location and time |
| First search location | Where the participant searches first and whether it matches the location shown |
| Search time | The measured time for each task, with and without the system |
| Task completion | Whether the item is found within the time limit |
| Unsuccessful searches | Record timeouts and failures using the procedure in Section 4.2 |

Use the decision thresholds and calculation defined in Section 4.2 to judge the solution hypothesis. Do not remove unsuccessful searches from the results.

If the required measurements are incomplete, report INCONCLUSIVE. If either rejection condition is met, revise the solution hypothesis.

Repeat use can be recorded during a later session if it actually occurs. A participant saying they would use the system again does not count as observed repeat use.

These are planned evaluation measures. No user-test results have been collected for this revision.
