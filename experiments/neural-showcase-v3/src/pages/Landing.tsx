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
import { CoworkPreview } from "@/components/CoworkPreview";
import { CouncilDemo } from "@/components/CouncilDemo";
import { Compare } from "@/components/Compare";
import { Pricing } from "@/components/Pricing";
import { Waitlist } from "@/components/Waitlist";
import { FAQ } from "@/components/FAQ";
import { Footer } from "@/components/Footer";
import { SectionDivider } from "@/components/SectionDivider";
import { useT } from "@/lib/i18n";

/**
 * Landing — public marketing surface for tars.meeet.world.
 *
 * Wave 66 — Cockpit removed from public site (CockpitLive section
 * deleted, /cockpit route redirected). The cockpit is the desktop
 * app's main UI; trying to preview it on the marketing surface
 * (without backend) was confusing users + producing the empty-block
 * regression. Marketing focus: download → install → run locally.
 */
export function Landing() {
  const t = useT();
  return (
    <>
      <Hero />
      <TrustStrip />
      <ProofStrip />
      <SectionDivider label={t("landing.section.00")} />
      <MeetTars />
      <Rail />
      <SectionDivider label={t("landing.section.01")} />
      <Layers />
      <SectionDivider label={t("landing.section.02")} />
      <Domains />
      <SectionDivider label={t("landing.section.03")} />
      <ScrollStory />
      <SectionDivider label={t("landing.section.04")} />
      <Steps />
      <SectionDivider label={t("landing.section.05")} />
      <MeeetSection />
      {/* meeet.world front-door card — sits between the brand pillars
          (MeeetSection) and the council demo. Reads /health for the
          live daemon pill. -mt-2 (was -mt-6) avoids collision with the
          SectionDivider's py-6 breathing room. */}
      <div className="mx-auto -mt-2 mb-12 max-w-[1280px] px-8 md:px-14">
        <MeeetWorldStrip variant="card" />
      </div>
      {/* Wave 132 — CoworkPreview sits between MeeetSection and
          CouncilDemo. Multiplayer is the new hero feature post-launch
          and deserves a landing-page demo card. Reuses the section.06
          divider; section.07+ shift down by one (no other refactor —
          the existing dividers were just labels not content anchors). */}
      <SectionDivider label={t("landing.section.06")} />
      <CoworkPreview />
      <CouncilDemo />
      <SectionDivider label={t("landing.section.07")} />
      <Compare />
      <SectionDivider label={t("landing.section.08")} />
      <Pricing />
      <SectionDivider label={t("landing.section.09")} />
      <Waitlist />
      <SectionDivider label={t("landing.section.10")} />
      <FAQ />
      <Footer />
    </>
  );
}
