#!/usr/bin/env python3
"""Local path-style S3 fixture gateway for public listing/read policy exercises."""

import os
import xml.etree.ElementTree as ET

from flask import Flask, Response, jsonify

from storage_client import create_storage_client

BUCKET = "warehouse-assets"
LAB_MODE = os.environ.get("LAB_MODE", "vulnerable")
s3 = create_storage_client("http://storage:9000")
app = Flask(__name__)


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "mode": LAB_MODE})


@app.get("/<bucket>")
def list_objects(bucket: str):
    if bucket != BUCKET:
        return jsonify({"error": "bucket not found"}), 404
    if LAB_MODE == "hardened":
        return Response(status=403)

    result = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=1000)
    root = ET.Element("ListBucketResult", xmlns="http://s3.amazonaws.com/doc/2006-03-01/")
    ET.SubElement(root, "Name").text = BUCKET
    ET.SubElement(root, "Prefix").text = ""
    ET.SubElement(root, "MaxKeys").text = "1000"
    ET.SubElement(root, "KeyCount").text = str(result.get("KeyCount", 0))
    ET.SubElement(root, "IsTruncated").text = str(result.get("IsTruncated", False)).lower()
    for item in result.get("Contents", []):
        contents = ET.SubElement(root, "Contents")
        ET.SubElement(contents, "Key").text = item["Key"]
        ET.SubElement(contents, "LastModified").text = item["LastModified"].isoformat()
        ET.SubElement(contents, "ETag").text = item["ETag"]
        ET.SubElement(contents, "Size").text = str(item["Size"])
        ET.SubElement(contents, "StorageClass").text = "STANDARD"
    return Response(ET.tostring(root, encoding="utf-8", xml_declaration=True), mimetype="application/xml")


@app.get("/<bucket>/<path:object_key>")
def get_object(bucket: str, object_key: str):
    if bucket != BUCKET:
        return jsonify({"error": "bucket not found"}), 404
    if LAB_MODE == "hardened":
        return Response(status=403)
    result = s3.get_object(Bucket=BUCKET, Key=object_key)
    return Response(result["Body"].read(), mimetype=result.get("ContentType", "application/octet-stream"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9001, debug=False)
