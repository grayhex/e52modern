import { useState } from 'react';
import type { Device } from '../api/contracts';
import { storage } from './derive';

const KEY = 'symport-linked-volume';
type Link = { phone: string; fingerprint: string; volume: string };

function read(): Link | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (
      value &&
      typeof value === 'object' &&
      'phone' in value &&
      'fingerprint' in value &&
      'volume' in value &&
      typeof value.phone === 'string' &&
      typeof value.fingerprint === 'string' &&
      typeof value.volume === 'string'
    )
      return { phone: value.phone, fingerprint: value.fingerprint, volume: value.volume };
  } catch {
    /* Storage may be unavailable or corrupt: behave as if nothing was linked. */
  }
  return null;
}

/**
 * Storage counters belong to the connection that reported them. A phone identified over Gammu
 * has no card counters of its own; the user may explicitly link a mounted volume to it. The link
 * is bound to the phone's capability fingerprint, so another phone or firmware drops it.
 */
export function useLinkedVolume(selected: Device | undefined, devices: Device[]) {
  const [link, setLink] = useState<Link | null>(read);
  const own = storage(selected);
  const candidates = devices.filter(
    (d) => d.id !== selected?.id && d.transport === 'mounted-volume' && d.connected && storage(d),
  );
  const active =
    selected &&
    link &&
    link.phone === selected.id &&
    link.fingerprint === (selected.capability_fingerprint ?? '')
      ? candidates.find((d) => d.id === link.volume)
      : undefined;
  return {
    own,
    volume: own ? selected : active,
    isLinked: !own && !!active,
    candidates: own ? [] : candidates,
    link(volume: string | null) {
      if (!selected) return;
      const next = volume
        ? { phone: selected.id, fingerprint: selected.capability_fingerprint ?? '', volume }
        : null;
      setLink(next);
      try {
        if (next) localStorage.setItem(KEY, JSON.stringify(next));
        else localStorage.removeItem(KEY);
      } catch {
        /* Not persisting is fine. */
      }
    },
  };
}
