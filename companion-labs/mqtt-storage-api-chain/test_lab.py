import datetime
import io
import unittest
from unittest.mock import patch

import app as lab
import storage_gateway


class MqttStorageApiChainTests(unittest.TestCase):
    def setUp(self):
        self.previous_mode = lab.LAB_MODE
        self.previous_storage_mode = storage_gateway.LAB_MODE
        lab.app.config["TESTING"] = True
        self.client = lab.app.test_client()
        self.storage_client = storage_gateway.app.test_client()

    def tearDown(self):
        lab.LAB_MODE = self.previous_mode
        storage_gateway.LAB_MODE = self.previous_storage_mode

    def test_telemetry_exposes_seeded_storage_urls(self):
        response = self.client.get("/api/telemetry")
        self.assertEqual(response.status_code, 200)
        config = response.get_json()["messages"]["warehouse/01/config"]
        self.assertTrue(config["firmware_url"].startswith("http://127.0.0.1:9900/"))

    def test_dashboard_bundle_contains_only_training_credentials(self):
        response = self.client.get("/static/dashboard.js")
        self.assertEqual(response.status_code, 200)
        bundle = response.data
        response.close()
        self.assertIn(b"dashboard-lab-only", bundle)
        self.assertIn(b"tenant-a-demo-token", bundle)

    def test_vulnerable_api_accepts_arbitrary_bearer_and_tenant_context(self):
        lab.LAB_MODE = "vulnerable"
        response = self.client.get(
            "/api/devices?tenant=tenant-b",
            headers={"Authorization": "Bearer made-up-local-token", "X-Tenant-ID": "tenant-b"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tenant"], "tenant-b")

    def test_hardened_api_binds_identity_to_its_tenant(self):
        lab.LAB_MODE = "hardened"
        headers = {"Authorization": "Bearer tenant-a-demo-token", "X-Tenant-ID": "tenant-b"}
        self.assertEqual(self.client.get("/api/devices", headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/api/devices?tenant=tenant-b", headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/api/devices", headers={"Authorization": "Bearer made-up"}).status_code, 401)

    def test_storage_gateway_changes_public_access_by_mode(self):
        storage_gateway.LAB_MODE = "vulnerable"
        listing = {
            "KeyCount": 1,
            "IsTruncated": False,
            "Contents": [{"Key": "firmware/warehouse-v2.bin", "LastModified": datetime.datetime(2026, 1, 1), "ETag": '"fixture"', "Size": 10}],
        }
        with patch.object(storage_gateway.s3, "list_objects_v2", return_value=listing):
            response = self.storage_client.get("/warehouse-assets?list-type=2")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"firmware/warehouse-v2.bin", response.data)
        with patch.object(storage_gateway.s3, "get_object", return_value={"Body": io.BytesIO(b"synthetic"), "ContentType": "text/plain"}):
            object_response = self.storage_client.get("/warehouse-assets/firmware/warehouse-v2.bin")
        self.assertEqual(object_response.status_code, 200)
        self.assertEqual(object_response.data, b"synthetic")

        storage_gateway.LAB_MODE = "hardened"
        self.assertEqual(self.storage_client.get("/warehouse-assets?list-type=2").status_code, 403)
        self.assertEqual(self.storage_client.get("/warehouse-assets/firmware/warehouse-v2.bin").status_code, 403)


if __name__ == "__main__":
    unittest.main()
