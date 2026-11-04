import { z } from 'zod';
import { jsonSchema, objectSchema } from './workspace';
export const collectionAppSchema = z.object({
  id: z.string(),
  version: z.string(),
  artifacts: z.array(z.object({ name: z.string(), sha256: z.string(), size: z.number() })),
});
export const collectionSchema = z.object({
  id: z.string(),
  schema: z.literal('symport.collection/1'),
  name: z.string(),
  profile: z.string(),
  apps: z.array(collectionAppSchema),
  updated: z.string().optional(),
});
export const collectionsSchema = z.object({
  collections: z.array(collectionSchema),
  templates: z.array(
    z.object({ id: z.string(), en: z.string(), ru: z.string(), ids: z.array(z.string()) }),
  ),
  profiles: z.record(
    z.string(),
    z.object({
      model: z.string(),
      symbian: z.string(),
      s60: z.string(),
      screen: z.array(z.number()),
    }),
  ),
});
export const recoverySchema = z.object({
  collection: z.string(),
  profile: z.string(),
  target: objectSchema,
  source_profile: z.string(),
  geometry_changed: z.boolean(),
  preview_sha256: z.string(),
  rows: z.array(
    z
      .object({
        id: z.string(),
        name: z.string(),
        status: z.string(),
        reasons: z.array(z.string()),
        sources: z.array(z.string()),
        compatibility: z.string(),
        requirements: z.array(z.string()).default([]),
        runtime_requirements: z.array(objectSchema).default([]),
      })
      .catchall(jsonSchema),
  ),
  transfer_ids: z.array(z.string()),
  problems: z.array(z.string()),
  partial: z.boolean(),
  instructions: z.array(z.object({ en: z.string(), ru: z.string() })),
  identity: objectSchema.nullable(),
});
export const measurementSchema = z.object({
  id: z.string(),
  time: z.string(),
  series: z.string(),
  connected: z.boolean(),
  model: z.string().nullable(),
  rm: z.string().nullable(),
  firmware: z.string().nullable(),
  transport: z.string().nullable(),
  usb_mode: z.string().nullable(),
  battery: z.number().nullable(),
  signal: z.number().nullable(),
  free: z.number().nullable(),
  total: z.number().nullable(),
  life_timer_hours: z.number().nullable(),
  capabilities: z.array(z.string()),
  capability_status: z.record(z.string(), z.object({ status: z.string() })),
  reasons: z.array(z.string()),
});
export const measurementsSchema = z.object({ measurements: z.array(measurementSchema) });
export const themeProjectSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    profile: z.string(),
    mode: z.enum(['clear', 'imported']),
    uid: z.number(),
    revision: z.number(),
    palette: z.record(z.string(), z.string()),
    wallpaper: z.boolean(),
    icons: objectSchema,
    resources: z.array(
      z.object({
        id: z.string(),
        name: z.string(),
        target: z.string(),
        kind: z.string(),
        size: z.number(),
        sha256: z.string(),
        editable: z.boolean(),
        bitmaps: z
          .array(
            z.object({
              index: z.number(),
              width: z.number(),
              height: z.number(),
              depth: z.number(),
              compression: z.number(),
              editable: z.boolean(),
            }),
          )
          .optional(),
        structure: objectSchema.optional(),
      }),
    ),
    blockers: z.array(z.string()),
    build: z
      .object({ status: z.string(), sha256: z.string(), size: z.number(), signature: z.string() })
      .optional(),
    built_revision: z.number().nullish(),
    contrast: z.array(objectSchema).optional(),
  })
  .catchall(jsonSchema);
export const themeStudioSchema = z.object({
  projects: z.array(themeProjectSchema),
  profiles: z.record(z.string(), z.array(z.number())),
  palettes: z.record(z.string(), z.record(z.string(), z.string())),
  limitations: z.array(z.string()),
});
export type Collection = z.infer<typeof collectionSchema>;
export type ThemeProject = z.infer<typeof themeProjectSchema>;
