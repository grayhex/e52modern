export type PackageChoice = { source: string; reference: string; kind: string; file: File | null };
export const initialChoice = (): PackageChoice => {
  const q = new URLSearchParams(location.hash.split('?')[1]);
  return {
    source: q.get('source') ?? 'upload',
    reference: q.get('reference') ?? '',
    kind: q.get('kind') ?? 'app',
    file: null,
  };
};
export const packageLink = (route: string, source: string, reference: string, kind = 'app') =>
  `#${route}?${new URLSearchParams({ source, reference, kind })}`;
