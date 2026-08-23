#!/usr/bin/env python3
"""Local-only SAML flow fixture with deliberately explicit validation."""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import html
import secrets
import time
import uuid
import xml.etree.ElementTree as ET

from flask import Flask, Response, make_response as flask_response, redirect, request


app = Flask(__name__)
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
NS = {"saml": SAML_NS, "ds": DS_NS}
ISSUER = "https://idp.local.example"
AUDIENCE = "https://sp.local.example"
ACS_URL = "http://127.0.0.1:5355/sp/acs"
SIGNING_KEY = b"saml-companion-lab-only-key"
PENDING: dict[str, str] = {}
SESSIONS: dict[str, dict[str, str]] = {}


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def local_signature(assertion: ET.Element) -> str:
    unsigned = copy.deepcopy(assertion)
    signature = unsigned.find("ds:Signature", NS)
    if signature is not None:
        unsigned.remove(signature)
    canonical_demo_bytes = ET.tostring(unsigned, encoding="utf-8", short_empty_elements=True)
    digest = hmac.new(SIGNING_KEY, canonical_demo_bytes, hashlib.sha256).digest()
    return b64(digest)


def make_saml_response(request_id: str) -> str:
    now = int(time.time())
    assertion_id = "_" + uuid.uuid4().hex
    assertion = ET.Element(
        f"{{{SAML_NS}}}Assertion",
        {"ID": assertion_id, "Version": "2.0", "IssueInstant": str(now)},
    )
    ET.SubElement(assertion, f"{{{SAML_NS}}}Issuer").text = ISSUER
    subject = ET.SubElement(assertion, f"{{{SAML_NS}}}Subject")
    ET.SubElement(subject, f"{{{SAML_NS}}}NameID", {"Format": "persistent"}).text = "local-user-001"
    confirmation = ET.SubElement(subject, f"{{{SAML_NS}}}SubjectConfirmation", {"Method": "bearer"})
    ET.SubElement(
        confirmation,
        f"{{{SAML_NS}}}SubjectConfirmationData",
        {"InResponseTo": request_id, "Recipient": ACS_URL, "NotOnOrAfter": str(now + 120)},
    )
    conditions = ET.SubElement(assertion, f"{{{SAML_NS}}}Conditions", {"NotBefore": str(now - 5), "NotOnOrAfter": str(now + 120)})
    restriction = ET.SubElement(conditions, f"{{{SAML_NS}}}AudienceRestriction")
    ET.SubElement(restriction, f"{{{SAML_NS}}}Audience").text = AUDIENCE
    attributes = ET.SubElement(assertion, f"{{{SAML_NS}}}AttributeStatement")
    attribute = ET.SubElement(attributes, f"{{{SAML_NS}}}Attribute", {"Name": "email"})
    ET.SubElement(attribute, f"{{{SAML_NS}}}AttributeValue").text = "user@local.example"

    signature = ET.SubElement(assertion, f"{{{DS_NS}}}Signature")
    signed_info = ET.SubElement(signature, f"{{{DS_NS}}}SignedInfo")
    ET.SubElement(signed_info, f"{{{DS_NS}}}Reference", {"URI": f"#{assertion_id}"})
    ET.SubElement(signature, f"{{{DS_NS}}}SignatureValue").text = local_signature(assertion)

    response = ET.Element(
        f"{{urn:oasis:names:tc:SAML:2.0:protocol}}Response",
        {"InResponseTo": request_id, "Destination": ACS_URL, "IssueInstant": str(now)},
    )
    ET.SubElement(response, f"{{{SAML_NS}}}Issuer").text = ISSUER
    response.append(assertion)
    return b64(ET.tostring(response, encoding="utf-8"))


def parse_time(value: str) -> int:
    return int(value)


def validate_response(encoded: str, expected_request_id: str) -> dict[str, str]:
    try:
        root = ET.fromstring(base64.b64decode(encoded, validate=True))
    except (ValueError, ET.ParseError) as error:
        raise ValueError("SAML response is not valid base64 XML") from error
    if root.tag != "{urn:oasis:names:tc:SAML:2.0:protocol}Response":
        raise ValueError("unexpected SAML response element")
    if root.attrib.get("Destination") != ACS_URL:
        raise ValueError("destination mismatch")
    if root.attrib.get("InResponseTo") != expected_request_id:
        raise ValueError("request correlation mismatch")
    response_issuer = root.find("saml:Issuer", NS)
    if response_issuer is None or response_issuer.text != ISSUER:
        raise ValueError("issuer mismatch")

    assertions = [child for child in list(root) if child.tag == f"{{{SAML_NS}}}Assertion"]
    if len(assertions) != 1:
        raise ValueError("expected exactly one direct assertion")
    assertion = assertions[0]
    assertion_issuer = assertion.find("saml:Issuer", NS)
    if assertion_issuer is None or assertion_issuer.text != ISSUER:
        raise ValueError("assertion issuer mismatch")
    assertion_id = assertion.attrib.get("ID", "")
    signature = assertion.find("ds:Signature", NS)
    reference = assertion.find("ds:Signature/ds:SignedInfo/ds:Reference", NS)
    signature_value = assertion.findtext("ds:Signature/ds:SignatureValue", default="", namespaces=NS)
    if not assertion_id or signature is None or reference is None or reference.attrib.get("URI") != f"#{assertion_id}":
        raise ValueError("signature does not identify the selected assertion")
    if not hmac.compare_digest(signature_value, local_signature(assertion)):
        raise ValueError("signature mismatch")

    now = int(time.time())
    conditions = assertion.find("saml:Conditions", NS)
    if conditions is None:
        raise ValueError("conditions are missing")
    if now < parse_time(conditions.attrib["NotBefore"]) - 5 or now >= parse_time(conditions.attrib["NotOnOrAfter"]):
        raise ValueError("assertion conditions are not valid")
    audience = conditions.find("saml:AudienceRestriction/saml:Audience", NS)
    if audience is None or audience.text != AUDIENCE:
        raise ValueError("audience mismatch")
    name_id = assertion.find("saml:Subject/saml:NameID", NS)
    confirmation = assertion.find("saml:Subject/saml:SubjectConfirmation/saml:SubjectConfirmationData", NS)
    if name_id is None or not name_id.text or confirmation is None:
        raise ValueError("subject is incomplete")
    if confirmation.attrib.get("Recipient") != ACS_URL or confirmation.attrib.get("InResponseTo") != expected_request_id:
        raise ValueError("subject recipient or correlation mismatch")
    if now >= parse_time(confirmation.attrib["NotOnOrAfter"]):
        raise ValueError("subject confirmation is expired")
    return {"issuer": ISSUER, "name_id": name_id.text}


def form(action: str, fields: dict[str, str], message: str) -> str:
    inputs = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}">'
        for key, value in fields.items()
    )
    return f"<!doctype html><title>Local SAML step</title><p>{html.escape(message)}</p><form method=post action=\"{html.escape(action)}\">{inputs}<button>Continue</button></form>"


@app.get("/")
def index() -> str:
    return '<!doctype html><title>Local SAML Lab</title><h1>Local SAML Lab</h1><p><a href="/sp/login?relaystate=/sp/profile">Start local SSO</a></p>'


@app.get("/sp/login")
def sp_login() -> str:
    relaystate = request.args.get("relaystate", "/sp/profile")
    if relaystate not in {"/", "/sp/profile"}:
        return "RelayState rejected", 400
    request_id = "_" + secrets.token_hex(12)
    PENDING[request_id] = relaystate
    return form("/idp/issue", {"request_id": request_id, "relaystate": relaystate}, "The mock SP sent a request to the mock IdP.")


@app.post("/idp/issue")
def idp_issue() -> str:
    request_id = request.form.get("request_id", "")
    relaystate = request.form.get("relaystate", "")
    if request_id not in PENDING or PENDING[request_id] != relaystate:
        return "Unknown local request", 400
    return form("/sp/acs", {"SAMLResponse": make_saml_response(request_id), "RelayState": relaystate}, "The mock IdP issued a signed local response.")


@app.post("/sp/acs")
def acs() -> Response:
    relaystate = request.form.get("RelayState", "")
    saml_response = request.form.get("SAMLResponse", "")
    try:
        raw = base64.b64decode(saml_response, validate=True)
        root = ET.fromstring(raw)
        request_id = root.attrib.get("InResponseTo", "")
        if request_id not in PENDING or PENDING[request_id] != relaystate:
            raise ValueError("RelayState or request is not pending")
        identity = validate_response(saml_response, request_id)
        del PENDING[request_id]
    except (ValueError, KeyError, ET.ParseError) as error:
        return flask_response(f"SAML validation failed: {html.escape(str(error))}", 400)
    identity_key = f"{identity['issuer']}|{identity['name_id']}"
    session_id = secrets.token_urlsafe(18)
    SESSIONS[session_id] = {"identity_key": identity_key}
    response = flask_response(redirect(relaystate))
    response.set_cookie("local_session", session_id, httponly=True, samesite="Strict")
    return response


@app.get("/sp/profile")
def profile() -> tuple[str, int] | str:
    session_id = request.cookies.get("local_session", "")
    identity = SESSIONS.get(session_id)
    if identity is None:
        return redirect("/sp/login?relaystate=/sp/profile")
    return f"<!doctype html><title>Local profile</title><h1>Authenticated local profile</h1><p>Identity key: {html.escape(identity['identity_key'])}</p>"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5355, debug=False)
