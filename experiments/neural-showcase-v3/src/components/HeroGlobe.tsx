import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { KernelSize } from "postprocessing";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";

/**
 * HeroGlobe — refined wireframe network globe.
 *
 * v2 design intent (premium restraint):
 *   - Single subtle wireframe sphere. No vertex-color rainbow.
 *   - Thinner lines, lower opacity → reads as a halo, not a focal object.
 *   - Two slow orbital rings that barely move.
 *   - Six (was sixteen) arcs flicker in/out gently — agent-to-agent
 *     handshakes, not Christmas lights.
 *   - Bloom only on the brightest pixels. No screen-wide glow.
 *
 * Designed to sit in the *background* of Hero, partially clipped at
 * the corner — supports the headline, never competes with it.
 */

interface ArcDef {
  curve: THREE.CubicBezierCurve3;
  speed: number;
  offset: number;
  color: THREE.Color;
}

const BRAND = {
  indigo: new THREE.Color("#6366F1"),
  violet: new THREE.Color("#8B5CF6"),
  cyan: new THREE.Color("#06B6D4"),
};

function randomPointOnSphere(r: number) {
  const u = Math.random();
  const v = Math.random();
  const theta = 2 * Math.PI * u;
  const phi = Math.acos(2 * v - 1);
  return new THREE.Vector3(
    r * Math.sin(phi) * Math.cos(theta),
    r * Math.sin(phi) * Math.sin(theta),
    r * Math.cos(phi),
  );
}

function makeArc(r: number, color: THREE.Color): ArcDef {
  const start = randomPointOnSphere(r);
  const end = randomPointOnSphere(r);
  const mid = start.clone().add(end).multiplyScalar(0.5).normalize().multiplyScalar(r * 1.35);
  return {
    curve: new THREE.CubicBezierCurve3(start, mid.clone(), mid.clone(), end),
    speed: 0.12 + Math.random() * 0.18,
    offset: Math.random() * Math.PI * 2,
    color,
  };
}

function GlobeWireframe() {
  const ref = useRef<THREE.Mesh>(null!);

  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.y += dt * 0.06;
  });

  return (
    <group>
      {/* Solid OLED inner sphere — keeps wireframe legible against bg */}
      <mesh>
        <sphereGeometry args={[1.55, 64, 64]} />
        <meshBasicMaterial color="#020208" />
      </mesh>
      {/* Wireframe shell — single muted indigo, low opacity */}
      <mesh ref={ref}>
        <icosahedronGeometry args={[1.6, 5]} />
        <meshBasicMaterial color="#6366F1" wireframe transparent opacity={0.22} />
      </mesh>
      {/* Soft halo — single back-side mesh, violet */}
      <mesh scale={1.04}>
        <sphereGeometry args={[1.6, 64, 64]} />
        <meshBasicMaterial
          color="#8B5CF6"
          transparent
          opacity={0.05}
          side={THREE.BackSide}
        />
      </mesh>
    </group>
  );
}

function OrbitRings() {
  const a = useRef<THREE.Mesh>(null!);
  const b = useRef<THREE.Mesh>(null!);
  useFrame((_, dt) => {
    if (a.current) a.current.rotation.z += dt * 0.025;
    if (b.current) b.current.rotation.z -= dt * 0.018;
  });
  return (
    <group>
      <mesh ref={a} rotation={[Math.PI / 2.2, 0, 0]}>
        <ringGeometry args={[2.05, 2.058, 128]} />
        <meshBasicMaterial color="#06B6D4" transparent opacity={0.18} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={b} rotation={[Math.PI / 2.6, 0.4, 0]}>
        <ringGeometry args={[2.45, 2.456, 128]} />
        <meshBasicMaterial color="#8B5CF6" transparent opacity={0.12} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

function Arc({ arc }: { arc: ArcDef }) {
  const ref = useRef<THREE.Line>(null!);
  const head = useRef<THREE.Mesh>(null!);
  const points = useMemo(() => arc.curve.getPoints(48), [arc]);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  useFrame(({ clock }) => {
    const t = (clock.getElapsedTime() * arc.speed + arc.offset) % (Math.PI * 2);
    const pulse = (Math.sin(t) + 1) / 2; // 0..1
    if (ref.current) {
      const mat = ref.current.material as THREE.LineBasicMaterial;
      mat.opacity = 0.05 + pulse * 0.3;
    }
    if (head.current) {
      const tt = (clock.getElapsedTime() * arc.speed * 0.4 + arc.offset / 6) % 1;
      const p = arc.curve.getPoint(tt);
      head.current.position.copy(p);
      const mat = head.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.4 + pulse * 0.5;
    }
  });

  return (
    <group>
      <line ref={ref as any}>
        <primitive object={geometry} attach="geometry" />
        <lineBasicMaterial color={arc.color} transparent opacity={0.18} />
      </line>
      <mesh ref={head}>
        <sphereGeometry args={[0.022, 12, 12]} />
        <meshBasicMaterial color={arc.color} transparent opacity={0.6} />
      </mesh>
    </group>
  );
}

function ArcField() {
  const arcs = useMemo(() => {
    // Six arcs total — two per brand colour, well-spaced
    const palette = [BRAND.indigo, BRAND.violet, BRAND.cyan];
    return Array.from({ length: 6 }, (_, i) => makeArc(1.62, palette[i % 3]));
  }, []);
  return (
    <>
      {arcs.map((a, i) => (
        <Arc key={i} arc={a} />
      ))}
    </>
  );
}

export function HeroGlobe({ className }: { className?: string }) {
  return (
    <div className={`pointer-events-none ${className ?? ""}`}>
      <Canvas
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true }}
        camera={{ position: [0, 0.2, 5.6], fov: 36 }}
        style={{ position: "absolute", inset: 0 }}
      >
        <ambientLight intensity={0.25} />
        <pointLight position={[3, 3, 5]} intensity={0.6} color="#6366F1" />
        <pointLight position={[-3, -2, -3]} intensity={0.35} color="#06B6D4" />

        <Suspense fallback={null}>
          <Float speed={0.4} rotationIntensity={0.12} floatIntensity={0.25}>
            <GlobeWireframe />
            <OrbitRings />
          </Float>
          <ArcField />
        </Suspense>

        <EffectComposer multisampling={0} enableNormalPass={false}>
          <Bloom
            intensity={0.32}
            luminanceThreshold={0.55}
            luminanceSmoothing={0.4}
            kernelSize={KernelSize.SMALL}
          />
        </EffectComposer>
      </Canvas>
    </div>
  );
}
