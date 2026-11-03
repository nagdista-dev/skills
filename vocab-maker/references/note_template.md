# Obsidian Note Template

This is the exact structure `scripts/build_word.py` renders into `Vocabulary/{char}/{Word}.md`.
You don't need to write this file yourself — the script fills it in from your JSON — but understanding
the shape helps you write better `context`/`example`/`notes` content.

Numeric limits live in `profiles.json`; see `references/adaptive_rules.md` for how they apply.

````markdown
---
subject: Vocabulary
category: {Noun|Verb|Adjective|Adverb|Phrasal Verb|Idiom|Phrase|Preposition|Conjunction|Pronoun|Determiner|Interjection}
level: {A1|A2|B1|B2|C1|C2 — CEFR level, see profiles.json}
status: {Not Started|In Progress|Done}
arabic: "{All available Arabic translations for the word, separated by ' - '}"
ipa: "{the exact IPA string without backticks, e.g. /əˈbændən/}"
chunks: "{the word split into memorable hyphenated parts, e.g. a-ban-don, or s-aw for 1-syllable words — always non-empty}"
definition: "{the exact Definition sentence from the Info block — one source of truth, rendered in both places}"
example: "{the exact Example sentence from the Info table}"
pronunciation: "{[[{Word}_pronunciation.mp3]] — script-derived, never typed by hand}"
voice: "{[[{word}_example.mp3]] — script-derived, never typed by hand}"
youglish: "{https://youglish.com/pronounce/{word_with_underscores}/english/us — script-derived, never typed by hand}"
playphrase: "{https://www.playphrase.me/#/search?q={words_with_plus}=2&language=en — script-derived, never typed by hand, present for Idiom and Phrase categories only}"
image: "{https://www.google.com/search?q=<QUERY>&tbm=isch&tbs=itp:clipart — Google Images search link derived per category & modifier rules}"
char: {char}
day: {English weekday of the created date — automatic, e.g. Sunday}
month: {English month name — automatic, e.g. August}
created: {YYYY-MM-DD (day the word was created — set automatically by the script)}
modified: {YYYY-MM-DD (equals created on creation, refreshed on every later edit; --maintenance sets modified=today only)}
review: {YYYY-MM-DD (equals created on creation — you can change it freely at any time; re-send sets review=today unless --maintenance)}
---

---

## {Word} Info

> [!quote] Context
> {context with ==target_word== highlighted}

**Definition:** {definition}

**Example:** {example}

**IPA:** `{ipa}` &nbsp;•&nbsp; **Lookup:** [YouGlish](https://youglish.com/pronounce/{word_with_underscores}/english/us) &nbsp;•&nbsp; [PlayPhrase](https://www.playphrase.me/#/search?q={words_with_plus}=2&language=en)

*(the PlayPhrase link appears ONLY on Idiom and Phrase cards)*

---

## {Word} Pronunciation

![[{Word}_pronunciation.mp3]]

---

## {Word} Example

![[{word}_example.mp3]]

---

## {Word} Notes

> [!abstract] ترجمة الكلمة
> {notes.word_translations (all on one line, separated by " — ")}

> [!abstract] ترجمة المثال
> {notes.example_translation (example translation in Egyptian Arabic)}

> [!info] إمتى بتتقال
> {notes.when_used (when value: register or context restrictions)}

> [!info] ملاحظة قواعد
> {notes.grammar_note (required when type is Phrasal Verb or Idiom; otherwise only when needed to prevent a real error)}

> [!info] السياق الثقافي
> {notes.cultural_context (when value: contrast between American English and Egyptian natural expression)}

> [!tip] عارف إن؟
> {notes.curiosity (required hook along with common_mistakes: verified fun fact; do not repeat etymology)}

> [!example] من نفس الأصل
> - [[{Derivative 1}]]
> - [[{Derivative 2}]]

> [!example] مرادفات
> - [[{Synonym 1}]]
> - [[{Synonym 2}]]

> [!important] فرق عن كلمة قريبة
> {notes.synonym_contrast (optional: practical distinction with one synonym; compared word wrapped in wikilink [[word]]; counts toward extras_max)}

> [!note] أضداد
> - `{antonym}`

> [!example] أمثلة شائعة
> - {full everyday sentence with the target word highlighted, e.g. I ==dispatch== the order before noon.}

> [!warning] أخطاء شائعة
> {notes.common_mistakes (optional: hook)}

> [!important] ملاحظات مهمة
> {notes.important_notes (optional: never use this to announce that the word has a second meaning — that other meaning belongs to another card)}

> [!note] ملاحظات إضافية
> {notes.additional_notes (optional)}

> [!todo] جرّبها النهارده
> {notes.try_it (optional: small daily task; rendered only if profile.try_it is true)}

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

**Section headings must be expressive — never the bare word.** Each `##` heading always carries a descriptor (`{Word} Info`, `{Word} Pronunciation`, `{Word} Example`, `{Word} Notes`). A heading that is just the bare word (`## Contiguous`) is forbidden — the reader must know what the section shows from the title alone.

**Every Arabic line starts with Arabic** (the card is read right-to-left). Open with an Arabic frame word and let the English follow inline: `كلمة dispatch بتاخد مفعول مباشر دايماً: dispatch an order.` — never `dispatch takes ...`. The rule applies inside callouts and list items too.

Core always: `word_translations`, `example_translation`; hook at least one: `curiosity` (`عارف إن؟`) or `common_mistakes` (`أخطاء شائعة`) (pick what helps most). `grammar_note` (`ملاحظة قواعد`) required for Phrasal Verb/Idiom, otherwise only when it prevents a real error. All other lines appear only if they pass the value test; empty fields are omitted. `try_it` (`جرّبها النهارده`) appears only when profile `try_it` is true (dropped with warning otherwise).

Every note field is rendered as an Obsidian callout with the Arabic title shown above, separated by one blank line, so the card reads as one clean scannable column. `common_examples` holds full everyday sentences (not two-word collocations) with the target word highlighted as `==word==`.

Naming rules:
- `{Word}` = Title-Case per token (e.g. `Abandon`, `Take Out`) — used for filename, word headings, pronunciation audio `![[{Word}_pronunciation.mp3]]`, and wikilinks.
- `{word}` = all lowercase (e.g. `abandon`, `take out`) — used for the example audio filename `![[{word}_example.mp3]]`; YouGlish URL uses lowercase with `_` for spaces (`{word_with_underscores}`); PlayPhrase URL uses lowercase with `+` for spaces (`{words_with_plus}`).
- `{char}` = first letter uppercase (e.g. `A`, `T`).

Property rules:
- `youglish` is the same link as the Info table's YouGlish row, kept as a property so the vault's bases and the properties panel can reach it. Script-owned: derived from the word and never passed by the agent or typed by hand.
- `playphrase` is kept as a frontmatter property right under `youglish` ONLY on **Idiom** and **Phrase** cards (derived from the word, lowercase, spaces replaced with `+`). On other word categories, it is omitted from frontmatter. (In the Info table, the PlayPhrase row is available for video lookup).
- `pronunciation` is the same file as the Pronunciation section embed (`[[{Word}_pronunciation.mp3]]`, Title-Case), kept as a property grouped with the other links. Script-owned: derived from the word, never passed by the agent or typed by hand.
- `voice` is the same file as the Example section embed (`[[{word}_example.mp3]]`, all lowercase), kept as a property grouped with the other links. Script-owned: derived from the word, never passed by the agent or typed by hand.
- `subject` is always `Vocabulary`.
- `category` is the part of speech (`Noun`, `Verb`, `Adjective`, `Adverb`, `Phrasal Verb`, `Idiom`, `Phrase`, etc.).
- `context` is displayed in the Info table's `Context` row (not in frontmatter properties). Must be a dramatic scene in English third person and MUST use the target word. Cards written before this label was fixed carry `Situation` and are upgraded the next time they are rebuilt.
- `ipa` is stored as a frontmatter property AND displayed as the Info table's `IPA` row (wrapped in backticks in the table, bare in frontmatter).
- `chunks` is stored as a frontmatter property: the word split into memorable hyphenated parts (e.g. `im-poss-ible`, `a-ban-don`) based on memorability, not syllables; empty if unsplittable.
- `definition` is stored as a frontmatter property AND displayed as the Info block's `**Definition:**` line — the exact same sentence in both places, written once in the payload so it can never drift (same pattern as `example`).
- `arabic` lists all available Arabic translations for the word, separated by ` - ` (dash with spaces).

