# Getting Started

Go from zero to content on a screen in about 10 minutes.

By the end of this guide you will have TinySignage running, an image uploaded, a playlist created, and a fullscreen player displaying your content.

---

## Install

The fastest path is Docker. If you prefer a native install, see the platform guides: [Raspberry Pi](install-raspberry-pi.md), [Windows](install-windows.md), [macOS](install-macos.md).

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
docker compose up -d
```

Wait about 30 seconds for the first build. When it finishes, TinySignage is running at `http://localhost:8080`.

For Docker details (data persistence, updating, resource limits), see [Install with Docker](install-docker.md).

---

## Run the setup wizard

Open `http://localhost:8080/setup` in your browser.

<!-- ![Setup wizard screenshot](images/setup-wizard.png) -->

Enter a name for your device (e.g., "Lobby TV") and create your admin account with a username and password. Click **Complete Setup**.

You are redirected to the CMS at `/cms`. Log in with the credentials you just created.

---

## Upload your first image

In the CMS, click **Media** in the sidebar. Drag an image file onto the upload zone, or click to browse.

<!-- ![Media upload screenshot](images/media-upload.png) -->

The image appears in the media library with an auto-generated thumbnail. Supported formats: JPG, PNG, WebP, GIF, MP4, WebM, and web URLs.

---

## Create a playlist

Click **Playlists** in the sidebar, then **New Playlist**. Give it a name.

Click into your new playlist. Click **Add Media** and select the image you uploaded. You can add more items, drag them to reorder, and set per-item display duration.

<!-- ![Playlist editor screenshot](images/playlist-editor.png) -->

---

## Open the player

Open `http://localhost:8080/player` in a new browser tab (or on a different screen). Press **F11** for fullscreen.

<!-- ![Player fullscreen screenshot](images/player-fullscreen.png) -->

The player polls the backend every 30 seconds. Your content appears automatically. Add or rearrange items in the CMS and the player picks up changes within 30 seconds -- no refresh needed.

---

## What's next?

You have a working signage display. Here is where to go depending on what you need:

- **More screens** -- Add devices from the CMS. See [Devices](devices.md).
- **Schedule by time of day** -- Show different playlists at different times. See [Scheduling](scheduling.md).
- **Split-screen zones** -- Divide the screen into regions with independent content. See [Multi-Zone Layouts](multi-zone-layouts.md).
- **Multiple users** -- Create accounts with different permission levels. See [Users and Permissions](users-and-permissions.md).
- **Custom display settings** -- Adjust transitions, durations, and more. See [Configuration](configuration.md).
- **HTML content and widgets** -- Add clocks, weather, or custom HTML. See [Managing Media](managing-media.md).

---

## See also

- [Install with Docker](install-docker.md) -- Docker-specific configuration
- [Managing Media](managing-media.md) -- All media types and upload options
- [Troubleshooting](troubleshooting.md) -- Common issues and fixes
