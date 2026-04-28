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
  { num: "01", name: "Traders", slug: "traders", color: "#CA8A04" },
  { num: "02", name: "Business", slug: "business", color: "#00FFFF" },
  { num: "03", name: "MLM", slug: "mlm", color: "#CA8A04" },
  { num: "04", name: "Science", slug: "science", color: "#00FFFF" },
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
        color="#CA8A04"
        emissive="#CA8A04"
        emissiveIntensity={0.6}
        roughness={0.2}
        metalness={0.7}
      />
      <Edges threshold={1} color="#00FFFF" />
    </mesh>
  );
}

function Orbit({ radius = 2.6 }: { radius?: number }) {
  return (
    <mesh rotation={[Math.PI / 2.4, 0, 0]}>
      <ringGeometry args={[radius - 0.005, radius + 0.005, 96]} />
      <meshBasicMaterial color="#00FFFF" transparent opacity={0.32} />
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
  const phase = (index / total) * Math.PI * 2;
  const radius = 2.6;

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * 0.18 + phase;
    if (ref.current) {
      ref.current.position.x = Math.cos(t) * radius;
      ref.current.position.z = Math.sin(t) * radius;
      ref.current.position.y = Math.sin(t * 1.2 + index) * 0.18;
      ref.current.lookAt(0, 0, 0);
    }
  });

  return (
    <group ref={ref}>
      <Float speed={1.2} rotationIntensity={0.4} floatIntensity={0.3}>
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
            emissiveIntensity={active ? 1.6 : 0.8}
            metalness={0.5}
            roughness={0.18}
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
      <pointLight position={[3, 3, 5]} intensity={1.4} color="#CA8A04" />
      <pointLight position={[-3, -2, -3]} intensity={0.55} color="#00FFFF" />

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
        <Sparkles count={120} size={1} speed={0.18} opacity={0.45} scale={[8, 4, 8]} color="#00FFFF" />
      </Suspense>

      <EffectComposer multisampling={0} enableNormalPass={false}>
        <Bloom
          intensity={1.2}
          mipmapBlur
          luminanceThreshold={0.16}
          luminanceSmoothing={0.32}
          kernelSize={KernelSize.MEDIUM}
        />
      </EffectComposer>
    </Canvas>
  );
}
