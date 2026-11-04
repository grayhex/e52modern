import type { Device } from '../api/contracts';
import type { PairResult, ProbeResult } from '../api/bridge';
import { computeLevels, computeSteps, transportMode, type WizardInput } from './model';

/** Remove anything that looks like a personal or hardware identifier from a free-text value. */
export function scrub(value: unknown, limit = 80): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  return value
    .replace(/(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}/g, '[mac]')
    .replace(/\b\d{12,}\b/g, '[number]')
    .replace(/\b[0-9A-Fa-f]{16,}\b/g, '[hex]')
    .replace(/[A-Za-z]:[\\/][^\s]*|\/(?:home|Users|root|tmp|var|mnt)\/[^\s]*/g, '[path]')
    .replace(/\+?\d[\d ()-]{7,}\d/g, '[number]')
    .slice(0, limit);
}

const kind = (value: ProbeResult | PairResult | 'loading' | null) =>
  value === null ? 'not-run' : value === 'loading' ? 'running' : value.kind;

/**
 * De-identified report for the first physical test. Built from an allow-list: only the fields
 * written here can ever be exported. No IMEI, MAC, serial, token, address, contact, SMS,
 * file name or path; capability entries carry status/source, never free-text evidence.
 */
export function buildReport(input: WizardInput, now = new Date()) {
  const steps = computeSteps(input);
  const failing = steps.find((s) => s.status === 'failed' || s.status === 'unsupported');
  const devices: Device[] = Array.isArray(input.devices) ? input.devices : [];
  const selected = devices.find((d) => d.id === input.selectedId && d.connected);
  const host = typeof input.host === 'object' && input.host ? input.host : null;
  const environment = host?.environment;
  return {
    schema: 'symport.first-connection-report/1',
    generated_at: now.toISOString(),
    privacy:
      'Contains no IMEI, MAC, serial numbers, tokens, addresses, contacts, SMS, file names or private paths.',
    hardware_verified: false,
    symport: {
      origin_kind:
        input.origin.protocol === 'https:'
          ? 'https'
          : ['localhost', '127.0.0.1', '[::1]'].includes(input.origin.hostname)
            ? 'localhost'
            : 'insecure-remote',
    },
    bridge: {
      mode: input.connection?.mode ?? null,
      relay_connected: input.connection?.connected ?? null,
      version: scrub(
        environment?.bridge_version ??
          (typeof input.probe === 'object' && input.probe?.kind === 'ok'
            ? input.probe.version
            : null),
        20,
      ),
      host_os: scrub(environment?.os, 40),
      python_gammu: environment?.python_gammu ?? null,
      probe: kind(input.probe),
      pairing: kind(input.pair),
    },
    stage: failing ? failing.id : 'complete',
    error: failing?.code ?? null,
    steps: steps.map((s) => ({ id: s.id, status: s.status, code: s.code })),
    levels: computeLevels(input),
    host: host && {
      com_ports: host.serial.length,
      drives: host.volumes.length,
      bluetooth_records: host.bluetooth.length,
      usb: host.usb.map((u) => ({
        vid: u.vid.slice(0, 4),
        pid: u.pid.slice(0, 4),
        class: scrub(u.class, 20),
        status: u.status,
      })),
    },
    connection: selected
      ? {
          transport: scrub(selected.transport, 30),
          connection_kind: scrub(selected.connection_kind, 30),
          mode: transportMode(selected),
          model: scrub(selected.model),
          rm: scrub(selected.rm, 12),
          firmware: scrub(selected.firmware, 40),
          failure_reason: selected.failure?.reason ?? null,
          checked_at: selected.capabilities_checked_at ?? null,
          capabilities: Object.fromEntries(
            Object.entries(selected.capability_matrix ?? {}).map(([op, s]) => [
              op,
              { status: s.status, attempt: s.attempt, source: scrub(s.source, 60) },
            ]),
          ),
        }
      : null,
  };
}
