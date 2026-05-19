# Theory Loop

Use this loop to turn ideas into theories.

The goal is to make claims stronger by attacking them with evidence, then keeping only the revision that survives.

## Theory

- Compress many cases into fewer concepts.
- Force a decision, prediction, or boundary.
- Can break under clear evidence.

## Evidence

- Strong claims need strong evidence.
- Evidence must be observable, reproducible, or cited.
- Mark hypotheses clearly; do not use them as evidence.
- Prefer cases that would change the theory if true.
- Use the best available evidence; do not stall the loop for exhaustive search.

## Loop

1. Claim one thing clearly.
   - It must explain more than itself.
   - It must imply a decision, prediction, or boundary.

2. Break it with evidence.
   - Use observations, experiments, cases, data, or sources.
   - Prefer the strongest objection, not the easiest one.

3. Fix one thing, and keep why.
   - Prefer fixing scope before terms, terms before definitions, definitions before the core claim.
   - Record what broke and why the revision is stronger.

4. Pick next, then re-read this.
   - Choose the next weakest point.
   - Read this file again before the next cycle.

## Roles

- Use isolated agents for roles when available.
- At minimum, Critic must run in an isolated context.
- Theorist handles step 1.
- Critic handles step 2.
- Synthesizer handles step 3.
- Archivist handles step 4 and saves the cycle.

## Output

Save each cycle in `docs/research/theory_YYYYMMDD_HHMMSS.md`.

When a revision changes the current theory, update `docs/research/THEORY_<name>.md`.

Each cycle must include:

- Claim
- Evidence
- Objection
- Revision
- Why it is stronger
- Next question

Do not force formulas or equation-like notation.

Use a short name, list, or structure only when it makes the claim clearer or more testable.

## Done

A cycle is done when it has one claim, evidence-based objection, stronger revision, and next question.

## Continue

After a cycle, use `Next question` to start the next cycle automatically.

Keep going until stable enough, restart is needed, evidence is blocked, or a user-set cycle limit is reached.

## Stable Enough

Stop when new evidence changes only examples or wording, not the claim's decisions, predictions, or boundaries.

## Restart

If revision keeps adding exceptions, replace the claim.
