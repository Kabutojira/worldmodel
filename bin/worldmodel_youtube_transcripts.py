#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".worldmodel" / "youtube"
USER_AGENT = "WorldModelBot/0.2 (+https://github.com/Kabutojira/worldmodel)"
YT_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
CHANNELS = {
    "all-in": {"name": "All-In Podcast", "channel_id": "UCESLZhusAkFfsNsApnjF_Cg"},
    "the-limiting-factor": {"name": "The Limiting Factor", "channel_id": "UCIFn7ONIJHyC-lMnb7Fm_jw"},
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def sanitize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def fetch_feed(channel_id: str) -> str:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    r = session().get(url, timeout=20)
    r.raise_for_status()
    return r.text


def parse_feed(xml_text: str, max_videos: int) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    videos = []
    for entry in root.findall("atom:entry", YT_NS)[:max_videos]:
        video_id = entry.findtext("yt:videoId", default="", namespaces=YT_NS)
        title = entry.findtext("atom:title", default="", namespaces=YT_NS)
        published = entry.findtext("atom:published", default="", namespaces=YT_NS)
        description = entry.findtext("media:group/media:description", default="", namespaces=YT_NS)
        videos.append({
            "video_id": video_id,
            "title": title,
            "published_at": published,
            "description": description,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return videos


def fetch_transcript(video_url: str, language: str | None) -> dict[str, object]:
    skill_script = "/opt/data/skills/media/youtube-content/scripts/fetch_transcript.py"
    cmd = [
        "uv", "run", "--with", "youtube-transcript-api", "python3", skill_script, video_url, "--timestamps"
    ]
    if language:
        cmd.extend(["--language", language])
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        try:
            return {"error": json.loads(proc.stdout or proc.stderr).get("error", proc.stderr.strip() or proc.stdout.strip())}
        except Exception:
            return {"error": proc.stderr.strip() or proc.stdout.strip() or "transcript fetch failed"}
    return json.loads(proc.stdout)


def matches_keywords(video: dict[str, str], keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f'{video.get("title", "")} {video.get("description", "")}'.lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recent YouTube video transcripts for selected channels.")
    parser.add_argument("--channel", action="append", choices=sorted(CHANNELS), help="Channel key to fetch. Repeatable.")
    parser.add_argument("--max-videos", type=int, default=3)
    parser.add_argument("--keywords", default="", help="Comma-separated keyword filter for titles/descriptions.")
    parser.add_argument("--language", default="en")
    parser.add_argument("--out", default=str(ROOT / ".worldmodel" / "youtube_transcripts_index.json"))
    args = parser.parse_args()

    channels = args.channel or list(CHANNELS.keys())
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at": None, "videos": []}

    for key in channels:
        meta = CHANNELS[key]
        channel_slug = sanitize(key)
        channel_dir = CACHE_DIR / channel_slug
        channel_dir.mkdir(parents=True, exist_ok=True)
        videos = parse_feed(fetch_feed(meta["channel_id"]), args.max_videos)
        for video in videos:
            if not matches_keywords(video, keywords):
                continue
            transcript = fetch_transcript(video["url"], args.language)
            json_path = channel_dir / f'{video["video_id"]}.json'
            record = {
                "channel_key": key,
                "channel_name": meta["name"],
                **video,
                "transcript_available": "error" not in transcript,
                "transcript_path": str(json_path),
            }
            if "error" in transcript:
                record["transcript_error"] = transcript["error"]
            else:
                json_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
                txt_path = channel_dir / f'{video["video_id"]}.txt'
                txt_path.write_text(transcript.get("timestamped_text") or transcript.get("full_text", ""), encoding="utf-8")
                record["segment_count"] = transcript.get("segment_count")
                record["duration"] = transcript.get("duration")
                record["text_path"] = str(txt_path)
            manifest["videos"].append(record)

    manifest["generated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out_path), "videos": len(manifest["videos"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
