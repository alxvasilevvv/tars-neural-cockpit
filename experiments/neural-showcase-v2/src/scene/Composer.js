import {
  EffectComposer,
  RenderPass,
  EffectPass,
  BloomEffect,
  ChromaticAberrationEffect,
  VignetteEffect,
  NoiseEffect,
  SMAAEffect,
  KernelSize,
  BlendFunction,
} from "postprocessing";
import { Vector2 } from "three";

export function createComposer(renderer, scene, camera) {
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  const bloom = new BloomEffect({
    intensity: 0.38,
    luminanceThreshold: 0.92,
    luminanceSmoothing: 0.3,
    kernelSize: KernelSize.SMALL,
    mipmapBlur: false,
  });

  const ca = new ChromaticAberrationEffect({
    offset: new Vector2(0.00015, 0.00015),
    radialModulation: false,
  });

  const vignette = new VignetteEffect({
    eskil: false,
    offset: 0.45,
    darkness: 0.6,
  });

  const noise = new NoiseEffect({
    blendFunction: BlendFunction.OVERLAY,
    premultiply: true,
  });
  noise.blendMode.opacity.value = 0.04;

  const smaa = new SMAAEffect();

  composer.addPass(new EffectPass(camera, bloom, ca));
  composer.addPass(new EffectPass(camera, vignette, noise, smaa));

  return { composer, bloom, ca, vignette, noise };
}
