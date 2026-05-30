---
name: levelup-email-tts
description: >
  Fetch emails from the Gmail "levelup" label and convert each one to an MP3
  audio file using Kokoro TTS (pdf_tts.py). Checks the audiobookshelf server
  for the latest existing audio file and only fetches emails newer than that,
  so no emails are missed even if older than 7 days. Use this skill whenever
  the user asks to convert their levelup emails to audio, listen to their
  levelup newsletter, or process their weekly levelup emails as speech.
  Also trigger when the user says something like "do the levelup emails",
  "convert my newsletters to audio", or "run the email TTS pipeline".
---

# LevelUp Email → Audio Skill

Convert Gmail "levelup" label emails into MP3 files using Kokoro TTS, starting
from the date of the latest already-converted file on the audiobookshelf server.

## Overview

1. SSH to `carl@nuc` to find the latest existing audio file and determine the cutoff date
2. Search Gmail for messages with the `levelup` label newer than that date
3. For each message: read the full body (HTML preferred), strip boilerplate, convert to audio
4. Save MP3 files to `~/devel/kokoro-pdf-tts/audio/levelup`

---

## Step 1 — Determine cutoff date from server

Run this command to list existing files on the audiobookshelf server:

```bash
ssh carl@nuc -t ls containers/audiobookshelf/podcasts/LevelUp
```

Files are named `YYYY-MM-DD_<slug>.mp3`. Parse the filenames to find the latest
date. Use that date as the Gmail search cutoff (`after:YYYY/MM/DD`).

If the directory is empty or the command returns no files, use `after:2020/01/01`
to fetch all available emails rather than assuming a recent window.

**Example:** if the latest file is `2026-03-14_friday-forward.mp3`, search Gmail
for `label:levelup after:2026/03/14`.

---

## Step 2 — Find emails

Use the `gmail_search_messages` MCP tool with the cutoff date from Step 1:

```
label:levelup after:YYYY/MM/DD
```

or the fallback:

```
label:levelup newer_than:7d
```

If no messages are found, tell the user and stop.

---

## Step 3 — Read each message

For each result, call `gmail_read_message` with the message ID.

**Important:** The Gmail MCP returns a flat `body` string (plain text only) — it does **not**
expose MIME multipart structure. HTML is not available directly from the MCP response.

Extract plain text and sender from the response like this:

```python
body_plain = msg.get("body", "")
body_html  = ""   # MCP does not provide HTML parts
sender     = msg.get("headers", {}).get("From", "")
# Strip angle-bracket address: "Robert Glazer <foo@bar.com>" → "Robert Glazer"
import re
sender = re.sub(r'\s*<[^>]+>', '', sender).strip()
```

**Note on HTML fetching:** The plain text body from Gmail MCP is already complete
and works well for TTS. The `WebFetch` tool returns a summarized markdown rendering,
not raw HTML — so fetching the "view in browser" Substack URL does **not** provide
usable HTML. Skip that step and proceed directly with `body_plain`.

If no HTML is available, Route B (plain-text fallback) works well.

---

## Step 4 — Clean and strip boilerplate

The bundled `clean_email.py` script handles this. It **always strips** newsletter
header/footer boilerplate — unsubscribe links, manage-preferences notices,
copyright blocks, postal addresses, "you received this because…" footers — from
the output so they are never heard in the audio.

The script lives at:
```
~/.claude/skills/levelup-email-tts/scripts/clean_email.py
```

The script supports two output routes. Use whichever fits the pipeline:

### Route A — Styled PDF (recommended)

Converts HTML to a PDF where heading font sizes are calibrated to the role
thresholds in `pdf_tts.extract_text_from_pdf()`:

| Tag   | Font size | Role detected |
|-------|-----------|---------------|
| h1    | 24 pt     | title         |
| h2    | 18 pt     | section       |
| h3/h4 | 14 pt     | deck          |
| body  | 12 pt     | body          |

The PDF is then fed into `extract_text_from_pdf()`, which does smart paragraph
reconstruction (joining wrapped lines, handling mid-sentence breaks) before
passing text to `text_to_audio()`.

```bash
python ~/.claude/skills/levelup-email-tts/scripts/clean_email.py \
  --input email.html \
  --pdf /tmp/email_clean.pdf \
  --subject "Newsletter Subject Here"
```

Then in Python:
```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/devel/kokoro-pdf-tts"))
from pdf_tts import extract_text_from_pdf, text_to_audio

text = extract_text_from_pdf("/tmp/email_clean.pdf")
text_to_audio(text, output_file=out_path)
```

### Route B — Structured plain text (fallback)

Parses HTML into heading/paragraph/list nodes, applies boilerplate stripping,
and emits plain text with blank-line spacing around headings. Headings surrounded
by blank lines become natural speech pauses via Kokoro's `split_pattern=r'\n+'`.

```bash
python ~/.claude/skills/levelup-email-tts/scripts/clean_email.py \
  --input email.html \
  --output /tmp/email_clean.txt
```

Or inline in Python:
```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/levelup-email-tts/scripts"))
from clean_email import clean_body, html_to_pdf

# HTML-first; falls back to plain if HTML unavailable
text = clean_body(plain=plain_text, html=html_text)
text_to_audio(text, output_file=out_path)
```

---

## Step 5 — Run the pipeline

The orchestration logic lives in a permanent script:
```
~/.claude/skills/levelup-email-tts/scripts/run_tts.py
```

It reads a JSON array from a file path passed as the first argument. Each object must have:
- `subject` — email subject line
- `date_str` — ISO date string, e.g. `"2026-03-18"`
- `body_plain` — plain-text body (may be empty string)
- `body_html` — HTML body (may be empty string)
- `sender` — (optional) sender name, used as ID3 artist tag
- `msg_id` — (optional but **required for autonomous runs**) Gmail message ID. If present, the message is moved to Gmail **Trash** after a successful upload, so the inbox stays clean on the next run. Omit to disable per-email.

Write the email data to `/tmp/levelup_emails.json`, then **run in the background** using the
`run_in_background: true` Bash parameter so the user isn't blocked:

```bash
cd ~/devel/kokoro-pdf-tts && \
  uv run python ~/.claude/skills/levelup-email-tts/scripts/run_tts.py /tmp/levelup_emails.json
```

Example data file (`/tmp/levelup_emails.json`):
```json
[
  {
    "subject": "Friday Forward - Bad Choices (#527)",
    "date_str": "2026-03-13",
    "body_plain": "...",
    "body_html": "",
    "sender": "Robert Glazer",
    "msg_id": "18f1c0a3b7d2e9f4"
  }
]
```

The `msg_id` field is the Gmail message ID returned by `gmail_search_messages` /
`gmail_read_message` (the top-level `id` of each message). Pass it through so
`run_tts.py` can trash the message after upload.

This approach avoids shell-escaping issues with email bodies that contain special characters, backslashes, or multi-line content.

The script automatically selects Route A (HTML→PDF) when `body_html` is available,
otherwise falls back to Route B (plain text). It skips emails whose MP3 already exists.

### Step 5b — Monitor progress

Immediately after starting the background Bash task, launch a Monitor on the output file path
returned in the task result. The output path is in the Bash tool result
(format: `/tmp/claude-1000/.../<task_id>.output`).

```
Monitor command:
  tail -f <output_path> | grep --line-buffered -E "Done:|Already exists|Uploaded OK|Moved email|Trash failed|Traceback|Error|skipping"

description: "LevelUp TTS — completed file notifications"
persistent: false
timeout_ms: 3600000
```

Each time a Monitor event arrives, send the user a one-line progress update:
- **Done** line → "✓ _filename_ (_duration_)"
- **Already exists / skipping** line → "– _filename_ (already exists)"
- **Moved email** line → "🗑 email trashed (_msg_id_)"
- **Trash failed** line → warn the user; the MP3 was uploaded but the email remains in inbox
- **Error / Traceback** line → alert the user immediately

When the background Bash task completes (you receive a task notification), send a final summary.

---

## Output

After all conversions are complete, report to the user:
- Number of emails processed
- File paths for each MP3 created
- Upload status for each file (`carl@nuc:containers/audiobookshelf/podcasts/LevelUp/`)
- Any skipped emails and the reason (already exists, body too short, etc.)

---

## Notes

- Audio files are named `YYYY-MM-DD_<slugified-subject>.mp3` so they sort
  chronologically.
- If an MP3 already exists for a given slug it is skipped — the pipeline is
  idempotent and safe to re-run.
- Voices are assigned per newsletter series. Subject prefix matched first, then sender substring:
| Match                                                          | Voice                                                  | Character                                                |
|----------------------------------------------------------------|--------------------------------------------------------|----------------------------------------------------------|
| Subject starts with `TBL:`                                     | `af_heart`                                             | female (US) — The Better Leader                          |
| Sender contains `adam grant`                                   | `am_michael` 35% + `bm_lewis` 20% + `af_heart` 25% + `af_sky` 20% | dynamic, animated, higher-pitched male — Adam Grant's "Granted" |
| Sender contains `robert glazer` *or* subject starts with `Friday Forward` | `am_michael` 30% + `bm_george` 15% + `bm_lewis` 10% + `am_adam` 10% + `af_bella` 15% + `af_heart` 10% + `af_sarah` 10% | 7-voice layered podcast-host blend — Robert Glazer's "Friday Forward" |
| Sender contains `ethan evans` *or* `level up newsletter`       | `am_adam` 65% + `am_michael` 25% + `af_nicole` 10%     | firm/articulate US male w/ warmth lift — Ethan Evans's "Level Up Newsletter" |
| Sender contains `scott alexander` *or* `astralcodexten`        | `bm_lewis` 40% + `am_michael` 35% + `af_nicole` 15% + `am_adam` 10% | light, thoughtful UK-leaning male + softness — Scott Alexander's "Astral Codex Ten" |
| Sender contains `melinda wenner moyer` *or* `melindawmoyer`    | `af_nicole` 60% + `af_heart` 40%                       | warm conversational US female — Melinda Wenner Moyer's "Now What" |
| *(other/unknown)*                                              | `af_bella`                                             | female fallback                                          |
  The `voice` field in the JSON input overrides the automatic mapping.
  Available voices: `af_heart`, `af_bella`, `af_nicole`, `af_sarah`, `af_sky`,
  `am_adam`, `am_michael`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`.
- The `audio/levelup/` output directory is created automatically if absent.
- Each MP3 is tagged with ID3 metadata: `TIT2` (title=subject), `TPE1` (artist=sender),
  `TALB` (album="LevelUp"), `TDRC` (date=full ISO date e.g. `2026-03-13`), `TCON` (genre="Podcast").
  `mutagen` must be installed in the kokoro-pdf-tts uv environment (`uv add mutagen`).
