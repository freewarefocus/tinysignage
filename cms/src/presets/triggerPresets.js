/**
 * Trigger flow preset templates.
 * Each preset batch-creates all its branches when applied.
 */

export const TRIGGER_PRESETS = [
  {
    id: 'gpio-button',
    name: 'GPIO Button',
    icon: 'pi pi-microchip',
    description: 'A GPIO button press switches to another playlist. Timeout returns to this one.',
    summary: '1 GPIO branch + timeout return',
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
    description: 'Two touch zones on a welcome screen branch to different content. Timeout returns here.',
    summary: '2 touch zones + timeout return',
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
    description: 'Three touch zones for destinations on a directory screen. Timeout returns to directory.',
    summary: '3 touch zones + timeout return',
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
    description: 'A webhook call interrupts normal content with an emergency playlist. No automatic return.',
    summary: '1 webhook branch, no return',
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
    id: 'arcade-controller',
    name: 'Arcade Controller',
    icon: 'pi pi-sliders-h',
    description: 'Two gamepad buttons branch to different content playlists. Timeout returns to idle.',
    summary: '2 gamepad buttons + timeout return',
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
    id: 'timed-interrupt',
    name: 'Timed Interrupt',
    icon: 'pi pi-clock',
    description: 'After a timeout, switches to an interrupt playlist. Returns here after a set number of loops.',
    summary: '1 timeout branch + loop-count return',
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
