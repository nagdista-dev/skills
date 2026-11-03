# Adaptive Rules — How to Write a Card that Teaches

Numeric limits are defined in `profiles.json`. The CEFR level is decided before any other field; its profile governs the example, definition, context, audio rate, and notes. Style hints and vocabulary ceiling (other words at or below the word's level) are your responsibility as a teacher, not machine-checked.

## Context — Dramatic Scene Rule

The context line (the Info table's `Context` row; frontmatter `context` property; payload key `context`, with `situation` honored as a legacy alias) is third person English and must:

1. **Use the target word.** The word being taught MUST appear in the context sentence and be highlighted with `==word==`. This is mandatory — no exceptions. The learner sees the word in a real situation, not just the example.
2. **Be a dramatic vivid scene** — like a moment from a film or story that freezes in the mind. The scene must create a strong mental image: tension, surprise, danger, emotion, or a striking moment. Generic filler sentences ("Ahmed uses this word at work") are strictly forbidden.
3. **Match the example moment.** The context describes the exact same moment or situation as the example sentence.
4. **Be level-appropriate in vocabulary and complexity**, but not in intensity — even A1 contexts can be vivid and cinematic.
5. **Real-Life Everyday Grounding (الحياة اليومية/العامية):** The scene must come from relatable everyday life (social interactions, family/friends, work conversations, home situations, daily dilemmas). It must represent the **single most common / frequent real-world usage of the word**, ensuring memorization directly yields practical fluency.

**Level intensity guide:**
- A1/A2: Concrete sensory images — hunger, fear, cold, someone running, something breaking. Simple but vivid.
- B1/B2: Interpersonal tension, stakes, decisions — a job interview, a confrontation, a turning point.
- C1/C2: Complex moral/professional tension — a boardroom crisis, an ethical dilemma, a high-stakes reveal.

**Bad context (generic):** `Omar starts every morning with a glass of water before doing anything else.`
**Good context (dramatic):** `Omar's hands were shaking — he grabbed the only glass of water on the table and drank it all in one go.`

**Bad context (word missing):** `She walked into the building, not knowing what was waiting.`
**Good context (word used):** `She abandoned her phone on the seat and walked into the building — there was no turning back now.`

Within `context.max_words` per profile.

## Arabic Text Direction — Arabic-First Lines

Arabic notes are read right-to-left. A line that starts with English text flips the paragraph direction and the mixed Arabic/English line becomes unreadable, so **every line of Arabic prose starts with Arabic** and the English follows after it.

- **Bad:** `dispatch takes a direct object always: dispatch an order.`
- **Good:** `كلمة dispatch بتاخد مفعول مباشر دايماً: dispatch an order.`

Rules:
- Open with an Arabic frame word — `كلمة X`, `فعل X`, `الكلمة دي`, `في الاستخدام ده`, `معنى X` — then let the English follow inline.
- Never open a line with an English word, phrase, or quote (`I'm dispatching it now` belongs after an Arabic start, e.g. `... والوقت ممكن ييجي قبلها: I'm dispatching it now.`).
- The rule applies inside callouts (`> [!tip] عارف إن؟`) and inside list items too — a bullet whose text opens with English is a violation.
- English phrases and grammar patterns stay in backticks per `formatting_rules.md`; the backtick does not exempt the line-start rule.
- Exception: the `أمثلة شائعة` (common examples) callout is English by design — its full English sentences may start with English.
- The card's English sections (Definition, Example, Context, IPA) are English-only and unaffected.

Enforced by `scripts/vocab_checks.py:check_rtl_line_start` — a payload that opens a line with English is rejected at build time (`rtl_line_start`); the audit reports it as an INFO proposal on existing cards, fixed on the next rebuild. Fix it yourself, no permission needed (see "Teacher Authority" in `SKILL.md`).

## Value Test

A note field is written only if a learner at this level would use the word differently, avoid a real mistake, or remember it better because of it. Otherwise omit it. Never write a field just because it exists. Specificity test: if the note still reads fine after swapping in a different word, delete it. Generic filler like "this word is important" or "it is used a lot" is strictly prohibited.

- **Core always:** `word_translations`, `example_translation`.
- **Hook at least one:** `curiosity` or `common_mistakes` — pick what helps this word most; two are allowed if both are genuinely good.
- **`grammar_note` required** for Phrasal Verb/Idiom; otherwise write it only when it prevents a real error.
- **Optional judged by value test:** `when_used` only when register/context restricted (formal vs casual, spoken vs written, with whom); `cultural_context` only when real American/Egyptian contrast or trap exists; `etymology` only when it gives a real memory hook and only confident claims (if unsure, omit and report uncertainty in chat, never hedging inside the note; a sound-alike mnemonic is allowed only if clearly labelled as a trick, never as actual origin); `synonyms`, `synonym_contrast`, `antonyms`, `common_examples`, `word_family`, `important_notes`, `additional_notes`, `try_it`.

Non-core count: number of non-empty note fields excluding `word_translations`, `example_translation` (core) and the two structural lists `word_family` (capped by `family_max`) and `common_examples` (capped by `collocations_max`) after any `try_it` drop (when profile `try_it` is false). `synonym_contrast` is prose and DOES count toward `extras_max`. Must be <= `extras_max` per level profile.

Tone: light, conversational Egyptian Arabic, friendly teacher; no lecturing; no emojis. Higher levels get more nuance (register, collocations, near-synonym contrast); lower levels get fewer, simpler notes. Warn when a note has <3 words or two notes overlap >80% tokens.

## Teacher Authority — Act, Don't Ask

You are the learner's private English teacher. Everything the rules already decide, you decide yourself and apply immediately:

- Fix objective errors (broken spelling/grammar, missing target word, wrong meaning) and rule violations (profile-breaking example, missing hook, missing `grammar_note` for a Phrasal Verb/Idiom, an Arabic line that starts with English, backtick overuse, over-cap note lists, non-canonical structure).
- When you rewrite an example, pick the best candidate yourself (write 3, rank, keep one — candidates never enter the note), apply it with `--change-example`, and let the example audio regenerate.
- When the assigned CEFR level is objectively wrong, rebuild the card at the correct level.
- Log every fix in the final report ("Fixed: ...") instead of asking for approval.

Only stop and ask when the request itself does not identify the word/file, or when the action is destructive and outside the skill's scope.

## Example — The Core Rule
 
Must be a sentence grounded in **everyday colloquial life (الحياة اليومية/العامية)** representing the **word's single most common / frequent everyday usage**. By memorizing the example sentence, the learner memorizes the exact, practical expression native speakers use in real life — hitting two birds with one stone.

Procedure: write 3 candidates, discard any failing a hard gate, rank survivors, keep one. Do not put candidates in the note.

**Hard gates** (enforced on new/changed only; existing examples stay immutable unless fixing an objective error):
- First person: starts with `I`, `I'm`, `I've`, `I'd`, `I'll`, `I can't`, `I don't`, `My`; `We`/`Our` only with non-empty `example_person_fallback` (one-line reason recorded).
- At most the level's `example.max_words`; contractions and slang within the level's ceiling (`basic` = only basic set, `standard` = both sets); `slang` false forbids slang terms.
- Contains the target word; every other word at or below the word's level; no filler `yesterday`/`today`/`tomorrow` unless the meaning requires it.

**Ranking:** 
1. Most natural/common in real speech.
2. Most sayable about the learner's own life (use `style_hint` as a nudge, not a rigid rule).
3. Clear meaning together with the context line (the context carries the situation and the explanation).
4. Short and easy to recall.

Invariants: the context line describes the exact same moment as the example; definition is one sentence within `definition.max_words`; context is within `context.max_words`. A changed example updates audio synchronously.

## Curiosity

Required as part of the hook. Written in Egyptian Arabic: fun, true, checkable, within `max_sentences_per_note`, and must not repeat etymology. Never invent a fact. Allowed types: surprising usage quirk, trap/false friend for Arabic speakers, odd collocation, word-family surprise, cultural/history nugget, sound/spelling trick, or tiny story. If no verified fact exists, use a usage quirk or Arabic-speaker trap. English terms inside it are written as plain text (never backticked) unless they are a grammar pattern — see `formatting_rules.md`. One paragraph, light tone.

## Grammar Note

Write `grammar_note` only when genuinely useful, never filler. By word type:
- Verb: irregular forms, transitivity, common preposition errors.
- Noun: countable vs uncountable, irregular plurals.
- Adjective: preposition patterns, gradability.
- Adverb: position in sentence.
- Phrasal Verb (required): separable vs inseparable, pronoun placement (e.g. `turn it off`), literal vs figurative.
- Idiom (required): literal vs figurative, fixed form, register.
- Phrase: fixed/semi-fixed structure, register.
- Preposition / Conjunction / Determiner / Pronoun / Interjection: syntax pattern, punctuation/position, tone.
Omit for regular words with predictable grammar.

## One Card Per Meaning

A word with more than one distinct meaning never gets one card that teaches both. Each meaning gets its own complete card, and they cross-link under `word_family`.

**Run the sense scan on every build and every review.** List the senses the dictionaries give before writing any field. Every sense that passes the distinct-meaning test is built in the same run — a split is never postponed, and a definition/example never carries two senses (if the definition needs "or" to join two separate translations, it is two cards). Never write a line that only announces another meaning; write its card instead.

- **Trigger:** the meaning you were about to hide in a second sentence — historically `second_meaning`, or a `common_mistakes`/`important_notes` line that only says "this word has two meanings". That is the signal to write a second card instead. The field `second_meaning` is retired; never write it on a new or rebuilt card.
- **Title tag:** one word in parentheses, right after the base title. Part of speech when that is what differs (`Water (N)`, `Water (V)`), the meaning when the part of speech is the same (`Beam (Smile)` / `Beam (Shine)`, `Check Out (Hotel)` / `Check Out (Inspect)`, `Charge (Accuse)`). One word only — the script strips the tag to reach the base word for audio, YouGlish and PlayPhrase.
- **Distinct-meaning test:** different Arabic translation AND a different everyday situation/pattern the learner must practise separately. Two readings of one live situation, or a sense a learner would not mix up, stay on the first card.
- **No half cards:** the new card gets its own `definition`, `context`, `example`, IPA, pronunciation audio, example audio, hooks, gang base and family links — never a stub pointing at the other card.
- **Card roles are picked in the payload, not in the title alone:** the most frequent everyday meaning owns the most common usage and its example; the other card is built to the same standard, not as a footnote.

## Word Family and Derivatives

Include `word_family` only when at least one other-part-of-speech form from the same root is genuinely common and useful for this word. If none is worth teaching, omit the section entirely.
- Each entry is an object: `{form, type, arabic, example}`, rendered text only, no audio.
- Entry type must be one of the canonical English types (`Noun`, `Verb`, `Adjective`, `Adverb`, etc.).
- Capped by profile `family_max` (structural limit, warning). Never pad with obscure derivations.

**Derivative and Non-Root Word Rule:**
When the user requests a non-root word (derivative: noun, adjective, adverb):
1. **Root verification & creation:** Check if the root word's note exists in the vault. If the root does NOT exist, create the complete vocabulary card for the ROOT word first.
2. **Derivative card creation:** Create the complete, separate vocabulary card for the requested derivative word (with its own note, pronunciation audio, and example audio).
3. **Independent cards:** Both words get their own separate cards; derivatives are NEVER collapsed into or suppressed by the root note.
4. **Cross-referencing:** Both cards can reference each other under their `word_family` lists.

## Collocations and Everyday Sentences

`common_examples` holds the **full everyday sentence** in which the word is actually used — never a bare two-word collocation.

- **Bad:** `mitigate risk`
- **Good:** `We mitigate the risk before we launch.`

The target word is highlighted inside the sentence with `==word==` (the renderer highlights it automatically when you do not). The sentence must be one the learner would actually hear in daily life — everyday, natural, no jargon. May contain multiple entries only when the word is genuinely used in several everyday situations. If there is just one obvious usage, keep it short or omit — never pad. Capped at profile `collocations_max` (structural limit, warning). Does not count toward `extras_max`. The callout is English by design, so its bullets may start with English (the Arabic-first rule does not apply there).

## Synonym Contrast

Write `synonym_contrast` only when the difference with one near-synonym actually matters (register, degree, context). Write one or two Egyptian Arabic sentences contrasting with ONE synonym, not every possible one. It must not repeat `common_mistakes` when that hook already covers the same contrast: one idea, one note. Counts toward `extras_max` like other prose notes.

## Try It

One line with a concrete micro-task to use the word today (e.g., saying the example about the learner's own situation). Simple Egyptian Arabic. Rendered only if profile `try_it` is true; if a payload provides it while the profile says false, it is dropped with a warning.

## Notes Depth and Register

Follow the level profile in `profiles.json` for `max_sentences_per_note`, `extras_max`, `try_it`, and `arabic_register` (`very simple`, `simple`, `normal`, `rich`). Pick optional notes strictly based on the value test for THIS word.
