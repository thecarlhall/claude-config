---
name: getting-carlibrated
description: >
  Create a podcast episode for Carl covering weather, local news, and industry/tech news.
  Produces a multi-speaker MP3 using Kokoro TTS and uploads it to Audiobookshelf.
  Trigger when the user asks to create, generate, or run the weekly podcast, or says
  "do the podcast", "make today's episode", or "run carlibrated".
---

# Getting Carlibrated Podcast Skill

Produce a ~20-minute podcast episode with three named on-air personas, rendered via
Kokoro TTS and uploaded to Audiobookshelf.

---

## Personas

| Role               | Name      | Voice blend                                    |
|--------------------|-----------|------------------------------------------------|
| Male host (primary)| **Marcus** | `am_michael` 60% + `bm_george` 40%            |
| Female contributor | **Sofia**  | `af_heart` 60% + `bf_emma` 40%                |
| Male contributor   | **Oliver** | `bm_george` 70% + `bm_lewis` 30%              |

Marcus speaks most of the time. Sofia and Oliver each pick **one topic** per episode to
discuss in depth with Marcus. Outside of those deep-dives, contributors deliver one or two
sentences of added colour, then hand back to Marcus.

Target transcript length: **~5,000 words** (roughly 20–22 minutes of audio at normal
speaking pace). Do not pad sections to hit a higher word count.

---

## Step 1 — Determine cutoff date

Check for the most recent episode already on the Audiobookshelf server:

```bash
ssh carl@nuc -t ls containers/audiobookshelf/podcasts/Carlibrated/
```

Files are named `getting-carlibrated-YYYY-MM-DD.mp3`. Use the date in the latest filename as the
cutoff. If the directory is empty, use today's date and produce an episode regardless.

If today's episode already exists, tell the user and stop — the pipeline is idempotent.

---

## Step 2 — Gather content

Collect live content for each section using web search. Spend proportionate effort: weather
and local news are quick; industry/tech news is the bulk of the episode.

### Weather

Marcus hands off to Sofia in one sentence. Sofia delivers a concise 150–200 word summary
covering exactly three things: (1) today's conditions and high, (2) weekend outlook,
(3) the rest of the week pattern. No replies from Marcus or Oliver — weather is a quick
solo segment by Sofia, then Marcus moves on to local news.

Content to gather:
1. **Clarkston, GA** — current conditions and today's forecast; 7-day summary.
2. **Upcoming travel** — check Google Calendar for events in other cities over the next
   14 days; fetch the forecast for each destination.

### Email Digest

Fetch via Gmail MCP. The "since last briefing" window = since last Friday at 8:30 AM ET.

1. **`watches` label** — list each email by sender/subject in one sentence each. Keep it quick: "You got a shipping update from Apple, a price alert from Google Fi, and a newsletter from The Pragmatic Engineer."
2. **Inbox** — summarize any threads that look actionable or noteworthy; skip newsletters/promos already covered in the industry section. If the inbox is quiet, say so in one sentence.

Marcus delivers this solo, conversationally, as if reading off his phone. Target: 100–150 words total. No contributor commentary.

### Local News

Positive / neutral stories only — skip crime, homelessness, or generally negative coverage.

- Tucker, GA: city council updates, commercial/residential developments
- Atlanta metro: notable civic or business highlights

### Industry News

Search across the following sources and topics. Note cross-source trends.

**Topics to cover:**
- AI (models, tools, regulations, research)
  - Track model release cadence across all major labs: OpenAI (GPT series), Anthropic (Claude), Google (Gemini/Gemma), xAI (Grok), DeepSeek — report all notable releases in a given week, not just headline announcements
  - NVIDIA GTC and major conferences: enterprise AI production deployment trends, shift from benchmarks to real-world agentic metrics
  - AI regulations and government policy — flag historic milestones (e.g., first frontier-model legislation)
  - Business metrics: revenue run-rate, major investments, compute partnerships
- Cloud computing (AWS, Azure, GCP)
  - Multicloud interoperability standards and provider positioning
  - Agentic data infrastructure (agent kits, autonomous pipeline builders)
  - Cross-cloud egress cost reduction tools
  - Q1 / quarterly cloud earnings context when relevant
- Databricks — check https://docs.databricks.com/aws/en/release-notes/product/ for recent
  release notes
- Cybersecurity
  - Breaches: exposure scale, affected parties, attacker group (e.g., ShinyHunters), root cause (direct vs. third-party vendor)
  - Critical CVEs: CVSS score, affected product, exploit type, patch urgency — flag drop-everything patches explicitly
  - Practical defender guidance: isolation vs. patch order, vendor risk review practices, automation needed to match attacker timelines
  - Macro trends: attack speed (lateral movement timelines), AI-assisted attacks, third-party vector prevalence
- Startup & VC
  - Agentic AI as investment thesis (autonomy vs. assistance)
  - Deep tech macro shift: why capital is moving from SaaS toward robotics, chips, manufacturing — include the "AI commoditizes software" argument
  - Compute/infrastructure layer as durable investment vs. application layer

**Daily general tech:**
- TLDR, TechCrunch, MIT Technology Review (The Download), Techpresso

**AI & deep tech:**
- The Rundown AI, Superhuman AI, The Batch (DeepLearning.AI)

**Business & strategy:**
- Benedict's Newsletter, Stratechery (Ben Thompson), The Information

**Software engineering:**
- The Pragmatic Engineer, ByteByteGo

**Startup & investment:**
- StrictlyVC, Hacker News, Last Week in AWS, TechCrunch Startups Weekly

---

## Step 3 — Write the transcript

Structure the transcript in section order: Weather → Email Digest → Local News → Industry News → Daily Grounding.

Format each line with a speaker tag:

```
[MARCUS]: Welcome to Getting Carlibrated for Thursday, May 15th. ...
[SOFIA]: Thanks Marcus. On the AI front, I wanted to dig into ...
[MARCUS]: Great point. Let's turn to ...
[JORDAN]: I'll add one thing here — ...
```

Rules:
- Each section opens and closes with Marcus.
- **Weather:** Sofia solo, 150–200 words, no conversation. Marcus hands off, Sofia summarizes, Marcus moves on.
- **Email Digest:** Marcus solo, 100–150 words. `watches` label items listed briefly, then inbox highlights. No contributor lines.
- **Daily Grounding:** Marcus solo, 60–90 words. Close the episode with a brief reflection drawn from Buddhism, Stoicism, or meditation philosophy — a quote, a teaching, or a framing thought. It should feel like a natural pause before the day begins, not a lecture. Pick something relevant to the week's themes if a connection is natural, otherwise choose something timeless. End with a simple sign-off: "That's Getting Carlibrated for [day]. Have a good one."
- Sofia's deep-dive topic must be from the AI or business/strategy categories.
- Oliver's deep-dive topic must be from cloud, engineering, or startup categories.
- Deep-dive exchanges run 300–500 words each; all other contributor lines are ≤ 2 sentences.
- Keep language conversational and unscripted-sounding. No bullet recitation.
- Do not include stage directions of any kind — no `[laughs]`, `[chuckles]`, `[sighs]`, `*laughs*`, etc. Kokoro reads them aloud literally.
- Always write full US state names — "Georgia" not "GA", "Texas" not "TX". Reserve abbreviations for contexts where the abbreviation itself is the subject.
- Spell out ambiguous tech abbreviations in full — "Generally Available" not "GA", "transmit" not "TX". Unambiguous initialisms (AI, API, AWS, GCP, SQL) are fine.
- Do not pad. If a topic is covered, move on.

---

## Step 4 — Render audio

The TTS script must:

1. Parse the transcript by `[SPEAKER]:` tag into segments. Before rendering each segment, run it through a `preprocess(text)` function that applies the following fixes in order:

   **a. Strip stage directions** — remove tokens Kokoro would read aloud literally:
   ```python
   text = re.sub(r'\*[^*]+\*', '', text)           # *laughs*
   text = re.sub(r'\[(?!MARCUS|SOFIA|OLIVER)[^\]]*\]', '', text)  # [laughs], [chuckles]
   ```

   **b. Expand known phonetic acronyms** — replace before any other substitution so the result isn't re-processed:
   ```python
   PRONUNCIATIONS = {
       'CISA': 'sigh-zuh',
       'CISO': 'see-so',
   }
   for abbr, spoken in PRONUNCIATIONS.items():
       text = re.sub(rf'\b{abbr}\b', spoken, text)
   ```

   **c. Expand US state abbreviations to full names** — the transcript writer is instructed to spell states out, so any remaining two-letter state code can be safely expanded. DC is excluded because both of its meanings ("Washington D.C." and "direct current") are already pronounced "dee-see" by Kokoro:
   ```python
   STATE_NAMES = {
       'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California',
       'CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia',
       'HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa',
       'KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland',
       'MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi',
       'MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire',
       'NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina',
       'ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania',
       'RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee',
       'TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington',
       'WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming',
   }
   text = re.sub(r'\b([A-Z]{2})\b', lambda m: STATE_NAMES.get(m.group(1), m.group(1)), text)
   # e.g. "Tucker, GA" → "Tucker, Georgia"
   ```

   **c. Rewrite version numbers** — so "4.1.0" is read "four-one-oh" not "four point one point zero":
   ```python
   _NUM = ['zero','one','two','three','four','five','six','seven','eight','nine']
   def _ver_part(p):
       return 'oh' if p == '0' else (_NUM[int(p)] if p.isdigit() and int(p) < 10 else p)
   def _ver_to_speech(m):
       return '-'.join(_ver_part(p) for p in m.group(0).split('.'))
   # Match version-like X.Y or X.Y.Z (1-2 digit parts), not money/decimals
   text = re.sub(r'(?<![.$])\b(\d{1,2})\.(\d{1,3})(?:\.(\d{1,3}))?\b(?!\s*(?:million|billion|thousand|%|st|nd|rd|th))', _ver_to_speech, text)
   # e.g. "4.1.0" → "four-one-oh", "3.11" → "three-eleven", "2.0" → "two-oh"
   ```

   Return `text.strip()`.

2. Build each persona's voice blend (lazy-load once, reuse):

```python
from kokoro import KPipeline
pipe = KPipeline(lang_code="a")

marcus_voice = 0.6 * pipe.load_voice("am_michael") + 0.4 * pipe.load_voice("bm_george")
sofia_voice  = 0.6 * pipe.load_voice("af_heart")   + 0.4 * pipe.load_voice("bf_emma")
oliver_voice = 0.7 * pipe.load_voice("bm_george")  + 0.3 * pipe.load_voice("bm_lewis")

VOICES = {"MARCUS": marcus_voice, "SOFIA": sofia_voice, "OLIVER": oliver_voice}
```

3. Render each segment with `text_to_audio()` from `~/devel/kokoro-pdf-tts/pdf_tts.py`,
   writing each to a temp MP3.
4. Concatenate all temp MP3s into a single file using ffmpeg with loudness normalisation
   (`loudnorm=I=-16:TP=-1.5:LRA=11`), matching the pattern in `run_redbook.py`.

Run the script inside the kokoro-pdf-tts uv environment:

```bash
cd ~/devel/kokoro-pdf-tts && uv run python /tmp/carlibrated_tts.py
```

---

## Output

- **File name:** `YYYY-MM-DD_carlibrated.mp3` (today's date)
- **Local output dir:** `~/devel/kokoro-pdf-tts/audio/carlibrated/`
- **Upload destination:** `carl@nuc:containers/audiobookshelf/podcasts/Carlibrated/`

Upload via SCP after rendering:

```bash
scp ~/devel/kokoro-pdf-tts/audio/carlibrated/YYYY-MM-DD_carlibrated.mp3 \
    carl@nuc:containers/audiobookshelf/podcasts/Carlibrated/
```

Tag the MP3 with ID3 metadata using `mutagen`:
- `TIT2` (title): `Getting Carlibrated — <date>`
- `TALB` (album): `Getting Carlibrated`
- `TCON` (genre): `Podcast`
- `TDRC` (date): ISO date string

---

## Categories

### Weather

1. For Tucker, GA:
   - Current temp and forecast for the day
   - Summarize the next 7 days
2. Check Google Calendar for upcoming travel; give forecast for each location.

### Local News

- Nothing about murders, homeless, or generally negative news
- Tucker, GA
  - City council updates
  - Commercial developments
- Atlanta, GA metro highlights

### Industry News

Aggregate news across industries and sources.

Note trends and developments in these areas:
- AI
- Cloud computing (AWS, Azure, GCP)
- Databricks (https://docs.databricks.com/aws/en/release-notes/product/)
- Cybersecurity

**General Tech News & Summaries**

- TLDR: A popular daily newsletter providing concise, 5-minute summaries of the most important news in tech, AI, and programming.
- TechCrunch Daily News: Delivers the best of TechCrunch's startup coverage and tech industry news every weekday.
- The Download (MIT Technology Review): A daily dose of emerging technology, offering expert analysis on AI, climate tech, and new innovations.
- Techpresso: A daily newsletter focusing on breaking down the latest tech news, tools, and insights for professionals.

**AI & Deep Technology**

- The Rundown AI: A popular, fast-paced newsletter focused on keeping readers updated on the latest AI developments.
- Superhuman AI: A highly rated daily AI newsletter covering news, tools, and professional applications of AI.
- The Batch (DeepLearning.AI): Focuses on AI, machine learning, and data science advancements.

**Business, Strategy, and Analysis**

- Benedict's Newsletter: A weekly newsletter that provides sharp, strategic analysis of tech industry trends, particularly in mobile and broader platform shifts.
- Stratechery by Ben Thompson: Offers in-depth analysis of the business and strategy behind big tech companies.
- The Information: Known for in-depth, exclusive, and investigative reporting on the tech industry, startups, and Silicon Valley deals.

**Software Engineering & Development**

- The Pragmatic Engineer: A popular newsletter for software developers, covering engineering practices and industry trends.
- ByteByteGo: A weekly newsletter focusing on system design, software architecture, and technical explanations.

**Startup & Investment Focus**

- StrictlyVC: A daily newsletter providing updates on venture capital deals, startups, and movers in the VC space.
- Startups Weekly (TechCrunch): Focuses specifically on startup news, funding, and trends.
- The Hacker News
- Last Week in AWS: A popular newsletter focused on cloud computing and specifically the AWS ecosystem.
