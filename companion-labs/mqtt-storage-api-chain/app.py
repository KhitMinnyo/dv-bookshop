#!/usr/bin/env python3
"""Local MQTT-to-storage-to-API security research fixture."""

from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

import paho.mqtt.client as mqtt
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, jsonify, request, send_from_directory

from storage_client import create_storage_client

HOST = "0.0.0.0"
PORT = 5000
MAX_TELEMETRY_BYTES = 4096
STORAGE_URL = "http://127.0.0.1:9900/warehouse-assets"
STORAGE_BUCKET = "warehouse-assets"

FLEET: dict[str, dict[str, Any]] = {
    "tenant-a": {
        "name": "Northstar Books Distribution",
        "region": "us-test-1",
        "gateway": "192.0.2.10",
        "devices": [
            {"id": "warehouse-01", "type": "temperature-gateway", "address": "192.0.2.41", "status_topic": "warehouse/01/status"},
            {"id": "warehouse-02", "type": "cold-storage-sensor", "address": "192.0.2.42", "status_topic": "warehouse/02/status"},
        ],
        "config": {
            "firmware_url": f"{STORAGE_URL}/firmware/warehouse-v2.bin",
            "certificate_record": f"{STORAGE_URL}/certificates/device-01.certificate.txt",
            "device_config": f"{STORAGE_URL}/device-config/warehouse-01.json",
            "storage_listing_url": f"{STORAGE_URL}?list-type=2",
            "network": "192.0.2.0/24",
            "synthetic": True,
        },
    },
    "tenant-b": {
        "name": "Bluebird Learning Logistics",
        "region": "eu-test-2",
        "gateway": "198.51.100.10",
        "devices": [
            {"id": "inventory-01", "type": "inventory-reader", "address": "198.51.100.41", "status_topic": "inventory/01/status"},
            {"id": "inventory-02", "type": "loading-bay-counter", "address": "198.51.100.42", "status_topic": "inventory/02/status"},
        ],
        "config": {
            "firmware_url": f"{STORAGE_URL}/firmware/warehouse-v2.bin",
            "certificate_record": f"{STORAGE_URL}/certificates/device-01.certificate.txt",
            "device_config": f"{STORAGE_URL}/device-config/warehouse-01.json",
            "storage_listing_url": f"{STORAGE_URL}?list-type=2",
            "network": "198.51.100.0/24",
            "synthetic": True,
        },
    },
}

API_IDENTITIES = {
    "tenant-a-demo-token": {"username": "alice", "tenant": "tenant-a", "role": "reader"},
    "tenant-b-demo-token": {"username": "bob", "tenant": "tenant-b", "role": "reader"},
}

INITIAL_TELEMETRY = {
    "warehouse/01/temperature": {"temperature_c": 24.5, "unit": "C"},
    "warehouse/01/status": {"status": "NORMAL", "device_id": "warehouse-01"},
    "warehouse/01/config": {
        "firmware_url": f"{STORAGE_URL}/firmware/warehouse-v2.bin",
        "storage_listing_url": f"{STORAGE_URL}?list-type=2",
    },
    "warehouse/02/temperature": {"temperature_c": 5.2, "unit": "C"},
    "warehouse/02/status": {"status": "NORMAL", "device_id": "warehouse-02"},
    "inventory/01/status": {"status": "ONLINE", "items_seen": 184},
}

app = Flask(__name__, static_folder="static", static_url_path="/static")
LAB_MODE = os.environ.get("LAB_MODE", "vulnerable")
telemetry: dict[str, Any] = dict(INITIAL_TELEMETRY)
telemetry_lock = threading.Lock()
mqtt_connected = threading.Event()
mqtt_client: Optional[mqtt.Client] = None


def on_connect(client, _userdata, _flags, reason_code, _properties):
    if reason_code.value == 0:
        mqtt_connected.set()
        client.subscribe([("warehouse/#", 0), ("inventory/#", 0)])
        for topic, value in INITIAL_TELEMETRY.items():
            client.publish(topic, json.dumps(value), qos=1, retain=True)


def on_message(_client, _userdata, message):
    if len(message.payload) > MAX_TELEMETRY_BYTES:
        return
    try:
        value = json.loads(message.payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        value = message.payload.decode("utf-8", errors="replace")[:MAX_TELEMETRY_BYTES]
    with telemetry_lock:
        telemetry[message.topic] = value


def start_mqtt_ingestor() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dv-bookshop-lab-ingestor")
    client.username_pw_set(
        os.environ.get("MQTT_USERNAME", "ingestor"),
        os.environ.get("MQTT_PASSWORD", "ingestor-lab-only"),
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(os.environ.get("MQTT_HOST", "127.0.0.1"), int(os.environ.get("MQTT_PORT", "18883")), 30)
    client.loop_start()
    return client


def initialize_storage() -> None:
    client = create_storage_client("http://storage:9000")
    for attempt in range(30):
        try:
            client.list_buckets()
            break
        except BotoCoreError:
            if attempt == 29:
                raise
            time.sleep(1)

    try:
        client.head_bucket(Bucket=STORAGE_BUCKET)
    except ClientError as error:
        if error.response["Error"].get("Code") not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        client.create_bucket(Bucket=STORAGE_BUCKET)

    seed_root = Path(__file__).parent / "seed"
    for path in seed_root.rglob("*"):
        if path.is_file():
            object_key = path.relative_to(seed_root).as_posix()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            client.put_object(
                Bucket=STORAGE_BUCKET,
                Key=object_key,
                Body=path.read_bytes(),
                ContentType=content_type,
            )

    if LAB_MODE == "hardened":
        try:
            client.delete_bucket_policy(Bucket=STORAGE_BUCKET)
        except ClientError as error:
            if error.response["Error"].get("Code") not in {"404", "NoSuchBucketPolicy", "NoSuchBucket"}:
                raise
    else:
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "TrainingPublicListing",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:ListBucket",
                    "Resource": f"arn:aws:s3:::{STORAGE_BUCKET}",
                },
                {
                    "Sid": "TrainingPublicObjectRead",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{STORAGE_BUCKET}/*",
                },
            ],
        }
        client.put_bucket_policy(Bucket=STORAGE_BUCKET, Policy=json.dumps(policy))


def api_identity() -> Optional[dict[str, str]]:
    scheme, separator, token = request.headers.get("Authorization", "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None
    if LAB_MODE != "hardened":
        return {"username": "alice", "tenant": "tenant-a", "role": "reader"}
    return API_IDENTITIES.get(token.strip())


def tenant_for_request(identity: dict[str, str]):
    requested_tenant = request.args.get("tenant") or request.headers.get("X-Tenant-ID") or identity["tenant"]
    if requested_tenant not in FLEET:
        return None, (jsonify({"error": "tenant not found"}), 404)
    if LAB_MODE == "hardened" and requested_tenant != identity["tenant"]:
        return None, (jsonify({"error": "tenant access denied"}), 403)
    return requested_tenant, None


def tenant_endpoint(section: str):
    identity = api_identity()
    if identity is None:
        return jsonify({"error": "authentication required"}), 401
    tenant_id, error = tenant_for_request(identity)
    if error is not None:
        return error
    tenant = FLEET[tenant_id]
    if section == "details":
        return jsonify({"tenant": tenant_id, "organization": tenant["name"], "region": tenant["region"], "gateway": tenant["gateway"], "network": tenant["config"]["network"], "synthetic": True})
    if section == "devices":
        return jsonify({"tenant": tenant_id, "devices": tenant["devices"], "count": len(tenant["devices"])})
    return jsonify({"tenant": tenant_id, "config": tenant["config"]})


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "mode": LAB_MODE, "mqtt_connected": mqtt_connected.is_set()})


@app.get("/api/telemetry")
def get_telemetry():
    identity = None
    if LAB_MODE == "hardened":
        identity = api_identity()
        if identity is None:
            return jsonify({"error": "authentication required"}), 401

    with telemetry_lock:
        current = dict(telemetry)
    if identity is not None:
        topic_prefix = "warehouse/" if identity["tenant"] == "tenant-a" else "inventory/"
        current = {topic: value for topic, value in current.items() if topic.startswith(topic_prefix)}
    return jsonify({"messages": current, "mqtt_connected": mqtt_connected.is_set()})


@app.get("/api/devices")
def devices():
    return tenant_endpoint("devices")


@app.get("/api/config")
def config():
    return tenant_endpoint("config")


@app.get("/api/warehouse/details")
def warehouse_details():
    return tenant_endpoint("details")


def main():
    global mqtt_client
    initialize_storage()
    mqtt_client = start_mqtt_ingestor()
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
