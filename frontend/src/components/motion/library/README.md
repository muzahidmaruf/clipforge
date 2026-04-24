# Motion Graphics Template Library

Vendored, offline-ready motion-graphics templates for ClipForge. The Gemma
director (backend) picks templates from `catalog.json`; the frontend loads
them on demand via `index.js`.

## What's inside

| Library           | License | Count | Type  | Source |
|-------------------|---------|-------|-------|--------|
| `magic-ui`        | MIT     | 56    | .tsx  | https://github.com/magicuidesign/magicui |
| `motion-primitives` | MIT   | 17    | .tsx  | https://github.com/ibelick/motion-primitives |
| `react-bits`      | MIT     | 130   | .jsx  | https://github.com/DavidHDev/react-bits |
| `lotties`         | Mixed\* | 21    | .json | LottieFiles free tier + airbnb/lottie-web test assets |

\* Each Lottie JSON is either CC-0 / LottieFiles free tier / from public
   open-source test suites. Check individual files before commercial use.

**Total: 224 templates.**

## Categories (React Bits)

- `text/` — text-specific animations (BlurText, SplitText, TextType, DecryptedText, …)
- `animations/` — effect primitives (ClickSpark, Crosshair, ElectricBorder, MetaBalls, …)
- `backgrounds/` — full-screen backgrounds (Aurora, Ballpit, GridMotion, Hyperspeed, …)
- `components/` — higher-level widgets (CardSwap, Carousel, Dock, Stepper, …)

## Regenerating the catalog

After adding/removing any file:

```
python frontend/src/components/motion/library/build_catalog.py
```

## Using a template in code

```js
import { loadTemplate, loadLottie } from './library'

// React components
const SparklesText = await loadTemplate('magic-ui', 'sparkles-text')
const BlurText     = await loadTemplate('react-bits', 'blur-text', 'text') // 3rd arg = category
const TextEffect   = await loadTemplate('motion-primitives', 'text-effect')

// Lottie JSON
const rocket = await loadLottie('rocket_launch')
```

## Adding more Lotties

Drop `.json` files in `lotties/` and re-run `build_catalog.py`. Use names
that describe content (e.g. `rocket_launch`, `confetti_burst`) — the director
prompt references assets by these names.

## Director integration

The backend reads `catalog.json` and injects a trimmed list of template names
into the Gemma prompt so it knows what's available. See
`backend/services/director.py` → `_load_library_catalog()`.
