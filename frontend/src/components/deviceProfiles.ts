import document from '../../../symport/phone/device_models.json';
const data = Object.fromEntries(document.models.map((p) => [p.id, p]));

export type DeviceProfile = (typeof document.models)[number];
export const defaultDeviceProfile =
  document.models[0] ??
  (() => {
    throw Error('Missing default device profile');
  })();
export const deviceProfiles: DeviceProfile[] = Object.values(data).filter((p) => p.selectable);
export const profileById = (id: string): DeviceProfile | undefined =>
  Object.values(data).find((p) => p.id === id);
export const profileLabel = (p: DeviceProfile) =>
  `${p.name} · ${p.screen.width}×${p.screen.height} / S60 ${p.s60}`;
export function targetForProfile(id: string) {
  const p = profileById(id) ?? defaultDeviceProfile;
  return { model: p.target_model, rm: '', firmware: '', os: p.symbian };
}
