import { motion } from "framer-motion";
import { Fragment } from "react";

/**
 * Char-level reveal with rotateX entrance.
 * Splits the input into words (preserving spaces) and animates each char
 * with a staggered y/rotate sweep. Optional accent word gets a soft text
 * shadow + colour tint that sweeps in on reveal.
 */

const charV = {
  hidden: { y: "120%", rotateX: -88, opacity: 0 },
  show: { y: "0%", rotateX: 0, opacity: 1 },
};

export function KineticText({
  text,
  delay = 0,
  accentWords = [],
  className,
}: {
  text: string;
  delay?: number;
  accentWords?: string[];
  className?: string;
}) {
  const words = text.split(/(\s+)/); // keep whitespace tokens
  let charIndex = 0;

  return (
    <motion.span
      className={`inline-flex flex-wrap [perspective:800px] ${className ?? ""}`}
      initial="hidden"
      animate="show"
      transition={{ delay }}
    >
      {words.map((w, wi) => {
        if (/\s/.test(w)) {
          return <span key={`s${wi}`}>&nbsp;</span>;
        }
        const isAccent = accentWords.includes(w.replace(/[^A-Za-zА-Яа-я0-9]/g, ""));
        const chars = Array.from(w);
        return (
          <span
            key={`w${wi}`}
            className="inline-flex overflow-hidden pb-[0.06em]"
            style={
              isAccent
                ? {
                    color: "var(--color-accent)",
                    textShadow: "0 0 24px var(--color-accent-soft)",
                  }
                : undefined
            }
          >
            {chars.map((c, ci) => {
              const i = charIndex++;
              return (
                <motion.span
                  key={`c${wi}-${ci}`}
                  variants={charV}
                  transition={{
                    duration: 0.85,
                    delay: i * 0.018,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="inline-block [transform-origin:50%_100%]"
                >
                  {c}
                </motion.span>
              );
            })}
            <Fragment />
          </span>
        );
      })}
    </motion.span>
  );
}
