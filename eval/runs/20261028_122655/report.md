# Pipeline-corpus eval — 20261028_122655

Cold-reader pass (REPORTING_STANDARDS rule 2): ___________  (DRAFT until filled)

- corpus `v20260717T062821Z_9eff22baacb0`, 77 notes, 20 questions; data files match MANIFEST: yes
- answering model `qwen3:4b`, retriever dense cosine, nomic-embed-text, K=5
- judge: `qwen3:30b`

### Retrieval (answerable questions)

| type | n | precision@K | recall@K | hit@K | all@K | MRR |
|---|---|---|---|---|---|---|
| single_hop | 6 | 0.13 | 0.67 | 0.67 | 0.67 | 0.44 |
| multi_hop | 6 | 0.30 | 0.75 | 1.00 | 0.50 | 0.58 |
| temporal_reasoning | 2 | 0.30 | 0.75 | 1.00 | 0.50 | 0.75 |
| conflict_resolution | 3 | 0.33 | 0.83 | 1.00 | 0.67 | 0.83 |
| **all** | 17 | 0.25 | 0.74 | 0.88 | 0.59 | 0.60 |

### Answer labels by type

| label | meaning | single_hop | multi_hop | temporal_reasoning | conflict_resolution | unanswerable | all |
|---|---|---|---|---|---|---|---|
| CORRECT_REFUSAL | unanswerable question, correctly said 'I don't know' | 0 | 0 | 0 | 0 | 2 | 2 |
| FAILED_REFUSAL | unanswerable question, made an answer up | 0 | 0 | 0 | 0 | 1 | 1 |
| CORRECT | matches the evidence notes | 4 | 2 | 1 | 3 | 0 | 10 |
| CONTRADICTS_NOTES | says something the evidence notes contradict | 1 | 0 | 0 | 0 | 0 | 1 |
| OTHER_NOTES | rests on a shown note outside the answer key; a human should check the key | 1 | 4 | 1 | 0 | 0 | 6 |

**Right: 12/20** (CORRECT + CORRECT_REFUSAL). Judge labels are advisory until a human has checked them.

**Judged correct without all the evidence shown:** q_0002 (none), q_0003 (none), q_0012 (some), q_0025 (some). Either a lucky guess, a near-duplicate note carrying the same fact, or a judge mistake. Check these first.

### Every answer that isn't right, with its evidence

| q | type | question | evidence | retrieved (rank order) | shown | reply | label | judge rationale |
|---|---|---|---|---|---|---|---|---|
| q_0004 | single_hop | What did I decide to do about coffee after seeing the price at The Blue Mitten? | N_202401072054 | N_202401072054, N_202401011151, N_202401220517, N_202401050202, E_202401141234 | all | I decided not to skip coffee now after seeing The Blue Mitten's price increase. | CONTRADICTS_NOTES | The evidence states 'skip coffee for the rest of the day? maybe later but definitely not now' which contradicts the answer claiming 'decided not to skip coffee now'. |
| q_0005 | single_hop | Did I schedule a dental checkup after months of delay? | n_001 | N_202401072210, note_202401071823, n_001, N_202401190314, note_202401151437 | all | Yes, I scheduled a dental checkup for next week after months of delay, as noted in the January 7th journal entry where I finally booked it despite Ben's reminders about skipping it for months. | OTHER_NOTES | The answer claims the journal entry from January 7th states 'finally booked it,' but the EVIDENCE shows the January 7th entry says 'skipped again' and 'had it scheduled for months'—the booking happened later on January 15th. |
| q_0007 | multi_hop | When did the user last work on The Art of War without distractions, and why do they feel differently about it compared to previous sessions? | N_202401160537, N_202401171017 | N_202401160537, N_202401220847, note_20240113_001, N_202401171017, N_202401090121 | all | The user last worked on The Art of War without distractions on 2024-01-22. They feel differently because the project is no longer paused (it was paused since 2023), and they experienced a sense of accomplishment without the guilt from Ethan's unpaid debts that hindered progress in previous sessions. | OTHER_NOTES | The answer claims the last session was on 2024-01-22, but the evidence shows the last session was on 2024-01-17 (with 2024-01-22 being in OTHER NOTES). The evidence states the last session was on 2024-01-17, not 2024-01-22. |
| q_0008 | multi_hop | After Ben said 'good job' for cleaning the couch, what happened to the coffee stain and Mochi's fur that was previously bigger and covered with an old blanket? | N_202401121632, n_202401180049 | E_202401141234, n_202401180049, N_202401092024, N_202401060721, N_202401121714 | some | After Ben said 'good job' on January 14, the coffee stain and Mochi's fur were cleaned away—specifically, the stain from Ben's coffee spill and the fur were removed. The journal notes state the couch was "finally cleaned" that day with both issues gone. | OTHER_NOTES | The answer claims the stain was from 'Ben's coffee spill' and references January 14, but the evidence shows the cleaning happened on January 18, not January 14, and the stain was from a spill mentioned on January 12, not Ben's spill. |
| q_0011 | multi_hop | What is the current state of the couch after Luna and Mochi's recent visits? | N_202401050410, N_202401060721 | N_202401060957, N_202401151725, N_202401121714, N_202401060721, N_202401050410 | all | The couch is clean for once after Luna and Mochi's recent visit, as the dog stayed on the rug this time. | OTHER_NOTES | The answer claims the couch is clean for once, but the evidence shows the couch is covered in fur from Mochi's visits, contradicting the claim. |
| q_0013 | multi_hop | Why does the couch stain look worse now, and why did I avoid going to the dentist despite Ben's reminders? | N_202401121632, N_202401200520 | N_202401200711, E_202401141234, n_202401180049, N_202401200520, N_202401190556 | some | The couch stain looks worse because Mochi's fur is still on it. I didn't avoid going to the dentist—I went on January 20th after Ben's reminders, though I felt like I should have come sooner. | OTHER_NOTES | The answer claims the stain is worse due to Mochi's fur, but the evidence states the stain is bigger and covered with an old blanket, not fur; the other notes mention fur but the evidence does not. |
| q_0016 | temporal_reasoning | Did St. Mary's Church still offer free parking on Sundays after the incident where Mochi shed fur all over the couch? | N_202401050410, N_202401060241 | N_202401060241, N_202401171458, N_202401180543, N_202401071306, N_202401151906 | some | Yes, St. Mary's Church still offered free parking on Sundays after the incident, as the journal entries from January 7, 15, 17, and 18 all describe free parking being available "like always" or "still a thing." | OTHER_NOTES | The answer cites journal entries from January 7, 15, 17, and 18, which are part of the OTHER NOTES, not the EVIDENCE. |
| q_0045 | unanswerable | What specific issue is causing the Art of War project to remain unresolved despite previous attempts? | - | N_202401220847, N_202401160537, N_202401190809, N_202401080039, N_202401170848 | - | Ethan's unpaid payment is the specific issue causing the Art of War project to remain unresolved, as noted in the journal where it states "Ethan didn't pay" and "Ethan's unpaid stuff" repeatedly. | FAILED_REFUSAL |  |
