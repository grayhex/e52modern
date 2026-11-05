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

// ---- Symbian TLS / CA revival ----
const stackCell = z.object({
  status: z.enum(['documented', 'not-applicable', 'unknown']),
  tested: z.string(),
  basis: z.string(),
  source: z.string(),
  abi: z.string().nullish(),
  firmware: z.string(),
  capabilities: z.string().nullish(),
  patch_version: z.string(),
  covered_by: z.string().nullish(),
});
export const tlsStateSchema = z.object({
  device: z.string().nullish(),
  reason: z.string().nullish(),
  components: z.array(
    z.object({
      id: z.string(),
      title: bilingual,
      role: z.string(),
      name: z.string(),
      size: z.number(),
      sha256: z.string(),
      version: z.string(),
      released: z.string(),
      author: z.string(),
      homepage: z.string(),
      source_repository: z.string(),
      licence: z.object({ spdx: z.string(), url: z.string(), note: z.string() }),
      release_notes: z.string(),
      release_notes_text: z.string(),
      depends_on: z.array(z.string()),
      risk: z.enum(['low', 'medium', 'high']),
      observed_at: z.string(),
      cached: z.boolean(),
      device: z.object({
        state: z.string(),
        at: z.string().nullish(),
        source: z.string().nullish(),
      }),
    }),
  ),
  stacks: z.record(z.string(), z.object({ title: bilingual, note: bilingual })),
  app_kinds: z.record(z.string(), z.object({ title: bilingual, stack: z.string() })),
  applicability: z.array(
    z.object({
      target: z.string(),
      name: z.string(),
      s60: z.string(),
      symbian: z.string().nullish(),
      stacks: z.record(z.string(), stackCell),
    }),
  ),
  https: z.object({ state: z.string(), at: z.string().nullish(), host: z.string().nullish() }),
  test_hosts: z.array(z.string()),
  statement: z.string(),
});
export const tlsKitSchema = z.object({
  device: z.string().nullish(),
  reason: z.string().nullish(),
  checks: z.array(checkSchema),
  steps: z.array(
    z.object({
      id: z.string(),
      title: bilingual,
      risk: z.enum(['low', 'medium', 'high']),
      version: z.string(),
      sha256: z.string(),
      size: z.number(),
      licence: z.string(),
      obtained: z.boolean(),
      device: z.object({ state: z.string() }),
      transfer: z.object({ execution: z.string(), status: STATUS }),
      install: z.object({ execution: z.string(), steps: z.array(bilingual) }),
      restore: bilingual,
      high_risk: z
        .object({
          status: z.enum(['ready', 'needs-action']),
          requirements: z.array(bilingual),
          privileged_adapter: z.string(),
          statement: bilingual,
        })
        .optional(),
    }),
  ),
  app_kind: z.string().nullish(),
  stack: z.string().nullish(),
  stack_support: z
    .object({
      status: z.string(),
      tested: z.string().optional(),
      covered_by: z.string().nullish(),
      reason: bilingual.optional(),
    })
    .passthrough()
    .nullish(),
  statement: z.string(),
});
export const tlsDiagnoseSchema = z.object({
  host: z.string(),
  server_probe: z
    .object({
      ran_on: z.string(),
      ok: z.boolean(),
      error: z.string().nullish(),
      tls_version: z.string().nullish(),
      meaning: z.string(),
      leaf: z
        .object({
          subject: z.string(),
          issuer: z.string(),
          not_before: z.string().nullish(),
          not_after: z.string().nullish(),
        })
        .nullish(),
    })
    .passthrough(),
  bridge_probe: z.object({ status: z.string(), reason: z.string() }),
  phone_test: z.object({ instructions: bilingual }),
  clock: z
    .object({
      server_utc: z.string(),
      phone_date: z.string().nullish(),
      skew_days: z.number().nullish(),
      verdict: z.string(),
      certificate_window: z.string().optional(),
    })
    .passthrough(),
  chain: z.object({ status: z.string(), reason: z.string() }),
});

// ---- Recovery Safety Net ----
export const safetyPlanSchema = z.object({
  id: z.string(),
  scenario: z.string(),
  label: z.string(),
  status: z.string(),
  folder: z.string(),
  device: z
    .object({
      model: z.string().nullish(),
      rm: z.string().nullish(),
      firmware: z.string().nullish(),
    })
    .passthrough(),
  items: z.array(
    z.object({
      name: z.string(),
      path: z.string(),
      sha256: z.string(),
      size: z.number(),
      state: z.string(),
      created: z.boolean(),
      removed: z.boolean().optional(),
    }),
  ),
  dry_run: z.object({
    new_files: z.number(),
    bytes: z.number(),
    folder_exists: z.boolean(),
    conflicts: z.array(z.string()),
    identical_preexisting: z.array(z.string()),
    free_before: z.number().nullish(),
    free_after: z.number().nullish(),
    note: z.string(),
  }),
  risk: z
    .object({ level: z.enum(['low', 'medium', 'high']), irreversible: z.boolean().optional() })
    .passthrough(),
  restore: z.object({ kind: z.string(), note: z.string().optional() }).passthrough(),
  phone_actions: z.array(
    z
      .object({ component: z.string(), steps: z.array(bilingual), restore: bilingual })
      .passthrough(),
  ),
  snapshot: z
    .object({ at: z.string(), kinds: z.record(z.string(), z.string()), statement: z.string() })
    .passthrough()
    .nullish(),
  blocking: z.array(
    z.object({ code: z.string(), text: bilingual, satisfied_by: z.string() }).passthrough(),
  ),
  checklist: z.record(
    z.string(),
    z.object({ result: z.string(), source: z.string() }).passthrough(),
  ),
  acknowledged: z.array(z.string()).optional(),
  statement: z.string(),
  rollback_scope: z.string(),
  events: z.array(
    z.object({ at: z.string(), action: z.string(), status: z.string() }).passthrough(),
  ),
});
export const safetyStateSchema = z.object({
  plans: z.array(
    z.object({
      id: z.string(),
      scenario: z.string(),
      label: z.string(),
      created: z.string(),
      status: z.string(),
      items: z.number(),
      risk: z.string(),
    }),
  ),
  checklist_items: z.array(z.string()),
  statement: z.string(),
});
export const postflightSchema = z.object({
  connected: z.boolean(),
  identity: z.string().optional(),
  diff: z
    .array(z.object({ field: z.string(), before: z.unknown(), after: z.unknown() }))
    .optional(),
  files: z.array(z.object({ path: z.string(), state: z.string() })).optional(),
  installation: z.string().optional(),
  statement: z.string(),
});
export const rollbackSchema = z
  .object({
    dry_run: z.boolean(),
    scope: z.string(),
    files: z.array(z.object({ path: z.string() })).optional(),
    removed: z.array(z.string()).optional(),
    conflicts: z.array(z.string()).optional(),
    status: z.string().optional(),
  })
  .passthrough();
export const exportSchema = z.object({ name: z.string(), mime: z.string(), content: z.string() });
export type SafetyPlan = z.infer<typeof safetyPlanSchema>;
