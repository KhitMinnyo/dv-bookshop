import io
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app import LAB_DIAGNOSTIC_MARKER, create_app, make_sample_heic


class ImageProcessingLabTests(unittest.TestCase):
    def setUp(self):
        self.runtime = tempfile.TemporaryDirectory(dir=os.environ.get("LAB_RUNTIME_DIR"))
        self.addCleanup(self.runtime.cleanup)
        self.client = create_app(mode="vulnerable", runtime_dir=self.runtime.name).test_client()

    def test_heic_is_decoded_resized_and_converted(self):
        response = self.client.post(
            "/api/covers",
            data={"cover": (io.BytesIO(make_sample_heic()), "book-cover.heic")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        result = response.get_json()["cover"]
        self.assertIn(result["source_format"], {"HEIF", "HEIC"})
        self.assertIn("converted to JPEG", result["processing"])
        thumbnail = self.client.get(result["thumbnail_url"])
        self.assertEqual(thumbnail.status_code, 200)
        self.assertEqual(thumbnail.mimetype, "image/jpeg")
        image_data = thumbnail.data
        thumbnail.close()
        with Image.open(io.BytesIO(image_data)) as processed:
            self.assertLessEqual(max(processed.size), 320)

    def test_normal_png_upload_is_converted(self):
        source = Image.new("RGB", (640, 400), "#29414d")
        payload = io.BytesIO()
        source.save(payload, format="PNG")
        response = self.client.post(
            "/api/covers",
            data={"cover": (io.BytesIO(payload.getvalue()), "book-cover.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        result = response.get_json()["cover"]
        self.assertEqual(result["source_format"], "PNG")
        self.assertIn("converted to JPEG", result["processing"])

    def test_diagnostic_impact_is_contained_and_mode_gated(self):
        payload = make_sample_heic(diagnostic=True)
        vulnerable = self.client.post(
            "/api/covers",
            data={"cover": (io.BytesIO(payload), "metadata.heic")},
            content_type="multipart/form-data",
        )
        self.assertEqual(vulnerable.status_code, 201)
        diagnostic = vulnerable.get_json()["processor_diagnostic"]
        self.assertEqual(diagnostic["cache_namespace"], "lab://book-cover/decoder-cache")

        secure = create_app(mode="hardened", runtime_dir=Path(self.runtime.name) / "secure").test_client()
        patched = secure.post(
            "/api/covers",
            data={"cover": (io.BytesIO(payload), "metadata.heic")},
            content_type="multipart/form-data",
        )
        self.assertEqual(patched.status_code, 201)
        self.assertTrue(patched.get_json()["diagnostic_suppressed"])
        self.assertNotIn("processor_diagnostic", patched.get_json())

    def test_non_image_is_rejected(self):
        response = self.client.post(
            "/api/covers",
            data={"cover": (io.BytesIO(b"not an image"), "notes.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
