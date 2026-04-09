# TinySignage Android Player

A minimal Android WebView wrapper that turns any Android device into a TinySignage display. The app loads the same `player.html` that runs on Raspberry Pi and BrightSign — no native playback logic, just a fullscreen browser shell.

## What it does

1. **First launch** — Setup screen where you enter your TinySignage server address (e.g. `http://192.168.1.50:8080`). The app checks the server is reachable via `/health`.
2. **After setup** — Loads `{server}/player` in a fullscreen WebView. No status bar, no navigation bar, screen stays on.
3. **On reboot** — Auto-launches to the player (no user interaction needed).
4. **Admin access** — Triple-tap the top-right corner, enter PIN (default: `0000`), change server URL or exit.

## Prerequisites

- **JDK 17** — [Adoptium](https://adoptium.net/) or any OpenJDK 17 distribution
- **Android SDK command-line tools** — [developer.android.com/studio#command-line-tools-only](https://developer.android.com/studio#command-line-tools-only)

Set environment variables:
```bash
export JAVA_HOME=/path/to/jdk-17
export ANDROID_HOME=/path/to/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
```

Install required SDK packages:
```bash
sdkmanager "platforms;android-34" "build-tools;34.0.0"
```

## Build

```bash
cd android

# Debug build (for testing)
./gradlew assembleDebug
# Output: app/build/outputs/apk/debug/app-debug.apk

# Release build (unsigned)
./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release-unsigned.apk
```

## Sign a release APK

```bash
# Generate a keystore (one time)
keytool -genkey -v -keystore tinysignage.keystore -alias tinysignage \
  -keyalg RSA -keysize 2048 -validity 10000

# Sign the APK
apksigner sign --ks tinysignage.keystore --ks-key-alias tinysignage \
  app/build/outputs/apk/release/app-release-unsigned.apk
```

## Install on device

```bash
# Via USB with ADB
adb install app/build/outputs/apk/debug/app-debug.apk

# Or transfer the APK file to the device and open it
```

## Architecture

```
app/src/main/java/com/tinysignage/player/
  SetupActivity.java    — First-run server URL entry + /health validation
  MainActivity.java     — Fullscreen WebView kiosk shell
  BootReceiver.java     — BOOT_COMPLETED → auto-launch player
  KioskHelper.java      — Immersive mode + screen-on utilities
```

The WebView is configured with:
- JavaScript + DOM storage enabled (player.js needs localStorage)
- Media autoplay without user gesture
- Custom user-agent suffix `TinySignageApp/1.0` (detected by player.js as `player_type: 'android'`)
- Self-signed HTTPS accepted for the configured server URL only
- Network error retry every 10 seconds
- Back button disabled in kiosk mode

## Optional: Full kiosk lockdown

For unattended displays, you can set the app as device owner to prevent users from exiting:

```bash
adb shell dpm set-device-owner com.tinysignage.player/.BootReceiver
```

This is optional and not needed for basic operation.
