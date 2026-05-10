// SYNC: claude-w106-marketplace
/**
 * Wave 106 — shared types for the marketplace surface.
 *
 * Mirrors the backend ``Listing`` / ``InstalledItem`` / ``Rating``
 * dataclasses (see backend/core/marketplace/models.py). Fields
 * left optional are the ones the registry serialises but the FE
 * doesn't render in v0.
 */

export type ListingKind = "playbook" | "skill" | "template" | "report_template";
export type PriceTier = "free" | "one-time" | "subscription";

export interface ListingAuthor {
  handle: string;
  url?: string | null;
}

export interface ListingRatings {
  count: number;
  avg: number;
}

export interface Listing {
  id: string;
  kind: ListingKind;
  name: string;
  slug: string;
  description: string;
  author: ListingAuthor;
  version: string;
  tags: string[];
  category: string;
  install_payload: unknown;
  preview_url?: string | null;
  ratings: ListingRatings;
  price: PriceTier;
  license: string;
  created_at: number;
  updated_at: number;
  /** Decorated server-side: true when the listing already lives in the local install. */
  installed?: boolean;
}

export interface InstalledItem {
  listing_id: string;
  version: string;
  installed_at: number;
  installed_path: string;
  target: "personal" | "workspace";
  listing_snapshot: Partial<Listing>;
}

export interface Rating {
  id: string;
  listing_id: string;
  rater: string;
  score: number;
  comment: string;
  rated_at: number;
}

export interface RatingsAggregate {
  listing_id: string;
  count: number;
  avg: number;
}

export interface RegistryEnvelope {
  ok: boolean;
  source: "remote" | "cache" | "seed";
  fetched_at: number;
  count: number;
  listings: Listing[];
}

export interface InstalledEnvelope {
  ok: boolean;
  count: number;
  installed: InstalledItem[];
}

export interface ListingPreview {
  description: string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  preview_url?: string | null;
}
