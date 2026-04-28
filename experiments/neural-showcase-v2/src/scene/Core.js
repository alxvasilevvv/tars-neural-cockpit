import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import {
  reactorVert,
  reactorFrag,
  ringVert,
  ringFrag,
} from "./shaders/core.glsl.js";

/**
 * Core = reactor + cage + two thin rings + ground glow disc.
 *
 * One clear focal sculpture. No floating monolith bars — they read as
 * unrelated debris. The cage and rings give silhouette and structure;
 * the ground glow grounds the object in space.
 */

const RING_DEFS = [
  { r: 1.55, t: 0.005, segments: 360, notches: 96, color: "#9ec3d4", tilt: 0.04, speed: 0.08, scan: 0.06 },
  { r: 2.05, t: 0.004, segments: 360, notches: 144, color: "#e6c97a", tilt: Math.PI / 3.2, speed: -0.06, scan: 0.05 },
];

export class Core {
  constructor({ envMap = null } = {}) {
    this.group = new THREE.Group();
    this.envMap = envMap;
    this._buildReactor();
    this._buildCage();
    this._buildRings();
    this._buildGround();
    this.gltfMesh = null;
  }

  _buildReactor() {
    const geom = new THREE.IcosahedronGeometry(0.62, 64);
    this.reactorMat = new THREE.ShaderMaterial({
      vertexShader: reactorVert,
      fragmentShader: reactorFrag,
      uniforms: {
        uTime: { value: 0 },
        uHover: { value: 0 },
        uColorA: { value: new THREE.Color("#1c3a5c") },
        uColorB: { value: new THREE.Color("#f2c779") },
      },
    });
    this.reactor = new THREE.Mesh(geom, this.reactorMat);
    this.group.add(this.reactor);

    // Soft inner halo — a slightly larger, additive-blended sphere.
    const haloGeom = new THREE.IcosahedronGeometry(0.78, 32);
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0x6f86a8,
      transparent: true,
      opacity: 0.07,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.halo = new THREE.Mesh(haloGeom, haloMat);
    this.group.add(this.halo);
  }

  _buildCage() {
    const baseGeom = new THREE.IcosahedronGeometry(1.35, 1);
    const edges = new THREE.EdgesGeometry(baseGeom, 1);
    const mat = new THREE.LineBasicMaterial({
      color: 0x7a92c4,
      transparent: true,
      opacity: 0.32,
    });
    this.cage = new THREE.LineSegments(edges, mat);
    this.group.add(this.cage);

    const innerGeom = new THREE.IcosahedronGeometry(1.0, 0);
    const innerEdges = new THREE.EdgesGeometry(innerGeom, 1);
    const innerMat = new THREE.LineBasicMaterial({
      color: 0xe6c97a,
      transparent: true,
      opacity: 0.18,
    });
    this.innerCage = new THREE.LineSegments(innerEdges, innerMat);
    this.group.add(this.innerCage);
  }

  _buildRings() {
    this.rings = [];
    for (const d of RING_DEFS) {
      const geom = new THREE.TorusGeometry(d.r, d.t, 6, d.segments);
      const mat = new THREE.ShaderMaterial({
        vertexShader: ringVert,
        fragmentShader: ringFrag,
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new THREE.Color(d.color) },
          uNotches: { value: d.notches },
          uScanSpeed: { value: d.scan },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const ring = new THREE.Mesh(geom, mat);
      ring.rotation.x = Math.PI / 2 + d.tilt;
      ring.rotation.y = d.tilt * 0.7;
      this.rings.push({ mesh: ring, mat, speed: d.speed });
      this.group.add(ring);
    }
  }

  _buildGround() {
    const geom = new THREE.CircleGeometry(5.5, 96);
    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uColor: { value: new THREE.Color("#9ec3d4") },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        varying vec2 vUv;
        uniform vec3 uColor;
        void main() {
          vec2 c = vUv - 0.5;
          float d = length(c) * 2.0;
          float ring = smoothstep(0.65, 0.5, d) * (1.0 - smoothstep(0.5, 0.42, d));
          float fade = smoothstep(1.0, 0.05, d);
          float alpha = ring * 0.55 + fade * 0.18;
          gl_FragColor = vec4(uColor, alpha * 0.55);
        }
      `,
    });
    this.ground = new THREE.Mesh(geom, mat);
    this.ground.rotation.x = -Math.PI / 2;
    this.ground.position.y = -2.6;
    this.group.add(this.ground);
  }

  async loadGLB(url) {
    return new Promise((resolve) => {
      const loader = new GLTFLoader();
      loader.load(
        url,
        (gltf) => {
          const obj = gltf.scene;
          const box = new THREE.Box3().setFromObject(obj);
          const sphere = new THREE.Sphere();
          box.getBoundingSphere(sphere);
          if (sphere.radius > 0) {
            const scale = 1.0 / sphere.radius;
            obj.scale.setScalar(scale);
            obj.position.copy(sphere.center).multiplyScalar(-scale);
          }
          obj.traverse((c) => {
            if (c.isMesh && c.material) {
              if (this.envMap) c.material.envMap = this.envMap;
              c.material.envMapIntensity = 1.1;
            }
          });
          this.gltfMesh = obj;
          this.group.add(obj);
          this.reactor.visible = false;
          this.halo.visible = false;
          resolve(true);
        },
        undefined,
        () => resolve(false),
      );
    });
  }

  update(time, hover) {
    this.reactorMat.uniforms.uTime.value = time;
    this.reactorMat.uniforms.uHover.value +=
      (hover - this.reactorMat.uniforms.uHover.value) * 0.06;

    this.reactor.rotation.y = time * 0.16;
    this.reactor.rotation.x = Math.sin(time * 0.12) * 0.06;

    this.halo.rotation.y = -time * 0.08;
    const haloScale = 1.0 + Math.sin(time * 0.6) * 0.025;
    this.halo.scale.setScalar(haloScale);

    this.cage.rotation.y = time * 0.05;
    this.cage.rotation.x = Math.sin(time * 0.07) * 0.06;
    this.innerCage.rotation.y = -time * 0.07;
    this.innerCage.rotation.z = Math.sin(time * 0.1) * 0.04;

    for (const r of this.rings) {
      r.mat.uniforms.uTime.value = time;
      r.mesh.rotation.z += r.speed * 0.014;
    }

    if (this.gltfMesh) {
      this.gltfMesh.rotation.y = time * 0.16;
    }
  }
}
