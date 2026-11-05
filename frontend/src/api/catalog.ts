import { z } from 'zod';
import { jsonSchema, objectSchema } from './workspace';
export const appSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    category: z.string(),
    version: z.string(),
    format: z.string(),
    compatibility: z.string(),
    model_compatibility: z
      .record(
        z.string(),
        z
          .object({ status: z.string(), reason: z.string(), basis: z.string() })
          .catchall(jsonSchema),
      )
      .default({}),
    delivery: z.string(),
    network: z.string(),
    collection: z.array(z.string()),
    sources: z.array(z.string()),
    manual_url: z.string().nullish(),
    delivery_reason: z.string().nullish(),
  })
  .catchall(jsonSchema);
export const catalogJobSchema = z
  .object({
    id: z.string(),
    action: z.string(),
    created: z.string(),
    state: z.string(),
    error: z.string().nullish(),
    items: z.array(
      z
        .object({ id: z.string(), stage: z.string(), error: z.string().nullish() })
        .catchall(jsonSchema),
    ),
  })
  .catchall(jsonSchema);
export const catalogSchema = z.object({
  apps: z.array(appSchema),
  sets: z.record(z.string(), z.array(z.string())),
  jobs: z.array(catalogJobSchema),
  research: z.array(objectSchema),
});
export const catalogPlanSchema = z.object({
  ids: z.array(z.string()),
  bytes: z.number(),
  problems: z.array(z.string()),
  requirements: z.record(z.string(), z.array(z.string())),
});
export type CatalogApp = z.infer<typeof appSchema>;
export const guideSchema = z.object({
  title: z.string(),
  steps: z.array(z.string()),
  docs: z.string().optional(),
});
export const runtimeRequirementsSchema = z.array(
  z.object({
    runtime: z.string(),
    name: z.string(),
    min_version: z.string().nullish(),
    declared_in: z.string(),
    status: z.string(),
  }),
);
