/**
 * Motion graphics template library — dynamic loader.
 *
 * Usage:
 *   import { loadTemplate, listTemplates, loadLottie } from '../motion/library'
 *
 *   const Comp = await loadTemplate('magic-ui', 'sparkles-text')
 *   const json = await loadLottie('rocket_launch')
 *
 * All templates are vendored locally (see catalog.json) and loaded via
 * Vite's dynamic import glob so no runtime fetches leave the machine.
 */

import catalog from './catalog.json'

// Vite eager-glob maps every vendored component file to a module loader.
// (These are lazy by default — only the ones we actually call get bundled.)
const MAGIC_UI = import.meta.glob('./magic-ui/*.tsx')
const MOTION_PRIMITIVES = import.meta.glob('./motion-primitives/*.tsx')
const REACT_BITS = import.meta.glob('./react-bits/*/*.jsx')
const LOTTIES = import.meta.glob('./lotties/*.json')

export { catalog }

/**
 * Return a flat list of every template with { library, name, category? }.
 */
export function listTemplates() {
  const out = []
  for (const name of catalog.libraries['magic-ui'].components) {
    out.push({ library: 'magic-ui', name })
  }
  for (const name of catalog.libraries['motion-primitives'].components) {
    out.push({ library: 'motion-primitives', name })
  }
  const rb = catalog.libraries['react-bits'].categories
  for (const [category, names] of Object.entries(rb)) {
    for (const name of names) {
      out.push({ library: 'react-bits', category, name })
    }
  }
  for (const name of catalog.libraries.lotties.assets) {
    out.push({ library: 'lotties', name })
  }
  return out
}

/**
 * Dynamically load a template component by library + name.
 * Returns the component's default export (a React component).
 */
export async function loadTemplate(library, name, category) {
  if (library === 'magic-ui') {
    const mod = await MAGIC_UI[`./magic-ui/${name}.tsx`]?.()
    return mod?.default ?? mod
  }
  if (library === 'motion-primitives') {
    const mod = await MOTION_PRIMITIVES[`./motion-primitives/${name}.tsx`]?.()
    return mod?.default ?? mod
  }
  if (library === 'react-bits') {
    const mod = await REACT_BITS[`./react-bits/${category}/${name}.jsx`]?.()
    return mod?.default ?? mod
  }
  throw new Error(`Unknown library: ${library}`)
}

/**
 * Load a Lottie JSON by asset name (without extension).
 */
export async function loadLottie(name) {
  const mod = await LOTTIES[`./lotties/${name}.json`]?.()
  return mod?.default ?? mod
}

export default { listTemplates, loadTemplate, loadLottie, catalog }
