# Contributing to Krinea

Thank you for helping. Bug reports, fixes, translations, documentation and new features
are all welcome. Questions and ideas go to GitHub Discussions, bugs to the issue tracker
of <https://github.com/aymardino/krinea>.

Security vulnerabilities never go in a public issue, discussion or pull request: see
[`SECURITY.md`](SECURITY.md).

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Set up

You need Python 3.11 or later, Node.js 22 (20.9 at least) and pnpm (`corepack enable`).

```bash
git clone https://github.com/aymardino/krinea && cd krinea
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt                               # Streamlit edition, pytest, the engine
pip install -e "packages/core[excel,llm]" -e "apps/api[dev]"      # engine (editable) and API
(cd apps/web && pnpm install)
```

Run the product: `cd apps/api && uvicorn krinea_api.main:app --reload` (API on
<http://localhost:8000>) and, in a second terminal, `cd apps/web && pnpm dev` (web app
on <http://localhost:3000>). No configuration is needed in development: SQLite, a local
PDF folder, e-mails printed to the console, jobs run inline. The settings are listed in
[`apps/api/README.md`](apps/api/README.md). The Streamlit edition runs with
`streamlit run review_app.py` from the repository root.

## Test

Run the three checks before you open a pull request:

```bash
python -m pytest -q                          # repository root: engine, root shims, Streamlit edition
(cd apps/api && python -m pytest -q)         # API
(cd apps/web && pnpm build)                  # type-checks and builds the web app
```

Continuous integration (`.github/workflows/ci.yml`) runs the same three on every push and
pull request. A pull request is merged only when CI passes.

## Pull requests

- Keep each pull request focused on one change, and say what it changes and why.
- Add or update tests when behaviour changes.
- Code, comments, commit messages and documentation are in English (decision D-04).
- Every interface string exists in English and French: `apps/web/messages/en.json` and
  `fr.json` for the web app, `i18n.py` for the Streamlit edition (a test checks it). The
  public pages under `apps/web/content/en` and `apps/web/content/fr` stay in sync.
- Product or technical choices worth remembering go to `docs/decisions.md`, with the
  reason and how to undo them.
- `packages/core` stays free of web frameworks and databases: plain functions that other
  tools can embed.

## Licences per directory

| Directory | Licence |
|---|---|
| `packages/core/` (the `krinea_core` engine) | MIT (`packages/core/LICENSE`) |
| Everything else: `apps/api/`, `apps/web/`, the Streamlit edition at the root, `docs/` | AGPL-3.0-only (`LICENSE`) |

By contributing, you agree that your contribution is released under the licence of the
directory it changes. The PRISMA 2020 templates are reproduced under CC BY 4.0 from
prisma-statement.org.

## Sign off your commits (DCO)

Krinea uses the [Developer Certificate of Origin 1.1](https://developercertificate.org)
instead of a contributor licence agreement. By signing off a commit you certify that you
wrote the contribution or otherwise have the right to submit it under the project's open
source licence, and that you understand the contribution and your sign-off are public
and kept in the project's history.

Sign off every commit with `-s`:

```bash
git commit -s -m "Explain what the commit changes"
```

Git adds a `Signed-off-by: Your Name <you@example.org>` line from your `user.name` and
`user.email`; use your real name. To sign off commits you already made on your branch:
`git rebase --signoff main`, then force-push the branch.
