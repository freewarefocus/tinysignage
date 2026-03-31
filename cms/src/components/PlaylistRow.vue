<template>
  <div class="playlist-row" draggable="true" @dragstart="onDragStart" @dragend="onDragEnd">
    <div class="drag-handle">
      <i class="pi pi-bars"></i>
    </div>
    <div class="row-thumb">
      <img
        v-if="item.asset?.thumbnail_path"
        :src="`/media/thumbs/${item.asset.thumbnail_path}`"
        alt=""
      />
      <div v-else class="thumb-placeholder">
        <i :class="typeIcon"></i>
      </div>
    </div>
    <div class="row-body">
      <div class="row-top">
        <div class="row-info">
          <div class="row-name">{{ item.asset?.name || 'Unknown' }}</div>
          <div class="row-meta">
            <span class="type-badge">{{ item.asset?.asset_type }}</span>
            <span v-if="item.asset?.duration">{{ item.asset.duration }}s</span>
            <span v-else-if="item.asset?.asset_type === 'video'">auto</span>
            <span
              v-for="t in tags"
              :key="t.id"
              class="item-tag"
              :style="{ background: t.color + '22', color: t.color, borderColor: t.color + '55' }"
            >{{ t.name }}</span>
          </div>
        </div>
      </div>
      <div v-if="canEdit" class="row-controls">
        <div class="control-group">
          <label>Effect</label>
          <select :value="item.transition_type || ''" @change="onUpdate('transition_type', $event.target.value || null)">
            <option value="">Default</option>
            <option value="fade">Fade</option>
            <option value="slide">Slide</option>
            <option value="cut">Cut</option>
          </select>
        </div>
        <div class="control-group">
          <label>Fade time</label>
          <input
            type="number"
            :value="item.transition_duration ?? ''"
            @change="onUpdate('transition_duration', $event.target.value === '' ? null : Number($event.target.value))"
            min="0" max="30" step="0.5"
            placeholder="--"
            class="num-input"
          />
        </div>
        <div class="control-group">
          <label>Show for</label>
          <input
            type="number"
            :value="item.duration ?? ''"
            @change="onUpdate('duration', $event.target.value === '' ? null : Number($event.target.value))"
            min="1" max="3600" step="1"
            placeholder="--"
            class="num-input"
          />
        </div>
        <div class="control-group">
          <label>Scaling</label>
          <select :value="item.object_fit || ''" @change="onUpdate('object_fit', $event.target.value || null)">
            <option value="">Default</option>
            <option value="contain">Fit inside</option>
            <option value="cover">Fill & crop</option>
            <option value="fill">Stretch</option>
            <option value="none">Original size</option>
          </select>
        </div>
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

const props = defineProps({
  item: Object,
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['remove', 'update'])

const tags = computed(() => props.item.asset?.tags || [])

const typeIcon = computed(() => {
  switch (props.item.asset?.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    case 'html': return 'pi pi-code'
    default: return 'pi pi-image'
  }
})

function onUpdate(field, value) {
  emit('update', { id: props.item.id, field, value })
}

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
  align-items: flex-start;
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
  padding-top: 0.4rem;
}

.row-thumb {
  width: 64px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #0f1117;
  margin-top: 0.15rem;
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

.row-body {
  flex: 1;
  min-width: 0;
}

.row-top {
  display: flex;
  align-items: center;
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
  flex-wrap: wrap;
  gap: 0.35rem;
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

.item-tag {
  display: inline-flex;
  align-items: center;
  padding: 0px 5px;
  border-radius: 10px;
  font-size: 0.6rem;
  border: 1px solid;
  line-height: 1.4;
}

/* Per-item controls */
.row-controls {
  display: flex;
  gap: 0.6rem;
  margin-top: 0.35rem;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.control-group label {
  font-size: 0.6rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  white-space: nowrap;
}

.control-group select {
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #aaa;
  font-size: 0.7rem;
  padding: 2px 4px;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}

.control-group select:focus { border-color: #7c83ff; }

.num-input {
  width: 42px;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #aaa;
  font-size: 0.7rem;
  padding: 2px 4px;
  border-radius: 4px;
  outline: none;
  text-align: center;
}

.num-input:focus { border-color: #7c83ff; }

.row-actions {
  padding-top: 0.3rem;
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
