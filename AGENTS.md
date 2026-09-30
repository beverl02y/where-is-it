# AGENTS.md

## 1. Product Context
- Project: Where-Is-It AI.
- Purpose: Help people find misplaced belongings when they cannot remember where they put them.
- Primary target users: University students who repeatedly have difficulty finding everyday belongings inside their rooms.
- Main function: Detect supported items in periodically captured camera images and provide their last recorded location, capture time, and corresponding image.
- Scope: Personal belongings in small rooms, limited to supported items visible to the camera.
- Limitations: Items hidden inside closed drawers or bags cannot be detected. The last recorded location does not guarantee the item's current location.
- Non-target uses: Managing multiple family members' belongings or business equipment.
- Reference: Problem.md for the detailed problem definition, interview evidence, and success criteria.

## 2. Domain Glossary
- Object: name, category.
- Query: questionText, objectName.
- Detection: location, timestamp, confidence.
- Camera: cameraId, room.
- ContextEvent: involvedType (person/pet/object), timestamp.
- Response: answer, confidenceLevel.
- Reference: ontology.yaml for full definitions and relationships.

## 3. Mandatory Rules

## 4. Prohibited Actions

## 5. Coding Conventions

## 6. Definition of Done

## 7. Operational Information
