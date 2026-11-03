# Skills

> A personal collection of drop-in **AI agent skills** — self-contained instruction packs that teach an agent a specialized workflow.

<p align="center">
  <img src="https://img.shields.io/badge/Agent_Skills-SKILL.md-6B46C1?style=for-the-badge" alt="Agent Skills" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Obsidian-7C3AED?style=for-the-badge&logo=obsidian&logoColor=white" alt="Obsidian" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License" />
</p>

Each skill lives in its own folder with a `SKILL.md` entry point (YAML frontmatter + instructions) plus any scripts, references, and tests it needs. Nothing is shared between skills, so you can copy only the ones you want.

## Available Skills

| Skill | What it does | Example triggers |
|-------|--------------|------------------|
| [**vocab-maker**](./vocab-maker) | Turns English words, phrases, and idioms into complete Obsidian vocabulary cards — level-aware notes, Egyptian Arabic explanations, and two audio files per word. | `"create word abandon"`, `"اعمل كلمة abandon"`, `"audit my vocabulary cards"` |

### vocab-maker

A teacher-style vocabulary builder for an Obsidian vault. For every requested word it scans the distinct senses, picks the right CEFR level, and writes a canonical card that passes the skill's own machine checks.

**Highlights**

- **Level-aware profiles (A1–C2)** control example length, definition/context ceilings, contractions, slang, note count, and audio speed.
- **One card per sense** — homographs like *saw* (noun) and *saw* (verb) become separate notes.
- **Audio built in** — pronunciation and example MP3s via `edge-tts` (US male voices), with an automatic Google TTS fallback.
- **Egyptian Arabic notes** — translations, common mistakes, and usage notes written in natural Masri, with RTL-safe line rules.
- **Deterministic output** — a single renderer builds the note, and a test suite compares rendered cards against reference examples.
- **Vault hygiene tools** — `--check`, `--upgrade`, `--maintenance`, and a full-vault audit.

**Requirements:** Python 3.10+ and an Obsidian vault. `edge-tts` (preferred) or `gtts` is only needed when generating audio.

**Setup**

```bash
git clone https://github.com/nagdista-dev/skills.git
cp -r skills/vocab-maker ~/.agents/skills/

cd ~/.agents/skills/vocab-maker
cp config.example.json config.json   # then set your own vault_root
python3 -m pip install edge-tts gtts  # optional: audio generation
```

`vault_root` can also be passed per command with `--vault-root`, or set with the `VOCAB_VAULT_ROOT` environment variable.

**Build a card**

```bash
python3 scripts/build_word.py --json '{
  "word": "Abandon",
  "category": "Verb",
  "level": "B1",
  "definition": "To leave someone or something behind for good.",
  "arabic": "يهجر",
  "context": "The family had to ==abandon== their old house after the flood.",
  "example": "I abandoned my plan and went home."
}'
```

**Verify**

```bash
python3 tests/run_tests.py                       # skill test suite
python3 scripts/build_word.py --check --word Abandon
python3 scripts/audit_vault.py                   # vault-wide audit
```

See [vocab-maker/SKILL.md](./vocab-maker/SKILL.md) for the full workflow, the card contract, and every CLI flag.

## Repository Layout

```
skills/
├── README.md
├── LICENSE
├── .gitignore
└── vocab-maker/
    ├── SKILL.md              # skill entry point (frontmatter + instructions)
    ├── profiles.json         # numeric limits per CEFR level
    ├── config.example.json   # copy to config.json and edit
    ├── references/           # templates, rules, worked examples
    ├── scripts/              # builder, renderer, checks, audio
    ├── tests/                # test suite
    └── Vocabulary/           # sample output card
```

## Installation

Different agents look for skills in different places. Copy (or symlink) the skill folder into the directory your agent scans:

| Agent / setup | Skills directory |
|---------------|------------------|
| OpenCode (current) | `~/.agents/skills/` |
| OpenCode (older) | `~/.config/opencode/skills/` |
| Project-local | `.agents/skills/` inside the project |

Only the folder name matters — the agent reads `SKILL.md` for its `name` and `description`.

## Adding a New Skill

1. Create a folder with the skill's name, e.g. `my-skill/`.
2. Add `SKILL.md` with `name` and `description` in the frontmatter, then the instructions.
3. Keep scripts, references, and tests inside that folder.
4. Commit and push.

## License

[MIT](./LICENSE) © 2026 Mahmoud Alnagdy
