<template>
  <div>
    <div class="page-header">
      <div class="breadcrumb">
        <router-link to="/playlists" class="breadcrumb-link">Playlists</router-link>
        <i class="pi pi-angle-right breadcrumb-sep"></i>
        <template v-if="playlist">
          <span v-if="!editingName" class="breadcrumb-current" @click="startEditName">
            {{ playlist.name }}
            <i class="pi pi-pencil edit-hint"></i>
          </span>
          <span v-else class="breadcrumb-edit">
            <input
              v-model="nameInput"
              @keydown.enter="saveName"
              @keydown.escape="editingName = false"
              ref="nameInputEl"
            />
            <button class="btn-sm" @click="saveName">Save</button>
            <button class="btn-sm secondary" @click="editingName = false">Cancel</button>
          </span>
        </template>
      </div>
    </div>

    <div v-if="!playlist" class="loading">Loading...</div>

    <template v-else>
      <div class="playlist-header">
        <div class="header-left">
          <span v-if="playlist.is_default" class="default-badge" v-tooltip="'Plays when no schedule is active'">Default</span>
          <span v-if="playlist.mode === 'advanced'" class="mode-badge" v-tooltip="'Uses trigger-based interactive transitions'">Advanced</span>
          <span class="item-count">{{ items.length }} item(s)</span>
        </div>
        <div class="header-right">
          <span class="hash-label">Hash: {{ playlist.hash?.slice(0, 8) }}</span>
          <button
            v-if="canEdit && playlist.mode !== 'advanced'"
            class="btn-mode"
            @click="toggleMode('advanced')"
            title="Enable advanced trigger features"
          >
            <i class="pi pi-bolt"></i>
            <span>Make Advanced</span>
          </button>
          <button
            v-if="canEdit && playlist.mode === 'advanced'"
            class="btn-mode simplify"
            @click="confirmSimplify"
            title="Switch back to simple mode"
          >
            <i class="pi pi-minus-circle"></i>
            <span>Simplify</span>
          </button>
          <button class="btn-toggle" @click="showSettings = !showSettings">
            <i class="pi pi-cog"></i>
            <span>Settings</span>
            <i :class="showSettings ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="toggle-arrow"></i>
          </button>
        </div>
      </div>

      <!-- Per-playlist settings panel -->
      <div v-if="showSettings" class="settings-panel">
        <div class="settings-grid">
          <div class="setting-field">
            <label>Transition Type</label>
            <select v-model="plSettings.transition_type" @change="saveSettings" class="setting-select">
              <option :value="null">Global default</option>
              <option value="fade">Fade</option>
              <option value="slide">Slide</option>
              <option value="cut">Cut</option>
            </select>
          </div>
          <div class="setting-field">
            <label>Transition Duration (s)</label>
            <div class="number-input-row">
              <input
                type="number"
                :value="plSettings.transition_duration"
                @change="updateNumber('transition_duration', $event)"
                min="0" max="10" step="0.1"
                class="setting-number"
                placeholder="Global default"
              />
              <button
                v-if="plSettings.transition_duration !== null"
                class="btn-clear"
                @click="clearSetting('transition_duration')"
                title="Reset to global default"
              >&times;</button>
            </div>
          </div>
          <div class="setting-field">
            <label>Default Duration (s)</label>
            <div class="number-input-row">
              <input
                type="number"
                :value="plSettings.default_duration"
                @change="updateNumber('default_duration', $event)"
                min="1" max="3600" step="1"
                class="setting-number"
                placeholder="Global default"
              />
              <button
                v-if="plSettings.default_duration !== null"
                class="btn-clear"
                @click="clearSetting('default_duration')"
                title="Reset to global default"
              >&times;</button>
            </div>
          </div>
          <div class="setting-field">
            <label>Scaling</label>
            <select v-model="plSettings.object_fit" @change="saveSettings" class="setting-select">
              <option :value="null">Global default</option>
              <option value="contain">Fit inside</option>
              <option value="cover">Fill & crop</option>
              <option value="fill">Stretch</option>
              <option value="none">Original size</option>
            </select>
          </div>
          <div class="setting-field">
            <label>Display Effect</label>
            <select v-model="plSettings.effect" @change="saveSettings" class="setting-select">
              <option :value="null">Global default</option>
              <option value="none">None</option>
              <option value="zoom-in">Zoom In</option>
              <option value="zoom-out">Zoom Out</option>
              <option value="pan-left">Pan Left</option>
              <option value="pan-right">Pan Right</option>
              <option value="pan-up">Pan Up</option>
              <option value="pan-down">Pan Down</option>
              <option value="random">Random</option>
            </select>
          </div>
          <div class="setting-field">
            <label>Shuffle</label>
            <select v-model="plSettings.shuffle" @change="saveSettings" class="setting-select">
              <option :value="null">Global default</option>
              <option :value="true">On</option>
              <option :value="false">Off</option>
            </select>
          </div>
        </div>
        <p class="settings-hint">
          Leave blank or "Global default" to inherit from global settings.
        </p>
      </div>

      <!-- Simplify confirmation dialog -->
      <div v-if="showSimplifyConfirm" class="dialog-overlay" @click.self="showSimplifyConfirm = false">
        <div class="dialog">
          <h3>Simplify Playlist</h3>
          <p>Switch <strong>{{ playlist.name }}</strong> back to simple mode? Any trigger flow configuration will need to be re-assigned if you make it advanced again later.</p>
          <div class="dialog-actions">
            <button class="btn-danger" @click="toggleMode('simple')">Simplify</button>
            <button class="btn-secondary" @click="showSimplifyConfirm = false">Cancel</button>
          </div>
        </div>
      </div>

      <!-- Trigger flow editor (advanced mode only) -->
      <div v-if="playlist.mode === 'advanced'" class="trigger-panel">
        <div class="trigger-panel-header" @click="showTriggerPanel = !showTriggerPanel" style="cursor: pointer;">
          <i class="pi pi-bolt"></i>
          <span>Trigger Flow</span>
          <i :class="showTriggerPanel ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" class="trigger-toggle-icon"></i>
        </div>

        <div v-show="showTriggerPanel">
        <!-- Flow selector -->
        <div class="flow-selector">
          <select v-model="selectedFlowId" @change="assignFlow" class="flow-select">
            <option value="">— No flow assigned —</option>
            <option v-for="f in availableFlows" :key="f.id" :value="f.id">
              {{ f.name }} ({{ f.branch_count }} branch{{ f.branch_count !== 1 ? 'es' : '' }})
            </option>
          </select>
          <button v-if="canEdit" class="btn-flow" @click="showCreateFlow = true" title="Create new flow">
            <i class="pi pi-plus"></i>
          </button>
          <button v-if="canEdit && selectedFlowId" class="btn-flow detach" @click="detachFlow" title="Detach flow from playlist">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <!-- Create flow dialog -->
        <div v-if="showCreateFlow" class="inline-form">
          <input v-model="newFlowName" placeholder="Flow name" class="setting-number" @keydown.enter="createFlow" />
          <button class="btn-sm" @click="createFlow">Create</button>
          <button class="btn-sm secondary" @click="showCreateFlow = false; newFlowName = ''">Cancel</button>
        </div>

        <!-- Flow content (when assigned) -->
        <template v-if="currentFlow">
          <!-- Branch list -->
          <div v-if="currentFlow.branches && currentFlow.branches.length > 0" class="branch-list">
            <div v-for="branch in sortedBranches" :key="branch.id" class="branch-row">
              <div class="branch-info">
                <span class="branch-playlist">{{ branch.source_playlist_name || 'Unknown' }}</span>
                <i :class="triggerIcon(branch.trigger_type)" class="branch-trigger-icon" :title="branch.trigger_type"></i>
                <span class="branch-type-label">{{ triggerLabel(branch.trigger_type, branch.trigger_config) }}</span>
                <i class="pi pi-arrow-right branch-arrow"></i>
                <span class="branch-playlist">{{ branch.target_playlist_name || 'Unknown' }}</span>
                <span v-if="branch.priority" class="branch-priority" v-tooltip="'Higher priority branches are evaluated first'">P{{ branch.priority }}</span>
              </div>
              <div v-if="canEdit" class="branch-actions">
                <button class="btn-icon" @click="startEditBranch(branch)" title="Edit"><i class="pi pi-pencil"></i></button>
                <button class="btn-icon danger" @click="deleteBranch(branch.id)" title="Delete"><i class="pi pi-trash"></i></button>
              </div>
            </div>
          </div>
          <!-- Preset selector (shown when no branches exist) -->
          <div v-else class="preset-section">
            <p class="preset-intro">Start from a preset or add branches manually.</p>
            <div class="preset-grid">
              <div
                v-for="preset in triggerPresets"
                :key="preset.id"
                class="preset-card"
                @click="applyPreset(preset)"
              >
                <i :class="preset.icon" class="preset-icon"></i>
                <div class="preset-name">{{ preset.name }}</div>
                <div class="preset-desc">{{ preset.description }}</div>
              </div>
            </div>
          </div>

          <!-- Add / Edit branch form -->
          <button v-if="canEdit && !showBranchForm" class="btn-add-branch" @click="startAddBranch">
            <i class="pi pi-plus"></i> Add Branch
          </button>

          <div v-if="showBranchForm" class="branch-form">
            <h4>{{ editingBranchId ? 'Edit Branch' : 'Add Branch' }}</h4>
            <div class="branch-form-grid">
              <div class="setting-field">
                <label>Source Playlist</label>
                <select v-model="branchForm.source_playlist_id" class="setting-select">
                  <option value="">— Select —</option>
                  <option v-for="p in allPlaylists" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
              <div class="setting-field">
                <label>Target Playlist</label>
                <select v-model="branchForm.target_playlist_id" class="setting-select">
                  <option value="">— Select —</option>
                  <option v-for="p in allPlaylists" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
              <div class="setting-field">
                <label>Trigger Type</label>
                <select v-model="branchForm.trigger_type" class="setting-select" @change="onTriggerTypeChange">
                  <option value="keyboard">Keyboard</option>
                  <option value="touch_zone">Touch Zone</option>
                  <option value="timeout">Timeout</option>
                  <option value="loop_count">Loop Count</option>
                  <option value="gpio">GPIO</option>
                  <option value="webhook">Webhook</option>
                </select>
              </div>
              <div class="setting-field">
                <label>Priority</label>
                <input type="number" v-model.number="branchForm.priority" min="0" max="100" class="setting-number" />
              </div>
            </div>

            <!-- Dynamic config per trigger type -->
            <div class="trigger-config-section">
              <label class="config-label">Trigger Configuration</label>

              <!-- Keyboard -->
              <div v-if="branchForm.trigger_type === 'keyboard'" class="config-grid">
                <div class="setting-field">
                  <label>Key</label>
                  <select v-model="branchForm.trigger_config.key" class="setting-select">
                    <option value="ArrowLeft">Arrow Left</option>
                    <option value="ArrowRight">Arrow Right</option>
                    <option value="ArrowUp">Arrow Up</option>
                    <option value="ArrowDown">Arrow Down</option>
                    <option value="Enter">Enter</option>
                    <option value=" ">Space</option>
                    <option value="Escape">Escape</option>
                    <option v-for="n in 9" :key="n" :value="String(n)">{{ n }}</option>
                    <option value="_custom">Custom...</option>
                  </select>
                </div>
                <div v-if="branchForm.trigger_config.key === '_custom'" class="setting-field">
                  <label>Custom Key Name</label>
                  <input v-model="branchForm.trigger_config.customKey" class="setting-number" placeholder="e.g. a, F1, Tab" />
                </div>
                <div class="setting-field">
                  <label>Modifiers</label>
                  <div class="modifier-checks">
                    <label class="check-label"><input type="checkbox" v-model="keyModifiers.shift" /> Shift</label>
                    <label class="check-label"><input type="checkbox" v-model="keyModifiers.ctrl" /> Ctrl</label>
                    <label class="check-label"><input type="checkbox" v-model="keyModifiers.alt" /> Alt</label>
                  </div>
                </div>
              </div>

              <!-- Touch Zone -->
              <div v-if="branchForm.trigger_type === 'touch_zone'" class="config-grid">
                <div class="setting-field">
                  <label>X Position (%)</label>
                  <input type="number" v-model.number="branchForm.trigger_config.x_percent" min="0" max="100" class="setting-number" />
                </div>
                <div class="setting-field">
                  <label>Y Position (%)</label>
                  <input type="number" v-model.number="branchForm.trigger_config.y_percent" min="0" max="100" class="setting-number" />
                </div>
                <div class="setting-field">
                  <label>Width (%)</label>
                  <input type="number" v-model.number="branchForm.trigger_config.width_percent" min="1" max="100" class="setting-number" />
                </div>
                <div class="setting-field">
                  <label>Height (%)</label>
                  <input type="number" v-model.number="branchForm.trigger_config.height_percent" min="1" max="100" class="setting-number" />
                </div>
              </div>

              <!-- Timeout -->
              <div v-if="branchForm.trigger_type === 'timeout'" class="config-grid">
                <div class="setting-field">
                  <label>Seconds</label>
                  <input type="number" v-model.number="branchForm.trigger_config.seconds" min="1" max="3600" class="setting-number" />
                </div>
              </div>

              <!-- Loop Count -->
              <div v-if="branchForm.trigger_type === 'loop_count'" class="config-grid">
                <div class="setting-field">
                  <label>Loop Count</label>
                  <input type="number" v-model.number="branchForm.trigger_config.count" min="1" max="1000" class="setting-number" />
                </div>
              </div>

              <!-- GPIO -->
              <div v-if="branchForm.trigger_type === 'gpio'" class="config-grid">
                <div class="setting-field">
                  <label>Pin Number</label>
                  <input type="number" v-model.number="branchForm.trigger_config.pin" min="0" max="40" class="setting-number" />
                </div>
                <div class="setting-field">
                  <label>Edge</label>
                  <select v-model="branchForm.trigger_config.edge" class="setting-select">
                    <option value="falling">Falling (button press)</option>
                    <option value="rising">Rising</option>
                  </select>
                </div>
                <div class="setting-field">
                  <label>Debounce (ms)</label>
                  <input type="number" v-model.number="branchForm.trigger_config.debounce_ms" min="0" max="2000" class="setting-number" />
                </div>
              </div>

              <!-- Webhook -->
              <div v-if="branchForm.trigger_type === 'webhook'" class="config-grid">
                <div class="setting-field">
                  <label>Token</label>
                  <div class="webhook-token-row">
                    <input :value="branchForm.trigger_config.token" class="setting-number" readonly />
                    <button class="btn-flow" @click="regenerateToken" title="Regenerate token"><i class="pi pi-refresh"></i></button>
                  </div>
                  <span class="config-hint">Auto-generated. External systems POST this token to fire the trigger.</span>
                </div>
              </div>
            </div>

            <div class="branch-form-actions">
              <button class="btn-sm" @click="saveBranch">{{ editingBranchId ? 'Update' : 'Add' }}</button>
              <button class="btn-sm secondary" @click="cancelBranchForm">Cancel</button>
            </div>
          </div>
        </template>
        </div>
        <p class="form-hint trigger-hint">Trigger flows define how playlists transition based on user interaction (keyboard, touch, GPIO).</p>
      </div>

      <div
        class="playlist-items"
        @dragover.prevent="onDragOver"
        @drop.prevent="onDrop"
      >
        <div v-if="items.length === 0" class="empty">
          <p>Playlist is empty. Add media from the library below.</p>
        </div>
        <PlaylistRow
          v-for="item in items"
          :key="item.id"
          :item="item"
          :can-edit="canEdit"
          :data-item-id="item.id"
          @remove="removeItem"
          @update="updateItem"
          @reset="resetItem"
        />
      </div>

      <MiniPlayer
        v-if="items.length > 0"
        :items="items"
        :transition-type="plSettings.transition_type || 'fade'"
        :transition-duration="plSettings.transition_duration ?? 1"
        :default-duration="plSettings.default_duration ?? 10"
        :shuffle="plSettings.shuffle ?? false"
        :object-fit="plSettings.object_fit"
        :effect="plSettings.effect"
      />

      <div v-if="canEdit" class="add-section">
        <h3>Add from Media Library</h3>
        <div v-if="availableAssets.length === 0" class="empty-hint">
          No media available. Upload files in the Media Library first.
        </div>
        <div v-else class="add-grid">
          <div
            v-for="asset in availableAssets"
            :key="asset.id"
            class="add-card"
            @click="addToPlaylist(asset)"
            v-tooltip="'Click to add to playlist'"
          >
            <div class="add-thumb">
              <img
                v-if="asset.thumbnail_path"
                :src="`/media/thumbs/${asset.thumbnail_path}`"
                alt=""
              />
              <i v-else :class="typeIcon(asset)" class="add-icon"></i>
              <div class="add-hover-overlay">
                <i class="pi pi-plus-circle"></i>
              </div>
            </div>
            <div class="add-name">{{ asset.name }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client.js'
import PlaylistRow from '../components/PlaylistRow.vue'
import MiniPlayer from '../components/MiniPlayer.vue'
import { TRIGGER_PRESETS } from '../presets/triggerPresets.js'

const triggerPresets = TRIGGER_PRESETS

const route = useRoute()
const router = useRouter()

const userRole = (() => { try { return JSON.parse(localStorage.getItem('tinysignage_user') || '{}').role } catch { return 'viewer' } })()
const canEdit = ['admin', 'editor'].includes(userRole)

const playlist = ref(null)
const items = ref([])
const allAssets = ref([])
const editingName = ref(false)
const nameInput = ref('')
const nameInputEl = ref(null)
const showSettings = ref(false)
const showSimplifyConfirm = ref(false)
const plSettings = ref({
  transition_type: null,
  transition_duration: null,
  default_duration: null,
  object_fit: null,
  effect: null,
  shuffle: null,
})

// Trigger flow state
const showTriggerPanel = ref(false)
const availableFlows = ref([])
const currentFlow = ref(null)
const selectedFlowId = ref('')
const allPlaylists = ref([])
const showBranchForm = ref(false)
const editingBranchId = ref(null)
const showCreateFlow = ref(false)
const newFlowName = ref('')
const keyModifiers = ref({ shift: false, ctrl: false, alt: false })
const branchForm = ref(getDefaultBranchForm())

const availableAssets = computed(() => allAssets.value)

const playlistId = computed(() => route.params.id)

const sortedBranches = computed(() => {
  if (!currentFlow.value?.branches) return []
  return [...currentFlow.value.branches].sort((a, b) => (b.priority || 0) - (a.priority || 0))
})

function getDefaultBranchForm() {
  return {
    source_playlist_id: '',
    target_playlist_id: '',
    trigger_type: 'keyboard',
    priority: 0,
    trigger_config: { key: 'ArrowRight', modifiers: [] },
  }
}

function getDefaultConfigForType(type) {
  switch (type) {
    case 'keyboard': return { key: 'ArrowRight', modifiers: [] }
    case 'touch_zone': return { x_percent: 0, y_percent: 0, width_percent: 100, height_percent: 100 }
    case 'timeout': return { seconds: 30 }
    case 'loop_count': return { count: 3 }
    case 'gpio': return { pin: 17, edge: 'falling', debounce_ms: 200 }
    case 'webhook': return { token: generateToken() }
    default: return {}
  }
}

function generateToken() {
  const arr = new Uint8Array(8)
  crypto.getRandomValues(arr)
  return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('')
}

function triggerIcon(type) {
  switch (type) {
    case 'keyboard': return 'pi pi-desktop'
    case 'touch_zone': return 'pi pi-th-large'
    case 'timeout': return 'pi pi-clock'
    case 'loop_count': return 'pi pi-replay'
    case 'gpio': return 'pi pi-microchip'
    case 'webhook': return 'pi pi-globe'
    default: return 'pi pi-question'
  }
}

function triggerLabel(type, config) {
  switch (type) {
    case 'keyboard': return `Key: ${config?.key || '?'}${config?.modifiers?.length ? ' +' + config.modifiers.join('+') : ''}`
    case 'touch_zone': return `Zone: ${config?.x_percent ?? 0}%,${config?.y_percent ?? 0}% ${config?.width_percent ?? 100}x${config?.height_percent ?? 100}`
    case 'timeout': return `${config?.seconds ?? 0}s timeout`
    case 'loop_count': return `After ${config?.count ?? 0} loops`
    case 'gpio': return `Pin ${config?.pin ?? '?'} (${config?.edge || 'falling'})`
    case 'webhook': return 'Webhook'
    default: return type
  }
}

function typeIcon(asset) {
  switch (asset.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    case 'html': return 'pi pi-code'
    default: return 'pi pi-image'
  }
}

async function loadPlaylist() {
  const id = playlistId.value
  if (!id) return
  try {
    const full = await api.get(`/playlists/${id}`)
    playlist.value = full
    items.value = full.items || []
    plSettings.value = {
      transition_type: full.transition_type ?? null,
      transition_duration: full.transition_duration ?? null,
      default_duration: full.default_duration ?? null,
      object_fit: full.object_fit ?? null,
      effect: full.effect ?? null,
      shuffle: full.shuffle ?? null,
    }
    // Load trigger flow data for advanced playlists
    if (full.mode === 'advanced') {
      await loadFlows()
      selectedFlowId.value = full.trigger_flow_id || ''
      if (full.trigger_flow_id) {
        await loadFlow(full.trigger_flow_id)
      } else {
        currentFlow.value = null
      }
    }
  } catch (e) {
    router.push('/playlists')
  }
}

async function loadAssets() {
  allAssets.value = await api.get('/assets')
}

function startEditName() {
  nameInput.value = playlist.value.name
  editingName.value = true
  nextTick(() => nameInputEl.value?.focus())
}

async function saveName() {
  const name = nameInput.value.trim()
  if (name && name !== playlist.value.name) {
    await api.patch(`/playlists/${playlist.value.id}`, { name })
    await loadPlaylist()
  }
  editingName.value = false
}

function confirmSimplify() {
  showSimplifyConfirm.value = true
}

async function toggleMode(newMode) {
  if (!playlist.value) return
  await api.patch(`/playlists/${playlist.value.id}`, { mode: newMode })
  showSimplifyConfirm.value = false
  await loadPlaylist()
}

// --- Trigger Flow functions ---

async function loadFlows() {
  try {
    availableFlows.value = await api.get('/trigger-flows')
  } catch (err) { console.warn('[PlaylistEditor] Failed to load flows:', err); availableFlows.value = [] }
}

async function loadFlow(flowId) {
  if (!flowId) { currentFlow.value = null; return }
  try {
    currentFlow.value = await api.get(`/trigger-flows/${flowId}`)
  } catch (err) { console.warn('[PlaylistEditor] Failed to load flow:', err); currentFlow.value = null }
}

async function loadAllPlaylists() {
  try {
    allPlaylists.value = await api.get('/playlists')
  } catch (err) { console.warn('[PlaylistEditor] Failed to load playlists:', err); allPlaylists.value = [] }
}

async function assignFlow() {
  if (!playlist.value) return
  const flowId = selectedFlowId.value || null
  await api.patch(`/playlists/${playlist.value.id}`, { trigger_flow_id: flowId })
  await loadPlaylist()
  if (flowId) {
    await loadFlow(flowId)
  } else {
    currentFlow.value = null
  }
}

async function detachFlow() {
  selectedFlowId.value = ''
  await assignFlow()
}

async function createFlow() {
  const name = newFlowName.value.trim()
  if (!name) return
  const flow = await api.post('/trigger-flows', { name })
  newFlowName.value = ''
  showCreateFlow.value = false
  await loadFlows()
  selectedFlowId.value = flow.id
  await assignFlow()
}

async function applyPreset(preset) {
  // Create a flow if none assigned
  if (!currentFlow.value) {
    const flowName = preset.name + ' Flow'
    const flow = await api.post('/trigger-flows', { name: flowName })
    await loadFlows()
    selectedFlowId.value = flow.id
    await assignFlow()
  }
  // Pre-fill branch form with the first preset branch
  const firstBranch = preset.branches[0]
  if (!firstBranch) return
  editingBranchId.value = null
  const config = { ...firstBranch.trigger_config }
  // Auto-generate webhook token if needed
  if (firstBranch.trigger_type === 'webhook' && !config.token) {
    config.token = generateToken()
  }
  branchForm.value = {
    source_playlist_id: playlist.value?.id || '',
    target_playlist_id: '',
    trigger_type: firstBranch.trigger_type,
    priority: 0,
    trigger_config: config,
  }
  keyModifiers.value = { shift: false, ctrl: false, alt: false }
  showBranchForm.value = true
}

function onTriggerTypeChange() {
  branchForm.value.trigger_config = getDefaultConfigForType(branchForm.value.trigger_type)
  keyModifiers.value = { shift: false, ctrl: false, alt: false }
}

function startAddBranch() {
  editingBranchId.value = null
  branchForm.value = getDefaultBranchForm()
  // Default source to current playlist
  if (playlist.value) branchForm.value.source_playlist_id = playlist.value.id
  keyModifiers.value = { shift: false, ctrl: false, alt: false }
  showBranchForm.value = true
}

function startEditBranch(branch) {
  editingBranchId.value = branch.id
  const config = typeof branch.trigger_config === 'string' ? JSON.parse(branch.trigger_config) : { ...branch.trigger_config }
  branchForm.value = {
    source_playlist_id: branch.source_playlist_id,
    target_playlist_id: branch.target_playlist_id,
    trigger_type: branch.trigger_type,
    priority: branch.priority || 0,
    trigger_config: config,
  }
  if (branch.trigger_type === 'keyboard') {
    const mods = config.modifiers || []
    keyModifiers.value = { shift: mods.includes('Shift'), ctrl: mods.includes('Control'), alt: mods.includes('Alt') }
  } else {
    keyModifiers.value = { shift: false, ctrl: false, alt: false }
  }
  showBranchForm.value = true
}

function cancelBranchForm() {
  showBranchForm.value = false
  editingBranchId.value = null
}

function buildTriggerConfig() {
  const cfg = { ...branchForm.value.trigger_config }
  if (branchForm.value.trigger_type === 'keyboard') {
    // Resolve custom key
    if (cfg.key === '_custom') cfg.key = cfg.customKey || 'a'
    delete cfg.customKey
    // Build modifiers
    const mods = []
    if (keyModifiers.value.shift) mods.push('Shift')
    if (keyModifiers.value.ctrl) mods.push('Control')
    if (keyModifiers.value.alt) mods.push('Alt')
    cfg.modifiers = mods
  }
  return cfg
}

async function saveBranch() {
  if (!currentFlow.value) return
  const payload = {
    source_playlist_id: branchForm.value.source_playlist_id,
    target_playlist_id: branchForm.value.target_playlist_id,
    trigger_type: branchForm.value.trigger_type,
    trigger_config: buildTriggerConfig(),
    priority: branchForm.value.priority,
  }
  if (!payload.source_playlist_id || !payload.target_playlist_id) return

  if (editingBranchId.value) {
    await api.patch(`/trigger-branches/${editingBranchId.value}`, payload)
  } else {
    await api.post(`/trigger-flows/${currentFlow.value.id}/branches`, payload)
  }
  showBranchForm.value = false
  editingBranchId.value = null
  await loadFlow(currentFlow.value.id)
  await loadFlows()
}

async function deleteBranch(branchId) {
  await api.delete(`/trigger-branches/${branchId}`)
  await loadFlow(currentFlow.value.id)
  await loadFlows()
}

function regenerateToken() {
  branchForm.value.trigger_config.token = generateToken()
}

async function saveSettings() {
  if (!playlist.value) return
  await api.patch(`/playlists/${playlist.value.id}`, {
    transition_type: plSettings.value.transition_type,
    transition_duration: plSettings.value.transition_duration,
    default_duration: plSettings.value.default_duration,
    object_fit: plSettings.value.object_fit,
    effect: plSettings.value.effect,
    shuffle: plSettings.value.shuffle,
  })
}

function updateNumber(field, event) {
  const val = event.target.value
  plSettings.value[field] = val === '' ? null : Number(val)
  saveSettings()
}

function clearSetting(field) {
  plSettings.value[field] = null
  saveSettings()
}

async function addToPlaylist(asset) {
  if (!playlist.value) return
  await api.post(`/playlists/${playlist.value.id}/items`, { asset_id: asset.id })
  await loadPlaylist()
}

async function removeItem(item) {
  if (!playlist.value) return
  await api.delete(`/playlists/${playlist.value.id}/items/${item.id}`)
  await loadPlaylist()
}

async function updateItem({ id, field, value }) {
  if (!playlist.value) return
  await api.patch(`/playlists/${playlist.value.id}/items/${id}`, { [field]: value })
  await loadPlaylist()
}

async function resetItem(itemId) {
  if (!playlist.value) return
  await api.patch(`/playlists/${playlist.value.id}/items/${itemId}`, {
    transition_type: null,
    transition_duration: null,
    duration: null,
    object_fit: null,
    effect: null,
  })
  await loadPlaylist()
}

// Drag-and-drop reorder
function onDragOver(e) {
  e.dataTransfer.dropEffect = 'move'
}

async function onDrop(e) {
  const draggedId = e.dataTransfer.getData('text/plain')
  if (!draggedId || !playlist.value) return

  const target = e.target.closest('[data-item-id]')
  if (!target) return

  const targetId = target.dataset.itemId
  if (draggedId === targetId) return

  const ids = items.value.map((i) => i.id)
  const fromIdx = ids.indexOf(draggedId)
  const toIdx = ids.indexOf(targetId)
  if (fromIdx === -1 || toIdx === -1) return

  ids.splice(fromIdx, 1)
  ids.splice(toIdx, 0, draggedId)

  await api.post(`/playlists/${playlist.value.id}/reorder`, { item_ids: ids })
  await loadPlaylist()
}

// Watch for route param changes (navigating between playlists)
watch(playlistId, () => {
  playlist.value = null
  items.value = []
  loadPlaylist()
})

onMounted(async () => {
  await Promise.all([loadPlaylist(), loadAssets(), loadAllPlaylists()])
})
</script>

<style scoped>
h3 { margin-bottom: 0.8rem; color: #ddd; font-size: 1rem; }

.loading { color: #888; }

.page-header {
  margin-bottom: 1.2rem;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.breadcrumb-link {
  color: #7c83ff;
  text-decoration: none;
  font-size: 1.1rem;
  font-weight: 600;
}

.breadcrumb-link:hover { text-decoration: underline; }

.breadcrumb-sep {
  color: #555;
  font-size: 0.8rem;
}

.breadcrumb-current {
  color: #fff;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.edit-hint {
  font-size: 0.7rem;
  color: #555;
}

.breadcrumb-edit {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.breadcrumb-edit input {
  background: #0f1117;
  border: 1px solid #7c83ff;
  color: #eee;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  outline: none;
  font-size: 1rem;
}

.btn-sm {
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.3rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-sm.secondary { background: #3a3a5a; }

.playlist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.6rem 0.75rem;
  background: #1a1d27;
  border-radius: 6px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.default-badge {
  background: #252836;
  color: #7c83ff;
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mode-badge {
  background: #2d2545;
  color: #a78bfa;
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.item-count { color: #888; font-size: 0.85rem; }

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.hash-label { color: #555; font-size: 0.75rem; font-family: monospace; }

.btn-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #252836;
  color: #999;
  border: none;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: color 0.15s, background 0.15s;
}

.btn-toggle:hover { color: #fff; background: #2f3348; }
.toggle-arrow { font-size: 0.65rem; }

.btn-mode {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #2d2545;
  color: #a78bfa;
  border: none;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: color 0.15s, background 0.15s;
}

.btn-mode:hover { color: #c4b5fd; background: #3d3560; }

.btn-mode.simplify {
  background: #252836;
  color: #999;
}

.btn-mode.simplify:hover { color: #fff; background: #2f3348; }

/* Per-playlist settings */
.settings-panel {
  background: #1a1d27;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
  border: 1px solid #2a2d3a;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

.setting-field label {
  display: block;
  font-size: 0.75rem;
  color: #888;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-select,
.setting-number {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  outline: none;
  font-size: 0.85rem;
}

.setting-select:focus,
.setting-number:focus { border-color: #7c83ff; }

.number-input-row {
  display: flex;
  gap: 0.3rem;
  align-items: center;
}

.number-input-row .setting-number { flex: 1; }

.btn-clear {
  background: #3a3a5a;
  color: #aaa;
  border: none;
  width: 24px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-clear:hover { color: #fff; background: #555; }

.settings-hint {
  color: #666;
  font-size: 0.75rem;
  margin-top: 0.75rem;
}

.playlist-items {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 2rem;
  min-height: 60px;
}

.empty, .empty-hint {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.add-section {
  border-top: 1px solid #2a2d3a;
  padding-top: 1.5rem;
}

.add-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}

.add-card {
  background: #1a1d27;
  border-radius: 6px;
  cursor: pointer;
  overflow: hidden;
  transition: box-shadow 0.15s;
}

.add-card:hover {
  box-shadow: 0 0 0 1px #7c83ff;
}

.add-thumb {
  aspect-ratio: 16 / 9;
  background: #0f1117;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.add-hover-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(124, 131, 255, 0.15);
  opacity: 0;
  transition: opacity 0.15s;
  pointer-events: none;
}

.add-hover-overlay i {
  font-size: 1.75rem;
  color: #7c83ff;
  filter: drop-shadow(0 1px 4px rgba(0, 0, 0, 0.5));
}

.add-card:hover .add-hover-overlay {
  opacity: 1;
}

.add-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.add-icon { font-size: 1.5rem; color: #444; }

.add-name {
  padding: 0.4rem 0.5rem;
  font-size: 0.8rem;
  color: #ccc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Trigger panel */
.trigger-panel {
  background: #1a1d27;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
  border: 1px solid #2d2545;
}

.trigger-panel-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #a78bfa;
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.75rem;
}

.trigger-toggle-icon {
  margin-left: auto;
  font-size: 0.75rem;
  opacity: 0.6;
}

.trigger-hint {
  margin-top: 0.5rem;
}

.trigger-placeholder {
  color: #666;
  font-size: 0.85rem;
  text-align: center;
  padding: 1.5rem 0;
}

/* Preset selector */
.preset-section {
  margin-bottom: 0.75rem;
}

.preset-intro {
  color: #666;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.5rem;
}

.preset-card {
  background: #0f1117;
  border: 1px solid #2a2d3a;
  border-radius: 6px;
  padding: 0.75rem;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.preset-card:hover {
  border-color: #a78bfa;
  box-shadow: 0 0 0 1px #a78bfa33;
}

.preset-icon {
  color: #a78bfa;
  font-size: 1.2rem;
  margin-bottom: 0.4rem;
  display: block;
}

.preset-name {
  color: #ddd;
  font-size: 0.82rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
}

.preset-desc {
  color: #666;
  font-size: 0.7rem;
  line-height: 1.4;
}

/* Flow selector */
.flow-selector {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.flow-select {
  flex: 1;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  outline: none;
  font-size: 0.85rem;
}

.flow-select:focus { border-color: #a78bfa; }

.btn-flow {
  background: #2d2545;
  color: #a78bfa;
  border: none;
  width: 30px;
  height: 30px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  transition: background 0.15s;
}

.btn-flow:hover { background: #3d3560; }
.btn-flow.detach { color: #999; background: #252836; }
.btn-flow.detach:hover { color: #fff; background: #3a3a5a; }

.inline-form {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.inline-form input { flex: 1; }

/* Branch list */
.branch-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.75rem;
}

.branch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #0f1117;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  border: 1px solid #2a2d3a;
}

.branch-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.branch-playlist {
  color: #ccc;
  font-size: 0.82rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.branch-trigger-icon {
  color: #a78bfa;
  font-size: 0.85rem;
}

.branch-type-label {
  color: #888;
  font-size: 0.75rem;
  white-space: nowrap;
}

.branch-arrow {
  color: #555;
  font-size: 0.7rem;
}

.branch-priority {
  color: #666;
  font-size: 0.65rem;
  background: #252836;
  padding: 1px 5px;
  border-radius: 3px;
}

.branch-actions {
  display: flex;
  gap: 0.3rem;
  margin-left: 0.5rem;
}

.btn-icon {
  background: transparent;
  border: none;
  color: #666;
  cursor: pointer;
  padding: 0.2rem;
  border-radius: 3px;
  font-size: 0.8rem;
  transition: color 0.15s;
}

.btn-icon:hover { color: #a78bfa; }
.btn-icon.danger:hover { color: #dc3545; }

.btn-add-branch {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #2d2545;
  color: #a78bfa;
  border: none;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.15s;
}

.btn-add-branch:hover { background: #3d3560; }

/* Branch form */
.branch-form {
  background: #0f1117;
  border-radius: 6px;
  padding: 1rem;
  margin-top: 0.75rem;
  border: 1px solid #2a2d3a;
}

.branch-form h4 {
  color: #a78bfa;
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
}

.branch-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.trigger-config-section {
  margin-bottom: 0.75rem;
}

.config-label {
  display: block;
  font-size: 0.7rem;
  color: #a78bfa;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.75rem;
}

.modifier-checks {
  display: flex;
  gap: 0.75rem;
}

.check-label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: #aaa;
  font-size: 0.8rem;
  cursor: pointer;
}

.check-label input[type="checkbox"] {
  accent-color: #a78bfa;
}

.webhook-token-row {
  display: flex;
  gap: 0.3rem;
  align-items: center;
}

.webhook-token-row input { flex: 1; }

.config-hint {
  color: #555;
  font-size: 0.7rem;
  margin-top: 0.25rem;
  display: block;
}

.branch-form-actions {
  display: flex;
  gap: 0.4rem;
}

/* Simplify confirmation dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: #1a1d27;
  border-radius: 10px;
  padding: 1.5rem;
  width: 380px;
  max-width: 90vw;
  border: 1px solid #2a2d3a;
}

.dialog h3 {
  color: #fff;
  margin-bottom: 1rem;
}

.dialog p {
  color: #aaa;
  font-size: 0.9rem;
  margin-bottom: 1rem;
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn-danger {
  background: #dc3545;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-danger:hover { background: #c82333; }

.btn-secondary {
  background: #3a3a5a;
  color: #ccc;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

</style>
