"""Agent Vidéo : script (LLM, JSON structuré) → diapositives (Pillow) → voix (macOS `say`) → MP4 (MoviePy/FFmpeg)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from . import config
from .agent import Agent, structured


class Scene(BaseModel):
    title: str
    bullets: list[str]
    narration: str


class Script(BaseModel):
    title: str
    scenes: list[Scene]


PALETTE = [(24, 39, 76), (17, 94, 89), (88, 28, 135), (153, 27, 27), (30, 64, 175), (55, 65, 81)]
FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40] or "video"


def _font(size: int):
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _make_slide(scene: dict, path: Path, size: tuple[int, int], idx: int, total: int) -> None:
    from PIL import Image, ImageDraw
    w, h = size
    img = Image.new("RGB", size, PALETTE[(idx - 1) % len(PALETTE)])
    d = ImageDraw.Draw(img)
    margin = int(w * 0.07)
    y = int(h * 0.12)
    for line in _wrap(d, scene["title"], _font(int(h * 0.09)), w - 2 * margin):
        d.text((margin, y), line, font=_font(int(h * 0.09)), fill="white")
        y += int(h * 0.11)
    y += int(h * 0.05)
    f_b = _font(int(h * 0.055))
    for b in scene.get("bullets", [])[:4]:
        for j, line in enumerate(_wrap(d, b, f_b, w - 2 * margin - 40)):
            d.text((margin + (0 if j == 0 else 40), y), ("•  " if j == 0 else "") + line, font=f_b, fill=(230, 235, 245))
            y += int(h * 0.075)
        y += int(h * 0.02)
    d.text((w - margin - 80, h - int(h * 0.09)), f"{idx}/{total}", font=_font(int(h * 0.04)), fill=(190, 200, 220))
    img.save(path)


def _tts(text: str, out: Path, voice: str):
    """Voix gratuite intégrée à macOS. Renvoie None si `say` est absent."""
    if not shutil.which("say"):
        return None
    r = subprocess.run(["say", "-v", voice, "-o", str(out), text], capture_output=True)
    if r.returncode != 0:  # voix non installée → voix par défaut
        r = subprocess.run(["say", "-o", str(out), text], capture_output=True)
    return out if r.returncode == 0 and out.exists() else None


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ----------------------------------------------------------------------
def create_video_script(topic: str, n_scenes: int = 5, language: str = "français") -> str:
    """Écrit le script structuré (scènes, puces, narration) d'une vidéo explicative et l'enregistre en JSON.

    Args:
        topic: Le sujet de la vidéo.
        n_scenes: Nombre de scènes (défaut 5).
        language: Langue de la vidéo (défaut français).
    """
    n_scenes = int(n_scenes)
    prompt = (
        f"Écris le script d'une vidéo explicative en {language} sur : {topic}.\n"
        f"Exactement {n_scenes} scènes. Pour chaque scène : title (court), bullets (2 à 3 puces de moins de "
        f"8 mots), narration (2 à 3 phrases naturelles à dire à voix haute). Réponds uniquement en JSON."
    )
    data = Script.model_validate(
        structured(config.MODEL_GENERAL, config.load_prompt("video"), prompt, Script.model_json_schema())
    )
    folder = config.OUTPUTS / f"video_{_slug(topic)}_{datetime.now():%Y%m%d_%H%M%S}"
    folder.mkdir(parents=True)
    path = folder / "scenes.json"
    path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    return f"Script « {data.title} » : {len(data.scenes)} scènes → {path}"


def render_video(scenes_json_path: str, voice: str = "") -> str:
    """Génère la vidéo MP4 (+ sous-titres .srt) à partir d'un fichier scenes.json.

    Args:
        scenes_json_path: Chemin du scenes.json créé par create_video_script.
        voice: Voix macOS (défaut : celle du fichier .env).
    """
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

    p = Path(scenes_json_path)
    if not p.exists():
        p = config.ROOT / scenes_json_path
    data = json.loads(p.read_text(encoding="utf-8"))
    scenes = data["scenes"]
    assets = p.parent / "assets"
    assets.mkdir(exist_ok=True)
    size = (1280, 720)

    clips, srt, t = [], [], 0.0
    for i, sc in enumerate(scenes, 1):
        png = assets / f"slide_{i:02d}.png"
        _make_slide(sc, png, size, i, len(scenes))
        audio = _tts(sc["narration"], assets / f"voice_{i:02d}.aiff", voice or config.TTS_VOICE)
        if audio:
            a = AudioFileClip(str(audio))
            dur = a.duration + 0.6
            clip = ImageClip(str(png)).with_duration(dur).with_audio(a)
        else:
            dur = max(3.0, len(sc["narration"].split()) / 2.6)
            clip = ImageClip(str(png)).with_duration(dur)
        srt.append(f"{i}\n{_srt_time(t)} --> {_srt_time(t + dur - 0.3)}\n{sc['narration']}\n")
        clips.append(clip)
        t += dur

    out = p.parent / "video.mp4"
    concatenate_videoclips(clips, method="compose").write_videofile(
        str(out), fps=24, codec="libx264", audio_codec="aac", ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    (p.parent / "video.srt").write_text("\n".join(srt), encoding="utf-8")
    return f"Vidéo prête : {out} ({t:.0f} s). Sous-titres : {p.parent / 'video.srt'}"


def make_video(topic: str, n_scenes: int = 5, voice: str = "") -> str:
    """Pipeline complet : script + rendu MP4 pour un sujet."""
    msg = create_video_script(topic, n_scenes)
    path = msg.split("→")[-1].strip()
    return msg + "\n" + render_video(path, voice)


def list_outputs() -> str:
    """Liste les vidéos et fichiers déjà générés dans outputs/."""
    files = sorted(str(p.relative_to(config.OUTPUTS)) for p in config.OUTPUTS.rglob("*")
                   if p.is_file() and p.suffix in {".mp4", ".json", ".srt", ".csv"})
    return "\n".join(files) or "(rien pour l'instant)"


def build_agent() -> Agent:
    return Agent(
        name="Agent Vidéo",
        model=config.MODEL_GENERAL,
        system=config.load_prompt("video"),
        tools=[create_video_script, render_video, list_outputs],
        temperature=0.3,
    )
