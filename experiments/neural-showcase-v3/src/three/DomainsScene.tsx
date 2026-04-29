import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Edges, Html, Sparkles, Environment } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { KernelSize } from "postprocessing";
import { Suspense, useRef } from "react";
import type { Group, Mesh } from "three";

interface PackNode {
  num: string;
  name: string;
  slug: string;
  color: string;
}

const NODES: PackNode[] = [
  { num: "01", name: "Traders",  slug: "traders",  color: "#6366F1" },
  { num: "02", name: "Business", slug: "business", color: "#8B5CF6" },
  { num: "03", name: "MLM",      slug: "mlm",      color: "#06B6D4" },
  { num: "04", name: "Science",  slug: "science",  color: "#A78BFA" },
];

function CenterCore() {
  const ref = useRef<Mesh>(null!);
  useFrame((_, d) => {
    if (ref.current) {
      ref.current.rotation.y += d * 0.3;
      ref.current.rotation.x += d * 0.18;
    }
  });
  return (
    <mesh ref={ref}>
      <icosahedronGeometry args={[0.7, 3]} />
      <meshStandardMaterial
        color="#6366F1"
        emissive="#6366F1"
        emissiveIntensity={0.55}
        roughness={0.28}
        metalness={0.6}
      />
      <Edges threshold={1} color="#06B6D4" />
    </mesh>
  );
}

function Orbit({ radius = 2.6 }: { radius?: number }) {
  return (
    <mesh rotation={[Math.PI / 2.4, 0, 0]}>
      <ringGeometry args={[radius - 0.005, radius + 0.005, 96]} />
      <meshBasicMaterial color="#06B6D4" transparent opacity={0.32} />
    </mesh>
  );
}

function Node({
  node,
  index,
  total,
  active,
  onActivate,
}: {
  node: PackNode;
  index: number;
  total: number;
  active: boolean;
  onActivate: (slug: string) => void;
}) {
  const ref = useRef<Group>(null!);
  const lineRef = useRef<any>(null);
  const ringRef = useRef<Mesh>(null!);
  const phase = (index / total) * Math.PI * 2;
  const radius = 2.6;

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * 0.18 + phase;
    const x = Math.cos(t) * radius;
    const z = Math.sin(t) * radius;
    const y = Math.sin(t * 1.2 + index) * 0.18;

    if (ref.current) {
      ref.current.position.set(x, y, z);
      ref.current.lookAt(0, 0, 0);
    }

    // Connection line — re-build geometry to (0,0,0) each frame
    if (lineRef.current) {
      const positions = lineRef.current.geometry.attributes.position;
      positions.setXYZ(0, 0, 0, 0);
      positions.setXYZ(1, x, y, z);
      positions.needsUpdate = true;
      const mat = lineRef.current.material as any;
      mat.opacity = active ? 0.65 : 0.18;
    }

    // Hover ripple ring on active
    if (ringRef.current) {
      const tt = clock.getElapsedTime();
      const pulse = active ? 1 + Math.sin(tt * 3.4) * 0.08 : 1;
      ringRef.current.scale.set(pulse, pulse, pulse);
      const mat = ringRef.current.material as any;
      mat.opacity = active ? 0.6 + Math.sin(tt * 3.4) * 0.2 : 0;
    }
  });

  return (
    <>
      {/* Connection line core ↔ node */}
      <line ref={lineRef as any}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={2}
            array={new Float32Array([0, 0, 0, 0, 0, 0])}
            itemSize={3}
            args={[new Float32Array([0, 0, 0, 0, 0, 0]), 3]}
          />
        </bufferGeometry>
        <lineBasicMaterial
          color={node.color}
          transparent
          opacity={0.18}
          depthWrite={false}
        />
      </line>

      <group ref={ref}>
        <Float speed={1.2} rotationIntensity={0.4} floatIntensity={0.3}>
          {/* Hover ripple ring — only visible when active */}
          <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.55, 0.62, 64]} />
            <meshBasicMaterial
              color={node.color}
              transparent
              opacity={0}
              depthWrite={false}
            />
          </mesh>

          <mesh
            onPointerOver={(e) => {
              e.stopPropagation();
              onActivate(node.slug);
              document.body.style.cursor = "pointer";
            }}
            onPointerOut={() => {
              document.body.style.cursor = "";
            }}
            scale={active ? 1.35 : 1}
          >
            <octahedronGeometry args={[0.34, 0]} />
            <meshStandardMaterial
              color={node.color}
              emissive={node.color}
              emissiveIntensity={active ? 1.0 : 0.55}
              metalness={0.45}
              roughness={0.28}
            />
            <Edges threshold={1} color={node.color} />
          </mesh>
          <Html
            position={[0, 0.6, 0]}
            center
            distanceFactor={9}
            zIndexRange={[20, 0]}
          >
            <div
              className="pointer-events-none whitespace-nowrap font-mono-tech text-[10px] uppercase tracking-[2.6px]"
              style={{ color: node.color }}
            >
              <span className="opacity-60">{node.num}</span>{" "}
              <span className="font-semibold">{node.name}</span>
            </div>
          </Html>
        </Float>
      </group>
    </>
  );
}

export function DomainsScene({
  activeSlug,
  onActivate,
}: {
  activeSlug: string;
  onActivate: (slug: string) => void;
}) {
  return (
    <Canvas
      dpr={[1, 1.7]}
      gl={{ antialias: true, alpha: true }}
      camera={{ position: [0, 1.6, 7], fov: 38 }}
      style={{ position: "absolute", inset: 0 }}
    >
      <ambientLight intensity={0.18} />
      {/* Brand lighting — indigo key + violet fill (was gold + cyan). */}
      <pointLight position={[3, 3, 5]} intensity={1.2} color="#6366F1" />
      <pointLight position={[-3, -2, -3]} intensity={0.55} color="#8B5CF6" />

      <Suspense fallback={null}>
        <Environment preset="city" />
        <CenterCore />
        <Orbit radius={2.6} />
        <Orbit radius={3.4} />
        {NODES.map((n, i) => (
          <Node
            key={n.slug}
            node={n}
            index={i}
            total={NODES.length}
            active={activeSlug === n.slug}
            onActivate={onActivate}
          />
        ))}
        {/* Brand sparkles — cyan instead of bright #00FFFF. */}
        <Sparkles count={120} size={1} speed={0.18} opacity={0.45} scale={[8, 4, 8]} color="#06B6D4" />
      </Suspense>

      <EffectComposer multisampling={0} enableNormalPass={false}>
        {/* Master.md §6 cap: intensity ≤ 0.85, threshold ≥ 0.18, no mipmapBlur. */}
        <Bloom
          intensity={0.55}
          luminanceThreshold={0.62}
          luminanceSmoothing={0.4}
          kernelSize={KernelSize.MEDIUM}
        />
      </EffectComposer>
    </Canvas>
  );
}
