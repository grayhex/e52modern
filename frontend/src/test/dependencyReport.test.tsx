import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PreferencesProvider } from '../state/app';
import DependencyReport from '../components/DependencyReport';
import { dependencySchema } from '../api/deps';

const report = dependencySchema.parse({
  schema: 'symport.dependencies/1',
  package: { name: 'Jellyfin', uid: '0xe0713d56', file: 'jellyfin.sis', version: '0.3.22' },
  target: { model: 'Nokia E52' },
  target_profile: 'nokia-e52',
  platform_verdict: 'supported-static',
  platforms: [
    {
      uid: '0x102752ae',
      label: 'S60 3rd Edition FP2',
      symbian: '9.3',
      relation: 'accepted-by-target',
      basis: 'inferred',
      source: null,
    },
  ],
  declared: [
    {
      uid: '0x2001e61c',
      name: 'Qt',
      runtime: 'qt',
      min_version: '4.7.3',
      max_version: null,
      status: 'required-unverified',
      matched_package: null,
    },
  ],
  runtimes: [
    {
      id: 'qt',
      title: 'Qt for Symbian',
      via: ['declared-dependency'],
      status: 'required-unverified',
      min_version: '4.7.3',
      dlls: [],
      distribution: 'Not distributed by SymPort.',
    },
  ],
  system_imports: [],
  binaries: [
    {
      target: '!:\\sys\\bin\\app.exe',
      kind: 'exe',
      compression: 'bytepair',
      imports: null,
      capabilities: ['NetworkServices'],
    },
  ],
  capabilities: ['NetworkServices'],
  restricted_capabilities: [],
  issues: ['dependency-unverified', 'imports-undecoded'],
  verdict: 'unresolved',
  firmware: null,
  levels: {
    static: 'analysed',
    installation: 'not-tested',
    runtime: 'not-tested',
    physical_device: 'not-tested',
  },
  limitations: ['Unknown dependencies are never treated as installed or compatible.'],
  graph: {
    nodes: [
      { id: 'pkg:jellyfin.sis', label: 'Jellyfin', kind: 'package', status: 'unresolved' },
      {
        id: 'dep:0x2001e61c',
        label: 'Qt ≥ 4.7.3',
        kind: 'dependency',
        status: 'required-unverified',
      },
    ],
    edges: [{ from: 'pkg:jellyfin.sis', to: 'dep:0x2001e61c', kind: 'requires' }],
  },
});

describe('dependency report', () => {
  it('keeps unknown unknown: unverified runtime, undecoded imports and untested levels are explicit', () => {
    render(
      <PreferencesProvider>
        <DependencyReport report={report} />
      </PreferencesProvider>,
    );
    expect(screen.getAllByText(/Не решено/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Требуется, не подтверждено').length).toBeGreaterThan(0);
    expect(screen.getByText(/НЕ пустой список зависимостей/)).toBeInTheDocument();
    expect(screen.getByText(/installation: not-tested/)).toBeInTheDocument();
    expect(screen.getByText(/runtime: not-tested/)).toBeInTheDocument();
    expect(screen.getByText(/нет данных прошивки|Данные прошивки не заданы/)).toBeInTheDocument();
    expect(screen.queryByText(/Статически выполнено/)).toBeNull();
    expect(screen.getByRole('img', { name: 'Граф зависимостей' })).toBeInTheDocument();
  });
});
