import { z } from 'zod';
import { imageListSchema } from './firmware';

const bilingual = z.object({ en: z.string(), ru: z.string() });
export { imageListSchema };
export const cfwSourcesSchema = z.object({
  sources: z.array(
    z.object({
      id: z.string(),
      family: z.string(),
      title: bilingual,
      kind: z.string(),
      platform: z.string(),
      models: z.array(z.object({ name: z.string(), rm: z.string() })),
      release: z.object({ version: z.string(), date: z.string() }),
      links: z.record(z.string(), z.string()),
      limitations: z.array(z.string()),
      distribution: z.string(),
      symport: z.record(z.string(), z.string()),
      advisories: z.array(z.string()),
    }),
  ),
  advisories: z.record(
    z.string(),
    z.object({
      title: z.string(),
      published: z.string(),
      severity: z.object({
        cvss_v3_1: z.number(),
        rating: z.string(),
        scored_by: z.string(),
        author_claim: z.string(),
      }),
      platform: z.string(),
      sources: z.array(z.object({ label: z.string(), url: z.string() })),
      caveats: z.array(z.string()),
    }),
  ),
  db_version: z.string(),
  containers: z.record(z.string(), z.string()),
  note: z.string(),
});
export const inventorySchema = z.object({
  id: z.string(),
  baseline: z.boolean(),
  categories: z.record(
    z.string(),
    z.object({
      basis: z.string(),
      items: z.array(
        z
          .object({
            path: z.string().optional(),
            url: z.string().optional(),
            origin: z.string().optional(),
            basis: z.string().optional(),
          })
          .passthrough(),
      ),
    }),
  ),
  statement: z.string(),
});
export const scanSchema = z.object({
  id: z.string(),
  verdict: z.enum([
    'vulnerable-version',
    'suspicious-pattern',
    'no-pattern-found',
    'unknown',
    'not-tested',
  ]),
  findings: z.array(
    z.object({
      rule: z.string(),
      title: z.string(),
      status: z.string(),
      path: z.string(),
      sha256: z.string(),
      offset: z.number(),
      advisory: z.string().nullish(),
      reliability: z.string(),
    }),
  ),
  declared_versions: z.array(z.object({ advisory: z.string(), basis: z.string() }).passthrough()),
  coverage: z.object({ files_scanned: z.number(), not_tested_total: z.number() }).passthrough(),
  proof_of_safety: z.literal(false),
  db_version: z.string(),
  statement: z.string(),
});
export const eka1Schema = z.object({
  report: z
    .object({
      status: z.enum(['converted', 'accepted-by-emulator', 'booted', 'unsupported']),
      reason: z.string().optional(),
      accepted_by_emulator: z.string(),
      booted: z.string(),
      real_image_tested: z.boolean(),
      output: z.object({ size: z.number(), sha256: z.string(), entries: z.number() }).optional(),
      limitations: z.array(z.string()).optional(),
    })
    .passthrough(),
  rpkg: z.string(),
  rpkg_name: z.string().nullish(),
  report_name: z.string(),
  report_json: z.string(),
});
