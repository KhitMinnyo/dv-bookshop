# HTTP Request Smuggling and Desynchronization Lab

This is an advanced, bounded parser fixture for studying `Content-Length` and
`Transfer-Encoding` disagreement. It does not open a socket, send a request,
start a proxy, or contact any target. All input is an in-memory byte string
whose maximum size is fixed in the source.

## Exact Scope

Only run this exercise against the fixture code in this directory. The only
host named by the examples is `localhost` as documentation context. Do not
point a browser, proxy, scanner, or custom request at DV-Bookshop, a shared
network, or an external service. Do not copy the sample framing into a
third-party request. The fixture is designed to show parser boundaries, not to
provide an exploitation tool.

## Run the Bounded Fixture

Python 3.10 or newer is sufficient and no packages are required:

```sh
python3 fixture.py --scenario cl-te
python3 fixture.py --scenario te-cl
```

The fixture prints the body and unread bytes as seen by a first parser and a
second parser. In the `cl-te` scenario, the first parser uses
`Content-Length` and the second uses chunked framing. In the `te-cl` scenario
the order is reversed. The sample is deliberately small and contains only the
literal host `localhost`.

## What It Demonstrates

The sample request has both headers:

```text
Content-Length: 4
Transfer-Encoding: chunked

4
WXYZ
0
```

The `Content-Length` view consumes four bytes (`4`, CR, LF, and `W`), while the
chunked view consumes the chunk framing and returns `WXYZ`. A real HTTP stack
has additional rules for duplicate headers, transfer codings, HTTP/2 and
HTTP/3 translation, connection reuse, and error handling. This fixture does
not model those rules and is not evidence that a real proxy is vulnerable.

## Safe Proxy Configuration Guidance

- Normalize framing once at the first trusted hop and pass a single unambiguous
  representation downstream.
- Reject requests containing both `Content-Length` and `Transfer-Encoding`
  unless the chosen standards-compliant parser has a documented, tested rule.
- Reject conflicting duplicate `Content-Length` values and invalid chunk
  syntax; do not silently choose one value.
- Use the same HTTP parser family and request-length limits at every hop when
  possible.
- Disable connection reuse after a framing parse error and close the affected
  client and upstream connections.
- Keep proxy, gateway, and application versions patched, and add regression
  tests for rejected ambiguous requests.
- Prefer an HTTP/2 or HTTP/3 end-to-end path where appropriate, while still
  validating any HTTP/1 translation boundary.
- Log parser decisions without logging credentials or full request bodies.

These are configuration principles, not a recommendation to weaken a real
proxy for testing. Validate changes in a disposable local environment with
vendor documentation and a review by the service owner.

## Limitations

This is an educational parser comparison, not a frontend/backend TCP server.
It does not demonstrate connection desynchronization, request queueing, proxy
behavior, TLS termination, HTTP/2 downgrades, or a complete RFC parser. Those
omissions are intentional safety and scope boundaries.
