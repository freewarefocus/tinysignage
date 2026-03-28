(function () {
    "use strict";

    const API = "/api/assets";
    let assets = [];
    let draggedItem = null;

    // --- DOM refs ---
    const playlist = document.getElementById("playlist");
    const fileInput = document.getElementById("file-input");
    const dropzone = document.getElementById("dropzone");
    const urlForm = document.getElementById("url-form");
    const editModal = document.getElementById("edit-modal");
    const editForm = document.getElementById("edit-form");
    const editCancel = document.getElementById("edit-cancel");
    const settingsForm = document.getElementById("settings-form");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const currentAssetEl = document.getElementById("current-asset");
    const playerCountEl = document.getElementById("player-count");

    // --- Init ---
    refreshPlaylist();
    loadSettings();
    pollStatus();

    // --- File upload ---
    fileInput.addEventListener("change", () => {
        uploadFiles(fileInput.files);
        fileInput.value = "";
    });

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            uploadFiles(e.dataTransfer.files);
        }
    });

    async function uploadFiles(files) {
        for (const file of files) {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("name", file.name.replace(/\.[^.]+$/, ""));
            try {
                const res = await fetch(API, { method: "POST", body: formData });
                if (!res.ok) throw new Error(await res.text());
                toast("Uploaded " + file.name, "success");
            } catch (err) {
                toast("Upload failed: " + err.message, "error");
            }
        }
        refreshPlaylist();
    }

    // --- URL form ---
    urlForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = document.getElementById("url-name").value.trim();
        const url = document.getElementById("url-input").value.trim();
        const duration = parseInt(document.getElementById("url-duration").value) || 10;

        const formData = new FormData();
        formData.append("name", name);
        formData.append("url", url);
        formData.append("asset_type", "url");
        formData.append("duration", duration);

        try {
            const res = await fetch(API, { method: "POST", body: formData });
            if (!res.ok) throw new Error(await res.text());
            toast("Added URL asset", "success");
            urlForm.reset();
            document.getElementById("url-duration").value = "10";
            refreshPlaylist();
        } catch (err) {
            toast("Failed to add URL: " + err.message, "error");
        }
    });

    // --- Playlist rendering ---
    async function refreshPlaylist() {
        try {
            const res = await fetch(API);
            assets = await res.json();
        } catch {
            toast("Failed to load playlist", "error");
            return;
        }
        render();
    }

    function render() {
        if (assets.length === 0) {
            playlist.innerHTML = '<div class="empty-state">No assets yet. Upload an image or add a URL above.</div>';
            return;
        }

        playlist.innerHTML = assets
            .map(
                (a) => `
            <div class="asset-item" draggable="true" data-id="${a.id}">
                <span class="drag-handle">&#9776;</span>
                ${thumbnail(a)}
                <div class="asset-info">
                    <span class="asset-name">${esc(a.name)}</span>
                    <span class="asset-meta">${a.asset_type} &middot; ${a.duration === 0 ? 'natural length' : a.duration + 's'}</span>
                </div>
                <div class="asset-controls">
                    <button class="play-btn" title="Play now">&#9654;</button>
                    <button class="toggle-btn" data-enabled="${a.is_enabled}" title="${a.is_enabled ? "Enabled" : "Disabled"}">&#9679;</button>
                    <button class="edit-btn">Edit</button>
                    <button class="delete-btn">Delete</button>
                </div>
            </div>`
            )
            .join("");

        setupDragDrop();
        setupControls();
    }

    function thumbnail(asset) {
        if (asset.asset_type === "image") {
            return `<img class="thumbnail" src="/media/${esc(asset.uri)}" alt="">`;
        }
        if (asset.asset_type === "video") {
            return `<div class="thumbnail-icon">&#127910;<span class="badge">Video</span></div>`;
        }
        if (asset.asset_type === "url") {
            return `<div class="thumbnail-icon">&#127760;</div>`;
        }
        return `<div class="thumbnail-icon">&#128196;</div>`;
    }

    function esc(str) {
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }

    // --- Drag and drop reorder ---
    function setupDragDrop() {
        const items = playlist.querySelectorAll(".asset-item");
        items.forEach((item) => {
            item.addEventListener("dragstart", (e) => {
                draggedItem = item;
                item.classList.add("dragging");
                e.dataTransfer.effectAllowed = "move";
            });

            item.addEventListener("dragend", () => {
                item.classList.remove("dragging");
                playlist.querySelectorAll(".asset-item").forEach((el) => el.classList.remove("drag-over"));
                draggedItem = null;
            });

            item.addEventListener("dragover", (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                if (draggedItem && item !== draggedItem) {
                    playlist.querySelectorAll(".asset-item").forEach((el) => el.classList.remove("drag-over"));
                    item.classList.add("drag-over");
                }
            });

            item.addEventListener("drop", (e) => {
                e.preventDefault();
                if (!draggedItem || item === draggedItem) return;
                const allItems = [...playlist.querySelectorAll(".asset-item")];
                const fromIdx = allItems.indexOf(draggedItem);
                const toIdx = allItems.indexOf(item);
                if (fromIdx < toIdx) {
                    item.after(draggedItem);
                } else {
                    item.before(draggedItem);
                }
                saveNewOrder();
            });
        });
    }

    async function saveNewOrder() {
        const items = playlist.querySelectorAll(".asset-item");
        const order = Array.from(items).map((item, index) => ({
            id: item.dataset.id,
            play_order: index,
        }));
        try {
            await fetch(API + "/reorder", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(order),
            });
        } catch {
            toast("Reorder failed", "error");
        }
    }

    // --- Controls (toggle, edit, delete) ---
    function setupControls() {
        playlist.querySelectorAll(".play-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const id = btn.closest(".asset-item").dataset.id;
                try {
                    await fetch(`/api/control/asset/${id}`, { method: "POST" });
                } catch {
                    toast("Jump failed", "error");
                }
            });
        });

        playlist.querySelectorAll(".toggle-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.closest(".asset-item").dataset.id;
                const enabled = btn.dataset.enabled === "true";
                toggleAsset(id, !enabled);
            });
        });

        playlist.querySelectorAll(".edit-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.closest(".asset-item").dataset.id;
                openEdit(id);
            });
        });

        playlist.querySelectorAll(".delete-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const id = btn.closest(".asset-item").dataset.id;
                deleteAsset(id);
            });
        });
    }

    async function toggleAsset(id, enabled) {
        try {
            const res = await fetch(`${API}/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_enabled: enabled }),
            });
            if (!res.ok) throw new Error();
            refreshPlaylist();
        } catch {
            toast("Toggle failed", "error");
        }
    }

    async function deleteAsset(id) {
        if (!window.confirm("Delete this asset?")) return;
        try {
            const res = await fetch(`${API}/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error();
            toast("Asset deleted", "success");
            refreshPlaylist();
        } catch {
            toast("Delete failed", "error");
        }
    }

    // --- Edit modal ---
    function openEdit(id) {
        const asset = assets.find((a) => a.id === id);
        if (!asset) return;
        document.getElementById("edit-id").value = asset.id;
        document.getElementById("edit-name").value = asset.name;
        document.getElementById("edit-duration").value = asset.duration;
        document.getElementById("edit-start").value = asset.start_date ? asset.start_date.slice(0, 16) : "";
        document.getElementById("edit-end").value = asset.end_date ? asset.end_date.slice(0, 16) : "";
        editModal.classList.remove("hidden");
    }

    editCancel.addEventListener("click", () => {
        editModal.classList.add("hidden");
    });

    editModal.addEventListener("click", (e) => {
        if (e.target === editModal) editModal.classList.add("hidden");
    });

    editForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = document.getElementById("edit-id").value;
        const body = {
            name: document.getElementById("edit-name").value.trim(),
            duration: parseInt(document.getElementById("edit-duration").value) || 10,
            start_date: document.getElementById("edit-start").value || null,
            end_date: document.getElementById("edit-end").value || null,
        };
        try {
            const res = await fetch(`${API}/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error();
            toast("Asset updated", "success");
            editModal.classList.add("hidden");
            refreshPlaylist();
        } catch {
            toast("Update failed", "error");
        }
    });

    // --- Settings ---
    async function loadSettings() {
        try {
            const res = await fetch("/api/settings");
            const s = await res.json();
            document.getElementById("transition-duration").value = s.transition_duration;
            document.getElementById("transition-type").value = s.transition_type;
            document.getElementById("default-duration").value = s.default_duration;
            document.getElementById("shuffle").checked = s.shuffle;
        } catch {
            toast("Failed to load settings", "error");
        }
    }

    settingsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const data = {
            transition_duration: parseFloat(document.getElementById("transition-duration").value) || 1.0,
            transition_type: document.getElementById("transition-type").value,
            default_duration: parseInt(document.getElementById("default-duration").value) || 10,
            shuffle: document.getElementById("shuffle").checked,
        };
        try {
            const res = await fetch("/api/settings", {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
            });
            if (!res.ok) throw new Error();
            toast("Settings saved", "success");
        } catch {
            toast("Failed to save settings", "error");
        }
    });

    // --- Playback controls ---
    prevBtn.addEventListener("click", async () => {
        try {
            await fetch("/api/control/previous", { method: "POST" });
        } catch {
            toast("Control failed", "error");
        }
    });

    nextBtn.addEventListener("click", async () => {
        try {
            await fetch("/api/control/next", { method: "POST" });
        } catch {
            toast("Control failed", "error");
        }
    });

    // --- Status polling ---
    async function pollStatus() {
        try {
            const res = await fetch("/api/status");
            const status = await res.json();
            currentAssetEl.textContent = status.current_asset_name || "\u2014";
            playerCountEl.textContent = status.connected_players ?? "\u2014";
        } catch {
            // silent
        }
        setTimeout(pollStatus, 5000);
    }

    // --- Toast ---
    function toast(msg, type) {
        const el = document.createElement("div");
        el.className = "toast " + type;
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }
})();
