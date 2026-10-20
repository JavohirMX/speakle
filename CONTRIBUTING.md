# Contributing

1. Branch from `dev` (or `main` if `dev` does not exist), for example `feature/short-name` or `fix/short-name`.
2. Keep a change focused. One feature or fix per pull request.
3. Run `python manage.py test` and `python manage.py makemigrations --check --dry-run` before pushing. Set `DEBUG=True` first, as the README explains. CI runs the same checks.
4. If you add a model change, include the migration. Check that your migration number does not collide with another open branch.
5. If you add Tailwind classes, rebuild `static/css/tailwind.css` (see README, "Front-end CSS").
6. Keep copy honest: no invented user counts, ratings or features that are not in the code.
7. Update `CHANGELOG.md` (Unreleased section) and any doc your change makes wrong.
8. Open a pull request against `dev`. Describe what changed, how you tested it, and what you could not test. For visible changes, add screenshots at desktop and 390px width.

## Style

- Python: follow the surrounding code. Small functions, no dead code.
- Templates: reuse components from `static/css/design.css`. Icons come from `partials/icons.html`.
- Accessibility: every control needs a visible label or `aria-label`, and must be reachable by keyboard.
- Do not commit secrets, `db.sqlite3`, `media/` or `staticfiles/`.

## Security

Report vulnerabilities privately to the repository owner instead of opening a public issue.
