// SYNC: claude-w80-fe-only
import { useMemo, useState } from "react";
import { Plus, Trash2, Code2 } from "lucide-react";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * <OutputSchemaBuilder /> — Wave 80-B
 *
 * Visual JSON Schema (Draft-07) builder. Operators add field rows
 * (name | type | description | required); enum values are entered as
 * comma-separated strings. The component is fully controlled — parent
 * owns the schema object and is notified via `onChange`.
 *
 * The output is shaped:
 *   { $schema, type: "object", properties: {...}, required: [...] }
 * — the smallest valid Draft-07 envelope an LLM structured-output
 * route will accept.
 */

export type FieldType = "string" | "number" | "boolean" | "enum";

export interface SchemaField {
  /** stable client-id, never serialised to the schema */
  id: string;
  name: string;
  type: FieldType;
  description: string;
  required: boolean;
  /** comma-separated user input; parsed on serialise */
  enumValues?: string;
}

export interface OutputSchema {
  $schema: "http://json-schema.org/draft-07/schema#";
  type: "object";
  properties: Record<string, JsonSchemaProp>;
  required: string[];
  additionalProperties: false;
}

export interface JsonSchemaProp {
  type: "string" | "number" | "boolean";
  description?: string;
  enum?: string[];
}

interface OutputSchemaBuilderProps {
  fields: SchemaField[];
  onChange: (next: SchemaField[]) => void;
}

let _fid = 1;
function newFieldId(): string {
  return `f${++_fid}-${Date.now().toString(36).slice(-4)}`;
}

export function makeEmptyField(): SchemaField {
  return {
    id: newFieldId(),
    name: "",
    type: "string",
    description: "",
    required: false,
  };
}

export function fieldsToSchema(fields: SchemaField[]): OutputSchema {
  const properties: Record<string, JsonSchemaProp> = {};
  const required: string[] = [];
  for (const f of fields) {
    const name = f.name.trim();
    if (!name) continue;
    let prop: JsonSchemaProp;
    if (f.type === "enum") {
      const values = (f.enumValues ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      prop = { type: "string", enum: values };
    } else {
      prop = { type: f.type };
    }
    if (f.description.trim()) prop.description = f.description.trim();
    properties[name] = prop;
    if (f.required) required.push(name);
  }
  return {
    $schema: "http://json-schema.org/draft-07/schema#",
    type: "object",
    properties,
    required,
    additionalProperties: false,
  };
}

export function OutputSchemaBuilder({ fields, onChange }: OutputSchemaBuilderProps) {
  const [showJson, setShowJson] = useState(false);

  const schema = useMemo(() => fieldsToSchema(fields), [fields]);

  const update = (id: string, patch: Partial<SchemaField>) => {
    onChange(fields.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  };
  const remove = (id: string) => onChange(fields.filter((f) => f.id !== id));
  const add = () => onChange([...fields, makeEmptyField()]);

  return (
    <div className="rounded-[12px] border border-line-strong bg-bg-1/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          output schema · json-schema draft-07
        </div>
        <button
          type="button"
          onClick={() => setShowJson((v) => !v)}
          className="inline-flex items-center gap-1.5 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2 hover:text-ink"
        >
          <Code2 size={11} strokeWidth={1.7} aria-hidden />
          {showJson ? "hide json" : "preview json"}
        </button>
      </div>
      <BrandHairline variant="static" />

      <ul className="mt-3 grid gap-2">
        {fields.map((f) => (
          <li
            key={f.id}
            className="grid grid-cols-[1.4fr_0.8fr_2fr_auto_auto] items-start gap-2 rounded-md border border-line/60 bg-bg-2/40 p-2"
          >
            <input
              value={f.name}
              onChange={(e) => update(f.id, { name: e.target.value })}
              placeholder="field_name"
              className="rounded border border-line bg-bg-0 px-2 py-1.5 font-mono-tech text-[11.5px] text-ink outline-none focus:border-accent"
              aria-label="field name"
            />
            <select
              value={f.type}
              onChange={(e) =>
                update(f.id, { type: e.target.value as FieldType })
              }
              className="rounded border border-line bg-bg-0 px-2 py-1.5 font-mono-tech text-[11.5px] text-ink outline-none focus:border-accent"
              aria-label="field type"
            >
              <option value="string">string</option>
              <option value="number">number</option>
              <option value="boolean">boolean</option>
              <option value="enum">enum</option>
            </select>
            <div className="grid gap-1">
              <input
                value={f.description}
                onChange={(e) => update(f.id, { description: e.target.value })}
                placeholder="description (helps the model decide)"
                className="rounded border border-line bg-bg-0 px-2 py-1.5 text-[12px] text-ink outline-none focus:border-accent"
                aria-label="field description"
              />
              {f.type === "enum" && (
                <input
                  value={f.enumValues ?? ""}
                  onChange={(e) => update(f.id, { enumValues: e.target.value })}
                  placeholder="comma,separated,values"
                  className="rounded border border-line bg-bg-0 px-2 py-1.5 font-mono-tech text-[11px] text-ink outline-none focus:border-accent"
                  aria-label="enum values"
                />
              )}
            </div>
            <label className="inline-flex items-center gap-1.5 self-center font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-2">
              <input
                type="checkbox"
                checked={f.required}
                onChange={(e) => update(f.id, { required: e.target.checked })}
                className="accent-accent"
                aria-label="required"
              />
              req
            </label>
            <button
              type="button"
              onClick={() => remove(f.id)}
              className="self-center rounded p-1 text-ink-3 transition-colors hover:bg-alert/10 hover:text-alert"
              aria-label="remove field"
            >
              <Trash2 size={13} strokeWidth={1.7} />
            </button>
          </li>
        ))}
        {fields.length === 0 && (
          <li className="rounded-md border border-dashed border-line bg-bg-2/30 px-3 py-4 text-center font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
            no fields yet — add one below
          </li>
        )}
      </ul>

      <button
        type="button"
        onClick={add}
        className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-line bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink-2 hover:border-accent hover:text-ink"
      >
        <Plus size={11} strokeWidth={1.8} aria-hidden /> add field
      </button>

      {showJson && (
        <pre className="mt-4 max-h-64 overflow-auto rounded-md border border-line/60 bg-bg-0 p-3 font-mono-tech text-[10.5px] leading-[1.55] text-ink-2">
{JSON.stringify(schema, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default OutputSchemaBuilder;
