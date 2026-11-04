# Agent Guidelines

## Version Control Conventions

### Commit messages

Format:

```
<type>: <short summary>

- <change>
- <change>
```

Types: `feat` (new feature), `fix` (bug fix), `update` (UI/behavior refinement), `refactor`, `docs`, `test`, `chore`.

Rules:
- Subject line: `<type>: <summary>`, concise (~72 chars), no trailing period.
- Leave one blank line after the subject.
- Add a body of one-line bullets, one per change; skip the body for trivial single-change commits.
- Group related changes under the relevant bullet rather than repeating the subject.
- Review `git status` / `git diff` and stage only intended files before committing.

Examples:

```
fix: UI/UX bugs

- Correct signup redirect for new customers
- Stop the FAB from blocking table row actions
- Separate the file chooser button from its filename text
```

```
feat: export analytics

- Reusable export CSV modal (type + date range, All records toggle) on dashboard and transactions
- Unified export_csv endpoint with range filtering
- Remove raw Bookings/Rentals exports and routes
```

### Changelog

`CHANGELOG.md` uses a date-based, Keep a Changelog-style layout:

```markdown
## YYYY-MM-DD — Short title

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Removed
- ...
```

Rules:
- Newest entry first; one section per change set.
- Heading format: `## YYYY-MM-DD — Title` (em dash), with a short descriptive title.
- Category order: `Added` → `Changed` → `Fixed` → `Removed`; omit empty categories.
- Bullets: one line each, sentence case, no trailing period.
- Use backticks for code identifiers, paths, commands, and routes.
- Add/update only before commits (once all changes is finalized) or when explicitly instructed.
- Add/update the entry in the same commit or PR as the user-visible change.
