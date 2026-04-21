// Bundled WOFF2 font registry — curated SIL OFL fonts for digital signage.
// Font files live in app/static/fonts/ and are served at /static/fonts/.

export const FONT_FAMILIES = [
  // ── Generic (system) fonts ──────────────────────────────
  { value: 'sans-serif',  label: 'Sans-serif (system)', generic: true },
  { value: 'serif',       label: 'Serif (system)',      generic: true },
  { value: 'monospace',   label: 'Monospace (system)',   generic: true },

  // ── Bundled fonts ───────────────────────────────────────
  {
    value: "'Roboto', sans-serif",
    label: 'Roboto',
    generic: false,
    faces: [
      { weight: 400, file: 'roboto.woff2' },
      { weight: 700, file: 'roboto.woff2' },
    ],
  },
  {
    value: "'Montserrat', sans-serif",
    label: 'Montserrat',
    generic: false,
    faces: [
      { weight: 400, file: 'montserrat.woff2' },
      { weight: 700, file: 'montserrat.woff2' },
    ],
  },
  {
    value: "'Lato', sans-serif",
    label: 'Lato',
    generic: false,
    faces: [
      { weight: 400, file: 'lato-400.woff2' },
      { weight: 700, file: 'lato-700.woff2' },
    ],
  },
  {
    value: "'Oswald', sans-serif",
    label: 'Oswald',
    generic: false,
    faces: [
      { weight: 400, file: 'oswald.woff2' },
      { weight: 700, file: 'oswald.woff2' },
    ],
  },
  {
    value: "'Playfair Display', serif",
    label: 'Playfair Display',
    generic: false,
    faces: [
      { weight: 400, file: 'playfairdisplay.woff2' },
      { weight: 700, file: 'playfairdisplay.woff2' },
    ],
  },
  {
    value: "'Merriweather', serif",
    label: 'Merriweather',
    generic: false,
    faces: [
      { weight: 400, file: 'merriweather.woff2' },
      { weight: 700, file: 'merriweather.woff2' },
    ],
  },
  {
    value: "'Bebas Neue', sans-serif",
    label: 'Bebas Neue',
    generic: false,
    faces: [
      { weight: 400, file: 'bebasneue.woff2' },
    ],
  },
  {
    value: "'Pacifico', cursive",
    label: 'Pacifico',
    generic: false,
    faces: [
      { weight: 400, file: 'pacifico.woff2' },
    ],
  },
]

/**
 * Generate @font-face CSS for all bundled fonts.
 * Used in the CMS designer to make every font available for preview.
 */
export function generateFontFaceCSS(basePath = '/static/fonts') {
  const rules = []
  const seen = new Set()
  for (const family of FONT_FAMILIES) {
    if (family.generic) continue
    const name = family.value.split("'")[1]
    for (const face of family.faces) {
      const key = `${name}-${face.weight}-${face.file}`
      if (seen.has(key)) continue
      seen.add(key)
      rules.push(
        `@font-face{font-family:'${name}';font-weight:${face.weight};font-display:swap;src:url('${basePath}/${face.file}') format('woff2');}`
      )
    }
  }
  return rules.join('\n')
}

/**
 * Generate @font-face CSS only for fonts actually used in the given elements.
 * Keeps rendered HTML blobs small — only the fonts the design references get embedded.
 */
export function generateUsedFontFaceCSS(elements, basePath = '/static/fonts') {
  const usedValues = new Set()
  for (const el of elements) {
    if (el.props && el.props.fontFamily) {
      usedValues.add(el.props.fontFamily)
    }
  }

  const rules = []
  const seen = new Set()
  for (const family of FONT_FAMILIES) {
    if (family.generic || !usedValues.has(family.value)) continue
    const name = family.value.split("'")[1]
    for (const face of family.faces) {
      const key = `${name}-${face.weight}-${face.file}`
      if (seen.has(key)) continue
      seen.add(key)
      rules.push(
        `@font-face{font-family:'${name}';font-weight:${face.weight};font-display:swap;src:url('${basePath}/${face.file}') format('woff2');}`
      )
    }
  }
  return rules.join('\n')
}
