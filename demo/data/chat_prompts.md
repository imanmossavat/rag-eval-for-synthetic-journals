# Prompts to paste into a Claude chat
## 1. World (save the JSON reply as `data/world.json`)
Design the HIDDEN FACTS behind a fictional person's 30-day diary (days 1-30).
This is test data for a memory benchmark: every fact becomes a question with a known answer,
so precision matters more than flair. Return JSON matching the schema.

- narrator: a first name and a city.
- people: exactly 4 people close to the narrator. id "P1".."P4". relation is ONE lowercase
  word, all different (e.g. sister, colleague, neighbour, roommate). name: a distinct first
  name. intro_day: 2-8 (the day the diary first introduces them).
- facts: exactly 8 stable facts. id "F1".."F8". subject is "ME" or a person id.
  attribute is a short noun phrase that reads naturally after "my" or "Lena's"
  (e.g. "dog's name", "favourite cafe", "car"). value: 1-3 words, distinctive (a proper
  noun or brand is ideal), never a common word. day: 3-28, and for a person it must be
  AFTER that person's intro_day.
  * At least 3 attributes must appear twice, for two different subjects (look-alike pairs,
    e.g. the narrator's "dog's name" and Lena's "dog's name").
  * At least 5 facts must be about people (not ME).
- changes: exactly 3 things about the narrator that change over the month. id "C1".."C3".
  attribute e.g. "workplace", "phone", "running shoes". history: values in order with strictly
  increasing days (2-29); one change has 3 values, the others 2. Values distinctive.
- habits: exactly 2 recurring activities. id "H1","H2". activity: base-form verb phrase
  ("go bouldering"). keyword: one distinctive lowercase word that names the activity
  ("bouldering"). days: H1 has 7 distinct days, H2 has 3 distinct days.
- never_mentioned: exactly 3 (subject, attribute) pairs about people (P1-P4) that are
  plausible questions but are NEVER stated. Prefer an attribute that someone else has in
  `facts` (e.g. ask about P2's "car" when the narrator has a car).

Hard rules: all values (facts and change histories) are different from each other and from
the city; no value contains a person's name; no keyword appears inside any value.

JSON schema:
```json
{
 "type": "object",
 "properties": {
  "narrator": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "city": {
     "type": "string"
    }
   },
   "required": [
    "name",
    "city"
   ],
   "additionalProperties": false
  },
  "people": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "string"
     },
     "name": {
      "type": "string"
     },
     "relation": {
      "type": "string"
     },
     "intro_day": {
      "type": "integer"
     }
    },
    "required": [
     "id",
     "name",
     "relation",
     "intro_day"
    ],
    "additionalProperties": false
   }
  },
  "facts": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "string"
     },
     "subject": {
      "type": "string"
     },
     "attribute": {
      "type": "string"
     },
     "value": {
      "type": "string"
     },
     "day": {
      "type": "integer"
     }
    },
    "required": [
     "id",
     "subject",
     "attribute",
     "value",
     "day"
    ],
    "additionalProperties": false
   }
  },
  "changes": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "string"
     },
     "attribute": {
      "type": "string"
     },
     "history": {
      "type": "array",
      "items": {
       "type": "object",
       "properties": {
        "value": {
         "type": "string"
        },
        "day": {
         "type": "integer"
        }
       },
       "required": [
        "value",
        "day"
       ],
       "additionalProperties": false
      }
     }
    },
    "required": [
     "id",
     "attribute",
     "history"
    ],
    "additionalProperties": false
   }
  },
  "habits": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "id": {
      "type": "string"
     },
     "activity": {
      "type": "string"
     },
     "keyword": {
      "type": "string"
     },
     "days": {
      "type": "array",
      "items": {
       "type": "integer"
      }
     }
    },
    "required": [
     "id",
     "activity",
     "keyword",
     "days"
    ],
    "additionalProperties": false
   }
  },
  "never_mentioned": {
   "type": "array",
   "items": {
    "type": "object",
    "properties": {
     "subject": {
      "type": "string"
     },
     "attribute": {
      "type": "string"
     }
    },
    "required": [
     "subject",
     "attribute"
    ],
    "additionalProperties": false
   }
  }
 },
 "required": [
  "narrator",
  "people",
  "facts",
  "changes",
  "habits",
  "never_mentioned"
 ],
 "additionalProperties": false
}
```

## 2. Notes (save the JSON reply as `data/note_texts.json`)
Long list: if the reply gets cut off, paste the plans in chunks of ~20.

Below is a JSON list of planned diary notes for a fictional person (Noor, lives in Utrecht).
For EACH plan write one private diary entry: first person, casual, 50-110 words, concrete
everyday detail, no title, no date line. The entry must convey the plan's "statement", must
contain every string in "must_include" exactly, and must not contain ANY word in
"must_exclude". Do not mention any other people by name.
Return only JSON: an object mapping each plan "id" to its text, e.g. {"N001": "...", ...}.

[
 {
  "id": "N001",
  "date": "2026-03-03",
  "statement": "My workplace is Bakkerij Vos.",
  "must_include": [
   "Bakkerij Vos"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N002",
  "date": "2026-03-03",
  "statement": "Introduce my sister Femke naturally, through something we did together.",
  "must_include": [
   "Femke",
   "sister"
  ],
  "must_exclude": [
   "Tomasz",
   "Ines",
   "Kofi",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N003",
  "date": "2026-03-03",
  "statement": "Nothing special happened. Write about: watering plants. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N004",
  "date": "2026-03-03",
  "statement": "Nothing special happened. Write about: paying bills. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N005",
  "date": "2026-03-03",
  "statement": "Nothing special happened. Write about: groceries and prices. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N006",
  "date": "2026-03-03",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N007",
  "date": "2026-03-03",
  "statement": "Nothing special happened. Write about: watering plants. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N008",
  "date": "2026-03-04",
  "statement": "My dog's name is Pickle.",
  "must_include": [
   "Pickle"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N009",
  "date": "2026-03-04",
  "statement": "Nothing special happened. Write about: a rainy evening in. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N010",
  "date": "2026-03-04",
  "statement": "My phone is Fairphone 4.",
  "must_include": [
   "Fairphone 4"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N011",
  "date": "2026-03-04",
  "statement": "Nothing special happened. Write about: paying bills. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N012",
  "date": "2026-03-05",
  "statement": "Nothing special happened. Write about: groceries and prices. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N013",
  "date": "2026-03-05",
  "statement": "Nothing special happened. Write about: watering plants. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N014",
  "date": "2026-03-05",
  "statement": "Nothing special happened. Write about: watering plants. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N015",
  "date": "2026-03-05",
  "statement": "Introduce my colleague Tomasz naturally, through something we did together.",
  "must_include": [
   "Tomasz",
   "colleague"
  ],
  "must_exclude": [
   "Femke",
   "Ines",
   "Kofi",
   "sister",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N016",
  "date": "2026-03-05",
  "statement": "Nothing special happened. Write about: a train delay. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N017",
  "date": "2026-03-06",
  "statement": "My running shoes is Asics Novablast.",
  "must_include": [
   "Asics Novablast"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N018",
  "date": "2026-03-06",
  "statement": "Introduce my neighbour Ines naturally, through something we did together.",
  "must_include": [
   "Ines",
   "neighbour"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Kofi",
   "sister",
   "colleague",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N019",
  "date": "2026-03-06",
  "statement": "Nothing special happened. Write about: paying bills. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N020",
  "date": "2026-03-07",
  "statement": "My favourite cafe is Koffie Kantoor.",
  "must_include": [
   "Koffie Kantoor"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N021",
  "date": "2026-03-07",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N022",
  "date": "2026-03-08",
  "statement": "Introduce my roommate Kofi naturally, through something we did together.",
  "must_include": [
   "Kofi",
   "roommate"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "sister",
   "colleague",
   "neighbour",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N023",
  "date": "2026-03-08",
  "statement": "Nothing special happened. Write about: something you cooked. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N024",
  "date": "2026-03-09",
  "statement": "Nothing special happened. Write about: a TV series episode. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N025",
  "date": "2026-03-09",
  "statement": "Today I did this: go swimming.",
  "must_include": [
   "swimming"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering"
  ]
 },
 {
  "id": "N026",
  "date": "2026-03-10",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N027",
  "date": "2026-03-10",
  "statement": "Femke's dog's name is Biscotti.",
  "must_include": [
   "Femke",
   "Biscotti"
  ],
  "must_exclude": [
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N028",
  "date": "2026-03-11",
  "statement": "Ines's car is Fiat Panda.",
  "must_include": [
   "Ines",
   "Fiat Panda"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N029",
  "date": "2026-03-11",
  "statement": "Nothing special happened. Write about: paying bills. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N030",
  "date": "2026-03-11",
  "statement": "Nothing special happened. Write about: a rainy evening in. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N031",
  "date": "2026-03-12",
  "statement": "Nothing special happened. Write about: a podcast you listened to. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N032",
  "date": "2026-03-13",
  "statement": "Nothing special happened. Write about: errands in town. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N033",
  "date": "2026-03-13",
  "statement": "Tomasz's favourite cafe is Bar Bolle.",
  "must_include": [
   "Tomasz",
   "Bar Bolle"
  ],
  "must_exclude": [
   "Femke",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N034",
  "date": "2026-03-14",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N035",
  "date": "2026-03-14",
  "statement": "Nothing special happened. Write about: something you cooked. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N036",
  "date": "2026-03-15",
  "statement": "My workplace has changed: it is now Openbare Bibliotheek. Do not name what it was before.",
  "must_include": [
   "Openbare Bibliotheek"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N037",
  "date": "2026-03-15",
  "statement": "Nothing special happened. Write about: a TV series episode. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N038",
  "date": "2026-03-16",
  "statement": "Kofi's car is Volvo Amazon.",
  "must_include": [
   "Kofi",
   "Volvo Amazon"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N039",
  "date": "2026-03-17",
  "statement": "Today I did this: go swimming.",
  "must_include": [
   "swimming"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering"
  ]
 },
 {
  "id": "N040",
  "date": "2026-03-18",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N041",
  "date": "2026-03-19",
  "statement": "Nothing special happened. Write about: a TV series episode. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N042",
  "date": "2026-03-19",
  "statement": "Nothing special happened. Write about: a rainy evening in. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N043",
  "date": "2026-03-19",
  "statement": "Femke's favourite band is Golden Earring.",
  "must_include": [
   "Femke",
   "Golden Earring"
  ],
  "must_exclude": [
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N044",
  "date": "2026-03-20",
  "statement": "Nothing special happened. Write about: something you cooked. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N045",
  "date": "2026-03-20",
  "statement": "My phone has changed: it is now Pixel 8. Do not name what it was before.",
  "must_include": [
   "Pixel 8"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N046",
  "date": "2026-03-20",
  "statement": "Nothing special happened. Write about: a bad night's sleep. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N047",
  "date": "2026-03-20",
  "statement": "Nothing special happened. Write about: something you cooked. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N048",
  "date": "2026-03-20",
  "statement": "Nothing special happened. Write about: rearranging furniture. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N049",
  "date": "2026-03-21",
  "statement": "Nothing special happened. Write about: a bad night's sleep. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N050",
  "date": "2026-03-21",
  "statement": "Kofi's home town is Paramaribo.",
  "must_include": [
   "Kofi",
   "Paramaribo"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N051",
  "date": "2026-03-22",
  "statement": "Nothing special happened. Write about: watering plants. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N052",
  "date": "2026-03-23",
  "statement": "My running shoes has changed: it is now Hoka Clifton. Do not name what it was before.",
  "must_include": [
   "Hoka Clifton"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N053",
  "date": "2026-03-24",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N054",
  "date": "2026-03-26",
  "statement": "My workplace has changed: it is now Museum Speelklok. Do not name what it was before.",
  "must_include": [
   "Museum Speelklok"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N055",
  "date": "2026-03-28",
  "statement": "Today I did this: go bouldering.",
  "must_include": [
   "bouldering"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "swimming"
  ]
 },
 {
  "id": "N056",
  "date": "2026-03-28",
  "statement": "Nothing special happened. Write about: cleaning the flat. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N057",
  "date": "2026-03-29",
  "statement": "Nothing special happened. Write about: a podcast you listened to. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 },
 {
  "id": "N058",
  "date": "2026-03-30",
  "statement": "Today I did this: go swimming.",
  "must_include": [
   "swimming"
  ],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering"
  ]
 },
 {
  "id": "N059",
  "date": "2026-03-31",
  "statement": "Nothing special happened. Write about: a slow work afternoon. No other people by name.",
  "must_include": [],
  "must_exclude": [
   "Femke",
   "Tomasz",
   "Ines",
   "Kofi",
   "sister",
   "colleague",
   "neighbour",
   "roommate",
   "Pickle",
   "Biscotti",
   "Koffie Kantoor",
   "Bar Bolle",
   "Fiat Panda",
   "Volvo Amazon",
   "Golden Earring",
   "Paramaribo",
   "Bakkerij Vos",
   "Openbare Bibliotheek",
   "Museum Speelklok",
   "Fairphone 4",
   "Pixel 8",
   "Asics Novablast",
   "Hoka Clifton",
   "bouldering",
   "swimming"
  ]
 }
]