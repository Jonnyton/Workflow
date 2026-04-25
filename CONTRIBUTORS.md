# Contributors

Canonical mapping of platform actor IDs to GitHub handles for Co-Authored-By
attribution. Opt-in: add your row to credit yourself in commit messages and
pull request bodies when your nodes or branches ship.

## How it works

When a branch or node ships, the chatbot reads `attribution_credit` rows for
the artifact, looks up each `actor_id` here, and emits:

```
Co-Authored-By: Display Name <github-handle@users.noreply.github.com>
```

GitHub automatically links these to contributor profiles and shows them in
the commit graph.

## Adding yourself

Open a PR that adds one row to the table below. Fields:

| Field | Description |
|---|---|
| `actor_id` | Your identity on this platform (the value in `UNIVERSE_SERVER_USER` when you run the daemon, or your chatbot session handle) |
| `github_handle` | Your GitHub username (without `@`) |
| `display_name` | How you want to appear in commit attribution |

## Contributor table

| Actor ID | GitHub Handle | Display Name |
|---|---|---|
| host | Jonnyton | Jonathan Farnsworth |

## Notes

- GitHub noreply format: `<handle>@users.noreply.github.com`
- Chatbot reads this file when crediting contributors in commits and PRs.
- One row per actor. If your actor_id changes, add the new row; keep the old one so historical attribution stays valid.
- OSS contributors who fork and run their own daemon: use your fork's `UNIVERSE_SERVER_USER` value as `actor_id`.
