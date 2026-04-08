// Designer starter templates — pre-built design_source blobs ready to load into the canvas.
// Each template is the same shape as Asset.design_source: { canvas, elements }.
// Positions and sizes are percentages of the 1920×1080 canvas; font sizes are px @ 1080p.

export const DESIGNER_TEMPLATES = [
  {
    id: 'announce',
    name: 'Announcement',
    description: 'Bold heading with supporting subtitle on a deep blue background.',
    icon: 'pi pi-megaphone',
    design: {
      version: 1,
      canvas: { background: '#0f2744' },
      elements: [
        {
          id: 'el-1',
          type: 'text',
          x: 4, y: 26, w: 92, h: 26, opacity: 1,
          props: {
            text: 'IMPORTANT ANNOUNCEMENT',
            fontSize: 56,
            color: '#ffffff',
            fontWeight: 700,
            align: 'center',
            fontFamily: 'sans-serif',
          },
        },
        {
          id: 'el-2',
          type: 'text',
          x: 8, y: 58, w: 84, h: 18, opacity: 1,
          props: {
            text: 'Your message details appear here',
            fontSize: 32,
            color: '#cfd8e6',
            fontWeight: 300,
            align: 'center',
            fontFamily: 'sans-serif',
          },
        },
      ],
    },
  },
  {
    id: 'event',
    name: 'Event Promo',
    description: 'Tonight-style event headline with accent divider.',
    icon: 'pi pi-calendar',
    design: {
      version: 1,
      canvas: { background: '#1a2a1a' },
      elements: [
        {
          id: 'el-1',
          type: 'shape',
          x: 8, y: 28, w: 84, h: 0.8, opacity: 1,
          props: { shape: 'divider', fill: '#34d399', borderRadius: 0 },
        },
        {
          id: 'el-2',
          type: 'text',
          x: 8, y: 32, w: 84, h: 22, opacity: 1,
          props: {
            text: 'Tonight @ 7PM',
            fontSize: 96,
            color: '#ffffff',
            fontWeight: 700,
            align: 'center',
            fontFamily: 'sans-serif',
          },
        },
        {
          id: 'el-3',
          type: 'text',
          x: 8, y: 58, w: 84, h: 12, opacity: 1,
          props: {
            text: 'Main Stage · All Are Welcome',
            fontSize: 52,
            color: '#a7f3c5',
            fontWeight: 400,
            align: 'center',
            fontFamily: 'sans-serif',
          },
        },
      ],
    },
  },
  {
    id: 'clock',
    name: 'Digital Clock',
    description: 'Minimal full-screen live clock.',
    icon: 'pi pi-clock',
    design: {
      version: 1,
      canvas: { background: '#060608' },
      elements: [
        {
          id: 'el-1',
          type: 'widget',
          x: 15, y: 30, w: 70, h: 40, opacity: 1,
          props: {
            widgetId: 'clock',
            params: {
              FORMAT_24H: false,
              SHOW_SECONDS: true,
              TIMEZONE: '',
              FONT_SIZE: '20vmin',
              COLOR: '#ffffff',
            },
          },
        },
      ],
    },
  },
  {
    id: 'lowerthird',
    name: 'Lower Third',
    description: 'Speaker name and title in a colored bar near the bottom.',
    icon: 'pi pi-id-card',
    design: {
      version: 1,
      canvas: { background: '#222222' },
      elements: [
        {
          id: 'el-1',
          type: 'shape',
          x: 0, y: 78, w: 52, h: 18, opacity: 0.92,
          props: { shape: 'rect', fill: '#6c74ff', borderRadius: 0 },
        },
        {
          id: 'el-2',
          type: 'text',
          x: 2, y: 80, w: 48, h: 8, opacity: 1,
          props: {
            text: 'Speaker Name',
            fontSize: 48,
            color: '#ffffff',
            fontWeight: 700,
            align: 'left',
            fontFamily: 'sans-serif',
          },
        },
        {
          id: 'el-3',
          type: 'text',
          x: 2, y: 88, w: 48, h: 6, opacity: 1,
          props: {
            text: 'Title / Organization',
            fontSize: 30,
            color: '#e0e0ff',
            fontWeight: 300,
            align: 'left',
            fontFamily: 'sans-serif',
          },
        },
      ],
    },
  },
  {
    id: 'welcome',
    name: 'Welcome Screen',
    description: 'Eyebrow + big headline on a purple gradient look.',
    icon: 'pi pi-star',
    design: {
      version: 1,
      canvas: { background: '#1a0a2e' },
      elements: [
        {
          id: 'el-1',
          type: 'text',
          x: 10, y: 32, w: 80, h: 8, opacity: 1,
          props: {
            text: 'WELCOME TO',
            fontSize: 48,
            color: '#a78bfa',
            fontWeight: 400,
            align: 'center',
            fontFamily: 'sans-serif',
          },
        },
        {
          id: 'el-2',
          type: 'text',
          x: 6, y: 42, w: 88, h: 24, opacity: 1,
          props: {
            text: 'The Event Name',
            fontSize: 104,
            color: '#ffffff',
            fontWeight: 700,
            align: 'center',
            fontFamily: 'sans-serif',
          },
        },
      ],
    },
  },
]
