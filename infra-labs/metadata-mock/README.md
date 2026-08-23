# Local Cloud Metadata Mock

This Python standard-library server is a local-only dummy metadata endpoint. It binds to `127.0.0.1:5160`, makes no cloud calls, has no dependency on AWS or Azure, and returns only clearly fake identity and credential values.

## Start and Stop

From this directory:

```sh
python3 mock_metadata.py
```

Stop it with `Ctrl-C`. Do not change the bind address in the source or expose port `5160` through a firewall, container port mapping, tunnel, or reverse proxy.

## IMDSv1-Style Requests

IMDSv1-style metadata requests do not send a token:

```sh
curl -i http://127.0.0.1:5160/latest/meta-data/instance-id
curl -i http://127.0.0.1:5160/latest/dynamic/instance-identity/document
curl -i http://127.0.0.1:5160/latest/meta-data/iam/security-credentials/
curl -i http://127.0.0.1:5160/latest/meta-data/iam/security-credentials/lab-role
```

## IMDSv2-Style Token Flow

First request a short-lived, dummy token with `PUT`, then present it on metadata requests:

```sh
TOKEN=$(curl -s -X PUT http://127.0.0.1:5160/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
curl -i http://127.0.0.1:5160/latest/meta-data/instance-id \
  -H "X-aws-ec2-metadata-token: $TOKEN"
```

The mock accepts both the token flow and tokenless flow so that an instructor can compare the two models. The token is a fixed lab value and is not a secret.

## Connect the Existing DV-Bookshop SSRF Only to This Mock

The existing application has an intentionally vulnerable admin preview route at `/admin/preview_url` that fetches a user-supplied URL. Run the existing application on its normal local port `5005` only as described by the root project documentation. Start this mock separately, then use the authenticated admin preview form and enter exactly one of these local URLs:

```text
http://127.0.0.1:5160/latest/meta-data/instance-id
http://127.0.0.1:5160/latest/dynamic/instance-identity/document
```

This is a controlled demonstration of the existing SSRF route reaching a dummy local service. Do not enter cloud metadata addresses, private network addresses, public URLs, or any other target. If the application runs inside Docker, its `127.0.0.1` is the application container, not the host; do not work around that boundary by exposing a broader network. Use a separately authorized, loopback-only setup instead.

The mock does not implement a real cloud credential, cannot authorize cloud actions, and must not be used to test any service other than the local DV-Bookshop process you control.

## Reset and Cleanup

The server is stateless. Stop it with `Ctrl-C`. Remove only local Python cache files with:

```sh
rm -rf __pycache__
```

No root project reset script is involved.
