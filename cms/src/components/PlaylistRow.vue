<template>
  <div class="playlist-row" draggable="true" @dragstart="onDragStart" @dragend="onDragEnd">
    <div class="drag-handle">
      <i class="pi pi-bars"></i>
    </div>
    <div class="row-thumb">
      <img
        v-if="item.asset?.thumbnail_path"
        :src="`/api/assets/${item.asset.id}/thumbnail`"
        alt=""
      />
      <div v-else class="thumb-placeholder">
        <i :class="typeIcon"></i>
      </div>
    </div>
    <div class="row-info">
      <div class="row-name">{{ item.asset?.name || 'Unknown' }}</div>
      <div class="row-meta">
        <span class="type-badge">{{ item.asset?.asset_type }}</span>
        <span v-if="item.asset?.duration">{{ item.asset.duration }}s</span>
        <span v-else-if="item.asset?.asset_type === 'video'">auto</span>
      </div>
    </div>
    <div class="row-actions">
      <button @click="$emit('remove', item)" title="Remove from playlist" class="btn-remove">
        <i class="pi pi-times"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ item: Object })
defineEmits(['remove'])

const typeIcon = computed(() => {
  switch (props.item.asset?.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    case 'html': return 'pi pi-code'
    default: return 'pi pi-image'
  }
})

function onDragStart(e) {
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', props.item.id)
  e.target.classList.add('dragging')
}

function onDragEnd(e) {
  e.target.classList.remove('dragging')
}
</script>

<style scoped>
.playlist-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: #1a1d27;
  border-radius: 6px;
  cursor: grab;
  transition: background 0.15s;
}

.playlist-row:hover {
  background: #22252f;
}

.playlist-row.dragging {
  opacity: 0.4;
}

.drag-handle {
  color: #555;
  cursor: grab;
}

.row-thumb {
  width: 64px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #0f1117;
}

.row-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb-placeholder i {
  color: #444;
  font-size: 1rem;
}

.row-info {
  flex: 1;
  min-width: 0;
}

.row-name {
  font-size: 0.9rem;
  color: #eee;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #888;
  margin-top: 2px;
}

.type-badge {
  background: #252836;
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: uppercase;
  font-size: 0.6rem;
  letter-spacing: 0.5px;
}

.btn-remove {
  background: none;
  border: 1px solid #3a3a5a;
  color: #888;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, border-color 0.15s;
}

.btn-remove:hover {
  color: #f44336;
  border-color: #f44336;
}
</style>
