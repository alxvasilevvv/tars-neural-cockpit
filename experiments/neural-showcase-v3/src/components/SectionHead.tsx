import { motion } from "framer-motion";

interface Props {
  num: string;
  tag: string;
  title: string;
  description: string;
}

export function SectionHead({ num, tag, title, description }: Props) {
  return (
    <motion.header
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="mb-11 grid grid-cols-1 items-end gap-6 border-b border-line pb-11 md:grid-cols-[1fr_1.2fr_1fr]"
    >
      <div className="flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
        <span className="text-[14px] tracking-normal text-accent">{num}</span>
        <span>{tag}</span>
      </div>
      <h2 className="font-display text-[clamp(2rem,4vw,3.6rem)] font-bold leading-[0.98] tracking-[-0.04em] text-ink">
        {title}
      </h2>
      <p className="max-w-[380px] text-right text-[14px] leading-[1.6] text-ink-2 md:justify-self-end">
        {description}
      </p>
    </motion.header>
  );
}
