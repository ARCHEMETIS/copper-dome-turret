# Copper Dome Turret

## Agent skills

### Issue tracker

Issues live as GitHub issues on `ARCHEMETIS/copper-dome-turret` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Codex orchestration

Claude is the lead agent for this repository. When a task benefits from delegation,
Claude may assign a concrete, self-contained subtask to Codex with:

```powershell
codex exec --full-auto "<task prompt>"
```

When delegating to Codex:

1. State the objective, relevant files, constraints, and acceptance checks in the prompt.
2. Keep Claude responsible for planning, scope decisions, and the final answer to the user.
3. Inspect Codex's diff and run appropriate tests before accepting its work.
4. Do not delegate destructive operations, secrets handling, publishing, deployment, or
   other externally consequential actions without explicit user approval.
5. Preserve unrelated working-tree changes and tell Codex not to overwrite user work.
6. If Codex reports ambiguity or a blocker, resolve it as lead agent and issue a narrower
   follow-up task when useful.

Codex is a subprocess collaborator, not an independent authority. Its output is input for
Claude to review; Claude remains accountable for the completed result.
