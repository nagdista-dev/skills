#!/usr/bin/env python3
"""vocab_profiles.py — config and profile loading for vocab-maker."""
import json
import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_LEVELS = {"A1","A2","B1","B2","C1","C2"}

def load_config(vault_root_cli: str | None):
    warnings=[]
    vault_root=None
    if vault_root_cli:
        vault_root=Path(vault_root_cli)
    elif os.environ.get("VOCAB_VAULT_ROOT"):
        vault_root=Path(os.environ["VOCAB_VAULT_ROOT"])
    else:
        cfg_path=SKILL_ROOT / "config.json"
        if cfg_path.exists():
            try:
                cfg=json.loads(cfg_path.read_text(encoding="utf-8"))
                vr=cfg.get("vault_root")
                if vr:
                    vault_root=Path(vr)
            except Exception as e:
                raise RuntimeError(f"failed to read config.json: {e}")
    if vault_root is None:
        raise RuntimeError("vault_root not configured — set --vault-root, env VOCAB_VAULT_ROOT, or config.json vault_root")
    return vault_root, warnings

def load_profiles(profiles_path_cli: str | None):
    path=Path(profiles_path_cli) if profiles_path_cli else SKILL_ROOT / "profiles.json"
    if not path.exists():
        print(f"ERROR: profiles file not found: {path}", file=sys.stderr)
        import sys
        sys.exit(1)
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: profiles.json is not valid JSON: {e} ({path})", file=sys.stderr)
        import sys
        sys.exit(1)
    try:
        if "_default" not in data:
            raise ValueError("missing '_default'")
        if data["_default"] not in ALLOWED_LEVELS:
            raise ValueError(f"_default '{data['_default']}' must be one of {sorted(ALLOWED_LEVELS)}")
        if "contraction_sets" not in data or "basic" not in data["contraction_sets"] or "standard" not in data["contraction_sets"]:
            raise ValueError("contraction_sets must contain 'basic' and 'standard'")
        if "slang_terms" not in data or not isinstance(data["slang_terms"], list):
            raise ValueError("slang_terms must be a list")
        if "levels" not in data or not isinstance(data["levels"], dict):
            raise ValueError("levels must be an object")
        for lvl in ALLOWED_LEVELS:
            if lvl not in data["levels"]:
                raise ValueError(f"levels missing '{lvl}'")
            lv=data["levels"][lvl]
            if "example" not in lv or not isinstance(lv["example"], dict):
                raise ValueError(f"levels.{lvl}.example missing")
            for k in ("max_words","target_words","contractions","slang","style_hint"):
                if k not in lv["example"]:
                    raise ValueError(f"levels.{lvl}.example.{k} missing")
            if lv["example"]["contractions"] not in ("basic","standard"):
                raise ValueError(f"levels.{lvl}.example.contractions must be 'basic' or 'standard'")
            if not isinstance(lv["example"]["slang"], bool):
                raise ValueError(f"levels.{lvl}.example.slang must be bool")
            if "definition" not in lv or "max_words" not in lv["definition"]:
                raise ValueError(f"levels.{lvl}.definition.max_words missing")
            if "context" not in lv and "situation" not in lv:
                raise ValueError(f"levels.{lvl}.context.max_words missing")
            ctx_node = lv.get("context") or lv.get("situation")
            if not isinstance(ctx_node, dict) or "max_words" not in ctx_node:
                raise ValueError(f"levels.{lvl}.context.max_words missing")
            lv["context"] = ctx_node
            lv["situation"] = ctx_node
            if "audio" not in lv or "rate" not in lv["audio"]:
                raise ValueError(f"levels.{lvl}.audio.rate missing")
            if "notes" not in lv:
                raise ValueError(f"levels.{lvl}.notes missing")
            for k in ("max_sentences_per_note","extras_max","try_it","arabic_register","family_max","collocations_max"):
                if k not in lv["notes"]:
                    if k=="extras_max" and "optional_max" in lv["notes"]:
                        raise ValueError(f"levels.{lvl}.notes.extras_max missing — found old 'optional_max', rename to 'extras_max' (see profiles.json)")
                    raise ValueError(f"levels.{lvl}.notes.{k} missing")
        if "formatting" not in data:
            raise ValueError("missing 'formatting'")
        fmt=data["formatting"]
        if "backticks_max_per_paragraph" not in fmt or "plain_terms" not in fmt:
            raise ValueError("formatting must contain backticks_max_per_paragraph and plain_terms")
        if not isinstance(fmt["plain_terms"], list):
            raise ValueError("formatting.plain_terms must be a list")
        return data
    except ValueError as ve:
        print(f"ERROR: profiles.json schema error: {ve} ({path})", file=sys.stderr)
        import sys
        sys.exit(1)

def resolve_profile(level: str, profiles: dict, warnings: list):
    if not level or level not in profiles.get("levels",{}):
        default=profiles.get("_default","B1")
        warnings.append(f"level '{level}' unknown or missing — falling back to _default '{default}'")
        level=default
    return profiles["levels"][level]
