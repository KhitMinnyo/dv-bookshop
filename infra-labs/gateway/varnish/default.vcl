vcl 4.1;

import std;

backend default {
    .host = "backend";
    .port = "8080";
    .first_byte_timeout = 5s;
    .between_bytes_timeout = 5s;
}

sub vcl_recv {
    # Only ordinary read methods are eligible for this lab cache.
    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    }

    # Do not cache requests carrying user state or credentials.
    if (req.http.Authorization || req.http.Cookie) {
        return (pass);
    }

    # Avoid turning redirect-like parameters into a reusable cached response.
    if (req.url ~ "(?i)(^|[?&])(next|url|return|redirect)=") {
        return (pass);
    }

    # A dynamic path with an asset-looking suffix is a cache-deception risk.
    if (req.url ~ "(?i)\.(css|js|jpg|jpeg|png|gif|svg|ico)(/|\?|$)") {
        return (pass);
    }

    # Query sorting makes equivalent parameter order share a key; no parameters
    # are discarded. Application-specific signed parameters need explicit review.
    set req.url = std.querysort(req.url);

    return (hash);
}

sub vcl_hash {
    # Use only server-derived host and the normalized URL. Do not hash arbitrary
    # X-Forwarded-* values supplied by a client.
    hash_data(req.http.host);
    hash_data(req.url);

    # This small origin declares content negotiation on Accept. Real services
    # should derive this list from their actual Vary contract.
    if (req.http.Accept ~ "application/json") {
        hash_data("accept:json");
    } else {
        hash_data("accept:other");
    }
}

sub vcl_backend_response {
    # Preserve Cache-Control, ETag, and Vary from the origin. Never cache a
    # response that sets a session cookie or explicitly forbids shared caching.
    if (beresp.http.Set-Cookie ||
        beresp.http.Cache-Control ~ "(?i)(private|no-store|no-cache)") {
        set beresp.uncacheable = true;
        set beresp.ttl = 0s;
        return (deliver);
    }

    set beresp.grace = 30s;
}

sub vcl_deliver {
    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
    } else {
        set resp.http.X-Cache = "MISS";
    }
    # Varnish supplies Age for cacheable objects. Do not manufacture it here.
}
