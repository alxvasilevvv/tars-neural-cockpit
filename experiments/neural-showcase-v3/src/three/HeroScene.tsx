import { Canvas, useFrame } from "@react-three/fiber";
import {
  Float,
  Icosahedron,
  MeshDistortMaterial,
  Sparkles,
  Edges,
  Environment,
} from "@react-three/drei";
import {
  EffectComposer,
  Bloom,
  ChromaticAberration,
  Vignette,
  Noise,
} from "@react-three/postprocessing";
import { BlendFunction, KernelSize } from "postprocessing";
import { Vector2 } from "three";
import { useRef, Suspense } from "react";
import type { Group } from "three";

/**
 * The cinematic core for v3. Three concentric meshes: a soft inner
 * distorted solid (accent-emissive), a wire icosahedron, and an outer
 * skeleton ring of edges. Light parallax on pointer move.
 */
function Core() {
  const root = useRef<Group>(null!);
  const pointer = useRef({ x: 0, y: 0 });

  useFrame((state, delta) => {
    pointer.current.x +=
      (state.pointer.x - pointer.current.x) * Math.min(1, delta * 4);
    pointer.current.y +=
      (state.pointer.y - pointer.current.y) * Math.min(1, delta * 4);
    if (root.current) {
      root.current.rotation.y += delta * 0.18;
      root.current.rotation.x = pointer.current.y * 0.18;
      root.current.rotation.z = pointer.current.x * 0.06;
    }
  });

  return (
    <Float speed={1.1} rotationIntensity={0.18} floatIntensity={0.55}>
      <group ref={root}>
        <Icosahedron args={[1.18, 4]}>
          <MeshDistortMaterial
            color="#67E8F9"
            emissive="#67E8F9"
            emissiveIntensity={0.42}
            roughness={0.18}
            metalness={0.65}
            distort={0.34}
            speed={1.4}
          />
        </Icosahedron>

        <Icosahedron args={[1.55, 1]}>
          <meshBasicMaterial
            color="#67E8F9"
            wireframe
            transparent
            opacity={0.13}
          />
        </Icosahedron>

        <Icosahedron args={[2.05, 0]}>
          <meshBasicMaterial transparent opacity={0} />
          <Edges threshold={1} color="#67E8F9" />
        </Icosahedron>

        <Icosahedron args={[2.62, 0]}>
          <meshBasicMaterial transparent opacity={0} />
          <Edges threshold={1} color="#67E8F9" />
        </Icosahedron>
      </group>
    </Float>
  );
}

export function HeroScene() {
  return (
    <Canvas
      dpr={[1, 1.7]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, 5.4], fov: 38 }}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      <ambientLight intensity={0.18} />
      <pointLight position={[3, 3, 5]} intensity={1.4} color="#67E8F9" />
      <pointLight position={[-4, -2, -3]} intensity={0.4} color="#FBBF24" />

      <Suspense fallback={null}>
        <Environment preset="city" />
        <Core />
        <Sparkles
          count={140}
          size={1.2}
          speed={0.18}
          opacity={0.42}
          scale={[8, 6, 6]}
          color="#67E8F9"
        />
      </Suspense>

      <EffectComposer multisampling={0} enableNormalPass={false}>
        <Bloom
          intensity={0.85}
          mipmapBlur
          luminanceThreshold={0.18}
          luminanceSmoothing={0.32}
          kernelSize={KernelSize.MEDIUM}
        />
        <ChromaticAberration
          offset={new Vector2(0.0008, 0.0012)}
          radialModulation
          modulationOffset={0.18}
          blendFunction={BlendFunction.NORMAL}
        />
        <Vignette eskil={false} offset={0.32} darkness={0.7} />
        <Noise opacity={0.04} />
      </EffectComposer>
    </Canvas>
  );
}
