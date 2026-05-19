# Agent Instructions

Guidelines for coding agents working in this repo. These instructions favor small, verified changes over broad refactors.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment and skip unnecessary ceremony.

## Project Notes

- Backend: FastAPI app in `backend/`, managed with `uv`.
- Frontend: React + Vite app in `frontend/`, managed with Bun workspace scripts.
- Use Docker Compose when a backend database or full-stack environment is required.

## Common Commands

- Install frontend dependencies: `bun install`
- Frontend dev server: `bun run dev`
- Frontend lint/format: `bun run lint` (Biome may write fixes)
- Frontend tests: `bun run test`
- Frontend build: `cd frontend && bun run build`
- Backend setup: `cd backend && uv sync`
- Backend lint/typecheck: `cd backend && bash ./scripts/lint.sh`
- Backend tests: `cd backend && bash ./scripts/test.sh`
- Regenerate frontend API client after backend OpenAPI changes: `bash ./scripts/generate-client.sh`

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If ambiguity affects correctness or scope, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- Avoid speculative error handling; add handling for concrete failure modes.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
