# photoswipe

One-off Clever Cleaner-style swipe page for the Mac Photos library. Local only, no repo.

- `uv run phone.py`: with the iPhone plugged in, saves its camera roll list to data/phone.json (run once, before the next phone clear)
- `uv run app.py`: serves http://localhost:8765, open in Safari
- Decks: Gone from iPhone, Videos (biggest first), Everything else (oldest first)
- ← delete, → keep, Z undo, or drag the card. Progress lives in data/progress.json
- "Send to album" puts rejects in the Photos album "To delete". Empty it yourself: open album, ⌘A, ⌘⌫

Where it is headed: nowhere. Delete the folder when the library is clean.
