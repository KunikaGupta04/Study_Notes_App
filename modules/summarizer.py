import os
import re
import time
import markdown
from google import genai
from dotenv import load_dotenv

load_dotenv()

API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
VALID_KEYS = [k for k in API_KEYS if k]

MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
]


# ─────────────────────────────────────────────
#  VIDEO LENGTH CLASSIFIER
# ─────────────────────────────────────────────
def classify_video(text: str) -> dict:
    """
    Classifies video by transcript character count.
    Returns settings controlling note depth and diagram count.

    Real-world calibration (words-per-minute ≈ 130):
      4 min  ≈  3,100 words ≈  18,000 chars
      7 min  ≈  5,400 words ≈  32,000 chars
      15 min ≈ 11,700 words ≈  70,000 chars
      30 min ≈ 23,400 words ≈ 140,000 chars

    BUT transcripts contain timestamps/tags so real char counts
    after parsing are roughly 30-50% of the above.
    So a 4-min video → ~6,000-9,000 chars after cleaning.
    """
    n = len(text)

    if n < 4000:
        return dict(
            label="very short (< 2 min)",
            max_chars=n,
            depth="brief",
            concepts="2-3",
            takeaways="3",
            max_diagrams=1,
            note_length="very short — 1 page maximum",
        )
    elif n < 12000:
        return dict(
            label="short (3-8 min)",
            max_chars=n,
            depth="concise",
            concepts="3-4",
            takeaways="4-5",
            max_diagrams=2,
            note_length="short — 1-2 pages",
        )
    elif n < 25000:
        return dict(
            label="medium (10-20 min)",
            max_chars=18000,
            depth="standard",
            concepts="5-7",
            takeaways="5-6",
            max_diagrams=3,
            note_length="medium — 2-3 pages",
        )
    elif n < 50000:
        return dict(
            label="long (25-40 min)",
            max_chars=30000,
            depth="detailed",
            concepts="7-10",
            takeaways="6-8",
            max_diagrams=3,
            note_length="long — 3-5 pages",
        )
    elif n < 100000:
        return dict(
            label="lecture (45-70 min)",
            max_chars=50000,
            depth="comprehensive",
            concepts="10-14",
            takeaways="8-10",
            max_diagrams=4,
            note_length="very long — 5+ pages",
        )
    else:
        return dict(
            label="full course (2h+)",
            max_chars=70000,
            depth="exhaustive",
            concepts="14+",
            takeaways="10+",
            max_diagrams=4,
            note_length="exhaustive — cover everything",
        )


# ─────────────────────────────────────────────
#  HARD DIAGRAM LIMIT ENFORCER
# ─────────────────────────────────────────────
def enforce_diagram_limit(raw: str, max_diagrams: int) -> str:
    """
    If Gemini generated MORE mermaid diagrams than allowed,
    keep only the first `max_diagrams` and remove the rest.
    This is the hard enforcement — AI instructions alone aren't reliable.
    """
    pattern = re.compile(r'```mermaid\s*\n.*?```', re.DOTALL)
    matches = list(pattern.finditer(raw))

    if len(matches) <= max_diagrams:
        return raw  # within limit, nothing to do

    # Remove excess diagrams (keep first N, delete the rest)
    # Work backwards so positions don't shift
    for match in reversed(matches[max_diagrams:]):
        raw = raw[:match.start()] + raw[match.end():]

    print(f"[summarizer] Trimmed diagrams from {len(matches)} → {max_diagrams}")
    return raw


# ─────────────────────────────────────────────
#  HTML CONVERTER  (mermaid-safe)
# ─────────────────────────────────────────────
def convert_to_html(raw_text):
    """
    Convert Gemini markdown → HTML.
    Mermaid blocks are extracted before markdown() processes them,
    sanitized, then re-injected as <div class="mermaid"> blocks.
    """
    mermaid_blocks = {}
    counter = [0]

    def save_mermaid(match):
        key = f"MERMAIDBLOCK{counter[0]}END"
        code = match.group(1).strip()

        # 1. Remove non-ASCII (emojis, unicode arrows, etc.)
        code = re.sub(r'[^\x00-\x7F]', '', code)

        # 2. Remove HTML entities
        code = re.sub(r'&[a-z]+;', '', code)

        # 3. Fix node labels — remove parens, colons, quotes inside [ ]
        def clean_label(m):
            inner = m.group(1)
            inner = re.sub(r'[():"\']', '', inner)   # remove ():"'
            inner = re.sub(r'\s{2,}', ' ', inner)    # collapse spaces
            inner = inner[:60]                         # truncate long labels
            return '[' + inner + ']'
        code = re.sub(r'\[([^\]]+)\]', clean_label, code)

        # 4. Fix parentheses in round nodes ( ) used in flowcharts
        def clean_round_label(m):
            inner = m.group(1)
            inner = re.sub(r'[():"\']', '', inner)
            inner = inner[:60]
            return '(' + inner + ')'
        code = re.sub(r'\(([^)]+)\)', clean_round_label, code)

        # 5. Fix mindmap indentation — ensure consistent 2-space or 4-space indent
        if code.strip().startswith('mindmap'):
            lines = code.split('\n')
            fixed = []
            for line in lines:
                # Replace tabs with spaces
                line = line.replace('\t', '  ')
                fixed.append(line)
            code = '\n'.join(fixed)

        # 6. Remove lines with just special characters or empty labels
        lines = code.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are only symbols
            if stripped and re.match(r'^[^a-zA-Z0-9`\-\>\/\s\[\]\(\)\{\}]+$', stripped):
                continue
            clean_lines.append(line)
        code = '\n'.join(clean_lines)

        # 7. Collapse excess blank lines
        code = re.sub(r'\n{3,}', '\n\n', code)

        mermaid_blocks[key] = (
            '<div class="mermaid-container">'
            '<div class="mermaid-label" onclick="toggleDiagram(this.parentElement)">'
            '<i class="fa-solid fa-diagram-project diagram-icon"></i>'
            '<span class="label-text">Diagram</span>'
            '<span class="expand-hint"><i class="fa-solid fa-expand"></i> Click to expand</span>'
            '<i class="fa-solid fa-chevron-down expand-chevron"></i>'
            '</div>'
            f'<div class="mermaid-preview" onclick="toggleDiagram(this.parentElement)"><div class="mermaid">{code}</div></div>'
            '<button class="mermaid-expand-btn" onclick="toggleDiagram(this.parentElement)">'
            '<i class="fa-solid fa-chevron-down"></i> Expand diagram'
            '</button>'
            '</div>'
        )
        
        counter[0] += 1
        return key  # ← CRITICAL: was missing, caused diagrams to vanish

    # Extract mermaid blocks BEFORE markdown processes them
    text = re.sub(r'```mermaid\s*\n(.*?)```', save_mermaid, raw_text, flags=re.DOTALL)

    # Convert remaining markdown to HTML
    html = markdown.markdown(
        text,
        extensions=['tables', 'fenced_code', 'nl2br', 'sane_lists']
    )

    # Re-inject mermaid blocks (replace placeholder keys with actual HTML)
    for key, block in mermaid_blocks.items():
        html = html.replace(f'<p>{key}</p>', block)
        html = html.replace(key, block)

    return html


# ─────────────────────────────────────────────
#  DYNAMIC PROMPT BUILDER
# ─────────────────────────────────────────────
def build_prompt(text: str, cfg: dict) -> str:
    is_brief = cfg['depth'] in ('brief', 'concise')
    is_long  = cfg['depth'] in ('comprehensive', 'exhaustive')

    seq_section = "" if is_brief else """
## Process / Lifecycle

```mermaid
sequenceDiagram
    participant User
    participant System
    User->>System: Action
    System-->>User: Result
```
"""

    return f"""
You are an expert Senior Professor. Convert this transcript into study notes in Markdown.

VIDEO LENGTH : {cfg['label']}
NOTE LENGTH  : {cfg['note_length']}
DEPTH        : {cfg['depth']}
DIAGRAMS     : exactly {cfg['max_diagrams']} mermaid diagram(s) — no more, no less

IMPORTANT: Match the note length to the video. A short video gets short notes.
A 4-minute video does NOT need 5 pages of notes.

══════════════════════════════
STRUCTURE:
══════════════════════════════

## Overview
{'2-3 sentence summary.' if is_brief else '4-6 sentence summary covering the full topic.'}

## Core Concepts
Cover exactly {cfg['concepts']} concepts.
{'Keep each concept brief — 2-3 bullets.' if is_brief else 'Expand each concept with 3-5 detailed bullets.'}

### [Concept Name]
- Bullet with **bold key terms**

## How It Works
{'3-4 numbered steps.' if is_brief else 'Detailed numbered steps explaining the full process.'}

```mermaid
flowchart TD
    A[Start] --> B[Step 1]
    B --> C[Step 2]
    C --> D[End]
```

{'## Concept Map' if not is_brief else ''}
{"""
```mermaid
mindmap
  root((Topic))
    ConceptA
      SubA
    ConceptB
      SubB
```
""" if not is_brief else ''}

{seq_section}

## Comparison Table
| Feature | Option A | Option B |
|---------|----------|----------|
| ...     | ...      | ...      |

## Real-World Applications
{'2 brief examples.' if is_brief else f'{cfg["concepts"]} examples with bold **domain** names.'}

## Key Takeaways
{cfg['takeaways']} bullet points.

══════════════════════════════
STRICT RULES:
══════════════════════════════
1. Markdown ONLY — no HTML, no extra text before or after.
2. Use EXACTLY {cfg['max_diagrams']} mermaid diagram(s). Not more.
3. Each mermaid block: ```mermaid on its own line, ``` closing on its own line.
4. Inside mermaid [ ] labels: NO parentheses, NO emojis, NO special characters.
   BAD : A[Process step (e.g. SGD)]
   GOOD: A[Process step e.g. SGD]
5. Bold every technical term on first use.
6. Keep total note length appropriate for a {cfg['label']} video.
7. DO NOT pad or repeat content just to seem thorough.

TRANSCRIPT:
{text}
"""


# ─────────────────────────────────────────────
#  MAIN FUNCTION
# ─────────────────────────────────────────────
def generate_structured_notes(text):
    """
    Returns (html_string, raw_markdown_string).
    Scales note depth and diagram count dynamically by video length.
    """
    if not VALID_KEYS:
        err = "Error: No valid Gemini API keys found in .env file."
        return err, err

    cfg = classify_video(text)
    print(
        f"[summarizer] '{cfg['label']}' | "
        f"{len(text):,} chars | "
        f"depth={cfg['depth']} | "
        f"max_diagrams={cfg['max_diagrams']} | "
        f"feeding {cfg['max_chars']:,} chars to Gemini"
    )

    prompt = build_prompt(text[:cfg['max_chars']], cfg)

    for api_key in VALID_KEYS:
        client = genai.Client(api_key=api_key)
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                raw = response.text.strip()

                # Hard enforce diagram limit — AI instructions alone aren't reliable
                raw = enforce_diagram_limit(raw, cfg['max_diagrams'])

                # Safety net — ensure at least 1 diagram exists
                if '```mermaid' not in raw:
                    raw += (
                        "\n\n## Summary Diagram\n\n"
                        "```mermaid\nflowchart LR\n"
                        "    A[Topic] --> B[Core Concepts]\n"
                        "    B --> C[Applications]\n"
                        "    C --> D[Key Takeaways]\n```\n"
                    )

                html = convert_to_html(raw)
                return html, raw

            except Exception as e:
                err_str = str(e)
                if any(c in err_str for c in ["429", "503", "UNAVAILABLE", "quota"]):
                    time.sleep(4)
                    continue
                elif "404" in err_str:
                    break
                else:
                    time.sleep(2)
                    continue

    err = "Error: All API keys and models exhausted. Please wait and try again."
    return err, err
