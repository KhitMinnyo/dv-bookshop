# Local API Gateway, WAF, CDN, and Cache Lab

This is a small local request path:

```text
browser or curl -> Nginx gateway -> Varnish cache -> dummy Nginx backend
                         127.0.0.1:8088
```

The Compose file is optional and uses only local Docker images. No service binds to the DV-Bookshop port `5005`; the only host binding is `127.0.0.1:8088`.

## Start and Stop

From this directory:

```sh
docker compose --profile stack up
```

The `stack` profile starts all three services. The backend has no host port and is reachable only on the internal Docker network. Stop and remove the containers with:

```sh
docker compose --profile stack down --remove-orphans
```

The configuration is a demonstration, not a production CDN or WAF. A real deployment needs a maintained WAF policy, request-size limits, origin authentication, observability, TLS policy, and an explicit cache invalidation strategy.

## Safe Inspection

Use only the dummy backend and ordinary requests:

```sh
curl -i http://127.0.0.1:8088/healthz
curl -i http://127.0.0.1:8088/catalog/book-1
curl -i http://127.0.0.1:8088/catalog/book-1
curl -i -H 'Accept: application/json' http://127.0.0.1:8088/catalog/book-1
curl -i -H 'Authorization: Bearer lab-user' http://127.0.0.1:8088/account
```

The second catalog request can show a Varnish `X-Cache: HIT` and an `Age` header. `/account` is explicitly passed before cache lookup, as are `/profile`, `/edit_profile`, `/delete_account`, `/cart`, `/checkout`, `/order_history`, `/order`, and `/admin`. Requests with `Authorization` or `Cookie` are also passed, so authenticated or session-personalized responses are not read from or stored in the shared cache. The `Accept` header is included in the Varnish hash only for the small content-negotiation example in `default.vcl`; production applications should make the variation policy match the backend's `Vary` contract.

## Configuration Examples

### Path normalization

Nginx has `merge_slashes on`, so repeated slashes are normalized before proxying. This configuration does not add an explicit dot-segment rejection; it relies on Nginx URI normalization and the origin's routing and authorization. Canonicalization must be consistent across the edge, cache, router, and application. If one layer decodes or normalizes a path differently, authorization and cache decisions can diverge.

The VCL sorts query parameters for the cache key. It does not remove query parameters: tracking parameters, signed parameters, and application parameters must be classified deliberately in a real system. The sample bypasses requests containing common redirect parameters rather than caching them.

### Forwarded-header trust

The public gateway does not trust client-supplied `X-Forwarded-For`, `X-Forwarded-Host`, or `X-Forwarded-Proto`. It overwrites them with values derived from the local request. In a multi-proxy deployment, replace this with a narrowly defined list of trusted proxy addresses and strip untrusted forwarding headers at the first trusted boundary. Never use arbitrary forwarded host data to create password-reset links or authorization decisions.

### Cache key and response headers

The VCL cache key includes the normalized host and URL. It deliberately excludes arbitrary request headers. Responses retain application-controlled `Cache-Control`, `ETag`, and `Vary` headers. Varnish supplies `Age` for a cached response, and the example adds `X-Cache` for local observation. Requests to known personalized paths, and requests carrying `Authorization` or `Cookie`, pass before cache lookup. Responses with `Set-Cookie`, a `Vary` header naming `Cookie` or `Authorization`, `private`, `no-store`, or `no-cache` are not cached.

### Cache poisoning

Cache poisoning occurs when an untrusted request value changes an origin response but is absent from the cache key. Typical examples are an unvalidated host, forwarding header, cookie, authorization context, or content-negotiation header. The sample reduces this risk by overwriting forwarding headers, bypassing known personalized paths and requests with cookies or authorization, refusing responses that vary on user context, hashing only an explicit `Accept` value, and refusing redirect-like query parameters. Those rules are not a substitute for matching the complete application response variation.

### Cache deception

Cache deception occurs when a dynamic endpoint is made to look like a cacheable static asset, such as a profile path followed by a fake `.css` suffix. The VCL bypasses paths that have an asset suffix followed by another path component, and the gateway marks `/account` as `private, no-store`. Applications should also route static and dynamic content under unambiguous namespaces and return `Cache-Control: private, no-store` for personalized responses.

## Simulated Fallback

If Docker or Varnish is unavailable, `nginx/simulated.conf` is a runnable, dependency-free Nginx fallback. It returns canned local responses and never proxies to an origin. Run it only on loopback with a locally installed Nginx, for example by reviewing the configuration and using a private prefix for Nginx runtime files. It demonstrates path handling and `Cache-Control`, `ETag`, and `Vary` headers without providing an executable external target.

`nginx/minimal.conf` is instead a proxy-only configuration for a placeholder origin at `127.0.0.1:8081`, which is intentionally not started by this repository. Point it at a local harmless HTTP server only if you are authorized to do so; do not bind that server beyond loopback.

Neither fallback is a replacement for the full Compose path because neither provides a Varnish cache process. The Varnish configuration remains the reference for cache-key and cache-deception behavior.

## Reset

This lab has no persistent application state. `docker compose --profile stack down --remove-orphans` removes its containers and networks. Add `--volumes` if a future local extension adds named volumes.
