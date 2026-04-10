/**
 * Trigger flow preset templates.
 * Client-side only — these are JSON blueprints that pre-populate the branch form.
 * User still selects source/target playlists manually.
 */

export const TRIGGER_PRESETS = [
  {
    id: 'museum-button',
    name: 'Museum Button',
    icon: 'pi pi-microchip',
    description: 'Idle loop with GPIO buttons branching to exhibit playlists. Each button triggers a different exhibit, with timeout return to idle.',
    branches: [
      {
        trigger_type: 'gpio',
        trigger_config: { pin: 17, edge: 'falling' },
        label: 'Button → Exhibit',
      },
    ],
    return_branch: {
      trigger_type: 'timeout',
      trigger_config: { seconds: 30 },
      label: 'Return to idle after 30s',
    },
  },
  {
    id: 'kiosk-touch',
    name: 'Kiosk Touch',
    icon: 'pi pi-th-large',
    description: 'Welcome screen with touch zones branching to content playlists. Timeout returns to welcome.',
    branches: [
      {
        trigger_type: 'touch_zone',
        trigger_config: { x_percent: 10, y_percent: 60, width_percent: 35, height_percent: 30 },
        label: 'Left zone → Content A',
      },
      {
        trigger_type: 'touch_zone',
        trigger_config: { x_percent: 55, y_percent: 60, width_percent: 35, height_percent: 30 },
        label: 'Right zone → Content B',
      },
    ],
    return_branch: {
      trigger_type: 'timeout',
      trigger_config: { seconds: 60 },
      label: 'Return to welcome after 60s',
    },
  },
  {
    id: 'wayfinding',
    name: 'Wayfinding',
    icon: 'pi pi-map',
    description: 'Directory screen with 3 touch zones for destinations. Timeout returns to directory.',
    branches: [
      {
        trigger_type: 'touch_zone',
        trigger_config: { x_percent: 5, y_percent: 30, width_percent: 28, height_percent: 50 },
        label: 'Zone 1 → Destination A',
      },
      {
        trigger_type: 'touch_zone',
        trigger_config: { x_percent: 36, y_percent: 30, width_percent: 28, height_percent: 50 },
        label: 'Zone 2 → Destination B',
      },
      {
        trigger_type: 'touch_zone',
        trigger_config: { x_percent: 67, y_percent: 30, width_percent: 28, height_percent: 50 },
        label: 'Zone 3 → Destination C',
      },
    ],
    return_branch: {
      trigger_type: 'timeout',
      trigger_config: { seconds: 45 },
      label: 'Return to directory after 45s',
    },
  },
  {
    id: 'emergency-alert',
    name: 'Emergency Alert',
    icon: 'pi pi-exclamation-triangle',
    description: 'Normal content interrupted by webhook-triggered emergency playlist. No automatic return — requires manual reset.',
    branches: [
      {
        trigger_type: 'webhook',
        trigger_config: {},
        label: 'Webhook → Emergency playlist',
      },
    ],
    return_branch: null,
  },
  {
    id: 'arcade-joystick',
    name: 'Arcade Joystick',
    icon: 'pi pi-sliders-h',
    description: 'Idle screen with joystick/gamepad buttons branching to content playlists. Timeout returns to idle.',
    branches: [
      {
        trigger_type: 'joystick',
        trigger_config: { input: 'button', button: 288, value: 1, device: null },
        label: 'Button 1 → Content A',
      },
      {
        trigger_type: 'joystick',
        trigger_config: { input: 'button', button: 289, value: 1, device: null },
        label: 'Button 2 → Content B',
      },
    ],
    return_branch: {
      trigger_type: 'timeout',
      trigger_config: { seconds: 30 },
      label: 'Return to idle after 30s',
    },
  },
  {
    id: 'scheduled-interrupt',
    name: 'Scheduled Interrupt',
    icon: 'pi pi-clock',
    description: 'Normal content with timeout-triggered interrupt playlist. Returns to normal after a set number of loops.',
    branches: [
      {
        trigger_type: 'timeout',
        trigger_config: { seconds: 300 },
        label: 'After 5min → Interrupt playlist',
      },
    ],
    return_branch: {
      trigger_type: 'loop_count',
      trigger_config: { count: 2 },
      label: 'Return after 2 loops',
    },
  },
]
