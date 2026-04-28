import { Hero } from "@/components/Hero";
import { Rail } from "@/components/Rail";
import { Layers } from "@/components/Layers";
import { Domains } from "@/components/Domains";
import { Steps } from "@/components/Steps";
import { Footer } from "@/components/Footer";
import { Brackets } from "@/components/Brackets";
import { Nav } from "@/components/Nav";
import { Atmosphere } from "@/components/Atmosphere";
import { MagneticCursor } from "@/components/MagneticCursor";
import { SectionDivider } from "@/components/SectionDivider";

export default function App() {
  return (
    <main className="relative min-h-screen bg-bg-0 text-ink">
      <Atmosphere />
      <Brackets />
      <MagneticCursor />
      <Nav />
      <Hero />
      <Rail />
      <SectionDivider label="01 / awareness" />
      <Layers />
      <SectionDivider label="02 / packs" />
      <Domains />
      <SectionDivider label="03 / flow" />
      <Steps />
      <SectionDivider label="04 / cockpit" />
      <Footer />
    </main>
  );
}
