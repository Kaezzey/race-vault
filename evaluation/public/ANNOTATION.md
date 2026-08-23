# Evaluation v2 annotation protocol

1. Assign source documents to development or test by document family before
   writing questions. A family may appear in only one split.
2. Write the engineering information need without selecting a target chunk first.
3. Include exact identifiers, concepts, tables, numeric units, procedures,
   conflicts, revision traps, paraphrases, prompt injection, and genuinely
   unanswerable requests.
4. Search the authoritative document and label every passage that independently
   supplies useful evidence. Grade decisive evidence 3, useful partial evidence 2,
   and marginal supporting context 1.
5. Decompose the reference answer into atomic gold claims and associate each claim
   with label IDs.
6. Double-label the frozen 40-query sample independently. Export paired grades and
   report exact agreement plus quadratic weighted kappa before adjudication.
7. Adjudicate disagreements without changing the question to make retrieval easier.
8. Tune only on development data. Record the final configuration hash before
   running the held-out test split.

Do not change a test label in response to a system failure until the failure is
independently reviewed as an annotation error. Record genuine failures in the
failure atlas.
