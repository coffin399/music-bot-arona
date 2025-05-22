from __future__ import annotations
import asyncio
from pathlib import Path
import http.cookiejar as cookiejar
from typing import List, Union

import yt_dlp
from yt_dlp.utils import ExtractorError
from domain.entity.track import Track
from config import config

CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

NICO_COOKIE_PATH = Path("./nico_cookies.txt")

COMMON_OPTS: dict = {
    "format": "bestaudio/best",
    "paths":   {"home": str(CACHE_DIR)},
    "outtmpl": "%(id)s.%(ext)s",
    "noplaylist": True,
    "concurrent_fragment_downloads": 4,
    "postprocessors": [
        {"key": "FFmpegExtractAudio",
         "preferredcodec": "mp3",
         "preferredquality": "0"},
        {"key": "FFmpegMetadata"},
    ],
    "quiet": False,
    "no_warnings": False,
    "source_address": "0.0.0.0",
}

def build_nico_opts(login: bool) -> dict:
    opts = COMMON_OPTS.copy()
    opts["cookiefile"] = str(NICO_COOKIE_PATH)
    if login:
        opts.update(
            username=config.get("niconico.email"),
            password=config.get("niconico.password"),
        )
    return opts


async def extract(query: str) -> Union[Track, List[Track]]:
    loop = asyncio.get_running_loop()
    is_nico = _is_nico(query)
    opts    = build_nico_opts(login=not NICO_COOKIE_PATH.exists()) if is_nico else COMMON_OPTS

    def _download() -> tuple[dict, yt_dlp.YoutubeDL]:
        ytdl = yt_dlp.YoutubeDL(opts)
        info = ytdl.extract_info(query, download=True)

        if info is None:
            info = ytdl.extract_info(query, download=False)

        def _inject_local_path(entry: dict):
            if entry is None:
                return
            if entry.get("requested_downloads"):
                entry["local_path"] = entry["requested_downloads"][0]["filepath"]
            else:
                entry["local_path"] = Path(
                    ytdl.prepare_filename(entry)
                ).with_suffix(".mp3")


        if isinstance(info, dict) and "entries" in info:
            for ent in info["entries"]:
                _inject_local_path(ent)
        else:
            _inject_local_path(info)

        return info, ytdl

    try:
        info, ytdl = await loop.run_in_executor(None, _download)
    except ExtractorError as e:
        raise RuntimeError(f"yt-dl 失敗: {e}") from e

    if is_nico:
        try:
            ytdl.cookiejar.save(
                str(NICO_COOKIE_PATH),
                ignore_discard=True,
                ignore_expires=True,
            )
        except Exception as e:
            print(f"[warn] cookie 保存失敗: {e}")

    if "entries" in info and isinstance(info["entries"], list):
        tracks: List[Track] = []
        for entry in info["entries"]:
            if not entry:
                continue
            track_path = entry.get("local_path") or Path(CACHE_DIR, f"{entry['id']}.mp3")
            tracks.append(
                Track(
                    title        = entry.get("title"),
                    url          = entry.get("webpage_url"),
                    stream_url   = str(track_path),
                    duration     = entry.get("duration") or 0,
                    thumbnail    = entry.get("thumbnail"),
                    requester_id = 0,
                )
            )
        return tracks

    return Track(
        title        = info.get("title"),
        url          = info.get("webpage_url"),
        stream_url   = str(info["local_path"]),
        duration     = info.get("duration") or 0,
        thumbnail    = info.get("thumbnail"),
        requester_id = 0,
    )

def _is_nico(url: str) -> bool:
    return "nicovideo.jp" in url or "nico.ms" in url