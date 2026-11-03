#!/usr/bin/env python3
r"""
vocab_checks.py — ONE implementation of all note checks.

Used by build_word.py (build-time validation and --check) and audit_vault.py.
No duplicated logic. Covers: frontmatter, format, level, arabic, summary rules and openings,
example vs profile, backtick policy, note count/overlap/short notes, \| normalization.
"""

import re
from pathlib import Path

# Codes and helpers
def _issue(code, severity, auto_fixable, message):
    return {"code": code, "severity": severity, "auto_fixable": auto_fixable, "message": message}

def normalize_table_escape(s: str) -> str:
    r"""Normalize table escape \| to | before comparing example strings."""
    return s.replace("\\|", "|")

# Frontmatter and format checks
FRONTMATTER_ORDER = [
    "subject", "category", "level", "status",
    "arabic", "ipa", "chunks", "definition", "example",
    "pronunciation", "voice", "youglish", "playphrase", "image",
    "char", "day", "month", "created", "modified", "review",
]
LEGACY_FRONTMATTER_ORDER = [k for k in FRONTMATTER_ORDER if k not in ("youglish","playphrase","pronunciation","voice","ipa","chunks","definition","image")]
# Findings that are PROPOSALS on existing notes (never violations): rebuild upgrades them.
# Single source of truth shared by build_word.py --check and audit_vault.py.
PROPOSAL_CODES = {
    "example_too_long","example_not_first_person","example_contraction","example_slang",
    "example_target","target_word_missing","example_form_missing","image_missing","image_url",
    "rtl_line_start",
}

# Arabic text-direction rule: a line in an Arabic note must not START with Latin
# text, otherwise the renderer guesses the paragraph direction and the mixed
# Arabic/English line becomes unreadable. The line must open with Arabic
# (e.g. "كلمة dispatch بتاخد ..." instead of "dispatch بتاخد ...").
RTL_START_MESSAGE = (
    "line starts with English text — start the line with Arabic so the mixed "
    "Arabic/English direction renders correctly (e.g. \"كلمة dispatch ...\" not \"dispatch ...\")"
)

def _strip_direction_prefixes(s: str) -> str:
    """Remove callout markers, list markers and bold labels so the real first
    character of the line content can be inspected."""
    s = s.strip()
    while s.startswith(">"):
        s = s[1:].strip()
    if s.startswith("**"):
        # Bold Arabic label governs the direction of the line — content after the
        # label is mid-line text, which is fine.
        return ""
    s = re.sub(r"^([-*+]|\d+[.)])\s+", "", s)
    return s.strip()

def check_rtl_line_start(note_text: str, blocking: bool = True):
    """Check that no line in the Notes block starts with Latin text.

    Arabic-first lines keep Obsidian's bidi rendering readable. A line that
    opens with an English word ("dispatch takes a direct object: ...") flips the
    paragraph direction and breaks the reading flow for an Arabic reader.

    The `أمثلة شائعة` (common examples) callout is English by design — its
    bullets are full English sentences — so it is exempt.

    blocking=True -> ERROR (a payload must not be written in this shape).
    blocking=False -> INFO proposal (an existing card is fixed on its next rebuild).
    """
    issues = []
    m = re.search(r"## .*? Notes\n\n(.*?)\n\n---", note_text, re.DOTALL)
    if not m:
        return issues
    in_code = False
    in_english_block = False
    for line in m.group(1).splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m_head = re.match(r"^>\s*\[!([a-zA-Z]+)\]\s*(.*)$", line.strip())
        if m_head:
            title = m_head.group(2).strip().rstrip(":").rstrip("؟")
            in_english_block = title == "أمثلة شائعة"
            continue
        if in_english_block:
            continue
        content = _strip_direction_prefixes(line)
        if not content:
            continue
        if re.match(r"^[A-Za-z]", content):
            if blocking:
                issues.append(_issue("rtl_line_start", "ERROR", False,
                                     f"{RTL_START_MESSAGE}: \"{content[:60]}\""))
            else:
                issues.append(_issue("rtl_line_start", "INFO", True,
                                     f"PROPOSAL: {RTL_START_MESSAGE}: \"{content[:60]}\""))
    return issues

def youglish_url(word: str) -> str:
    """Canonical YouGlish URL for a word: lowercase, spaces become underscores.

    Multi-meaning cards ("Crack (N)", "Faint (V)") use the clean base word, so the
    URL must strip the disambiguation tag — same rule as vocab_io.youglish_url.
    """
    from vocab_io import base_word as _base
    w = _base(word)
    return "https://youglish.com/pronounce/" + str(w).strip().lower().replace(" ", "_") + "/english/us"

def playphrase_url(word: str) -> str:
    """Canonical PlayPhrase URL: lowercase, spaces become `+` (all cards)."""
    from vocab_io import base_word as _base
    w = _base(word)
    return "https://www.playphrase.me/#/search?q=" + str(w).strip().lower().replace(" ", "+") + "=2&language=en"

def pronunciation_link(word: str) -> str:
    """Canonical pronunciation embed: Title-Case word, `[[{Word}_pronunciation.mp3]]`."""
    from vocab_io import normalize_word as _norm
    w = _norm(word)
    return "[[" + w + "_pronunciation.mp3]]"

def voice_link(word: str) -> str:
    """Canonical example-voice embed: lowercase word, `[[{word}_example.mp3]]`."""
    from vocab_io import normalize_word as _norm
    w = _norm(word).lower()
    return "[[" + w + "_example.mp3]]"

def check_pronunciation_voice(fm: dict, word: str, legacy_ok: bool = False):
    issues=[]
    expected_pron=pronunciation_link(word) if word else ""
    expected_voice=voice_link(word) if word else ""
    val_pron=str(fm.get("pronunciation","") or "").strip()
    val_voice=str(fm.get("voice","") or "").strip()
    if not val_pron:
        if legacy_ok:
            issues.append(_issue("pronunciation_missing", "INFO", True, "PROPOSAL: card has no pronunciation property — rebuild it to add the canonical pronunciation embed"))
        else:
            issues.append(_issue("pronunciation_missing", "ERROR", False, f"pronunciation property is required — expected {expected_pron}"))
    elif expected_pron and val_pron != expected_pron:
        issues.append(_issue("pronunciation_link", "ERROR", True, f"pronunciation must be {expected_pron} — got {val_pron}"))
    if not val_voice:
        if legacy_ok:
            issues.append(_issue("voice_missing", "INFO", True, "PROPOSAL: card has no voice property — rebuild it to add the canonical voice embed"))
        else:
            issues.append(_issue("voice_missing", "ERROR", False, f"voice property is required — expected {expected_voice}"))
    elif expected_voice and val_voice != expected_voice:
        issues.append(_issue("voice_link", "ERROR", True, f"voice must be {expected_voice} — got {val_voice}"))
    return issues

def check_playphrase(fm: dict, word: str, type_v: str = "", legacy_ok: bool = False):
    issues=[]
    is_idiom_or_phrase = type_v in ("Idiom", "Phrase")
    if is_idiom_or_phrase:
        expected=playphrase_url(word) if word else ""
        val=str(fm.get("playphrase","") or "").strip()
        if not val:
            if legacy_ok:
                issues.append(_issue("playphrase_missing", "INFO", True, "PROPOSAL: idiom/phrase card has no playphrase property — rebuild it to add the canonical PlayPhrase link"))
            else:
                issues.append(_issue("playphrase_missing", "ERROR", False, f"playphrase property is required for idioms/phrases — expected {expected}"))
            return issues
        if expected and val != expected:
            issues.append(_issue("playphrase_url", "ERROR", True, f"playphrase URL must be {expected} — got {val}"))
        return issues
    if str(fm.get("playphrase","") or "").strip():
        issues.append(_issue("playphrase_non_idiom", "INFO", True, "PROPOSAL: playphrase is idiom/phrase-only — it will be dropped on the next rebuild"))
    return issues

def check_chunks(fm: dict, word: str, legacy_ok: bool = False):
    issues=[]
    val=str(fm.get("chunks","") or "").strip()
    if not val:
        if legacy_ok:
            issues.append(_issue("chunks_missing", "INFO", True, "PROPOSAL: card has no chunks property or empty chunks — rebuild it to add chunks"))
        else:
            issues.append(_issue("chunks_missing", "ERROR", False, "chunks property is required in frontmatter and must not be empty"))
    return issues

def check_definition(fm: dict, legacy_ok: bool = False):
    issues=[]
    val=str(fm.get("definition","") or "").strip()
    if not val:
        if legacy_ok:
            issues.append(_issue("definition_missing", "INFO", True, "PROPOSAL: card has no definition property — rebuild it to add the canonical definition property (same text as the Info block definition)"))
        else:
            issues.append(_issue("definition_missing", "ERROR", False, "definition property is required in frontmatter and must not be empty"))
    return issues

def check_youglish(fm: dict, word: str, legacy_ok: bool = False):
    issues=[]
    expected=youglish_url(word) if word else ""
    val=str(fm.get("youglish","") or "").strip()
    if not val:
        if legacy_ok:
            issues.append(_issue("youglish_missing", "INFO", True, "PROPOSAL: card has no youglish property — rebuild it to add the canonical YouGlish link"))
        else:
            issues.append(_issue("youglish_missing", "ERROR", False, f"youglish property is required — expected {expected}"))
        return issues
    if expected and val != expected:
        issues.append(_issue("youglish_url", "ERROR", True, f"youglish URL must be {expected} — got {val}"))
    return issues

def check_image(fm: dict, word: str, legacy_ok: bool = False):
    issues=[]
    val=str(fm.get("image","") or "").strip()
    if not val:
        if legacy_ok:
            issues.append(_issue("image_missing", "INFO", True, "PROPOSAL: card has no image property — rebuild it to add the Google Images link"))
        else:
            issues.append(_issue("image_missing", "ERROR", False, "image property is required on frontmatter"))
        return issues
    if not (val.startswith("https://www.google.com/search?q=") and "tbm=isch" in val):
        issues.append(_issue("image_url", "ERROR", True, f"image URL must follow https://www.google.com/search?q=<QUERY>&tbm=isch format, got '{val}'"))
    return issues

# Legacy cards carried PlayPhrase in the Info block on every category.
INFO_TABLE_ROWS = ["Context","Definition","Example","IPA","YouGlish","PlayPhrase"]
# Cards written before the `Context` row label was fixed.
LEGACY_INFO_TABLE_ROWS = ["Situation","Definition","Example","IPA","YouGlish"]

def check_info_table(note_text: str, legacy_ok: bool = False, type_v: str = ""):
    """The Info block is the card's head.
    Modern cards use Obsidian callout card layout:
      > [!quote] Context (if context provided)
      **Definition:** ...
      **Example:** ...
      **IPA:** `{ipa}` &nbsp;•&nbsp; **Lookup:** [YouGlish](...)  (+ PlayPhrase for idioms/phrases only)
    Legacy cards use a Markdown table with fixed rows.
    """
    issues=[]
    sev = "INFO" if legacy_ok else "ERROR"
    m=re.search(r"^## .*? Info\s*\n\n(.*?)\n\n---", note_text, re.DOTALL | re.MULTILINE)
    if not m:
        issues.append(_issue("info_table_missing", sev, False, "Info block not found — expected `## {Word} Info` section"))
        return issues
    block = m.group(1).strip()

    # 1. Modern Obsidian callout card layout
    # PlayPhrase is a video lookup for idioms and phrases only.
    expects_playphrase = type_v in ("Idiom", "Phrase")
    has_playphrase = "[PlayPhrase]" in block
    is_card_layout = (
        "**Definition:**" in block and
        "**Example:**" in block and
        "**IPA:**" in block and
        "[YouGlish]" in block and
        has_playphrase == expects_playphrase
    )
    if is_card_layout:
        return issues
    if (not legacy_ok) and (not expects_playphrase) and has_playphrase and "**Definition:**" in block and "**Example:**" in block and "**IPA:**" in block and "[YouGlish]" in block:
        issues.append(_issue("playphrase_lookup_non_idiom", "ERROR", True,
                             "PlayPhrase lookup is for idioms and phrases only — remove it from the Info block"))
        return issues

    # 2. Legacy markdown table
    if block.startswith("|"):
        labels=[]
        for row in block.splitlines():
            row=row.strip()
            if not row.startswith("|"):
                continue
            cells=[c.strip() for c in row.strip("|").split("|")]
            if not cells or not cells[0]:
                continue
            if set(cells[0]) <= set("-: "):
                continue
            labels.append(cells[0])
        labels=[l for l in labels if l != "Word"]
        if legacy_ok:
            if labels == INFO_TABLE_ROWS:
                issues.append(_issue("info_table_legacy", "INFO", True, "PROPOSAL: legacy table card head — rebuild the card to upgrade to Obsidian callout card"))
                return issues
            if labels == LEGACY_INFO_TABLE_ROWS:
                issues.append(_issue("info_table_legacy_context", "INFO", True, "PROPOSAL: legacy `Situation` row label — rebuild the card to rename it to `Context` and upgrade to callout card"))
                return issues
            if labels == ["Context","Definition","Example","IPA","YouGlish"]:
                issues.append(_issue("info_table_playphrase", "INFO", True, "PROPOSAL: card without PlayPhrase row — rebuild the card to add it and upgrade to callout card"))
                return issues
            issues.append(_issue("info_table_rows", "INFO", True, f"PROPOSAL: legacy table rows — {', '.join(labels) or 'none'}"))
            return issues
        else:
            issues.append(_issue("info_table_rows", "ERROR", True, f"New cards must use the Obsidian card layout (Context callout, **Definition:**, **Example:**, **IPA:** • Lookup links)"))
            return issues

    # 3. Missing elements from card layout
    missing = []
    if "**Definition:**" not in block:
        missing.append("**Definition:**")
    if "**Example:**" not in block:
        missing.append("**Example:**")
    if "**IPA:**" not in block:
        missing.append("**IPA:**")
    if "[YouGlish]" not in block:
        missing.append("[YouGlish]")
    if "[PlayPhrase]" not in block:
        missing.append("[PlayPhrase]")
    issues.append(_issue("info_table_missing", sev, False, f"Info card missing elements: {', '.join(missing)}"))
    return issues

def check_frontmatter_order(fm_keys, legacy_ok: bool = False, type_v: str = ""):
    issues=[]
    is_idiom_or_phrase = type_v in ("Idiom", "Phrase")
    expected_order = FRONTMATTER_ORDER if is_idiom_or_phrase else [k for k in FRONTMATTER_ORDER if k != "playphrase"]
    if fm_keys == expected_order:
        return issues
    if legacy_ok:
        issues.append(_issue("frontmatter_order", "INFO", True, "PROPOSAL: legacy frontmatter order — rebuild the card to upgrade it to the canonical order"))
        return issues
    issues.append(_issue("frontmatter_order", "ERROR", True, f"frontmatter order must be {', '.join(expected_order)} — got {', '.join(fm_keys or [])}"))
    return issues

def check_summary(summary: str, definition: str = ""):
    issues=[]
    if not summary or not summary.strip():
        issues.append(_issue("summary_missing", "ERROR", False, "summary is required"))
        return issues
    s=summary.strip()
    if '"' in s or "\\" in s:
        issues.append(_issue("summary_quote_backslash", "ERROR", False, 'summary must not contain " or \\'))
    if re.search(r"[A-Za-z]", s):
        issues.append(_issue("summary_latin", "ERROR", False, "summary must be Arabic only, no Latin"))
    for ch in s:
        if ch in set(':;.!?—–-|؛؟'):
            issues.append(_issue("summary_punct", "ERROR", False, f"summary forbidden punctuation '{ch}'"))
            break
    wc=len(s.split())
    if wc>15:
        issues.append(_issue("summary_length", "ERROR", False, f"summary {wc} words >15"))
    # openings
    openings=["أنا فخور","أنا اتفاجئت","أنا انبهرت","عرفت إن"]
    for op in openings:
        if s.startswith(op):
            issues.append(_issue("summary_opening", "WARNING", False, f"summary opens with '{op}' — must state insight, not feelings (see adaptive_rules.md)"))
            break
    if definition and definition.strip() and s.strip() == definition.strip():
        issues.append(_issue("summary_repeats_definition", "WARNING", False, "summary must not repeat the definition"))
    # Check summary repeats definition more loosely? If summary contains definition verbatim, warn? Simple check
    if definition:
        def_low=definition.strip().lower()
        sum_low=s.lower()
        if def_low and def_low in sum_low and len(def_low)>5:
            # already handled exact, but warn for containment
            pass
    return issues

def check_arabic(arabic: str):
    issues=[]
    if not arabic or not arabic.strip():
        issues.append(_issue("arabic_missing", "ERROR", False, "arabic is required"))
    elif re.search(r"[A-Za-z]", arabic):
        issues.append(_issue("arabic_latin", "ERROR", False, "arabic must be Arabic script only"))
    return issues

def check_level(level: str, profiles: dict):
    issues=[]
    allowed={"A1","A2","B1","B2","C1","C2"}
    if level not in allowed:
        issues.append(_issue("level_invalid", "ERROR", True, f"level '{level}' must be one of {sorted(allowed)}"))
    elif level not in profiles.get("levels",{}):
        issues.append(_issue("level_not_in_profiles", "ERROR", False, f"level '{level}' not in profiles.json"))
    return issues

def check_example_profile(example: str, level: str, profiles: dict, is_new_or_changed: bool, fallback: str | None = None):
    issues=[]
    if not is_new_or_changed:
        return issues
    if not example or not example.strip():
        issues.append(_issue("example_missing", "ERROR", False, "example is required for new/changed"))
        return issues
    # Resolve profile (fallback handling already done by caller, but re-resolve)
    prof=profiles.get("levels",{}).get(level)
    if not prof:
        # fallback to default, but still check with default
        prof=profiles.get("levels",{}).get(profiles.get("_default","B1"))
        if not prof:
            return issues
    ex=example.strip()
    wc=len(ex.split())
    max_w=prof["example"]["max_words"]
    if wc>max_w:
        issues.append(_issue("example_too_long", "ERROR", False, f"example {wc} words > max {max_w} for {level}"))
    # first person
    # Use same logic as build_word
    low=ex.lower()
    allowed=["i can't","i don't","i'm","i've","i'd","i'll","my","i"]
    is_fp=False
    for a in sorted(allowed, key=len, reverse=True):
        al=a.lower()
        if low==al or low.startswith(al+" ") or low.startswith(al+"'") or low.startswith(al+"’"):
            if al=="i":
                if low=="i" or low.startswith("i "):
                    is_fp=True
                    break
                else:
                    continue
            if al=="my":
                if low=="my" or low.startswith("my ") or low.startswith("my'"):
                    is_fp=True
                    break
                else:
                    continue
            is_fp=True
            break
    if not is_fp:
        # check We/Our with fallback
        if (low.startswith("we ") or low=="we" or low.startswith("we'") or low.startswith("our ") or low=="our"):
            if fallback and str(fallback).strip():
                issues.append(_issue("example_we_fallback", "WARNING", False, f"We/Our allowed via fallback: {fallback.strip()}"))
                is_fp=True
            else:
                issues.append(_issue("example_not_first_person", "ERROR", False, f"example must be first person — got: {ex[:30]}"))
        else:
            issues.append(_issue("example_not_first_person", "ERROR", False, f"example must be first person — got: {ex[:30]}"))
    # contractions
    basic=[c.lower() for c in profiles["contraction_sets"]["basic"]]
    standard=[c.lower() for c in profiles["contraction_sets"]["standard"]]
    all_cons=basic+standard
    ceiling=prof["example"]["contractions"]
    allowed_cons=set(basic) if ceiling=="basic" else set(all_cons)
    for con in all_cons:
        if con in low and con not in allowed_cons:
            issues.append(_issue("example_contraction", "ERROR", False, f"contraction '{con}' not allowed for {level} ceiling {ceiling}"))
            break
    # slang
    slang_allowed=prof["example"]["slang"]
    if not slang_allowed:
        for term in profiles.get("slang_terms",[]):
            if re.search(rf"\b{re.escape(term.lower())}\b", low):
                issues.append(_issue("example_slang", "ERROR", False, f"slang '{term}' not allowed for {level}"))
                break
    # target
    target=prof["example"]["target_words"]
    if wc < target[0] or wc > target[1]:
        issues.append(_issue("example_target", "WARNING", False, f"example {wc} words outside target {target} for {level}"))
    # definition/situation length handled elsewhere but also check here? We'll handle in notes checks
    return issues

def inflected_forms(base: str):
    base_low=base.lower()
    forms={base_low}
    forms.add(base_low+"s")
    forms.add(base_low+"es")
    forms.add(base_low+"ed")
    forms.add(base_low+"ing")
    forms.add(base_low+"d")
    forms.add(base_low+"ies")
    # silent-e drop: if base ends in 'e' (but not 'ee'), drop it before vowel suffixes
    if base_low.endswith("e") and not base_low.endswith("ee") and len(base_low) > 2:
        stem=base_low[:-1]
        forms.add(stem+"ing")   # e.g. ruminate -> ruminating, love -> loving
        forms.add(stem+"ed")    # e.g. ruminate -> ruminated, love -> loved
        forms.add(stem+"er")    # e.g. love -> lover
        forms.add(stem+"ers")
    # y -> ies / ied: if base ends in consonant+y, replace y with ies/ied
    if len(base_low) >= 2 and base_low.endswith("y") and base_low[-2] not in "aeiou":
        stem=base_low[:-1]
        forms.discard(base_low+"ies")  # remove naive form
        forms.add(stem+"ies")   # e.g. rely -> relies
        forms.add(stem+"ied")   # e.g. rely -> relied
    # doubled final consonant (simple heuristic: if ends with single consonant after vowel, double)
    if len(base_low)>=2 and base_low[-1] not in "aeiou" and base_low[-2] in "aeiou":
        forms.add(base_low + base_low[-1] + "ed")
        forms.add(base_low + base_low[-1] + "ing")
        forms.add(base_low + base_low[-1] + "s")
    return forms

def check_target_word_in_example(word: str, example: str, example_form: str | None, type_v: str):
    issues=[]
    if not example or not example.strip():
        return issues
    clean_word = re.sub(r"\s*\([A-Za-z]+\)$", "", str(word)).strip()
    ex_low=example.lower()
    if example_form and str(example_form).strip():
        ef=str(example_form).strip().lower()
        if ef not in ex_low:
            issues.append(_issue("example_form_missing", "ERROR", False, f"example_form '{example_form}' not found in example"))
        return issues
    # For phrasal verbs / idioms, every content token must appear
    if type_v in ("Phrasal Verb", "Idiom"):
        tokens=[t for t in re.split(r"\s+", clean_word.strip()) if t]
        for tok in tokens:
            forms=inflected_forms(tok)
            # check if any form appears as word in example
            found=False
            for f in forms:
                if re.search(rf"\b{re.escape(f)}\b", ex_low):
                    found=True
                    break
            # also check base without inflection for idioms (e.g., "kick the bucket" -> "kick", "bucket")
            # For idioms, tokens include "the" which is stopword; we should skip stopwords like "the", "a", "an"
            if tok.lower() in ("the","a","an","to","in","on","at","for","with","of"):
                continue
            if not found:
                issues.append(_issue("target_word_missing", "ERROR", False, f"target token '{tok}' not found in example in any inflected form"))
                break
    else:
        # Single word: check any inflected form appears
        forms=inflected_forms(clean_word)
        found=False
        for f in forms:
            if re.search(rf"\b{re.escape(f)}\b", ex_low):
                found=True
                break
        if not found:
            issues.append(_issue("target_word_missing", "ERROR", False, f"example must contain target word '{clean_word}' in any inflected form"))
    return issues

def check_context_link(context: str, example: str, word: str, type_v: str):
    issues=[]
    if not context or not example:
        return issues
    clean_word = re.sub(r"\s*\([A-Za-z]+\)$", "", str(word)).strip()
    stopwords={"the","a","an","and","or","but","in","on","at","to","for","with","of","is","are","was","were","be","been","have","has","had","i","my","you","we","he","she","it","they","me","my","mine","our","your","his","her","its","their","this","that","these","those","as","by","from","about","into","through","after","before","under","over","again","further","then","once","here","there","when","where","why","how","all","any","both","each","few","more","most","other","some","such","no","nor","not","only","own","same","so","than","too","very","can","will","just","don","should","now"}
    def tokens(text, word, type_v):
        # remove target word inflections and stopwords, keep content tokens
        low=text.lower()
        # remove target word forms
        if type_v in ("Phrasal Verb","Idiom"):
            toks=[t for t in re.split(r"\s+", word.strip().lower()) if t not in ("the","a","an","to","in","on")]
            for tok in toks:
                for f in inflected_forms(tok):
                    low=re.sub(rf"\b{re.escape(f)}\b", " ", low)
        else:
            for f in inflected_forms(word):
                low=re.sub(rf"\b{re.escape(f)}\b", " ", low)
        words=re.findall(r"[a-z]+", low)
        return set(w for w in words if w not in stopwords and len(w)>2)
    s_toks=tokens(context, clean_word, type_v)
    e_toks=tokens(example, clean_word, type_v)
    if s_toks and e_toks and not (s_toks & e_toks):
        issues.append(_issue("context_example_link", "WARNING", False, "context may not describe the same moment as the example"))
    return issues

check_situation_link = check_context_link

def check_single_word_backticks(note_text: str, notes: dict, word: str):
    issues=[]
    clean_word = re.sub(r"\s*\([A-Za-z]+\)$", "", str(word)).strip()
    # Only prose fields, not list fields (word_family entries use backticks by design)
    prose_fields=["word_translations","example_translation","when_used","cultural_context","etymology","curiosity","second_meaning","synonym_contrast","common_mistakes","important_notes","additional_notes","try_it","grammar_note"]
    # Build allowed single words: target word inflections + synonyms/antonyms
    allowed=set()
    for f in inflected_forms(clean_word):
        allowed.add(f.lower())
    for lst_key in ("synonyms","antonyms"):
        lst=notes.get(lst_key)
        if lst:
            if isinstance(lst, list):
                for item in lst:
                    m=re.search(r"\[\[([^\]]+)\]\]|`([^`]+)`", str(item))
                    if m:
                        raw_w = m.group(1) or m.group(2)
                    else:
                        raw_w = str(item).strip().lstrip("- ")
                    w=raw_w.strip().lower().split()[0].strip(".,;:")
                    allowed.add(w)
            else:
                parts=re.split(r"[—\n]+", str(lst))
                for p in parts:
                    m=re.search(r"\[\[([^\]]+)\]\]|`([^`]+)`", p)
                    if m:
                        raw_w = m.group(1) or m.group(2)
                    else:
                        raw_w = p.strip().lstrip("- ")
                    w=raw_w.strip().lower().split()[0].strip(".,;:")
                    allowed.add(w)
    for field in prose_fields:
        val=notes.get(field)
        if not val or not isinstance(val, str):
            continue
        spans=re.findall(r"`([^`]+)`", val)
        for span in spans:
            span_stripped=span.strip()
            # Check if span is single English word
            if re.match(r"^[A-Za-z][A-Za-z']*$", span_stripped):
                low=span_stripped.lower()
                if low not in allowed:
                    issues.append(_issue("single_word_backtick", "WARNING", False, f"single-word span — wrap only what the learner should notice: `{span_stripped}` in {field}"))
    return issues

def check_backticks(note_text: str, profiles: dict):
    """Check backtick policy for the whole note text."""
    issues=[]
    # Extract frontmatter, headings, table cells
    # Frontmatter
    fm_match=re.match(r"^---\n(.*?)\n---\n", note_text, re.DOTALL)
    frontmatter=""
    body=note_text
    if fm_match:
        frontmatter=fm_match.group(1)
        body=note_text[fm_match.end():]
        if "`" in frontmatter:
            # Check if backtick inside frontmatter values (should be none)
            # Any backtick in frontmatter is error
            issues.append(_issue("backtick_in_frontmatter", "ERROR", True, "backtick in frontmatter value — not allowed"))
    # Headings
    for m in re.finditer(r"^##.*$", body, re.MULTILINE):
        line=m.group(0)
        if "`" in line:
            issues.append(_issue("backtick_in_heading", "ERROR", True, f"backtick in heading: {line[:40]}"))
    # Info table cells except IPA row
    # Find Info table rows
    info_match=re.search(r"##.*Info\n\n(.*?)\n\n---", body, re.DOTALL)
    if info_match:
        table=info_match.group(1)
        for row in table.splitlines():
            if "`" in row and "**IPA:**" not in row and "IPA" not in row:
                if re.search(r"\|\s*IPA\s*\|", row):
                    continue
                issues.append(_issue("backtick_in_table", "ERROR", True, f"backtick in Info section other than IPA: {row[:50]}"))

    formatting=profiles.get("formatting",{})
    plain_terms=[t.lower() for t in formatting.get("plain_terms",[])]
    max_per_para=formatting.get("backticks_max_per_paragraph",4)

    # Paragraphs: split body by blank lines (double newline) and also treat table rows as not paragraphs? For backtick count, treat each Notes paragraph as one
    # Extract Notes block
    notes_match=re.search(r"##.*Notes\n\n(.*?)\n\n---", body, re.DOTALL)
    notes_body=""
    if notes_match:
        notes_body=notes_match.group(1)
        paragraphs=[p.strip() for p in notes_body.split("\n\n") if p.strip()]
    else:
        paragraphs=[p for p in body.split("\n\n") if p.strip()]

    # TASK 5-FIX: density rules (max spans per paragraph, same-span-twice) apply
    # ONLY to prose note fields. Structural lists carry one span per item by
    # design — that is not the "wrapping ordinary words" problem. All other
    # rules (plain_terms, mixed Arabic, unwrapped phrase, frontmatter/heading/
    # table ERRORs) still apply everywhere.
    _STRUCTURAL_PARAS={"من نفس الأصل","مرادفات","أضداد","أمثلة شائعة"}
    def _para_is_structural(para: str) -> bool:
        m=re.match(r"^\*\*(.*?)\*\*", para.strip())
        if m:
            return m.group(1).strip().rstrip(":").rstrip("؟") in _STRUCTURAL_PARAS
        # Callout form: "> [!example] أمثلة شائعة" / "> [!info] مرادفات"
        m_c=re.match(r"^>\s*\[!([a-zA-Z]+)\]\s*(.*)$", para.strip())
        if m_c:
            title=m_c.group(2).strip().rstrip(":").rstrip("؟")
            return title in _STRUCTURAL_PARAS
        return False

    for para in paragraphs:
        # Count spans
        spans=re.findall(r"`([^`]+)`", para)
        structural=_para_is_structural(para)
        if not structural and len(spans) > max_per_para:
            issues.append(_issue("backticks_too_many", "WARNING", False, f"{len(spans)} backtick spans > max {max_per_para} in paragraph: {para[:40]}"))
        # Check each span
        seen=set()
        for span in spans:
            norm=span.strip().lower()
            # plain_terms warning
            if norm in plain_terms or span.strip() in formatting.get("plain_terms",[]):
                issues.append(_issue("backtick_plain_term", "WARNING", False, f"span `{span}` is in plain_terms — do not wrap"))
            # duplicate same span twice in one paragraph (prose only)
            if norm in seen:
                if not structural:
                    issues.append(_issue("backtick_duplicate", "WARNING", False, f"same span `{span}` twice in one paragraph"))
            else:
                seen.add(norm)
            # Arabic inside backticks
            if re.search(r"[\u0600-\u06FF]", span):
                issues.append(_issue("backtick_mixed_arabic", "WARNING", False, f"span `{span}` mixes Arabic and English"))
        if structural:
            continue
        # Natural English phrases inside Arabic explanations are allowed unwrapped
        # without backticks to avoid backtick clutter and monospace overload.

    return issues

def _notes_text(v) -> str:
    """Flatten a notes value (str, list of str, list of dicts) to plain text for length/overlap checks."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        parts=[]
        for x in v:
            if x is None:
                continue
            if isinstance(x, dict):
                parts.append(" ".join(str(x.get(k,"")) for k in ("form","type","arabic","example")))
            else:
                parts.append(str(x))
        return " — ".join(p for p in parts if p.strip())
    if isinstance(v, dict):
        return " ".join(str(v.get(k,"")) for k in ("form","type","arabic","example"))
    return str(v)

def _count_entries(v) -> int:
    """Count structural entries: list length, or non-empty lines / ' — ' parts for parsed strings."""
    if v is None:
        return 0
    if isinstance(v, (list, tuple)):
        return len([x for x in v if (str(x).strip() if not isinstance(x, dict) else True)])
    if isinstance(v, str):
        s=v.strip()
        if not s:
            return 0
        lines=[l for l in s.splitlines() if l.strip()]
        if len(lines) > 1:
            return len(lines)
        return len([p for p in s.split(" — ") if p.strip()])
    return 1 if str(v).strip() else 0

def check_common_examples(notes: dict, word: str):
    """Common examples must be full everyday sentences using the target word.

    A two-word collocation ("mitigate risk") teaches the pattern but not the
    usage; a full sentence ("We mitigate the risk before we launch.") is what
    the learner actually hears and repeats.
    """
    issues=[]
    raw=notes.get("common_examples")
    if not raw:
        return issues
    items = raw if isinstance(raw,(list,tuple)) else [raw]
    clean_word = re.sub(r"\s*\([A-Za-z]+\)$", "", str(word)).strip()
    forms = set()
    for tok in clean_word.split():
        if tok.lower() in ("the","a","an","to","in","on","at","for","with","of"):
            continue
        forms.update(inflected_forms(tok))
    for item in items:
        s=str(item or "").strip()
        if not s:
            continue
        if s.startswith("- "):
            s=s[2:].strip()
        plain=s.replace("==","")
        wc=len(plain.split())
        if wc < 4:
            issues.append(_issue("examples_too_short", "WARNING", False,
                                 f"[examples_too_short] common_examples entry is a collocation, not a full sentence: \"{plain[:50]}\" — write the everyday sentence"))
        if forms and not any(re.search(rf"\b{re.escape(f)}\b", plain.lower()) for f in forms):
            issues.append(_issue("examples_target_missing", "WARNING", False,
                                 f"[examples_target_missing] common_examples entry does not use the target word '{clean_word}': \"{plain[:50]}\""))
    return issues

def check_family_cap(notes: dict, profiles: dict, level: str):
    issues=[]
    prof=profiles.get("levels",{}).get(level) or profiles.get("levels",{}).get(profiles.get("_default","B1"))
    if not prof:
        return issues
    cap=prof["notes"].get("family_max")
    if cap is None:
        return issues
    n=_count_entries(notes.get("word_family"))
    if n > cap:
        issues.append(_issue("family_max", "WARNING", False, f"{n} word_family entries > family_max {cap} for {level}"))
    return issues

def check_collocations_cap(notes: dict, profiles: dict, level: str):
    issues=[]
    prof=profiles.get("levels",{}).get(level) or profiles.get("levels",{}).get(profiles.get("_default","B1"))
    if not prof:
        return issues
    cap=prof["notes"].get("collocations_max")
    if cap is None:
        return issues
    n=_count_entries(notes.get("common_examples"))
    if n > cap:
        issues.append(_issue("collocations_max", "WARNING", False, f"{n} common_examples entries > collocations_max {cap} for {level}"))
    return issues

def check_notes_count(notes: dict, profiles: dict, level: str):
    issues=[]
    prof=profiles.get("levels",{}).get(level) or profiles.get("levels",{}).get(profiles.get("_default","B1"))
    if not prof:
        return issues
    extras_max=prof["notes"]["extras_max"]
    # Count non-empty note fields excluding core translations AND structural lists
    # (word_family capped by family_max, common_examples capped by collocations_max).
    # synonym_contrast IS a prose note and counts toward extras_max.
    structural={"word_translations","example_translation","word_family","common_examples"}
    # Determine if try_it was dropped by profile (caller should have removed it)
    count=0
    for k,v in notes.items():
        if k in structural:
            continue
        if v is None:
            continue
        if isinstance(v, list):
            if len([x for x in v if (str(x).strip() if not isinstance(x, dict) else True)])==0:
                continue
        elif isinstance(v, str):
            if not v.strip():
                continue
        else:
            if not str(v).strip():
                continue
        count+=1
    if count > extras_max:
        issues.append(_issue("extras_max", "WARNING", False, f"{count} non-core notes > extras_max {extras_max} for {level}"))
    return issues

def check_short_and_overlap(notes: dict):
    issues=[]
    # Short note <3 words — exclude core translations which are naturally short
    for k,v in notes.items():
        if k in ("word_translations", "example_translation"):
            continue
        if v is None:
            continue
        txt=_notes_text(v)
        if not txt.strip():
            continue
        wc=len(txt.split())
        if wc < 3:
            issues.append(_issue("note_too_short", "WARNING", False, f"notes.{k} has {wc} words <3"))
    # Overlap >80% tokens between any two notes — exclude core (includes synonym_contrast
    # vs common_mistakes idea-duplication check per TASK 5 §4)
    keys=[k for k in notes.keys() if k not in ("word_translations", "example_translation")]
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            ki=keys[i]; kj=keys[j]
            vi=notes.get(ki); vj=notes.get(kj)
            if vi is None or vj is None:
                continue
            ti=_notes_text(vi).lower().split()
            tj=_notes_text(vj).lower().split()
            if not ti or not tj:
                continue
            # Jaccard or overlap: count common tokens / max len?
            set_i=set(ti); set_j=set(tj)
            inter=set_i & set_j
            # overlap by tokens: len(inter) / max(len(set_i), len(set_j))
            max_len=max(len(set_i), len(set_j))
            overlap=len(inter)/max_len if max_len else 0
            if overlap>0.8:
                issues.append(_issue("notes_overlap", "WARNING", False, f"notes.{ki} and {kj} overlap {overlap*100:.0f}% tokens"))
    return issues

def check_hook(notes: dict, type_v: str = ""):
    """Etymology is never used (omit always). Hooks are: curiosity or common_mistakes."""
    issues=[]
    has_hook=False
    for hook in ("curiosity", "common_mistakes"):
        v=notes.get(hook)
        if v is not None and not (isinstance(v, str) and not v.strip()) and not (isinstance(v, list) and len([x for x in v if str(x).strip()])==0):
            has_hook=True
            break
    if not has_hook:
        issues.append(_issue("hook_missing", "ERROR", False, "at least one hook is required: curiosity or common_mistakes"))
    if type_v in ("Phrasal Verb", "Idiom"):
        gn=notes.get("grammar_note")
        if gn is None or (isinstance(gn, str) and not gn.strip()) or (isinstance(gn, list) and len([x for x in gn if str(x).strip()])==0):
            issues.append(_issue("grammar_note_missing", "ERROR", False, f"grammar_note required when type is '{type_v}'"))
    return issues

def check_all(note_text: str, notes: dict, level: str, profiles: dict, example: str = "", is_new_or_changed: bool = True, fallback: str = None, type_v: str = "", word: str = "", example_form: str | None = None, situation: str = "", context: str = "", legacy_ok: bool = False, category: str = "", category_v: str = ""):
    type_v = category or category_v or type_v
    """Run all checks and return list of issues.

    legacy_ok=True is for EXISTING notes (audit / --check): missing `youglish` and the
    legacy frontmatter shape are reported as INFO upgrade proposals instead of ERRORs.
    """
    issues=[]
    # Frontmatter order
    fm_match=re.match(r"^---\n(.*?)\n---\n", note_text, re.DOTALL)
    if not type_v and fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                if k.strip() in ("category", "type"):
                    type_v = v.strip().strip('"')
                    break
    if fm_match:
        fm=fm_match.group(1)
        keys=[l.split(":")[0].strip() for l in fm.splitlines() if ":" in l]
        issues.extend(check_frontmatter_order(keys, legacy_ok, type_v))
    # Check level
    issues.extend(check_level(level, profiles))
    # Check arabic and link properties (summary removed)
    if fm_match:
        fm_dict={}
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k,v=line.split(":",1)
                fm_dict[k.strip()]=v.strip().strip('"').replace('\\"','"').replace('\\\\','\\')
        issues.extend(check_arabic(fm_dict.get("arabic","")))
        issues.extend(check_chunks(fm_dict, word or "", legacy_ok))
        issues.extend(check_definition(fm_dict, legacy_ok))
        issues.extend(check_youglish(fm_dict, word or "", legacy_ok))
        issues.extend(check_playphrase(fm_dict, word or "", type_v, legacy_ok))
        issues.extend(check_pronunciation_voice(fm_dict, word or "", legacy_ok))
        issues.extend(check_image(fm_dict, word or "", legacy_ok))
    # Card head: Info table labels (Context, not the legacy Situation)
    issues.extend(check_info_table(note_text, legacy_ok, type_v))
    # Hook and grammar_note
    issues.extend(check_hook(notes, type_v))
    # Example profile
    issues.extend(check_example_profile(example, level, profiles, is_new_or_changed, fallback))
    # Target word in example (2.1)
    if is_new_or_changed:
        issues.extend(check_target_word_in_example(word or "", example, example_form, type_v))
        # Context/Situation link (2.2)
        ctx = context or situation
        if ctx:
            issues.extend(check_context_link(ctx, example, word or "", type_v))
    # Backticks (general)
    issues.extend(check_backticks(note_text, profiles))
    # Arabic text direction: no line in the Notes block may start with Latin text
    issues.extend(check_rtl_line_start(note_text, blocking=not legacy_ok))
    # Single-word backtick prose (2.3)
    issues.extend(check_single_word_backticks(note_text, notes, word or ""))
    # Notes count (extras_max excludes structural word_family / common_examples)
    issues.extend(check_notes_count(notes, profiles, level))
    # Structural caps
    issues.extend(check_family_cap(notes, profiles, level))
    issues.extend(check_collocations_cap(notes, profiles, level))
    # Common examples must be full everyday sentences using the target word
    issues.extend(check_common_examples(notes, word or ""))
    # Short and overlap
    issues.extend(check_short_and_overlap(notes))
    return issues

def as_proposals(issues: list, extra_note: str = ""):
    """Downgrade PROPOSAL_CODES findings to INFO proposals for existing notes.

    Used by build_word.py --check and audit_vault.py so both report the same
    severity for the same finding — one implementation, no drift.
    """
    out=[]
    for iss in issues:
        if iss["code"] in PROPOSAL_CODES and iss["severity"] != "INFO":
            iss2=dict(iss)
            iss2["severity"]="INFO"
            msg=str(iss["message"])
            if not msg.startswith("PROPOSAL: "):
                msg="PROPOSAL: "+msg
            iss2["message"]=msg+extra_note
            out.append(iss2)
        else:
            out.append(iss)
    return out
