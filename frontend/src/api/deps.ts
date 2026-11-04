import { z } from 'zod';
import { jsonSchema } from './workspace';

const maybe = z.string().nullish();
const issueList = z.array(z.string());
const node = z.object({ id: z.string(), label: z.string(), kind: z.string(), status: maybe });
const edge = z.object({ from: z.string(), to: z.string(), kind: z.string() });
export const dependencySchema = z
  .object({
    schema: z.string(),
    package: z.object({ name: z.string(), uid: maybe, file: z.string(), version: maybe }),
    target: z.record(z.string(), z.string()),
    target_profile: maybe,
    platform_verdict: z.string(),
    platforms: z.array(
      z.object({
        uid: z.string(),
        label: z.string(),
        symbian: maybe,
        relation: z.string(),
        basis: z.string(),
        source: maybe,
      }),
    ),
    declared: z.array(
      z.object({
        uid: maybe,
        name: z.string(),
        runtime: maybe,
        min_version: maybe,
        max_version: maybe,
        status: z.string(),
        matched_package: z
          .object({ uid: z.string(), name: z.string(), basis: z.string() })
          .nullish(),
      }),
    ),
    runtimes: z.array(
      z.object({
        id: z.string(),
        title: z.string(),
        via: z.array(z.string()),
        status: z.string(),
        min_version: maybe,
        dlls: z.array(z.string()),
        distribution: z.string(),
      }),
    ),
    system_imports: z.array(
      z.object({
        dll: z.string(),
        runtime: maybe,
        status: z.string(),
        used_by: z.array(z.string()),
      }),
    ),
    binaries: z.array(
      z
        .object({
          target: maybe,
          kind: z.string().optional(),
          compression: z.string().optional(),
          imports: z.array(z.string()).nullish(),
          capabilities: z.array(z.string()).nullish(),
        })
        .catchall(jsonSchema.optional()),
    ),
    capabilities: z.array(z.string()),
    restricted_capabilities: z.array(z.string()),
    issues: issueList,
    verdict: z.string(),
    firmware: z.object({ source: maybe, dll_count: z.number() }).nullish(),
    levels: z.record(z.string(), z.string()),
    limitations: z.array(z.string()),
    graph: z.object({ nodes: z.array(node), edges: z.array(edge) }),
  })
  .catchall(jsonSchema.optional());
export type DependencyAnalysis = z.infer<typeof dependencySchema>;

export const bundleSchema = z
  .object({
    schema: z.string(),
    status: z.enum(['complete', 'incomplete']),
    order: z.array(
      z.object({
        position: z.number(),
        file: z.string(),
        name: z.string(),
        role: z.string(),
        uid: z.string(),
        version: z.string(),
        size: z.number(),
        sha256: z.string(),
      }),
    ),
    unresolved: z.array(
      z
        .object({ name: z.string(), min_version: maybe, status: z.string() })
        .catchall(jsonSchema.optional()),
    ),
    unused_runtimes: z.array(z.string()),
    instructions: z.array(z.string()),
    limitations: z.array(z.string()),
    analysis: dependencySchema,
    zip: z.string().nullable(),
    zip_name: z.string().nullable(),
  })
  .catchall(jsonSchema.optional());
export type Bundle = z.infer<typeof bundleSchema>;
