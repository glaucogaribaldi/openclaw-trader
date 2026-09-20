"""
Content pipeline: download, edit, caption rewrite.

Download:   yt-dlp pulls from source TikTok channels.
Edit:       ffmpeg LUT color grade, speed/pitch jitter.
Caption:    OpenAI rewrites per target country (US vs UK hook style).
"""
import subprocess
import json
import os
import random
from openai import OpenAI

OPENAI_CLIENT = None


def get_openai():
    global OPENAI_CLIENT
    if OPENAI_CLIENT is None:
        OPENAI_CLIENT = OpenAI()
    return OPENAI_CLIENT


def fetch_channel_videos(channel: str, count: int = 9) -> list:
    """Return metadata for the latest N videos from a TikTok channel via yt-dlp."""
    cmd = ["yt-dlp", "-j", "--playlist-items", f"1-{count}", f"https://www.tiktok.com/@{channel}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return []
    videos = []
    for line in proc.stdout.strip().splitlines():
        try:
            videos.append(json.loads(line))
        except Exception:
            continue
    videos.sort(key=lambda v: v.get("timestamp", 0), reverse=True)
    return videos


def download_video(url: str, out_path: str) -> bool:
    cmd = ["yt-dlp", "-o", out_path, url]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    return proc.returncode == 0


def adjust_speed(input_path: str, output_path: str, factor: float = None) -> bool:
    if factor is None:
        factor = random.uniform(0.95, 1.05)
    audio_factor = 1 / factor
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", f"[0:v]setpts={1/factor:.4f}*PTS[v];[0:a]atempo={audio_factor:.4f}[a]",
        "-map", "[v]", "-map", "[a]", output_path
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    return proc.returncode == 0


def pick_random_lut(lut_dir: str) -> str | None:
    if not os.path.isdir(lut_dir):
        return None
    luts = [f for f in os.listdir(lut_dir) if f.endswith(".cube")]
    return os.path.join(lut_dir, random.choice(luts)) if luts else None


def apply_lut(input_path: str, output_path: str, lut_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"lut3d='{lut_path}'",
        "-c:a", "copy", output_path
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    return proc.returncode == 0


def rewrite_caption(original: str, country: str = "US") -> str:
    """Rewrite a TikTok caption for the target market using OpenAI."""
    style = "casual American hook-first TikTok style" if country in ("US", "MX") else "British English, slightly more formal, local references where natural"
    prompt = (
        f"Rewrite this TikTok video caption for a {country} audience in {style}. "
        f"Keep it under 150 characters. Return only the caption text.\n\nOriginal: {original}"
    )
    try:
        resp = get_openai().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return original