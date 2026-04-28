import { Canvas, useFrame, extend } from "@react-three/fiber";
import {
  Float,
  Icosahedron,
  MeshDistortMaterial,
  Sparkles,
  Edges,
  Environment,
  shaderMaterial,
  Stars,
  TorusKnot,
} from "@react-three/drei";
import {
  EffectComposer,
  Bloom,
  ChromaticAberration,
  Vignette,
  Noise,
} from "@react-three/postprocessing";
import { BlendFunction, KernelSize } from "postprocessing";
import { Vector2, Color, AdditiveBlending, BackSide, FrontSide } from "three";
import { useRef, Suspense, useMemo } from "react";
import type { Group, Mesh, ShaderMaterial as TShaderMaterial } from "three";

/* -------------------------------------------------------------------------- */
/* Custom fresnel + scan shader for the outer skeleton — gives a real         */
/* "powered shield" rim glow that scrolls a horizon of light around the mesh. */
/* -------------------------------------------------------------------------- */

const FresnelMaterial = shaderMaterial(
  {
    uTime: 0,
    uColor: new Color("#00FFFF"),
    uIntensity: 1.6,
    uSpeed: 0.6,
    uOpacity: 0.85,
  },
  /* glsl */ `
    varying vec3 vNormalView;
    varying vec3 vViewPos;
    varying vec3 vWorldPos;

    void main() {
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      vViewPos = -mvPosition.xyz;
      vNormalView = normalize(normalMatrix * normal);
      vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  /* glsl */ `
    uniform float uTime;
    uniform vec3 uColor;
    uniform float uIntensity;
    uniform float uSpeed;
    uniform float uOpacity;

    varying vec3 vNormalView;
    varying vec3 vViewPos;
    varying vec3 vWorldPos;

    void main() {
      vec3 V = normalize(vViewPos);
      vec3 N = normalize(vNormalView);
      float fresnel = pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 2.6);

      // Scrolling horizon — sweeps a band of brightness around the mesh.
      float band = 0.5 + 0.5 * sin(vWorldPos.y * 4.2 - uTime * uSpeed * 6.2831);
      band = pow(band, 6.0) * 0.85;

      float scan = step(0.992, fract(vWorldPos.y * 8.0 - uTime * 0.7));

      float a = fresnel * uIntensity + band * 0.45 + scan * 0.6;
      vec3 col = uColor * (1.0 + fresnel * 1.8);

      gl_FragColor = vec4(col, clamp(a, 0.0, 1.0) * uOpacity);
    }
  `,
);

extend({ FresnelMaterial });

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      fresnelMaterial: any;
    }
  }
}

/* -------------------------------------------------------------------------- */

function FresnelShell({
  radius,
  color = "#00FFFF",
  intensity = 1.6,
  speed = 0.6,
  opacity = 0.85,
}: {
  radius: number;
  color?: string;
  intensity?: number;
  speed?: number;
  opacity?: number;
}) {
  const mat = useRef<TShaderMaterial>(null!);
  const colorObj = useMemo(() => new Color(color), [color]);
  useFrame((_, delta) => {
    if (mat.current) (mat.current as any).uTime += delta;
  });
  return (
    <mesh>
      <icosahedronGeometry args={[radius, 5]} />
      <fresnelMaterial
        ref={mat}
        transparent
        depthWrite={false}
        blending={AdditiveBlending}
        side={FrontSide}
        uColor={colorObj}
        uIntensity={intensity}
        uSpeed={speed}
        uOpacity={opacity}
      />
    </mesh>
  );
}

/* -------------------------------------------------------------------------- */

function OrbitingSatellite({
  radius,
  speed,
  yOffset,
  size = 0.16,
  color = "#CA8A04",
}: {
  radius: number;
  speed: number;
  yOffset: number;
  size?: number;
  color?: string;
}) {
  const ref = useRef<Mesh>(null!);
  const phase = useRef(Math.random() * Math.PI * 2);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * speed + phase.current;
    if (ref.current) {
      ref.current.position.x = Math.cos(t) * radius;
      ref.current.position.z = Math.sin(t) * radius;
      ref.current.position.y =
        yOffset + Math.sin(t * 1.4) * 0.18;
      ref.current.rotation.x = t * 0.6;
      ref.current.rotation.y = t * 0.8;
    }
  });
  return (
    <group>
      <mesh ref={ref}>
        <octahedronGeometry args={[size, 0]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1.2}
          metalness={0.5}
          roughness={0.18}
        />
        <Edges threshold={1} color={color} />
      </mesh>
    </group>
  );
}

/* -------------------------------------------------------------------------- */

function Core() {
  const root = useRef<Group>(null!);
  const knot = useRef<Mesh>(null!);
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
    if (knot.current) {
      knot.current.rotation.x += delta * 0.32;
      knot.current.rotation.y -= delta * 0.21;
    }
  });

  return (
    <Float speed={1.05} rotationIntensity={0.18} floatIntensity={0.55}>
      <group ref={root}>
        {/* Inner reactor — gold accent per skill master. */}
        <Icosahedron args={[1.18, 5]}>
          <MeshDistortMaterial
            color="#CA8A04"
            emissive="#CA8A04"
            emissiveIntensity={0.55}
            roughness={0.16}
            metalness={0.78}
            distort={0.36}
            speed={1.4}
          />
        </Icosahedron>

        {/* Liquid metal mid-shell with inverted faces for inner glow read */}
        <Icosahedron args={[1.34, 4]}>
          <MeshDistortMaterial
            color="#CA8A04"
            emissive="#CA8A04"
            emissiveIntensity={0.18}
            roughness={0.25}
            metalness={0.6}
            distort={0.22}
            speed={0.9}
            transparent
            opacity={0.32}
            side={BackSide}
            depthWrite={false}
          />
        </Icosahedron>

        {/* HUD wireframe shell */}
        <Icosahedron args={[1.55, 1]}>
          <meshBasicMaterial color="#00FFFF" wireframe transparent opacity={0.16} />
        </Icosahedron>

        {/* Custom GLSL fresnel skeletons — the expensive crown jewel */}
        <FresnelShell radius={2.05} color="#00FFFF" intensity={1.5} speed={0.55} opacity={0.85} />
        <FresnelShell radius={2.62} color="#00FFFF" intensity={1.1} speed={0.34} opacity={0.55} />

        {/* Two skeleton edge cages */}
        <Icosahedron args={[2.05, 0]}>
          <meshBasicMaterial transparent opacity={0} />
          <Edges threshold={1} color="#00FFFF" />
        </Icosahedron>
        <Icosahedron args={[2.62, 0]}>
          <meshBasicMaterial transparent opacity={0} />
          <Edges threshold={1} color="#00FFFF" />
        </Icosahedron>

        {/* Orbiting torus knot — adds asymmetric motion. */}
        <mesh ref={knot} rotation={[Math.PI / 4, 0, Math.PI / 6]}>
          <TorusKnot args={[2.95, 0.018, 320, 6, 2, 5]} />
          <meshBasicMaterial color="#00FFFF" transparent opacity={0.55} />
        </mesh>

        {/* Satellites — small data points orbiting the core. */}
        <OrbitingSatellite radius={2.95} speed={0.55} yOffset={0.4} size={0.13} color="#CA8A04" />
        <OrbitingSatellite radius={3.25} speed={-0.42} yOffset={-0.55} size={0.1} color="#00FFFF" />
        <OrbitingSatellite radius={3.55} speed={0.31} yOffset={0.9} size={0.09} color="#CA8A04" />
        <OrbitingSatellite radius={3.85} speed={-0.22} yOffset={-1.1} size={0.08} color="#00FFFF" />
      </group>
    </Float>
  );
}

/* -------------------------------------------------------------------------- */

export function HeroScene() {
  return (
    <Canvas
      dpr={[1, 1.7]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, 6.4], fov: 38 }}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      <ambientLight intensity={0.18} />
      <pointLight position={[3, 3, 5]} intensity={1.6} color="#CA8A04" />
      <pointLight position={[-4, -2, -3]} intensity={0.55} color="#00FFFF" />
      <pointLight position={[0, 4, -3]} intensity={0.32} color="#FFFFFF" />

      <Suspense fallback={null}>
        <Environment preset="city" />
        <Core />
        {/* Three depth-layers of particles for parallax */}
        <Sparkles count={120} size={1.4} speed={0.18} opacity={0.45} scale={[6, 4, 4]} color="#CA8A04" />
        <Sparkles count={220} size={0.7} speed={0.1} opacity={0.32} scale={[12, 8, 8]} color="#00FFFF" />
        <Sparkles count={80} size={2.2} speed={0.05} opacity={0.18} scale={[18, 10, 10]} color="#FFFFFF" />
        <Stars radius={42} depth={28} count={600} factor={2.4} fade speed={0.4} />
      </Suspense>

      <EffectComposer multisampling={0} enableNormalPass={false}>
        <Bloom
          intensity={1.05}
          mipmapBlur
          luminanceThreshold={0.16}
          luminanceSmoothing={0.32}
          kernelSize={KernelSize.MEDIUM}
        />
        <ChromaticAberration
          offset={new Vector2(0.0009, 0.0014)}
          radialModulation
          modulationOffset={0.18}
          blendFunction={BlendFunction.NORMAL}
        />
        <Vignette eskil={false} offset={0.28} darkness={0.78} />
        <Noise opacity={0.045} />
      </EffectComposer>
    </Canvas>
  );
}
