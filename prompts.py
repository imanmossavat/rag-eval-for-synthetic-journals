"""
prompts.py — Pipeline prompts
==============================
All LLM prompts live here. Editing a prompt does not require touching
any stage file. Each prompt is a plain module-level string constant.

Prompt naming convention:
    STAGE_01_WORLD_STATE
    STAGE_02_EVENT_TIMELINE
    STAGE_04_NOTE_GENERATION
    STAGE_05_QA
"""

# ── Stage 01 — World state ────────────────────────────────────────────────────

STAGE_01_WORLD_STATE = """You are generating the hidden world state for a synthetic personal knowledge dataset used for retrieval-augmented generation (RAG) evaluation.

Generate a realistic long-term life simulation for ONE primary user.

The output should resemble the messy continuity of a real person's life rather than a neatly constructed fictional character profile.

GOALS

The dataset should support:
- longitudinal memory retrieval
- conflicting memory resolution
- temporal reasoning
- entity disambiguation
- incomplete task tracking
- evolving relationships
- mundane recurring details
- emotionally realistic inconsistencies

The simulation should feel partially unfinished, uneven, and organically evolving.

REQUIREMENTS

Core structure:
- One primary user only
- <<MIN_ENTITIES>>–<<MAX_ENTITIES>> recurring entities
- At least <<MIN_STORY_ARCS>> story arcs, each with an ordered list of 3–5
  phases describing how it could unfold over time (earliest phase first),
  and varied scale — not all life-defining. A single-phase arc is a short,
  already-settled thread with nothing left to develop; a multi-phase arc
  still has room to evolve.
- Mixture of: work, relationships, family, logistics, finances, health,
  hobbies, routines, travel, digital life, home maintenance
- Some entities should recur across multiple domains
- Some entities should overlap semantically to create retrieval ambiguity
- Entity names should admit natural surface variants a journaler would use
  (nicknames, shortened forms, role descriptions like "Ethan's mother")
- Include both major life events and mundane repetitive behaviors

Realism requirements:
- Not every entity should be equally important
- Include dormant or low-activity periods
- Include abandoned habits, stale plans, and forgotten intentions
- Include recurring annoyances and low-stakes routines
- Include unfinished admin tasks and minor repeated failures
- Include emotionally irrational behavior occasionally
- Include inconsistencies between stated intentions and actual behavior
- Include things the user avoids thinking about
- Include changing priorities over time

Temporal requirements:
- Include explicit dates or relative timelines
- Include temporal dependencies between events
- Some facts should later be corrected, revised, or contradicted
- Some plans should quietly disappear without resolution
- Include recurring weekly patterns with occasional disruptions
- Ensure not all story arcs peak simultaneously

Social coherence requirements:
- Entities should know each other in overlapping ways
- Relationships should influence unrelated domains
- Include mild interpersonal tensions, obligations, favors, or asymmetries
- Some entities should appear disproportionately often

Health and behavioral realism:
- Health issues should affect scheduling, mood, work, spending, or routines
- Habits should fluctuate instead of remaining perfectly consistent
- Include coping mechanisms, avoidance behaviors, or self-tracking systems

Financial/logistical realism:
- Financial anxiety should have concrete causes
- Include subscriptions, repairs, appointments, insurance, taxes, scheduling friction
- Include realistic tradeoffs between time, money, energy, and social obligations

RAG DIFFICULTY REQUIREMENTS

The world state should contain:
- overlapping contexts and recurring entities in multiple topics
- ambiguous references and evolving facts
- partially outdated beliefs and stale reminders
- repeated mentions of the same object or project over time
- realistic memory fragmentation

Avoid:
- perfectly clean timelines or overly dramatic lives
- every event being equally important
- isolated entities with no social overlap
- profiles where every detail is narratively meaningful

Return ONLY valid JSON. No markdown, no explanation, no code fences.

Schema:
{
  "user_profile": {
    "user_id": "u_001",
    "name": "...",
    "age": 0,
    "occupation": "...",
    "location": "...",
    "baseline_traits": ["..."]
  },
  "entities": [
    {
      "id": "...",
      "name": "...",
      "type": "person | place | project | object | organization | habit",
      "domains": ["..."],
      "salience": "low | medium | high",
      "notes": "..."
    }
  ],
  "story_arcs": [
    {
      "arc_id": "...",
      "title": "...",
      "phases": ["...", "..."],
      "involved_entities": ["..."],
      "summary": "..."
    }
  ],
  "projects": [
    {
      "project_id": "...",
      "title": "...",
      "status": "active | paused | abandoned | completed",
      "related_entities": ["..."],
      "notes": "..."
    }
  ],
  "latent_facts": [
    {
      "fact_id": "...",
      "subject": "...",
      "relation": "...",
      "object": "...",
      "arc_id": "...",
      "confidence": "assumed | confirmed | contradicted"
    }
  ]
}"""


# ── Stage 02 — Event timeline ─────────────────────────────────────────────────

STAGE_02_EVENT_TIMELINE = """Using the provided world state and event skeletons, generate a chronological event timeline.

You are simulating a noisy, partially incomplete human memory system, not a narrative story.

The event skeletons below have their structure pre-filled (story_arc_id, involved_entities,
timestamp). You must only write the following fields for each event:
- text               : a natural-language description of what happened
- latent_fact_updates: how a latent fact changed, was reinforced, or contradicted
- importance         : integer 1–5
- affect             : the emotional tone of the event (see Affect Rules below)

Do NOT change event_id, timestamp, story_arc_id, or involved_entities.

Core Requirements

Generate event text that:
- Evolves existing story arcs explicitly over time
- Includes recurring routines and meetings with realistic irregularity
- Includes cancellations, reschedules, and partial completions
- Includes temporal dependencies (later events depend on earlier ones)
- Occasionally introduces conflicting or corrected information

Realism Constraints
- Not all arcs progress evenly or continuously
- Some tasks remain perpetually unfinished
- Behavior must reflect inconsistency between intent and action
- Avoid uniform importance distribution

Latent Fact Rules (CRITICAL)
latent_fact_updates must:
- Represent a change, reinforcement, contradiction, or activation
- Be event-specific — not a repeated static fact
- NOT repeat latent facts verbatim unless explicitly recontextualized

Contradiction events (those with _contradiction_of set):
- MUST introduce a different outcome, revised fact, or changed status
  compared to the event they reference
- Do NOT simply repeat the earlier event with different wording

Affect Rules
affect must be an object: {"emotion": "...", "valence": -1|0|1, "intensity": 0-3}
- emotion   : a short free-text label for the feeling in this event, in your
              own words — do not force it into a fixed list
- valence   : -1 negative, 0 neutral, 1 positive
- intensity : 0 none, 1 mild, 2 moderate, 3 strong
Ground affect in what the event text itself implies — do not invent a feeling
that contradicts the event's tone.

Return ONLY valid JSON. No markdown, no commentary, no extra keys.

{
  "events": [
    {
      "event_id": "...",
      "timestamp": "YYYY-MM-DDTHH:MM:SS",
      "event_type": "...",
      "text": "...",
      "involved_entities": ["..."],
      "story_arc_id": "...",
      "latent_fact_updates": ["..."],
      "importance": 1,
      "affect": {"emotion": "...", "valence": 0, "intensity": 0}
    }
  ]
}"""


# ── Stage 04 — Note generation ────────────────────────────────────────────────

STAGE_04_NOTE_GENERATION = """Convert the structured event into a realistic personal note.

Requirements:
- Natural language, imperfect human writing style
- Concise, sometimes partial or incomplete
- Sometimes references prior context implicitly
- Maintain consistency with entities and timeline
- Do not make the note sound polished or fully resolved
- Prefer a lived-in, messy memory fragment style

Apply 1–3 of the following rules (pick randomly, never apply all):

OMISSION — leave out one concrete detail from the event (the person's name,
  the exact date, or the outcome). The note should feel like the writer
  didn't bother to write everything down.

ABRUPT_END — stop the note mid-thought as if the writer got distracted.
  Do not add a conclusion or summary sentence.

IMPLICIT_REFERENCE — mention something from a prior event without explaining
  it. Use phrases like "the usual thing", "same as before", or "like last time"
  without clarifying what that means. Do NOT attach an invented name to the
  callback — either refer back to an entity that is in the Context by its name,
  or leave the reference unnamed ("the usual thing again").

UNCERTAINTY — express doubt about a fact: "think it was Tuesday",
  "not sure if I already replied", "might have been €200, can't remember".

LATENT_FACT_AS_TEXTURE — do not state the latent fact directly. Let it
  colour the tone instead. If the latent fact is "user is avoiding thinking
  about rent", the note might just say "didn't open the bank app again".

CRITICAL: latent_facts in the output JSON must represent a state transition,
not a summary of the event text.
Bad:  "user attended the meeting"
Good: "user now knows the deadline moved — activates the anxiety arc"

NAMING CONSTRAINT (hard rule — do not break):
- You may only use proper names of people, places, projects, or organizations
  that appear in the Context above. Do NOT invent new named characters.
- For anyone or anything not in the Context, refer to them generically —
  "a friend", "someone", "the neighbour", "the client" — never a made-up name.
  (A note that invents a name like "Marcus" who is not in the Context is wrong.)

GROUND-TRUTH FIELDS (benchmark gold labels — fill them carefully):
- "entities": the ids (from the Context above) of every entity the note text
  refers to, as plain strings like "p_013". Implicit or unnamed references
  count — if OMISSION dropped the name but the note still refers to that
  entity, its id belongs in the list. Never invent ids not in the Context.
- "tags": 2–5 short lowercase topic tags a journaling app user might attach,
  grounded in this event and its story arc (e.g. "car repair", "budget",
  "team meeting"). Prefer the arc's recurring vocabulary so the same topic
  gets the same tag across notes.
- "renderings": for EACH entity id in the event's involved_entities, declare how
  this note refers to it, as an object:
    {"entity_id": "<id>", "explicit": true|false, "as": "<surface form>" | null}
  - explicit true  → you wrote the entity's actual name/label in the text; set
    "as" to that exact surface string (must appear verbatim in the text).
  - explicit false → you referred to it obliquely; set "as" to the oblique
    phrase you used (e.g. "the small business series").
  - not referenced in the text at all → explicit false, "as": null.
  Oblique reference is realistic and encouraged for habitual/background things —
  but declare it honestly here; do not claim explicit unless the name is in text.

Return ONLY valid JSON:
{
  "note_id": "",
  "timestamp": "",
  "note_type": "personal",
  "text": "",
  "entities": ["p_001"],
  "tags": ["example tag"],
  "latent_facts": [],
  "story_arc_id": "",
  "importance": "",
  "renderings": [{"entity_id": "p_001", "explicit": false, "as": null}]
}"""


# ── Stage 05 — QA generation ──────────────────────────────────────────────────

STAGE_05_QA = """You are generating a question-answer pair for a RAG benchmark dataset.

You are given a set of personal notes (the retrieval corpus).
The question must be answerable ONLY from these notes — no outside knowledge.

QA type: {qa_type}

Type-specific instructions:
- single_hop:          Question answerable from exactly one note. Keep it concrete.
- multi_hop:           Question that REQUIRES combining information from all notes given.
                       The answer cannot be found in any single note alone.
- temporal_reasoning:  Question whose answer depends on the ORDER of events.
                       e.g. "What changed between the first and last mention of X?"
- conflict_resolution: Two notes contradict each other. The question must ask
                       the reader to identify or resolve the contradiction.
                       e.g. "The notes give two different statuses for X — which is more recent?"
- unanswerable:        The notes hint at something but do not contain the answer.
                       The correct answer is "cannot be determined from the notes."

Notes (these are the ONLY source of truth):
{notes_text}

Rules:
- Answer must be literally supported by the notes — no inference beyond what is stated
- Do not invent facts not present in the notes
- Keep the question specific and unambiguous
- The answer should be 1–3 sentences maximum

Return ONLY valid JSON:
{{
  "question": "...",
  "answer": "...",
  "reasoning_type": "{qa_type}",
  "supporting_notes": {note_ids},
  "required_hops": {hop_count},
  "difficulty": "easy | medium | hard"
}}"""


# ── Stage 05 (v2) — question-only generation + narrow verification ──────────────
# WHY these exist: STAGE_05_QA above has the model invent the question AND the
# answer key in one call, from raw note prose, with nothing checking the output
# afterward -- that's the root cause traced in REPORT_datagen_grounding.md. The
# prompts below split the job: the answer is pinned in code to a fact the pipeline
# already knows (a note's own latent_facts entry, a chronological order, a known
# contradiction pairing), and the model's only job is to phrase a question that
# fact would answer. See stage_05_qa_generation.py for how each QA type computes
# its pinned fact(s) before calling STAGE_05_QUESTION_ONLY.

STAGE_05_QUESTION_ONLY = """You are writing ONE question for a RAG benchmark dataset.

A fact below is already known to be true and has already been checked against the notes
elsewhere in this pipeline -- you are not being asked to judge it, and you are not writing
the answer. Your ONLY job is to phrase a natural, specific question that this fact answers.

QA type: {qa_type}

Notes (context, for phrasing only -- the source of the question's wording, not its answer):
{notes_text}

Fact(s) the question must resolve to (do not repeat this in the question itself):
{given_facts}

{type_instruction}

Rules:
- Write a question a person could plausibly ask about their own notes.
- Do NOT reveal the fact's content in the question.
- Be specific and unambiguous -- avoid vague wording like "what happened."
- Do NOT invent details beyond what is in the notes or the given fact(s).

Return ONLY valid JSON, no markdown, no commentary:
{{
  "question": "..."
}}"""

STAGE_05_UNANSWERABLE_QUESTION = """You are writing ONE question for a RAG benchmark dataset.

The note below hedges or hints at something without stating it outright. Write a question
about the SPECIFIC unresolved thing the note hints at -- not about anything else the note
also mentions. Do not answer the question yourself, and do not resolve the uncertainty.

Note:
{notes_text}

Return ONLY valid JSON, no markdown, no commentary:
{{
  "question": "..."
}}"""

# Narrow verifier: "does this one note actually support this one fact string" -- a much
# easier judging task than grading a whole free-form QA pair (see RECOMMENDATIONS.md #1
# and the calibration failure of the old broad gate in REPORT_datagen_grounding.md).
STAGE_05_FACT_CHECK = """You are an independent fact-checker. You did NOT write this note or \
this fact. Using ONLY the note text below, decide whether the note actually states or \
directly and specifically supports the given fact -- not just mentions the same topic.

NOTE:
{note_text}

CANDIDATE FACT:
{fact_text}

Return ONLY valid JSON, no markdown, no commentary:
{{
  "supported": true | false,
  "quote": "the exact phrase from the note your verdict rests on, or null",
  "explanation": "one sentence"
}}"""

# Blind Q&A check for unanswerable pairs -- reused near-verbatim from grounding_gate.py's
# v3 UNANSWERABLE_PROMPT, which is the one part of that gate calibration proved reliable
# (3/4 known defects caught). Deliberately never mentions that the pair was constructed
# to be unanswerable, so the model isn't anchored toward confirming that label.
STAGE_05_BLIND_ANSWER_CHECK = """Answer the question below using ONLY the notes provided. Do \
not use outside knowledge and do not guess beyond what the notes state.

QUESTION: {question}

NOTES (the ONLY source you may use):
{notes_text}

If the notes state or clearly imply a specific, concrete answer to the question, give that \
exact answer and quote the sentence it comes from.

If the notes do NOT contain enough information to answer the question -- they only hint at \
it, hedge about it, or never address it at all -- say you cannot answer it.

Return ONLY valid JSON, no markdown, no commentary:
{{
  "can_answer": true | false,
  "answer": "the specific answer you found stated in the notes, or null if you cannot answer",
  "quote": "the exact sentence from the notes that supports your answer, or null",
  "explanation": "one sentence"
}}"""