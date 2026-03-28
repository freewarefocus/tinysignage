<template>
  <div>
    <h2>Media Library</h2>

    <UploadZone @uploaded="loadAssets" />

    <div v-if="assets.length === 0" class="empty">
      <p>No media yet. Upload images or videos to get started.</p>
    </div>

    <div v-else class="asset-grid">
      <AssetCard
        v-for="asset in assets"
        :key="asset.id"
        :asset="asset"
        @updated="loadAssets"
        @replace="replaceAsset"
        @duplicate="duplicateAsset"
        @delete="deleteAsset"
      />
    </div>

    <!-- Hidden file input for replace -->
    <input
      ref="replaceInput"
      type="file"
      accept="image/*,video/mp4,video/webm"
      hidden
      @change="onReplaceFile"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'
import UploadZone from '../components/UploadZone.vue'
import AssetCard from '../components/AssetCard.vue'

const assets = ref([])
const replaceInput = ref(null)
const replaceTarget = ref(null)

async function loadAssets() {
  assets.value = await api.get('/assets')
}

function replaceAsset(asset) {
  replaceTarget.value = asset
  replaceInput.value.click()
}

async function onReplaceFile(e) {
  const file = e.target.files?.[0]
  if (!file || !replaceTarget.value) return

  const formData = new FormData()
  formData.append('file', file)

  await api.put(`/assets/${replaceTarget.value.id}/replace`, formData)
  replaceTarget.value = null
  e.target.value = ''
  await loadAssets()
}

async function duplicateAsset(asset) {
  await api.post(`/assets/${asset.id}/duplicate`)
  await loadAssets()
}

async function deleteAsset(asset) {
  if (!confirm(`Delete "${asset.name}"?`)) return
  await api.delete(`/assets/${asset.id}`)
  await loadAssets()
}

onMounted(loadAssets)
</script>

<style scoped>
h2 {
  margin-bottom: 1.2rem;
  color: #fff;
}

.empty {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
</style>
