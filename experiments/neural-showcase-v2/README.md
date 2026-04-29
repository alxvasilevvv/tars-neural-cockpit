# TARS · Neural Showcase v2

Active-Theory-flavored marketing surface for TARS. Built as an isolated experiment so it
does not collide with the dependency-free `frontend/` of the main project.

## Stack

- Vite (dev server + build)
- Three.js (WebGL2 renderer)
- Custom GLSL shaders (galaxy particles, brain core)
- postprocessing (bloom + chromatic aberration + vignette + film noise + SMAA)
- GSAP + ScrollTrigger (intro timeline, scroll-driven camera, reveals)
- Lenis (smooth scroll engine)

## Run

```bash
cd experiments/neural-showcase-v2
npm install
npm run dev      # http://127.0.0.1:5173
npm run build    # static output in dist/
npm run preview  # serve the built bundle
```

## Anatomy

- `src/main.js` — orchestrator. Boots the renderer, scene, composer, Lenis, and ScrollTrigger camera moves.
- `src/scene/Galaxy.js` — instanced Points with 6 cluster centers and per-vertex color/size/phase. Vertex shader does the swirl + breathing + scroll outward drift.
- `src/scene/Brain.js` — icosahedron core with simplex-noise vertex displacement and fresnel emissive frag. Plus a faint cyan torus ring.
- `src/scene/Composer.js` — postprocessing pipeline.
- `src/ui/Loader.js` — animated counter loader + intro timeline (word stagger).
- `src/ui/Cursor.js` — magnetic custom cursor with `[data-magnet]` hooks.
- `src/ui/Reveal.js` — ScrollTrigger reveals + counter animation.
- `index.html` — semantic structure (hero, layers, how, footer).
- `src/style.css` — design tokens + layout. Tokens mirror the main project palette.

## Notes

- This experiment intentionally adds dependencies. The main `frontend/` should remain dependency-free
  per `.cursorrules`. Only this folder owns its `node_modules/`.
- Respects `prefers-reduced-motion` for intro, reveals and camera drift.
- Mobile: simplified cursor (off), tighter padding, single-column cards.
