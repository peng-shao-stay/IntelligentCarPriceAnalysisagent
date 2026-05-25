# Domain Docs

**Layout**: Multi-context

This project has two separate domains, each with its own `CONTEXT.md` and `docs/adr/`:

| Context | Root | CONTEXT.md | ADR directory |
|---|---|---|---|
| **Backend** | `app/` | `app/CONTEXT.md` | `app/docs/adr/` |
| **Frontend** | `frontend/` | `frontend/CONTEXT.md` | `frontend/docs/adr/` |

The root `CONTEXT-MAP.md` indexes both contexts. When a skill needs domain docs, it reads the map to find the relevant context.

## Consumer rules

- Skills that read `CONTEXT.md` look at `CONTEXT-MAP.md` first to find which context applies
- For backend work (Python, FastAPI, agent): read `app/CONTEXT.md`
- For frontend work (React, antd): read `frontend/CONTEXT.md`
- For cross-cutting work: read both
- ADR directories are per-context: `app/docs/adr/` and `frontend/docs/adr/`
