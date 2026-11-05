import { z } from 'zod';

const bilingual = z.object({ en: z.string(), ru: z.string() });
export const STATUS = z.enum(['ready', 'needs-action', 'unknown', 'unsupported']);
export type ReviveStatus = z.infer<typeof STATUS>;
export const checkSchema = z.object({
  id: z.string(),
  status: STATUS,
  reason: bilingual,
  basis: z.string(),
  source: z.string(),
});
export const factSchema = z.object({
  value: z.union([z.string(), z.number(), z.array(z.string()), z.null()]),
  source: z.enum(['observed', 'documented', 'manual', 'unknown']),
  note: z.string().nullish(),
});
export const deviceBriefSchema = z.object({
  id: z.string(),
  name: z.string().nullish(),
  model: z.string().nullish(),
  transport: z.string().nullish(),
  connected: z.boolean(),
});
const manualSchema = z.object({ model: z.string(), rm: z.string(), firmware: z.string() });
export const inspectSchema = z.object({
  device: z.string().nullish(),
  devices: z.array(deviceBriefSchema),
  reason: z.string().nullish(),
  connected: z.boolean(),
  facts: z.record(z.string(), factSchema),
  manual: manualSchema,
  conflict: z.object({ observed: z.string().nullish(), manual: z.string().nullish() }).nullish(),
  checks: z.array(checkSchema),
  baseline: z.string().nullish(),
});
export const operationSchema = z.object({
  id: z.string(),
  title: bilingual,
  risk: z.enum(['low', 'medium', 'high']),
  execution: z.enum(['read-only', 'bridge-transfer', 'manual-on-phone']),
  prerequisites: z.array(z.object({ id: z.string(), status: STATUS })),
  source: z.object({ kind: z.string(), ref: z.string() }),
  version: z.string().nullish(),
  sha256: z.string().nullish(),
  restore_point: z.string(),
  status: STATUS,
  note: bilingual.nullish(),
  result: z.object({
    result: z.string(),
    at: z.string().nullish(),
    source: z.string().nullish(),
    note: z.string().nullish(),
  }),
  blocking: z.array(z.string()),
});
export const profileSchema = z.object({
  id: z.string(),
  title: bilingual,
  summary: bilingual,
  targets: z.array(z.string()),
  operations: z.array(z.string()),
});
export const stateSchema = z.object({
  profiles: z.record(z.string(), profileSchema),
  planning_margin: z.number(),
  rights_scopes: z.array(z.string()),
});
export const planSchema = z.object({
  profile: profileSchema,
  device: z.string().nullish(),
  reason: z.string().nullish(),
  facts: z.record(z.string(), factSchema),
  manual: manualSchema,
  conflict: z.object({ observed: z.string().nullish(), manual: z.string().nullish() }).nullish(),
  checks: z.array(checkSchema),
  operations: z.array(operationSchema),
  status: STATUS,
  statement: z.string(),
});
export const verifySchema = z.object({
  device: z.string(),
  connected: z.boolean(),
  baseline: z.string().nullish(),
  diff: z.array(
    z.object({
      field: z.string(),
      before: z.union([z.string(), z.number(), z.null()]),
      after: z.union([z.string(), z.number(), z.null()]),
      delta: z.number().optional(),
    }),
  ),
  phone_changed: z.boolean(),
  checks: z.array(checkSchema),
  operations: z.array(operationSchema),
  statement: z.string(),
});
export type Inspect = z.infer<typeof inspectSchema>;
export type Plan = z.infer<typeof planSchema>;
export type Operation = z.infer<typeof operationSchema>;
export type Check = z.infer<typeof checkSchema>;
export type Fact = z.infer<typeof factSchema>;
export const simpleSchema = z.object({}).passthrough();
