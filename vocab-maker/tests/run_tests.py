#!/usr/bin/env python3
"""
Characterization tests for vocab-maker skill.
Runs against temp fake vaults, stdlib unittest only.
"""
import unittest
import json
import tempfile
import shutil
import subprocess
import hashlib
from pathlib import Path
import os
import re

SKILL_ROOT = Path(__file__).resolve().parent.parent
BUILD = SKILL_ROOT / "scripts" / "build_word.py"
AUDIT = SKILL_ROOT / "scripts" / "audit_vault.py"
VOCAB_CHECKS = SKILL_ROOT / "scripts" / "vocab_checks.py"

def run_cmd(args, cwd=None):
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return result

def sha256_file(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

def make_payload(word="TestWord", level="A1", example=None, extra_notes=None, **overrides):
    # Example must contain target word (or its inflected form) per 2.1
    if example is None:
        # Generate example that contains the word
        w_low = word.lower()
        example = f"I {w_low} this now."
    base = {
        "word": word,
        "category": "Noun",
        "type": "Noun",
        "level": level,
        "ipa": "/tɛst/",
        "chunks": "",
        "definition": "A simple test.",
        "arabic": "اختبار",
        "context": "I was nervous before the exam and needed to test my knowledge.",
        "situation": "I was nervous before the exam and needed to test my knowledge.",
        "example": example,
        "notes": {
            "word_translations": ["اختبار"],
            "example_translation": "بجرب الاختبار",
            "curiosity": "كلمة `test` نفس الحروف اسم وفعل وده بيخدع"
        }
    }
    if extra_notes:
        base["notes"].update(extra_notes)
    base.update(overrides)
    return base

class VocabMakerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir(parents=True, exist_ok=True)
        # Ensure skill uses this vault via --vault-root, not config
        self.maxDiff = None

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, payload, extra_args=None):
        extra_args = extra_args or []
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            fname = f.name
        args = ["python3", str(BUILD), "--json-file", fname, "--vault-root", str(self.vault)] + extra_args
        result = run_cmd(args)
        Path(fname).unlink(missing_ok=True)
        return result

    # 1. new note
    def test_new_note(self):
        payload = make_payload(word="NewWord", level="A1")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "N" / "Newword.md"
        self.assertTrue(note.exists())
        self.assertIn("RESULT:", r.stdout)
        data = json.loads(r.stdout.split("RESULT:")[1].strip())
        self.assertTrue(data["created"])

    # 2. dry-run writes nothing
    def test_dry_run_writes_nothing(self):
        payload = make_payload(word="DryRunWord", level="A1")
        r = self.build(payload, ["--dry-run", "--audio", "never"])
        self.assertEqual(r.returncode, 0)
        note = self.vault / "Vocabulary" / "D" / "Dryrunword.md"
        self.assertFalse(note.exists())

    # 3. validation failures happen before any file write
    def test_validation_before_write(self):
        # Create a valid note first
        payload_ok = make_payload(word="ValidBefore", level="A1", example="I validbefore this now.")
        r = self.build(payload_ok, ["--audio", "never"])
        self.assertEqual(r.returncode, 0)
        note = self.vault / "Vocabulary" / "V" / "Validbefore.md"
        sha_before = sha256_file(note)
        # Now try invalid arabic (contains Latin) — should fail before write, file unchanged
        payload_bad = make_payload(word="ValidBefore", level="A1", example="I validbefore this now.", arabic="invalid latin")
        r2 = self.build(payload_bad, ["--audio", "never"])
        self.assertNotEqual(r2.returncode, 0)
        sha_after = sha256_file(note)
        self.assertEqual(sha_before, sha_after)

    # 4. re-send existing word status rule
    def test_resend_status_rule(self):
        payload = make_payload(word="StatusWord", level="A1")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0)
        note = self.vault / "Vocabulary" / "S" / "Statusword.md"
        # Patch to Done
        text = note.read_text(encoding="utf-8")
        text = re.sub(r"^status:.*", "status: Done", text, flags=re.MULTILINE)
        note.write_text(text, encoding="utf-8")
        created_before = re.search(r"^created: (.*)", text, re.MULTILINE).group(1)
        # Re-send
        r2 = self.build(payload, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0)
        new_text = note.read_text(encoding="utf-8")
        self.assertIn("status: In Progress", new_text)
        self.assertIn(f"created: {created_before}", new_text)
        # review = today
        import datetime
        today = datetime.date.today().isoformat()
        self.assertIn(f"review: {today}", new_text)

        # In Progress stays In Progress
        payload2 = make_payload(word="StatusWord2", level="A1")
        self.build(payload2, ["--audio", "never"])
        note2 = self.vault / "Vocabulary" / "S" / "Statusword2.md"
        txt = note2.read_text(encoding="utf-8")
        txt = re.sub(r"^status:.*", "status: In Progress", txt, flags=re.MULTILINE)
        note2.write_text(txt, encoding="utf-8")
        self.build(payload2, ["--audio", "never"])
        self.assertIn("status: In Progress", note2.read_text(encoding="utf-8"))

        # Not Started stays Not Started
        payload3 = make_payload(word="StatusWord3", level="A1")
        self.build(payload3, ["--audio", "never"])
        note3 = self.vault / "Vocabulary" / "S" / "Statusword3.md"
        self.assertIn("status: Not Started", note3.read_text(encoding="utf-8"))
        self.build(payload3, ["--audio", "never"])
        self.assertIn("status: Not Started", note3.read_text(encoding="utf-8"))

    # 5. --maintenance
    def test_maintenance(self):
        payload = make_payload(word="MaintWord", level="A1")
        self.build(payload, ["--audio", "never"])
        note = self.vault / "Vocabulary" / "M" / "Maintword.md"
        txt = note.read_text(encoding="utf-8")
        txt = re.sub(r"^status:.*", "status: Done", txt, flags=re.MULTILINE)
        txt = re.sub(r"^modified:.*", "modified: 2026-09-20", txt, flags=re.MULTILINE)
        txt = re.sub(r"^review:.*", "review: 2026-09-23", txt, flags=re.MULTILINE)
        note.write_text(txt, encoding="utf-8")
        # Change payload slightly
        payload2 = make_payload(word="MaintWord", level="A1", definition="A changed definition that is still short.")
        r = self.build(payload2, ["--audio", "never", "--maintenance", "--force"])
        self.assertEqual(r.returncode, 0)
        new_txt = note.read_text(encoding="utf-8")
        self.assertIn("status: Done", new_txt)
        self.assertIn("review: 2026-09-23", new_txt)
        import datetime
        today = datetime.date.today().isoformat()
        self.assertIn(f"modified: {today}", new_txt)

    # 6. --touch-only
    def test_touch_only(self):
        payload = make_payload(word="TouchWord", level="A1")
        self.build(payload, ["--audio", "never"])
        note = self.vault / "Vocabulary" / "T" / "Touchword.md"
        txt = note.read_text(encoding="utf-8")
        txt = re.sub(r"^status:.*", "status: Done", txt, flags=re.MULTILINE)
        note.write_text(txt, encoding="utf-8")
        # Create dummy audio at correct paths (under vault_root/Media/)
        pron = self.vault / "Media" / "Pronunciation" / "Touchword_pronunciation.mp3"
        ex = self.vault / "Media" / "Examples" / "touchword_example.mp3"
        pron.parent.mkdir(parents=True, exist_ok=True)
        ex.parent.mkdir(parents=True, exist_ok=True)
        pron.write_bytes(b"dummy")
        ex.write_bytes(b"dummy")
        sha_p_before = sha256_file(pron)
        sha_e_before = sha256_file(ex)
        content_before = note.read_text(encoding="utf-8")
        # touch-only via --word
        r = run_cmd(["python3", str(BUILD), "--touch-only", "--word", "TouchWord", "--vault-root", str(self.vault)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue("no audio" in r.stdout.lower() or "skipped" in r.stdout.lower() or "touch" in r.stdout.lower())
        sha_p_after = sha256_file(pron)
        sha_e_after = sha256_file(ex)
        self.assertEqual(sha_p_before, sha_p_after)
        self.assertEqual(sha_e_before, sha_e_after)
        # also test --touch-only with payload
        payload2 = make_payload(word="TouchWord", level="A1")
        r2 = self.build(payload2, ["--touch-only", "--audio", "never"])
        self.assertEqual(r2.returncode, 0)

    # 7. --change-example gating
    def test_change_example_gating(self):
        payload = make_payload(word="ChangeGate", level="A1")
        self.build(payload, ["--audio", "never"])
        payload2 = make_payload(word="ChangeGate", level="A1", example="I changegate my test now.")
        r = self.build(payload2, ["--audio", "never"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("pass --change-example", r.stderr)
        r2 = self.build(payload2, ["--audio", "never", "--change-example"])
        self.assertEqual(r2.returncode, 0)

    # 8. word normalization and forbidden characters
    def test_word_normalization_and_forbidden(self):
        payload = make_payload(word="  take   out  ", level="A2", example="I take my food out now.", extra_notes={"grammar_note": "الفعل ده منفصل: `take it out`"})
        payload["type"] = "Phrasal Verb"
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0)
        note = self.vault / "Vocabulary" / "T" / "Take Out.md"
        self.assertTrue(note.exists())
        # Forbidden char
        payload2 = make_payload(word="bad/word", level="A1")
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("forbidden character", r2.stderr)

    # All-caps acronyms keep their caps so the vault's IPO/TV/CEO files stay reachable
    def test_acronym_case_preserved(self):
        payload = make_payload(word="IPO", level="C1", example="I read about the IPO this week.")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "I" / "IPO.md"
        self.assertTrue(note.exists(), "all-caps acronym must keep its caps")
        text = note.read_text(encoding="utf-8")
        self.assertIn("## IPO Info", text)
        self.assertIn('pronunciation: "[[IPO_pronunciation.mp3]]"', text)
        self.assertIn('voice: "[[ipo_example.mp3]]"', text)
        self.assertIn("https://youglish.com/pronounce/ipo/english/us", text)
        # Mixed-case words are still Title-Cased (no regression)
        payload2 = make_payload(word="LegacyWord", level="A1", example="I legacyword my work today.")
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertTrue((self.vault / "Vocabulary" / "L" / "Legacyword.md").exists())

    # 9. A1 vs C1 profile limits
    def test_profile_limits(self):
        # A1 max 7, target 4-6, basic only, slang false
        payload_a1_ok = make_payload(word="A1Ok", level="A1", example="I A1Ok this now.")
        r = self.build(payload_a1_ok, ["--dry-run", "--audio", "never"])
        self.assertEqual(r.returncode, 0)
        # A1 9 words should fail
        payload_a1_fail = make_payload(word="A1Fail", level="A1", example="I really love a1fail water every single morning now")
        r2 = self.build(payload_a1_fail, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r2.returncode, 0)
        # A1 with I've should fail (standard not allowed)
        payload_a1_ive = make_payload(word="A1Ive", level="A1", example="I've tested a1ive now.")
        r3 = self.build(payload_a1_ive, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r3.returncode, 0)
        # A1 with I'm should pass (basic)
        payload_a1_im = make_payload(word="A1Im", level="A1", example="I'm testing a1im now.")
        r4 = self.build(payload_a1_im, ["--dry-run", "--audio", "never"])
        self.assertEqual(r4.returncode, 0)
        # A2 gonna fail, B2 gonna pass
        payload_a2 = make_payload(word="A2Gonna", level="A2", example="I'm gonna test a2gonna now.")
        r5 = self.build(payload_a2, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r5.returncode, 0)
        payload_b2 = make_payload(word="B2Gonna", level="B2", example="I'm gonna test b2gonna now.")
        r6 = self.build(payload_b2, ["--dry-run", "--audio", "never"])
        self.assertEqual(r6.returncode, 0)
        # We/Our fallback
        payload_we = make_payload(word="WeTest", level="A1", example="We wetest water now.")
        r7 = self.build(payload_we, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r7.returncode, 0)
        payload_we2 = make_payload(word="WeTest2", level="A1", example="We wetest2 water now.")
        payload_we2["example_person_fallback"] = "We refers to my family and me"
        r8 = self.build(payload_we2, ["--dry-run", "--audio", "never"])
        self.assertEqual(r8.returncode, 0)
        self.assertIn("We/Our", r8.stdout)

    # 10. required notes and hook
    def test_required_notes_and_hook(self):
        # Missing curiosity and no hook should fail
        payload = make_payload(word="NoHook", level="A1")
        payload["notes"] = {"word_translations": ["اختبار"], "example_translation": "ترجمة"}
        r = self.build(payload, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("at least one hook", r.stderr)
        # Phrasal Verb without grammar_note should fail
        payload2 = make_payload(word="Take Out2", level="B1", example="I take my food out now.")
        payload2["type"] = "Phrasal Verb"
        payload2["notes"] = {"word_translations": ["يخرج"], "example_translation": "ترجمة", "curiosity": "curiosity"}
        r2 = self.build(payload2, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("grammar_note", r2.stderr)

    # 11. extras_max warning
    def test_extras_max(self):
        payload = make_payload(word="ExtrasTest", level="A1", extra_notes={
            "synonyms": ["`a`"], "antonyms": ["`b`"], "common_examples": ["`c`"], "important_notes": "الكلمة دي مهمة في الشغل اليومي"
        })
        # A1 extras_max 3, we have curiosity + synonyms/antonyms/common_examples/important_notes =5 >3 should warn but not fail
        r = self.build(payload, ["--dry-run", "--audio", "never"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("extras_max", r.stdout)

    # 12. backtick policy errors and warnings
    def test_backtick_policy(self):
        # Frontmatter backtick error: backtick in arabic value
        payload = make_payload(word="BackFront", level="A1")
        payload["arabic"] = "`اختبار`"
        r = self.build(payload, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r.returncode, 0, "backtick in arabic should fail")
        self.assertIn("backtick", r.stderr.lower())
        # Warnings: plain_terms
        payload2 = make_payload(word="BackPlain", level="A1", extra_notes={"curiosity": "كلمة `American English` غريبة"})
        r2 = self.build(payload2, ["--dry-run", "--audio", "never"])
        self.assertEqual(r2.returncode, 0)
        self.assertIn("plain_terms", r2.stdout)
        # Same span twice
        payload3 = make_payload(word="BackDup", level="A1", extra_notes={"curiosity": "كلمة `test` غريبة `test` تاني"})
        r3 = self.build(payload3, ["--dry-run", "--audio", "never"])
        self.assertIn("same span", r3.stdout)

    # 13. (summary removed — no summary_rules test)

    # 14. --check is read-only
    def test_check_readonly(self):
        payload = make_payload(word="CheckWord", level="A1")
        self.build(payload, ["--audio", "never"])
        note = self.vault / "Vocabulary" / "C" / "Checkword.md"
        sha_before = sha256_file(note)
        r = run_cmd(["python3", str(BUILD), "--check", "--word", "CheckWord", "--vault-root", str(self.vault)])
        self.assertEqual(r.returncode, 0)
        sha_after = sha256_file(note)
        self.assertEqual(sha_before, sha_after)

    # 15. audit_vault is read-only and ends with no_changes_made
    def test_audit_readonly(self):
        payload = make_payload(word="AuditWord", level="A1")
        self.build(payload, ["--audio", "never"])
        import hashlib, pathlib
        # hash before
        before = {}
        for p in self.vault.rglob("*.md"):
            before[p] = sha256_file(p)
        r = run_cmd(["python3", str(AUDIT), "--vault-root", str(self.vault)])
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip().endswith("no_changes_made"))
        for p in self.vault.rglob("*.md"):
            self.assertEqual(before[p], sha256_file(p))

    # 16. (Word Groups removed — add_to_group.py deleted)

    # 17. \| normalization test (Word Groups removed; pipe in example is allowed)
    def test_pipe_normalization(self):
        # Pipe in example doesn't cause failures
        payload = make_payload(word="PipeWord", level="A1", example="I pipeword this now.")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0)

    # 18. Audio tests (only if tools exist)
    def test_audio(self):
        if not shutil.which("edge-tts") or not shutil.which("ffmpeg"):
            self.skipTest("edge-tts or ffmpeg not found — SKIP")
        payload = make_payload(word="AudioTest", level="B1")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            fname = f.name
        try:
            r = run_cmd(["python3", str(BUILD), "--json-file", fname, "--vault-root", str(self.vault), "--audio", "always"])
            self.assertEqual(r.returncode, 0)
            pron = self.vault / "Media" / "Pronunciation" / "Audiotest_pronunciation.mp3"
            ex = self.vault / "Media" / "Examples" / "audiotest_example.mp3"
            self.assertTrue(pron.exists())
            self.assertTrue(ex.exists())
            # Check duration
            import subprocess as sp
            def duration(p):
                out = sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)], capture_output=True, text=True)
                return float(out.stdout.strip() or 0)
            # Single synthesis duration
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                single = Path(tf.name)
            sp.run(["edge-tts", "--voice", "en-US-BrianNeural", "--rate", "-15%", "--text", "I audiotest this now.", "--write-media", str(single)], capture_output=True)
            try:
                single_dur = duration(single)
                ex_dur = duration(ex)
                if single_dur > 0.1:
                    # Expected: 5 repetitions + 4 gaps of 0.5s each = 5*single + 2.0s
                    expected = 5*single_dur + 2.0
                    self.assertAlmostEqual(ex_dur, expected, delta=2.0)
                else:
                    # single synthesis returned 0 (fake word) — skip duration math, trust the file exists
                    self.assertGreater(ex_dur, 0.5)
            finally:
                single.unlink(missing_ok=True)
            # Now test auto regenerates both (single-voice rule); always changes both; never changes none
            # Change example
            payload2 = make_payload(word="AudioTest", level="B1", example="I change my audiotest today.")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f2:
                json.dump(payload2, f2, ensure_ascii=False)
                fname2 = f2.name
            pron.write_bytes(b"stale pron auto")
            ex.write_bytes(b"stale ex auto")
            r2 = run_cmd(["python3", str(BUILD), "--json-file", fname2, "--vault-root", str(self.vault), "--audio", "auto", "--change-example"])
            self.assertEqual(r2.returncode, 0)
            self.assertNotEqual(sha256_file(pron), hashlib.sha256(b"stale pron auto").hexdigest(), "auto regenerates pron too (single-voice rule)")
            self.assertNotEqual(sha256_file(ex), hashlib.sha256(b"stale ex auto").hexdigest(), "auto should change ex")
            # always
            pron.write_bytes(b"stale pron")
            ex.write_bytes(b"stale ex")
            r3 = run_cmd(["python3", str(BUILD), "--json-file", fname2, "--vault-root", str(self.vault), "--audio", "always", "--change-example", "--force"])
            self.assertEqual(r3.returncode, 0)
            self.assertNotEqual(sha256_file(pron), hashlib.sha256(b"stale pron").hexdigest(), "always should regenerate pron")
            self.assertNotEqual(sha256_file(ex), hashlib.sha256(b"stale ex").hexdigest(), "always should regenerate ex")
            # never
            payload3 = make_payload(word="AudioTest", level="B1", example="I change my audiotest again.")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f3:
                json.dump(payload3, f3, ensure_ascii=False)
                fname3 = f3.name
            pron_b = sha256_file(pron)
            ex_b = sha256_file(ex)
            r4 = run_cmd(["python3", str(BUILD), "--json-file", fname3, "--vault-root", str(self.vault), "--audio", "never", "--change-example"])
            self.assertEqual(r4.returncode, 0)
            self.assertEqual(pron_b, sha256_file(pron))
            self.assertEqual(ex_b, sha256_file(ex))
            Path(fname2).unlink(missing_ok=True)
            Path(fname3).unlink(missing_ok=True)
        finally:
            Path(fname).unlink(missing_ok=True)

    # 19. worked-examples drift test (TASK 4-FIX §2)
    def test_examples_drift(self):
        examples_dir = SKILL_ROOT / "references" / "examples"
        mapping = {
            "abandon": ("example_abandon.md", 0),
            "saw-verb": ("example_abandon.md", 1),
            "saw-noun": ("example_abandon.md", 2),
            "water": ("example_water.md", 0),
            "mitigate": ("example_mitigate.md", 0),
        }
        def extract_note_blocks(md_text):
            blocks = []
            search_from = 0
            while True:
                start = md_text.find("```markdown\n", search_from)
                if start == -1:
                    break
                content_start = start + len("```markdown\n")
                dbl = md_text.find("\n```\n```", content_start)
                if dbl != -1:
                    blocks.append(md_text[content_start:dbl + len("\n```")])
                    search_from = dbl + len("\n```\n```")
                else:
                    end = md_text.find("\n```", content_start)
                    if end == -1:
                        break
                    blocks.append(md_text[content_start:end])
                    search_from = end + len("\n```")
            return blocks
        def strip_dates(s):
            return "\n".join(
                l for l in s.strip().splitlines()
                if not re.match(r"^(day|created_day|created|modified|review|month):", l)
            )
        for name, (md_file, idx) in mapping.items():
            json_path = examples_dir / f"{name}.json"
            self.assertTrue(json_path.exists(), f"missing {json_path}")
            md_text = (SKILL_ROOT / "references" / md_file).read_text(encoding="utf-8")
            blocks = extract_note_blocks(md_text)
            self.assertGreater(len(blocks), idx, f"{md_file} has no markdown block #{idx} for {name}")
            expected = strip_dates(blocks[idx])
            with open(json_path, encoding="utf-8") as f:
                payload = json.load(f)
            r = self.build(payload, ["--audio", "never"])
            self.assertEqual(r.returncode, 0, f"{name}: build failed: {r.stderr}")
            notes = list(self.vault.rglob("*.md"))
            self.assertEqual(len(notes), 1, f"{name}: expected 1 note, got {[str(p) for p in notes]}")
            actual = strip_dates(notes[0].read_text(encoding="utf-8"))
            self.assertEqual(expected, actual, f"{name}: rendered note drifts from {md_file} block #{idx}")
            # reset vault for next example
            shutil.rmtree(self.vault)
            self.vault.mkdir(parents=True, exist_ok=True)

    # TASK 5 §9.1: family present within cap; absent word omits section entirely
    def test_task5_family_present_and_absent(self):
        payload = make_payload(word="FamAlpha", level="B1", example="I famalpha my work today.",
            extra_notes={"word_family": [
                {"form": "Famalphaing", "type": "Noun", "arabic": "الاختبار", "example": "Famalphaing takes a long time"},
                {"form": "Famalphaed", "type": "Adjective", "arabic": "مختبر", "example": "The famalphaed group waited outside"}]})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "F" / "Famalpha.md"
        self.assertTrue(note.exists())
        text = note.read_text(encoding="utf-8")
        self.assertIn("> [!example] من نفس الأصل", text)
        self.assertIn("> - [[Famalphaing]]", text)
        self.assertIn("> - [[Famalphaed]]", text)
        # word with no useful family omits the section entirely
        payload2 = make_payload(word="NoFamWord", level="B1")
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        note2 = self.vault / "Vocabulary" / "N" / "Nofamword.md"
        self.assertTrue(note2.exists())
        self.assertNotIn("من نفس الأصل", note2.read_text(encoding="utf-8"))

    # TASK 5 §9.2: family_max exceeded warns, does not error
    def test_task5_family_max_warns(self):
        fam = [{"form": f"Fform{i}", "type": "Noun", "arabic": "اختبار عربي للكلمة", "example": f"Fform{i} takes a long time today"}
               for i in range(4)]  # B1 family_max is 3
        payload = make_payload(word="FamOver", level="B1", example="I famover my work today.",
                               extra_notes={"word_family": fam})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("> family_max", r.stdout)

    # TASK 5 §9.3: collocations cap warns; common_examples no longer counts toward extras_max
    def test_task5_collocations_cap_and_extras_exclusion(self):
        # over cap (A1 collocations_max 2): warns but builds
        payload = make_payload(word="ColOver", level="A1", example="I colover this now.",
            extra_notes={"common_examples": ["`colover one`", "`colover two`", "`colover three`"]})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("> collocations_max", r.stdout)
        # at extras cap (curiosity + synonyms + antonyms = 3 = A1 max) plus collocations:
        # no false extras warning
        payload2 = make_payload(word="ColOk", level="A1", example="I colok this now.",
            extra_notes={"synonyms": ["`colok fast`"], "antonyms": ["`colok slow`"],
                         "common_examples": ["`colok one`", "`colok two`"]})
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertNotIn("non-core notes > extras_max", r2.stdout)

    # TASK 5 §9.4: synonym_contrast DOES count toward extras_max
    def test_task5_synonym_contrast_counts(self):
        payload = make_payload(word="SynCon", level="A1", example="I syncon this now.",
            extra_notes={"synonyms": ["`syncon fast`"], "antonyms": ["`syncon slow`"],
                         "synonym_contrast": "كلمة `syncon` رسمية أكتر من `syncon fast` وده بيفرق في الشغل"})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("non-core notes > extras_max", r.stdout)
        note = self.vault / "Vocabulary" / "S" / "Syncon.md"
        self.assertIn("> [!important] فرق عن كلمة قريبة", note.read_text(encoding="utf-8"))

    # TASK 5 §9.5: routing a derivative to an existing root (agent path via --add-family-member)
    def test_task5_routing_to_existing_root(self):
        payload = make_payload(word="RouteRoot", level="B1", example="I routeroot my work today.")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "R" / "Routeroot.md"
        self.assertTrue(note.exists())
        fam = json.dumps({"form": "Routerootment", "type": "Noun", "arabic": "التخلي",
                          "example": "Routerootment takes a long time"}, ensure_ascii=False)
        r2 = run_cmd(["python3", str(BUILD), "--add-family-member", "--word", "RouteRoot",
                      "--family-json", fam, "--vault-root", str(self.vault)])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        # no new note file for the derivative, no audio run
        self.assertFalse((self.vault / "Vocabulary" / "R" / "Routerootment.md").exists())
        text = note.read_text(encoding="utf-8")
        self.assertIn("Routerootment", text)
        self.assertIn("> [!example] من نفس الأصل", text)
        import datetime
        today = datetime.date.today().isoformat()
        self.assertIn(f"modified: {today}", text)
        self.assertIn(f"review: {today}", text)
        self.assertIn("routed", r2.stdout)
        self.assertIn("already covered under", r2.stdout)

    # TASK 5 §9.6: derivative with no root note creates the ROOT's note (not the derivative's)
    def test_task5_derivative_creates_root(self):
        payload = make_payload(word="NewRoot", level="B1", example="I newroot my work today.",
            extra_notes={"word_family": [
                {"form": "Newrootment", "type": "Noun", "arabic": "التخلي",
                 "example": "Newrootment takes a long time today"}]})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.vault / "Vocabulary" / "N" / "Newroot.md").exists())
        self.assertFalse((self.vault / "Vocabulary" / "N" / "Newrootment.md").exists())
        text = (self.vault / "Vocabulary" / "N" / "Newroot.md").read_text(encoding="utf-8")
        self.assertIn("Newrootment", text)

    # TASK 5 §9.7: canonical order in a real rendered note matches §5 exactly
    def test_task5_canonical_order(self):
        payload = make_payload(word="OrderTest", level="B1", example="I ordertest my work today.",
            extra_notes={
                "when_used": "بقولها في الشغل لما المشكلة تكون صغيرة ومحتاجة حل سريع",
                "grammar_note": "فعل متعد `ordertest something` وما بياخدش حرف جر زيادة",
                "cultural_context": "الأمريكان بيقولوها في الاجتماعات والمصريين بيعبروا عنها بجملة أطول",
                "second_meaning": "كاسم `ordertest` معناها اختبار الترتيب — مثال `I took an ordertest yesterday` وترجمتها عملت اختبار ترتيب امبارح",
                "word_family": [{"form": "Ordertesting", "type": "Noun", "arabic": "الترتيب",
                                 "example": "Ordertesting takes a long time today"}],
                "synonyms": ["`ordertest arrange`"],
                "synonym_contrast": "كلمة `ordertest` أعم من `ordertest arrange` وبتتقال في سياقات أكتر",
                "antonyms": ["`ordertest scatter`"],
                "common_examples": ["`ordertest files`", "`ordertest tasks`"],
                "common_mistakes": "ما تقولش `ordertest` مع حرف الجر الغلط وخليك على النمط الثابت",
                "important_notes": "الكلمة دي مهمة في سياق الشغل اليومي وبتتكرر كتير",
                "additional_notes": "لو سمعتها في اجتماع ركز على السياق عشان تفهم المقصود",
                "try_it": "قول `I ordertest my work today` عن ترتيب شغلك النهارده"})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "O" / "Ordertest.md"
        text = note.read_text(encoding="utf-8")
        m = re.search(r"## Ordertest Notes\n\n(.*?)\n\n---", text, re.DOTALL)
        self.assertIsNotNone(m)
        labels = []
        for line in m.group(1).splitlines():
            s = line.strip()
            if s.startswith("**"):
                lab = re.match(r"\*\*(.*?)\*\*", s).group(1).strip().rstrip(":").rstrip("؟")
                labels.append(lab)
            elif s.startswith("> [!"):
                m_c = re.match(r">\s*\[![A-Za-z]+\]\s*(.*)", s)
                if m_c:
                    labels.append(m_c.group(1).strip().rstrip(":").rstrip("؟"))
        expected = ["ترجمة الكلمة", "ترجمة المثال", "إمتى بتتقال", "ملاحظة قواعد",
                    "السياق الثقافي", "عارف إن",
                    "معنى تاني", "من نفس الأصل", "مرادفات", "فرق عن كلمة قريبة",
                    "أضداد", "أمثلة شائعة", "أخطاء شائعة", "ملاحظات مهمة",
                    "ملاحظات إضافية", "جرّبها النهارده"]
        self.assertEqual(labels, expected)

    # TASK 5-FIX §1: structural lists exempt from backtick density/duplicate checks
    def test_task5fix_backtick_scope(self):
        import json as _json
        # 4-entry word_family = 8 backtick spans -> zero backtick warnings
        fam = [{"form": f"Fform{i}", "type": t, "arabic": "اختبار عربي للكلمة",
                "example": f"Fform{i} takes a long time today"}
               for i, t in enumerate(["Noun", "Verb", "Adjective", "Adverb"])]
        payload = make_payload(word="BacktickFam", level="C1",
                               example="I backtickfam my work today please.",
                               extra_notes={"word_family": fam})
        payload["notes"]["curiosity"] = "الكلمة دي بتتقال كتير في الشغل اليومي وبتتكرر في الاجتماعات"
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        res = _json.loads(r.stdout.split("RESULT:")[1].strip())
        bt = [w for w in res["warnings"]
              if "backtick" in w or "same span" in w or "unwrapped" in w
              or "plain_terms" in w or "mixes Arabic" in w]
        self.assertEqual(bt, [], f"structural list should produce no backtick warnings: {bt}")
        # prose curiosity with 5 spans still warns
        payload2 = make_payload(word="SpanTest", level="A1", example="I spantest this now.",
            extra_notes={"curiosity": "عندي `take the lead` وكمان `break the ice` وكمان `hit the books` وكمان `miss the boat` وكمان `see the light` في الكلام"})
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("backtick spans > max", r2.stdout)

    # TASK 5-FIX-2: --add-family-member must render exactly like a --force rebuild
    def test_task5fix2_family_render_equivalence(self):
        base = make_payload(word="RegFix", level="B1", example="I regfix my work today.",
            extra_notes={"synonyms": ["`regfix fast`", "`regfix slow`"]})
        r = self.build(base, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "R" / "Regfix.md"
        fam_dicts = []
        for i in range(4):  # B1 family_max 3: 4th addition must warn
            entry = {"form": f"RegFam{i}", "type": "Noun", "arabic": "اختبار",
                     "example": f"RegFam{i} takes a long time today"}
            r_add = run_cmd(["python3", str(BUILD), "--add-family-member", "--word", "RegFix",
                             "--family-json", json.dumps(entry, ensure_ascii=False),
                             "--vault-root", str(self.vault)])
            self.assertEqual(r_add.returncode, 0, r_add.stderr)
            fam_dicts.append(entry)
            text_after_add = note.read_text(encoding="utf-8")
            m = re.search(r"## Regfix Notes\n\n(.*?)\n\n---", text_after_add, re.DOTALL)
            self.assertIsNotNone(m)
            nb = m.group(1)
            # exactly one blank line between family block and next paragraph
            self.assertIn("> [!example] من نفس الأصل", nb)
            self.assertNotIn("`\n> [!", nb)
            self.assertNotIn("\n\n\n> [!", nb)
            # byte-identical to a --force rebuild with the same complete family list
            base["notes"]["word_family"] = [dict(e) for e in fam_dicts]
            r_force = self.build(base, ["--force", "--audio", "never"])
            self.assertEqual(r_force.returncode, 0, r_force.stderr)
            self.assertEqual(note.read_text(encoding="utf-8"), text_after_add,
                             f"add #{i+1} diverges from --force rebuild")
            if i == 3:
                self.assertIn("> family_max", r_add.stdout)

    # Canonical card shape: all cards have playphrase, youglish, Context row, standalone --- separator
    def test_card_shape_and_youglish_property(self):
        payload = make_payload(word="ShapeWord", level="B1", example="I shapeword my work today.")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "S" / "Shapeword.md"
        text = note.read_text(encoding="utf-8")
        fm_block = text.split("---\n")[1]
        keys = [l.split(":")[0].strip() for l in fm_block.splitlines() if ":" in l]
        self.assertEqual(keys, [
            "subject", "category", "level", "status",
            "arabic", "ipa", "chunks", "definition", "example",
            "pronunciation", "voice", "youglish", "image",
            "char", "day", "month", "created", "modified", "review"
        ])
        self.assertIn('definition: "A simple test."', text)
        self.assertNotIn("playphrase:", fm_block)
        self.assertIn('image: "https://www.google.com/search?q=shapeword+illustration&tbm=isch&tbs=itp:clipart"', text)
        self.assertIn("category: Noun", text)
        self.assertIn("subject: Vocabulary", text)
        self.assertIn("## Shapeword Gang", text)
        self.assertIn("name: Shapeword Gang", text)
        self.assertIn("- voice", text)
        self.assertIn('category == "Noun"', text)
        self.assertIn('pronunciation: "[[Shapeword_pronunciation.mp3]]"', text)
        self.assertIn('voice: "[[shapeword_example.mp3]]"', text)
        self.assertIn('youglish: "https://youglish.com/pronounce/shapeword/english/us"', text)
        self.assertNotIn("context:", fm_block)
        self.assertIn("> [!quote] Context\n> I was nervous before the exam and needed to test my knowledge.", text)
        self.assertIn('ipa: "/tɛst/"', text)
        self.assertIn('chunks: "sha-pe-word"', text)
        self.assertNotIn("| Situation", text)
        self.assertNotIn("| Context", text)
        self.assertIn("\n---\n\n---\n\n## Shapeword Info\n", text)
        self.assertIn("[YouGlish](https://youglish.com/pronounce/shapeword/english/us)", text)
        # PlayPhrase is idiom/phrase only — a Noun card must not carry it
        self.assertNotIn("PlayPhrase", text)
        # Gang view shows five columns with narrow audio/image columns
        self.assertIn("    order:\n      - file.name\n      - pronunciation\n      - voice\n      - image\n      - review", text)
        self.assertIn("    columnSize:\n      note.pronunciation: 155\n      note.voice: 155", text)
        # Test word with chunks
        payload_chunks = make_payload(word="Impossible", level="B1", chunks="im-poss-ible")
        r_c = self.build(payload_chunks, ["--audio", "never"])
        self.assertEqual(r_c.returncode, 0)
        text_c = (self.vault / "Vocabulary" / "I" / "Impossible.md").read_text(encoding="utf-8")
        self.assertIn('chunks: "im-poss-ible"', text_c)
        # a multi-word card uses underscores in YouGlish URL
        payload2 = make_payload(word="Take Out", level="B1", type="Phrase", example="I take out my keys now.")
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        text2 = (self.vault / "Vocabulary" / "T" / "Take Out.md").read_text(encoding="utf-8")
        self.assertIn('youglish: "https://youglish.com/pronounce/take_out/english/us"', text2)
        self.assertIn("https://youglish.com/pronounce/take_out/english/us", text2)

    # PlayPhrase is restricted to Idioms and Phrases (property + Info lookup link)
    def test_all_cards_have_playphrase(self):
        payload = make_payload(word="Pull Test", level="B2", type="Idiom",
                               example="I pull test my work now.",
                               context="He pull test his work now.",
                               extra_notes={"grammar_note": "المعنى مش حرفي: `pull test it` وثابت كده"})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "P" / "Pull Test.md"
        text = note.read_text(encoding="utf-8")
        fm_block = text.split("---\n")[1]
        keys = [l.split(":")[0].strip() for l in fm_block.splitlines() if ":" in l]
        self.assertEqual(keys, [
            "subject", "category", "level", "status",
            "arabic", "ipa", "chunks", "definition", "example",
            "pronunciation", "voice", "youglish", "playphrase", "image",
            "char", "day", "month", "created", "modified", "review"
        ])
        self.assertIn('pronunciation: "[[Pull Test_pronunciation.mp3]]"', text)
        self.assertIn('voice: "[[pull test_example.mp3]]"', text)
        self.assertIn('playphrase: "https://www.playphrase.me/#/search?q=pull+test=2&language=en"', text)
        self.assertIn("[PlayPhrase](https://www.playphrase.me/#/search?q=pull+test=2&language=en)", text)
        # a non-idiom card does NOT have playphrase anywhere (property or lookup link)
        payload2 = make_payload(word="Plain Word", level="B2", example="I plain word my work now.")
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        text2 = (self.vault / "Vocabulary" / "P" / "Plain Word.md").read_text(encoding="utf-8")
        fm_block2 = text2.split("---\n")[1]
        self.assertNotIn("playphrase:", fm_block2)
        self.assertNotIn("PlayPhrase", text2)
        # a Phrase card keeps it too
        payload3 = make_payload(word="Take Out", level="B1", type="Phrase", example="I take out my keys now.")
        r3 = self.build(payload3, ["--audio", "never"])
        self.assertEqual(r3.returncode, 0, r3.stderr)
        text3 = (self.vault / "Vocabulary" / "T" / "Take Out.md").read_text(encoding="utf-8")
        self.assertIn("playphrase:", text3)
        self.assertIn("[PlayPhrase](https://www.playphrase.me/#/search?q=take+out=2&language=en)", text3)

    def _make_legacy(self, word):
        """Build a card, then strip it back to the legacy shape (no youglish, Situation table, no separator)."""
        payload = make_payload(word=word, level="B1", example=f"I {word.lower()} my work today.")
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # normalize_word() Title-Cases every token: LegacyWord -> Legacyword
        norm = word[0].upper() + word[1:].lower()
        note = self.vault / "Vocabulary" / norm[0] / f"{norm}.md"
        text = note.read_text(encoding="utf-8")
        # Strip out new canonical fields to simulate legacy
        text = re.sub(r"^youglish:.*\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^playphrase:.*\n", "", text, flags=re.MULTILINE)
        text = text.replace("\n---\n\n---\n\n## ", "\n---\n\n## ")
        # Convert modern info card to legacy table with Situation
        legacy_table = f"""| Word       | {norm} |
| ---------- | ------ |
| Situation  | I was nervous before the exam and needed to test my knowledge. |
| Definition | A simple test. |
| Example    | I {norm.lower()} my work today. |
| IPA        | `/tɛst/` |"""
        text = re.sub(r"## " + re.escape(norm) + r" Info\n\n.*?\n\n---", f"## {norm} Info\n\n{legacy_table}\n\n---", text, flags=re.DOTALL)
        note.write_text(text, encoding="utf-8")
        return payload, note, text

    # Arabic text direction: a note line must not START with English text
    def test_rtl_line_start_blocks_build(self):
        # Line opens with English -> build rejected
        payload = make_payload(word="RtlWord", level="B1", example="I rtlword my work today.",
            extra_notes={"grammar_note": "dispatch takes a direct object always: dispatch an order."})
        r = self.build(payload, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r.returncode, 0, "line starting with English must be rejected")
        self.assertIn("rtl_line_start", r.stderr)
        # Same content with an Arabic start -> accepted
        payload2 = make_payload(word="RtlWord", level="B1", example="I rtlword my work today.",
            extra_notes={"grammar_note": "كلمة dispatch بتاخد مفعول مباشر دايماً: dispatch an order."})
        r2 = self.build(payload2, ["--audio", "never"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        note = self.vault / "Vocabulary" / "R" / "Rtlword.md"
        text = note.read_text(encoding="utf-8")
        self.assertIn("كلمة dispatch بتاخد", text)
        # A callout body line that opens with English is rejected too
        payload3 = make_payload(word="Rltip", level="B1", example="I rltip my work today.",
            extra_notes={"curiosity": "I'm dispatching it now — that's the natural order."})
        r3 = self.build(payload3, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r3.returncode, 0)
        self.assertIn("rtl_line_start", r3.stderr)
        # A list item that opens with English is rejected too
        payload4 = make_payload(word="Rltlist", level="B1", example="I rltlist my work today.",
            extra_notes={"important_notes": "- dispatch an order\n- dispatch a team"})
        r4 = self.build(payload4, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r4.returncode, 0)
        self.assertIn("rtl_line_start", r4.stderr)

    # The RTL checker itself
    def test_rtl_checker_function(self):
        import sys
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import vocab_checks
        note = ("---\nsubject: Vocabulary\n---\n\n---\n\n## X Notes\n\n"
                "**ترجمة الكلمة:** ترجمة\n\n"
                "> [!tip] عارف إن؟\n> كلمة dispatch بتاخد مفعول مباشر.\n\n"
                "- [[Related]]\n\n---\n\n## X Gang\n")
        self.assertEqual(vocab_checks.check_rtl_line_start(note), [])
        bad = note.replace("> كلمة dispatch بتاخد مفعول مباشر.", "> dispatch takes a direct object always.")
        issues = vocab_checks.check_rtl_line_start(bad)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["code"], "rtl_line_start")
        self.assertEqual(issues[0]["severity"], "ERROR")
        # existing cards report it as an INFO proposal, never a violation
        soft = vocab_checks.check_rtl_line_start(bad, blocking=False)
        self.assertEqual(soft[0]["severity"], "INFO")
        self.assertTrue(soft[0]["message"].startswith("PROPOSAL:"))

    # Notes render as Obsidian callouts; common examples are full everyday sentences
    def test_notes_callouts_and_full_sentence_examples(self):
        payload = make_payload(word="Calloutword", level="B1", example="I calloutword my work today.",
            extra_notes={
                "when_used": "بقولها في الشغل لما المشكلة تكون بسيطة",
                "important_notes": "الكلمة دي مهمة في الشغل اليومي",
                "common_examples": ["I calloutword my work every Friday.",
                                    "We calloutword the plan before the meeting."],
                "word_family": [{"form": "Calloutwording", "type": "Noun", "arabic": "الكلام",
                                 "example": "Calloutwording takes a long time"}]})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (self.vault / "Vocabulary" / "C" / "Calloutword.md").read_text(encoding="utf-8")
        self.assertIn("> [!info] إمتى بتتقال", text)
        self.assertIn("> [!important] ملاحظات مهمة", text)
        self.assertIn("> [!example] من نفس الأصل", text)
        self.assertIn("> [!example] أمثلة شائعة", text)
        self.assertIn("> [!abstract] ترجمة الكلمة", text)
        self.assertIn("> [!tip] عارف إن؟", text)
        # common examples are full sentences and the target word is highlighted
        self.assertIn("> - I ==calloutword== my work every Friday.", text)
        self.assertIn("> - We ==calloutword== the plan before the meeting.", text)

    # The common-examples callout is English by design — English-first lines there are allowed
    def test_rtl_exempt_inside_common_examples(self):
        payload = make_payload(word="Exemptword", level="B1", example="I exemptword my work today.",
            extra_notes={"common_examples": ["I exemptword my work every Friday."]})
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # ...but an Arabic prose field still may not open with English
        payload2 = make_payload(word="Exemptword2", level="B1", example="I exemptword2 my work today.",
            extra_notes={"common_examples": ["I exemptword2 my work every Friday."],
                         "important_notes": "This note opens with English."})
        r2 = self.build(payload2, ["--dry-run", "--audio", "never"])
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("rtl_line_start", r2.stderr)

    # Common examples must be full sentences — a bare collocation is reported
    def test_common_examples_must_be_sentences(self):
        payload = make_payload(word="Colloqword", level="B1", example="I colloqword my work today.",
            extra_notes={"common_examples": ["colloqword risk"]})
        r = self.build(payload, ["--dry-run", "--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("examples_too_short", r.stdout)

    # Legacy cards often carry a placeholder `category: Vocabulary` next to a real `type`
    def test_legacy_placeholder_category_is_resolved(self):
        import sys
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("bw", SKILL_ROOT / "scripts" / "build_word.py")
        bw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bw)
        self.assertEqual(bw.resolve_category("Vocabulary", "Adverb"), "Adverb")
        self.assertEqual(bw.resolve_category("", "Noun"), "Noun")
        self.assertEqual(bw.resolve_category("Verb", "Noun"), "Verb")
        self.assertEqual(bw.resolve_category("Noun", "Phrasal Verb"), "Phrasal Verb")
        self.assertEqual(bw.resolve_category("", ""), "")
        # an upgraded legacy card gets the real category
        char_dir = self.vault / "Vocabulary" / "A"
        char_dir.mkdir(parents=True, exist_ok=True)
        old_note = char_dir / "Legacycat.md"
        old_note.write_text("""---
day: Wednesday
created: 2026-09-09
modified: 2026-09-19
review: 2026-09-25
month: September
char: A
type: Adverb
level: B1
status: Done
example: I accidentally deleted all my photos from the phone.
category: Vocabulary
arabic: "بالغلط"
---

## Legacycat Info

| Word       | Legacycat |
| ---------- | ------ |
| Situation  | She ==accidentally== stepped into a puddle. |
| Definition | In a way that is not planned. |
| Example    | I accidentally deleted all my photos from the phone. |
| IPA        | `/ə/` |

---

## Legacycat Notes

**ترجمة الكلمة:** بالغلط

---

## Legacycat Gang

```base
views:
  - type: table
    name: Legacycat Gang
    filters:
      and:
        - file.inFolder("English/Vocabulary/A")
        - type == "Adverb"
        - status == "Done"
    order:
      - file.name
      - example
      - review
```
""", encoding="utf-8")
        r = run_cmd(["python3", str(BUILD), "--upgrade-file", str(old_note), "--vault-root", str(self.vault), "--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        text = old_note.read_text(encoding="utf-8")
        self.assertIn("category: Adverb", text)
        self.assertNotIn("category: Vocabulary", text)
        self.assertIn('category == "Adverb"', text)

    # Skill documentation must keep the three new behavior sections
    def test_skill_doc_sections_present(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Workflow — Plan First, Then Execute", text)
        self.assertIn("## Teacher Authority — Act, Don't Ask", text)
        self.assertIn("## Arabic Text Direction (RTL Rule)", text)
        self.assertIn("rtl_line_start", text)
        rules = (SKILL_ROOT / "references" / "formatting_rules.md").read_text(encoding="utf-8")
        self.assertIn("Do Not Start a Line With English", rules)
        adaptive = (SKILL_ROOT / "references" / "adaptive_rules.md").read_text(encoding="utf-8")
        self.assertIn("Arabic Text Direction — Arabic-First Lines", adaptive)
        self.assertIn("Teacher Authority — Act, Don't Ask", adaptive)

    # A re-send of a legacy card must upgrade it in place, never freeze it with a date-only patch
    def test_resend_upgrades_legacy_card(self):
        payload, note, legacy_text = self._make_legacy("LegacyWord")
        self.assertNotIn("youglish:", legacy_text)
        self.assertIn("| Situation  |", legacy_text)
        created = re.search(r"^created: (.*)$", legacy_text, re.MULTILINE).group(1)
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        upgraded = note.read_text(encoding="utf-8")
        self.assertIn('youglish: "https://youglish.com/pronounce/legacyword/english/us"', upgraded)
        self.assertIn('pronunciation: "[[Legacyword_pronunciation.mp3]]"', upgraded)
        self.assertIn('voice: "[[legacyword_example.mp3]]"', upgraded)
        self.assertIn("> [!quote] Context", upgraded)
        self.assertNotIn("| Situation", upgraded)
        self.assertNotIn("| Context", upgraded)
        self.assertIn("\n---\n\n---\n\n## Legacyword Info\n", upgraded)
        self.assertIn(f"created: {created}", upgraded)

    # --check is read-only and reports legacy-card upgrades as INFO proposals, never ERRORs
    def test_check_reports_legacy_upgrade_as_proposal(self):
        payload, note, _ = self._make_legacy("CheckLegacy")
        sha_before = sha256_file(note)
        r = run_cmd(["python3", str(BUILD), "--check", "--word", "CheckLegacy", "--vault-root", str(self.vault)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("youglish_missing", r.stdout)
        self.assertIn("frontmatter_order", r.stdout)
        # Legacy card has Situation instead of Context: that's a legacy row (not info_table_legacy_context now)
        # but the info_table_rows issue must be INFO not ERROR
        self.assertNotIn('"severity": "ERROR"', r.stdout)
        self.assertEqual(sha_before, sha256_file(note))

    # audit_vault treats legacy cards as upgrade proposals (INFO), not violations
    def test_audit_legacy_cards_are_info(self):
        payload, note, _ = self._make_legacy("AuditLegacy")
        r = run_cmd(["python3", str(AUDIT), "--vault-root", str(self.vault)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("youglish_missing(INFO)", r.stdout)
        self.assertIn("frontmatter_order(INFO)", r.stdout)
        self.assertNotIn("youglish_missing(ERROR)", r.stdout)
        self.assertTrue(r.stdout.strip().endswith("no_changes_made"))
        # --only format still surfaces the upgrade proposals
        r2 = run_cmd(["python3", str(AUDIT), "--vault-root", str(self.vault), "--only", "format"])
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("youglish_missing(INFO)", r2.stdout)

    # Multi-meaning cards with disambiguation in title: Water (N) and Water (V)
    def test_multi_meaning_disambiguation(self):
        payload_n = make_payload(word="Water (N)", category="Noun", level="A1", example="I drink water every morning.")
        r_n = self.build(payload_n, ["--audio", "never"])
        self.assertEqual(r_n.returncode, 0, r_n.stderr)
        note_n = self.vault / "Vocabulary" / "W" / "Water (N).md"
        self.assertTrue(note_n.exists())
        text_n = note_n.read_text(encoding="utf-8")
        self.assertIn("char: W", text_n)
        self.assertIn("category: Noun", text_n)
        self.assertIn("## Water (N) Info", text_n)
        self.assertIn("## Water (N) Gang", text_n)
        self.assertIn('category == "Noun"', text_n)
        self.assertIn("https://youglish.com/pronounce/water/english/us", text_n)
        self.assertNotIn("PlayPhrase", text_n)

        payload_v = make_payload(word="Water (V)", category="Verb", level="A2", example="I water my plants every morning.")
        r_v = self.build(payload_v, ["--audio", "never"])
        self.assertEqual(r_v.returncode, 0, r_v.stderr)
        note_v = self.vault / "Vocabulary" / "W" / "Water (V).md"
        self.assertTrue(note_v.exists())
        text_v = note_v.read_text(encoding="utf-8")
        self.assertIn("char: W", text_v)
        self.assertIn("category: Verb", text_v)
        self.assertIn("## Water (V) Info", text_v)
        self.assertIn("## Water (V) Gang", text_v)
        self.assertIn('category == "Verb"', text_v)

    # Chunks guarantee: auto_chunk_word and fallback in build_word.py when chunks is missing
    def test_auto_chunking_and_fallback(self):
        import sys
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import vocab_io
        self.assertEqual(vocab_io.auto_chunk_word("Abandon"), "a-ban-don")
        self.assertEqual(vocab_io.auto_chunk_word("Water"), "wa-ter")
        self.assertEqual(vocab_io.auto_chunk_word("Saw"), "s-aw")
        self.assertEqual(vocab_io.auto_chunk_word("Cat"), "c-at")
        self.assertEqual(vocab_io.auto_chunk_word("Take Out"), "take-out")
        self.assertEqual(vocab_io.auto_chunk_word("Calculate"), "cal-cul-ate")
        self.assertEqual(vocab_io.auto_chunk_word("Old"), "o-ld")
        self.assertEqual(vocab_io.highlight_target_in_context("Ahmed abandoned the room", "Abandon"), "Ahmed ==abandoned== the room")
        self.assertEqual(vocab_io.generate_image_url("Lonely", "Adjective"), "https://www.google.com/search?q=lonely+concept&tbm=isch&tbs=itp:clipart")
        self.assertEqual(vocab_io.generate_image_url("Tired", "Adjective"), "https://www.google.com/search?q=tired+person+illustration&tbm=isch&tbs=itp:clipart")
        self.assertEqual(vocab_io.generate_image_url("On", "Preposition"), "https://www.google.com/search?q=on+preposition+diagram&tbm=isch")
        self.assertEqual(vocab_io.generate_image_url("Break The Ice", "Idiom"), "https://www.google.com/search?q=break+the+ice+idiom+illustration&tbm=isch&tbs=itp:clipart")
        self.assertEqual(vocab_io.generate_image_url("Play", "Verb"), "https://www.google.com/search?q=play+illustration&tbm=isch&tbs=itp:clipart")

        # Payload without chunks property -> auto-chunks automatically
        # Payload with synonyms -> renders as bulleted wikilinks
        payload = make_payload(word="Calculate", level="B1", example="I calculate my hours daily.",
                               context="I calculate my expenses every evening.",
                               extra_notes={
                                   "synonyms": ["compute", "figure"],
                                   "synonym_contrast": "كلمة `calculate` بتستخدم للحسابات الدقيقة مقارنة بـ [[estimate]]"
                               })
        payload.pop("chunks", None)
        r = self.build(payload, ["--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)
        note = self.vault / "Vocabulary" / "C" / "Calculate.md"
        self.assertTrue(note.exists())
        text = note.read_text(encoding="utf-8")
        self.assertIn('chunks: "cal-cul-ate"', text)
        self.assertIn("> I ==calculate== my expenses every evening.", text)
        self.assertIn("> [!example] مرادفات\n> - [[compute]]\n> - [[figure]]", text)
        self.assertIn("[[estimate]]", text)

    # Legacy card upgrade: --upgrade and --upgrade-file upgrade old schema in-place
    def test_legacy_card_upgrade(self):
        char_dir = self.vault / "Vocabulary" / "A"
        char_dir.mkdir(parents=True, exist_ok=True)
        old_note = char_dir / "Abandon.md"
        old_content = """---
type: Verb
level: B1
status: Done
arabic: "يتخلى عن - يترك"
ipa: "/əˈbændən/"
example: "I abandoned the project after it failed."
playphrase: "https://www.playphrase.me/#/search?q=abandon=2&language=en"
char: A
day: Friday
month: September
created: 2026-09-25
modified: 2026-09-25
review: 2026-09-25
---

## Abandon

| Word       | Abandon |
| ---------- | ------ |
| Situation  | Ahmed abandoned the burning building in a rush. |
| Definition | To leave someone or something permanently. |
| Example    | I abandoned the project after it failed. |
| IPA        | `/əˈbændən/` |

---

## Abandon Pronunciation

![[Abandon_pronunciation.mp3]]

---

## Abandon Example

![[abandon_example.mp3]]

---

## Abandon Notes

**ترجمة الكلمة:** يترك شيئًا نهائيًا

**ترجمة المثال:** سيبت المشروع بعد ما فشل

**أصل الكلمة وإزاي تفتكرها:** أصلها فرنسي قديم

**من نفس الأصل:**
`Abandonment` (Noun): التخلي — `The abandonment was painful.`

---

## Abandon Gang

```base
views:
  - type: table
    name: Abandon Gang
    filters:
      and:
        - file.inFolder("English/Vocabulary/A")
        - type == "Verb"
        - status == "Done"
    order:
      - file.name
      - example
      - review
```
"""
        old_note.write_text(old_content, encoding="utf-8")

        r = run_cmd(["python3", str(BUILD), "--upgrade", "--word", "Abandon", "--vault-root", str(self.vault), "--audio", "never"])
        self.assertEqual(r.returncode, 0, r.stderr)

        upgraded_text = old_note.read_text(encoding="utf-8")
        # 1. Frontmatter
        self.assertIn("subject: Vocabulary", upgraded_text)
        self.assertIn("category: Verb", upgraded_text)
        self.assertNotIn("type: Verb", upgraded_text)
        self.assertNotIn("playphrase:", upgraded_text.split("---")[1])
        self.assertIn('chunks: "a-ban-don"', upgraded_text)
        self.assertIn('youglish: "https://youglish.com/pronounce/abandon/english/us"', upgraded_text)
        self.assertIn('image: "https://www.google.com/search?q=abandon+illustration&tbm=isch&tbs=itp:clipart"', upgraded_text)
        self.assertIn('pronunciation: "[[Abandon_pronunciation.mp3]]"', upgraded_text)
        self.assertIn('voice: "[[abandon_example.mp3]]"', upgraded_text)
        # 2. Headings & Modern Card Layout
        self.assertIn("## Abandon Info", upgraded_text)
        self.assertIn("> [!quote] Context", upgraded_text)
        self.assertIn("Ahmed ==abandoned== the burning building in a rush.", upgraded_text)
        self.assertNotIn("| Situation", upgraded_text)
        self.assertNotIn("| Context", upgraded_text)
        self.assertIn("[YouGlish](https://youglish.com/pronounce/abandon/english/us)", upgraded_text)
        self.assertNotIn("PlayPhrase", upgraded_text)
        # 3. Word Family Wikilinks
        self.assertIn("- [[Abandonment]]", upgraded_text)
        # 4. Gang View
        self.assertIn('category == "Verb"', upgraded_text)
        self.assertIn("- voice", upgraded_text)

if __name__ == "__main__":
    unittest.main(verbosity=2)
