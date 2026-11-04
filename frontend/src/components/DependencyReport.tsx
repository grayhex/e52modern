import { CircleAlert, CircleCheck, CircleHelp } from 'lucide-react';
import { usePreferences } from '../state/app';
import type { DependencyAnalysis } from '../api/deps';
import { issueText, statusLabel } from './depStatus';

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const { t } = usePreferences();
  const { text, tone } = statusLabel(status, t);
  const Icon = tone === 'ok' ? CircleCheck : tone === 'bad' ? CircleAlert : CircleHelp;
  return (
    <span className={`status-chip status-chip--${tone}`}>
      <Icon size={14} aria-hidden="true" />
      {text}
    </span>
  );
}

const COLUMN = 232;
const ROW = 38;
function layout(graph: DependencyAnalysis['graph']) {
  const layer = new Map(graph.nodes.map((n) => [n.id, n.kind === 'package' ? 0 : 1]));
  for (let pass = 0; pass < graph.nodes.length; pass++)
    for (const e of graph.edges) {
      const from = layer.get(e.from);
      if (from !== undefined && (layer.get(e.to) ?? 0) < from + 1 && layer.has(e.to))
        layer.set(e.to, Math.min(from + 1, 4));
    }
  const rows = new Map<number, number>();
  const placed = graph.nodes.map((n) => {
    const column = layer.get(n.id) ?? 1;
    const row = rows.get(column) ?? 0;
    rows.set(column, row + 1);
    return { ...n, x: 8 + column * COLUMN, y: 8 + row * ROW };
  });
  return {
    nodes: placed,
    width: 8 + (Math.max(...placed.map((n) => n.x)) + 200),
    height: 16 + Math.max(1, ...rows.values()) * ROW,
  };
}

export function DependencyGraph({ graph }: { graph: DependencyAnalysis['graph'] }) {
  const { t } = usePreferences();
  const { nodes, width, height } = layout(graph);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  return (
    <div className="dep-graph table-scroll">
      <svg
        role="img"
        aria-label={t('Dependency graph', 'Граф зависимостей')}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
      >
        <title>{t('Dependency graph', 'Граф зависимостей')}</title>
        <desc>
          {t(
            'Boxes are the package, platforms, declared dependencies, runtimes, executables and imported DLLs. The tables above hold the same facts.',
            'Блоки — пакет, платформы, объявленные зависимости, runtime, исполняемые файлы и импортируемые DLL. Те же факты есть в таблицах выше.',
          )}
        </desc>
        {graph.edges.map((e, i) => {
          const a = byId.get(e.from);
          const b = byId.get(e.to);
          if (!a || !b) return null;
          const x1 = a.x + 200;
          const y1 = a.y + 15;
          const x2 = b.x;
          const y2 = b.y + 15;
          return (
            <path
              key={i}
              className={`dep-edge dep-edge--${e.kind}`}
              d={`M${x1} ${y1} C${x1 + 16} ${y1} ${x2 - 16} ${y2} ${x2} ${y2}`}
              fill="none"
            />
          );
        })}
        {nodes.map((n) => {
          const tone = statusLabel(n.status, t).tone;
          const shown = n.label.length > 27 ? n.label.slice(0, 26) + '…' : n.label;
          return (
            <g
              key={n.id}
              className={`dep-node dep-node--${n.kind} dep-node--${n.status ? tone : 'plain'}`}
            >
              <title>{`${n.label}${n.status ? ' — ' + statusLabel(n.status, t).text : ''}`}</title>
              <rect x={n.x} y={n.y} width="200" height="30" rx="4" />
              <text x={n.x + 8} y={n.y + 19}>
                {shown}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function DependencyReport({ report }: { report: DependencyAnalysis }) {
  const { t } = usePreferences();
  return (
    <section className="dep-report" aria-label={t('Dependency analysis', 'Анализ зависимостей')}>
      <p>
        <strong>{report.package.name}</strong> {report.package.version ?? ''} ·{' '}
        {report.package.uid ?? ''} · <StatusBadge status={report.verdict} />
      </p>
      <p className="note">
        {t(
          'Static analysis only. Installation and launch on the phone are not tested: ',
          'Только статический анализ. Установка и запуск на телефоне не проверялись: ',
        )}
        {Object.entries(report.levels)
          .map(([k, v]) => `${k}: ${v}`)
          .join(' · ')}
      </p>
      {report.issues.length > 0 && (
        <ul className="dep-issues">
          {report.issues.map((issue) => (
            <li key={issue}>
              {issueText[issue] ? t(issueText[issue][0], issueText[issue][1]) : issue}
            </li>
          ))}
        </ul>
      )}
      <h3>
        {t('Platform', 'Платформа')} · <StatusBadge status={report.platform_verdict} />
      </h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>{t('Platform', 'Платформа')}</th>
              <th>Symbian</th>
              <th>{t('Relation to the selected phone', 'Отношение к выбранному телефону')}</th>
            </tr>
          </thead>
          <tbody>
            {report.platforms.map((p) => (
              <tr key={p.uid}>
                <td className="lab-value">{p.uid}</td>
                <td>{p.label}</td>
                <td>{p.symbian ?? '—'}</td>
                <td>
                  <StatusBadge status={p.relation} /> <small>({p.basis})</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>{t('Declared dependencies', 'Объявленные зависимости')}</h3>
      {report.declared.length === 0 ? (
        <p className="empty">
          {t('The package declares none.', 'Пакет не объявляет зависимостей.')}
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('Name', 'Имя')}</th>
                <th>UID</th>
                <th>{t('Min. version', 'Мин. версия')}</th>
                <th>{t('Status', 'Статус')}</th>
              </tr>
            </thead>
            <tbody>
              {report.declared.map((d) => (
                <tr key={`${d.uid}-${d.name}`}>
                  <td>{d.name}</td>
                  <td className="lab-value">{d.uid ?? '—'}</td>
                  <td>{d.min_version ?? '—'}</td>
                  <td>
                    <StatusBadge status={d.status} />
                    {d.matched_package && (
                      <small>
                        {' '}
                        {d.matched_package.name} ({d.matched_package.basis})
                      </small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {report.runtimes.length > 0 && (
        <>
          <h3>{t('Runtimes', 'Runtime-среды')}</h3>
          {report.runtimes.map((r) => (
            <div className="note" key={r.id}>
              <strong>{r.title}</strong> <StatusBadge status={r.status} />
              {r.min_version && <span> · ≥ {r.min_version}</span>}
              <p>{r.distribution}</p>
            </div>
          ))}
        </>
      )}
      <h3>{t('Imported DLLs', 'Импортируемые DLL')}</h3>
      {report.system_imports.length === 0 ? (
        <p className="empty">
          {t(
            'No imports available (compressed or no executables). This is NOT an empty dependency list.',
            'Импорты недоступны (сжатые образы или нет исполняемых файлов). Это НЕ пустой список зависимостей.',
          )}
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>DLL</th>
                <th>{t('Status', 'Статус')}</th>
                <th>{t('Used by', 'Используется в')}</th>
              </tr>
            </thead>
            <tbody>
              {report.system_imports.map((s) => (
                <tr key={s.dll}>
                  <td className="lab-value">{s.dll}</td>
                  <td>
                    <StatusBadge status={s.status} />
                  </td>
                  <td>{s.used_by.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h3>{t('Capabilities', 'Capabilities')}</h3>
      <p>
        {report.capabilities.length ? report.capabilities.join(', ') : '—'}
        {report.restricted_capabilities.length > 0 && (
          <strong>
            {' '}
            · {t('restricted', 'ограниченные')}: {report.restricted_capabilities.join(', ')}
          </strong>
        )}
      </p>
      {report.firmware ? (
        <p className="note">
          {t('Firmware data: ', 'Данные прошивки: ')}
          {report.firmware.source} ({report.firmware.dll_count} DLL)
        </p>
      ) : (
        <p className="note">
          {t(
            'No firmware data supplied: system DLL imports stay unknown.',
            'Данные прошивки не заданы: импорты системных DLL остаются неизвестными.',
          )}
        </p>
      )}
      <DependencyGraph graph={report.graph} />
      <ul className="note">
        {report.limitations.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </section>
  );
}
