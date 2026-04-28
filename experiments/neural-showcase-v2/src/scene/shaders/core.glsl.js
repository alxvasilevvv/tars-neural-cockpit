import { noiseGLSL } from "./lib.glsl.js";

export const reactorVert = /* glsl */ `
  uniform float uTime;
  uniform float uHover;
  varying vec3 vNormal;
  varying vec3 vViewPos;
  varying vec3 vPosition;

  ${noiseGLSL}

  void main() {
    vec3 p = position;
    float n = snoise(p * 1.7 + vec3(uTime * 0.42));
    float n2 = snoise(p * 3.0 - vec3(uTime * 0.55));
    float disp = (n * 0.6 + n2 * 0.4) * (0.035 + 0.05 * uHover);
    vec3 displaced = p + normal * disp;

    vNormal = normalize(normalMatrix * normal);
    vec4 mv = modelViewMatrix * vec4(displaced, 1.0);
    vViewPos = -mv.xyz;
    vPosition = displaced;
    gl_Position = projectionMatrix * mv;
  }
`;

export const reactorFrag = /* glsl */ `
  uniform float uTime;
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  varying vec3 vNormal;
  varying vec3 vViewPos;
  varying vec3 vPosition;

  void main() {
    vec3 N = normalize(vNormal);
    vec3 V = normalize(vViewPos);
    float fresnel = pow(1.0 - max(dot(N, V), 0.0), 2.4);

    float r = length(vPosition);
    float pulse = sin(r * 28.0 - uTime * 2.4) * 0.5 + 0.5;
    pulse *= smoothstep(0.55, 0.0, r);

    vec3 col = uColorA * (0.32 + 0.55 * fresnel);
    col += uColorB * pulse * 0.08;
    gl_FragColor = vec4(col, 1.0);
  }
`;

export const ringVert = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const ringFrag = /* glsl */ `
  uniform float uTime;
  uniform vec3 uColor;
  uniform float uNotches;
  uniform float uScanSpeed;

  varying vec2 vUv;

  void main() {
    float theta = vUv.x;

    float minor = step(0.55, fract(theta * uNotches));
    float major = step(0.88, fract(theta * (uNotches / 6.0)));

    float baseAlpha = 0.08 + 0.18 * minor + 0.22 * major;

    float scanPos = fract(uTime * uScanSpeed);
    float dist = abs(theta - scanPos);
    dist = min(dist, 1.0 - dist);
    float scan = smoothstep(0.06, 0.0, dist);

    vec3 col = uColor * (0.55 + 0.5 * baseAlpha + scan * 1.3);
    float alpha = baseAlpha + scan * 0.45;
    gl_FragColor = vec4(col, clamp(alpha, 0.0, 0.85));
  }
`;
