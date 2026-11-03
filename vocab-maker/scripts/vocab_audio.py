#!/usr/bin/env python3
"""vocab_audio.py — audio generation for vocab-maker.

Voice policy: always male, native-like US English.
  1. edge-tts  — tries MALE_VOICES in order (Brian preferred), 3 attempts each.
  2. Google TTS — automatic fallback when edge-tts is unavailable (clear US English).

Single-voice rule: resolve_engine() picks ONE engine per run and
generate_audio_pair() synthesizes both files with it, so pronunciation and
example always share the same voice.
"""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Primary voice — Brian (US male). Always tried first for every word.
PRIMARY_VOICE = "en-US-BrianNeural"

# All male Neural voices — Brian first (most natural), then fallbacks.
MALE_VOICES = [
    PRIMARY_VOICE,
    "en-US-GuyNeural",
    "en-US-EricNeural",
    "en-US-RogerNeural",
    "en-US-SteffanNeural",
    "en-GB-RyanNeural",
]

# Single-voice rule: both files of one word must share the same engine and voice.
# The engine is resolved ONCE per run and reused for both files — never resolved
# per file, which is what used to produce mismatched voices.
# Cached per process: ("edge-tts", voice) | ("gtts", None).
_RESOLVED_ENGINE = None


def resolve_engine(rate: str, warnings: list):
    """Pick one working TTS engine for the whole run. Returns (kind, voice)."""
    global _RESOLVED_ENGINE
    if _RESOLVED_ENGINE is not None:
        return _RESOLVED_ENGINE
    # Tier 1: edge-tts — probe each voice with a short text (1 attempt each).
    for voice in MALE_VOICES:
        try:
            probe = Path(tempfile.mktemp(suffix=".mp3"))
            try:
                if synthesize_once("test", probe, voice, rate):
                    _RESOLVED_ENGINE = ("edge-tts", voice)
                    return _RESOLVED_ENGINE
            finally:
                probe.unlink(missing_ok=True)
        except Exception:
            continue
    # Tier 2: Google TTS US voice — clear American English, better than silence.
    try:
        from gtts import gTTS as _gtts_probe  # noqa: F401
        warnings.append("WARNING: edge-tts unavailable — using Google TTS US voice for all audio in this run")
        _RESOLVED_ENGINE = ("gtts", None)
        return _RESOLVED_ENGINE
    except ImportError:
        pass
    # No engine available
    warnings.append("WARNING: no TTS engine available — audio generation will fail")
    _RESOLVED_ENGINE = ("gtts", None)
    return _RESOLVED_ENGINE


def _synthesize_single_with_engine(text: str, out_single: Path, kind: str, voice, rate: str, warnings: list, tmpdir: Path) -> bool:
    """Synthesize one utterance with the already-resolved engine. No fallback here —
    downgrade decisions happen in generate_audio_pair so both files stay together."""
    if kind == "edge-tts":
        for attempt in range(1, 4):
            try:
                if synthesize_once(text, out_single, voice, rate):
                    return True
            except Exception:
                pass
            time.sleep(0.5 * attempt)
        return False
    if kind == "gtts":
        return _gtts_synthesize(text, out_single, rate, warnings, tmpdir)
    return False


def _repeat_single_to_final(single: Path, final_path: Path, warnings: list, tmpdir: Path) -> None:
    """Repeat one utterance 5x with 0.5 s silence gaps via ffmpeg (shared helper).

    Always re-encodes to 22050 Hz mono so every file has identical audio
    params regardless of which engine synthesized it.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not available")
    silence = tmpdir / "silence.mp3"
    cmd_sil = [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
               "-t", "0.5", "-q:a", "9", "-acodec", "libmp3lame", str(silence)]
    r = subprocess.run(cmd_sil, capture_output=True, text=True)
    if r.returncode != 0 or not silence.exists():
        raise RuntimeError(f"ffmpeg silence generation failed: {r.stderr[:300]}")
    list_file = tmpdir / "concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for i in range(5):
            f.write(f"file '{single}'\n")
            if i < 4:
                f.write(f"file '{silence}'\n")
    tmp_final = tmpdir / "final.mp3"
    cmd_concat = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                  "-ar", "22050", "-ac", "1", "-c:a", "libmp3lame", str(tmp_final)]
    r2 = subprocess.run(cmd_concat, capture_output=True, text=True)
    if r2.returncode != 0 or not tmp_final.exists():
        raise RuntimeError(f"ffmpeg concat failed: {r2.stderr[:300]}")
    shutil.copy2(tmp_final, final_path)


def generate_audio_pair(word_text: str, example_text: str, pron_final: Path, example_final: Path,
                        warnings: list, rate: str, need_pron: bool, need_example: bool):
    """Synthesize pronunciation + example with ONE shared engine/voice.

    Returns (pron_status, example_status, engine_label) where each status is
    "generated" or "kept". Raises RuntimeError if all engines fail.
    """
    kind, voice = resolve_engine(rate, warnings)

    def _label(k, v):
        if k == "edge-tts":
            return f"edge-tts {v}"
        return "gtts"

    engine_label = _label(kind, voice)
    tmpdir = Path(tempfile.mkdtemp(prefix="vocab-audio-pair-"))
    try:
        jobs = []
        if need_pron:
            jobs.append((word_text, tmpdir / "pron_single.mp3"))
        if need_example:
            jobs.append((example_text, tmpdir / "ex_single.mp3"))

        def _downgrade(failed_kind: str):
            global _RESOLVED_ENGINE
            if failed_kind == "edge-tts":
                warnings.append("WARNING: edge-tts failed mid-run — downgrading whole run to Google TTS US voice")
                _RESOLVED_ENGINE = ("gtts", None)
                return _RESOLVED_ENGINE
            warnings.append("WARNING: all TTS engines failed")
            return ("gtts", None)

        singles = {}
        for text, single_path in jobs:
            ok = _synthesize_single_with_engine(text, single_path, kind, voice, rate, warnings, tmpdir)
            if not ok and kind == "edge-tts":
                kind, voice = _downgrade(kind)
                engine_label = _label(kind, voice)
                ok = _synthesize_single_with_engine(text, single_path, kind, voice, rate, warnings, tmpdir)
            if not ok or not single_path.exists():
                raise RuntimeError(f"All TTS engines failed for '{text[:30]}...'")
            singles[single_path] = True

        pron_status = "kept"
        example_status = "kept"
        if need_pron:
            pron_final.parent.mkdir(parents=True, exist_ok=True)
            _repeat_single_to_final(tmpdir / "pron_single.mp3", pron_final, warnings, tmpdir)
            pron_status = "generated"
        if need_example:
            example_final.parent.mkdir(parents=True, exist_ok=True)
            _repeat_single_to_final(tmpdir / "ex_single.mp3", example_final, warnings, tmpdir)
            example_status = "generated"
        return pron_status, example_status, engine_label
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def synthesize_once(text: str, out_path: Path, voice: str, rate: str) -> bool:
    cmd = ["edge-tts", "--voice", voice, "--rate", rate, "--text", text, "--write-media", str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0


def generate_audio_final(text: str, final_path: Path, warnings: list, rate: str) -> str:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="vocab-audio-"))
    single = tmpdir / "single.mp3"
    success = False
    last_err = ""

    # --- Tier 1: edge-tts male voices ---
    for voice in MALE_VOICES:
        for attempt in range(1, 4):
            if synthesize_once(text, single, voice, rate):
                success = True
                break
            last_err = f"voice {voice} attempt {attempt}"
            time.sleep(0.5 * attempt)
        if success:
            break

    # --- Tier 2: Google TTS US (clear American English) ---
    if not success or not single.exists():
        warnings.append(f"WARNING: edge-tts failed ({last_err}) — falling back to Google TTS US voice")
        gtts_ok = _gtts_synthesize(text, single, rate, warnings, tmpdir)
        if gtts_ok:
            success = True
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise RuntimeError(f"All TTS engines failed for '{text[:30]}...'")

    # --- ffmpeg: repeat 5x with 0.5s silence gaps ---
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            silence = tmpdir / "silence.mp3"
            cmd_sil = [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                       "-t", "0.5", "-q:a", "9", "-acodec", "libmp3lame", str(silence)]
            r = subprocess.run(cmd_sil, capture_output=True, text=True)
            if r.returncode != 0 or not silence.exists():
                raise RuntimeError(f"ffmpeg silence generation failed: {r.stderr[:300]}")
            list_file = tmpdir / "concat.txt"
            with open(list_file, "w", encoding="utf-8") as f:
                for i in range(5):
                    f.write(f"file '{single}'\n")
                    if i < 4:
                        f.write(f"file '{silence}'\n")
            tmp_final = tmpdir / "final.mp3"
            cmd_concat = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(tmp_final)]
            r2 = subprocess.run(cmd_concat, capture_output=True, text=True)
            if r2.returncode != 0 or not tmp_final.exists():
                cmd_re = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:a", "libmp3lame", str(tmp_final)]
                r3 = subprocess.run(cmd_re, capture_output=True, text=True)
                if r3.returncode != 0 or not tmp_final.exists():
                    raise RuntimeError(f"ffmpeg concat failed: {r2.stderr[:300]} / {r3.stderr[:300]}")
            shutil.copy2(tmp_final, final_path)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return "generated"
        except Exception as e:
            warnings.append(f"WARNING: ffmpeg concat failed ({e}), falling back to joined-text")

    # --- joined-text fallback (no ffmpeg) ---
    warnings.append("WARNING: ffmpeg not available — using joined-text fallback; 0.5 s gap not guaranteed")
    repeated = ". ".join([text] * 5) + "."
    fallback_ok = False
    for voice in MALE_VOICES:
        for attempt in range(1, 4):
            if synthesize_once(repeated, final_path, voice, rate):
                fallback_ok = True
                break
            time.sleep(0.5 * attempt)
        if fallback_ok:
            break
    if not fallback_ok:
        fallback_ok = _gtts_synthesize(repeated, final_path, rate, warnings, tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)
    if not fallback_ok:
        raise RuntimeError(f"All TTS engines failed for repeated text '{text[:30]}...'")
    return "generated"


def _rate_to_atempo(rate: str) -> float:
    """Convert edge-tts rate string (e.g. '-15%', '+10%') to ffmpeg atempo factor."""
    rate = rate.strip()
    if rate.endswith("%"):
        try:
            pct = float(rate[:-1])
            factor = 1.0 + pct / 100.0
            return max(0.5, min(2.0, factor))
        except ValueError:
            pass
    return 1.0


def _gtts_synthesize(text: str, out_path: Path, rate: str, warnings: list, tmpdir: Path) -> bool:
    """Synthesize text with Google TTS (gtts) and apply speed via ffmpeg atempo."""
    try:
        from gtts import gTTS
    except ImportError:
        warnings.append("WARNING: gtts not installed — cannot use Google TTS fallback")
        return False
    try:
        raw = tmpdir / "gtts_raw.mp3"
        tts = gTTS(text, lang="en", tld="us", slow=False)
        tts.save(str(raw))
        if not raw.exists() or raw.stat().st_size == 0:
            return False
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            atempo = _rate_to_atempo(rate)
            if abs(atempo - 1.0) > 0.01:
                sped = tmpdir / "gtts_sped.mp3"
                r = subprocess.run(
                    [ffmpeg, "-y", "-i", str(raw), "-filter:a", f"atempo={atempo:.4f}",
                     "-codec:a", "libmp3lame", str(sped)],
                    capture_output=True, text=True
                )
                if r.returncode == 0 and sped.exists() and sped.stat().st_size > 0:
                    shutil.copy2(sped, out_path)
                    return True
                warnings.append(f"WARNING: ffmpeg atempo failed ({r.stderr[:200]}) — using raw gtts speed")
        shutil.copy2(raw, out_path)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception as e:
        warnings.append(f"WARNING: gtts synthesis failed: {e}")
        return False
