<template>
  <div class="asset-card" :class="{ disabled: !asset.is_enabled }">
    <div class="thumb-wrap">
      <img
        v-if="asset.thumbnail_path"
        :src="`/api/assets/${asset.id}/thumbnail`"
        class="thumb"
        alt=""
      />
      <div v-else class="thumb-placeholder">
        <i :class="typeIcon"></i>
      </div>
      <div class="hover-actions">
        <button @click.stop="$emit('replace', asset)" title="Replace file">
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
        <span class="type-badge">{{ asset.asset_type }}</span>
        <span v-if="asset.duration">{{ asset.duration }}s</span>
        <span v-else-if="asset.asset_type === 'video'">auto</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue'
import { api } from '../api/client.js'

const props = defineProps({ asset: Object })
const emit = defineEmits(['updated', 'replace', 'duplicate', 'delete'])

const editing = ref(false)
const editName = ref('')
const nameInput = ref(null)

const typeIcon = computed(() => {
  switch (props.asset.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    default: return 'pi pi-image'
  }
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
</script>

<style scoped>
.asset-card {
  background: #1a1d27;
  border-radius: 8px;
  overflow: hidden;
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
</style>
