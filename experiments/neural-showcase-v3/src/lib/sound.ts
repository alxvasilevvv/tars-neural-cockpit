/**
 * Ambient bed + UI cue sound layer (WebAudio).
 *
 * Singleton — single AudioContext, two pan channels, multiple LFOs.
 * Honours `prefers-reduced-motion` (skips the modulation, keeps a
 * static bed at lower gain). Starts MUTED to comply with autoplay
 * policies; user opts in via <SoundToggle/>.
 *
 * Public API (unchanged):
 *   sound.mute(), sound.unmute(), sound.isOn,
 *   sound.tick(), sound.click(), sound.confirm(), sound.subscribe(cb)
 *
 * v2 polish (HANDOFF design item 6):
 *   - 5-tone ambient bed: low drone + 2 mid pads + high cue + sub
 *   - 2 LFOs (slow + slower), tiny detune wobble, stereo width
 *   - explicit `confirm()` cue separate from `click()`, with two-step
 *     envelope so it reads as "ok, accepted" rather than UI ping
 *   - press cue lower volume than confirm, brighter timbre
 *   - prefers-reduced-motion → static bed (no LFO sweeps)
 */

type Listener = (on: boolean) => void;

const TONES = [
  // freq, gain, pan (-1..1)
  { f: 55,    g: 0.45, pan: 0.0   }, // sub drone
  { f: 110,   g: 0.55, pan: -0.35 }, // low pad L
  { f: 164.81, g: 0.45, pan: 0.30 }, // mid pad R (E3)
  { f: 220,   g: 0.32, pan: -0.15 }, // upper pad
  { f: 329.63, g: 0.18, pan: 0.45 }, // air shimmer (E4, very low gain)
];

class SoundLayer {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private bedNodes: { osc: OscillatorNode; gain: GainNode; lfos: OscillatorNode[] }[] = [];
  private bedBus: GainNode | null = null;
  private filter: BiquadFilterNode | null = null;
  private listeners = new Set<Listener>();
  private reducedMotion = false;
  on = false;

  constructor() {
    if (typeof window !== "undefined") {
      this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    }
  }

  private ensureCtx() {
    if (this.ctx) return this.ctx;
    const Ctx =
      (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext })
        .AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    this.ctx = new Ctx();
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0;
    this.masterGain.connect(this.ctx.destination);
    return this.ctx;
  }

  private buildBed() {
    if (!this.ctx || !this.masterGain) return;
    if (this.bedNodes.length) return;
    const ctx = this.ctx;

    this.bedBus = ctx.createGain();
    this.bedBus.gain.value = 0.6;

    // Lowpass at 720Hz to keep things velvet, not resonant.
    this.filter = ctx.createBiquadFilter();
    this.filter.type = "lowpass";
    this.filter.frequency.value = 720;
    this.filter.Q.value = 0.65;
    this.bedBus.connect(this.filter);
    this.filter.connect(this.masterGain);

    // 5 tones, each through its own gain + StereoPanner
    for (const t of TONES) {
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = t.f;

      const gain = ctx.createGain();
      gain.gain.value = t.g * 0.18; // bed is loud relative to itself; master scales down

      const pan = ctx.createStereoPanner();
      pan.pan.value = t.pan;

      const lfos: OscillatorNode[] = [];

      if (!this.reducedMotion) {
        // Slow LFO on detune (tiny wobble, ±5 cents)
        const lfo1 = ctx.createOscillator();
        lfo1.frequency.value = 0.07 + Math.random() * 0.05;
        const lfo1Gain = ctx.createGain();
        lfo1Gain.gain.value = 5;
        lfo1.connect(lfo1Gain);
        lfo1Gain.connect(osc.detune);
        lfo1.start();
        lfos.push(lfo1);

        // Slower LFO on gain (breathing)
        const lfo2 = ctx.createOscillator();
        lfo2.frequency.value = 0.04 + Math.random() * 0.03;
        const lfo2Gain = ctx.createGain();
        lfo2Gain.gain.value = t.g * 0.04;
        lfo2.connect(lfo2Gain);
        lfo2Gain.connect(gain.gain);
        lfo2.start();
        lfos.push(lfo2);
      }

      osc.connect(gain);
      gain.connect(pan);
      pan.connect(this.bedBus);
      osc.start();
      this.bedNodes.push({ osc, gain, lfos });
    }
  }

  unmute() {
    const ctx = this.ensureCtx();
    if (!ctx || !this.masterGain) return;
    this.buildBed();
    if (ctx.state === "suspended") void ctx.resume();
    const t = ctx.currentTime;
    const target = this.reducedMotion ? 0.025 : 0.04;
    this.masterGain.gain.cancelScheduledValues(t);
    this.masterGain.gain.linearRampToValueAtTime(target, t + 1.6);
    this.on = true;
    this.notify();
  }

  mute() {
    if (!this.ctx || !this.masterGain) {
      this.on = false;
      this.notify();
      return;
    }
    const t = this.ctx.currentTime;
    this.masterGain.gain.cancelScheduledValues(t);
    this.masterGain.gain.linearRampToValueAtTime(0, t + 0.4);
    this.on = false;
    this.notify();
  }

  private notify() {
    for (const fn of this.listeners) fn(this.on);
  }

  subscribe(cb: Listener) {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  }

  /** Short hover blip — bright, very brief, very quiet. */
  tick() {
    if (!this.on || !this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "triangle";
    o.frequency.value = 1180;
    const t = ctx.currentTime;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.045, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.14);
    o.connect(g);
    g.connect(this.masterGain);
    o.start(t);
    o.stop(t + 0.16);
  }

  /** Press cue — UI button click. Sweep down, mid energy. */
  click() {
    if (!this.on || !this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    const t = ctx.currentTime;
    o.frequency.setValueAtTime(720, t);
    o.frequency.exponentialRampToValueAtTime(360, t + 0.18);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.09, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
    o.connect(g);
    g.connect(this.masterGain);
    o.start(t);
    o.stop(t + 0.30);
  }

  /** Operator-grade confirm cue — two-step envelope reads as "accepted".
   *  Use after destructive-action confirm, successful login, etc. */
  confirm() {
    if (!this.on || !this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const make = (freq: number, when: number, dur: number, gain: number, type: OscillatorType = "sine") => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = type;
      o.frequency.value = freq;
      g.gain.setValueAtTime(0, t + when);
      g.gain.linearRampToValueAtTime(gain, t + when + 0.012);
      g.gain.exponentialRampToValueAtTime(0.0001, t + when + dur);
      o.connect(g);
      g.connect(this.masterGain!);
      o.start(t + when);
      o.stop(t + when + dur + 0.02);
    };
    // Two-step: low pulse, then octave-up bell
    make(440, 0.00, 0.16, 0.10, "sine");
    make(880, 0.10, 0.32, 0.07, "triangle");
  }
}

export const sound = new SoundLayer();

if (typeof window !== "undefined") {
  // Tick on hover for interactive elements.
  const tickHover = (e: Event) => {
    const t = e.target as HTMLElement | null;
    if (
      t &&
      t.closest('a, button, [role="button"], [data-magnetic]')
    ) {
      sound.tick();
    }
  };
  document.addEventListener("mouseover", tickHover, true);
}
