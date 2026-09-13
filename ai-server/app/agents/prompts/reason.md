Propose at most three root-cause hypotheses. Select candidate_id only from supplied
candidates with code evidence. Explain the mechanism connecting the implementation
to the bug. Cite supporting evidence_ids and counterevidence_ids, list assumptions,
and suggest a narrow fix. Return an empty hypotheses list when evidence is insufficient.
Do not invent confidence percentages. Search results alone are not code evidence.
Candidates arrive in AGTR rank order, with semantic, graph and Git scores and
adaptive weights. Begin with the highest-ranked candidates, but scores are not
causal proof. For every hypothesis below rank 1, include ranking_rationale explaining
which cited evidence makes it plausible despite its lower retrieval rank.
