import "./style.css";
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";

import { Galaxy } from "./scene/Galaxy.js";
import { Core } from "./scene/Core.js";
import { createComposer } from "./scene/Composer.js";

import { initCursor } from "./ui/Cursor.js";
import { runLoader, runIntro } from "./ui/Loader.js";
import { initReveals, initCounters } from "./ui/Reveal.js";
import { initHUD } from "./ui/HUD.js";

gsap.registerPlugin(ScrollTrigger);

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const canvas = document.querySelector("canvas.stage");
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: false,
  alpha: false,
  powerPreference: "high-performance",
});
renderer.setClearColor(0x04060d, 1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.92;

const dpr = Math.min(window.devicePixelRatio || 1, 2);
renderer.setPixelRatio(dpr);
renderer.setSize(innerWidth, innerHeight, false);

const pmrem = new THREE.PMREMGenerator(renderer);
const envTexture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const scene = new THREE.Scene();
scene.environment = envTexture;
scene.fog = new THREE.FogExp2(0x04060d, 0.04);

const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 0.1, 100);
camera.position.set(0, 0.55, 9.0);

const galaxy = new Galaxy({
  dustCount: matchMedia("(max-width: 640px)").matches ? 700 : 1400,
  pixelRatio: dpr,
});
scene.add(galaxy.points);
if (galaxy.connections) scene.add(galaxy.connections);

const core = new Core({ envMap: envTexture });
scene.add(core.group);
core.loadGLB("models/brain.glb").catch(() => {});

const { composer } = createComposer(renderer, scene, camera);
composer.setSize(innerWidth, innerHeight);

const pointer = new THREE.Vector2(0, 0);
const targetRot = new THREE.Vector2(0, 0);
let hover = 0;

addEventListener(
  "pointermove",
  (e) => {
    pointer.x = (e.clientX / innerWidth) * 2 - 1;
    pointer.y = -((e.clientY / innerHeight) * 2 - 1);
    targetRot.x = pointer.y * 0.18;
    targetRot.y = pointer.x * 0.32;
  },
  { passive: true },
);

addEventListener("pointerdown", () => (hover = 1));
addEventListener("pointerup", () => (hover = 0));

addEventListener(
  "resize",
  () => {
    renderer.setSize(innerWidth, innerHeight, false);
    composer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  },
  { passive: true },
);

const lenis = new Lenis({
  duration: 1.2,
  easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
  smoothWheel: true,
});
lenis.on("scroll", ScrollTrigger.update);
gsap.ticker.add((time) => lenis.raf(time * 1000));
gsap.ticker.lagSmoothing(0);

let scrollProgress = 0;
lenis.on("scroll", ({ scroll, limit }) => {
  scrollProgress = limit > 0 ? scroll / limit : 0;
});

const camTarget = { z: 9.0, x: 0, y: 0.55 };
ScrollTrigger.create({
  trigger: ".layers",
  start: "top center",
  end: "bottom center",
  onUpdate(self) {
    const p = self.progress;
    camTarget.z = gsap.utils.interpolate(9.0, 7.4, p);
    camTarget.x = gsap.utils.interpolate(0, -0.55, p);
    camTarget.y = gsap.utils.interpolate(0.55, 0.2, p);
  },
});
ScrollTrigger.create({
  trigger: ".how",
  start: "top center",
  end: "bottom bottom",
  onUpdate(self) {
    const p = self.progress;
    camTarget.z = gsap.utils.interpolate(7.4, 8.4, p);
    camTarget.x = gsap.utils.interpolate(-0.55, 0.4, p);
    camTarget.y = gsap.utils.interpolate(0.2, -0.1, p);
  },
});
ScrollTrigger.create({
  trigger: ".domains",
  start: "top center",
  end: "bottom center",
  onUpdate(self) {
    const p = self.progress;
    camTarget.z = gsap.utils.interpolate(8.4, 9.6, p);
    camTarget.x = gsap.utils.interpolate(0.4, 0, p);
    camTarget.y = gsap.utils.interpolate(-0.1, 0.3, p);
  },
});

const clock = new THREE.Clock();
let elapsed = 0;
let camRot = new THREE.Vector2(0, 0);

function tick() {
  const dt = Math.min(0.05, clock.getDelta());
  elapsed += dt;

  if (!reduceMotion) {
    camRot.x += (targetRot.x - camRot.x) * 0.05;
    camRot.y += (targetRot.y - camRot.y) * 0.05;
  }

  scene.rotation.x = camRot.x + Math.sin(elapsed * 0.1) * 0.03;
  scene.rotation.y = camRot.y + elapsed * 0.045;

  camera.position.x += (camTarget.x - camera.position.x) * 0.05;
  camera.position.y += (camTarget.y - camera.position.y) * 0.05;
  camera.position.z += (camTarget.z - camera.position.z) * 0.05;
  camera.lookAt(0, -0.1, 0);

  galaxy.update(elapsed, scrollProgress);
  core.update(elapsed, hover);

  composer.render(dt);
  requestAnimationFrame(tick);
}

initCursor();
initReveals();
initCounters();
initHUD();

requestAnimationFrame(tick);

runLoader({ minDuration: 1400 }).then(() => {
  runIntro();
});
