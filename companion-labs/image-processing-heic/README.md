# Image Processing / HEIC Research Lab

**Difficulty:** Advanced  
**Category:** File Upload / Image Processing / Parser Security

## STUDENT GUIDE

### Scenario and Learning Objectives

The bookshop accepts cover images from authors and vendors. The upload looks like ordinary file handling, but covers are decoded, orientation-corrected, resized, converted, and turned into thumbnails on the server.

By completing this lab, you should be able to:

- Trace an uploaded file through the full server-side processing pipeline.
- Identify the image libraries, supported formats, versions, and relevant configuration.
- Test how untrusted image metadata behaves at the parser/application boundary.
- Distinguish a parser-facing application bug from native-code execution.
- Recommend and verify a least-disclosure remediation.

### Architecture

```text
Browser -> local Flask upload API -> Pillow / pillow-heif -> JPEG cover and thumbnail
                                  -> isolated synthetic diagnostic behavior
```

The container is read-only except for a 64 MiB temporary runtime directory. It runs as an unprivileged user, accepts at most 5 MiB per upload and 20 megapixels per decoded image, and binds only to `127.0.0.1:5507` on the host. The main DV-Bookshop app and its databases are not involved.

### Prerequisites

- Docker Engine and Docker Compose v2.
- No AWS, cloud, external network, or real account is used. The first image build/pull needs the pinned packages and container image; once cached locally, the lab itself makes no external requests.

### Start and Stop

From any working directory:

```sh
bash companion-labs/image-processing-heic/start.sh vulnerable
curl -s http://127.0.0.1:5507/healthz
```

Open `http://127.0.0.1:5507`. Upload a normal image or use the generated HEIC samples linked on the page. To stop the service and discard its temporary filesystem:

```sh
bash companion-labs/image-processing-heic/stop.sh
```

To remove the lab's locally built image as well:

```sh
bash companion-labs/image-processing-heic/clean.sh
```

### Scope and Safety Notice

This fixture intentionally demonstrates a controlled application-level information-disclosure mistake. It does not contain a real HEIF exploit, execute a command, load attacker-supplied native code, access host files, or invoke external services. The synthetic diagnostic strings are not credentials or real host paths. Do not replace the bounded fixture behavior with a real-world exploit payload.

### Student Challenge

Start with a normal JPEG or PNG and observe what the server returns. Then follow the file beyond the multipart handler: identify the decoder, transformations, output format, and available format/version information. Compare normal image metadata with the provided metadata-rich HEIC sample. Record the exact request, response, and impact, then determine whether the same information is available in hardened mode.

Submit a short finding that explains the trust boundary, the smallest reproducible input, the observable impact, and a fix that preserves ordinary image processing.

### Hints

- Inspect the processor information endpoint and the generated browser samples.
- File extensions and browser MIME types are not proof of the bytes being decoded.
- Compare the image's parsed metadata with the JSON returned after processing.
- Keep the investigation within the generated samples and this localhost service.

### Remediation

Treat decoded metadata as untrusted input. Do not return parser diagnostics or internal processing context to clients. Return a stable generic error/processing result, log only appropriately sanitized diagnostics to a protected sink, strip metadata from generated output when it is not required, and keep decoder dependencies current. Maintain strict size/pixel limits and process uploads with least privilege and resource isolation.

### Verification

Run the lab's unit tests inside the image:

```sh
docker compose -f companion-labs/image-processing-heic/docker-compose.yml \
  run --rm image-lab python -m unittest -v
```

For an interactive patched comparison, switch modes and upload the same generated metadata-rich sample again:

```sh
bash companion-labs/image-processing-heic/stop.sh
bash companion-labs/image-processing-heic/start.sh hardened
```

Successful verification includes a decoded HEIC output available as JPEG, no synthetic diagnostic in the hardened response, and unchanged normal image processing. Stop with the same `stop.sh` command.

## MAINTAINER / SOLUTION GUIDE

### Intended Vulnerability and Impact

`app.py` registers `pillow-heif` as a Pillow decoder and accepts decoded HEIF metadata. In vulnerable mode, an exact training-only EXIF `ImageDescription` marker causes the upload response to include a synthetic decoder cache namespace, worker label, and profile. This is an intentionally deterministic model of verbose parser/application diagnostics leaking internal processing context.

The impact is limited to three fixed strings under the `lab://` namespace. It does not disclose environment variables, filesystem paths, real secrets, or host state. The marker is included only in `/sample/cover-diagnostic.heic` and is `LAB:PROCESSOR-DIAGNOSTIC`.

### Why It Exists

The server performs actual image decoding, EXIF orientation handling, resizing, conversion to JPEG, and thumbnail generation. That makes the parser and metadata output part of the upload attack surface, rather than treating upload completion as the end of processing. The deliberate flaw is in the application response policy after metadata parsing; the pinned Pillow/pillow-heif versions are not represented as vulnerable native decoder releases.

### Vulnerable Configuration and Remediation

The default Compose file sets `LAB_MODE=vulnerable`. The bounded branch in the upload route includes synthetic diagnostics only for the training marker. The hardened Compose override sets `LAB_MODE=hardened`; the response then omits those details and reports that diagnostics were suppressed. The underlying HEIF decode and thumbnail path remain enabled so the before/after comparison isolates disclosure handling.

In a real service, remove the diagnostic branch, avoid reflecting parser internals, avoid logging attacker-controlled metadata unsafely, strip metadata where possible, enforce upload and decoded-pixel limits, run a current decoder in a constrained worker, and return stable errors. Updating the library alone would not correct an application-level disclosure policy.

### Verify the Fix

The four `unittest` cases check normal PNG conversion, actual generated HEIC decode/thumbnail conversion, the bounded vulnerable-versus-hardened diagnostic behavior, and rejection of non-image data. The Compose service binds host access to loopback, uses a read-only container with a bounded tmpfs, drops capabilities, and has no mounts into the repository or host. The lab intentionally does not claim to demonstrate native HEIF memory corruption or remote code execution.
