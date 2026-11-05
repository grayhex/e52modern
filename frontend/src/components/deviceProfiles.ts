import data from '../../../symport/phone/model_registry.json';

export type DeviceProfile = (typeof data)[keyof typeof data];
export const defaultDeviceProfile = data['nokia-e52'];
export const deviceProfiles: DeviceProfile[] = Object.values(data).filter((p) => p.selectable);
export const profileById = (id: string): DeviceProfile | undefined =>
  Object.values(data).find((p) => p.id === id);
export const profileLabel = (p: DeviceProfile) =>
  `${p.name} · ${p.screen.width}×${p.screen.height} / S60 ${p.s60}`;
export function targetForProfile(id: string) {
  const p = profileById(id) ?? data['nokia-e52'];
  return { model: p.target_model, rm: '', firmware: '', os: p.symbian };
}
