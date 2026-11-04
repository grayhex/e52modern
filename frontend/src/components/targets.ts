export type Target = { model: string; rm: string; firmware: string; os: string };
export const defaultTarget: Target = { model: 'Nokia E52', rm: '', firmware: '', os: '9.3' };

export function initialTarget(): Target {
  return {
    ...defaultTarget,
    model:
      new URLSearchParams(location.hash.split('?')[1]).get('profile') === 'nokia-e72'
        ? 'Nokia E72'
        : defaultTarget.model,
  };
}
