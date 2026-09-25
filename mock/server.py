#!/usr/bin/env python3
"""
Mock of the comfy-bridge backend for the 🎬 Видео SillyTavern extension.
Standard library only. Implements the bridge contract from README.md plus a
fake OpenAI-compatible vision endpoint so the whole flow can be tested
without a GPU or a real model.

    python3 mock/server.py --port 8787 --key test-key

Endpoints (prefix is empty by default, see --prefix):
    GET  {prefix}/video/loras           LoRA catalogue        -> {"loras": [{"name","triggers","hint","strength","group"}]}
    POST {prefix}/video/jobs            create a job          -> {"id": "..."}
         body: image (base64) | start_job, prompt, sec, res, seed, lora ["set:strength", ...],
               quality "fast"|"hi", smooth bool, neg_extra str, deliver chat|tg|both, chat, message_id
    GET  {prefix}/video/jobs/{id}       job status            -> {"status": ..., "position": n, "elapsed": s, "error": "...", "video_url": "...",
                                                                  "quality": ..., "smooth": ..., "start_job": ...}
    GET  {prefix}/video/jobs/{id}/file  the rendered mp4
    GET  {prefix}/video/jobs/{id}/last  PNG of the last frame of a finished job (96x64 here)
    POST {prefix}/v1/chat/completions   fake vision model (OpenAI chat format, returns JSON {"lora","prompt"})
    GET  {prefix}/v1/models             model list for the fake vision model
    GET  {prefix}/  or /health          {"ok": true, "comfy": "mock"}  (settings «Тест» button)

The fake render takes --queue-seconds in the queue and --render-seconds rendering,
then returns a tiny embedded mp4 (or the file given with --video).
A prompt containing "[fail]" (or starting the mock with --fail) ends the job with status=error.
"""

import argparse
import base64
import json
import struct
import sys
import zlib
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# 64x64, 1 second, h264 — generated with ffmpeg (testsrc), ~5 KB.
TINY_MP4_B64 = """
AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAANCbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAA+gAAQAAAQAA
AAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAA
Am10cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAA+gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAA
AAAAAAAAAAAAAABAAAAAAEAAAABAAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAPoAAAAAAABAAAAAAHlbWRpYQAAACBtZGhk
AAAAAAAAAAAAAAAAAABAAAAAQABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABkG1p
bmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAVBzdGJsAAAAuHN0c2QA
AAAAAAAAAQAAAKhhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAEAAQABIAAAASAAAAAAAAAABFExhdmM2MS4zLjEwMCBsaWJ4
MjY0AAAAAAAAAAAAAAAAGP//AAAALmF2Y0MBQsAK/+EAFmdCwAraEJsBEAAAAwAQAAADAQDxImoBAAVozgJcgAAAABBwYXNwAAAA
AQAAAAEAAAAUYnRydAAAAAAAAIOYAACDmAAAABhzdHRzAAAAAAAAAAEAAAAIAAAIAAAAABRzdHNzAAAAAAAAAAEAAAABAAAAHHN0
c2MAAAAAAAAAAQAAAAEAAAAIAAAAAQAAADRzdHN6AAAAAAAAAAAAAAAIAAAFIgAAA04AAAGaAAABbQAAATQAAAE9AAABWQAAATIA
AAAUc3RjbwAAAAAAAAABAAADcgAAAGF1ZHRhAAAAWW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAA
LGlsc3QAAAAkqXRvbwAAABxkYXRhAAAAAQAAAABMYXZmNjEuMS4xMDAAAAAIZnJlZQAAEHttZGF0AAACUwYF//9P3EXpvebZSLeW
LNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzE5MSA0NjEzYWMzIC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIw
MDMtMjAyNCAtIGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTAgcmVmPTEgZGVibG9j
az0wOjA6MCBhbmFseXNlPTA6MCBtZT1kaWEgc3VibWU9MCBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0wIG1lX3Jh
bmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MCA4eDhkY3Q9MCBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hy
b21hX3FwX29mZnNldD0wIHRocmVhZHM9MiBsb29rYWhlYWRfdGhyZWFkcz0xIHNsaWNlZF90aHJlYWRzPTAgbnI9MCBkZWNpbWF0
ZT0xIGludGVybGFjZWQ9MCBibHVyYXlfY29tcGF0PTAgY29uc3RyYWluZWRfaW50cmE9MCBiZnJhbWVzPTAgd2VpZ2h0cD0wIGtl
eWludD0yNTAga2V5aW50X21pbj04IHNjZW5lY3V0PTAgaW50cmFfcmVmcmVzaD0wIHJjPWNyZiBtYnRyZWU9MCBjcmY9MzUuMCBx
Y29tcD0wLjYwIHFwbWluPTAgcXBtYXg9NjkgcXBzdGVwPTQgaXBfcmF0aW89MS40MCBhcT0wAIAAAALHZYiEOgxgAeiIGdEONgsb
fvXv4Au6Q3MeuADytes1YKT+ugBaqY3MevDiASkQAA+AxgTG8Njj+GgBHkUw1ZghAkUgkZgDGAEBBWUxgBADzdqKX8ACv2adUEEo
gJhpYf/hoBgAgEACAAIA4goUlmANXwIBtpxZq/2UXUC++NNDhjAdAbSlAEAAEBZ+BwTjyw4Jx5fnCZMm5/8JAAgoAAgBhACwG0gJ
jSwDfKYg2zz9+gG5imEBNnnwxgCEvYS2Ka/EaEDKj4AZGioJff6//AImOI3wPgMS1GWyZGHQcrxnrhCf114YEc5BAAHwABADoMR9
Pnmv+uspaA0Ob5wYFQbTmTaPCWAAjNgfd1FYx+vAgQAAxlLM9EjPvi3mZAl6iccZq4iSZgAGQEYq4H/FES/Iwf6g5ARirhACObcD
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
"""

ARGS = None
VIDEO_BYTES = b""

# The LoRA catalogue the real bridge serves from its ComfyUI folder.
LORA_CATALOG = [
    {"name": "nsfw", "triggers": [], "hint": "nudity / sensual scenes, no explicit acts", "strength": 1.0, "group": "body"},
    {"name": "dreamlay", "triggers": ["bl0wj0b", "d0ubl3_bj", "d0gg1e", "c0wg1rl", "r3v3rs3_c0wg1rl", "m15510n4ry"],
     "hint": "explicit sex acts; start the prompt with one trigger word", "strength": 0.9, "group": "explicit"},
    {"name": "slow_pan", "triggers": ["sl0wpan"], "hint": "slow camera pan instead of a static camera", "strength": 0.7, "group": "camera"},
]
LORA_NAMES = {entry["name"] for entry in LORA_CATALOG}
JOBS = {}
ORDER = []  # job ids in creation order (for queue positions)
LOCK = threading.Lock()


def log(*parts):
    print(time.strftime("%H:%M:%S"), "[mock-bridge]", *parts, flush=True)


def now():
    return time.monotonic()


def strip_prefix(path):
    prefix = ARGS.prefix.rstrip("/")
    if prefix and path.startswith(prefix):
        path = path[len(prefix):]
    return path or "/"


def decode_image(value):
    """Accepts raw base64 or a data URL. Returns (bytes, mime)."""
    if not isinstance(value, str) or not value:
        raise ValueError("image is missing")
    mime = "image/png"
    if value.startswith("data:"):
        header, _, value = value.partition(",")
        mime = header[5:].split(";")[0] or mime
    try:
        data = base64.b64decode(value, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"image is not valid base64: {exc}") from exc
    if not data:
        raise ValueError("image is empty")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    return data, mime


def make_png(width, height, rgb):
    """Solid-colour RGB PNG (stdlib only) — stands in for the last frame of a clip."""
    row = b"\x00" + bytes(rgb) * width
    raw = row * height

    def chunk(tag, payload):
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


LAST_FRAME_PNG = make_png(96, 64, (180, 60, 200))


def parse_lora_list(value):
    """Validates ["name:strength", ...] against the catalogue. Returns [(name, strength)]."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("lora must be a list of 'name:strength' strings")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError("lora entries must be non-empty strings")
        name, sep, strength = item.partition(":")
        if name not in LORA_NAMES:
            raise ValueError(f"unknown lora set: {name!r} (known: {sorted(LORA_NAMES)})")
        try:
            weight = float(strength) if sep else 1.0
        except ValueError as exc:
            raise ValueError(f"bad strength in {item!r}") from exc
        if not 0.0 <= weight <= 2.0:
            raise ValueError(f"strength out of range in {item!r}")
        result.append((name, weight))
    return result


def png_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def render_worker(job_id):
    with LOCK:
        job = JOBS[job_id]
    # Wait for our turn: everything created before us must be finished.
    while True:
        with LOCK:
            ahead = [j for j in ORDER if j != job_id and JOBS[j]["status"] in ("queued", "rendering") and ORDER.index(j) < ORDER.index(job_id)]
        if not ahead:
            break
        time.sleep(0.25)
    time.sleep(ARGS.queue_seconds)
    with LOCK:
        job["status"] = "rendering"
        job["started"] = now()
    log(f"job {job_id}: rendering ({ARGS.render_seconds}s)")
    time.sleep(ARGS.render_seconds)
    with LOCK:
        if ARGS.fail or "[fail]" in job["request"].get("prompt", "").lower():
            job["status"] = "error"
            job["error"] = "mock render failed" + (" (started with --fail)" if ARGS.fail else " (prompt contains [fail])")
        else:
            job["status"] = "done"
            job["video_url"] = f"{ARGS.prefix.rstrip('/')}/video/jobs/{job_id}/file"
        job["finished"] = now()
    if job["status"] == "done":
        log(f"job {job_id}: done -> {job['video_url']}")
        if job["deliver"] in ("tg", "both"):
            log(f"job {job_id}: (mock) would send the video to Telegram")
    else:
        log(f"job {job_id}: error: {job['error']}")


def job_public(job):
    status = job["status"]
    with LOCK:
        position = 0
        if status == "queued":
            position = 1 + sum(
                1 for j in ORDER
                if JOBS[j]["status"] in ("queued", "rendering") and ORDER.index(j) < ORDER.index(job["id"])
            )
    elapsed = 0.0
    if job.get("started"):
        elapsed = (job.get("finished") or now()) - job["started"]
    return {
        "id": job["id"],
        "status": status,
        "position": position,
        "elapsed": round(elapsed, 1),
        "error": job.get("error"),
        "video_url": job.get("video_url"),
        "quality": job.get("quality"),
        "smooth": job.get("smooth"),
        "start_job": job.get("start_job"),
    }


def fake_vision_answer(body):
    """Builds a canned JSON answer and reports whether an image part arrived."""
    messages = body.get("messages") or []
    image_info = "no image part received"
    text_len = 0
    system_seen = any(m.get("role") == "system" for m in messages if isinstance(m, dict))
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text_len += len(part.get("text") or "")
                if part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url") or ""
                    try:
                        data, mime = decode_image(url)
                        size = png_size(data)
                        image_info = f"image received: {mime}, {len(data)} bytes" + (f", {size[0]}x{size[1]}" if size else "")
                    except ValueError as exc:
                        image_info = f"image part present but unreadable: {exc}"
        elif isinstance(content, str):
            text_len += len(content)
    user_text = " ".join(
        part.get("text", "") for m in messages if isinstance(m, dict) and isinstance(m.get("content"), list)
        for part in m["content"] if isinstance(part, dict) and part.get("type") == "text"
    )
    continuation = "Continue the motion from this frame" in user_text
    log(f"vision request: model={body.get('model')} messages={len(messages)} system={system_seen} "
        f"text_chars={text_len} continuation={continuation} :: {image_info}")
    if continuation:
        # string form of "lora" — the extension must accept both a string and an array
        answer = {
            "lora": "nsfw",
            "prompt": (
                "Anime style. Seraphina keeps turning and steps closer, her hair settling on her shoulders "
                f"as the breeze fades. [mock continuation: {image_info}] camera static, smooth continuous motion"
            ),
        }
    else:
        answer = {
            "lora": ["nsfw", "unknown_set"],
            "prompt": (
                "Anime style. Seraphina slowly turns toward the viewer and brushes her hair back, "
                "her dress swaying gently in the breeze while leaves drift past. "
                f"[mock: {image_info}] camera static, smooth continuous motion"
            ),
        }
    return json.dumps(answer, ensure_ascii=False)


class Handler(BaseHTTPRequestHandler):
    server_version = "MockComfyBridge/1.0"

    # ---- helpers -------------------------------------------------------
    def log_message(self, fmt, *args):  # quieter default logging
        if ARGS.verbose:
            super().log_message(fmt, *args)

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def send_json(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, code, data, content_type):
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def authorized(self):
        if not ARGS.key:
            return True
        header = self.headers.get("Authorization") or ""
        return header == f"Bearer {ARGS.key}"

    # ---- routing -------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = strip_prefix(urlparse(self.path).path)
        if path in ("/", "/health"):
            # the settings panel's «Тест» button expects {ok, comfy}
            return self.send_json(200, {"ok": True, "comfy": "mock", "jobs": len(JOBS)})
        if path == "/v1/models":
            return self.send_json(200, {"object": "list", "data": [{"id": "mock-vision", "object": "model"}]})
        if path == "/video/loras":
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            return self.send_json(200, {"loras": LORA_CATALOG})
        if path.startswith("/video/jobs/"):
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            rest = path[len("/video/jobs/"):].strip("/")
            parts = rest.split("/")
            job = JOBS.get(parts[0])
            if not job:
                return self.send_json(404, {"error": "job not found"})
            if len(parts) == 1:
                return self.send_json(200, job_public(job))
            if len(parts) == 2 and parts[1] == "file":
                if job["status"] != "done":
                    return self.send_json(409, {"error": "job is not done yet"})
                return self.send_bytes(200, VIDEO_BYTES, "video/mp4")
            if len(parts) == 2 and parts[1] == "last":
                if job["status"] != "done":
                    return self.send_json(409, {"error": "job is not done yet"})
                return self.send_bytes(200, LAST_FRAME_PNG, "image/png")
        return self.send_json(404, {"error": f"no route for GET {path}"})

    def do_POST(self):
        path = strip_prefix(urlparse(self.path).path)
        try:
            body = self.read_json()
        except Exception as exc:  # noqa: BLE001
            return self.send_json(400, {"error": f"invalid JSON: {exc}"})

        if path == "/v1/chat/completions":
            content = fake_vision_answer(body)
            return self.send_json(200, {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model") or "mock-vision",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            })

        if path == "/video/jobs":
            if not self.authorized():
                return self.send_json(401, {"error": "unauthorized"})
            start_job = body.get("start_job")
            image, mime = b"", None
            if start_job is not None and body.get("image"):
                return self.send_json(400, {"error": "send either image or start_job, not both"})
            if start_job is not None:
                parent = JOBS.get(str(start_job))
                if not parent:
                    return self.send_json(404, {"error": f"start_job {start_job!r} not found"})
                if parent["status"] != "done":
                    return self.send_json(409, {"error": f"start_job {start_job!r} is not done yet"})
                start_job = str(start_job)
            else:
                try:
                    image, mime = decode_image(body.get("image"))
                except ValueError as exc:
                    return self.send_json(400, {"error": str(exc)})
            prompt = str(body.get("prompt") or "").strip()
            if not prompt:
                return self.send_json(400, {"error": "prompt is required"})
            deliver = body.get("deliver") or "chat"
            if deliver not in ("chat", "tg", "both"):
                return self.send_json(400, {"error": "deliver must be chat|tg|both"})
            try:
                loras = parse_lora_list(body.get("lora"))
            except ValueError as exc:
                return self.send_json(400, {"error": str(exc)})
            quality = body.get("quality", "fast")
            if quality not in ("fast", "hi"):
                return self.send_json(400, {"error": "quality must be fast|hi"})
            smooth = body.get("smooth", False)
            if not isinstance(smooth, bool):
                return self.send_json(400, {"error": "smooth must be a boolean"})
            neg_extra = body.get("neg_extra", "")
            if neg_extra is not None and not isinstance(neg_extra, str):
                return self.send_json(400, {"error": "neg_extra must be a string"})
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "status": "queued",
                "created": now(),
                "started": None,
                "finished": None,
                "error": None,
                "video_url": None,
                "deliver": deliver,
                "quality": quality,
                "smooth": smooth,
                "neg_extra": neg_extra or "",
                "start_job": start_job,
                "request": {k: v for k, v in body.items() if k != "image"},
            }
            with LOCK:
                JOBS[job_id] = job
                ORDER.append(job_id)
            size = png_size(image) if image else None
            source = f"start_job={start_job} (last frame of that clip)" if start_job else f"image={mime} {len(image)} bytes" + (f" {size[0]}x{size[1]}" if size else "")
            log(
                f"job {job_id}: created {source}"
                + f" sec={body.get('sec')} res={body.get('res')} seed={body.get('seed')} lora={loras}"
                + f" quality={quality} smooth={smooth} neg_extra={neg_extra!r}"
                + f" deliver={deliver} chat={body.get('chat')!r} message_id={body.get('message_id')}"
            )
            log(f"job {job_id}: prompt: {prompt}")
            threading.Thread(target=render_worker, args=(job_id,), daemon=True).start()
            return self.send_json(200, {"id": job_id})

        return self.send_json(404, {"error": f"no route for POST {path}"})


def main():
    global ARGS, VIDEO_BYTES
    parser = argparse.ArgumentParser(description="Mock comfy-bridge for the 🎬 Видео extension")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--key", default="test-key", help="Bearer key; empty string disables auth")
    parser.add_argument("--prefix", default="", help="URL prefix, e.g. /comfy-bridge")
    parser.add_argument("--queue-seconds", type=float, default=2.0)
    parser.add_argument("--render-seconds", type=float, default=8.0)
    parser.add_argument("--video", help="mp4 file to return instead of the embedded one")
    parser.add_argument("--fail", action="store_true", help="every job ends with status=error")
    parser.add_argument("--verbose", action="store_true")
    ARGS = parser.parse_args()

    if ARGS.video:
        with open(ARGS.video, "rb") as handle:
            VIDEO_BYTES = handle.read()
    else:
        VIDEO_BYTES = base64.b64decode(TINY_MP4_B64)

    server = ThreadingHTTPServer((ARGS.host, ARGS.port), Handler)
    log(f"listening on http://{ARGS.host}:{ARGS.port}{ARGS.prefix}  key={'(none)' if not ARGS.key else ARGS.key}  "
        f"queue={ARGS.queue_seconds}s render={ARGS.render_seconds}s video={len(VIDEO_BYTES)} bytes")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
