# Prototype Pollution Lab

This is a local-only Node.js and Express fixture. It listens on `127.0.0.1:3003` and never contacts DV-Bookshop or another production target. Use it only for learning on your own machine.

## Definitions

Prototype pollution occurs when attacker-controlled property names modify a shared JavaScript prototype, often `Object.prototype`. New objects can then inherit unexpected values. Common dangerous keys include `__proto__`, `constructor`, and `prototype`.

Deep merge utilities and path setters are frequent sources because they recursively trust keys supplied in JSON. A polluted property can influence authorization checks, feature flags, serialization, or other code that reads inherited values.

## Setup

Node.js 18 or newer is recommended. The dependency is intentionally not installed by this repository.

```sh
cd prototype-pollution
npm install
```

## Run Safe Mode

```sh
npm start
```

The service uses safe mode by default. It uses null-prototype containers, rejects protected path segments, and applies a smaller safe endpoint payload limit.

## Demonstrate the Vulnerable Paths

Start a second process after stopping safe mode:

```sh
npm run start:vulnerable
```

Reset first, then exercise the `__proto__` merge path:

```sh
curl -s -X POST http://127.0.0.1:3003/reset
curl -s -X POST http://127.0.0.1:3003/vulnerable/merge \
  -H 'content-type: application/json' \
  -d '{"source":{"__proto__":{"polluted":true}}}'
curl -s http://127.0.0.1:3003/
```

The final response should report `freshObjectPolluted: true` in vulnerable mode. The request changed the process-wide `Object.prototype`; it is not a safe pattern and should never be copied into an application.

The `constructor.prototype` concept can be observed with the path setter:

```sh
curl -s -X POST http://127.0.0.1:3003/reset
curl -s -X POST http://127.0.0.1:3003/vulnerable/set \
  -H 'content-type: application/json' \
  -d '{"path":"constructor.prototype.role","value":"training"}'
curl -s http://127.0.0.1:3003/
```

Node.js versions and object behavior can differ around special properties. If a platform does not show the expected status, inspect the source and use the response status as the lesson rather than weakening runtime protections. Do not send these payloads to an external target.

## Compare the Safe Fix

With safe mode running, send the same JSON to `/safe/merge` and the same path to `/safe/set`:

```sh
curl -s -X POST http://127.0.0.1:3003/safe/merge \
  -H 'content-type: application/json' \
  -d '{"source":{"__proto__":{"polluted":true},"theme":"local"}}'
curl -s -X POST http://127.0.0.1:3003/safe/set \
  -H 'content-type: application/json' \
  -d '{"path":"constructor.prototype.role","value":"training"}'
curl -s http://127.0.0.1:3003/
```

The safe merge ignores protected keys and preserves `theme`. The safe setter returns HTTP `400` for the protected path. The final status should show that a fresh object has not inherited the demo properties.

## Remediation

Prefer well-maintained merge libraries with prototype-pollution fixes. If implementing a merge or setter, allowlist expected schema keys, reject `__proto__`, `constructor`, and `prototype` at every depth, use own-property checks, and construct data containers with `Object.create(null)` where suitable. Do not treat inherited values as trusted authorization state. Add regression tests for both nested JSON keys and dotted/array paths.

## Reset and Cleanup

Reset process state before stopping the server:

```sh
curl -s -X POST http://127.0.0.1:3003/reset
```

Then stop Node with `Ctrl-C` and remove this lab's install artifacts:

```sh
./cleanup.sh
```

The cleanup script removes only `node_modules` and the local npm lockfile. It does not remove global Node.js or npm installations.
