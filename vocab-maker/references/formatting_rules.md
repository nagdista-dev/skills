# Formatting Rules — Backticks and Table Safety

The purpose of backticks (`` ` ``) in Markdown is to format code or syntax structures. In vocabulary notes, overusing backticks on every English word is visually annoying, distracting, and clutters the Obsidian reading experience. **Backticks must be used sparingly and only in specific, necessary places.**

## USE Backticks ONLY For

- **Grammar formulas and sentence patterns:** e.g. `subject + verb`, `give up + on someone`, `turn + object + off`.
- **Specific morphological / syntax tokens:** e.g. suffixes `-able`, `-ment`, prefixes `un-`, `re-`.
- **IPA pronunciation string:** e.g. `/əˈbændən/`.

## DO NOT Use Backticks For

- **Casual English words or mentions:** When an English word is mentioned naturally in an Arabic explanation or note, do NOT wrap it in backticks. Let it sit cleanly in plain text.
- **Wikilinked items:** `word_family` and `synonyms` use Obsidian wikilinks (`- [[Form]]`, `- [[Synonym]]`), never backticks.
- **Contrasted words:** Comparisons in `synonym_contrast` wrap the compared word in wikilinks (e.g. `[[leave]]`), never backticks.
- **Full English sentences:** Sentences inside `additional_notes`, `try_it`, or notes should be in natural text or regular quotes (`"..."`), never backticks.
- **Proper nouns and common terms:** Terms listed in `plain_terms` (`American English`, `British English`, `English`, `Egyptian`, `Arabic`, `OK`, `CEFR`, `IPA`, `TV`, `YouTube`, `Google`, `WhatsApp`, etc.).
- **Headings, frontmatter, or Info block rows** (except the IPA value).
- **Arabic script:** Never place Arabic letters inside backticks.
- **The same span twice:** Never repeat the same backtick span in a single paragraph.

## Callout Policy

Every note field is rendered as an Obsidian callout (`> [!type] Arabic Title`) so the card reads as one clean, scannable column:

| Field | Callout | Title |
|---|---|---|
| `word_translations` | `[!abstract]` | ترجمة الكلمة |
| `example_translation` | `[!abstract]` | ترجمة المثال |
| `when_used` | `[!info]` | إمتى بتتقال |
| `grammar_note` | `[!info]` | ملاحظة قواعد |
| `cultural_context` | `[!info]` | السياق الثقافي |
| `curiosity` | `[!tip]` | عارف إن؟ |
| `word_family` | `[!example]` | من نفس الأصل |
| `synonyms` | `[!example]` | مرادفات |
| `synonym_contrast` | `[!important]` | فرق عن كلمة قريبة |
| `antonyms` | `[!note]` | أضداد |
| `common_examples` | `[!example]` | أمثلة شائعة |
| `common_mistakes` | `[!warning]` | أخطاء شائعة |
| `important_notes` | `[!important]` | ملاحظات مهمة |
| `additional_notes` | `[!note]` | ملاحظات إضافية |
| `try_it` | `[!todo]` | جرّبها النهارده |

Callout types come from the Obsidian set (`note`, `abstract`, `info`, `todo`, `tip`, `important`, `warning`, `example`). The agent never types the callout markup — it writes the content and the renderer produces the callout.

## Text Direction — Do Not Start a Line With English

Arabic prose is read right-to-left. A line that opens with English text flips the paragraph direction and breaks the reading flow:

- **Bad:** `dispatch takes a direct object always: dispatch an order.`
- **Good:** `كلمة dispatch بتاخد مفعول مباشر دايماً: dispatch an order.`

Start every Arabic line with an Arabic word (`كلمة X`, `فعل X`, `الكلمة دي`, `معنى X`) and let the English follow inline — including inside callouts and list items. Backticks do not exempt the rule.

Prefer clean, natural prose. A card with minimal backticks is far more readable and elegant.

## Machine Checks (Enforced by `scripts/vocab_checks.py`)

- **ERROR:**
  - Backtick in any frontmatter value.
  - Backtick in a heading line (`## ...`).
  - Backtick in an Info table cell other than the IPA row (`| IPA | \`{ipa}\` |`).
  - A line in the Notes block starting with Latin text (`rtl_line_start`).
- **WARNING:**
  - Span text matches a `plain_terms` entry (case-insensitive).
  - The same normalized span appears twice in one prose paragraph.
  - More than `backticks_max_per_paragraph` spans in a prose paragraph.
  - A span containing Arabic letters.
  - Single-word backtick span wrapping an unallowed word in prose notes.

The `unwrapped_english_phrase` check is disabled on purpose — natural English phrases inside Arabic prose are written unwrapped.

