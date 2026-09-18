# Interview Findings → Project Features

## Finding 1. Small everyday items are difficult to find

Participants frequently mentioned items such as glasses, cards, earphones, phones,
hair ties, chargers, and documents.

### Feature: Object Detection

The system detects selected everyday objects from images captured by the room camera.

For the first version, the system can focus on a limited number of objects such as:

- glasses
- wallet
- card
- earphones
- phone
- charger

---

## Finding 2. People usually notice the problem when they need the item

Many participants noticed that an item was missing before going to class,
going outside, going to work, or when they needed to use it.

Some participants said that searching while in a hurry was stressful.

### Feature: Natural-Language Search

The user can quickly ask the system where an item is instead of manually
checking many places.

Example:

User:
"Where are my glasses?"

The system searches the saved information and returns the latest result.

---

## Finding 3. People first search the item's usual location

Participants often checked places such as the desk, bed, table, cupboard,
or bag first because those were the places where they normally kept the item.

When the item was not in its usual place, finding it became more difficult.

### Feature: Save Object Location

When an object is detected, the system saves its location.

Example:

Object: Glasses
Location: On the desk

This allows the system to tell the user where the object was detected instead
of making the user search every possible place.

---

## Finding 4. Existing finder apps do not always provide an exact indoor location

Some participants used Apple Find My or Samsung Find My Device.

They said these services could show that an item was nearby, but they still
had to search for the exact location themselves.

### Feature: Indoor Location Information

The camera-based system provides more specific room-level information.

Example:

Instead of:
"Your AirPods are nearby."

The system can provide:
"Your AirPods were last seen on the desk."

---

## Finding 5. The last place where an item was seen is useful information

Several participants found an item by remembering where they had last used it.

Some participants also said that knowing the last place where an item was
seen would be useful.

### Feature: Last-Seen Location and Time

The system stores:

- object name
- last detected location
- last detected time

Example:

Object: Glasses
Location: Bedside table
Time: 14:30

User:
"Where are my glasses?"

System:
"Your glasses were last seen on the bedside table at 2:30 PM."

---

## Finding 6. A camera cannot detect hidden objects

Some objects may be inside bags, drawers, cupboards, under clothes,
or outside the camera view.

### Feature: Visibility Check and Safe Failure

The system should not guess the location of an object if there is no camera evidence.

Example:

User:
"Where are my AirPods?"

If the system has no recent visible record:

System:
"I could not find your AirPods in the available camera records."
