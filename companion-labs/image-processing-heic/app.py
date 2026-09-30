#!/usr/bin/env python3
"""Local book-cover image-processing security research fixture."""

from __future__ import annotations

import io
import os
import uuid
import warnings
from pathlib import Path
from typing import Optional, Union

import PIL
from flask import Flask, jsonify, render_template_string, request, send_file
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pillow_heif import __version__ as pillow_heif_version
from pillow_heif import register_heif_opener

HOST = "0.0.0.0"
PORT = 5000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
THUMBNAIL_SIZE = (320, 320)
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC"}
LAB_DIAGNOSTIC_MARKER = "LAB:PROCESSOR-DIAGNOSTIC"

register_heif_opener()
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DV Bookshop | Cover Studio</title>
  <style>
    :root { color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; background: #10151b; color: #e8edf2; }
    body { max-width: 900px; margin: 3rem auto; padding: 0 1.2rem; }
    h1 { letter-spacing: -.04em; } p, small { color: #aab6c2; }
    form, article { border: 1px solid #35424d; border-radius: 12px; padding: 1.2rem; background: #171f27; }
    input, button { padding: .7rem; margin: .3rem 0; }
    button { cursor: pointer; background: #d8a34a; border: 0; border-radius: 6px; font-weight: 700; }
    #covers { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 1.5rem; }
    img { width: 100%; max-height: 240px; object-fit: contain; background: #0c1014; }
    code { overflow-wrap: anywhere; }
  </style>
</head>
<body>
  <h1>Bookshop Cover Studio</h1>
  <p>Upload a cover image. The local service decodes it, normalizes its orientation,
  converts it to JPEG, and builds a thumbnail before storing the result.</p>
  <form id="upload-form">
    <label for="cover">Book cover (JPEG, PNG, WebP, HEIC, or HEIF)</label><br>
    <input id="cover" name="cover" type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" required>
    <button type="submit">Process cover</button>
  </form>
  <p><a href="/sample/cover.heic">Download a generated HEIC sample</a> |
     <a href="/sample/cover-diagnostic.heic">Download a metadata-rich HEIC sample</a></p>
  <pre id="result" role="status"></pre>
  <section id="covers" aria-live="polite"></section>
  <script>
    const form = document.querySelector('#upload-form');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const response = await fetch('/api/covers', { method: 'POST', body: new FormData(form) });
      document.querySelector('#result').textContent = JSON.stringify(await response.json(), null, 2);
      if (response.ok) await loadCovers();
    });
    async function loadCovers() {
      const response = await fetch('/api/covers');
      const covers = await response.json();
      document.querySelector('#covers').replaceChildren(...covers.map((cover) => {
        const card = document.createElement('article');
        const image = document.createElement('img');
        image.src = cover.thumbnail_url;
        image.alt = 'Processed book cover';
        const details = document.createElement('small');
        details.textContent = `${cover.source_format} ${cover.source_size[0]}x${cover.source_size[1]} -> ${cover.output_size[0]}x${cover.output_size[1]} JPEG`;
        card.append(image, details);
        return card;
      }));
    }
    loadCovers();
  </script>
</body>
</html>"""


def make_sample_heic(diagnostic: bool = False) -> bytes:
    image = Image.new("RGB", (720, 960), "#29414d")
    draw = ImageDraw.Draw(image)
    draw.rectangle((34, 34, 686, 926), outline="#e4bb70", width=8)
    draw.text((75, 380), "DV BOOKSHOP", fill="#f7f0df", stroke_width=1)
    draw.text((75, 430), "HEIF cover sample", fill="#f7f0df")
    exif = image.getexif()
    if diagnostic:
        exif[270] = LAB_DIAGNOSTIC_MARKER
    output = io.BytesIO()
    image.save(output, format="HEIF", quality=85, exif=exif.tobytes())
    return output.getvalue()


def create_app(mode: Optional[str] = None, runtime_dir: Optional[Union[str, Path]] = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["LAB_MODE"] = mode or os.environ.get("LAB_MODE", "vulnerable")
    app.config["RUNTIME_DIR"] = Path(
        runtime_dir or os.environ.get("LAB_RUNTIME_DIR", Path(__file__).parent / "runtime")
    )
    app.config["RUNTIME_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["COVERS"] = []

    @app.get("/")
    def index():
        return render_template_string(PAGE)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "mode": app.config["LAB_MODE"]})

    @app.get("/api/processor")
    def processor_info():
        return jsonify(
            {
                "pipeline": ["Pillow", "pillow-heif", "ImageOps.exif_transpose", "JPEG thumbnail"],
                "pillow_version": PIL.__version__,
                "pillow_heif_version": pillow_heif_version,
                "maximum_upload_bytes": MAX_UPLOAD_BYTES,
                "maximum_image_pixels": MAX_IMAGE_PIXELS,
            }
        )

    @app.get("/sample/<sample_name>")
    def sample(sample_name: str):
        if sample_name not in {"cover.heic", "cover-diagnostic.heic"}:
            return jsonify({"error": "sample not found"}), 404
        output = io.BytesIO()
        output.write(make_sample_heic(diagnostic=sample_name == "cover-diagnostic.heic"))
        output.seek(0)
        return send_file(output, mimetype="image/heic", download_name=sample_name)

    @app.get("/api/covers")
    def list_covers():
        return jsonify(app.config["COVERS"])

    @app.get("/api/covers/<cover_id>/thumbnail.jpg")
    def thumbnail(cover_id: str):
        if not cover_id.isalnum():
            return jsonify({"error": "cover not found"}), 404
        path = app.config["RUNTIME_DIR"] / f"{cover_id}.jpg"
        if not path.is_file():
            return jsonify({"error": "cover not found"}), 404
        return send_file(path, mimetype="image/jpeg", max_age=0)

    @app.post("/api/covers")
    def upload_cover():
        uploaded = request.files.get("cover")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "select a cover image"}), 400

        payload = uploaded.stream.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            return jsonify({"error": "image exceeds the 5 MiB upload limit"}), 413

        try:
            with Image.open(io.BytesIO(payload)) as source:
                source_format = (source.format or "").upper()
                if source_format not in SUPPORTED_FORMATS:
                    return jsonify({"error": "unsupported image format"}), 415
                source_size = source.size
                if source.width < 1 or source.height < 1 or source.width * source.height > MAX_IMAGE_PIXELS:
                    return jsonify({"error": "image dimensions exceed the lab limit"}), 413
                description = str(source.getexif().get(270, ""))[:256]
                decoded = ImageOps.exif_transpose(source).convert("RGB")
                decoded.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return jsonify({"error": "image could not be decoded"}), 400

        cover_id = uuid.uuid4().hex
        full_path = app.config["RUNTIME_DIR"] / f"{cover_id}.jpg"
        thumbnail = decoded.copy()
        thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        thumbnail.save(full_path, format="JPEG", quality=88, optimize=True)

        record = {
            "id": cover_id,
            "source_format": source_format,
            "source_size": list(source_size),
            "output_size": list(thumbnail.size),
            "thumbnail_url": f"/api/covers/{cover_id}/thumbnail.jpg",
            "processing": "decoded, orientation-normalized, resized, and converted to JPEG",
        }
        response = {"cover": record}

        # This models a bounded diagnostic-disclosure bug; no native exploit or host action runs.
        if app.config["LAB_MODE"] != "hardened" and description == LAB_DIAGNOSTIC_MARKER:
            response["processor_diagnostic"] = {
                "cache_namespace": "lab://book-cover/decoder-cache",
                "worker_label": "synthetic-image-worker-01",
                "decoder_profile": "training-only HEIF profile",
            }
        elif app.config["LAB_MODE"] == "hardened" and description == LAB_DIAGNOSTIC_MARKER:
            response["diagnostic_suppressed"] = True

        app.config["COVERS"].insert(0, record)
        return jsonify(response), 201

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
