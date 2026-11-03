# Vocab-Maker TODO

## 🎯 Current Task: Callout Notes Section, 5-Column Gang, Idiom/Phrase-Only PlayPhrase, Full-Sentence Common Examples, No Narration

### Objectives:
1. **Notes section as Obsidian callouts**: every note field renders as a callout with an Arabic title (`abstract` for translations, `info` for when_used/grammar/cultural, `tip` for curiosity, `note` for second meaning/antonyms/additional, `example` for word family/synonyms/common examples, `important` for synonym contrast/important notes, `warning` for common mistakes, `todo` for try_it).
2. **Word Gang view shows five columns**: `file.name`, `pronunciation`, `voice`, `image`, `review`.
3. **PlayPhrase only on Idiom and Phrase cards**: the frontmatter property AND the Info lookup link; single words carry no PlayPhrase at all.
4. **Common examples are full everyday sentences** with the target word highlighted as `==word==` — never bare two-word collocations (`check_common_examples` reports collocations).
5. **No narration**: the teacher applies what is right and stays quiet — only warnings/errors are surfaced, then one short confirmation. No per-word report, no judgment-calls list.

### Checklist:
- [x] `vocab_io.render_note()`: callout renderer for all note fields, `add_examples` with auto-highlight, `add_antonyms` bullets.
- [x] `vocab_io.render_note()`: PlayPhrase link only for Idiom/Phrase; Gang view with five columns.
- [x] Gang view `columnSize`: `pronunciation`/`voice` 120 px, `image` 90 px — the table no longer scrolls sideways.
- [x] `vocab_checks.check_info_table()`: PlayPhrase expectation depends on category (`playphrase_lookup_non_idiom`).
- [x] `vocab_checks.check_rtl_line_start()`: the English-by-design `أمثلة شائعة` callout is exempt.
- [x] `vocab_checks.check_backticks()`: structural-list exemption also matches the callout form.
- [x] `vocab_checks.check_common_examples()`: sentence length + target word check (warning).
- [x] `build_word.py`: run `check_common_examples` at build time.
- [x] `SKILL.md`: Notes Rendering callout map, Common Examples section, Reporting — No Narration, Gang columns, PlayPhrase rule, no per-word report.
- [x] `references/note_template.md`, `references/adaptive_rules.md`, `references/formatting_rules.md`: same rules.
- [x] Reference payloads: full-sentence `common_examples` in all four example JSONs; reference notes regenerated.
- [x] Tests: update PlayPhrase/card-shape/canonical-order assertions, add callout + full-sentence + RTL-exemption + collocation tests → 41/41 pass.

### Follow-up (not done yet):
- [ ] Repair the 117 existing vault cards that start a line with English (audit reports them as `rtl_line_start` INFO proposals; each needs a rebuild with Arabic-first lines).
- [ ] Bulk-upgrade the vault cards to the callout Notes shape + five-column Gang + no-PlayPhrase-on-single-words (`--upgrade` per word).
