/** Revive wizard profile id (as the server names it) → the page that hosts it. */
const PROFILE_PAGE: Record<string, string> = {
  'network-certs': 'network',
  'app-kit': 'kit',
  'legacy-services': 'services',
  'reborn-n95': 'reborn',
  addons: 'addons',
  'post-check': 'post-check',
};
/** Route of the page that hosts a wizard profile. */
export function profileRoute(profile: string) {
  if (profile === 'belle-cfw') return 'tools/cfw';
  return `revive/${PROFILE_PAGE[profile] ?? 'home'}`;
}
export function goRevive(profile: string) {
  location.hash = profileRoute(profile);
}
