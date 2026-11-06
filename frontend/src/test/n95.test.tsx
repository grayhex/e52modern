import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { deviceProfiles, profileById, targetForProfile } from '../components/deviceProfiles';
import { DeviceFrame } from '../components/DeviceFrame';
import { ModelProfileSelect } from '../components/ModelProfileSelect';
import { PreferencesProvider } from '../state/app';
import { initialTarget } from '../components/targets';
import { deviceSchema } from '../api/contracts';

describe('N95 model registry and previews', () => {
  it('uses independent variants and a neutral unknown fallback', () => {
    expect(deviceProfiles.map((p) => p.id)).toEqual([
      'nokia-e52',
      'nokia-e72',
      'nokia-n95',
      'nokia-n95-8gb',
      'nokia-n97-mini',
      'nokia-n8',
      'nokia-e7',
      'nokia-7610',
    ]);
    expect(profileById('nokia-n95')?.image).not.toBe(profileById('nokia-n95-8gb')?.image);
    expect(profileById('nokia-n95-family')?.selectable).toBe(false);
    expect(targetForProfile('nokia-n95').os).toBe('9.2');
    expect(targetForProfile('nokia-e72').os).toBe('9.3');
  });
  it.each(['nokia-n95', 'nokia-n95-8gb'])(
    'puts the native portrait screen in the %s master',
    (id) => {
      const p = profileById(id);
      if (!p?.artwork) throw Error('Missing device profile artwork');
      const { container } = render(
        <DeviceFrame profile={id}>
          <rect width="240" height="320" fill="white" />
        </DeviceFrame>,
      );
      expect(screen.getByRole('group', { name: p.name })).toHaveAttribute(
        'viewBox',
        '0 0 1000 1868',
      );
      expect(container.querySelector('image')).toHaveAttribute('href', p.image);
      expect(container.querySelector('svg svg')).toHaveAttribute('viewBox', '0 0 240 320');
      expect(container.querySelector('svg svg')).toHaveAttribute('x', String(p.artwork.screen.x));
    },
  );
  it('selects FP1 with no stale FP2 OS, RM or firmware', () => {
    localStorage.setItem('symport-language', 'en');
    const onTarget = vi.fn();
    render(
      <PreferencesProvider>
        <ModelProfileSelect
          target={{ model: 'Nokia E52', os: '9.3', rm: 'old', firmware: 'old' }}
          onTarget={onTarget}
        />
      </PreferencesProvider>,
    );
    fireEvent.change(screen.getByLabelText('Model profile'), {
      target: { value: 'nokia-n95-8gb' },
    });
    expect(onTarget).toHaveBeenCalledWith({
      model: 'Nokia N95 8GB',
      os: '9.2',
      rm: '',
      firmware: '',
    });
  });
  it('package deep links preserve model platform', () => {
    location.hash = '#tools/certificates?profile=nokia-n95';
    expect(initialTarget()).toEqual({ model: 'Nokia N95-1', rm: '', firmware: '', os: '9.2' });
    location.hash = '';
  });
  it('retains identity evidence through the typed API without granting capabilities', () => {
    const p = profileById('nokia-n95-family');
    if (!p) throw Error('Missing family fallback');
    const d = deviceSchema.parse({
      id: 'n95',
      transport: 'gammu',
      connected: true,
      capabilities: [],
      model_profile: { ...p, variant_known: false },
    });
    expect(d.model_profile?.id).toBe('nokia-n95-family');
    expect(d.model_profile?.variant_known).toBe(false);
    expect(d.capabilities).toEqual([]);
  });
});
