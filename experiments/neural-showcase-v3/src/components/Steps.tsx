import { motion } from "framer-motion";
import { SectionHead } from "@/components/SectionHead";

const STEPS = [
  {
    num: "01",
    title: "Drop folders & files",
    body: "MD, PDF, code, audio. Local indexing, no upload.",
  },
  {
    num: "02",
    title: "Embed & cluster",
    body: "Six awareness layers light up. Each cluster picks a place in the graph.",
  },
  {
    num: "03",
    title: "Pick a domain pack",
    body: "The core specialises into a tool for your craft — traders, business, MLM or science.",
  },
];

export function Steps() {
  return (
    <section
      id="how"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-32 md:px-14 md:py-36"
    >
      <SectionHead
        num="03"
        tag="FLOW"
        title="Drop. Cluster. Specialise."
        description="Drop any folder. TARS embeds, clusters, and wires it into a graph you can navigate at the speed of thought."
      />
      <ol className="grid grid-cols-1 gap-px overflow-hidden rounded-[22px] border border-line bg-line md:grid-cols-3">
        {STEPS.map((s, i) => (
          <motion.li
            key={s.num}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{
              duration: 0.6,
              delay: i * 0.08,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="bg-bg-1 p-10"
          >
            <span className="mb-4 block font-display text-[56px] font-extrabold leading-none tracking-[-0.04em] text-accent opacity-85">
              {s.num}
            </span>
            <h4 className="mb-2 font-display text-[20px] font-semibold tracking-[-0.02em] text-ink">
              {s.title}
            </h4>
            <p className="text-[14px] leading-[1.6] text-ink-2">{s.body}</p>
          </motion.li>
        ))}
      </ol>
    </section>
  );
}
