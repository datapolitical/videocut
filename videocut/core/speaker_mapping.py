"""Speaker mapping utilities using speaker embeddings."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

__all__ = ["build_speaker_db", "apply_speaker_map"]


def build_speaker_db(samples_dir: str, out_json: str = "speaker_db.json") -> None:
    """Compute embeddings from WAV files in ``samples_dir`` and save to JSON."""
    try:
        from speechbrain.pretrained import EncoderClassifier
        import torchaudio
    except Exception as exc:
        raise RuntimeError("speechbrain and torchaudio are required for speaker embedding") from exc

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": "cpu"},
    )

    db: Dict[str, List[float]] = {}
    for wav in Path(samples_dir).glob("*.wav"):
        wav_name = wav.stem.replace("_", " ")
        waveform, sr = torchaudio.load(str(wav))
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        emb = classifier.encode_batch(waveform).squeeze().tolist()
        db[wav_name] = emb

    Path(out_json).write_text(json.dumps(db, indent=2))
    print(f"✅  {len(db)} speaker embedding(s) → {out_json}")


def _load_audio(video: str, tmp_wav: Path) -> tuple["torch.Tensor", int]:
    """Extract mono 16kHz audio from ``video`` to ``tmp_wav`` and return waveform."""
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", video,
        "-ac", "1", "-ar", "16000", str(tmp_wav)
    ], check=True)
    from torchaudio import load  # type: ignore
    waveform, sr = load(str(tmp_wav))
    tmp_wav.unlink()
    return waveform, sr


def apply_speaker_map(
    video: str,
    diarized_json: str,
    db_json: str = "speaker_db.json",
    out_json: Optional[str] = None,
    threshold: float = 0.75,
) -> None:
    """Replace diarized speaker labels with real names using embeddings."""
    try:
        from speechbrain.pretrained import EncoderClassifier
        import torch
        import torchaudio
    except Exception as exc:
        raise RuntimeError("speechbrain and torchaudio are required for speaker mapping") from exc

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": "cpu"},
    )

    db_raw = json.loads(Path(db_json).read_text())
    db = {name: torch.tensor(vec) for name, vec in db_raw.items()}

    data = json.loads(Path(diarized_json).read_text())
    segments = data.get("segments", [])

    tmp_wav = Path("_tmp_audio.wav")
    waveform, sr = _load_audio(video, tmp_wav)

    spk_frames: Dict[str, List[tuple[int, int]]] = {}
    for seg in segments:
        spk = seg.get("speaker")
        if not spk:
            continue
        start, end = int(float(seg["start"]) * sr), int(float(seg["end"]) * sr)
        spk_frames.setdefault(spk, []).append((start, end))

    spk_embs: Dict[str, torch.Tensor] = {}
    for spk, ranges in spk_frames.items():
        embs = []
        for s, e in ranges:
            piece = waveform[:, s:e]
            if piece.numel() == 0:
                continue
            emb = classifier.encode_batch(piece).squeeze()
            embs.append(emb)
        if embs:
            spk_embs[spk] = torch.stack(embs).mean(dim=0)

    mapping: Dict[str, str] = {}
    for spk, emb in spk_embs.items():
        best_name = None
        best_score = -1.0
        for name, db_emb in db.items():
            score = torch.nn.functional.cosine_similarity(emb, db_emb, dim=0).item()
            if score > best_score:
                best_score = score
                best_name = name
        if best_name and best_score >= threshold:
            mapping[spk] = best_name

    if mapping:
        if "word_segments" in data:
            for ws in data["word_segments"]:
                spk = ws.get("speaker")
                if spk in mapping:
                    ws["speaker"] = mapping[spk]
        for seg in segments:
            spk = seg.get("speaker")
            if spk in mapping:
                seg["speaker"] = mapping[spk]

    Path(out_json or diarized_json).write_text(json.dumps(data, indent=2))
    if mapping:
        print(f"✅  Applied speaker mapping ({len(mapping)} match(es))")
    else:
        print("ℹ️  No speaker matches found")
