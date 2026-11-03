---
name: vocab-maker
description: 'Turns English words, phrases, and idioms into Obsidian vocabulary cards (note + pronunciation and example audio) and keeps them consistent via level-aware profiles. Triggers on: creating cards from one or more words/phrases/idioms (e.g. "create word abandon", "make english word X", lists, Arabic user prompts like "اعمل كلمة abandon"), re-sending an existing word to refresh review, changing or proposing an example, repairing/reformatting or bulk-updating old notes, auditing or reviewing examples for profile violations, and tuning level profiles.'
---

# Vocab Maker

> Behaves like a good teacher. It decides what THIS learner needs to know about THIS word at THIS level, and leaves out everything else. A note exists only if it passes the value test. A shorter card that teaches is better than a full card that fills space.

Turns English words, phrases, and idioms into an Obsidian note and two audio files. Mechanical execution is handled by `scripts/build_word.py`. Your job is teacher judgment — authoring high-value content tailored to the learner's level.

Notes include an `image:` frontmatter property providing a targeted Google Images search link for visual reinforcement (no local image files or image embeds).

## Workflow — Plan First, Then Execute

Every request is a short project, not a single action. Never start writing card content before a plan exists.

0. **Sense scan before the plan.** For every requested word, list its distinct senses first (EVP, Oxford, a learner's dictionary, or teacher knowledge) and decide how many cards they need. A word with more than one distinct meaning is built as separate cards **in the same run** — the split belongs to the plan, it is never postponed and never squeezed into one card.
1. **Plan first.** Write a numbered plan (3–8 steps) that names exactly what will be done for this request: which words, which cards are new vs. existing, root/derivative routing, content decisions, scripts to run, verification.
2. **Convert the plan into a todo list.** One todo item per plan step, in the same order, with the status of each step tracked (`pending` → `in_progress` → `completed`). Keep exactly one step `in_progress` at a time.
3. **Execute the plan step by step.** Finish a step (and its todo) before moving to the next one. A step is only `completed` when its output exists on disk (note written, audio generated, check run).
4. **Re-plan instead of drifting.** If the work turns out to differ from the plan (a word needs a root card, a check fails, a derivative appears), update the plan and the todo list first, then continue.
5. **Verify.** Run the relevant check (`--check`, `--dry-run`, the audit) before reporting, and close the todo list with every item resolved.

For a single word the plan is short (one card, one build, one verification) — but it still exists. For a batch, the plan lists every word and the order of processing.

## Teacher Authority — Act, Don't Ask

You are this learner's private English teacher. You are authorized to make every correction that falls inside this skill's rules, and you are expected to make it immediately — silently, in the flow of the work — instead of stopping to ask for permission. The learner reads your final report; the report is a record of what you did, not a request for approval.

**Fix immediately, without asking (and log it in the report):**
- Any objective error: wrong meaning, broken spelling/grammar, missing target word, wrong CEFR level, wrong category, malformed frontmatter, missing or stale properties, legacy structure that is not the canonical shape.
- Any violation of this skill: an example that breaks the level profile (too long, not first person, off-level vocabulary, disallowed contraction or slang), a missing required hook, a missing `grammar_note` for a Phrasal Verb/Idiom, a line that breaks the Arabic text-direction rule, backtick overuse, an over-cap note list, a note field that fails the value test.
- Any card that is not the canonical structure (missing `image`/`youglish`/`pronunciation`/`voice`, legacy `Situation` row, old frontmatter order) — rebuild it in the canonical shape.

**How to fix:**
- Use the level's profile as the source of truth and rewrite the offending content yourself (write 3 candidate examples internally, rank them, keep the best — the candidates stay out of the note).
- When you change an example, pass `--change-example` so the example audio regenerates, and sync the three places together: Info table, frontmatter `example`, example audio.
- When you change the level, rebuild the card at the corrected level so every limit re-applies.
- Rebuild with the canonical payload (`--force`) so the card is re-rendered through `vocab_io.render_note()`.

**Never ask the user about:** a wrong word choice, a broken card, a failing check, a missing field, an off-level example, an unclear register, or anything else the skill already decides. Do not interrupt the run with questions about content the rules settle.

**Only stop and ask when:** the request itself is ambiguous at the level of *which word or which file* (no signal at all), or the action is destructive and outside the skill's scope (deleting notes, wiping media, changing the vault structure). Even then, ask once, briefly.

**Do not narrate the work:** no per-word report, no summary of what was fixed, no "judgment calls" list. Apply what is right, surface only warnings and errors, and finish with one short confirmation (see "Reporting — No Narration").

## Arabic Text Direction (RTL Rule)

Arabic notes are read right-to-left. A line that STARTS with English text flips the paragraph direction, and the mixed Arabic/English line becomes unreadable (the reader loses the thread). **Every line of Arabic prose must start with Arabic**, and the English may follow after it.

- **Bad:** `dispatch takes a direct object always: dispatch an order.`
- **Good:** `كلمة dispatch بتاخد مفعول مباشر دايماً: dispatch an order.`

Rules:
- Open the line with an Arabic word — `كلمة X`, `فعل X`, `الكلمة دي`, `في الاستخدام ده`, `معنى X` — then let the English follow inline.
- Never open a line with an English word, an English phrase, or an English quote. `I'm dispatching it now` must sit after an Arabic start, e.g. `... والوقت ممكن ييجي قبلها: I'm dispatching it now.`
- The same rule applies inside callouts (`> [!tip] عارف إن؟`) and list items — a bullet whose text starts with English is a violation too.
- English phrases, grammar patterns and IPA strings stay in backticks per `references/formatting_rules.md`; the backtick does not exempt the line-start rule.
- The card's own English sections (Definition, Example, Context, IPA row) are English-only and unaffected.

`scripts/vocab_checks.py` enforces this (`check_rtl_line_start`): a payload whose notes open a line with English is rejected at build time with `rtl_line_start`; existing cards are reported by the audit as an upgrade proposal fixed on the next rebuild. When you see it, rewrite the line to start with Arabic — you do not need to ask.

## Word Groups — Permanently Disabled

Word Groups are not used. `scripts/add_to_group.py` is NEVER called — not for new words, rebuilds, example changes, audits, or any other operation. When an example changes, sync only the three places: note Info table, frontmatter `example`, and example audio. Final reports never mention groups.

## Vault Configuration

Vault root in `config.json`: `{"vault_root": "/path/to/English"}`. Resolution order: CLI `--vault-root` > env `VOCAB_VAULT_ROOT` > `config.json`.
From vault root:
- Note file: `Vocabulary/{char}/{Word}.md`
- Pronunciation audio: `Media/Pronunciation/{Word}_pronunciation.mp3` (Title-Case)
- Example audio: `Media/Examples/{word}_example.mp3` (all lowercase)


Deprecated `vocabulary_path`, `pronunciation_path`, and `examples_path` in payload are still honored with a warning.

## Adaptive Profiles

All numeric limits live in `profiles.json` (the single source of truth for numeric limits). Read `profiles.json` and `references/adaptive_rules.md` before writing. The CEFR level is decided **before** any other field; its profile controls example length/slang/contractions, definition length, context length, audio rate, and note limits. Style hints and vocabulary ceiling (other words at or below the word's level) are your responsibility as a teacher, not machine-checked. See `references/formatting_rules.md` for backtick rules.

## Word Naming

`normalize_word()` = strip leading/trailing whitespace, collapse internal whitespace to single spaces, and Title-Case each token (`take out` → `Take Out`). All-caps acronyms (2+ letters, no lowercase) keep their caps (`IPO` → `IPO`, `TV` → `TV`) — the vault stores acronyms in caps, so the tooling must reach them.
- Note filename: `{Word}.md` (Title-Case)
- Expressive headings: `## {Word} Info`, `## {Word} Pronunciation`, `## {Word} Example`, `## {Word} Notes` (Title-Case)
- Internal wikilinks: `[[{Word}]]` (Title-Case)
- Pronunciation audio: `![[{Word}_pronunciation.mp3]]` (Title-Case `{Word}`)
- Example audio: `![[{word}_example.mp3]]` (all lowercase `{word}`)
- YouGlish URL: `https://youglish.com/pronounce/{word_with_underscores}/english/us` (all lowercase, spaces replaced with `_`) — rendered both in the Info lookup line and as the `youglish` property, from the same value
- PlayPhrase URL: `https://www.playphrase.me/#/search?q={words_with_plus}=2&language=en` (all lowercase, spaces replaced with `+`) — rendered ONLY on `Idiom` and `Phrase` cards, as the `playphrase` frontmatter property AND as the Info lookup link. Single words and ordinary parts of speech carry no PlayPhrase at all
- `image` property: Google Images search URL `https://www.google.com/search?q=<QUERY>&tbm=isch&tbs=itp:clipart` (or without `&tbs=itp:clipart` for prepositions) derived per word category & modifier rules — rendered as a frontmatter property grouped under Media
- `pronunciation` property: `[[{Word}_pronunciation.mp3]]` (Title-Case, same file as the Pronunciation section embed) — rendered as a frontmatter property so links stay grouped and reachable from bases
- `voice` property: `[[{word}_example.mp3]]` (all lowercase, same file as the Example section embed) — rendered as a frontmatter property so links stay grouped and reachable from bases
- Forbidden characters rejected: `/ \ : * ? " < > | # ^ [ ]`
- `char`: derived from the first letter uppercase (e.g. `Take Out` → `T`); payload `char` is overridden with a warning if mismatched.

## Lemmatization & Derivative Rule

1. **Derivatives and Non-Root Words (Nouns, Adjectives, Adverbs):**
   - The old rule that collapsed derivatives into the root note is CANCELLED.
   - When the user requests a non-root word (e.g. a noun derivative with `-ment`, `-ness`, `-ity`, `-ation`, an adjective with `-ive`, `-ous`, `-able`, or an adverb with `-ly`, etc.):
     a. **Root verification & creation:** Check if the root word's note exists in the vault. If the root note does NOT exist, create the complete vocabulary card for the ROOT word first (note + pronunciation audio + example audio).
     b. **Derivative card creation:** Create the complete, separate vocabulary card for the requested derivative word itself (with its own note, pronunciation audio, and example audio).
     c. **Dual independent cards:** Both words get their own separate cards; derivatives are NEVER collapsed into or suppressed by the root note.
     d. **Cross-referencing:** Both cards cross-reference each other under their `word_family` lists.
2. **Meaning-change first:** Keep as typed if reducing changes the core meaning (`news` ≠ `new`, `means` ≠ `mean`, etc.). When a word carries more than one distinct meaning (`saw`, `found`, `beam`, `check out`), it is NEVER squeezed into one card: every distinct meaning gets its OWN card under "One Card Per Meaning".
3. **Inflectional lemmatization only:** Strip only grammatical inflections of the same part of speech:
   - Plural nouns → singular (`abandonments` → `Abandonment`, `deserts` → `Desert`).
   - Verb conjugations → base infinitive (`abandoned` → `Abandon`, `running` → `Run`).
   - Comparatives/superlatives → base adjective (`faster` → `Fast`).
   - Phrasal verbs / idioms → base infinitive (`kicked the bucket` → `Kick The Bucket`) unless the inflected form is fixed.
4. **Existing lemma:** If the base lemma already exists, treat as an existing word and perform the mandatory teacher review and rebuild.

## Card Content

### `category`

`Noun`, `Verb`, `Adjective`, `Adverb`, `Phrasal Verb`, `Idiom`, `Phrase`, `Preposition`, `Conjunction`, `Pronoun`, `Determiner`, `Interjection` (case-sensitive; part of speech, previously named `type`).

### `level`

Decide first. Order of resolution:
1. With web tool, check English Vocabulary Profile (EVP) then Oxford badge (badge overrides).
2. Otherwise use best teacher knowledge.
3. Last resort frequency bands: `A1` 1–1000, `A2` 1001–2000, `B1` 2001–3000, `B2` 3001–5000, `C1` 5001–7000, `C2` 7001+. For >10 words verify only uncertain words and report estimated ones.

### Value Test and Notes

A note field is written only if a learner at this level would use the word differently, avoid a real mistake, or remember it better because of it. Otherwise omit it. Never write a field just because it exists.

- **Core always:** `word_translations`, `example_translation`.
- **Hook at least one:** `curiosity` or `common_mistakes` (pick what helps this word most; both allowed if genuinely good). `etymology` is never used — omit always.
- **`grammar_note` required** for Phrasal Verb/Idiom; otherwise only when it prevents a real error.
- **Other optional judged by value test:** `when_used` only when register/context restricted; `cultural_context` only when real American/Egyptian contrast or trap exists; `synonyms`, `synonym_contrast`, `antonyms`, `important_notes`, `additional_notes`, `try_it`.
- **Structural lists (own caps in `profiles.json`, NOT counted in `extras_max`):** 
  - `word_family` (**MANDATORY** for every word): list of related morphological forms/derivatives (e.g. `["Abandonment", "Abandoned"]`). Rendered as Obsidian wikilinks `- [[Form]]` inside the `> [!example] من نفس الأصل` callout to build the word's family tree in Obsidian Graph View.
  - `synonyms`: rendered as Obsidian wikilinks `- [[Synonym]]` inside the `> [!example] مرادفات` callout so that synonyms also connect into the graph view just like the word family.
  - `common_examples` (cap `collocations_max`: full everyday sentences that use the word, with the target word highlighted as `==word==` — never bare two-word collocations).
  - `synonym_contrast` is prose and DOES count toward `extras_max`. When contrasting words, wrap the compared word in wikilinks (e.g. `[[leave]]`) for fast navigation and referencing.

Count non-empty note fields excluding `word_translations`, `example_translation` (core) and structural `word_family` / `common_examples` after any `try_it` drop — must be <= `extras_max` (warning, not error; values per profile in `profiles.json`). Warn also when a note has <3 words or two notes overlap >80% tokens (overlap check includes `synonym_contrast` vs `common_mistakes`). Details: `references/adaptive_rules.md`.

### `definition`, `context`, `example`

- `definition`: one sentence within profile `definition.max_words`.
- `context`: English third person, describes the exact same moment as the example, within `context.max_words`. Grounded in relatable everyday colloquial life situations (الحياة اليومية/العامية) representing the **word's single most common / frequent everyday usage**. Rendered as an Obsidian `> [!quote] Context` callout (omitted from frontmatter properties). The target word MUST appear in it and must be highlighted with `==target_word==` (e.g. `==abandoned==`, `==saw==`).
- `example`: Grounded in everyday colloquial life (الحياة اليومية/العامية) in the word's single most frequent pattern/usage (memorizing the sentence teaches how native speakers actually use the word in daily life; see `references/adaptive_rules.md`). Starts with first person (`I`, `I'm`, `I've`, `I'd`, `I'll`, `I can't`, `I don't`, `My`; `We`/`Our` only with non-empty `example_person_fallback`). `try_it` rendered only if profile `try_it` is true (dropped with warning otherwise).
- `ipa`: IPA pronunciation string (e.g. `/əˈbændən/`), stored as a frontmatter property AND displayed in the Info section's `**IPA:**` line.
- `chunks` (**MANDATORY**): The word split into memorable hyphenated phonetic parts (e.g. `a-ban-don`, `wa-ter`, `mit-i-gate`, `cal-cu-late`). Must NEVER be empty (`""`), even for single-syllable words (e.g. `Saw` → `s-aw`, `Cat` → `c-at`, `Take` → `t-ake`, `Old` → `o-ld`), because chunks exist to assist memorization for all words. Stored as a frontmatter property. The script provides an automatic heuristic fallback `auto_chunk_word` (including onset-rime splitting for single-syllable words) if omitted.
- `arabic`: All available Arabic translations for the word, separated by " - " (dash with spaces). Arabic script only, no backticks allowed. Example: `منشار - رأيت`.
- Hook fields per value test: `curiosity` is Egyptian Arabic, fun, true/checkable, within `max_sentences_per_note`, not repeating etymology; if no verified fact exists use a usage quirk or trap. Rendered as `> [!tip] عارف إن؟`.

Backticks (`` ` ``): used sparingly and only in specific necessary places (grammar patterns e.g. `subject + verb`, specific linguistic tokens, and IPA strings). Do NOT wrap casual English words or phrases in backticks — backtick overuse creates distracting monospace code blocks that clutter the note. See `references/formatting_rules.md`. Machine checks in `profiles.json: formatting` (`backticks_max_per_paragraph` 4 for prose notes; structural lists exempt).

## Note Structure

Frontmatter order: `subject`, `category`, `level`, `status`, `arabic`, `ipa`, `chunks`, `definition`, `example`, `pronunciation`, `voice`, `youglish`, `playphrase` (Idiom/Phrase only), `image`, `char`, `day`, `month`, `created`, `modified`, `review`. Grouped aesthetically: Core Classification → Language Content → Audio & Media → Timeline & Vault. Script-owned: never manually pass `created`/`review`/`status`/`modified`/`day`/`month`/`char`/`youglish`/`playphrase`/`pronunciation`/`voice`/`image`. After the closing `---` comes one standalone `---` separator line, then one blank line, and only then the first heading.

`definition` is a frontmatter property on purpose: it holds the exact same definition sentence shown in the Info block's `**Definition:**` line — one source of truth, written once in the payload and rendered by the script in both places, so it can never drift or go stale (same idea as the `example` property). It is reachable from the properties panel and from any base.

`image` is a property in frontmatter: a targeted Google Images search URL derived per category & modifier rules (`https://www.google.com/search?q=<QUERY>&tbm=isch&tbs=itp:clipart` or without `&tbs=itp:clipart` for prepositions), reachable directly from Obsidian properties for visual learning.

`youglish` is a property on purpose: it is the same link as the Info section's YouGlish lookup, but reachable from the properties panel and from any base. It is derived from the word — lowercase, spaces replaced with `_` — so the agent never types it and it can never be mistyped or left stale.

`playphrase` is kept as a frontmatter property right under `youglish` ONLY on **Idiom** and **Phrase** cards. On all other word categories (Noun, Verb, Adjective, etc.), `playphrase` is omitted from frontmatter **and** the PlayPhrase lookup link is omitted from the Info block — PlayPhrase is a video search for idioms and phrases, it has no value for a single word. It is derived from the word — lowercase, spaces replaced with `+` — so the agent never types it and it can never be mistyped or left stale.

`pronunciation` and `voice` are the same idea for audio embeds: the same files as the Pronunciation and Example section embeds, kept as properties grouped with the other links so they are reachable from the properties panel and from any base. Both are derived from the word (`pronunciation` is Title-Case `{Word}_pronunciation.mp3`, `voice` is lowercase `{word}_example.mp3`) — so the agent never types them and they can never be mistyped or left stale.

## One Card Per Meaning (MANDATORY)

Every distinct meaning of a word gets its own card. A second meaning is NEVER taught inside another card: the `second_meaning` field is **RETIRED** — it is no longer written, and the renderer only still reads it so that legacy cards do not lose text until they are rebuilt (the same goes for `important_notes` lines that merely announce "this word has two meanings").

- **The parenthetical tag names what makes the card different**, and it is always a single word:
  - different part of speech → the role tag: `(N)`, `(V)`, `(Adj)`, `(Adv)`, `(PV)`, `(Idm)`, `(Phr)` — e.g. `Water (N)` and `Water (V)`.
  - same part of speech, different meaning → the meaning itself: `Beam (Smile)` and `Beam (Shine)`, `Check Out (Hotel)` and `Check Out (Inspect)`, `Charge (Accuse)`, `Figure (Person)`.
- **The tag is exactly one word** matching `[A-Za-z]+`, because the script strips it to derive the base word for audio synthesis, YouGlish and PlayPhrase. A two-word tag breaks that strip (`Deliver (Speech)` → `deliver` works; `Check Out (Look At)` would not). If a meaning needs two words, choose the single closest word — `(Inspect)`, not `(Look At)`.
- **Distinct-meaning test:** the two senses carry different Arabic translations AND live in different everyday situations/patterns, so the learner needs a separate example and a separate memory hook. A figurative extension the learner would never confuse with the literal sense does not earn its own card.
- **Sense scan is mandatory on every build and every review, and it happens in the same run.** Read the senses the dictionaries list. Each sense that passes the distinct-meaning test gets its own complete card right now — never one card today and the second "later", never a card that carries two senses because the run is long.
- **One definition, one sense.** The `definition` sentence and the `example` must describe exactly one sense. If the definition needs "or" to join two translations that a dictionary lists as separate senses, that is two cards.
- **Announcing is forbidden.** No note may say "this word has another meaning", "also means", or similar — announcing a second sense is the trigger to write its card, not a note line.
- **Each card stands alone:** its own `definition`, `context`, `example`, pronunciation audio, example audio, notes and gang base. Cards sharing a root cross-link through `word_family` (each pointing at the other), so the graph shows them as siblings.
- **Renaming an existing card** (splitting one card into two) keeps each card's `created` date: rename the note file (and its audio files) with a shell move first, then rebuild through the script.

The script automatically uses the clean base word for audio synthesis, YouGlish, and PlayPhrase, while keeping the full title for the note file, headings, and gang view.

Sections exact headings separated by `---`. The Notes section renders every field as an Obsidian callout (see "Notes Rendering" for the callout map), so the card reads as one clean, scannable column:

````markdown
---

## {Word} Info

> [!quote] Context
> {context}

**Definition:** {definition}

**Example:** {example}

**IPA:** `{ipa}` &nbsp;•&nbsp; **Lookup:** [YouGlish](https://youglish.com/pronounce/{word_with_underscores}/english/us) &nbsp;•&nbsp; [PlayPhrase](https://www.playphrase.me/#/search?q={words_with_plus}=2&language=en)

*(the PlayPhrase link is added ONLY on Idiom and Phrase cards — single words keep the YouGlish lookup alone)*

---

## {Word} Pronunciation

![[{Word}_pronunciation.mp3]]

---

## {Word} Example

![[{word}_example.mp3]]

---

## {Word} Notes

> [!abstract] ترجمة الكلمة
> ...

> [!abstract] ترجمة المثال
> ...

> [!info] إمتى بتتقال
> ... (when value)

> [!info] ملاحظة قواعد
> ... (when value/required)

> [!info] السياق الثقافي
> ... (when value)

> [!tip] عارف إن؟
> ... (hook)

> [!example] من نفس الأصل
> - [[Form]]

> [!example] مرادفات
> - [[Synonym]]

> [!important] فرق عن كلمة قريبة
> ... (when value; compared words wrapped in wikilinks `[[...]]`; counts toward extras_max)

> [!note] أضداد
> - `...`

> [!example] أمثلة شائعة
> - I ==dispatch== the order before noon.

> [!warning] أخطاء شائعة
> ... (hook)

> [!important] ملاحظات مهمة
> ...

> [!note] ملاحظات إضافية
> ...

> [!todo] جرّبها النهارده
> ... (only if profile try_it is true)

---

## {Word} Gang

```base
views:
  - type: table
    name: {Word} Gang
    filters:
      and:
        - file.inFolder("English/Vocabulary/{char}")
        - category == "{category}"
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
```
````

Headings must be expressive, never the bare word. YAML escapes `\` and `"`; table escapes `|` as `\|`.

## Teacher Review & Always Rebuild with New Structure

Whenever ANY existing word is encountered (re-sent by the user, audited, reviewed, or inspected):

### Comprehensive Letter-by-Letter Inspection (Every Review, No Exceptions)
Every existing word must undergo a thorough inspection checking every single letter, field, constraint, and character escape:
1. **Frontmatter & Escaping:** Exact order (`subject`, `category`, `level`, `status`, `arabic`, `ipa`, `chunks`, `definition`, `example`, `pronunciation`, `voice`, `youglish`, `playphrase` [Idiom/Phrase only], `image`, `char`, `day`, `month`, `created`, `modified`, `review`). `youglish` must be exactly `https://youglish.com/pronounce/{word_with_underscores}/english/us`. `playphrase` must be exactly `https://www.playphrase.me/#/search?q={words_with_plus}=2&language=en` on Idiom/Phrase cards (omitted from frontmatter on other categories). `image` must follow the Google Images search URL rules. Arabic must be Arabic script only, no backticks.
2. **Expressive Headings & Embeds:** Headings must be expressive (`## {Word} Info`, `## {Word} Pronunciation`, `## {Word} Example`, `## {Word} Notes`, `## {Word} Gang`). Audio embeds must point to `{Word}_pronunciation.mp3` (Title-Case) and `{word}_example.mp3` (lowercase). No bare word headings.
3. **Card Head & Backticks:** the Info block is the callout card layout (`> [!quote] Context` first), a legacy table is upgraded to it, and `|` inside text is escaped as `\|`. Backticks appear only around the IPA value. Backticks in notes must comply with `formatting_rules.md` (no `plain_terms`, no duplicates in prose, English phrases wrapped as a single span, structural lists exempt).
4. **Content & Notes:** Level verified against EVP then Oxford badge (badge overrides). Definition 1 sentence within ceiling; context 3rd person describing the same moment within ceiling. Hook present, extras within `extras_max`, family/examples within caps. Every note field is a callout with its Arabic title; `common_examples` holds full everyday sentences with the target word highlighted. Sense scan done: every distinct meaning has its own card, and the definition describes exactly one sense. {Word} Gang uses `file.inFolder("English/Vocabulary/{char}")`, `category == "{category}"`, and the five columns `file.name`, `pronunciation`, `voice`, `image`, `review` (`columnSize` pins `note.pronunciation` and `note.voice` to 155 px so the table does not scroll sideways).

### Always Rebuild and Upgrade Old Cards to the New Structure
- **MANDATORY UPGRADE FOR ANY EXISTING / OLD WORD OR FILE:** Whenever an existing word or old note/file is received, requested, audited, or reviewed, it MUST ALWAYS be upgraded to the latest canonical structure according to all current skill rules:
  1. Frontmatter has `subject: Vocabulary`, `category: ...` (not `type:`), `chunks: "..."` (auto-chunked if missing), `ipa`, `definition: "..."` (the exact Info-block definition sentence), links (`youglish`, `pronunciation`, `voice`, `image`), and `playphrase` ONLY if category is `Idiom` or `Phrase`. No `context` property in frontmatter.
  2. Standalone `---` separator line between frontmatter and the first heading.
  3. Expressive headings: `## {Word} Info`, `## {Word} Pronunciation`, `## {Word} Example`, `## {Word} Notes`, `## {Word} Gang`.
  4. Info block: `> [!quote] Context` callout (not a legacy `Situation` table row), then `**Definition:**`, `**Example:**`, `**IPA:**` (backticked), and the YouGlish + PlayPhrase lookup links.
  5. `word_family` (`> [!example] من نفس الأصل`) MUST be populated with related forms as Obsidian wikilinks `- [[Form]]` to connect the word in the Obsidian Graph View.
  6. `{Word} Gang` table view filters by `file.inFolder("English/Vocabulary/{char}")`, `category == "{category}"`, `status == "Done"`, and displays `voice`.
- **Command-line Upgrade:**
  - `python3 scripts/build_word.py --upgrade --word <WORD>`: Upgrades the note in the vault in-place.
  - `python3 scripts/build_word.py --upgrade-file /path/to/note.md`: Upgrades any specific markdown note file directly.
  - Rebuilding with `python3 scripts/build_word.py --json '<payload>' --force` also completely upgrades the card.
- **Date-only refresh is opt-in, never a shortcut:** `--touch-only --word X` (or `--maintenance` during an audit pass) patches dates on disk and changes nothing else, so it never upgrades a legacy card. Use it only when the payload is unavailable and the content must stay untouched — never to skip a rebuild.
- **Dates & Status:** Preserves `created`. On user re-send, sets `modified=today`, `review=today`; `status` Done → In Progress (otherwise preserved). Under `--maintenance` (audit pass), keeps `review`/`status` unchanged.
- **Objective Errors vs Profile Violations — Both Are Fixed, Neither Is Asked:**
  - **Fix automatically and log:** Any objective error in any field (broken spelling/grammar, missing target word, wrong meaning of the word). If the word's assigned CEFR level itself is objectively wrong, rebuild at the correct level.
  - **Also fix automatically (no permission needed):** Example text that breaks the level profile — unnatural, off-level vocabulary, too long, not first person, disallowed contraction or slang. Write <= 3 level-compliant candidates internally, rank them, keep the best one, apply it with `--change-example` so the example audio regenerates. No narration — just fix it.
  - **Fix automatically (no permission needed):** any other rule violation found during the review — missing hook, missing `grammar_note` for a Phrasal Verb/Idiom, a line that breaks the Arabic text-direction rule, backtick overuse, an over-cap note list, a note field that fails the value test, a non-canonical structure.
  - The report lists what was fixed; it never asks the learner to approve a fix the skill already mandates (see "Teacher Authority").
- **Reporting:** None. Apply what is right, surface only warnings and errors, and finish with one short confirmation (see "Reporting — No Narration").

## Changing an Example

When an example is updated, sync all three places together:
1. Note Info block
2. Frontmatter `example`
3. Example audio file

Build with `--change-example` so the example audio is regenerated with the same engine/voice as the pronunciation file. When the change comes from your own teacher review (not a user request), apply it directly — do not ask for approval (see "Teacher Authority").

## Audio Generation

Rate from `profiles.json: audio.rate` for the word's level; CLI `--rate` overrides. Voice policy: **primary voice is `en-US-BrianNeural` (Brian, US male) — always tried first for every word**. Fallback chain when Brian is unreachable:
1. **edge-tts** — tries `en-US-BrianNeural` → `en-US-GuyNeural` → `en-US-EricNeural` → `en-US-RogerNeural` → `en-US-SteffanNeural` → `en-GB-RyanNeural` (3 attempts each).
2. **Google TTS US** — clear American English voice; automatic fallback when edge-tts is unavailable so audio never sounds robotic.

Each file synthesized once then repeated 5 times with 0.5 s silence via `ffmpeg`.
- Single-voice rule: both files of one word always share the same engine and voice. The engine is resolved once per run (`vocab_audio.resolve_engine()`) and both files are synthesized together via `vocab_audio.generate_audio_pair()` — never one file per engine. If either file needs (re)generation, both are regenerated so a stale file from an older engine can never be paired with a new file from a different voice. The resolved engine is reported in `warnings` and stdout.
- CLI `--dry-run` prints the rate.
- Audio modes: `--audio auto` (regenerate both if either is missing/changed/new, else keep both), `always` (both), `never` (none).
- Passing `--force` rebuilds the note without forcing audio regeneration unless `--audio always` is specified.

## Egyptian Arabic Content — Humanizer Integration

All Arabic content written in notes (translations, curiosity, etymology, common_mistakes, summary, when_used, grammar_note, cultural_context, synonym_contrast, important_notes, additional_notes, try_it) **must follow Egyptian Arabic (عامية مصرية) standards** as defined by the `humanizer-ar-egt` skill. This is not optional — it is the default for every field.

Mandatory rules (applied without needing to invoke the humanizer skill explicitly):
- **Vocabulary:** دلوقتي not الآن, عايز not أريد, ده/دي not هذا/هذه, مش not ليس, عشان not لأن/لكي, أوي not جداً, كمان not أيضاً.
- **Grammar:** Present tense with بـ prefix (بيفكر not يفكر). Future with هـ/حـ prefix (هيروح not سيذهب). Negation: ما+verb+ش or مش (ماعرفش, مش كويس).
- **Discourse:** Include يعني, بقى, خلاص, طب at natural junctions — never leave a paragraph particle-free.
- **Register:** Informal-professional (vocab card notes are not WhatsApp — no letter lengthening or هههه, but full vocabulary and grammar rules apply).
- **No MSA contamination:** No tanwin endings (ـاً ـٍ ـٌ), no formal openers (بالتأكيد, من المهم أن نلاحظ), no passive يُفعل patterns.
- **Fragmented rhythm:** Short punchy sentences. One idea per sentence. Vary length.

The `summary` field is always self-directed first-person Egyptian Arabic. The `curiosity` field is conversational Egyptian Arabic — light, direct, fun. All translations use Egyptian Arabic vocabulary, not MSA.

**Text direction is part of the writing, not an afterthought:** every Arabic line starts with Arabic (see "Arabic Text Direction (RTL Rule)"), so the card reads correctly right-to-left in Obsidian.

## Card Shape Decisions

The card is a fixed shape, not a style choice. These points settle every conflict between this skill, the vault rules, and the cards already living in `Vocabulary/`:

- **Info block layout:** the card head is the Obsidian card layout — `> [!quote] Context` callout, then `**Definition:**`, `**Example:**`, and `**IPA:** \`{ipa}\` • **Lookup:** [YouGlish](...) • [PlayPhrase](...)` — in that order on ALL cards. The first item is the `Context` callout. Legacy markdown tables (with a `Situation` row) are upgraded to this layout on the next rebuild.
- **Card head:** frontmatter, closing `---`, standalone `---` separator, blank line, then `## {Word} Info`. Content never starts before that separator.
- **`subject` is always `Vocabulary`** and **`category` is the part of speech** (`Noun`, `Verb`, etc.). `arabic` always sits directly before the link block (`youglish`, `playphrase`, `pronunciation`, `voice`). The script writes all of these.
- **No `title`, `description`, `order`, `recall`, `summary` or `tags` properties, no embedded local image files, no HTML, no Mermaid, no emoji in headings.** A card is markdown text plus its audio embeds and links.
- **Every fact lives in one place.** The frontmatter, the Info table and the notes each carry their own job and never restate one another; anything shared with another card is reached by wikilink.

## Notes Rendering

Every note field is rendered as an Obsidian callout with an Arabic title, in this canonical order. The callout type is fixed per field (it is the script that renders it — you only write the content):

| # | Field | Callout | Title |
|---|---|---|---|
| 1 | `word_translations` | `[!abstract]` | ترجمة الكلمة |
| 2 | `example_translation` | `[!abstract]` | ترجمة المثال |
| 3 | `when_used` | `[!info]` | إمتى بتتقال |
| 4 | `grammar_note` | `[!info]` | ملاحظة قواعد |
| 5 | `cultural_context` | `[!info]` | السياق الثقافي |
| 6 | `curiosity` | `[!tip]` | عارف إن؟ |
| 7 | `word_family` | `[!example]` | من نفس الأصل |
| 8 | `synonyms` | `[!example]` | مرادفات |
| 9 | `synonym_contrast` | `[!important]` | فرق عن كلمة قريبة |
| 10 | `antonyms` | `[!note]` | أضداد |
| 11 | `common_examples` | `[!example]` | أمثلة شائعة |
| 12 | `common_mistakes` | `[!warning]` | أخطاء شائعة |
| 13 | `important_notes` | `[!important]` | ملاحظات مهمة |
| 14 | `additional_notes` | `[!note]` | ملاحظات إضافية |
| 15 | `try_it` | `[!todo]` | جرّبها النهارده |

(`second_meaning` / `معنى تاني` is retired and deliberately absent: a second meaning is a second card, not a callout — see "One Card Per Meaning".)

Rules:
- Each callout is separated from the next by one blank line; empty fields are omitted entirely.
- `word_family` and `synonyms` render as bulleted wikilink lists (`- [[Form]]` / `- [[Synonym]]`) inside their callout — they connect the card into the Obsidian Graph View.
- `antonyms` render as a bulleted list of backticked items inside their callout.
- `common_examples` render as a bulleted list of **full everyday sentences** (see "Common Examples"), with the target word highlighted as `==word==` (the script highlights it for you when you do not).
- Prose fields keep their sentences; list items inside a prose field are separated by ` — `.
- `try_it` appears only if profile `try_it` is true.
- Backticks are used only for grammar patterns/IPA, never for casual English words; URLs and wikilinks are never in backticks; no emojis.

## Common Examples — Full Everyday Sentences

`common_examples` holds the **full everyday sentence** in which the word is actually used — not a two-word collocation.

- **Bad (collocation):** `mitigate risk`
- **Good (everyday sentence):** `We mitigate the risk before we launch.`

Why: a collocation teaches a pattern; a full sentence teaches the usage the learner will actually hear and repeat. The target word is highlighted inside the sentence with `==word==` (the script highlights it automatically; you may add more highlights yourself). Cap: `collocations_max` per profile. The callout is English by design, so its bullets may start with English.

## Reporting — No Narration

The learner has given the teacher full authority: whatever the teacher judges correct and suitable is applied directly. The learner reads the cards, not a narration of the work.

- **Do not produce a per-word report, a summary of what was changed, a table of decisions, or a "Judgment calls" list.**
- **Do surface:** warnings, errors, failed checks, and anything that needs the learner's attention (a word that could not be built, an audio engine fallback, a card whose content the script rejected).
- **Finish with one short confirmation** (e.g. "Done — 12 cards written.") and stop.

## Batch Processing

Process multiple words sequentially without asking or previewing; complete each word fully (root check + derivative card + audio) before proceeding to the next. No per-word report — see "Reporting — No Narration". Only warnings and errors are surfaced, followed by a short confirmation.

## Auditing Vault

- `audit` / review examples (e.g. `audit`, `راجع الأمثلة`): `scripts/audit_vault.py [--only examples|format|backticks|notes|all] [--word X] [--level X] [--letter Y] [--status S] [--limit N] [--out FILE]` summarizes worst offenders; changes nothing. READ-ONLY mode ends with `no_changes_made`. On existing notes every example finding, a missing `youglish` property, a missing `playphrase` property/row, a missing `pronunciation`/`voice` property, a legacy `Situation` row and a legacy frontmatter order are INFO proposals (`PROPOSAL:`), never violations — they are upgrade prompts for the next rebuild. Format proposals are grouped under `--only format`, example ones under `--only examples`, Arabic text-direction findings under `--only notes`.
- Review example for X / propose example (e.g. `review example X`, `راجع مثال X`): show 3 level-compliant candidate sentences with reasoning; change nothing. This is a *reporting* command the learner asked for — it does not authorize edits by itself.
- Change example X (e.g. `change example X`, `غيّر مثال X`): pick best candidate, apply with `--change-example`, regenerate example audio, and report old vs new.
- When an audit run is part of a repair task (not a pure report), fix the findings you can fix under "Teacher Authority" in the same run.

## Teacher Judgment Clause

Anything the profiles and explicit rules do not cover is decided by teacher judgment: choose what best serves the learner at this level, preserve invariants (first person example, concise, natural, canonical file structure, immutability, honesty). Decide, act, and stay quiet unless something warns or fails — never interrupt the user to ask trivial choices (see "Teacher Authority — Act, Don't Ask" and "Reporting — No Narration").

## Scripts Reference

- `scripts/build_word.py --json '<payload>' [--vault-root PATH] [--profiles PATH] [--rate RATE] [--show-profile LEVEL] [--check --word X] [--force] [--change-example] [--maintenance] [--touch-only] [--dry-run] [--audio {auto,always,never}] [--add-family-member --word ROOT --family-json '{...}' [--replace-form X]]`: Validates before writing to disk, creates temp audio then moves into place, writes note in canonical structure. Any existing note is always re-rendered through `vocab_io.render_note()`, so a rebuild refresh arrives with every build. `RESULT:` includes `profile_level`, `applied_limits`, `audio_rate`, `warnings`. `--check` is read-only, returning one JSON issue per line as `{code, severity, auto_fixable, message}`, with existing-note findings reported as INFO `PROPOSAL:` entries.
- `scripts/audit_vault.py`: READ-ONLY vault audit reporting issues across notes.
- `scripts/vocab_audio.py`: Audio engine — primary voice `en-US-BrianNeural` (Brian, US male) first; if Microsoft edge-tts is unavailable, automatically falls back to Google TTS US (`gtts`). Only Microsoft and Google TTS engines are used (all others removed). One shared engine/voice per run via `resolve_engine()` + `generate_audio_pair()`. Never call directly; invoked by `build_word.py`.

Reference documents:
- `references/note_template.md`: Canonical template structure.
- `references/example_abandon.md`: Complete end-to-end worked example.
- `references/adaptive_rules.md`: Value test, curiosity, grammar, try_it, example selection.
- `references/formatting_rules.md`: Backticks policy and table safety.

## Skill Editing Policy

All edits to this skill file (SKILL.md) and all reference documents are written in **English only**. Arabic appears only inside card content fields — never in skill instructions, rules, or code comments.
