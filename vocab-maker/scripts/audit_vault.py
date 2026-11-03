#!/usr/bin/env python3
"""
audit_vault.py — READ-ONLY vault audit for vocab-maker.

Scans notes under {vault_root}/Vocabulary and reports issues using vocab_checks.
Never writes to the vault. For existing notes, example-vs-profile findings are INFO/proposals, never violations.
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

def load_config_vault(cli_vault):
    if cli_vault:
        return Path(cli_vault)
    if os.environ.get("VOCAB_VAULT_ROOT"):
        return Path(os.environ["VOCAB_VAULT_ROOT"])
    cfg = SKILL_ROOT / "config.json"
    if cfg.exists():
        try:
            j = json.loads(cfg.read_text(encoding="utf-8"))
            if j.get("vault_root"):
                return Path(j["vault_root"])
        except Exception:
            pass
    print("ERROR: vault_root not configured", file=sys.stderr)
    sys.exit(1)

def load_profiles(profiles_path_cli):
    path = Path(profiles_path_cli) if profiles_path_cli else SKILL_ROOT / "profiles.json"
    if not path.exists():
        print(f"ERROR: profiles file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: profiles.json is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    return data

def parse_frontmatter(note_path: Path) -> dict:
    text = note_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = m.group(1)
    out: dict[str,str] = {}
    for line in fm.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":",1)
        key=key.strip()
        val=val.strip()
        if val.startswith('"') and val.endswith('"') and len(val)>=2:
            inner=val[1:-1]
            inner=inner.replace('\\"', '"').replace('\\\\','\\')
            val=inner
        out[key]=val
    return out

def extract_notes_dict(note_text: str, word: str):
    """Extract notes dict from Notes block for checks."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vocab_io
    return vocab_io.extract_notes_dict(note_text, word)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", help="Override vault root")
    parser.add_argument("--profiles", help="Override profiles.json path")
    parser.add_argument("--level", help="Filter by level (A1..C2)")
    parser.add_argument("--letter", help="Filter by letter (A-Z)")
    parser.add_argument("--status", help="Filter by status (Not Started, In Progress, Done)")
    parser.add_argument("--limit", type=int, help="Limit number of reported notes")
    parser.add_argument("--out", help="Output file (markdown .md or CSV .csv by extension; default stdout)")
    parser.add_argument("--only", choices=["examples","format","backticks","notes","all"], default="all", help="Only report category (default all)")
    parser.add_argument("--word", help="Filter by word (exact normalized word)")
    args=parser.parse_args()

    # Validate --out extension
    if args.out:
        ext=Path(args.out).suffix.lower()
        if ext not in (".md",".csv",".markdown"):
            print(f"ERROR: unknown --out extension '{ext}' — use .md or .csv", file=sys.stderr)
            sys.exit(1)

    vault_root=load_config_vault(args.vault_root)
    profiles=load_profiles(args.profiles)
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vocab_checks

    notes_root=vault_root / "Vocabulary"
    if not notes_root.exists():
        print(f"WARNING: notes root not found: {notes_root}", file=sys.stderr)
        all_notes=[]
    else:
        all_notes=sorted(notes_root.rglob("*.md"))

    rows=[]
    invalid_level_notes=[]
    for p in all_notes:
        word=p.stem
        if args.word and word.lower()!=args.word.strip().lower():
            # Also try normalized
            import re as _re2
            norm= _re2.sub(r"\s+", " ", args.word.strip())
            norm=" ".join(t[0].upper()+t[1:].lower() for t in norm.split(" "))
            if word!=norm:
                continue
        fm=parse_frontmatter(p)
        level=fm.get("level","")
        status=fm.get("status","")
        char=fm.get("char","")
        if args.level and level!=args.level:
            continue
        if args.letter and char.upper()!=args.letter.upper():
            continue
        if args.status and status!=args.status:
            continue
        if level not in {"A1","A2","B1","B2","C1","C2"} or level not in profiles.get("levels",{}):
            # List separately, still check other issues? For invalid level, list separately
            try:
                text=p.read_text(encoding="utf-8")
            except:
                text=""
            invalid_level_notes.append({"word":word,"level":level,"status":status,"path":str(p),"example":fm.get("example","")})
            continue
        # For valid level, run checks
        try:
            note_text=p.read_text(encoding="utf-8")
        except Exception as e:
            print(f"WARNING: failed to read {p}: {e}", file=sys.stderr)
            continue
        example_raw=fm.get("example","")
        # Normalize table escape before comparing (per spec)
        example=vocab_checks.normalize_table_escape(example_raw)
        notes=extract_notes_dict(note_text, word)
        # Need category/type for hook check
        type_v=fm.get("category","") or fm.get("type","")
        if type_v not in ("Noun","Verb","Adjective","Adverb","Phrasal Verb","Idiom","Phrase","Preposition","Conjunction","Pronoun","Determiner","Interjection"):
            alt=fm.get("type","")
            if alt in ("Noun","Verb","Adjective","Adverb","Phrasal Verb","Idiom","Phrase","Preposition","Conjunction","Pronoun","Determiner","Interjection"):
                type_v=alt
        # Run checks — for existing notes, example vs profile is INFO
        issues=vocab_checks.check_all(note_text, notes, level, profiles, example, is_new_or_changed=True, fallback=None, type_v=type_v, word=word, legacy_ok=True)
        # Existing notes: example/target findings and legacy-card upgrades (missing youglish,
        # legacy frontmatter shape) are INFO proposals, never violations — the same severity
        # mapping build_word.py --check uses, from one shared implementation.
        filtered=vocab_checks.as_proposals(issues)
        # Filter by --only
        if args.only!="all":
            def _cat(code):
                if code.startswith("example_") or code.startswith("target_word"):
                    return "examples"
                if code.startswith("frontmatter") or code.startswith("summary") or code.startswith("arabic") or code.startswith("level") or code.startswith("youglish") or code.startswith("playphrase") or code.startswith("pronunciation") or code.startswith("voice") or code.startswith("definition") or code.startswith("chunks") or code.startswith("info_table"):
                    return "format"
                if code.startswith("backtick") or code.startswith("unwrapped"):
                    return "backticks"
                if code.startswith("extras") or code.startswith("note_") or code.startswith("notes_") or code.startswith("hook") or code.startswith("grammar") or code.startswith("rtl"):
                    return "notes"
                return "all"
            filtered=[i for i in filtered if _cat(i["code"])==args.only]
        if not filtered:
            continue
        # Severity score: hard violations first (ERROR)
        severity=sum(10 if i["severity"]=="ERROR" else 5 if i["severity"]=="INFO" else 1 for i in filtered)
        rows.append({
            "word":word,"level":level,"status":status,"example":example,"issues":filtered,"severity":severity,"path":str(p)
        })

    # Sort by severity desc
    rows.sort(key=lambda r: (-r["severity"], r["word"]))
    if args.limit:
        rows=rows[:args.limit]

    out_path=Path(args.out) if args.out else None
    out_f=None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_f=open(out_path,"w",encoding="utf-8",newline="")

    dest=out_f if out_f else sys.stdout
    if out_path and out_path.suffix.lower()==".csv":
        writer=csv.DictWriter(dest, fieldnames=["word","level","status","example","severity","issues","path"])
        writer.writeheader()
        for r in rows:
            iss_str="; ".join(f"{i['code']}({i['severity']}):{i['message']}" for i in r["issues"])
            writer.writerow({"word":r["word"],"level":r["level"],"status":r["status"],"example":r["example"],"severity":r["severity"],"issues":iss_str,"path":r["path"]})
        if invalid_level_notes:
            writer.writerow({})
            writer.writerow({"word":"INVALID LEVEL NOTES"})
            for inv in invalid_level_notes:
                writer.writerow({"word":inv["word"],"level":inv["level"],"status":inv["status"],"example":inv["example"],"path":inv["path"]})
    else:
        if rows:
            dest.write("| Word | Level | Status | Example | Severity | Issues |\n")
            dest.write("|---|---|---|---|---|---|\n")
            for r in rows:
                ex=r["example"].replace("|","\\|").replace("\n"," ")
                iss="; ".join(f"{i['code']}({i['severity']})" for i in r["issues"])
                dest.write(f"| {r['word']} | {r['level']} | {r['status']} | {ex} | {r['severity']} | {iss} |\n")
                # Detailed issues as sub-list
                for i in r["issues"]:
                    dest.write(f"  - {i['code']} {i['severity']} {'[auto]' if i['auto_fixable'] else ''} {i['message'].replace('|','\\|')}\n")
        else:
            dest.write("No notes matched filters or no issues found.\n")
        if invalid_level_notes:
            dest.write("\n### Notes without valid level\n")
            for inv in invalid_level_notes:
                dest.write(f"- {inv['word']} (level='{inv['level']}' status='{inv['status']}') — {inv['example']}\n")

    if out_f:
        out_f.close()
        print(f"Wrote {len(rows)} rows to {out_path}", file=sys.stderr)

    print("no_changes_made")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
