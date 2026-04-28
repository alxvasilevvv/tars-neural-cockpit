export const galaxyVert = /* glsl */ `
  attribute float aSize;
  attribute float aPhase;
  attribute float aSpeed;
  attribute vec3 aColor;

  uniform float uTime;
  uniform float uPixelRatio;
  uniform float uScrollProgress;

  varying vec3 vColor;
  varying float vPulse;

  mat3 rotY(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat3(c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c);
  }

  void main() {
    vColor = aColor;

    vec3 p = rotY(uTime * aSpeed) * position;

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;

    float pulse = 0.72 + 0.28 * sin(uTime * aSpeed * 14.0 + aPhase);
    vPulse = pulse;

    float persp = 220.0 / -mv.z;
    gl_PointSize = aSize * persp * uPixelRatio * (0.7 + 0.35 * pulse);
  }
`;

export const galaxyFrag = /* glsl */ `
  varying vec3 vColor;
  varying float vPulse;

  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;

    float core = smoothstep(0.5, 0.0, d);
    float halo = pow(core, 3.4);
    vec3 col = vColor * (0.6 + 0.4 * vPulse);
    float alpha = halo * (0.42 + 0.28 * vPulse);

    gl_FragColor = vec4(col, alpha);
  }
`;
