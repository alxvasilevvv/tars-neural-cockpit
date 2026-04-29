import { Hero } from "@/components/Hero";
import { MeetTars } from "@/components/MeetTars";
import { TrustStrip } from "@/components/TrustStrip";
import { ProofStrip } from "@/components/ProofStrip";
import { ScrollStory } from "@/components/ScrollStory";
import { Rail } from "@/components/Rail";
import { Layers } from "@/components/Layers";
import { Domains } from "@/components/Domains";
import { Steps } from "@/components/Steps";
import { MeeetSection } from "@/components/MeeetSection";
import { MeeetWorldStrip } from "@/components/MeeetWorldStrip";
import { CockpitLive } from "@/components/CockpitLive";
import { CouncilDemo } from "@/components/CouncilDemo";
import { Compare } from "@/components/Compare";
import { Pricing } from "@/components/Pricing";
import { Waitlist } from "@/components/Waitlist";
import { FAQ } from "@/components/FAQ";
import { Footer } from "@/components/Footer";
import { SectionDivider } from "@/components/SectionDivider";

export function Landing() {
  return (
    <>
      <Hero />
      <TrustStrip />
      <ProofStrip />
      <SectionDivider label="00 / persona" />
      <MeetTars />
      <Rail />
      <SectionDivider label="01 / awareness" />
      <Layers />
      <SectionDivider label="02 / packs" />
      <Domains />
      <SectionDivider label="03 / how" />
      <ScrollStory />
      <SectionDivider label="04 / flow" />
      <Steps />
      <SectionDivider label="05 / cockpit" />
      <CockpitLive />
      <SectionDivider label="06 / meeet" />
      <MeeetSection />
      {/* meeet.world front-door card — sits between the brand pillars
          (MeeetSection) and the council demo. Reads /health for the
          live daemon pill. */}
      <div className="mx-auto -mt-6 mb-12 max-w-[1280px] px-8 md:px-14">
        <MeeetWorldStrip variant="card" />
      </div>
      <SectionDivider label="07 / council" />
      <CouncilDemo />
      <SectionDivider label="08 / vs" />
      <Compare />
      <SectionDivider label="09 / pricing" />
      <Pricing />
      <SectionDivider label="10 / waitlist" />
      <Waitlist />
      <SectionDivider label="11 / faq" />
      <FAQ />
      <Footer />
    </>
  );
}
