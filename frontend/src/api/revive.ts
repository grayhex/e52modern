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

// ---- Reborn Hybrid CFW (N95) ----
export const rebornStateSchema = z.object({
  card: z
    .object({
      title: bilingual,
      not_a_flash: bilingual,
      author: z.string(),
      author_page: z.string(),
      index_page: z.string(),
      version: z.string(),
      release_date: z.string().nullish(),
      changelog: z.string().nullish(),
      expected_name: z.string(),
      distribution: z.object({ status: z.string(), note: bilingual }),
      compatibility: z.record(z.string(), z.string()),
      prerequisites: z.array(z.string()),
      warnings: z.array(z.string()),
      pinned_artifacts: z.array(z.unknown()),
    })
    .passthrough(),
  device: z.string().nullish(),
  reason: z.string().nullish(),
  variant: z
    .object({ status: z.enum(['blocked', 'candidate']), code: z.string(), reason: bilingual })
    .passthrough(),
  checks: z.array(checkSchema),
  pin: z
    .object({ sha256: z.string(), name: z.string(), pinned_at: z.string(), source: z.string() })
    .nullish(),
  artifact_present: z.boolean(),
  backups: z.object({ count: z.number(), latest: z.string().nullish(), note: z.string() }),
  data_backup: z.object({ at: z.string(), source: z.string() }).nullish(),
  stages: z.record(z.string(), z.object({ result: z.string(), source: z.string() }).passthrough()),
  postcheck_items: z.array(z.string()),
  statement: z.string(),
});
export const rebornImportSchema = z.object({
  sha256: z.string(),
  size: z.number(),
  name: z.string(),
  name_matches: z.boolean(),
  expected_name: z.string(),
  signature: z.string(),
  platform_verdict: z.string(),
  issues: z.array(z.string()),
  restricted_capabilities: z.array(z.unknown()),
  files: z.array(
    z.object({ target: z.string(), high_risk: z.boolean(), reasons: z.array(z.string()) }),
  ),
  high_risk_count: z.number(),
  modifications: z.array(
    z.object({
      category: z.string(),
      status: z.string(),
      evidence: z.array(z.string()),
      basis: z.string(),
    }),
  ),
  tls_overlap: z.array(z.string()),
  tls_state: z.record(z.string(), z.string()),
  version_check: z.object({
    package: z.string().nullish(),
    author_claim: z.string(),
    status: z.string(),
  }),
  pinned: z.boolean(),
  differs_from_pin: z.boolean(),
  statement: z.string(),
});
export const rebornStageSchema = z.object({
  stages: z.record(z.string(), z.object({ result: z.string() }).passthrough()),
  success: z.string(),
});

// ---- Revive home + legacy services ----
export const homeSchema = z.object({
  device: z.string().nullish(),
  reason: z.string().nullish(),
  profile: z.string().nullish(),
  sections: z.array(z.object({ id: z.string(), available: z.boolean() })),
  recommendations: z.array(
    z.object({
      id: z.string(),
      area: z.string(),
      title: bilingual,
      basis: z.string(),
      action: z.string(),
    }),
  ),
  history: z.array(
    z.object({
      at: z.string().nullish(),
      kind: z.string(),
      item: z.string(),
      result: z.string().nullish(),
      source: z.string(),
    }),
  ),
  statement: z.string(),
});
const serviceStatus = z.enum([
  'available',
  'manual-setup-required',
  'not-confirmed',
  'unsupported',
]);
export const servicesStateSchema = z.object({
  device: z.string().nullish(),
  reason: z.string().nullish(),
  profile: z.string().nullish(),
  services: z.array(
    z.object({
      id: z.string(),
      title: bilingual,
      category: z.string(),
      description: z.string(),
      original_url: z.string().nullish(),
      original_url_note: z.string().nullish(),
      apply_method: z.string(),
      host_probeable: z.boolean(),
      origin: z.object({ kind: z.string() }).passthrough(),
      substitute: z
        .object({
          entry: z.string().nullish(),
          final_url: z.string().nullish(),
          trust: z.string(),
          mechanism: z.string(),
        })
        .passthrough()
        .nullish(),
      record: z
        .object({ result: z.string(), at: z.string(), restore: bilingual })
        .passthrough()
        .nullish(),
    }),
  ),
  matrix: z.array(
    z.object({
      target: z.string(),
      name: z.string(),
      services: z.record(z.string(), z.object({ status: serviceStatus, reason: bilingual })),
    }),
  ),
  bridge: z.object({ status: z.string(), requirements: z.array(z.string()), note: z.string() }),
  statement: z.string(),
});
export const servicesDiagnoseSchema = z.object({
  ran_on: z.string(),
  results: z.array(
    z
      .object({
        id: z.string(),
        status: z.string(),
        reason: z.string().optional(),
        live_target: z.string().nullish(),
      })
      .passthrough(),
  ),
  statement: z.string(),
});

// ---- Device Agent ----
export const agentStateSchema = z.object({
  protocol: z.string(),
  status: z.enum(['not-installed', 'not-paired', 'pairing', 'paired']),
  agent_binary: z.string(),
  levels: z.array(z.string()),
  agent: z
    .object({
      agent_version: z.string().nullish(),
      model: z.string().nullish(),
      synthetic: z.boolean().nullish(),
    })
    .passthrough()
    .nullish(),
  permissions: z.record(z.string(), z.number()),
  operations: z.record(
    z.string(),
    z.object({
      tier: z.enum(['read', 'confirmed']),
      permission: z.string().nullish(),
      consent: z.boolean(),
      evidence: z.string(),
    }),
  ),
  forbidden: z.array(z.string()),
  statement: z.string(),
});
// ---- Add-ons and Patch Manager ----
const decisionSchema = z.object({
  decision: z.enum(['blocked', 'manual-only', 'ready-to-prepare']),
  blocks: z.array(z.object({ code: z.string(), text: bilingual })),
  warnings: z.array(z.string()),
  steps: z.array(bilingual),
  rollback: bilingual,
  statement: z.string(),
});
export const addonsStateSchema = z.object({
  device: z.string().nullish(),
  reason: z.string().nullish(),
  categories: z.record(
    z.string(),
    z.object({ title: bilingual, closed_by_default: z.boolean(), open: z.boolean() }),
  ),
  addons: z.array(
    z.object({
      id: z.string(),
      title: bilingual,
      category: z.string(),
      risk: z.enum(['low', 'medium', 'high']),
      source: z.object({ author: z.string(), url: z.string() }),
      licence: z.object({
        spdx: z.string().nullish(),
        url: z.string().nullish(),
        status: z.string().optional(),
      }),
      version: z.string().nullish(),
      version_confirmed: z.boolean(),
      install: bilingual,
      uninstall: bilingual,
      mode: z.enum(['pinned-artifact', 'manual-only']),
      decision: decisionSchema.nullish(),
      levels: z.object({
        downloaded: z.boolean(),
        transferred: z.boolean(),
        'user-confirmed-installed': z.boolean(),
        'verified-on-device': z.string(),
      }),
      update_available: z.boolean(),
    }),
  ),
  patches: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      source: z.string(),
      state: z.string(),
      autostart_via: z.string().nullish(),
      risk: z.string(),
      notes: z.string(),
      recorded_for: z.object({
        model: z.string().nullish(),
        rm: z.string().nullish(),
        firmware: z.string().nullish(),
      }),
    }),
  ),
  patch_warnings: z.array(
    z.object({ code: z.string(), patch: z.string(), detail: z.string().optional() }),
  ),
  patch_manager: z.object({ agent_inventory: z.string(), writes: z.string(), note: z.string() }),
  statement: z.string(),
});
export const addonPlanSchema = decisionSchema.extend({
  addon: z.string(),
  action: z.string(),
  dry_run: z.boolean(),
});

// ---- Settings and databases ----
export const settingsStateSchema = z.object({
  device: z.string().nullish(),
  reason: z.string().nullish(),
  categories: z.array(
    z.object({
      id: z.string(),
      level: z.enum(['exportable', 'unverified', 'unavailable', 'manual-only']),
      reason: bilingual,
      sensitive: z.boolean(),
      restore: z.boolean(),
    }),
  ),
  backups: z.array(
    z.object({
      id: z.string(),
      created: z.string(),
      categories: z.record(
        z.string(),
        z.object({ status: z.string(), count: z.number(), sensitive: z.boolean() }),
      ),
      device: z.object({ model: z.string().nullish(), rm: z.string().nullish() }).passthrough(),
    }),
  ),
  levels: z.array(z.string()),
  statement: z.string(),
});
export const restorePreviewSchema = z.object({
  backup: z.string(),
  category: z.string(),
  other_phone: z.boolean(),
  snapshot: z.string(),
  plan: z.string().nullish(),
  changes: z.array(z.object({ operation: z.string() }).passthrough()),
  conflicts: z.array(z.unknown()),
  blocked: z.boolean(),
  blocking: z.array(z.string()),
  statement: z.string(),
});
export const restoreResultSchema = z.object({
  level: z.string(),
  statement: z.string(),
  checkpoint: z.string().nullish(),
});
export const settingsDownloadSchema = z.object({
  name: z.string(),
  mime: z.string(),
  content: z.string(),
  warning: z.string(),
});

// ---- Verified Essentials ----
export const essentialsListSchema = z.object({
  profiles: z.array(
    z.object({
      id: z.string(),
      title: bilingual,
      models: z.array(z.string()),
      apps: z.array(z.string()),
    }),
  ),
  guide: z.object({ en: z.array(z.string()), ru: z.array(z.string()) }),
  note: z.string(),
});
export const essentialsSchema = z.object({
  profile: z.string(),
  title: bilingual,
  model: z.string(),
  applicable: z.boolean(),
  reason: z.string().optional(),
  items: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      version: z.string().optional(),
      licence: z.string().nullish(),
      eligible: z.boolean(),
      reasons: z.array(z.string()),
      size: z.number().optional(),
      network: z.string().optional(),
      evidence: z
        .object({
          declared: z.string(),
          model: z.string(),
          hardware: z.string(),
          installation: z.string(),
        })
        .passthrough()
        .optional(),
    }),
  ),
  eligible_ids: z.array(z.string()),
  order: z.array(z.string()),
  bytes: z.number(),
  statement: z.string(),
});

// ---- Media to Nokia ----
export const mediaPresetsSchema = z.object({
  model: z.string(),
  screen: z.object({ width: z.number(), height: z.number() }).passthrough(),
  presets: z.record(
    z.string(),
    z.array(
      z.object({
        id: z.string(),
        title: bilingual,
        ext: z.string(),
        hardware: z.string(),
        basis: z.string(),
      }),
    ),
  ),
  statement: z.string(),
});
export const mediaSourceSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    size: z.number(),
    sha256: z.string(),
    kind: z.enum(['video', 'audio', 'image']),
    duration: z.number().optional(),
  })
  .passthrough();
export const mediaJobSchema = z.object({
  id: z.string(),
  state: z.enum(['queued', 'running', 'done', 'failed']),
  stage: z.string(),
  queue_position: z.number(),
  kind: z.string(),
  preset: z.string(),
  model: z.string(),
  estimate_bytes: z.number(),
  error: z.string().nullish(),
  output: z.object({ name: z.string(), size: z.number(), sha256: z.string() }).nullish(),
  preview: z.string().nullish(),
  outcomes: z.object({
    exported: z.boolean(),
    transferred: z.boolean(),
    'played-on-device': z.string(),
  }),
  hardware: z.string(),
  basis: z.string(),
});
export const mediaExportSchema = z.object({
  name: z.string(),
  content: z.string(),
  report_name: z.string(),
  report: z.string(),
});
