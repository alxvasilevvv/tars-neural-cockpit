import { Hero } from "@/components/Hero";
import { Rail } from "@/components/Rail";
import { Layers } from "@/components/Layers";
import { Domains } from "@/components/Domains";
import { Steps } from "@/components/Steps";
import { Footer } from "@/components/Footer";
import { SectionDivider } from "@/components/SectionDivider";

export function Landing() {
  return (
    <>
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
    </>
  );
}
