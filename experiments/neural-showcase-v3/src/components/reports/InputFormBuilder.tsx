// SYNC: claude-w103-reports
/**
 * Wave 103 — auto-generates a form from the template input schema.
 *
 * The schema dialect mirrors ``backend/core/reports/templates_lib.py``
 * (see Wave 103 spec). Complex shapes (object + nested array of
 * object) degrade to a JSON textarea so the operator can still
 * supply data without us shipping a deep form library.
 */

import { useCallback } from "react";
import type { FieldSchema, RunInputs } from "./types";

type Props = {
  schema: Record<string, FieldSchema>;
  values: RunInputs;
  onChange: (next: RunInputs) => void;
};

export function InputFormBuilder({ schema, values, onChange }: Props) {
  const setField = useCallback(
    (k: string, v: unknown) => {
      const next = { ...values, [k]: v };
      onChange(next);
    },
    [values, onChange],
  );

  const fields = Object.keys(schema || {});
  if (fields.length === 0) {
    return (
      <p className="text-[12.5px] text-ink-3">
        This template has no input fields.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {fields.map((name) => {
        const spec = schema[name] || {};
        const label = spec.label || name;
        const required = !!spec.required;
        const fieldId = `report-field-${name}`;
        return (
          <div key={name} className="flex flex-col gap-1">
            <label
              htmlFor={fieldId}
              className="text-[12px] font-medium text-ink"
            >
              {label}
              {required && (
                <span aria-hidden className="ml-1 text-[var(--brand-cyan)]">
                  *
                </span>
              )}
            </label>
            {spec.description && (
              <p className="text-[11.5px] text-ink-3">{spec.description}</p>
            )}
            {renderInput(fieldId, name, spec, values[name], setField)}
          </div>
        );
      })}
    </div>
  );
}

function renderInput(
  id: string,
  name: string,
  spec: FieldSchema,
  value: unknown,
  set: (k: string, v: unknown) => void,
) {
  const t = spec.type || "string";
  const baseClass =
    "w-full rounded-sm border border-line bg-bg-0/60 px-3 py-2 text-[13px] text-ink outline-none transition-colors focus:border-[var(--brand-cyan)]";

  if (t === "string") {
    return (
      <input
        id={id}
        type="text"
        value={typeof value === "string" ? value : ""}
        onChange={(e) => set(name, e.target.value)}
        className={baseClass}
        required={!!spec.required}
      />
    );
  }
  if (t === "number" || t === "int") {
    return (
      <input
        id={id}
        type="number"
        step={t === "int" ? 1 : "any"}
        value={typeof value === "number" ? value : ""}
        onChange={(e) =>
          set(
            name,
            e.target.value === "" ? "" : Number(e.target.value),
          )
        }
        className={baseClass}
        required={!!spec.required}
      />
    );
  }
  if (t === "boolean") {
    return (
      <input
        id={id}
        type="checkbox"
        checked={!!value}
        onChange={(e) => set(name, e.target.checked)}
        className="h-4 w-4 accent-[var(--brand-cyan)]"
      />
    );
  }
  if (t === "array") {
    // Render as one-line-per-item textarea -- splits/joins on newlines.
    const items = Array.isArray(value) ? (value as unknown[]) : [];
    return (
      <textarea
        id={id}
        rows={4}
        value={items.map((x) => String(x ?? "")).join("\n")}
        onChange={(e) =>
          set(
            name,
            e.target.value
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean),
          )
        }
        placeholder="One item per line"
        className={baseClass + " font-mono-tech text-[12px]"}
      />
    );
  }
  // object (and anything else) -> JSON textarea fallback.
  return (
    <textarea
      id={id}
      rows={5}
      value={
        value === undefined
          ? ""
          : typeof value === "string"
            ? value
            : safeJson(value)
      }
      onChange={(e) => {
        const raw = e.target.value;
        try {
          const parsed = JSON.parse(raw);
          set(name, parsed);
        } catch {
          // Keep the raw string until valid JSON; surface a hint via title.
          set(name, raw);
        }
      }}
      placeholder='{"key": "value"}'
      className={baseClass + " font-mono-tech text-[12px]"}
      title="Object input — paste JSON. Invalid JSON is held until valid."
    />
  );
}

function safeJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
