<template>
  <div
    class="upload-zone"
    :class="{ dragover }"
    @dragover.prevent="dragover = true"
    @dragleave.prevent="dragover = false"
    @drop.prevent="onDrop"
    @click="$refs.fileInput.click()"
  >
    <input
      ref="fileInput"
      type="file"
      accept="image/*,video/mp4,video/webm"
      multiple
      hidden
      @change="onFileSelect"
    />
    <div class="upload-content">
      <i class="pi pi-cloud-upload"></i>
      <p>Drop files here or click to browse</p>
      <span class="hint">Images and videos (MP4, WebM)</span>
    </div>
    <div v-if="uploads.length" class="upload-list">
      <div v-for="u in uploads" :key="u.name" class="upload-item">
        <span class="upload-name">{{ u.name }}</span>
        <div v-if="u.error" class="upload-error">{{ u.error }}</div>
        <div v-else-if="u.status === 'processing'" class="upload-processing">Processing...</div>
        <div v-else class="upload-bar">
          <div class="upload-progress" :style="{ width: u.progress + '%' }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['uploaded'])
const dragover = ref(false)
const uploads = ref([])

function onDrop(e) {
  dragover.value = false
  if (e.dataTransfer?.files) uploadFiles(e.dataTransfer.files)
}

function onFileSelect(e) {
  // Snapshot files before clearing the input — uploadFiles is async, and
  // resetting value='' empties the live FileList mid-iteration, so without
  // the copy only the first selected file would actually upload.
  const files = e.target.files ? Array.from(e.target.files) : []
  e.target.value = ''
  if (files.length) uploadFiles(files)
}

async function uploadFiles(files) {
  for (const file of files) {
    uploads.value.push({ name: file.name, progress: 0, error: null, status: 'uploading' })
    const entry = uploads.value[uploads.value.length - 1]

    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', file.name)

    try {
      const xhr = new XMLHttpRequest()
      await new Promise((resolve, reject) => {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            entry.progress = Math.round((e.loaded / e.total) * 100)
            if (entry.progress >= 100) entry.status = 'processing'
          }
        })
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            entry.status = 'done'
            resolve()
          } else {
            let detail = ''
            try { detail = JSON.parse(xhr.responseText)?.detail || xhr.responseText } catch { detail = xhr.statusText }
            reject(new Error(`Upload failed for "${file.name}": HTTP ${xhr.status} — ${detail}`))
          }
        })
        xhr.addEventListener('error', () => reject(new Error(`Upload failed for "${file.name}": network error (server unreachable or request blocked)`)))
        xhr.open('POST', '/api/assets')
        const token = localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
        xhr.send(formData)
      })
    } catch (err) {
      entry.error = err.message
      console.error(`[UploadZone] ${err.message}`)
    }

    // Keep failed entries visible longer so the user sees the error
    setTimeout(() => {
      uploads.value = uploads.value.filter((u) => u !== entry)
    }, entry.error ? 5000 : 1500)
  }
  emit('uploaded')
}
</script>

<style scoped>
.upload-zone {
  border: 2px dashed var(--border-strong);
  border-radius: 8px;
  padding: 1rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  margin-bottom: 0;
}

.upload-zone:hover,
.upload-zone.dragover {
  border-color: var(--accent);
  background: rgba(var(--accent-rgb), 0.05);
}

.upload-content i {
  font-size: 1.5rem;
  color: var(--text-faint);
  margin-bottom: 0.3rem;
}

.upload-content p {
  color: var(--text-secondary);
  margin-bottom: 0.3rem;
}

.hint {
  font-size: 0.8rem;
  color: var(--text-faint);
}

.upload-list {
  margin-top: 1rem;
  text-align: left;
}

.upload-item {
  margin-bottom: 0.5rem;
}

.upload-name {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.upload-bar {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 3px;
}

.upload-progress {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s;
}

.upload-processing {
  font-size: 0.8rem;
  color: var(--accent);
  margin-top: 3px;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.upload-error {
  color: #ff6b6b;
  font-size: 0.8rem;
  margin-top: 3px;
}
</style>
