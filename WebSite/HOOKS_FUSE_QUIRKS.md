# FUSE Mount Quirks — Notes for future sessions

The Cowork sandbox mounts the Windows project folder over FUSE. The Edit
and Write tools both silently truncate file overwrites on this mount.
Only **bash heredoc** is reliable.

## STANDING RULE — both Edit and Write can truncate

Every truncation incident has now triggered a stronger preventive
measure. The current rule is:

**For any file that already exists in `WebSite/site/src/**` (or anywhere
under the FUSE mount), do not use the `Edit` or `Write` tools. Use bash
heredoc.**

```bash
cat > "/full/path/to/file" << 'FILE_EOF'
... full file content ...
FILE_EOF
```

Quote the delimiter (`'FILE_EOF'`) so shell variable / backtick
expansion stays off.

New files (file did not previously exist) are usually fine via Write.
But once a file has been written, treat all subsequent overwrites or
edits as heredoc-only.

## Hook coverage

`.claude/hooks/fuse_write_truncation_guard.py` runs in **PostToolUse**
for both `Write` and `Edit`:

* **Write**: compares on-disk size to the size of the content sent. If
  they differ by more than 32 bytes, exits 2 with a clear message
  prompting a heredoc retry.
* **Edit**: reads the file and verifies that the supplied `new_string`
  is present as a contiguous substring. If only a prefix is present
  (the FUSE truncation chops the tail), reports how many characters
  survived and exits 2.

Wired into `.claude/settings.json` under
`hooks.PostToolUse[matcher="Write"]` and `[matcher="Edit"]`.

The hook only fires inside Claude Code (which honors `.claude/settings.json`).
**Cowork agents do not get the hook** — they have to follow the standing
rule manually. The rule is repeated in:

- `Workflow/CLAUDE.md` (under "FUSE truncation rule")
- `WebSite/HOOKS_FUSE_QUIRKS.md` (this file)
- agent memory: `feedback_fuse_truncation.md`

## Why "auto-iterate" matters

User directive (2026-04-29): "truncation should never happen in the
first place, each time it does we auto reiterate to it never happening."

So every recurrence is a signal that the prevention layer is too weak
and should be hardened immediately:

| Incident                         | Iteration                           |
|----------------------------------|-------------------------------------|
| First mcp-snapshot.json truncate | atomic temp+rename in snapshot script |
| package.json + ChatDemo truncate | initial PostToolUse Write hook        |
| graph/+page.svelte Edit truncate | hook now also matches Edit + Edit-mode substring check + standing rule documented in CLAUDE.md |

If it happens again the next iteration is: PreToolUse hook that **rejects**
Edit/Write on any path under the FUSE mount, forcing heredoc as the only
path.

## Other quirk: `node_modules/.bin/` symlinks don't materialize

`npm install` succeeds but `node_modules/.bin/` is missing executable
shims, so `npm run dev` errors with "vite: not found".

**Workaround:** invoke binaries via `npx` or directly via
`node node_modules/<pkg>/bin/<name>.js`. Better: run the build on the
Windows host (where the FUSE quirk doesn't exist) — that's what the
GitHub Actions deploy job does anyway.
