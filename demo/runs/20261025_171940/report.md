# Results — 20261025_171940

### Accuracy (right answers / questions)


| question type | n | full_context<br>qwen3:4b | vector_rag<br>qwen3:4b | summary<br>qwen3:4b | facts<br>qwen3:4b | full_context<br>qwen3:30b | vector_rag<br>qwen3:30b |
|---|---|---|---|---|---|---|---|
| L1 single_fact | 8 | 8/8 | 8/8 | 3/8 | 5/8 | 8/8 | 8/8 |
| L2 current_state | 3 | 2/3 | 3/3 | 2/3 | 2/3 | 3/3 | 3/3 |
| L3 previous_state | 3 | 3/3 | 3/3 | 2/3 | 3/3 | 3/3 | 3/3 |
| L3 two_hop | 6 | 6/6 | 4/6 | 1/6 | 3/6 | 6/6 | 5/6 |
| L4 count | 2 | 2/2 | 1/2 | 0/2 | 2/2 | 2/2 | 1/2 |
| L4 history | 1 | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 | 0/1 |
| L5 unanswerable | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| **all** | 26 | **24/26** | **22/26** | **11/26** | **18/26** | **26/26** | **23/26** |

### Was the answer in what the model was shown?

String check on the context each bot handed the model; for vector_rag, every gold note retrieved (n/a: counts and unanswerables).

| question type | n | full_context<br>qwen3:4b | vector_rag<br>qwen3:4b | summary<br>qwen3:4b | facts<br>qwen3:4b | full_context<br>qwen3:30b | vector_rag<br>qwen3:30b |
|---|---|---|---|---|---|---|---|
| L1 single_fact | 8 | 8/8 | 8/8 | 5/8 | 8/8 | 8/8 | 8/8 |
| L2 current_state | 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| L3 previous_state | 3 | 3/3 | 3/3 | 2/3 | 3/3 | 3/3 | 3/3 |
| L3 two_hop | 6 | 6/6 | 3/6 | 5/6 | 6/6 | 6/6 | 3/6 |
| L4 count | 2 | n/a | n/a | n/a | n/a | n/a | n/a |
| L4 history | 1 | 1/1 | 0/1 | 1/1 | 1/1 | 1/1 | 0/1 |
| L5 unanswerable | 3 | n/a | n/a | n/a | n/a | n/a | n/a |
| **all** | 26 | **21/21** | **17/21** | **16/21** | **21/21** | **21/21** | **17/21** |

### Why answers were wrong (label counts)

| label | meaning | full_context<br>qwen3:4b | vector_rag<br>qwen3:4b | summary<br>qwen3:4b | facts<br>qwen3:4b | full_context<br>qwen3:30b | vector_rag<br>qwen3:30b |
|---|---|---|---|---|---|---|---|
| CORRECT | answered correctly | 21 | 19 | 8 | 15 | 23 | 20 |
| PARTIAL | list question, only some items named | 1 | 0 | 0 | 1 | 0 | 1 |
| WRONG_DISTRACTOR | named a look-alike or an out-of-date value (the trap worked) | 1 | 0 | 0 | 2 | 0 | 0 |
| WRONG_OTHER | wrong in some other way | 0 | 1 | 3 | 0 | 0 | 1 |
| IDK_BUT_IN_MEMORY | said 'I don't know' although the answer WAS in what it was shown (reading failure) | 0 | 0 | 7 | 4 | 0 | 0 |
| IDK_NOT_IN_MEMORY | said 'I don't know' and the answer was NOT in what it was shown (memory/retrieval failure) | 0 | 3 | 5 | 0 | 0 | 1 |
| CORRECT_IDK | unanswerable question, correctly said 'I don't know' | 3 | 3 | 3 | 3 | 3 | 3 |
| HALLUCINATED | unanswerable question, made an answer up | 0 | 0 | 0 | 0 | 0 | 0 |
| RAMBLED | ignored the short-answer format (over 40 words), so no answer to grade | 0 | 0 | 0 | 1 | 0 | 0 |

### Retrieval quality of vector_rag (same for every model)

| question type | precision@K | recall@K | hit@K | all@K | MRR |
|---|---|---|---|---|---|
| single_fact | 0.20 | 1.00 | 1.00 | 1.00 | 0.94 |
| current_state | 0.20 | 1.00 | 1.00 | 1.00 | 0.78 |
| previous_state | 0.40 | 1.00 | 1.00 | 1.00 | 1.00 |
| two_hop | 0.30 | 0.75 | 1.00 | 0.50 | 0.83 |
| count | 0.80 | 0.86 | 1.00 | 0.50 | 1.00 |
| history | 0.20 | 0.33 | 1.00 | 0.00 | 1.00 |
| **all** | 0.30 | 0.89 | 1.00 | 0.78 | 0.91 |

### Every answer

| q | type | expected | full_context<br>qwen3:4b | vector_rag<br>qwen3:4b | summary<br>qwen3:4b | facts<br>qwen3:4b | full_context<br>qwen3:30b | vector_rag<br>qwen3:30b |
|---|---|---|---|---|---|---|---|---|
| Q01 What is my dog's name? | L1 single_fact | Pickle | ✅ Pickle | ✅ Pickle | ❌ I don't know | ✅ Pickle | ✅ Pickle | ✅ Pickle |
| Q02 What is Femke's dog's name? | L1 single_fact | Biscotti | ✅ Biscotti | ✅ Biscotti | ❌ I don't know | ❌ I don't know | ✅ Biscotti | ✅ Biscotti |
| Q03 What is my favourite cafe? | L1 single_fact | Koffie Kantoor | ✅ Koffie Kantoor | ✅ Koffie Kantoor | ❌ I don't know | ❌ I don't know | ✅ Koffie Kantoor | ✅ Koffie Kantoor |
| Q04 What is Tomasz's favourite cafe? | L1 single_fact | Bar Bolle | ✅ Bar Bolle | ✅ Bar Bolle | ❌ I don't know | ✅ Bar Bolle | ✅ Bar Bolle | ✅ Bar Bolle |
| Q05 What is Ines's car? | L1 single_fact | Fiat Panda | ✅ old yellow Fiat Panda | ✅ Fiat Panda | ❌ I don't know | ✅ Fiat Panda | ✅ Fiat Panda | ✅ Fiat Panda |
| Q06 What is Kofi's car? | L1 single_fact | Volvo Amazon | ✅ Volvo Amazon | ✅ Volvo Amazon | ✅ Volvo Amazon | ❌ I don't know | ✅ Volvo Amazon | ✅ Volvo Amazon |
| Q07 What is Femke's favourite band? | L1 single_fact | Golden Earring | ✅ Golden Earring | ✅ Golden Earring | ✅ Golden Earring | ✅ Golden Earring | ✅ Golden Earring | ✅ Golden Earring |
| Q08 What is Kofi's home town? | L1 single_fact | Paramaribo | ✅ Paramaribo | ✅ Paramaribo | ✅ Paramaribo | ✅ Paramaribo | ✅ Paramaribo | ✅ Paramaribo |
| Q09 What is my workplace now? | L2 current_state | Museum Speelklok | ❌ Openbare Bibliotheek | ✅ Museum Speelklok | ❌ shop | ❌ Openbare Bibliotheek | ✅ Museum Speelklok | ✅ Museum Speelklok |
| Q10 What was my workplace before Museum Speelklok? | L3 previous_state | Openbare Bibliotheek | ✅ Openbare Bibliotheek | ✅ Openbare Bibliotheek | ✅ Openbare Bibliotheek | ✅ Openbare Bibliotheek | ✅ Openbare Bibliotheek | ✅ Openbare Bibliotheek |
| Q11 What is my phone now? | L2 current_state | Pixel 8 | ✅ Pixel 8 | ✅ Pixel 8 | ✅ Pixel 8 | ✅ Pixel 8 | ✅ Pixel 8 | ✅ Pixel 8 |
| Q12 What was my phone before Pixel 8? | L3 previous_state | Fairphone 4 | ✅ Fairphone 4 | ✅ Fairphone 4 | ✅ Fairphone 4 | ✅ Fairphone 4 | ✅ Fairphone 4 | ✅ Fairphone 4 |
| Q13 What are my running shoes now? | L2 current_state | Hoka Clifton | ✅ Hoka Clifton | ✅ Hoka Clifton | ✅ Hoka Clifton | ✅ Hoka Clifton | ✅ Hoka Clifton | ✅ Hoka Clifton |
| Q14 What were my running shoes before Hoka Clifton? | L3 previous_state | Asics Novablast | ✅ Asics Novablast | ✅ Asics Novablast | ❌ I don't know | ✅ Asics Novablast | ✅ Asics Novablast | ✅ Asics Novablast |
| Q15 What is my sister's dog's name? | L3 two_hop | Biscotti | ✅ Biscotti | ✅ Biscotti | ❌ I don't know | ❌ Let me carefully review the journal entries to find the name | ✅ Biscotti | ✅ Biscotti |
| Q16 What is my colleague's favourite cafe? | L3 two_hop | Bar Bolle | ✅ Bar Bolle | ✅ Bar Bolle | ❌ I don't know | ✅ Bar Bolle | ✅ Bar Bolle | ✅ Bar Bolle |
| Q17 What is my neighbour's car? | L3 two_hop | Fiat Panda | ✅ old yellow Fiat Panda | ✅ Fiat Panda | ❌ I don't know | ❌ I don't know | ✅ Fiat Panda | ✅ Fiat Panda |
| Q18 What is my roommate's car? | L3 two_hop | Volvo Amazon | ✅ Volvo Amazon | ❌ I don't know | ✅ Volvo Amazon | ❌ Fiat Panda | ✅ Volvo Amazon | ❌ I don't know |
| Q19 What is my sister's favourite band? | L3 two_hop | Golden Earring | ✅ Golden Earring | ✅ Golden Earring | ❌ I don't know | ✅ Golden Earring | ✅ Golden Earring | ✅ Golden Earring |
| Q20 What is my roommate's home town? | L3 two_hop | Paramaribo | ✅ Paramaribo | ❌ I don't know | ❌ I don't know | ✅ Paramaribo | ✅ Paramaribo | ✅ Paramaribo |
| Q21 How many times did I go bouldering this month? | L4 count | 7 | ✅ 7 | ❌ 5 | ❌ 5 | ✅ 7 | ✅ 7 | ❌ 5 |
| Q22 How many times did I go swimming this month? | L4 count | 3 | ✅ 3 | ✅ 3 | ❌ 2 | ✅ 3 | ✅ 3 | ✅ 3 |
| Q23 List every workplace I have had this month, in order. | L4 history | Bakkerij Vos, Openbare Bibliotheek, Museum Speelklok | ❌ Openbare Bibliotheek, Museum Speelklok | ❌ I don't know | ❌ I don't know | ❌ delivery company, Openbare Bibliotheek, Museum Speelklok | ✅ Bakkerij Vos, Openbare Bibliotheek, Museum Speelklok | ❌ Openbare Bibliotheek |
| Q24 What is Tomasz's dog's name? | L5 unanswerable | (I don't know) | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know |
| Q25 What is Ines's favourite cafe? | L5 unanswerable | (I don't know) | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know |
| Q26 What is Femke's car? | L5 unanswerable | (I don't know) | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know | ✅ I don't know |
