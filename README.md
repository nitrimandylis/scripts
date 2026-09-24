# scripts

Small local tools. Each folder is one tool: a single Python file with its dependencies inline, run with [uv](https://docs.astral.sh/uv/).

```sh
cd <tool> && uv run <file>.py
```

| Tool | What it does |
|---|---|
| [photoswipe](photoswipe) | Swipe through the macOS Photos library in the browser, Clever Cleaner style, and collect rejects in a "To delete" album |

Each tool's `PRODUCT.md` has its usage. Anything a tool writes goes in its `data/` folder, which is never committed.
