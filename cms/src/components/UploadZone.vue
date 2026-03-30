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
  if (e.target.files) uploadFiles(e.target.files)
  e.target.value = ''
}

async function uploadFiles(files) {
  for (const file of files) {
    const entry = { name: file.name, progress: 0, error: null }
    uploads.value.push(entry)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', file.name)

    try {
      const xhr = new XMLHttpRequest()
      await new Promise((resolve, reject) => {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) entry.progress = Math.round((e.loaded / e.total) * 100)
        })
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            entry.progress = 100
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
  border: 2px dashed #3a3a5a;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  margin-bottom: 1.5rem;
}

.upload-zone:hover,
.upload-zone.dragover {
  border-color: #7c83ff;
  background: rgba(124, 131, 255, 0.05);
}

.upload-content i {
  font-size: 2rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.upload-content p {
  color: #ccc;
  margin-bottom: 0.3rem;
}

.hint {
  font-size: 0.8rem;
  color: #666;
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
  color: #aaa;
}

.upload-bar {
  height: 4px;
  background: #2a2d3a;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 3px;
}

.upload-progress {
  height: 100%;
  background: #7c83ff;
  transition: width 0.2s;
}

.upload-error {
  color: #ff6b6b;
  font-size: 0.8rem;
  margin-top: 3px;
}
</style>
