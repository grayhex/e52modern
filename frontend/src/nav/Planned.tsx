import { Construction } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { usePreferences } from '../state/app';

export type PlannedSpec = {
  icon: LucideIcon;
  title: [string, string];
  summary: [string, string];
  capabilities: [string, string][];
  related?: { route: string; label: [string, string] }[];
};

/** Honest placeholder for sections without a working feature: describes the plan, simulates nothing. */
export default function Planned({ spec }: { spec: PlannedSpec }) {
  const { t } = usePreferences();
  const Icon = spec.icon;
  return (
    <>
      <h1>{t(...spec.title)}</h1>
      <section className="card planned-card" aria-labelledby="planned-title">
        <div className="planned-head">
          <span className="planned-icon" aria-hidden="true">
            <Icon size={28} strokeWidth={1.8} />
          </span>
          <div>
            <h2 id="planned-title">{t(...spec.title)}</h2>
            <p className="status-chip status-chip--planned">
              <Construction size={14} aria-hidden="true" />
              {t('In development', 'В разработке')}
            </p>
          </div>
        </div>
        <p>{t(...spec.summary)}</p>
        <h3>{t('Planned capabilities', 'Планируемые возможности')}</h3>
        <ul className="planned-list">
          {spec.capabilities.map((item) => (
            <li key={item[0]}>{t(...item)}</li>
          ))}
        </ul>
        <p className="note">
          {t(
            'Nothing on this page works yet and no result is simulated. Related tools that already work are linked below.',
            'Здесь пока ничего не работает, результаты не имитируются. Ниже — уже работающие связанные инструменты.',
          )}
        </p>
        {spec.related && (
          <p className="planned-links">
            {spec.related.map((link) => (
              <a key={link.route} className="btn secondary" href={`#${link.route}`}>
                {t(...link.label)}
              </a>
            ))}
          </p>
        )}
      </section>
    </>
  );
}
