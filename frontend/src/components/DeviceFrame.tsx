import type { ReactNode } from 'react';
import { profileById } from './deviceProfiles';

/** The same source geometry drives every phone preview, without per-model CSS offsets. */
export function DeviceFrame({ profile, children }: { profile: string; children: ReactNode }) {
  const p = profileById(profile);
  if (!p?.image || !p.artwork) return null;
  const a = p.artwork,
    s = a.screen;
  return (
    <svg
      className="device-frame"
      viewBox={`0 0 ${a.width} ${a.height}`}
      role="group"
      aria-label={p.name}
      style={{ display: 'block', width: '100%', maxWidth: 280, maxHeight: 540, margin: '0 auto' }}
    >
      <image href={p.image} width={a.width} height={a.height} />
      <svg
        x={s.x}
        y={s.y}
        width={s.width}
        height={s.height}
        viewBox={`0 0 ${p.screen.width} ${p.screen.height}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {children}
      </svg>
    </svg>
  );
}
