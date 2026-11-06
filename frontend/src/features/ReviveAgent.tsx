import { useQuery } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator, type Tone } from '../components/kit';
import { agentStateSchema } from '../api/revive';
import { st } from './statements';

const TONE: Record<string, Tone> = {
  'not-installed': 'off',
  'not-paired': 'unknown',
  pairing: 'warn',
  paired: 'info',
};
const TEXT: Record<string, [string, string]> = {
  'not-installed': ['Not installed', 'Не установлен'],
  'not-paired': ['Not paired', 'Не сопряжён'],
  pairing: ['Pairing', 'Сопряжение'],
  paired: ['Paired', 'Сопряжён'],
};

/** Optional Device Agent: protocol, permissions and levels. No agent binary exists in this build. */
export default function ReviveAgent() {
  const api = useApi();
  const { t, language } = usePreferences();
  const state = useQuery({
    queryKey: ['revive', '', 'agent'],
    queryFn: () => api.request('/api/revive', { action: 'agent-state' }, agentStateSchema),
    retry: false,
  });
  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data) return null;
  const s = state.data;
  return (
    <SectionPanel
      title={t('Device Agent (optional)', 'Device Agent (необязательный)')}
      id="revive-agent"
    >
      <p>
        <StatusIndicator tone={TONE[s.status] ?? 'unknown'}>
          {t(...(TEXT[s.status] ?? [s.status, s.status]))}
        </StatusIndicator>{' '}
        <span data-testid="agent-binary">
          {s.status === 'not-installed'
            ? t(
                'No agent binary exists in this build; every other function works as before.',
                'В этой сборке нет бинарного агента; все остальные функции работают как раньше.',
              )
            : s.agent_binary}
        </span>
      </p>
      <p className="k-note-line">{st(language, s.statement)}</p>
      <p className="k-note-line" data-testid="agent-levels">
        {t('Levels', 'Уровни')}: {s.levels.join(' → ')}
      </p>
      <div className="rv-table-wrap">
        <table className="rv-table" data-testid="agent-ops">
          <caption className="rv-sr">{t('Agent operations', 'Операции агента')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('Operation', 'Операция')}</th>
              <th scope="col">{t('Tier', 'Класс')}</th>
              <th scope="col">{t('Permission', 'Разрешение')}</th>
              <th scope="col">{t('Consent on the phone', 'Согласие на телефоне')}</th>
              <th scope="col">{t('Evidence', 'Доказательство')}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(s.operations).map(([op, v]) => (
              <tr key={op} data-op={op}>
                <th scope="row">{op}</th>
                <td>{v.tier}</td>
                <td>{v.permission ?? '—'}</td>
                <td>{v.consent ? t('yes', 'да') : t('no', 'нет')}</td>
                <td>{v.evidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="k-note-line" data-testid="agent-forbidden">
        {t('Forbidden by design', 'Запрещено по замыслу')}: {s.forbidden.join(', ')}
      </p>
    </SectionPanel>
  );
}
