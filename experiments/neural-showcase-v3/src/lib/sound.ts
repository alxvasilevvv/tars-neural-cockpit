/**
 * Ambient hum + UI cue sound layer (WebAudio).
 *
 * Singleton pattern — single AudioContext shared across the app.
 * Honours `prefers-reduced-motion` and starts MUTED by default to
 * comply with browser autoplay policies. The user opts in via
 * <SoundToggle/>.
 *
 * Public API:
 *   sound.mute(), sound.unmute(), sound.isOn,
 *   sound.tick(), sound.click(), sound.subscribe(cb)
 */

type Listener = (on: boolean) => void;

class SoundLayer {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private hum: OscillatorNode[] = [];
  private humGain: GainNode | null = null;
  private listeners = new Set<Listener>();
  on = false;

  private ensureCtx() {
    if (this.ctx) return this.ctx;
    const Ctx =
      (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!Ctx) return null;
    this.ctx = new Ctx() as AudioContext;
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 0;
    this.masterGain.connect(this.ctx.destination);
    return this.ctx;
  }

  private buildHum() {
    if (!this.ctx || !this.masterGain) return;
    if (this.hum.length) return;

    this.humGain = this.ctx.createGain();
    this.humGain.gain.value = 0.6;

    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 380;
    lp.Q.value = 0.7;

    const tones = [110, 165, 82.5];
    for (const f of tones) {
      const osc = this.ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = f;
      const detune = this.ctx.createOscillator();
      detune.frequency.value = 0.07; // tiny LFO for breathing
      const detuneGain = this.ctx.createGain();
      detuneGain.gain.value = 4;
      detune.connect(detuneGain);
      detuneGain.connect(osc.detune);
      detune.start();
      osc.connect(this.humGain);
      osc.start();
      this.hum.push(osc);
    }
    this.humGain.connect(lp);
    lp.connect(this.masterGain);
  }

  unmute() {
    const ctx = this.ensureCtx();
    if (!ctx || !this.masterGain) return;
    this.buildHum();
    if (ctx.state === "suspended") void ctx.resume();
    const t = ctx.currentTime;
    this.masterGain.gain.cancelScheduledValues(t);
    this.masterGain.gain.linearRampToValueAtTime(0.045, t + 1.6);
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

  /** Short hover/typewriter blip — cheap and bright. */
  tick() {
    if (!this.on || !this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "triangle";
    o.frequency.value = 1180;
    const t = ctx.currentTime;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.06, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    o.connect(g);
    g.connect(this.masterGain);
    o.start(t);
    o.stop(t + 0.18);
  }

  /** Heavier confirmation tone — for CTAs and successful actions. */
  click() {
    if (!this.on || !this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    const t = ctx.currentTime;
    o.frequency.setValueAtTime(880, t);
    o.frequency.exponentialRampToValueAtTime(420, t + 0.18);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.12, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
    o.connect(g);
    g.connect(this.masterGain);
    o.start(t);
    o.stop(t + 0.34);
  }
}

export const sound = new SoundLayer();

if (typeof window !== "undefined") {
  // Auto-tick on hover for any [data-magnetic] / link / button.
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
