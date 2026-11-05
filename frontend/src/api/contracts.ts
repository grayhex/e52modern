import { z } from 'zod';
const maybeText = z.string().nullish();
const maybeNumber = z.number().nullish();
export const capabilityStateSchema = z.object({
  mode: z.enum(['read', 'write']),
  status: z.enum(['available', 'not-tested', 'unsupported', 'error']),
  attempt: z.enum(['verified', 'unverified', 'confirmed-only', 'blocked']),
  source: z.string(),
  evidence: z.string(),
  checked_at: z.string(),
});
export const deviceSchema = z.object({
  id: z.string(),
  name: maybeText,
  model: maybeText,
  rm: maybeText,
  firmware: maybeText,
  transport: z.string(),
  connection_kind: maybeText,
  connected: z.boolean(),
  configured: z.boolean().optional(),
  battery: maybeNumber,
  signal: maybeNumber,
  free: maybeNumber,
  total: maybeNumber,
  imei: maybeText,
  evidence: maybeText,
  capabilities: z.array(z.string()),
  capability_matrix: z.record(z.string(), capabilityStateSchema).optional(),
  capability_fingerprint: z.string().optional(),
  failure: z.object({ reason: z.string() }).nullish(),
  capabilities_checked_at: z.string().optional(),
  sms_send_verified: z.boolean().optional(),
  usb_mode: maybeText,
  life_timer_hours: maybeNumber,
  life_timer_reason: maybeText,
  capability_status: z
    .record(z.string(), z.object({ status: z.string(), reason: maybeText }))
    .optional(),
  model_profile: z
    .object({
      id: z.string().optional(),
      name: z.string(),
      name_ru: z.string().optional(),
      variant_known: z.boolean().optional(),
      identity_note: z.string().nullish(),
      image: z.string(),
      screen: z.object({ width: z.number(), height: z.number(), orientation: z.string() }),
      s60: z.string(),
      symbian: z.string(),
      input: z.string(),
    })
    .nullish(),
  firmware_update: z
    .object({ status: z.string(), latest_known: maybeText, sources: z.array(z.string()) })
    .optional(),
});
export const connectionRowSchema = z.object({
  id: z.string(),
  connected: z.boolean().nullish(),
  failure: z.object({ reason: z.string() }).nullish(),
  model: maybeText,
  connection_kind: maybeText,
});
export const discoverySchema = z.object({
  devices: z.array(deviceSchema),
  connections: z.array(connectionRowSchema).optional(),
  limitations: z.record(z.string(), z.string()),
});
export const filesSchema = z.object({
  entries: z.array(z.object({ name: z.string(), directory: z.boolean(), size: maybeNumber })),
});
export const downloadSchema = z.object({ name: z.string(), content: z.string() });
export const resultSchema = z.object({
  status: z.string().optional(),
  destination: z.string().optional(),
});
export const historySchema = z.object({
  operations: z.array(z.object({ time: z.string(), action: z.string(), status: z.string() })),
});
export const connectionSchema = z.object({
  mode: z.string(),
  connected: z.boolean(),
  relay_token: z.string().optional(),
  expires_in: z.number().optional(),
});
export type CapabilityState = z.infer<typeof capabilityStateSchema>;
export const recheckSchema = z.object({ device: deviceSchema });
export type ConnectionRow = z.infer<typeof connectionRowSchema>;
export type Device = z.infer<typeof deviceSchema>;
export type FileEntry = z.infer<typeof filesSchema>['entries'][number];
export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };
