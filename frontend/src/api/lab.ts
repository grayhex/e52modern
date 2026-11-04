import { z } from 'zod';
import { jsonSchema, objectSchema } from './workspace';
export const firmwareSchema = z
  .object({ code: z.string(), manufacturer: z.string().optional(), model: z.string().optional() })
  .catchall(jsonSchema);
export const labReportSchema = z
  .object({
    id: z.string(),
    kind: z.string(),
    status: z.string(),
    install: z.string(),
    launch: z.string(),
    running: z.boolean(),
    created: z.string(),
    updated: z.string().optional(),
    state: z.string().optional(),
    package: z.object({ name: z.string(), sha256: z.string() }).catchall(jsonSchema).nullish(),
    engine: z.string().optional(),
    screenshots: z
      .array(z.object({ name: z.string(), width: z.number(), height: z.number(), at: z.string() }))
      .optional(),
    events: z.array(objectSchema).optional(),
  })
  .catchall(jsonSchema);
export const uploadSchema = z
  .object({
    id: z.string(),
    slot: z.string(),
    name: z.string(),
    size: z.number(),
    consumed: z.boolean().optional(),
  })
  .catchall(jsonSchema);
export const labSchema = z
  .object({
    available: z.boolean(),
    reason: z.string().optional(),
    active: z.string().nullable(),
    current: z.string().nullable(),
    reports: z.array(labReportSchema),
    uploads: z.record(z.string(), uploadSchema),
    health: z
      .object({
        firmware: z.object({ devices: z.array(firmwareSchema) }).optional(),
        instance: z.object({ running: z.boolean() }).optional(),
        defaults: z.object({ symbian: z.string().nullish() }).optional(),
      })
      .optional(),
    control_reason: z.string().optional(),
    keys: z.object({ keys: objectSchema }).optional(),
    java: objectSchema,
  })
  .catchall(jsonSchema);
export const inspectorSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    kind: z.string(),
    sha256: z.string(),
    compatibility: z.string(),
    package: z
      .object({ uid: z.number(), version: z.array(z.number()), vendor_names: z.array(z.string()) })
      .catchall(jsonSchema),
    signatures: z.object({ status: z.string(), trust: z.string() }).catchall(jsonSchema),
    capabilities: z.array(z.string()),
    recommendations: z.record(z.string(), z.array(z.string())),
  })
  .catchall(jsonSchema);
export type LabReport = z.infer<typeof labReportSchema>;
