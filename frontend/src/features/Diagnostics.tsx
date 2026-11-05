import { usePreferences } from '../state/app';
import { PageHeader } from '../components/kit';
import Telemetry from './Telemetry';
import Workbench, { Updates } from './Workbench';

/** Device diagnostics: the manual E52 test protocol plus the firmware reference. */
export default function Diagnostics() {
  const { t } = usePreferences();
  return (
    <>
      <PageHeader title={t('Device Diagnostics', 'Диагностика устройства')} />
      <Telemetry />
      <details>
        <summary>{t('Device test protocol', 'Протокол испытаний')}</summary>
        <Workbench page="device" />
      </details>
      <details open={new URLSearchParams(location.hash.split('?')[1]).get('view') === 'updates'}>
        <summary>{t('Firmware reference', 'Справочник прошивок')}</summary>
        <section id="diagnostics-updates" aria-label="Firmware updates">
          <Updates heading={false} />
        </section>
      </details>
    </>
  );
}
