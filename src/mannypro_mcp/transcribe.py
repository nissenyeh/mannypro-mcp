"""Local podcast transcription with faster-whisper, run as a detached background process.

The MCP tool starts `python -m mannypro_mcp.transcribe <audio> <out.md> ...` and returns at once
(agent tool calls time out long before a 30–90 minute episode is done). Progress is written to
`<out>.status.json` so later tool calls can report it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = os.environ.get("MANNYPRO_WHISPER_MODEL", "small")
PROMPT = "以下是繁體中文的 Podcast 逐字稿，來自《曼報 Pro》，主持人是 Manny。"


def status_path(out_md: Path) -> Path:
    return out_md.with_name(out_md.name + ".status.json")


def read_status(out_md: Path) -> dict | None:
    try:
        return json.loads(status_path(out_md).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_status(out_md: Path, **fields) -> None:
    path = status_path(out_md)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({**fields, "updatedAt": time.time()}, ensure_ascii=False))
    tmp.replace(path)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_running(out_md: Path) -> bool:
    st = read_status(out_md)
    return bool(st and st.get("state") in ("loading", "transcribing") and _alive(st.get("pid", -1)))


def start(audio: Path, out_md: Path, title: str, source_url: str, model: str = DEFAULT_MODEL) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    _write_status(out_md, state="loading", progress=0.0, model=model, pid=0)
    log = open(out_md.with_name(out_md.name + ".log"), "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "mannypro_mcp.transcribe", str(audio), str(out_md),
         "--title", title, "--source", source_url, "--model", model],
        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    _write_status(out_md, state="loading", progress=0.0, model=model, pid=proc.pid)


def _ts(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def run(audio: Path, out_md: Path, title: str, source_url: str, model: str) -> None:
    pid = os.getpid()
    started = time.time()
    try:
        from faster_whisper import WhisperModel

        _write_status(out_md, state="loading", progress=0.0, model=model, pid=pid)
        whisper = WhisperModel(model, device="auto", compute_type="int8")
        segments, info = whisper.transcribe(str(audio), language="zh", initial_prompt=PROMPT, vad_filter=True)
        duration = info.duration or 1

        # Group segments into ~30 second paragraphs, each led by its start time.
        paragraphs: list[str] = []
        buf: list[str] = []
        para_start = 0.0
        for seg in segments:
            if not buf:
                para_start = seg.start
            buf.append(seg.text.strip())
            if seg.end - para_start >= 30:
                paragraphs.append(f"**[{_ts(para_start)}]** " + "".join(buf))
                buf = []
            _write_status(out_md, state="transcribing", progress=min(seg.end / duration, 1.0),
                          model=model, pid=pid, elapsedSec=round(time.time() - started))
        if buf:
            paragraphs.append(f"**[{_ts(para_start)}]** " + "".join(buf))

        header = [f"# {title}", "", f"- 來源：{source_url}", f"- 長度：{_ts(duration)}",
                  f"- 逐字稿：本機 faster-whisper（{model} 模型）自動轉錄，可能有錯字", ""]
        out_md.write_text("\n".join(header) + "\n" + "\n\n".join(paragraphs) + "\n")
        _write_status(out_md, state="done", progress=1.0, model=model, pid=pid,
                      elapsedSec=round(time.time() - started))
    except Exception as e:  # surfaced to the agent through the status file
        _write_status(out_md, state="error", error=f"{type(e).__name__}: {e}", model=model, pid=pid)
        raise


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--title", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    run(a.audio, a.out, a.title or a.audio.stem, a.source, a.model)


if __name__ == "__main__":
    main()
