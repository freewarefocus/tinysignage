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
        :class="layerClasses('a')"
        :style="layerStyle"
      >
        <component :is="layerComponent(layerA)" v-bind="layerProps(layerA)" />
      </div>
      <!-- Layer B -->
      <div
        class="mp-layer"
        :class="layerClasses('b')"
        :style="layerStyle"
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
  props.items.filter(item => item.asset)
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

const currentTxType = ref(props.transitionType || 'fade')
const currentTxDur = ref(props.transitionDuration ?? 1)
const prevLayer = ref(null)   // tracks which layer just became inactive (for slide-out)

const layerStyle = computed(() => {
  if (currentTxType.value === 'cut') return { transitionDuration: '0s' }
  return { '--mp-tx-dur': currentTxDur.value + 's' }
})

function layerClasses(id) {
  const isActive = activeLayer.value === id
  const isSlide = currentTxType.value === 'slide'
  return {
    'mp-visible': isActive && !isSlide,
    'mp-slide': isSlide,
    'mp-slide-in': isSlide && isActive,
    'mp-slide-out': isSlide && !isActive && prevLayer.value === id,
  }
}

function getItemTransition(item) {
  if (!item) return { type: props.transitionType || 'fade', dur: props.transitionDuration ?? 1 }
  const type = item.transition_type || item.asset?.transition_type || props.transitionType || 'fade'
  const dur = item.transition_duration ?? item.asset?.transition_duration ?? props.transitionDuration ?? 1
  return { type, dur }
}

function getAsset(item) {
  return item?.asset || item
}

function assetSrc(item) {
  const asset = getAsset(item)
  if (!asset) return ''
  if (asset.asset_type === 'url') return asset.uri
  return asset.uri.startsWith('http') ? asset.uri : `/media/${asset.uri}`
}

function layerComponent(item) {
  const asset = getAsset(item)
  if (!asset) return 'div'
  switch (asset.asset_type) {
    case 'video': return 'video'
    case 'html': return 'iframe'
    case 'url': return 'iframe'
    default: return 'img'
  }
}

function layerProps(item) {
  const asset = getAsset(item)
  if (!asset) return {}
  const src = assetSrc(item)
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

function getDuration(item) {
  if (!item) return props.defaultDuration
  // Item-level override → asset duration → global default
  if (item.duration != null && item.duration > 0) return item.duration
  const asset = item.asset || item
  return asset.duration || props.defaultDuration
}

function showAsset(index) {
  const item = orderedAssets.value[index]
  if (!item) return

  // Apply this item's transition settings
  const tx = getItemTransition(item)
  currentTxType.value = tx.type
  currentTxDur.value = tx.dur

  const prev = activeLayer.value
  // Load into the inactive layer, then flip
  if (prev === 'a') {
    layerB.value = item
    nextTick(() => { prevLayer.value = 'a'; activeLayer.value = 'b' })
  } else {
    layerA.value = item
    nextTick(() => { prevLayer.value = 'b'; activeLayer.value = 'a' })
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
  const item = orderedAssets.value[currentIndex.value]
  const dur = getDuration(item) * 1000
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
  currentTxType.value = props.transitionType || 'fade'
  currentTxDur.value = props.transitionDuration ?? 1
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
  transition: opacity var(--mp-tx-dur, 1s) ease-in-out;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mp-layer.mp-visible {
  opacity: 1;
}

/* Slide transition */
.mp-layer.mp-slide {
  opacity: 1;
  transition: transform var(--mp-tx-dur, 1s) ease-in-out, opacity 0s;
  transform: translateX(100%);  /* off-screen right by default */
}

.mp-layer.mp-slide.mp-slide-in {
  transform: translateX(0);
}

.mp-layer.mp-slide.mp-slide-out {
  transform: translateX(-100%);
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
