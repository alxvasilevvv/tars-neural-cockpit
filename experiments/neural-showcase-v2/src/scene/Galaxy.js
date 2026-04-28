import * as THREE from "three";
import { galaxyVert, galaxyFrag } from "./shaders/galaxy.glsl.js";

/**
 * Galaxy = atmospheric dust + structured orbital rings.
 *
 * Two tilted rings give the scene a "Saturn / Bohr atom" silhouette around
 * the core. Atmospheric dust fills the negative space without competing
 * with the core for attention. Nothing here is random snow.
 */

const RINGS = [
  { r: 2.7, tilt: 0.12, twist: 0.0, count: 1100, color: "#e7eef7", thickness: 0.06, speed: 0.05 },
  { r: 3.4, tilt: Math.PI / 3.2, twist: Math.PI / 6, count: 700, color: "#e6c97a", thickness: 0.04, speed: -0.04 },
];

const DUST_COUNT_DEFAULT = 1400;
const DUST_RADIUS = 7.0;
const DUST_INNER = 2.1;

function generateRing(def, sizes, phases, speeds, positions, colors, attrSize, offset) {
  const m = new THREE.Matrix4().makeRotationFromEuler(
    new THREE.Euler(def.tilt, def.twist, 0),
  );
  const v = new THREE.Vector3();
  const c = new THREE.Color(def.color);
  for (let i = 0; i < def.count; i++) {
    const theta = Math.random() * Math.PI * 2;
    const t = (Math.random() - 0.5) * 2;
    const localR = def.r + t * def.thickness;
    const yJ = (Math.random() - 0.5) * def.thickness * 0.6;
    v.set(Math.cos(theta) * localR, yJ, Math.sin(theta) * localR);
    v.applyMatrix4(m);
    const idx = (offset + i) * 3;
    positions[idx + 0] = v.x;
    positions[idx + 1] = v.y;
    positions[idx + 2] = v.z;
    colors[idx + 0] = c.r;
    colors[idx + 1] = c.g;
    colors[idx + 2] = c.b;
    sizes[offset + i] = 0.32 + Math.random() * 0.28;
    phases[offset + i] = Math.random() * Math.PI * 2;
    speeds[offset + i] = def.speed * (0.85 + Math.random() * 0.3);
    attrSize[offset + i] = sizes[offset + i];
  }
}

function generateDust(count, sizes, phases, speeds, positions, colors, attrSize, offset) {
  const main = new THREE.Color("#c4cfde");
  const accent = new THREE.Color("#e6c97a");
  for (let i = 0; i < count; i++) {
    let x, y, z, d;
    do {
      x = (Math.random() * 2 - 1) * DUST_RADIUS;
      y = (Math.random() * 2 - 1) * DUST_RADIUS;
      z = (Math.random() * 2 - 1) * DUST_RADIUS;
      d = Math.sqrt(x * x + y * y + z * z);
    } while (d < DUST_INNER || d > DUST_RADIUS);
    const idx = (offset + i) * 3;
    positions[idx + 0] = x;
    positions[idx + 1] = y;
    positions[idx + 2] = z;
    const useAccent = Math.random() < 0.06;
    const c = useAccent ? accent : main;
    const tone = 0.55 + Math.random() * 0.45;
    colors[idx + 0] = c.r * tone;
    colors[idx + 1] = c.g * tone;
    colors[idx + 2] = c.b * tone;
    sizes[offset + i] = 0.16 + Math.random() * 0.22;
    phases[offset + i] = Math.random() * Math.PI * 2;
    speeds[offset + i] = 0.04 + Math.random() * 0.08;
    attrSize[offset + i] = sizes[offset + i];
  }
}

export class Galaxy {
  constructor({ pixelRatio = 1, dustCount = DUST_COUNT_DEFAULT } = {}) {
    const ringTotal = RINGS.reduce((s, r) => s + r.count, 0);
    const total = ringTotal + dustCount;

    const positions = new Float32Array(total * 3);
    const colors = new Float32Array(total * 3);
    const sizes = new Float32Array(total);
    const attrSize = new Float32Array(total);
    const phases = new Float32Array(total);
    const speeds = new Float32Array(total);

    let offset = 0;
    for (const def of RINGS) {
      generateRing(def, sizes, phases, speeds, positions, colors, attrSize, offset);
      offset += def.count;
    }
    generateDust(dustCount, sizes, phases, speeds, positions, colors, attrSize, offset);

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
    geom.setAttribute("aSize", new THREE.BufferAttribute(attrSize, 1));
    geom.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
    geom.setAttribute("aSpeed", new THREE.BufferAttribute(speeds, 1));
    geom.computeBoundingSphere();

    this.material = new THREE.ShaderMaterial({
      vertexShader: galaxyVert,
      fragmentShader: galaxyFrag,
      uniforms: {
        uTime: { value: 0 },
        uPixelRatio: { value: pixelRatio },
        uScrollProgress: { value: 0 },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    this.points = new THREE.Points(geom, this.material);
    this.points.frustumCulled = false;

    this.connections = null;
  }

  update(time, scrollProgress) {
    this.material.uniforms.uTime.value = time;
    this.material.uniforms.uScrollProgress.value = scrollProgress;
  }

  setPixelRatio(pr) {
    this.material.uniforms.uPixelRatio.value = pr;
  }
}
