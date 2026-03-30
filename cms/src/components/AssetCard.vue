<template>
  <div class="asset-card" :class="{ disabled: !asset.is_enabled }">
    <div class="thumb-wrap">
      <img
        v-if="asset.thumbnail_path"
        :src="`/media/thumbs/${asset.thumbnail_path}`"
        class="thumb"
        alt=""
      />
      <div v-else class="thumb-placeholder">
        <i :class="typeIcon"></i>
      </div>
      <div class="hover-actions">
        <button v-if="asset.asset_type === 'html'" @click.stop="$emit('edit-html', asset)" title="Edit HTML">
          <i class="pi pi-pencil"></i>
        </button>
        <button v-if="asset.asset_type !== 'html'" @click.stop="$emit('replace', asset)" title="Replace file">
          <i class="pi pi-refresh"></i>
        </button>
        <button @click.stop="$emit('duplicate', asset)" title="Duplicate">
          <i class="pi pi-copy"></i>
        </button>
        <button @click.stop="$emit('delete', asset)" title="Delete" class="danger">
          <i class="pi pi-trash"></i>
        </button>
      </div>
    </div>
    <div class="card-info">
      <div
        v-if="editing"
        class="name-edit"
      >
        <input
          ref="nameInput"
          v-model="editName"
          @blur="saveName"
          @keydown.enter="saveName"
          @keydown.escape="cancelEdit"
        />
      </div>
      <div v-else class="name" @click="startEdit" :title="asset.name">
        {{ asset.name }}
      </div>
      <div class="meta">
        <span class="type-badge" :class="{ 'type-html': asset.asset_type === 'html' }">{{ asset.asset_type }}</span>
        <span v-if="asset.duration">{{ asset.duration }}s</span>
        <span v-else-if="asset.asset_type === 'video'">auto</span>
      </div>
      <!-- Transition override row -->
      <div class="transition-row">
        <select
          v-model="transitionType"
          class="transition-select"
          @change="saveTransition"
          title="Transition type override"
        >
          <option value="">Default</option>
          <option value="fade">Fade</option>
          <option value="slide">Slide</option>
          <option value="cut">Cut</option>
        </select>
        <input
          v-model.number="transitionDuration"
          type="number"
          class="transition-dur"
          min="0"
          max="30"
          step="0.5"
          placeholder=""
          title="Transition duration override (seconds)"
          @change="saveTransition"
        />
      </div>
      <!-- Tags row -->
      <div class="tags-row">
        <span
          v-for="t in asset.tags"
          :key="t.id"
          class="asset-tag"
          :style="{ background: t.color + '22', color: t.color, borderColor: t.color + '55' }"
        >
          {{ t.name }}
          <button class="tag-remove" @click.stop="removeTag(t)" :style="{ color: t.color }">&times;</button>
        </span>
        <button v-if="!showTagPicker" class="add-tag-btn" @click.stop="showTagPicker = true" title="Add tag">
          <template v-if="asset.tags?.length">+</template>
          <i v-else class="pi pi-tag" style="font-size: 0.6rem;"></i>
        </button>
        <!-- Tag picker dropdown (inside tags-row for correct positioning) -->
        <div v-if="showTagPicker" class="tag-picker" @click.stop>
          <div
            v-for="t in availableTags"
            :key="t.id"
            class="tag-option"
            @click="addTag(t)"
          >
            <span class="tag-dot" :style="{ background: t.color }"></span>
            {{ t.name }}
          </div>
          <div v-if="availableTags.length === 0" class="no-tags">No more tags</div>
          <button class="tag-picker-close" @click="showTagPicker = false">Done</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, watch } from 'vue'
import { api } from '../api/client.js'

const props = defineProps({
  asset: Object,
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['updated', 'replace', 'duplicate', 'delete', 'tag-changed', 'edit-html'])

const editing = ref(false)
const editName = ref('')
const nameInput = ref(null)
const showTagPicker = ref(false)
const transitionType = ref(props.asset.transition_type || '')
const transitionDuration = ref(props.asset.transition_duration ?? '')

watch(() => props.asset.transition_type, (v) => { transitionType.value = v || '' })
watch(() => props.asset.transition_duration, (v) => { transitionDuration.value = v ?? '' })

const typeIcon = computed(() => {
  switch (props.asset.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    case 'html': return 'pi pi-code'
    default: return 'pi pi-image'
  }
})

const availableTags = computed(() => {
  const assignedIds = new Set((props.asset.tags || []).map(t => t.id))
  return props.allTags.filter(t => !assignedIds.has(t.id))
})

function startEdit() {
  editName.value = props.asset.name
  editing.value = true
  nextTick(() => nameInput.value?.select())
}

async function saveName() {
  if (!editing.value) return
  editing.value = false
  if (editName.value && editName.value !== props.asset.name) {
    await api.patch(`/assets/${props.asset.id}`, { name: editName.value })
    emit('updated')
  }
}

function cancelEdit() {
  editing.value = false
}

async function saveTransition() {
  const body = {
    transition_type: transitionType.value || null,
    transition_duration: transitionDuration.value !== '' ? Number(transitionDuration.value) : null,
  }
  await api.patch(`/assets/${props.asset.id}`, body)
  emit('updated')
}

async function addTag(tag) {
  await api.post(`/assets/${props.asset.id}/tags`, { tag_id: tag.id })
  showTagPicker.value = false
  emit('tag-changed')
}

async function removeTag(tag) {
  await api.delete(`/assets/${props.asset.id}/tags/${tag.id}`)
  emit('tag-changed')
}
</script>

<style scoped>
.asset-card {
  background: #1a1d27;
  border-radius: 8px;
  overflow: visible;
  transition: box-shadow 0.2s;
}

.asset-card:hover {
  box-shadow: 0 0 0 1px #7c83ff;
}

.asset-card.disabled {
  opacity: 0.5;
}

.thumb-wrap {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #0f1117;
  border-radius: 8px 8px 0 0;
  overflow: hidden;
}

.thumb {
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
  font-size: 2rem;
  color: #444;
}

.hover-actions {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  opacity: 0;
  transition: opacity 0.15s;
}

.thumb-wrap:hover .hover-actions {
  opacity: 1;
}

.hover-actions button {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: #fff;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  transition: background 0.15s;
}

.hover-actions button:hover {
  background: rgba(255, 255, 255, 0.3);
}

.hover-actions button.danger:hover {
  background: rgba(244, 67, 54, 0.6);
}

.card-info {
  padding: 0.6rem 0.75rem;
}

.name {
  font-size: 0.85rem;
  color: #eee;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: text;
}

.name-edit input {
  width: 100%;
  background: #0f1117;
  border: 1px solid #7c83ff;
  color: #eee;
  font-size: 0.85rem;
  padding: 2px 4px;
  border-radius: 3px;
  outline: none;
}

.meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.3rem;
}

.type-badge {
  background: #252836;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  font-size: 0.65rem;
  letter-spacing: 0.5px;
}

.type-badge.type-html {
  background: #1a3a2a;
  color: #4caf50;
}

/* Transition overrides */
.transition-row {
  display: flex;
  gap: 0.3rem;
  margin-top: 0.35rem;
}

.transition-select {
  flex: 1;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #aaa;
  font-size: 0.7rem;
  padding: 2px 4px;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}

.transition-select:focus { border-color: #7c83ff; }

.transition-dur {
  width: 40px;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #aaa;
  font-size: 0.7rem;
  padding: 2px 4px;
  border-radius: 4px;
  outline: none;
  text-align: center;
}

.transition-dur:focus { border-color: #7c83ff; }

/* Tags */
.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.35rem;
  position: relative;
}

.asset-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 0.65rem;
  border: 1px solid;
  line-height: 1.4;
}

.tag-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0;
  line-height: 1;
  opacity: 0.6;
}

.tag-remove:hover { opacity: 1; }

.add-tag-btn {
  background: none;
  border: 1px dashed #444;
  color: #666;
  padding: 0px 5px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.7rem;
  line-height: 1.4;
  transition: all 0.15s;
}

.add-tag-btn:hover {
  border-color: #7c83ff;
  color: #7c83ff;
}

.tag-picker {
  position: absolute;
  top: 100%;
  left: 0;
  background: #252836;
  border: 1px solid #2a2d3a;
  border-radius: 6px;
  padding: 0.3rem;
  z-index: 10;
  min-width: 140px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}

.tag-option {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.5rem;
  font-size: 0.8rem;
  color: #ccc;
  cursor: pointer;
  border-radius: 4px;
}

.tag-option:hover {
  background: #1a1d27;
  color: #fff;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.no-tags {
  padding: 0.5rem;
  font-size: 0.75rem;
  color: #666;
  text-align: center;
}

.tag-picker-close {
  display: block;
  width: 100%;
  background: none;
  border: none;
  border-top: 1px solid #2a2d3a;
  color: #888;
  padding: 0.3rem;
  margin-top: 0.3rem;
  cursor: pointer;
  font-size: 0.75rem;
}

.tag-picker-close:hover { color: #fff; }
</style>
