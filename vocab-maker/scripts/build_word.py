#!/usr/bin/env python3
"""build_word.py — orchestration for vocab-maker."""
import argparse, json, re, shutil, sys, tempfile
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocab_audio, vocab_checks, vocab_io, vocab_profiles
ALLOWED_CATEGORIES={"Noun","Verb","Adjective","Adverb","Phrasal Verb","Idiom","Phrase","Preposition","Conjunction","Pronoun","Determiner","Interjection"}
ALLOWED_TYPES=ALLOWED_CATEGORIES

def resolve_category(cat_raw, type_raw, warnings=None):
    """Pick the real part of speech from `category` / `type`.

    Legacy cards often carry a placeholder `category: Vocabulary` next to a
    correct `type: Adverb` (or the reverse). A placeholder `category: Noun`
    is also treated as unset when `type` says something more specific.
    """
    cat = (cat_raw or "").strip()
    typ = (type_raw or "").strip()
    if cat == "Noun" and typ and typ != "Noun" and typ in ALLOWED_CATEGORIES:
        return typ
    if cat in ALLOWED_CATEGORIES:
        return cat
    if typ in ALLOWED_CATEGORIES:
        if cat and warnings is not None:
            warnings.append(f"category '{cat}' is not a valid category — using type '{typ}'")
        return typ
    return cat or typ

def handle_show_profile(args):
    profiles=vocab_profiles.load_profiles(args.profiles)
    warnings=[]; lvl=args.show_profile.strip()
    prof=vocab_profiles.resolve_profile(lvl, profiles, warnings)
    out={"level":lvl,"resolved_level":lvl if lvl in profiles["levels"] else profiles["_default"],"profile":prof,"formatting":profiles.get("formatting",{}),"warnings":warnings}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    return 0

def handle_check(args):
    if not args.word:
        print("ERROR: --check requires --word X", file=sys.stderr)
        return 1
    profiles=vocab_profiles.load_profiles(args.profiles)
    try:
        vault_root,_=vocab_profiles.load_config(args.vault_root)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    try:
        word=vocab_io.normalize_word(str(args.word))
    except Exception as e:
        print(f"ERROR: invalid word: {e}", file=sys.stderr)
        return 1
    char=vocab_io.base_word(word)[0].upper()
    note_path=Path(vault_root)/"Vocabulary"/char/f"{word}.md"
    if not note_path.exists():
        print(f"ERROR: note not found: {note_path}", file=sys.stderr)
        return 1
    note_text=note_path.read_text(encoding="utf-8")
    fm=vocab_io.parse_frontmatter(note_path)
    level=fm.get("level",""); example=fm.get("example",""); category_v=resolve_category(fm.get("category",""), fm.get("type",""))
    type_v=category_v
    notes = vocab_io.extract_notes_dict(note_text, word)
    info_fields = vocab_io.extract_info_fields(note_text, word)
    context = info_fields.get("context", "")
    # is_new_or_changed=True so example findings are actually produced, then downgraded
    # to INFO proposals below — existing notes are never failed for a profile-mismatched example.
    issues=vocab_checks.check_all(note_text, notes, level, profiles, example, is_new_or_changed=True, fallback=None, type_v=type_v, word=word, example_form=None, context=context, situation=context, legacy_ok=True)
    out=vocab_checks.as_proposals(issues, " (fix only if the meaning is unclear or profile rules are violated)")
    if not out:
        print("No issues found.")
    else:
        for iss in out:
            print(json.dumps(iss, ensure_ascii=False))
    print(f"Checked {note_path} — {len(out)} issues")
    return 0

def handle_touch_word(args):
    if not args.word or args.json or args.json_file:
        return None
    profiles=vocab_profiles.load_profiles(args.profiles)
    try:
        vault_root,_=vocab_profiles.load_config(args.vault_root)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    try:
        word=vocab_io.normalize_word(str(args.word))
    except Exception as e:
        print(f"ERROR: invalid word: {e}", file=sys.stderr)
        return 1
    char=vocab_io.base_word(word)[0].upper()
    note_path=Path(vault_root)/"Vocabulary"/char/f"{word}.md"
    if not note_path.exists():
        print(f"ERROR: note not found: {note_path}", file=sys.stderr)
        return 1
    fm=vocab_io.parse_frontmatter(note_path)
    ec=fm.get("created",""); es=fm.get("status",""); er=fm.get("review",""); eo=fm.get("order","")
    today=date.today().isoformat(); today_day=date.today().strftime("%A"); today_month=date.today().strftime("%B")
    if ec:
        try:
            cd=date.fromisoformat(ec); created=ec; day=cd.strftime("%A"); month=cd.strftime("%B")
        except Exception:
            created=today; day=today_day; month=today_month
    else:
        created=today; day=today_day; month=today_month
    order=eo
    if args.maintenance:
        modified=today; review=er or created; status=es or "Not Started"
    else:
        modified=today; review=today
        if es=="Done":
            status="In Progress"
        elif es in ("In Progress","Not Started"):
            status=es
        else:
            status=es or "Not Started"
    if args.dry_run:
        print(f"[dry-run] would touch {note_path}: review={review}, modified={modified}, status={status}, created={created}")
        print(f'RESULT: {json.dumps({"word":word,"note":str(note_path),"created":False,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":[],"profile_level":fm.get("level",""),"audio_rate":""})}')
        return 0
    content=note_path.read_text(encoding="utf-8")
    content=re.sub(r"^day:.*$", f"day: {day}", content, flags=re.MULTILINE, count=1)
    # Also upgrade legacy created_day key on old notes
    content=re.sub(r"^created_day:.*$", f"day: {day}", content, flags=re.MULTILINE, count=1)
    content=re.sub(r"^created:.*$", f"created: {created}", content, flags=re.MULTILINE, count=1)
    content=re.sub(r"^modified:.*$", f"modified: {modified}", content, flags=re.MULTILINE, count=1)
    content=re.sub(r"^review:.*$", f"review: {review}", content, flags=re.MULTILINE, count=1)
    content=re.sub(r"^month:.*$", f"month: {month}", content, flags=re.MULTILINE, count=1)
    content=re.sub(r"^status:.*$", f"status: {status}", content, flags=re.MULTILINE, count=1)
    content=re.sub(r"^char:.*$", f"char: {char}", content, flags=re.MULTILINE, count=1)
    with open(note_path,"w",encoding="utf-8") as f:
        f.write(content)
    print(f"[touch] updated {note_path}: review={review}, modified={modified}, status={status}")
    result={"word":word,"note":str(note_path),"created":False,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":[],"profile_level":fm.get("level",""),"audio_rate":""}
    print(f"RESULT: {json.dumps(result, ensure_ascii=False)}")
    return 0

def validate_payload(payload, profiles, warnings, is_new, existing_example, args):
    level_raw=str(payload.get("level","")).strip()
    if not level_raw:
        warnings.append(f"level missing — falling back to _default '{profiles['_default']}'")
        level=profiles["_default"]
    else:
        if level_raw not in {"A1","A2","B1","B2","C1","C2"}:
            raise ValueError(f"level '{level_raw}' is invalid — must be one of A1, A2, B1, B2, C1, C2.")
        level=level_raw
        if level not in profiles["levels"]:
            warnings.append(f"level '{level}' not in profiles — falling back to _default '{profiles['_default']}'")
            level=profiles["_default"]
    profile=vocab_profiles.resolve_profile(level, profiles, warnings)
    ctx_max = profile.get("context", {}).get("max_words") or profile.get("situation", {}).get("max_words", 50)
    applied={"example_max_words":profile["example"]["max_words"],"example_target_words":profile["example"]["target_words"],"example_contractions":profile["example"]["contractions"],"example_slang":profile["example"]["slang"],"definition_max_words":profile["definition"]["max_words"],"context_max_words":ctx_max,"situation_max_words":ctx_max,"audio_rate":profile["audio"]["rate"],"notes_max_sentences_per_note":profile["notes"]["max_sentences_per_note"],"notes_extras_max":profile["notes"]["extras_max"],"notes_try_it":profile["notes"]["try_it"],"notes_family_max":profile["notes"].get("family_max"),"notes_collocations_max":profile["notes"].get("collocations_max")}
    effective_rate=args.rate if args.rate else profile["audio"]["rate"]
    cat_raw=str(payload.get("category","")).strip()
    type_raw=str(payload.get("type","")).strip()
    category_v=resolve_category(cat_raw, type_raw, warnings)
    type_v=category_v
    if not category_v:
        raise ValueError(f"category is required — must be one of {sorted(ALLOWED_CATEGORIES)}")
    if category_v not in ALLOWED_CATEGORIES:
        if args.maintenance:
            warnings.append(f"category '{category_v}' not in allowed list {sorted(ALLOWED_CATEGORIES)} — maintenance mode: warning only")
        else:
            raise ValueError(f"category '{category_v}' is invalid — must be one of {sorted(ALLOWED_CATEGORIES)} (case-sensitive).")
    arabic_raw = payload.get("arabic", "")
    if isinstance(arabic_raw, (list, tuple)):
        arabic = " - ".join(str(x).strip() for x in arabic_raw if str(x).strip())
    else:
        arabic = str(arabic_raw or "").strip()
    summary=str(payload.get("summary","")).strip()
    definition=str(payload.get("definition","")).strip()
    if not definition:
        raise ValueError("definition is required — must be a short sentence.")
    ipa=str(payload.get("ipa","")).strip()
    if not ipa:
        raise ValueError("ipa is required.")
    context=str(payload.get("context") or payload.get("situation") or "").strip()
    if not context:
        raise ValueError("context is required.")
    notes=payload.get("notes")
    if not isinstance(notes, dict):
        raise ValueError("notes is required and must be an object.")
    for req in ("word_translations","example_translation"):
        v=notes.get(req)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and len([x for x in v if str(x).strip()])==0):
            raise ValueError(f"notes.{req} is required — must not be empty.")
    has_hook=False
    for hook in ("curiosity","common_mistakes"):
        v=notes.get(hook)
        if v is not None and not (isinstance(v, str) and not v.strip()) and not (isinstance(v, list) and len([x for x in v if str(x).strip()])==0):
            has_hook=True
            break
    if not has_hook:
        raise ValueError("at least one hook is required: curiosity or common_mistakes")
    if type_v in ("Phrasal Verb","Idiom"):
        gn=notes.get("grammar_note")
        if gn is None or (isinstance(gn, str) and not gn.strip()) or (isinstance(gn, list) and len([x for x in gn if str(x).strip()])==0):
            raise ValueError(f"notes.grammar_note is required when type is '{type_v}' — must not be empty.")
    if notes.get("try_it") and not profile["notes"]["try_it"]:
        warnings.append(f"try_it dropped — profile for {level} has try_it false")
        notes=dict(notes)
        notes.pop("try_it", None)
        payload["notes"]=notes
    # TASK 5 §2: word_family entries — each needs form, closed-list type, arabic, example
    fam=notes.get("word_family")
    if fam is not None:
        entries=fam if isinstance(fam, (list, tuple)) else [fam]
        if not isinstance(fam, (list, tuple)):
            raise ValueError("notes.word_family must be a list of {form, type, arabic, example}")
        for e in entries:
            if not isinstance(e, dict):
                raise ValueError("notes.word_family entries must be objects {form, type, arabic, example}")
            for req in ("form","type","arabic","example"):
                v=e.get(req)
                if v is None or not str(v).strip():
                    raise ValueError(f"notes.word_family entry missing required '{req}': {e}")
            if str(e.get("type","")).strip() not in ALLOWED_TYPES:
                raise ValueError(f"notes.word_family entry type '{e.get('type')}' is invalid — must be one of {sorted(ALLOWED_TYPES)} (case-sensitive).")
    for iss in vocab_checks.check_arabic(arabic):
        if iss["severity"]=="ERROR":
            raise ValueError(iss["message"])
    payload_example_raw=payload.get("example")
    payload_example=None
    if payload_example_raw is not None:
        payload_example=str(payload_example_raw).strip()
        if payload_example=="":
            payload_example=None
    need=False
    if is_new:
        if not payload_example:
            raise ValueError("example is required for new words.")
        need=True
    else:
        if payload_example is None:
            payload_example=existing_example
            if not payload_example:
                raise ValueError("existing note has no example and payload has no example — cannot reuse.")
            need=False
        elif payload_example != existing_example:
            if not args.change_example:
                print(f"ERROR: example differs from existing note (existing: \"{existing_example}\", payload: \"{payload_example}\") — pass --change-example to update.", file=sys.stderr)
                return None
            need=True
        else:
            need=False
    if need:
        ex=payload_example
        assert ex is not None
        issues=[]
        issues.extend(vocab_checks.check_example_profile(ex, level, profiles, True, payload.get("example_person_fallback")))
        issues.extend(vocab_checks.check_target_word_in_example(payload.get("word",""), ex, payload.get("example_form"), type_v))
        for iss in issues:
            if iss["severity"]=="ERROR":
                raise ValueError(iss["message"])
            else:
                warnings.append(iss["message"])
        for iss in vocab_checks.check_context_link(context, ex, payload.get("word",""), type_v):
            warnings.append(iss["message"])
        if len(definition.split()) > profile["definition"]["max_words"]:
            warnings.append(f"definition {len(definition.split())} words exceeds max {profile['definition']['max_words']} for {level}")
        ctx_limit = profile.get("context", {}).get("max_words") or profile.get("situation", {}).get("max_words", 50)
        if len(context.split()) > ctx_limit:
            warnings.append(f"context {len(context.split())} words exceeds max {ctx_limit} for {level}")
        for iss in vocab_checks.check_notes_count(notes, profiles, level):
            warnings.append(iss["message"])
        for iss in vocab_checks.check_family_cap(notes, profiles, level):
            warnings.append(iss["message"])
        for iss in vocab_checks.check_collocations_cap(notes, profiles, level):
            warnings.append(iss["message"])
        for iss in vocab_checks.check_common_examples(notes, payload.get("word","")):
            warnings.append(iss["message"])
        for iss in vocab_checks.check_short_and_overlap(notes):
            warnings.append(iss["message"])
        for iss in vocab_checks.check_single_word_backticks("", notes, payload.get("word","")):
            warnings.append(iss["message"])
    return level, profile, applied, effective_rate, payload_example, need

def handle_add_family_member(args):
    # TASK 5 §6 mechanics: agent has decided typed word routes to this root.
    # Adds/confirms one word_family entry, refreshes modified/review (touch-only path).
    if not getattr(args, "add_family_member", False):
        return None
    profiles=vocab_profiles.load_profiles(args.profiles)
    try:
        vault_root,_=vocab_profiles.load_config(args.vault_root)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if not args.word:
        print("ERROR: --add-family-member requires --word ROOT", file=sys.stderr)
        return 1
    if not getattr(args, "family_json", None):
        print("ERROR: --add-family-member requires --family-json '{\"form\":...,\"type\":...,\"arabic\":...,\"example\":...}'", file=sys.stderr)
        return 1
    try:
        root=vocab_io.normalize_word(str(args.word))
    except Exception as e:
        print(f"ERROR: invalid word: {e}", file=sys.stderr)
        return 1
    try:
        entry=json.loads(args.family_json)
    except Exception as e:
        print(f"ERROR: invalid --family-json: {e}", file=sys.stderr)
        return 1
    if not isinstance(entry, dict):
        print("ERROR: --family-json must be an object {form, type, arabic, example}", file=sys.stderr)
        return 1
    for req in ("form","type","arabic","example"):
        if entry.get(req) is None or not str(entry.get(req)).strip():
            print(f"ERROR: family entry missing required '{req}': {entry}", file=sys.stderr)
            return 1
    if str(entry.get("type","")).strip() not in ALLOWED_TYPES:
        print(f"ERROR: family entry type '{entry.get('type')}' is invalid — must be one of {sorted(ALLOWED_TYPES)} (case-sensitive).", file=sys.stderr)
        return 1
    char=vocab_io.base_word(root)[0].upper()
    note_path=Path(vault_root)/"Vocabulary"/char/f"{root}.md"
    if not note_path.exists():
        print(f"ERROR: root note not found: {note_path} — create the ROOT note first", file=sys.stderr)
        return 1
    fm=vocab_io.parse_frontmatter(note_path)
    level=fm.get("level","") or profiles.get("_default","B1")
    prof=profiles.get("levels",{}).get(level, {})
    family_max=(prof.get("notes") or {}).get("family_max")
    warnings=[]
    content=note_path.read_text(encoding="utf-8")
    # Reconstruct the full note fields from disk and re-render through the SAME
    # renderer as a normal build (vocab_io.render_note) — no separate splice path.
    info_fields = vocab_io.extract_info_fields(content, root)
    if not info_fields:
        print(f"ERROR: Info block not found in {note_path}", file=sys.stderr)
        return 1
    definition = info_fields.get("definition", "")
    context = info_fields.get("context", "")
    ipa = info_fields.get("ipa", "")
    notes = vocab_io.extract_notes_dict(content, root)
    # word_family back to a data list so render_note draws it canonically
    fam_entries=[]
    if notes.get("word_family"):
        for ln in str(notes["word_family"]).splitlines():
            ln=ln.strip()
            if not ln:
                continue
            m=re.match(r"^`([^`]+)`\s*\(([^)]+)\):\s*(.*?)\s*\u2014\s*`(.*)`$", ln)
            if m:
                fam_entries.append({"form":m.group(1).strip(),"type":m.group(2).strip(),"arabic":m.group(3).strip(),"example":m.group(4).strip()})
            else:
                m_wiki=re.match(r"^-\s*\[\[([^\]]+)\]\]$", ln)
                if m_wiki:
                    fam_entries.append({"form": m_wiki.group(1).strip()})
                else:
                    fam_entries.append(ln)
    def _fam_form(e):
        if isinstance(e, dict):
            return str(e.get("form","")).strip()
        m=re.match(r"^`([^`]+)`\s*\(", str(e).strip())
        if m:
            return m.group(1).strip()
        m_wiki=re.match(r"^-\s*\[\[([^\]]+)\]\]$", str(e).strip())
        if m_wiki:
            return m_wiki.group(1).strip()
        m_wiki2=re.match(r"^\[\[([^\]]+)\]\]$", str(e).strip())
        if m_wiki2:
            return m_wiki2.group(1).strip()
        return str(e).strip()
    known_low=[_fam_form(e).lower() for e in fam_entries if _fam_form(e)]
    new_form=str(entry["form"]).strip()
    action="confirmed"
    if new_form.lower() in known_low:
        warnings.append(f"family form '{new_form}' already present under {root} — confirmed")
    else:
        replace=getattr(args, "replace_form", None)
        if replace:
            rl=str(replace).strip().lower()
            if rl in known_low:
                fam_entries=[e for e in fam_entries if _fam_form(e).lower() != rl]
                warnings.append(f"family form '{replace}' replaced by '{new_form}' (at cap, weakest removed per agent judgment)")
            else:
                warnings.append(f"--replace-form '{replace}' not found under {root} — appending '{new_form}'")
        fam_entries.append({"form":new_form,"type":str(entry["type"]).strip(),"arabic":str(entry["arabic"]).strip(),"example":str(entry["example"]).strip()})
        action="added"
    notes["word_family"]=fam_entries
    total=len(fam_entries)
    if family_max is not None and total > family_max:
        warnings.append(f"{total} word_family entries > family_max {family_max} for {level}")
    # Touch dates via touch-only path (review reset because the word needed remembering)
    today=date.today().isoformat()
    ec=fm.get("created",""); es=fm.get("status",""); eo=fm.get("order","")
    if ec:
        try:
            cd=date.fromisoformat(ec); created=ec; day=cd.strftime("%A"); month=cd.strftime("%B")
        except Exception:
            created=today; day=date.today().strftime("%A"); month=date.today().strftime("%B")
    else:
        created=today; day=date.today().strftime("%A"); month=date.today().strftime("%B")
    modified=today; review=today
    if es=="Done":
        status="In Progress"
    elif es in ("In Progress","Not Started"):
        status=es
    else:
        status=es or "Not Started"
    order=eo
    if args.dry_run:
        print(f"[dry-run] would {action} family form '{new_form}' under {root} ({note_path}): review={review}, modified={modified}, status={status}")
        print(f'RESULT: {json.dumps({"word":root,"note":str(note_path),"created":False,"routed":True,"family_action":action,"family_form":new_form,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":warnings,"profile_level":level,"audio_rate":""})}')
        return 0
    try:
        fields={"char":char,"category":resolve_category(fm.get("category",""), fm.get("type","")),"subject":"Vocabulary","level":level,"definition":definition,"arabic":fm.get("arabic",""),"context":context,"situation":context,"example":fm.get("example",""),"ipa":ipa,"chunks":fm.get("chunks") if fm.get("chunks") is not None else vocab_io.auto_chunk_word(root),"status":status,"created":created,"day":day,"modified":modified,"review":review,"month":month,"notes":notes}
        rendered=vocab_io.render_note(root, fields)
    except Exception as e:
        print(f"ERROR: render failed: {e}", file=sys.stderr)
        return 1
    with open(note_path,"w",encoding="utf-8") as f:
        f.write(rendered)
    typed=new_form
    print(f"[family] {action} '{typed}' under root {root} — already covered under {root}; see {root}'s note. ({note_path}: review={review}, modified={modified}, status={status})")
    result={"word":root,"note":str(note_path),"created":False,"routed":True,"family_action":action,"family_form":new_form,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":warnings,"profile_level":level,"audio_rate":""}
    print(f"RESULT: {json.dumps(result, ensure_ascii=False)}")
    return 0

def handle_upgrade(args) -> int:
    """Upgrade an existing legacy note to the newest canonical skill shape.
    Handles legacy frontmatter, converts Situation -> Context, updates headings,
    generates chunks if missing, ensures PlayPhrase row and Wikilinks in word_family,
    and upgrades Gang base view.
    """
    try:
        vault_root, _ = vocab_profiles.load_config(args.vault_root)
    except Exception:
        vault_root = Path(args.vault_root) if args.vault_root else None

    if getattr(args, "upgrade_file", None):
        note_path = Path(args.upgrade_file)
        if not note_path.exists():
            print(f"ERROR: note file not found: {note_path}", file=sys.stderr)
            return 1
        word = note_path.stem
    elif getattr(args, "upgrade", False):
        if not args.word:
            print("ERROR: --upgrade requires --word <WORD>", file=sys.stderr)
            return 1
        word = vocab_io.normalize_word(args.word)
        char = vocab_io.base_word(word)[0].upper()
        if not vault_root:
            print("ERROR: vault_root not found or specified", file=sys.stderr)
            return 1
        note_path = Path(vault_root) / "Vocabulary" / char / f"{word}.md"
        if not note_path.exists():
            print(f"ERROR: note not found in vault: {note_path}", file=sys.stderr)
            return 1
    else:
        return None

    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: could not read {note_path}: {e}", file=sys.stderr)
        return 1

    fm = vocab_io.parse_frontmatter(note_path)
    b_word = vocab_io.base_word(word)
    char = b_word[0].upper()
    category = resolve_category(fm.get("category",""), fm.get("type",""))
    level = fm.get("level", "B1")
    status = fm.get("status", "In Progress")
    arabic = fm.get("arabic", "")
    ipa = fm.get("ipa", "")
    example = fm.get("example", "")
    created = fm.get("created") or date.today().isoformat()
    day = fm.get("day") or fm.get("created_day") or date.today().strftime("%A")
    month = fm.get("month") or date.today().strftime("%B")
    modified = date.today().isoformat()
    review = fm.get("review") or date.today().isoformat()
    chunks = fm.get("chunks")
    if not chunks:
        chunks = vocab_io.auto_chunk_word(b_word)

    info_fields = vocab_io.extract_info_fields(content, word)
    definition = info_fields.get("definition", "")
    context = info_fields.get("context", "")
    if not example:
        example = info_fields.get("example", "")
    if not ipa:
        ipa = info_fields.get("ipa", "")

    notes = vocab_io.extract_notes_dict(content, word)

    if "etymology" in notes and "curiosity" not in notes:
        notes["curiosity"] = notes.pop("etymology")

    fam_forms = []
    if notes.get("word_family"):
        for ln in str(notes["word_family"]).splitlines():
            ln = ln.strip()
            if not ln:
                continue
            m_old = re.match(r"^`([^`]+)`\s*\(", ln)
            if m_old:
                fam_forms.append(m_old.group(1).strip())
            else:
                m_wiki = re.match(r"^-\s*\[\[([^\]]+)\]\]$", ln)
                if m_wiki:
                    fam_forms.append(m_wiki.group(1).strip())
                elif ln.startswith("[[") and ln.endswith("]]"):
                    fam_forms.append(ln[2:-2].strip())
                elif ln.startswith("- "):
                    fam_forms.append(ln[2:].strip())
                else:
                    fam_forms.append(ln)
        notes["word_family"] = fam_forms

    fields = {
        "char": char,
        "category": category,
        "subject": "Vocabulary",
        "level": level,
        "definition": definition,
        "arabic": arabic,
        "context": context,
        "situation": context,
        "example": example,
        "ipa": ipa,
        "chunks": chunks,
        "image": fm.get("image", ""),
        "status": status,
        "created": created,
        "day": day,
        "modified": modified,
        "review": review,
        "month": month,
        "notes": notes,
    }

    try:
        rendered = vocab_io.render_note(word, fields)
    except Exception as e:
        print(f"ERROR: failed to render upgraded note: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[dry-run] would upgrade {note_path} to canonical schema")
        return 0

    try:
        note_path.write_text(rendered, encoding="utf-8")
        print(f"[upgrade] successfully upgraded {word} ({note_path}) to canonical standard")
    except Exception as e:
        print(f"ERROR: failed to write {note_path}: {e}", file=sys.stderr)
        return 1

    if getattr(args, "audio", "auto") != "never" and vault_root:
        pron_dir = Path(vault_root) / "Media" / "Pronunciation"
        example_dir = Path(vault_root) / "Media" / "Examples"
        pron_path = pron_dir / f"{word}_pronunciation.mp3"
        example_path = example_dir / f"{word.lower()}_example.mp3"
        pron_needed = not pron_path.exists()
        example_needed = not example_path.exists()
        if pron_needed or example_needed:
            try:
                vocab_audio.generate_audio_pair(b_word, example, pron_path, example_path, [], "", pron_needed, example_needed)
            except Exception as e:
                print(f"WARNING: audio generation during upgrade failed: {e}", file=sys.stderr)

    return 0

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="JSON payload as a string")
    parser.add_argument("--json-file", help="Path to a JSON file with the payload")
    parser.add_argument("--vault-root", help="Override vault root")
    parser.add_argument("--profiles", help="Override profiles.json path")
    parser.add_argument("--rate", help="Override audio rate (e.g. -10%%)")
    parser.add_argument("--show-profile", help="Print resolved profile for LEVEL and exit")
    parser.add_argument("--force", action="store_true", help="Rebuild existing note (overwrite content)")
    parser.add_argument("--change-example", action="store_true", help="Allow changing the Example")
    parser.add_argument("--maintenance", action="store_true", help="Archive fix: set modified=today but leave review/status untouched")
    parser.add_argument("--touch-only", action="store_true", help="Only refresh review/modified/status, no audio, no re-render")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print what would be written, no disk writes, no audio")
    parser.add_argument("--audio", choices=["auto","always","never"], default="auto", help="Audio generation mode (default auto)")
    parser.add_argument("--check", action="store_true", help="Read-only check of existing note for WORD")
    parser.add_argument("--word", help="Word to check (for --check/--touch-only/--add-family-member)")
    parser.add_argument("--add-family-member", action="store_true", help="Add/confirm one word_family entry under root --word (derivational routing mechanics)")
    parser.add_argument("--family-json", help="Family entry as JSON: '{\"form\":...,\"type\":...,\"arabic\":...,\"example\":...}'")
    parser.add_argument("--replace-form", help="With --add-family-member: remove this existing family form to make room at cap")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade existing note for --word to latest canonical skill format")
    parser.add_argument("--upgrade-file", help="Path to an existing note file to upgrade in-place to latest canonical skill format")
    args=parser.parse_args()
    if args.show_profile:
        return handle_show_profile(args)
    if args.check:
        return handle_check(args)
    if getattr(args, "add_family_member", False):
        return handle_add_family_member(args)
    if getattr(args, "upgrade", False) or getattr(args, "upgrade_file", None):
        return handle_upgrade(args)
    touch_res=handle_touch_word(args)
    if touch_res is not None:
        return touch_res
    profiles=vocab_profiles.load_profiles(args.profiles)
    warnings=[]; profile_level=None; applied={}
    try:
        if args.json:
            payload=json.loads(args.json)
        elif args.json_file:
            payload=json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        else:
            parser.error("Provide --json or --json-file")
    except Exception as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 1
    try:
        vault_root,_=vocab_profiles.load_config(args.vault_root)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    # paths
    has_v="vocabulary_path" in payload and payload["vocabulary_path"]
    has_p="pronunciation_path" in payload and payload["pronunciation_path"]
    has_e="examples_path" in payload and payload["examples_path"]
    if has_v:
        warnings.append("DEPRECATED: vocabulary_path in payload is deprecated; prefer vault_root — honoring override")
        words_dir=Path(payload["vocabulary_path"])
    else:
        words_dir=Path(vault_root)/"Vocabulary"
    if has_p:
        warnings.append("DEPRECATED: pronunciation_path in payload is deprecated; prefer vault_root — honoring override")
        pron_dir=Path(payload["pronunciation_path"])
    else:
        pron_dir=Path(vault_root)/"Media"/"Pronunciation"
    if has_e:
        warnings.append("DEPRECATED: examples_path in payload is deprecated; prefer vault_root — honoring override")
        example_dir=Path(payload["examples_path"])
    else:
        example_dir=Path(vault_root)/"Media"/"Examples"
    try:
        word=vocab_io.normalize_word(str(payload.get("word")))
    except Exception as e:
        print(f"ERROR: invalid word: {e}", file=sys.stderr)
        return 1
    b_word=vocab_io.base_word(word)
    char=b_word[0].upper()
    if str(payload.get("char","")).strip() and str(payload.get("char","")).strip().upper()!=char:
        warnings.append(f"char '{payload.get('char')}' overridden with derived '{char}' from word '{word}'")
    word_cap=word; word_lower=word.lower()
    derived_youglish=vocab_io.youglish_url(word)
    if str(payload.get("youglish","")).strip() and str(payload.get("youglish")).strip()!=derived_youglish:
        warnings.append(f"youglish '{payload.get('youglish')}' overridden with derived '{derived_youglish}' — the property is script-owned from the word")
    derived_playphrase=vocab_io.playphrase_url(word)
    if str(payload.get("playphrase","")).strip() and str(payload.get("playphrase")).strip()!=derived_playphrase:
        warnings.append(f"playphrase '{payload.get('playphrase')}' overridden with derived '{derived_playphrase}' — the property is script-owned from the word")
    derived_pron=vocab_io.pronunciation_link(word)
    if str(payload.get("pronunciation","")).strip() and str(payload.get("pronunciation")).strip()!=derived_pron:
        warnings.append(f"pronunciation '{payload.get('pronunciation')}' overridden with derived '{derived_pron}' — the property is script-owned from the word")
    derived_voice=vocab_io.voice_link(word)
    if str(payload.get("voice","")).strip() and str(payload.get("voice")).strip()!=derived_voice:
        warnings.append(f"voice '{payload.get('voice')}' overridden with derived '{derived_voice}' — the property is script-owned from the word")
    note_path=words_dir/char/f"{word_cap}.md"
    pron_path=pron_dir/f"{word_cap}_pronunciation.mp3"
    example_path=example_dir/f"{word_lower}_example.mp3"
    note_exists=note_path.exists()
    is_new=not note_exists
    existing_example=""; existing_created=""; existing_order=""; existing_status=""; existing_review=""
    if note_exists:
        try:
            fm=vocab_io.parse_frontmatter(note_path)
            existing_example=fm.get("example","")
            existing_created=fm.get("created","")
            existing_order=fm.get("order","")
            existing_status=fm.get("status","")
            existing_review=fm.get("review","")
        except Exception as e:
            print(f"ERROR: failed to parse existing note {note_path}: {e}", file=sys.stderr)
            return 1
    today=date.today().isoformat(); today_day=date.today().strftime("%A"); today_month=date.today().strftime("%B")
    if is_new:
        created=today; day=today_day; month=today_month; modified=created; review=created; status="Not Started"
    else:
        if existing_created:
            try:
                cd=date.fromisoformat(existing_created)
                created=existing_created; day=cd.strftime("%A"); month=cd.strftime("%B")
            except Exception:
                created=today; day=today_day; month=today_month; warnings.append(f"existing created date '{existing_created}' invalid — using today")
        else:
            created=today; day=today_day; month=today_month; warnings.append("existing note missing created — using today")
        order=existing_order if 'existing_order' in dir() else ""
        if args.maintenance:
            modified=today; review=existing_review or created; status=existing_status or "Not Started"
        else:
            modified=today; review=today
            if existing_status=="Done":
                status="In Progress"
            elif existing_status in ("In Progress","Not Started"):
                status=existing_status
            else:
                status=existing_status or "Not Started"
                if existing_status and existing_status not in ("Done","In Progress","Not Started"):
                    warnings.append(f"existing status '{existing_status}' unknown — preserving as is")
    try:
        res=validate_payload(payload, profiles, warnings, is_new, existing_example, args)
        if res is None:
            return 1
        level, profile, applied, effective_rate, payload_example, need_profile = res
        profile_level=level
    except ValueError as ve:
        print(f"ERROR: validation failed: {ve}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: validation error: {e}", file=sys.stderr)
        return 1
    effective_example=payload_example if payload_example is not None else existing_example
    cat_raw=str(payload.get("category","")).strip()
    type_raw=str(payload.get("type","")).strip()
    category_val=resolve_category(cat_raw, type_raw, warnings)
    if args.touch_only:
        if is_new:
            print("ERROR: --touch-only requires an existing note", file=sys.stderr)
            return 1
        if args.dry_run:
            print(f"[dry-run] would touch {note_path}: review={review}, modified={modified}, status={status}, created={created} (rate {effective_rate})")
            print(f'RESULT: {json.dumps({"word":word_cap,"note":str(note_path),"created":False,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":warnings,"profile_level":profile_level,"applied_limits":applied,"audio_rate":effective_rate})}')
            return 0
        content=note_path.read_text(encoding="utf-8")
        content=re.sub(r"^day:.*$", f"day: {day}", content, flags=re.MULTILINE, count=1)
        # Also upgrade legacy created_day key on old notes
        content=re.sub(r"^created_day:.*$", f"day: {day}", content, flags=re.MULTILINE, count=1)
        content=re.sub(r"^created:.*$", f"created: {created}", content, flags=re.MULTILINE, count=1)
        content=re.sub(r"^modified:.*$", f"modified: {modified}", content, flags=re.MULTILINE, count=1)
        content=re.sub(r"^review:.*$", f"review: {review}", content, flags=re.MULTILINE, count=1)
        content=re.sub(r"^month:.*$", f"month: {month}", content, flags=re.MULTILINE, count=1)
        content=re.sub(r"^status:.*$", f"status: {status}", content, flags=re.MULTILINE, count=1)
        content=re.sub(r"^char:.*$", f"char: {char}", content, flags=re.MULTILINE, count=1)
        with open(note_path,"w",encoding="utf-8") as f:
            f.write(content)
        print(f"[touch] updated {note_path}: review={review}, modified={modified}, status={status}")
        result={"word":word_cap,"note":str(note_path),"created":False,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":warnings,"profile_level":profile_level,"applied_limits":applied,"audio_rate":effective_rate}
        print(f"RESULT: {json.dumps(result, ensure_ascii=False)}")
        return 0
    if args.dry_run:
        print(f"[dry-run] would write note -> {note_path}")
        print(f"[dry-run] audio rate {effective_rate} for level {profile_level} (profile {applied.get('audio_rate')})")
        print(f"[dry-run] would ensure audio: {pron_path} and {example_path} (audio={args.audio})")
        try:
            ctx_val = payload.get("context") or payload.get("situation", "")
            arabic_raw = payload.get("arabic", "")
            if isinstance(arabic_raw, (list, tuple)):
                arabic_val = " - ".join(str(x).strip() for x in arabic_raw if str(x).strip())
            else:
                arabic_val = str(arabic_raw or "").strip()
            chunks_raw = payload.get("chunks")
            if chunks_raw is None:
                chunks_val = vocab_io.auto_chunk_word(b_word)
            elif isinstance(chunks_raw, (list, tuple)):
                chunks_val = "-".join(str(x).strip() for x in chunks_raw if str(x).strip())
            else:
                chunks_val = str(chunks_raw).strip()
            fields={"char":char,"category":category_val,"subject":"Vocabulary","level":level,"definition":payload.get("definition",""),"arabic":arabic_val,"context":ctx_val,"situation":ctx_val,"example":effective_example,"ipa":payload.get("ipa",""),"chunks":chunks_val,"image":payload.get("image",""),"status":status,"created":created,"day":day,"modified":modified,"review":review,"month":month,"notes":payload.get("notes",{})}
            rendered=vocab_io.render_note(word_cap, fields)
            assert f"{word_cap} Gang" in rendered
            for iss in vocab_checks.check_backticks(rendered, profiles):
                if iss["severity"]=="ERROR":
                    print(f"ERROR: validation failed: {iss['message']}", file=sys.stderr)
                    return 1
                warnings.append(iss["message"])
            for iss in vocab_checks.check_rtl_line_start(rendered):
                if iss["severity"]=="ERROR":
                    print(f"ERROR: validation failed ({iss['code']}): {iss['message']}", file=sys.stderr)
                    return 1
                warnings.append(iss["message"])
            for iss in vocab_checks.check_single_word_backticks(rendered, payload.get("notes",{}), word):
                warnings.append(iss["message"])
        except Exception as e:
            print(f"ERROR: render failed: {e}", file=sys.stderr)
            return 1
        result={"word":word_cap,"note":str(note_path),"created":is_new,"audio":{"pronunciation":"skipped","example":"skipped"},"warnings":warnings,"profile_level":profile_level,"applied_limits":applied,"audio_rate":effective_rate}
        print(f"RESULT: {json.dumps(result, ensure_ascii=False)}")
        return 0
    pron_needed=False; example_needed=False
    if args.audio=="never":
        pron_needed=False; example_needed=False; pron_status="skipped"; example_status="skipped"
    elif args.audio=="always":
        pron_needed=True; example_needed=True; pron_status="skipped"; example_status="skipped"
    else:
        pron_needed=not pron_path.exists()
        if not example_path.exists():
            example_needed=True
        elif not is_new and effective_example != existing_example:
            example_needed=True
        elif is_new:
            example_needed=True
        else:
            example_needed=False
        # Single-voice rule: if either file needs (re)generation, regenerate
        # BOTH with one shared engine/voice — keeping one file from an older
        # engine while generating the other is what produced mismatched voices.
        if pron_needed or example_needed:
            pron_needed=True
            example_needed=True
        pron_status="kept" if not pron_needed else "skipped"
        example_status="kept" if not example_needed else "skipped"
    try:
        if pron_needed or example_needed:
            # Single-voice rule: both files are synthesized with one shared
            # engine/voice in the same run — never one kept from an old engine
            # while the other is generated with a new one.
            pron_status, example_status, engine_label = vocab_audio.generate_audio_pair(
                b_word, effective_example, pron_path, example_path,
                warnings, effective_rate, pron_needed, example_needed)
            warnings.append(f"audio engine for this run: {engine_label} — both files share one voice")
            if pron_needed:
                print(f"[audio] pronunciation generated -> {pron_path} (rate {effective_rate}, {engine_label})")
            else:
                print(f"[audio] pronunciation kept (exists) -> {pron_path} (rate {effective_rate})")
            if example_needed:
                print(f"[audio] example generated -> {example_path} (rate {effective_rate}, {engine_label})")
            else:
                print(f"[audio] example kept (unchanged) -> {example_path} (rate {effective_rate})")
        else:
            if args.audio != "never":
                print(f"[audio] pronunciation kept (exists) -> {pron_path} (rate {effective_rate})")
                print(f"[audio] example kept (unchanged) -> {example_path} (rate {effective_rate})")
    except Exception as e:
        print(f"ERROR: audio generation failed: {e}", file=sys.stderr)
        return 1
    if not is_new and effective_example != existing_example:
        print(f"REMINDER: example changed — run audio regeneration if needed.")
        warnings.append("example changed — audio should be regenerated")
    # An existing note is ALWAYS re-rendered through vocab_io.render_note() (canonical rebuild):
    # a silent date-only patch would freeze a legacy card forever. Date-only refresh is opt-in
    # only, via --touch-only / --maintenance (see SKILL.md).
    try:
        ctx_val = payload.get("context") or payload.get("situation", "")
        arabic_raw = payload.get("arabic", "")
        if isinstance(arabic_raw, (list, tuple)):
            arabic_val = " - ".join(str(x).strip() for x in arabic_raw if str(x).strip())
        else:
            arabic_val = str(arabic_raw or "").strip()
        chunks_raw = payload.get("chunks")
        if chunks_raw is None:
            chunks_val = vocab_io.auto_chunk_word(b_word)
        elif isinstance(chunks_raw, (list, tuple)):
            chunks_val = "-".join(str(x).strip() for x in chunks_raw if str(x).strip())
        else:
            chunks_val = str(chunks_raw).strip()
        fields={"char":char,"category":category_val,"subject":"Vocabulary","level":level,"definition":payload.get("definition",""),"arabic":arabic_val,"context":ctx_val,"situation":ctx_val,"example":effective_example,"ipa":payload.get("ipa",""),"chunks":chunks_val,"image":payload.get("image",""),"status":status,"created":created,"day":day,"modified":modified,"review":review,"month":month,"notes":payload.get("notes",{})}
        rendered=vocab_io.render_note(word_cap, fields)
        for iss in vocab_checks.check_backticks(rendered, profiles):
            if iss["severity"]=="ERROR":
                print(f"ERROR: validation failed: {iss['message']}", file=sys.stderr)
                return 1
            warnings.append(iss["message"])
        for iss in vocab_checks.check_rtl_line_start(rendered):
            if iss["severity"]=="ERROR":
                print(f"ERROR: validation failed ({iss['code']}): {iss['message']}", file=sys.stderr)
                return 1
            warnings.append(iss["message"])
        for iss in vocab_checks.check_single_word_backticks(rendered, payload.get("notes",{}), word):
            warnings.append(iss["message"])
        for iss in vocab_checks.check_short_and_overlap(payload.get("notes",{})):
            if iss["severity"]=="WARNING":
                warnings.append(iss["message"])
    except Exception as e:
        print(f"ERROR: render failed: {e}", file=sys.stderr)
        return 1
    try:
        note_path.parent.mkdir(parents=True, exist_ok=True)
        with open(note_path,"w",encoding="utf-8") as f:
            f.write(rendered)
        action="updated" if note_exists else "created"
        print(f"[note] {action} -> {note_path}")
        result={"word":word_cap,"note":str(note_path),"created":is_new,"audio":{"pronunciation":pron_status,"example":example_status},"warnings":warnings,"profile_level":profile_level,"applied_limits":applied,"audio_rate":effective_rate}
        print(f"RESULT: {json.dumps(result, ensure_ascii=False)}")
        return 0
    except Exception as e:
        print(f"ERROR: failed to write note: {e}", file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
