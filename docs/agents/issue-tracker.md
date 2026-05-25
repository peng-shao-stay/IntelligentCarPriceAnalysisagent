# Issue Tracker

**Type**: Local markdown

Issues are stored as markdown files under `.scratch/<feature-name>/` in this repository.

## Workflow

1. Create a directory under `.scratch/` named after the feature or bug (kebab-case).
2. Write an `issue.md` file inside that directory describing the problem or task.
3. Use YAML frontmatter for metadata:

```yaml
---
title: Brief issue title
status: open
labels:
  - needs-triage
created: 2026-05-20
assigned: none
---
```

## Commands

- `to-issues` writes issues to `.scratch/<feature>/issue.md`
- `triage` reads and updates issue labels via frontmatter
- Issues don't use GitHub/GitLab APIs — all operations are file-based
