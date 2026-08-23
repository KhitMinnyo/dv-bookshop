"use strict";

const output = document.querySelector("#output");

function show(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function fromBase64Url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function toBase64Url(value) {
  const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : value;
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function jsonRequest(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Local server rejected the request");
  return data;
}

function serializeCreation(credential) {
  return {
    id: credential.id,
    rawId: toBase64Url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: toBase64Url(credential.response.clientDataJSON),
      attestationObject: toBase64Url(credential.response.attestationObject)
    }
  };
}

function serializeAssertion(credential) {
  return {
    id: credential.id,
    rawId: toBase64Url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: toBase64Url(credential.response.clientDataJSON),
      authenticatorData: toBase64Url(credential.response.authenticatorData),
      signature: toBase64Url(credential.response.signature),
      userHandle: credential.response.userHandle ? toBase64Url(credential.response.userHandle) : null
    }
  };
}

document.querySelector("#register").addEventListener("click", async () => {
  try {
    if (!window.PublicKeyCredential) throw new Error("This browser does not expose WebAuthn");
    const options = await jsonRequest("/options/register");
    options.publicKey.challenge = fromBase64Url(options.publicKey.challenge);
    options.publicKey.user.id = fromBase64Url(options.publicKey.user.id);
    const credential = await navigator.credentials.create(options);
    const result = await jsonRequest("/verify/register", serializeCreation(credential));
    show(result);
  } catch (error) {
    show(`Registration failed: ${error.message}`);
  }
});

document.querySelector("#authenticate").addEventListener("click", async () => {
  try {
    if (!window.PublicKeyCredential) throw new Error("This browser does not expose WebAuthn");
    const options = await jsonRequest("/options/authenticate");
    options.publicKey.challenge = fromBase64Url(options.publicKey.challenge);
    const credential = await navigator.credentials.get(options);
    const result = await jsonRequest("/verify/authenticate", serializeAssertion(credential));
    show(result);
  } catch (error) {
    show(`Authentication failed: ${error.message}`);
  }
});
