#!/usr/bin/env node
"use strict";

const express = require("express");

const HOST = "127.0.0.1";
const PORT = 3003;
const BLOCKED_KEYS = new Set(["__proto__", "prototype", "constructor"]);

function parseMode() {
  const index = process.argv.indexOf("--mode");
  const mode = index >= 0 ? process.argv[index + 1] : "safe";
  if (mode !== "safe" && mode !== "vulnerable") {
    throw new Error("mode must be safe or vulnerable");
  }
  return mode;
}

// Intentionally unsafe: inherited __proto__ and constructor properties are reachable.
function vulnerableDeepMerge(target, source) {
  for (const key of Object.keys(source)) {
    const value = source[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      if (!target[key]) target[key] = {};
      vulnerableDeepMerge(target[key], value);
    } else {
      target[key] = value;
    }
  }
  return target;
}

function safeDeepMerge(target, source) {
  for (const key of Object.keys(source)) {
    if (BLOCKED_KEYS.has(key)) continue;
    const value = source[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const child = Object.create(null);
      target[key] = safeDeepMerge(child, value);
    } else {
      target[key] = value;
    }
  }
  return target;
}

function normalizePath(path) {
  if (Array.isArray(path)) return path;
  if (typeof path === "string") return path.split(".").filter(Boolean);
  return [];
}

// Intentionally unsafe: a path such as constructor.prototype.flag reaches a shared prototype.
function vulnerableSet(target, path, value) {
  const segments = normalizePath(path);
  if (segments.length === 0) throw new Error("path is required");
  let cursor = target;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    if (!cursor[segment]) cursor[segment] = {};
    cursor = cursor[segment];
  }
  cursor[segments[segments.length - 1]] = value;
  return target;
}

function safeSet(target, path, value) {
  const segments = normalizePath(path);
  if (segments.length === 0 || segments.some((segment) => BLOCKED_KEYS.has(segment))) {
    throw new Error("path is empty or contains a protected key");
  }
  let cursor = target;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    if (!Object.hasOwn(cursor, segment) || typeof cursor[segment] !== "object") {
      cursor[segment] = Object.create(null);
    }
    cursor = cursor[segment];
  }
  cursor[segments[segments.length - 1]] = value;
  return target;
}

function pollutionStatus() {
  const probe = {};
  return {
    objectPrototypeHasPolluted: Object.hasOwn(Object.prototype, "polluted"),
    freshObjectPolluted: probe.polluted === true,
    objectPrototypeHasRole: Object.hasOwn(Object.prototype, "role"),
    freshObjectRole: probe.role || null,
  };
}

function requireObject(value, name) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${name} must be a JSON object`);
  }
  return value;
}

function createApp(mode) {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/", (req, res) => {
    res.json({ lab: "prototype-pollution", mode, localOnly: true, status: pollutionStatus() });
  });

  app.post("/vulnerable/merge", (req, res) => {
    if (mode !== "vulnerable") {
      return res.status(404).json({ error: "vulnerable endpoints are disabled in safe mode" });
    }
    try {
      const body = requireObject(req.body, "body");
      const result = vulnerableDeepMerge({}, requireObject(body.source, "source"));
      res.json({ result, status: pollutionStatus() });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post("/safe/merge", (req, res) => {
    if (mode !== "safe") {
      return res.status(404).json({ error: "safe endpoints are disabled in vulnerable mode" });
    }
    try {
      if (JSON.stringify(req.body).length > 16 * 1024) {
        return res.status(413).json({ error: "safe payload limit exceeded" });
      }
      const body = requireObject(req.body, "body");
      const result = safeDeepMerge(Object.create(null), requireObject(body.source, "source"));
      return res.json({ result, status: pollutionStatus() });
    } catch (error) {
      return res.status(400).json({ error: error.message });
    }
  });

  app.post("/vulnerable/set", (req, res) => {
    if (mode !== "vulnerable") {
      return res.status(404).json({ error: "vulnerable endpoints are disabled in safe mode" });
    }
    try {
      const body = requireObject(req.body, "body");
      const result = vulnerableSet({}, body.path, body.value);
      res.json({ result, status: pollutionStatus() });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post("/safe/set", (req, res) => {
    if (mode !== "safe") {
      return res.status(404).json({ error: "safe endpoints are disabled in vulnerable mode" });
    }
    try {
      const body = requireObject(req.body, "body");
      const result = safeSet(Object.create(null), body.path, body.value);
      res.json({ result, status: pollutionStatus() });
    } catch (error) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post("/reset", (req, res) => {
    delete Object.prototype.polluted;
    delete Object.prototype.role;
    res.json({ reset: true, status: pollutionStatus() });
  });

  return app;
}

const mode = parseMode();
createApp(mode).listen(PORT, HOST, () => {
  console.log(`Prototype pollution lab (${mode}) listening on http://${HOST}:${PORT}`);
});
