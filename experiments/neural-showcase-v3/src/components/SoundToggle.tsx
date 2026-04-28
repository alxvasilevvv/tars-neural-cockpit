import { useEffect, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { sound } from "@/lib/sound";

export function SoundToggle() {
  const [on, setOn] = useState(false);

  useEffect(() => sound.subscribe(setOn), []);

  return (
    <button
      type="button"
      aria-label={on ? "Mute ambient" : "Unmute ambient"}
      onClick={() => {
        if (on) {
          sound.mute();
        } else {
          sound.unmute();
          sound.click();
        }
      }}
      className="ml-1 inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-md border border-line bg-white/[0.02] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:bg-white/[0.05] hover:text-ink"
      title="Ambient hum"
    >
      {on ? <Volume2 size={14} strokeWidth={1.6} /> : <VolumeX size={14} strokeWidth={1.6} />}
    </button>
  );
}
