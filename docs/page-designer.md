# Page Designer

The Page Designer is a visual, drag-and-drop slide builder for creating **Custom Slides** -- branded announcements, event posters, lower thirds, live clocks, scrolling text, and other one-off displays -- without writing any HTML.

You can think of it as PowerPoint for one slide at a time. Drop in some text, an image, maybe a clock widget, drag things around until they look right, hit **Save**, and the result lands in your Media Library as a regular asset that you can drop into any playlist.

---

## What's a Custom Slide?

Most TinySignage content is uploaded media -- a JPG, an MP4, a PDF page. A **Custom Slide** is content you build *inside* the CMS instead of uploading. It still ends up as an asset in the Media Library and still plays through playlists like everything else, but the source of truth is the design you laid out, not a file on your computer.

Use Custom Slides for things like:

- "We close at 4pm today" announcements
- Event posters with title, date, and location
- A live digital clock to fill a corner of a lobby screen
- Welcome screens with your business name
- A scrolling marquee message above other content

---

## Opening the designer

There are three ways to get there. They all open the same editor.

1. **Sidebar nav** -- click **Designer** (the palette icon) to start a fresh, blank slide.
2. **Media Library > Add Custom Slide** -- the palette icon button at the top of the Media page. Same thing: a fresh blank slide.
3. **Media Library > Edit on an existing Custom Slide** -- if you previously made a slide in the designer, clicking its **Edit** button reopens it with every element exactly where you left it.

> **Note for legacy slides:** If you have HTML assets created before the Page Designer existed (with the old "raw HTML" editor), clicking **Edit** on those still opens the raw HTML editor instead of the designer. There is no automatic conversion -- the designer only opens slides it created. If you navigate to one of these directly, you'll see a yellow banner with an **Open in raw HTML editor instead** button.

You need the **Editor** or **Admin** role to use the designer. Viewers don't see the Designer entry in the sidebar.

---

## A 5-minute tour of the editor

```
+---------------------------------------------------------------+
|  [Slide name]   Undo  Redo  [ ] Snap   Preview   Save    X    |
+---------------+---------------------------------+-------------+
| Tabs:         |                                 | Properties  |
|  Elements     |                                 |             |
|  Templates    |       16:9 canvas               |  X / Y      |
|  Layers       |       (centered, scaled)        |  W / H      |
|               |                                 |  Opacity    |
|  > Text       |                                 |             |
|  > Image      |                                 |  Text /     |
|  > Shapes     |                                 |  Image /    |
|  > Widgets    |                                 |  Shape /    |
|  > Background |                                 |  Widget     |
|               |                                 |  fields     |
|               |                                 |             |
|               |                                 |  Duplicate  |
|               |                                 |  Delete     |
+---------------+---------------------------------+-------------+
```

### Topbar

- **Slide name** -- what the asset will be called in the Media Library. Change it before you save.
- **Undo / Redo** -- 50 levels of undo. Anything you do is recoverable, including loading a template over your work.
- **Snap** -- when checked (default), dragging and resizing snap to whole-percent steps so things line up cleanly. Uncheck for fine adjustments.
- **Preview** -- opens a fullscreen preview that renders the slide exactly the way the player will. Live widgets actually animate. Press **Esc** or click outside to close.
- **Save** -- saves the slide to the Media Library. The first save creates the asset; subsequent saves update it.
- **X** -- closes the designer and returns to the Media Library. Unsaved changes are lost, so save first.

### The canvas

The canvas in the middle is fixed at **16:9** (the widescreen ratio used by virtually every TV). The editor scales it to fit your screen, but the saved slide always describes a 1920x1080 layout that scales automatically when it plays -- a slide you make on a laptop will look right on a 4K TV, a vertical kiosk, or any other display.

You don't need to think about pixels. Position and size are stored as percentages of the canvas, so everything moves and resizes proportionally.

Click an element to select it. Drag it to move. Drag a corner handle to resize. Click the empty canvas to deselect.

### The left palette -- three tabs

**Elements** (default tab) -- click any tile to drop that element onto the canvas.

| Section | Tiles |
|---|---|
| **Text** | Heading (big), Body (smaller) |
| **Image** | Image -- pick from your Media Library |
| **Shapes** | Rectangle, Circle, Line (divider) |
| **Live Widgets** | Clock, Date, Weather, Centered Text, Heading + Subtitle, Scrolling Text, Countdown |
| **Background** | Eight color swatches plus a custom color picker |

**Templates** -- five ready-made designs you can load with one click as a starting point:

| Template | What it looks like |
|---|---|
| Announcement | Bold heading with supporting subtitle on a deep blue background |
| Event Promo | "Tonight @ 7PM"-style event headline with an accent divider |
| Digital Clock | Minimal full-screen live clock |
| Lower Third | Speaker name and title in a colored bar near the bottom |
| Welcome Screen | Eyebrow line plus a big headline on a purple background |

Loading a template **replaces** whatever's currently on the canvas. Don't worry -- it's a single Undo away.

**Layers** -- a vertical list of every element on the canvas. The top of the list is drawn on top of everything below it. Click a row to select that element. The up/down arrows on each row reorder the stack.

### The right properties panel

If nothing is selected, this panel shows a hint: *"Select an element to edit its properties."*

When you click an element, the panel fills in with that element's settings.

**Common to every element:**

- **X %, Y %** -- position from the top-left of the canvas
- **W %, H %** -- width and height as percentages of the canvas
- **Opacity** -- 0% (invisible) to 100% (solid)

**Text elements:**

- Text content (multi-line)
- Font size (px @ 1080p -- see [About font sizes](#about-font-sizes-px--1080p) below)
- Color
- Weight: Light / Regular / Semibold / Bold
- Alignment: Left / Center / Right
- Font family: Sans-serif / Serif / Monospace

**Image elements:**

- Image picker (a dropdown of every image already in your Media Library)
- Fit: Cover (fill, may crop) / Contain (fit inside) / Stretch
- *If your library has no images yet*, the picker will tell you. Upload one in **Media Library** first, then come back.

**Shape elements:**

- Shape: Rectangle / Circle / Divider line
- Fill color
- Border radius (rectangles only)

**Widget elements:**

- Widget picker (Clock, Date, Weather, etc.)
- A dynamic form for that widget's parameters -- a clock has 24-hour toggle, show seconds, timezone, font size, color. A weather widget has latitude, longitude, units, refresh interval. Each widget defines its own parameters.

**At the bottom:**

- **Duplicate** -- makes an offset copy of the selected element
- **Delete** -- removes the selected element (red button)

---

## Adding your first element

1. Click **Heading** in the left palette. A heading lands in the middle of the canvas.
2. The properties panel on the right fills in. Type your real headline into the **Text** box.
3. Drag the heading where you want it, or change **X / Y** in the panel for precise placement.
4. Drag a corner handle to resize, or change **W / H** for precise sizing.
5. Click a **Background** swatch on the left to set the slide's background color.
6. Click **Preview** to see what it'll look like at full screen.
7. Type a slide name into the topbar and click **Save**.

Done. The slide is now in your Media Library and has been added to the default playlist.

---

## Using a template

If you're not sure where to start, the Templates tab is the easy path:

1. Click the **Templates** tab in the left palette.
2. Click any template card. It loads onto the canvas.
3. Click each element and edit its text, color, size, or position. Templates are starting points -- they're meant to be customized.
4. Preview, name, save.

Templates are the recommended path for first-time users. Even if you don't keep much of the layout, you'll learn how the editor works by changing things in a real design.

---

## Live widgets

Live widgets are special elements that **keep updating in real time** while the slide is on screen. A clock ticks. Weather refreshes. A countdown counts down. They're not static images.

Available widgets:

| Widget | What it does |
|---|---|
| **Clock** | Live time, configurable 12/24h, optional seconds, timezone, font size, color |
| **Date** | Current date with format and locale options |
| **Weather** | Current temperature from Open-Meteo (free, no API key). Configurable lat/lon, units, refresh interval |
| **Centered Text** | Static centered message with custom size and weight |
| **Heading + Subtitle** | Two-line heading and subtitle pair |
| **Scrolling Text** | Smooth horizontal marquee text |
| **Countdown** | Live countdown to a target date and time |

Each widget you add is independent. You can put two clocks on one slide and set them to different time zones for a hotel lobby, for example.

> Widgets show as a placeholder tile in the editor canvas (so editing stays fast). To see what a widget actually looks like in motion, click **Preview**.

---

## Preview and save

Always click **Preview** before you save. The preview opens a fullscreen overlay that renders the slide using the exact same code that the player will run, including animated widgets. This is how you check that:

- Text isn't too big for its box
- Colors look right against the background
- Images aren't getting cropped weirdly
- Widgets are showing the values you expect

Press **Esc** or click outside the preview to close it.

When you're happy, type a **Slide name** in the topbar and click **Save**. The first save creates a new asset in your Media Library. Subsequent saves update that same asset.

If a save fails for any reason (network blip, server error), you'll see a toast notification. Your work isn't lost -- the canvas keeps your design, just hit Save again.

---

## Editing a slide later

Open the Media Library and click **Edit** on a Custom Slide. If it was made in the designer, it reopens in the designer with every element, color, font, position, and widget parameter restored exactly. Edit anything you want and Save again to update the asset.

The slide can be reopened and edited any number of times with no quality loss.

(Slides that were created with the old raw HTML editor open in the raw HTML editor instead -- there is no migration path. If you want to recreate a legacy slide visually, you'll need to rebuild it from scratch in the designer.)

---

## Adding your slide to a playlist

Custom Slides behave like any other media asset. New slides are auto-added to the default playlist on save. To use one in a different playlist, open the [Playlists](playlists.md) page, open the playlist you want, and add the slide from the asset picker.

You can give a Custom Slide its own display duration, transition type, and transition fade time, just like any other asset.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| **Ctrl+Z** | Undo |
| **Ctrl+Y** | Redo |
| **Ctrl+D** | Duplicate selected element |
| **Delete** / **Backspace** | Delete selected element |
| **Esc** | Close the Preview overlay, or deselect the current element |

Shortcuts are ignored while you're typing in a text field, so editing text won't accidentally delete your selection.

---

## Tips and gotchas

### About font sizes (px @ 1080p)

Font sizes in the designer are entered in pixels, and the number is what the text would measure on a 1080p TV. The actual rendered size **scales with the screen** -- a 96px headline shows up bigger on a 4K wall and smaller on a 720p monitor, but it stays in the same proportion to the rest of the slide. You don't need to redesign for different screen sizes.

The rule of thumb: pick a number that looks right in **Preview**, not on the editor canvas (which is scaled down to fit your editor window).

### One slide per design

The designer makes **one slide at a time**. There's no concept of multi-page or slide sequences inside the designer. If you want a sequence -- "announcement, then promo, then clock" -- make each one as a separate Custom Slide and add them all to the same [Playlist](playlists.md). Playlists are how TinySignage composes sequences, and they handle slide-to-slide transitions for you.

### Templates are starting points

Loading a template replaces your current design. The expectation is that you then edit the text, swap images, change colors, and reposition things. The template is just there to save you the "blank canvas" problem.

### Images must already be in the Media Library

The image picker only shows images that already exist in your Media Library. If you need a photo that isn't there yet, save your designer work, go upload the image in **Media Library**, and come back -- the picker will see it on the next visit.

### Widgets are an iframe

Each live widget is rendered inside its own sandboxed iframe so it can run its own scripts safely. This is invisible to you, but it explains why widgets show as a placeholder tile in the editor and only render live in **Preview** and on the player.

### What the designer doesn't do (yet)

- **No multi-slide.** One design = one slide.
- **No element animation.** Text and shapes are static. Only widgets animate themselves. Slide-to-slide transitions are configured at the playlist level.
- **No author-time resolution picker.** Always 16:9 / 1920x1080. Designs scale at playback.
- **Fixed font choices.** Sans-serif, Serif, Monospace. Custom font upload is not supported in the current version.

### Power user escape hatch

If you really need raw HTML (maybe you have a snippet a designer gave you, or you want CSS animations the designer doesn't expose), the legacy raw HTML editor still exists. From the Media Library, use **Add HTML** instead of **Add Custom Slide**. Slides created that way are independent from the designer and can only be edited in the raw editor.

---

## See also

- [Managing Media](managing-media.md) -- Where Custom Slides live alongside your other assets
- [Playlists](playlists.md) -- Putting Custom Slides into a play sequence
- [Multi-Zone Layouts](multi-zone-layouts.md) -- Showing different content in different parts of the screen
