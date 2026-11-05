export type Target = { model: string; rm: string; firmware: string; os: string };
export const defaultTarget: Target = { model: 'Nokia E52', rm: '', firmware: '', os: '9.3' };

export function initialTarget(): Target {
  return {
    ...defaultTarget,
    // `?profile=nokia-e72` → “Nokia E72”: derived from the id, so a newly registered model needs no code.
    model: (() => {
      const id = /^nokia-([a-z0-9-]{2,30})$/.exec(
        new URLSearchParams(location.hash.split('?')[1]).get('profile') ?? '',
      );
      return id?.[1] ? `Nokia ${id[1].toUpperCase()}` : defaultTarget.model;
    })(),
  };
}
