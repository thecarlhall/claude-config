#!/usr/bin/env python3
"""
LevelUp email TTS pipeline.

Reads a JSON array of email objects from a file path passed as the first argument.

Each object must have:
  subject    (str)  email subject line
  date_str   (str)  ISO date, e.g. "2026-03-18"
  body_plain (str)  plain-text body (may be empty string)
  body_html  (str)  HTML body (may be empty string)

Run inside the kokoro-pdf-tts uv environment:
    cd ~/devel/kokoro-pdf-tts && \
        uv run python ~/.claude/skills/levelup-email-tts/scripts/run_tts.py /tmp/levelup_emails.json
"""
import sys, os, re, json, tempfile, subprocess
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, ID3NoHeaderError

PDF_TTS_DIR = os.path.expanduser("~/devel/kokoro-pdf-tts")
CLEANER_DIR = os.path.dirname(os.path.abspath(__file__))
GOOGLE_AUTH = os.path.expanduser("~/.config/home-automation")
AUDIO_DIR   = os.path.join(PDF_TTS_DIR, "audio", "levelup")

sys.path.insert(0, PDF_TTS_DIR)
sys.path.insert(0, CLEANER_DIR)
sys.path.insert(0, GOOGLE_AUTH)

from pdf_tts     import extract_text_from_pdf, text_to_audio
from clean_email import clean_body, html_to_pdf

os.makedirs(AUDIO_DIR, exist_ok=True)

# Lazy Gmail client for trashing processed messages.
_GMAIL_CLIENT = None


def _gmail():
    global _GMAIL_CLIENT
    if _GMAIL_CLIENT is None:
        from google_auth import get_gmail
        _GMAIL_CLIENT = get_gmail()
    return _GMAIL_CLIENT


def trash_message(msg_id: str) -> bool:
    """Move a Gmail message to Trash. Returns True on success."""
    try:
        _gmail().users().messages().trash(userId="me", id=msg_id).execute()
        print(f"  Moved email {msg_id} to Trash")
        return True
    except Exception as e:
        print(f"  Trash failed for {msg_id}: {e}")
        return False

# Voice assignments per newsletter series.
# Matched against the start of the subject line (case-insensitive).
VOICE_MAP = [
    ("tbl:",            "af_heart"),     # The Better Leader — female
]
DEFAULT_VOICE = "af_bella"              # fallback for unrecognised series

_PIPELINE = None
_BLEND_CACHE: dict = {}


def _get_pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        from kokoro import KPipeline
        _PIPELINE = KPipeline(lang_code="a")
    return _PIPELINE


def _get_blend(label, specs):
    if label not in _BLEND_CACHE:
        pipe = _get_pipeline()
        blend = None
        for weight, name in specs:
            t = pipe.load_voice(name)
            blend = weight * t if blend is None else blend + weight * t
        _BLEND_CACHE[label] = blend
    return _BLEND_CACHE[label]


# Each entry: (sender_keywords, subject_prefixes, label, weighted_voices)
# am_adam dropped from Grant blend — firm/intense quality reads as 'mad'
_SENDER_BLENDS = [
    (
        ["adam grant"], [],
        "am_michael+bm_lewis+af_heart+af_sky(35/20/25/20) [Grant]",
        [(0.35, "am_michael"), (0.20, "bm_lewis"), (0.25, "af_heart"), (0.20, "af_sky")],
    ),
    # warm, conversational; 7-voice blend male/female 65/35, US/UK 75/25
    (
        ["robert glazer"], ["friday forward"],
        "am_michael+bm_george+bm_lewis+am_adam+af_bella+af_heart+af_sarah(30/15/10/10/15/10/10) [Glazer]",
        [(0.30, "am_michael"), (0.15, "bm_george"), (0.10, "bm_lewis"),
         (0.10, "am_adam"), (0.15, "af_bella"), (0.10, "af_heart"), (0.10, "af_sarah")],
    ),
    # am_adam's firmness fits Ethan's persona — kept as primary per listen test
    (
        ["ethan evans", "level up newsletter"], [],
        "am_adam+am_michael+af_nicole(65/25/10) [Evans]",
        [(0.65, "am_adam"), (0.25, "am_michael"), (0.10, "af_nicole")],
    ),
    (
        ["scott alexander", "astralcodexten"], [],
        "bm_lewis+am_michael+af_nicole+am_adam(40/35/15/10) [Alexander]",
        [(0.40, "bm_lewis"), (0.35, "am_michael"), (0.15, "af_nicole"), (0.10, "am_adam")],
    ),
    (
        ["melinda wenner moyer", "melindawmoyer"], [],
        "af_nicole+af_heart(60/40) [Moyer]",
        [(0.6, "af_nicole"), (0.4, "af_heart")],
    ),
]


def pick_voice(subject: str, sender: str = "") -> tuple:
    """Returns (voice, label); voice is a tensor or a string voice name."""
    s = subject.lower()
    for prefix, voice in VOICE_MAP:
        if s.startswith(prefix):
            return voice, voice
    sender_l = sender.lower()
    for sender_kws, subject_prefixes, label, specs in _SENDER_BLENDS:
        if any(kw in sender_l for kw in sender_kws) or any(s.startswith(p) for p in subject_prefixes):
            return _get_blend(label, specs), label
    return DEFAULT_VOICE, DEFAULT_VOICE


def slugify(s):
    s = re.sub(r'[^\w\s-]', '', s.lower())
    return re.sub(r'[\s_-]+', '-', s).strip('-')[:60]


def tag_mp3(path, subject, date_str, sender=""):
    """Write ID3 tags to the MP3 file."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags["TIT2"] = TIT2(encoding=3, text=subject)
    tags["TALB"] = TALB(encoding=3, text="LevelUp")
    tags["TCON"] = TCON(encoding=3, text="Podcast")
    tags["TDRC"] = TDRC(encoding=3, text=date_str)
    if sender:
        tags["TPE1"] = TPE1(encoding=3, text=sender)
    tags.save(path, v2_version=4)


SCP_DEST = "carl@nuc:containers/audiobookshelf/podcasts/LevelUp/"


def upload_mp3(path) -> bool:
    """Upload MP3 to audiobookshelf via SCP. Returns True on success."""
    print(f"  Uploading to {SCP_DEST}...")
    result = subprocess.run(["scp", path, SCP_DEST], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Uploaded OK")
        return True
    print(f"  Upload failed: {result.stderr.strip()}")
    return False


def process_email(subject, date_str, body_plain, body_html, sender="", voice=None, msg_id=None):
    slug     = f"{date_str}_{slugify(subject)}"
    out_path = os.path.join(AUDIO_DIR, f"{slug}.mp3")

    if os.path.exists(out_path):
        print(f"  Already exists, skipping: {out_path}")
        # Re-trash in case a previous run uploaded but failed to trash.
        if msg_id:
            trash_message(msg_id)
        return out_path

    print(f"\nConverting: {subject}")

    # Route A: HTML -> PDF -> extract_text_from_pdf
    if body_html and len(body_html.strip()) >= 200:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_pdf = f.name
        try:
            html_to_pdf(body_html, tmp_pdf, subject=subject)
            text = extract_text_from_pdf(tmp_pdf)
        finally:
            try:
                os.unlink(tmp_pdf)
            except OSError:
                pass

    # Route B: plain-text fallback
    else:
        text = clean_body(plain=body_plain or "", html=body_html or "")

    if len(text) < 100:
        print(f"  Skipping '{subject}' -- cleaned body too short ({len(text)} chars)")
        return None

    if voice is not None:
        chosen_voice, voice_label = voice, "custom"
    else:
        chosen_voice, voice_label = pick_voice(subject, sender=sender)
    print(f"  Text length: {len(text)} chars  |  voice: {voice_label}")
    text_to_audio(text, voice=chosen_voice, output_file=out_path)
    tag_mp3(out_path, subject=subject, date_str=date_str, sender=sender)
    print(f"  Saved: {out_path}")
    if upload_mp3(out_path) and msg_id:
        trash_message(msg_id)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: run_tts.py <emails.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        emails = json.load(f)
    saved = [process_email(**e) for e in emails]
    print("\nDone:", [p for p in saved if p])
