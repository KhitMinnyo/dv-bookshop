# Advanced Mobile Native Reversing Lab

This is an owner-controlled emulator lab. It is a small Android source fixture rather than a prebuilt APK. Build it only if the Android SDK, JDK, and Gradle toolchain are available. Do not point it at a production API or install it on a device you do not control.

## Learning Goals

- Locate embedded client configuration and dummy credentials in a release artifact.
- Compare runtime configuration, certificate pinning, and cleartext policy.
- Observe why client-side secrets are not a secure authorization boundary.
- Contrast the intentionally vulnerable fixture with the hardened source variant.

## Fixture Contents

- `android-fixture/app/src/main/java/com/example/mobilelab/MainActivity.kt`: small activity that shows the active lab mode and starts a request only after an explicit button press.
- `android-fixture/app/src/main/java/com/example/mobilelab/RuntimeConfig.kt`: deliberately shipped fake API key, fake client secret, and runtime endpoint.
- `android-fixture/app/src/main/java/com/example/mobilelab/ApiClient.kt`: vulnerable and hardened OkHttp examples, including certificate pinning.
- `android-fixture/app/src/main/AndroidManifest.xml`: network permission and an explicit non-production network security configuration.

The values `demo-public-key-DO-NOT-USE` and `demo-client-secret-DO-NOT-USE` are dummy training values. They are not credentials and are not valid against a real service.

## Build Or Inspect the Fixture

From this directory, if the Android toolchain is installed:

```sh
cd android-fixture
gradle --no-daemon assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.example.mobilelab/.MainActivity
```

The repository intentionally does not include a Gradle wrapper, wrapper JAR, or APK. If `gradle` is unavailable, inspect the source directly or add a local wrapper after checking the Android Gradle Plugin compatibility matrix. The fixture uses an intentionally obvious fake pin and endpoint, so a live request is expected to fail unless the learner supplies a private local test service and adjusts the fixture deliberately.

## Static Analysis Walkthrough

These commands are examples only. Run them against an APK you built locally or another authorized sample.

```sh
apktool d -o /tmp/mobile-lab-apktool app/build/outputs/apk/debug/app-debug.apk
jadx -d /tmp/mobile-lab-jadx app/build/outputs/apk/debug/app-debug.apk
```

In JADX or the apktool output, search for `demo-public-key`, `demo-client-secret`, `CertificatePinner`, `runtimeEndpoint`, and `lab_mode`. Compare source names with names and control flow in the decompiled artifact.

For MobSF, start MobSF according to its own installation documentation, upload only the locally built APK through its local interface, and review hardcoded secrets, network security, exported components, and certificate pinning findings. Do not upload this fixture to a public scanner.

## Dynamic Analysis Walkthrough

Use an Android emulator that you own. Frida and objection versions, package names, and USB/emulator transport differ by platform; verify their help output before using commands.

```sh
adb shell pm list packages | grep com.example.mobilelab
frida-ps -U
frida -U -f com.example.mobilelab -l your-authorized-observation-script.js
objection -g com.example.mobilelab explore
```

Observation exercises include locating the activity, recording the fake endpoint used by the fixture, and comparing the vulnerable and hardened code paths. Do not bypass protections on a third-party application. The hardened example is educational and does not claim to defeat a determined rooted-device analyst.

## Local API Testing

The fixture does not ship an API server. If you create a separate, local mock API, bind it to loopback and use the emulator host alias where required (`10.0.2.2` for the standard Android emulator). Example request shape:

```sh
curl --fail-with-body -i \
  -H 'Authorization: Bearer local-lab-token' \
  -H 'X-Client-Key: demo-public-key-DO-NOT-USE' \
  http://127.0.0.1:8787/health
```

This command is documentation for an optional local mock only. There is no service on port `8787` in this repository, and no external call should be substituted.

## Vulnerable Versus Hardened

The vulnerable path uses compile-time fake values, accepts a runtime endpoint, and demonstrates a pin configuration that is easy to find in a decompiled artifact. The hardened path keeps no client secret, rejects non-HTTPS endpoints, uses a network security policy, and enables certificate pinning with a placeholder pin that must be replaced during a controlled local exercise. Server-side authorization remains mandatory in both cases.

The hardened source is not a universal mobile security recipe. Real applications should use short-lived server-issued tokens, platform keystores where appropriate, secure release configuration, dependency updates, logging controls, and server-side verification.

## Reset and Cleanup

```sh
rm -rf android-fixture/app/build android-fixture/.gradle
adb uninstall com.example.mobilelab
```

Only run the `adb uninstall` command against an emulator or device you own. Remove temporary apktool/JADX/MobSF output under `/tmp` when the exercise is complete. No cleanup command is required if you only inspect the source.
