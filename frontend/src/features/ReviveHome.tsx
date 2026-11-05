import { useQuery } from '@tanstack/react-query';
import { Compass, Puzzle, Waypoints } from 'lucide-react';
import { useApi, usePreferences } from '../state/app';
import { ErrorMessage } from '../components/ui';
import { SectionPanel, StatusIndicator } from '../components/kit';
import { homeSchema } from '../api/revive';

const KIND: Record<string, [string, string]> = {
  tls: ['TLS components', 'TLS-компоненты'],
  'service-setting': ['Service setting', 'Настройка сервиса'],
  reborn: ['Reborn step', 'Шаг Reborn'],
  operation: ['Operation', 'Операция'],
  'safety-plan': ['Safe copy plan', 'План безопасного копирования'],
  addon: ['Add-on', 'Дополнение'],
};

/** Revive home: shortcuts, suggestions for the identified model, one de-identified history. */
export default function ReviveHome({
  device,
  manual,
  onOpen,
}: {
  device: string;
  manual: Record<string, string>;
  onOpen: (profile: string) => void;
}) {
  const api = useApi();
  const { t } = usePreferences();
  const home = useQuery({
    queryKey: ['revive', device, 'home', manual],
    queryFn: () => api.request('/api/revive', { action: 'home', device, manual }, homeSchema),
    staleTime: 0,
    retry: false,
  });
  if (home.error) return <ErrorMessage error={home.error} />;
  if (!home.data) return null;
  const data = home.data;
  const available = (id: string) => data.sections.find((s) => s.id === id)?.available ?? false;
  return (
    <SectionPanel title={t('Revive home', 'Главная Revive')} id="revive-home">
      <div className="rv-profiles" role="group" aria-label={t('Shortcuts', 'Быстрые переходы')}>
        <button
          type="button"
          className="rv-profile"
          data-shortcut="legacy-services"
          disabled={!available('legacy-services')}
          onClick={() => onOpen('legacy-services')}
        >
          <strong>
            <Waypoints size={16} aria-hidden="true" />{' '}
            {t('Restore services', 'Восстановить сервисы')}
          </strong>
          <span>
            {t(
              'Old system endpoints and what is proven',
              'Старые системные адреса и что подтверждено',
            )}
          </span>
        </button>
        <button
          type="button"
          className="rv-profile"
          data-shortcut="addons"
          disabled={!available('addons')}
          onClick={() => onOpen('addons')}
        >
          <strong>
            <Puzzle size={16} aria-hidden="true" /> {t('Add-ons and patches', 'Дополнения и патчи')}
          </strong>
          <span>
            {available('addons')
              ? t(
                  'Optional add-ons and the Patch Manager',
                  'Необязательные дополнения и Patch Manager',
                )
              : t('Not available in this build', 'Недоступно в этой сборке')}
          </span>
        </button>
      </div>
      <h3>
        <Compass size={16} aria-hidden="true" />{' '}
        {t('What else can be improved on this Nokia', 'Что ещё можно улучшить на этой Nokia')}
      </h3>
      {data.recommendations.length === 0 ? (
        <p className="k-note-line" data-testid="home-no-recs">
          {t(
            'Nothing to suggest until the phone model is identified from the device.',
            'Рекомендаций нет, пока модель не определена по устройству.',
          )}
        </p>
      ) : (
        <ul className="k-list" data-testid="home-recs">
          {data.recommendations.map((r) => (
            <li key={r.id} data-rec={r.id}>
              <span className="rv-check-text">
                <strong>{t(r.title.en, r.title.ru)}</strong>
                <small>
                  {t('Basis', 'Основание')}: {r.basis}
                </small>
              </span>
              <button type="button" className="k-btn" onClick={() => onOpen(r.action)}>
                {t('Open', 'Открыть')}
              </button>
            </li>
          ))}
        </ul>
      )}
      <h3>{t('History for this phone', 'История для этого телефона')}</h3>
      {data.history.length === 0 ? (
        <p className="k-note-line">{t('Nothing recorded yet.', 'Пока ничего не записано.')}</p>
      ) : (
        <ul className="k-list" data-testid="home-history">
          {data.history.slice(0, 12).map((h, i) => (
            <li key={`${h.kind}-${h.item}-${i}`}>
              <span>
                {t(...(KIND[h.kind] ?? [h.kind, h.kind]))}: {h.item}{' '}
                {h.result ? `— ${h.result}` : ''}
              </span>
              <StatusIndicator tone={h.source === 'manual' ? 'warn' : 'info'}>
                {h.source === 'manual' ? t('typed by you', 'введено вами') : 'SymPort'} ·{' '}
                {(h.at ?? '').slice(0, 16)}
              </StatusIndicator>
            </li>
          ))}
        </ul>
      )}
      <p className="k-note-line">{data.statement}</p>
    </SectionPanel>
  );
}
