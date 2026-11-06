import { Code2 } from 'lucide-react';
import { usePreferences } from '../state/app';
import { EmptyState } from '../components/kit';
import { findItem } from './routes';

/** Shown instead of a developer-mode page when the interface is in user mode (e.g. after following a link). */
export default function DeveloperOnly({ route }: { route: string }) {
  const { t, setMode } = usePreferences();
  const item = findItem(route);
  return (
    <EmptyState
      icon={Code2}
      title={t('This section is for developer mode', 'Этот раздел — для режима разработчика')}
    >
      <p>
        {item ? `${t(item.en, item.ru)}: ` : ''}
        {t(
          'Firmware, SDK, emulator and experimental tools are hidden in user mode so that everyday functions stay simple.',
          'Прошивки, SDK, эмулятор и экспериментальные инструменты скрыты в режиме пользователя, чтобы повседневные функции оставались простыми.',
        )}
      </p>
      <p>
        <button type="button" className="k-btn k-btn--primary" onClick={() => setMode('developer')}>
          <Code2 size={14} aria-hidden="true" />{' '}
          {t('Turn on developer mode', 'Включить режим разработчика')}
        </button>{' '}
        <a className="k-btn" href="#phone/overview">
          {t('Back to the overview', 'К обзору устройства')}
        </a>
      </p>
    </EmptyState>
  );
}
