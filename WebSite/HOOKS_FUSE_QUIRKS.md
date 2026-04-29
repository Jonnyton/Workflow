# FUSE Mount Quirks — Notes for future sessions

The Cowork sandbox mounts the Windows project folder over FUSE. Two real
gotchas surface here, and we have a hook to catch one of them.

## 1. Write tool silently truncates overwrites (BLOCKING bug)

**Symptom:** `Write` reports success on overwriting an existing file, but
the on-disk size is much smaller than what was sent. New files write
correctly; overwrites fail silently.

**Workaround:** when overwriting an existing file, use `bash` heredoc:

```bash
cat > /full/path/to/file << 'EOF'
... content ...
EOF
```

Quote the heredoc delimiter (`'EOF'`) so shell variables / backticks aren't
expanded.

**Detection:** the
[`fuse_write_truncation_guard.py`](../.claude/hooks/fuse_write_truncation_guard.py)
PostToolUse hook checks `os.path.getsize(file_path)` against
`len(content.encode('utf-8'))` after every `Write` call. If they differ by
more than 32 bytes, it surfaces a loud stderr message and exit code 2,
prompting the model to rewrite via heredoc.

Hook is wired into `.claude/settings.json` under
`hooks.PostToolUse[matcher="Write"]`.

## 2. `node_modules/.bin/` symlinks don't materialize

**Symptom:** `npm install` succeeds and packages land in `node_modules/`,
but the `.bin/` directory with executable shims is missing. Running
`npm run dev` errors with "vite: not found".

**Workaround:** invoke binaries via `npx` or directly via `node
node_modules/<pkg>/bin/<name>.js`. Better: just run the build on the
Windows host (where the FUSE quirk doesn't exist).

This is why we don't try to verify SvelteKit builds inside the sandbox.
