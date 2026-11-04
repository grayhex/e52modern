import { z } from 'zod';
export const jsonSchema = z.json();
export const objectSchema = z.record(z.string(), jsonSchema);
export const fileSchema = z.object({
  name: z.string(),
  content: z.string(),
  mime: z.string().optional(),
});
export const contactSchema = z
  .object({
    name: z.string(),
    given: z.string().nullish(),
    family: z.string().nullish(),
    phones: z.array(z.string()),
    emails: z.array(z.string()),
  })
  .catchall(jsonSchema);
export const personalRow = z
  .object({
    native_id: z.string().optional(),
    name: z.string().optional(),
    phones: z.array(z.string()).optional(),
    emails: z.array(z.string()).optional(),
    summary: z.string().optional(),
    kind: z.string().optional(),
    number: z.string().optional(),
    text: z.string().optional(),
    date: z.string().optional(),
    direction: z.string().optional(),
    state: z.string().optional(),
    recurrence: z.boolean().optional(),
    completed: z.boolean().nullish(),
  })
  .catchall(jsonSchema.optional());
export const snapshotSchema = z.object({
  snapshot: z.string(),
  fingerprint: z.string(),
  rows: z.array(personalRow),
  duplicates: z.array(z.array(z.number())).default([]),
});
export const planSchema = z.object({
  plan: z.string(),
  changes: z.array(z.object({ operation: z.string(), before: jsonSchema, after: jsonSchema })),
  conflicts: z.array(objectSchema),
  skipped: z.number(),
});
export const writeSchema = z
  .object({ status: z.string(), verified: z.number().optional(), backup: z.string().nullish() })
  .catchall(jsonSchema);
export const packageSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    kind: z.string().optional(),
    size: z.number().optional(),
    source: z.string().optional(),
  })
  .catchall(jsonSchema);
export const jobSchema = z
  .object({
    id: z.string(),
    action: z.string(),
    command: z.string(),
    status: z.string(),
    output: z.string(),
    started: z.string(),
    exit_code: z.number().nullable(),
    report: objectSchema.nullish(),
  })
  .catchall(jsonSchema);
export const stateSchema = z.object({
  packages: z.array(packageSchema),
  library: z.array(packageSchema),
  projects: z.array(z.string()),
  jobs: z.array(jobSchema),
  device_report: objectSchema,
  backups: z.array(objectSchema),
  backup_free: z.number().nullable(),
});
export const mediaItemSchema = z.object({
  name: z.string(),
  path: z.string(),
  revision: z.string(),
  kind: z.enum(['photo', 'audio', 'video']),
  size: z.number(),
  modified: z.number(),
  mime: z.string(),
});
export const mediaSchema = z.object({
  items: z.array(mediaItemSchema),
  truncated: z.boolean().optional(),
  skipped: z.number().optional(),
});
export const audioSourceSchema = z.object({
  id: z.string(),
  duration: z.number(),
  preview: z.string(),
});
export const audioOutputSchema = z.object({
  id: z.string(),
  version: z.string(),
  url: z.string(),
  duration: z.number(),
  size: z.number(),
  channels: z.number(),
  sample_rate: z.number(),
});
export type PersonalRow = z.infer<typeof personalRow>;
export type Snapshot = z.infer<typeof snapshotSchema>;
export type ChangePlan = z.infer<typeof planSchema>;
export type MediaItem = z.infer<typeof mediaItemSchema>;
// Decode optional metadata without propagating unknown/any through feature code.
export const payload = (value: unknown) =>
  objectSchema.parse(JSON.parse(JSON.stringify(value)) as unknown);
export function text(value: unknown): string {
  return typeof value === 'string' ? value : typeof value === 'number' ? String(value) : '';
}
export function entries(value: unknown) {
  return z.array(objectSchema).parse(value ?? []);
}
export function strings(value: unknown) {
  return z.array(z.string()).parse(value ?? []);
}
