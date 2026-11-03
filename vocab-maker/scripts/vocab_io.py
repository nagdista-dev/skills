#!/usr/bin/env python3
"""vocab_io.py — parse/render/write for vocab-maker."""
import re
from pathlib import Path

FRONTMATTER_ORDER = [
    "subject", "category", "level", "status",
    "arabic", "ipa", "chunks", "definition", "example",
    "pronunciation", "voice", "youglish", "playphrase", "image",
    "char", "day", "month", "created", "modified", "review",
]

def base_word(word: str) -> str:
    """Extract clean base word by stripping any disambiguation tag like (N), (V), (Adj)."""
    return re.sub(r"\s*\([A-Za-z]+\)$", "", str(word)).strip()

def youglish_url(word: str) -> str:
    """Canonical YouGlish URL for a word: lowercase, spaces become underscores, uses base word."""
    w = base_word(word)
    return "https://youglish.com/pronounce/" + str(w).strip().lower().replace(" ", "_") + "/english/us"

def playphrase_url(word: str) -> str:
    """Canonical PlayPhrase URL: lowercase, spaces become `+`, uses base word."""
    w = base_word(word)
    return "https://www.playphrase.me/#/search?q=" + str(w).strip().lower().replace(" ", "+") + "=2&language=en"

def generate_image_url(word: str, category: str = "", definition: str = "", modifier: str = "") -> str:
    """
    Generate Google Images search URL for a vocabulary word/phrase based on category and rules:
    Template: https://www.google.com/search?q=<QUERY>&tbm=isch&tbs=itp:clipart
    Rules:
    1. <QUERY> = word + modifier with spaces converted to '+'
    2. Modifiers:
       - Action verb (play, jump, run) -> illustration
       - Concrete noun (apple, bridge) -> illustration
       - Abstract emotion / concept (lonely, freedom, anxiety) -> concept
       - Adjective or state (tired, crowded, empty) -> person+illustration (e.g. tired+person+illustration)
       - Phrasal verb or idiom -> add meaning or simple situation (e.g. break+the+ice+idiom+illustration)
       - Multi-meaning word (bank, light) -> add intended context (e.g. bank+river+illustration)
    3. Words where drawing won't clarify meaning (e.g. prepositions in, on, at):
       strip &tbs=itp:clipart and add diagram or meaning (e.g. https://www.google.com/search?q=on+preposition+diagram&tbm=isch)
    4. Exact format: image: <URL>
    """
    w = base_word(word).strip().lower()
    cat = (category or "").strip()

    # Clean disambiguators like "Bank (River)"
    disambig = ""
    m_dis = re.search(r"\(([^)]+)\)$", str(word).strip())
    if m_dis:
        tag = m_dis.group(1).strip()
        if tag.lower() not in ("n", "v", "adj", "adv", "pv", "idm", "phr"):
            disambig = tag.lower()

    # 1. Custom modifier passed explicitly
    if modifier:
        mod_clean = re.sub(r"\s+", "+", modifier.strip().lower().strip("+"))
        q = f"{w.replace(' ', '+')}+{mod_clean}"
        if "diagram" in mod_clean or "meaning" in mod_clean or cat.lower() == "preposition":
            return f"https://www.google.com/search?q={q}&tbm=isch"
        return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"

    # 2. Prepositions (or words where drawing won't clarify meaning)
    PREPOSITIONS = {
        "in", "on", "at", "under", "over", "between", "behind", "through",
        "across", "into", "onto", "toward", "towards", "against", "among", "with", "from"
    }
    if cat.lower() == "preposition" or w in PREPOSITIONS:
        q = f"{w.replace(' ', '+')}+preposition+diagram"
        return f"https://www.google.com/search?q={q}&tbm=isch"

    # 3. Phrasal verb or idiom
    if cat == "Idiom":
        q = f"{w.replace(' ', '+')}+idiom+illustration"
        return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"
    if cat in ("Phrasal Verb", "Phrase") or " " in w:
        q = f"{w.replace(' ', '+')}+illustration"
        return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"

    # 4. Adjective or state
    ABSTRACT_KEYWORDS = {
        "lonely", "freedom", "anxiety", "patience", "justice", "peace",
        "hope", "love", "hate", "courage", "fear", "anger", "grief",
        "knowledge", "truth", "belief", "faith", "sorrow", "mitigate"
    }
    if cat == "Adjective":
        if w in ABSTRACT_KEYWORDS:
            q = f"{w.replace(' ', '+')}+concept"
            return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"
        q = f"{w.replace(' ', '+')}+person+illustration"
        return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"

    # 5. Abstract emotion or concept
    if w in ABSTRACT_KEYWORDS:
        q = f"{w.replace(' ', '+')}+concept"
        return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"

    # 6. Multi-meaning word with context or disambiguation
    if disambig:
        q = f"{w.replace(' ', '+')}+{disambig.replace(' ', '+')}+illustration"
        return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"

    # 7. Action verb or concrete noun (default)
    q = f"{w.replace(' ', '+')}+illustration"
    return f"https://www.google.com/search?q={q}&tbm=isch&tbs=itp:clipart"

def pronunciation_link(word: str) -> str:
    """Canonical pronunciation embed: Title-Case word, `[[{Word}_pronunciation.mp3]]`."""
    w = normalize_word(word)
    return "[[" + w + "_pronunciation.mp3]]"

def voice_link(word: str) -> str:
    """Canonical example-voice embed: lowercase word, `[[{word}_example.mp3]]`."""
    w = normalize_word(word).lower()
    return "[[" + w + "_example.mp3]]"

def auto_chunk_word(word: str) -> str:
    """Split English word into memorable hyphenated chunks.
    Ensures EVERY word has a chunk representation (even single-syllable words)
    to facilitate easy memorization for learners.
    """
    w = base_word(word).strip()
    if not w:
        return ""
    if " " in w:
        return "-".join(p.lower() for p in w.split() if p)
    s = re.sub(r"[^a-zA-Z]", "", w).lower()
    if not s:
        return ""

    def single_syllable_chunk(token: str) -> str:
        if len(token) <= 1:
            return token
        m = re.search(r"[aeiouy]", token)
        if not m:
            if len(token) >= 2:
                return token[:len(token)//2] + "-" + token[len(token)//2:]
            return token
        idx = m.start()
        if idx > 0 and idx < len(token):
            return f"{token[:idx]}-{token[idx:]}"
        elif idx == 0 and len(token) >= 2:
            m_v = re.match(r"^[aeiouy]+", token)
            if m_v:
                v_len = len(m_v.group(0))
                if v_len < len(token):
                    return f"{token[:v_len]}-{token[v_len:]}"
                else:
                    return f"{token[0]}-{token[1:]}"
        return token

    vowels = "aeiouy"
    vg = re.findall(r"[aeiouy]+", s)
    if not vg:
        return single_syllable_chunk(s)

    if len(s) <= 3:
        return single_syllable_chunk(s)

    # Single syllable with silent trailing e (e.g. 'take', 'make', 'time')
    if s.endswith("e") and not s.endswith("ee") and len(vg) > 1 and s[-2] not in vowels:
        if len(re.findall(r"[aeiouy]+", s[:-1])) == 1 and not s.endswith("le"):
            return single_syllable_chunk(s)

    if len(vg) == 1:
        return single_syllable_chunk(s)

    # Common prefixes
    pref_pattern = r"^(un|re|dis|mis|pre|pro|sub|in|im|ex|non|anti|trans|inter)"
    m_pref = re.match(pref_pattern, s)
    pref = ""
    rest = s
    if m_pref and len(s) - len(m_pref.group(1)) >= 3:
        if re.search(r"[aeiouy]", s[len(m_pref.group(1)):]):
            pref = m_pref.group(1)
            rest = s[len(pref):]

    # Suffixes
    suff_pattern = r"(tion|sion|ment|ness|able|ible|ful|less|ing|ized|ize|ate|ly|ous|ive)$"
    m_suff = re.search(suff_pattern, rest)
    suff = ""
    if m_suff and len(rest) - len(m_suff.group(1)) >= 2:
        if re.search(r"[aeiouy]", rest[:-len(m_suff.group(1))]):
            suff = m_suff.group(1)
            rest = rest[:-len(suff)]

    # Syllabic split on the middle part
    pattern = r"(?<=[aeiouy])(?=[bcdfghjklmnpqrstvwxz][aeiouy])|(?<=[aeiouy][bcdfghjklmnpqrstvwxz])(?=[bcdfghjklmnpqrstvwxz][aeiouy])"
    mid_parts = [p for p in re.split(pattern, rest) if p]

    chunks = []
    if pref:
        chunks.append(pref)
    chunks.extend(mid_parts)
    if suff:
        chunks.append(suff)

    if len(chunks) <= 1:
        return single_syllable_chunk(s)
    return "-".join(chunks)

def inflected_forms(base: str) -> set:
    base_low = base_word(base).lower()
    forms = {base_low}
    forms.add(base_low + "s")
    forms.add(base_low + "es")
    forms.add(base_low + "ed")
    forms.add(base_low + "ing")
    forms.add(base_low + "d")
    forms.add(base_low + "ies")
    if base_low.endswith("e") and not base_low.endswith("ee") and len(base_low) > 2:
        stem = base_low[:-1]
        forms.add(stem + "ing")
        forms.add(stem + "ed")
        forms.add(stem + "er")
        forms.add(stem + "ers")
    if len(base_low) >= 2 and base_low.endswith("y") and base_low[-2] not in "aeiou":
        stem = base_low[:-1]
        forms.discard(base_low + "ies")
        forms.add(stem + "ies")
        forms.add(stem + "ied")
    if len(base_low) >= 2 and base_low[-1] not in "aeiou" and base_low[-2] in "aeiou":
        forms.add(base_low + base_low[-1] + "ed")
        forms.add(base_low + base_low[-1] + "ing")
        forms.add(base_low + base_low[-1] + "s")
    return forms

def highlight_target_in_context(ctx: str, word: str) -> str:
    """Highlight the target word (or its inflected forms) in the dramatic scene context using Obsidian ==word== syntax."""
    if not ctx or not word:
        return ctx
    if "==" in ctx:
        return ctx
    clean_w = base_word(word)
    tokens = [t for t in clean_w.split() if t.lower() not in ("the","a","an","to","in","on","at","for","with","of")]
    if len(tokens) > 1:
        forms = {clean_w.lower()}
    else:
        forms = inflected_forms(clean_w)
    sorted_forms = sorted(forms, key=len, reverse=True)
    pattern = r"\b(" + "|".join(re.escape(f) for f in sorted_forms) + r")\b"
    return re.sub(pattern, r"==\1==", ctx, flags=re.IGNORECASE)

def normalize_word(raw: str) -> str:
    if raw is None:
        raise ValueError("word is required")
    collapsed=re.sub(r"\s+", " ", str(raw).strip())
    if not collapsed:
        raise ValueError("word must not be empty")
    forbidden=set('/\\:*?"<>|#^[]')
    for ch in collapsed:
        if ch in forbidden:
            raise ValueError(f"word contains forbidden character '{ch}' — not allowed: / \\ : * ? \" < > | # ^ [ ]")
    tokens=collapsed.split(" ")
    out_tokens = []
    for i, t in enumerate(tokens):
        if not t:
            continue
        if i == len(tokens) - 1 and re.match(r"^\([A-Za-z]+\)$", t):
            inner = t[1:-1]
            if len(inner) <= 2:
                formatted_tag = f"({inner.upper()})"
            else:
                formatted_tag = f"({inner.capitalize()})"
            out_tokens.append(formatted_tag)
        elif len(t) >= 2 and t.isalpha() and t.isupper():
            # All-caps acronyms (IPO, TV, CEO) keep their caps — the vault stores them in caps.
            out_tokens.append(t)
        else:
            out_tokens.append(t[0].upper() + t[1:].lower())
    normalized = " ".join(out_tokens)
    if not normalized:
        raise ValueError("word must not be empty after normalization")
    return normalized

def escape_yaml(s: str) -> str:
    return s.replace("\\","\\\\").replace('"','\\"')

def escape_table(s: str) -> str:
    return s.replace("|","\\|")

def parse_frontmatter(note_path: Path) -> dict:
    text=note_path.read_text(encoding="utf-8")
    m=re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm=m.group(1)
    out={}
    for line in fm.splitlines():
        if ":" not in line:
            continue
        key,val=line.split(":",1)
        key=key.strip()
        val=val.strip()
        if val.startswith('"') and val.endswith('"') and len(val)>=2:
            inner=val[1:-1]
            inner=inner.replace('\\"', '"').replace('\\\\','\\')
            val=inner
        out[key]=val
    return out
def extract_info_fields(note_text: str, word: str = "") -> dict:
    """Extract context, definition, example, ipa, youglish, playphrase from Info section.
    Supports both the new Obsidian callout layout and the legacy markdown table.
    """
    clean_w = base_word(word) if word else ""
    pattern = rf"## (?:{re.escape(word)} Info|{re.escape(clean_w)} Info|{re.escape(word)}|{re.escape(clean_w)}|.*? Info)\n\n(.*?)(?:\n\n---|\Z)" if word else r"## .*? Info\n\n(.*?)(?:\n\n---|\Z)"
    m_info = re.search(pattern, note_text, re.DOTALL)
    if not m_info:
        m_info = re.search(r"## (?:.*? Info|.*?)\n\n(\|.*?)(?:\n\n---|\Z)", note_text, re.DOTALL)
    if not m_info:
        return {}
    block = m_info.group(1).strip()
    out = {
        "context": "",
        "definition": "",
        "example": "",
        "ipa": "",
        "youglish": "",
        "playphrase": "",
    }
    # 1. Try markdown table parsing
    if block.startswith("|"):
        def _cell(name):
            m = re.search(rf"\|\s*{re.escape(name)}\s*\|\s*(.*?)\s*\|", block)
            return m.group(1).replace(r"\|", "|").strip() if m else ""
        out["context"] = _cell("Context") or _cell("Situation")
        out["definition"] = _cell("Definition")
        out["example"] = _cell("Example")
        m_ipa = re.search(r"`([^`]+)`", block)
        if m_ipa:
            out["ipa"] = m_ipa.group(1)
        m_yg = re.search(r"\[YouGlish\]\((.*?)\)", block)
        if m_yg:
            out["youglish"] = m_yg.group(1)
        m_pp = re.search(r"\[PlayPhrase\]\((.*?)\)", block)
        if m_pp:
            out["playphrase"] = m_pp.group(1)
        return out

    # 2. Parse Obsidian Callout card layout
    # Context callout: > [!quote] Context\n> line1\n> line2
    m_ctx = re.search(r">\s*\[!quote\]\s*(?:Context|Situation)?\s*\n((?:>[^\n]*\n?)+)", block)
    if m_ctx:
        ctx_lines = []
        for cl in m_ctx.group(1).splitlines():
            cl_s = re.sub(r"^>\s?", "", cl)
            ctx_lines.append(cl_s)
        out["context"] = "\n".join(ctx_lines).strip()

    # Definition: **Definition:** ...
    m_def = re.search(r"\*\*Definition:\*\*\s*(.*?)(?=\n\n|\n\*\*|\Z)", block, re.DOTALL)
    if m_def:
        out["definition"] = m_def.group(1).strip()

    # Example: **Example:** ...
    m_ex = re.search(r"\*\*Example:\*\*\s*(.*?)(?=\n\n|\n\*\*|\Z)", block, re.DOTALL)
    if m_ex:
        out["example"] = m_ex.group(1).strip()

    # IPA: **IPA:** `{ipa}`
    m_ipa = re.search(r"\*\*IPA:\*\*\s*`([^`]+)`", block)
    if not m_ipa:
        m_ipa = re.search(r"`([^`]+)`", block)
    if m_ipa:
        out["ipa"] = m_ipa.group(1).strip()

    # Lookups: [YouGlish](url) and [PlayPhrase](url)
    m_yg = re.search(r"\[YouGlish\]\((.*?)\)", block)
    if m_yg:
        out["youglish"] = m_yg.group(1).strip()
    m_pp = re.search(r"\[PlayPhrase\]\((.*?)\)", block)
    if m_pp:
        out["playphrase"] = m_pp.group(1).strip()

    return out

def extract_notes_dict(note_text: str, word: str = "") -> dict:
    """Extract notes dict from ## {word} Notes block.
    Supports both bold labels (**ترجمة الكلمة:**) and Obsidian callouts (> [!tip] عارف إن؟).
    """
    clean_w = base_word(word) if word else ""
    pattern = rf"## (?:{re.escape(word)} Notes|{re.escape(clean_w)} Notes|.*? Notes)\n\n(.*?)(?:\n\n---|\Z)" if word else r"## .*? Notes\n\n(.*?)(?:\n\n---|\Z)"
    m_notes = re.search(pattern, note_text, re.DOTALL)
    if not m_notes:
        m_notes = re.search(r"## .*? Notes\n\n(.*?)(?:\n\n---|\Z)", note_text, re.DOTALL)
    if not m_notes:
        return {}
    block = m_notes.group(1)
    label_map = {
        "ترجمة الكلمة": "word_translations",
        "ترجمة المثال": "example_translation",
        "إمتى بتتقال": "when_used",
        "ملاحظة قواعد": "grammar_note",
        "السياق الثقافي": "cultural_context",
        "أصل الكلمة وإزاي تفتكرها": "etymology",
        "عارف إن؟": "curiosity",
        "عارف إن": "curiosity",
        "معنى تاني": "second_meaning",
        "من نفس الأصل": "word_family",
        "مرادفات": "synonyms",
        "فرق عن كلمة قريبة": "synonym_contrast",
        "أضداد": "antonyms",
        "أمثلة شائعة": "common_examples",
        "أخطاء شائعة": "common_mistakes",
        "ملاحظات مهمة": "important_notes",
        "ملاحظات إضافية": "additional_notes",
        "جرّبها النهارده": "try_it",
    }
    callout_map = {
        "tip": "curiosity",
        "warning": "common_mistakes",
        "info": "grammar_note",
        "note": "second_meaning",
        "todo": "try_it",
    }
    notes = {}
    current_key = None

    paras = re.split(r"\n\n+", block)
    for p in paras:
        p_str = p.strip()
        if not p_str:
            continue
        # Check callout: > [!type] Title
        m_c = re.match(r"^>\s*\[!([a-zA-Z]+)\]\s*(.*)", p_str)
        if m_c:
            c_type = m_c.group(1).lower()
            c_title = m_c.group(2).strip().rstrip(":").rstrip("؟")
            key = None
            if c_title:
                key = label_map.get(c_title) or label_map.get(c_title + "؟")
            if not key:
                key = callout_map.get(c_type)
            lines = p_str.splitlines()[1:]
            content = "\n".join(re.sub(r"^>\s?", "", l) for l in lines).strip()
            if key:
                notes[key] = content
            current_key = None
            continue

        # Check bold label: **Label:** content
        if p_str.startswith("**"):
            m_lab = re.match(r"\*\*(.*?)\*\*\s*(.*)", p_str, re.DOTALL)
            if m_lab:
                lab = m_lab.group(1).strip().rstrip(":").rstrip("؟")
                key = label_map.get(lab) or label_map.get(lab + "؟")
                val = m_lab.group(2).strip()
                if key:
                    notes[key] = val
                    current_key = key
                    continue

        if current_key in ("word_family", "synonyms"):
            notes[current_key] = (notes.get(current_key, "") + "\n" + p_str).strip()

    return notes

def render_note(word: str, fields: dict) -> str:
    notes=fields.get("notes") or {}
    lines=[]
    def note_text(v):
        if isinstance(v, (list, tuple)):
            items=[str(x or "").strip() for x in v]
            return " — ".join(x for x in items if x)
        return str(v or "").strip()
    def make_callout(callout_type: str, title: str, content: str) -> str:
        res = [f"> [!{callout_type}] {title}"]
        for cl in content.splitlines():
            res.append(f"> {cl}" if cl else ">")
        return "\n".join(res)

    def add_callout(callout_type: str, title: str, val):
        """Render one note field as an Obsidian callout with an Arabic title."""
        txt = note_text(val)
        if not txt:
            return
        lines.append(make_callout(callout_type, title, txt))
    def add_family(val):
        """Render word family members as Obsidian wikilinks for Graph View tree connections."""
        if val is None:
            return
        entries = val if isinstance(val, (list, tuple)) else [val]
        rendered=[]
        for e in entries:
            if isinstance(e, dict):
                form=str(e.get("form","")).strip()
                if not form:
                    continue
                if form.startswith("[[") and form.endswith("]]"):
                    rendered.append(f"- {form}")
                else:
                    rendered.append(f"- [[{form}]]")
            elif str(e).strip():
                s=str(e).strip()
                if s.startswith("- "):
                    s=s[2:].strip()
                if s.startswith("[[") and s.endswith("]]"):
                    rendered.append(f"- {s}")
                else:
                    rendered.append(f"- [[{s}]]")
        if rendered:
            lines.append(make_callout("example", "من نفس الأصل", "\n".join(rendered)))
    def add_synonyms(val):
        """Render synonyms as Obsidian wikilinks for Graph View connections."""
        if val is None:
            return
        entries = val if isinstance(val, (list, tuple)) else [val]
        rendered=[]
        for e in entries:
            s=str(e or "").strip()
            if not s:
                continue
            sub_items = [p.strip() for p in re.split(r"[\n—–]+", s) if p.strip()]
            for item in sub_items:
                item_clean = item.strip()
                if item_clean.startswith("- "):
                    item_clean = item_clean[2:].strip()
                item_clean = item_clean.strip("`").strip()
                if not item_clean:
                    continue
                if item_clean.startswith("[[") and item_clean.endswith("]]"):
                    rendered.append(f"- {item_clean}")
                else:
                    rendered.append(f"- [[{item_clean}]]")
        if rendered:
            lines.append(make_callout("example", "مرادفات", "\n".join(rendered)))
    def add_antonyms(val):
        """Render antonyms as a bulleted callout; items keep their backticks."""
        if val is None:
            return
        items = val if isinstance(val, (list, tuple)) else [val]
        rendered = []
        for item in items:
            s = str(item or "").strip()
            if not s:
                continue
            if s.startswith("`") and s.endswith("`"):
                rendered.append(s)
            else:
                rendered.append(f"`{s}`")
        if rendered:
            lines.append(make_callout("note", "أضداد", "\n".join(f"- {r}" for r in rendered)))
    def add_examples(val, word):
        """Render common_examples as full everyday sentences, target word highlighted."""
        if val is None:
            return
        items = val if isinstance(val, (list, tuple)) else [val]
        rendered = []
        for item in items:
            s = str(item or "").strip()
            if not s:
                continue
            if s.startswith("- "):
                s = s[2:].strip()
            if "==" not in s:
                s = highlight_target_in_context(s, word)
            rendered.append(f"- {s}")
        if rendered:
            lines.append(make_callout("example", "أمثلة شائعة", "\n".join(rendered)))
    add_callout("abstract", "ترجمة الكلمة", notes.get("word_translations") or notes.get("translations"))
    add_callout("abstract", "ترجمة المثال", notes.get("example_translation"))
    add_callout("info", "إمتى بتتقال", notes.get("when_used"))
    add_callout("info", "ملاحظة قواعد", notes.get("grammar_note"))
    add_callout("info", "السياق الثقافي", notes.get("cultural_context"))
    add_callout("tip", "عارف إن؟", notes.get("curiosity"))
    add_callout("note", "معنى تاني", notes.get("second_meaning"))
    add_family(notes.get("word_family"))
    add_synonyms(notes.get("synonyms"))
    add_callout("important", "فرق عن كلمة قريبة", notes.get("synonym_contrast"))
    add_antonyms(notes.get("antonyms"))
    add_examples(notes.get("common_examples"), word)
    add_callout("warning", "أخطاء شائعة", notes.get("common_mistakes"))
    add_callout("important", "ملاحظات مهمة", notes.get("important_notes"))
    add_callout("note", "ملاحظات إضافية", notes.get("additional_notes"))
    add_callout("todo", "جرّبها النهارده", notes.get("try_it"))
    block="\n\n".join(lines)
    arabic=fields.get("arabic","").strip()
    example=fields.get("example","").strip()
    arabic_esc=escape_yaml(arabic)
    example_esc=escape_yaml(example)
    ctx_raw=fields.get("context") or fields.get("situation") or ""
    ctx_clean=ctx_raw.replace("\\|","|").strip()
    ctx_clean=highlight_target_in_context(ctx_clean, word)
    ctx_callout = "\n> ".join(ctx_clean.splitlines()) if ctx_clean else ""
    context_block = f"> [!quote] Context\n> {ctx_callout}\n\n" if ctx_callout else ""
    defin_clean=fields.get("definition","").replace("\\|","|").strip()
    defin_esc=escape_yaml(defin_clean)
    ex_clean=example.replace("\\|","|").strip()
    ipa=fields.get("ipa","")
    ipa_esc=escape_yaml(ipa)
    chunks=fields.get("chunks")
    if not chunks or not str(chunks).strip():
        chunks = auto_chunk_word(word)
    chunks_esc=escape_yaml(str(chunks))
    char=fields.get("char","")
    category_v=fields.get("category") or fields.get("type","")
    level=fields.get("level","")
    status=fields.get("status","")
    day=fields.get("day","")
    created=fields.get("created","")
    modified=fields.get("modified","")
    review=fields.get("review","")
    month=fields.get("month","")
    word_lower=word.lower()
    b_word=base_word(word)
    b_word_lower=b_word.lower()
    b_word_us=b_word_lower.replace(" ", "_")
    youglish=youglish_url(word)
    playphrase=playphrase_url(word)
    pron_link=pronunciation_link(word)
    voice_link_val=voice_link(word)
    fm_lines = [
        "---",
        "subject: Vocabulary",
        f"category: {category_v}",
        f"level: {level}",
        f"status: {status}",
        f'arabic: "{arabic_esc}"',
        f'ipa: "{ipa_esc}"',
        f'chunks: "{chunks_esc}"',
        f'definition: "{defin_esc}"',
        f'example: "{example_esc}"',
        f'pronunciation: "{pron_link}"',
        f'voice: "{voice_link_val}"',
        f'youglish: "{youglish}"',
    ]
    if category_v in ("Idiom", "Phrase"):
        fm_lines.append(f'playphrase: "{playphrase}"')
    image_val = str(fields.get("image", "") or "").strip()
    if not image_val:
        image_val = generate_image_url(word, category_v, defin_clean)
    if image_val:
        fm_lines.append(f'image: "{image_val}"')
    fm_lines.extend([
        f"char: {char}",
        f"day: {day}",
        f"month: {month}",
        f"created: {created}",
        f"modified: {modified}",
        f"review: {review}",
        "---",
    ])
    fm_header = "\n".join(fm_lines)
    # PlayPhrase is a video-lookup for idioms and phrases only — single words
    # and ordinary parts of speech keep the YouGlish lookup only.
    lookup = f"**IPA:** `{ipa}` &nbsp;•&nbsp; **Lookup:** [YouGlish]({youglish})"
    if category_v in ("Idiom", "Phrase"):
        lookup += f" &nbsp;•&nbsp; [PlayPhrase]({playphrase})"
    return f"""{fm_header}

---

## {word} Info

{context_block}**Definition:** {defin_clean}

**Example:** {ex_clean}

{lookup}

---

## {word} Pronunciation

![[{word}_pronunciation.mp3]]

---

## {word} Example

![[{word_lower}_example.mp3]]

---

## {word} Notes

{block}

---

## {word} Gang

```base
views:
  - type: table
    name: {word} Gang
    filters:
      and:
        - file.inFolder("English/Vocabulary/{char}")
        - category == "{category_v}"
        - status == "Done"
    order:
      - file.name
      - pronunciation
      - voice
      - image
      - review
    columnSize:
      note.pronunciation: 155
      note.voice: 155
```"""
