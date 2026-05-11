/**
 * roles.data — Wave 124 split out of /pages/Onboarding.tsx.
 * Default 6 roles + the briefing-tick copy. Pure data; the page imports
 * everything below.
 */

import {
  Briefcase,
  TrendingUp,
  FlaskConical,
  Megaphone,
  Code,
  Crown,
} from "lucide-react";
import type { TKey } from "@/lib/i18n";

export type RoleSlug =
  | "founder"
  | "trader"
  | "researcher"
  | "marketer"
  | "engineer"
  | "operator"
  | "custom";

export interface Role {
  slug: RoleSlug;
  num: string;
  /** Translation keys; resolved at render via useT(). */
  nameKey: TKey;
  descriptionKey: TKey;
  Icon: typeof Briefcase;
  color: string;
  /** Pack slugs the role maps onto. Backend uses this to build the
   *  composite system prompt. Empty for `custom` (synthesised by the
   *  /api/roles endpoint when Cursor ships P7). */
  backingPacks: string[];
}

export const ROLES: Role[] = [
  {
    slug: "founder",
    num: "01",
    nameKey: "onboarding.role.founder.name",
    descriptionKey: "onboarding.role.founder.desc",
    Icon: Crown,
    color: "var(--brand-indigo)",
    backingPacks: ["entrepreneur", "business"],
  },
  {
    slug: "trader",
    num: "02",
    nameKey: "onboarding.role.trader.name",
    descriptionKey: "onboarding.role.trader.desc",
    Icon: TrendingUp,
    color: "var(--brand-violet)",
    backingPacks: ["traders"],
  },
  {
    slug: "researcher",
    num: "03",
    nameKey: "onboarding.role.researcher.name",
    descriptionKey: "onboarding.role.researcher.desc",
    Icon: FlaskConical,
    color: "var(--brand-cyan)",
    backingPacks: ["science"],
  },
  {
    slug: "marketer",
    num: "04",
    nameKey: "onboarding.role.marketer.name",
    descriptionKey: "onboarding.role.marketer.desc",
    Icon: Megaphone,
    color: "var(--brand-orchid)",
    backingPacks: ["entrepreneur"],
  },
  {
    slug: "engineer",
    num: "05",
    nameKey: "onboarding.role.engineer.name",
    descriptionKey: "onboarding.role.engineer.desc",
    Icon: Code,
    color: "var(--color-success)",
    backingPacks: ["science"],
  },
  {
    slug: "operator",
    num: "06",
    nameKey: "onboarding.role.operator.name",
    descriptionKey: "onboarding.role.operator.desc",
    Icon: Briefcase,
    color: "var(--brand-amber)",
    backingPacks: ["traders", "entrepreneur", "science", "business"],
  },
];

export const BRIEF_TICKS = [
  "Reading calendar (today + tomorrow)…",
  "Indexing 47 unread mail threads…",
  "Pulling starred GitHub repos…",
  "Drafting one-page briefing…",
  "Council voting on tone calibration…",
  "Briefing ready.",
];

export default ROLES;
