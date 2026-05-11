/**
 * <CoworkHandoffAccept /> — Wave 129 / split out in Wave 136.
 *
 * `/cowork/handoff/:token` recipient-side screen. Tiny chunk —
 * displays the token + directs the user to open the session in
 * desktop TARS. No heavy components, no SSE, no fetches.
 */

import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Breadcrumbs } from "@/components/Breadcrumbs";
import { useDocumentMeta } from "@/lib/meta";

export function CoworkHandoffAccept() {
  const { token } = useParams<{ token: string }>();

  useDocumentMeta({
    title: "Accept cowork handoff",
    description:
      "Accept ownership of a TARS cowork session that was handed off to you.",
  });

  return (
    <section className="mx-auto max-w-[640px] px-6 py-20">
      <Breadcrumbs
        items={[
          { label: "Cowork", to: "/cowork" },
          { label: "Accept handoff" },
        ]}
      />
      <div className="rounded-[14px] border border-line bg-bg-1/70 p-8 backdrop-blur-sm">
        <div className="mb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
          Handoff received
        </div>
        <h1 className="mb-4 font-display text-[24px] font-medium leading-[1.1] tracking-[-0.01em] text-ink">
          You've been handed a cowork session.
        </h1>
        <p className="mb-6 text-[13.5px] leading-[1.65] text-ink-2">
          To accept ownership of this session, open it in the desktop TARS
          app (which carries your local identity). The token below is
          single-use and expires shortly.
        </p>
        <div className="mb-6 break-all rounded-md border border-line bg-bg-2 px-3 py-2 font-mono-tech text-[12.5px] text-ink">
          {token ?? "(missing token)"}
        </div>
        <Link
          to="/cowork"
          className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-2 px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition hover:bg-bg-1"
        >
          <ArrowLeft size={14} strokeWidth={1.6} />
          Back to sessions
        </Link>
      </div>
    </section>
  );
}
