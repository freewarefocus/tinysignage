<template>
  <div class="mini-player" v-if="assets.length > 0">
    <div class="mini-player-label">
      <i class="pi pi-play-circle"></i>
      <span>Preview</span>
      <button class="mp-control" @click="togglePlay" :title="playing ? 'Pause' : 'Play'">
        <i :class="playing ? 'pi pi-pause' : 'pi pi-play'"></i>
      </button>
      <span class="mp-counter">{{ currentIndex + 1 }} / {{ orderedAssets.length }}</span>
    </div>
    <div class="mini-player-frame" ref="frameEl">
      <!-- Layer A -->
      <div
        class="mp-layer"
        :class="{ 'mp-visible': activeLayer === 'a' }"
        :style="{ transitionDuration: transitionDur + 's' }"
      >
        <component :is="layerComponent(layerA)" v-bind="layerProps(layerA)" />
      </div>
      <!-- Layer B -->
      <div
        class="mp-layer"
        :class="{ 'mp-visible': activeLayer === 'b' }"
        :style="{ transitionDuration: transitionDur + 's' }"
      >
        <component :is="layerComponent(layerB)" v-bind="layerProps(layerB)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  /** Array of playlist items (each has .asset with .uri, .asset_type, .duration, .transition_type, .transition_duration) */
  items: { type: Array, default: () => [] },
  /** Playlist-level settings */
  transitionType: { type: String, default: 'fade' },
  transitionDuration: { type: Number, default: 1 },
  defaultDuration: { type: Number, default: 10 },
  shuffle: { type: Boolean, default: false },
})

const playing = ref(true)
const currentIndex = ref(0)
const activeLayer = ref('a')
const layerA = ref(null)
const layerB = ref(null)
let timer = null

const assets = computed(() =>
  props.items
    .filter(item => item.asset)
    .map(item => item.asset)
)

const orderedAssets = computed(() => {
  if (!props.shuffle) return assets.value
  // Deterministic shuffle based on array length (re-shuffles when list changes)
  const arr = [...assets.value]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
})

const transitionDur = computed(() => props.transitionDuration ?? 1)

function assetSrc(asset) {
  if (!asset) return ''
  if (asset.asset_type === 'url') return asset.uri
  // For images/videos, use the media path
  return asset.uri.startsWith('http') ? asset.uri : `/media/${asset.uri}`
}

function layerComponent(asset) {
  if (!asset) return 'div'
  switch (asset.asset_type) {
    case 'video': return 'video'
    case 'html': return 'iframe'
    case 'url': return 'iframe'
    default: return 'img'
  }
}

function layerProps(asset) {
  if (!asset) return {}
  const src = assetSrc(asset)
  switch (asset.asset_type) {
    case 'video':
      return { src, autoplay: true, muted: true, loop: true, class: 'mp-media' }
    case 'html':
      return { src, sandbox: 'allow-scripts allow-same-origin', class: 'mp-media mp-iframe' }
    case 'url':
      return { src: asset.uri, sandbox: 'allow-scripts allow-same-origin', class: 'mp-media mp-iframe' }
    default:
      return { src, class: 'mp-media', alt: asset.name || '' }
  }
}

function getDuration(asset) {
  if (!asset) return props.defaultDuration
  return asset.duration || props.defaultDuration
}

function showAsset(index) {
  const asset = orderedAssets.value[index]
  if (!asset) return

  // Load into the inactive layer, then flip
  if (activeLayer.value === 'a') {
    layerB.value = asset
    nextTick(() => { activeLayer.value = 'b' })
  } else {
    layerA.value = asset
    nextTick(() => { activeLayer.value = 'a' })
  }
  currentIndex.value = index
}

function advance() {
  if (orderedAssets.value.length === 0) return
  const next = (currentIndex.value + 1) % orderedAssets.value.length
  showAsset(next)
  scheduleNext()
}

function scheduleNext() {
  clearTimeout(timer)
  if (!playing.value) return
  const asset = orderedAssets.value[currentIndex.value]
  const dur = getDuration(asset) * 1000
  timer = setTimeout(advance, dur)
}

function togglePlay() {
  playing.value = !playing.value
  if (playing.value) {
    scheduleNext()
  } else {
    clearTimeout(timer)
  }
}

function reset() {
  clearTimeout(timer)
  currentIndex.value = 0
  activeLayer.value = 'a'
  if (orderedAssets.value.length > 0) {
    layerA.value = orderedAssets.value[0]
    layerB.value = null
    if (playing.value) scheduleNext()
  }
}

// Watch for item changes and reset
watch(() => props.items, reset, { deep: true })

onMounted(() => {
  if (orderedAssets.value.length > 0) {
    layerA.value = orderedAssets.value[0]
    if (playing.value) scheduleNext()
  }
})

onUnmounted(() => {
  clearTimeout(timer)
})
</script>

<style scoped>
.mini-player {
  margin-top: 1.5rem;
  border-top: 1px solid #2a2d3a;
  padding-top: 1rem;
}

.mini-player-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
  color: #888;
  font-size: 0.85rem;
}

.mini-player-label i:first-child {
  color: #7c83ff;
}

.mp-control {
  background: #252836;
  border: none;
  color: #999;
  width: 26px;
  height: 26px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  margin-left: 0.3rem;
  transition: background 0.15s, color 0.15s;
}

.mp-control:hover {
  background: #2f3348;
  color: #fff;
}

.mp-counter {
  margin-left: auto;
  font-size: 0.75rem;
  color: #666;
  font-family: monospace;
}

.mini-player-frame {
  position: relative;
  width: 400px;
  max-width: 100%;
  aspect-ratio: 16 / 9;
  background: #111;
  border-radius: 6px;
  overflow: hidden;
}

.mp-layer {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity ease-in-out;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mp-layer.mp-visible {
  opacity: 1;
}

.mp-media {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.mp-iframe {
  border: none;
}
</style>
