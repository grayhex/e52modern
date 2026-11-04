import { z } from 'zod';
import { jsonSchema, objectSchema } from './workspace';

const maybe = z.string().nullish();
export const imageSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    label: z.string().optional(),
    size: z.number(),
    kind: z.string(),
    created: z.string(),
    status: z.enum(['indexing', 'ready', 'failed']),
    progress: z.object({ done: z.number(), total: z.number() }),
    error: maybe,
    files: z.number().nullish(),
  })
  .catchall(jsonSchema.optional());
export const imageListSchema = z.object({ images: z.array(imageSchema) });
export const statusSchema = imageSchema.extend({
  counts: z
    .object({
      files: z.number(),
      bytes: z.number(),
      by_kind: z.record(z.string(), z.number()),
      e32: z.number(),
    })
    .optional(),
  skipped_count: z.number().optional(),
  limitations: z.array(z.string()).optional(),
  levels: z.record(z.string(), z.string()).optional(),
  rom: objectSchema.nullish(),
});
export const e32Lite = z.object({
  capabilities: z.array(z.string()).nullish(),
  is_dll: z.boolean(),
  secure_id: maybe,
  compression: z.string(),
  module_version: z.string(),
  kernel: z.string(),
  cpu: z.string(),
  imports_known: z.boolean(),
});
export const entrySchema = z
  .object({
    path: z.string(),
    name: z.string(),
    dir: z.string(),
    size: z.number(),
    kind: z.string(),
    basis: z.string(),
    sha256: maybe,
    uids: z.array(z.string()).nullish(),
    e32: e32Lite.optional(),
    parse_error: maybe,
  })
  .catchall(jsonSchema.optional());
export type FirmwareEntry = z.infer<typeof entrySchema>;
export const childrenSchema = z.object({
  dir: z.string(),
  folders: z.array(
    z.object({ name: z.string(), path: z.string(), files: z.number(), bytes: z.number() }),
  ),
  files: z.array(entrySchema),
  files_total: z.number(),
});
export const searchSchema = z.object({
  total: z.number(),
  offset: z.number(),
  entries: z.array(entrySchema),
});
export const fileSchema = z.object({
  entry: z
    .object({
      path: z.string(),
      name: z.string(),
      size: z.number(),
      kind: z.string(),
      basis: z.string(),
      sha256: maybe,
      uids: z.array(z.string()).nullish(),
      e32: objectSchema.optional(),
      mbm: objectSchema.optional(),
      mif: objectSchema.optional(),
      parse_error: maybe,
    })
    .catchall(jsonSchema.optional()),
  hex_head: z.string().nullable(),
  e32_full: objectSchema.nullable(),
  read_error: z.string().optional(),
});
export const depsSchema = z.object({
  path: z.string(),
  imports_known: z.boolean(),
  imports: z.array(z.object({ name: z.string(), resolved: maybe, status: z.string() })).nullable(),
  imported_by: z.array(z.string()),
  note: maybe,
});
export const compareSchema = z.object({
  a: z.object({ id: z.string().nullish(), name: z.string(), files: z.number() }),
  b: z.object({ id: z.string().nullish(), name: z.string(), files: z.number() }),
  summary: z.object({
    only_a: z.number(),
    only_b: z.number(),
    changed: z.number(),
    identical: z.number(),
    e32_changed: z.number(),
  }),
  only_a: z.array(z.string()),
  only_b: z.array(z.string()),
  changed: z.array(
    z
      .object({ path: z.string(), kind: z.string(), details: z.record(z.string(), jsonSchema) })
      .catchall(jsonSchema),
  ),
  truncated: z.object({ only_a: z.boolean(), only_b: z.boolean(), changed: z.boolean() }),
  basis: z.string(),
});
export const profileSchema = objectSchema;
