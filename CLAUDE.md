Skills are organized into bucket folders under `skills/`:

- `engineering/` — daily code work
- `productivity/` — daily non-code workflow tools
- `misc/` — kept around but rarely used
- `personal/` — tied to my own setup, not promoted
- `in-progress/` — drafts not yet ready to ship
- `deprecated/` — no longer used

Every skill in `engineering/`, `productivity/`, or `misc/` must have a reference in the top-level `README.md` and an entry in `.claude-plugin/plugin.json`. Skills in `personal/`, `in-progress/`, and `deprecated/` must not appear in either.

Each skill entry in the top-level `README.md` must link the skill name to its `SKILL.md`.


Each bucket folder has a `README.md` that lists every skill in the bucket with a one-line description, with the skill name linked to its `SKILL.md`.

## Agent skills

### Issue tracker

Issues are stored as local markdown files under `.scratch/<feature-name>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Labels use Chinese strings: `待评估`, `等回复`, `AI可处理`, `需人工`, `不做`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context layout. `app/CONTEXT.md` for backend, `frontend/CONTEXT.md` for frontend. See `docs/agents/domain.md`.
