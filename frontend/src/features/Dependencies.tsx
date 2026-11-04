import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { encode } from '../utils/files';
import { initialChoice } from '../utils/packages';
import { useApi, usePreferences } from '../state/app';
import { dependencySchema } from '../api/deps';
import { payload } from '../api/workspace';
import { Card, ErrorMessage } from '../components/ui';
import { PackagePicker } from '../components/PackagePicker';
import DependencyReport from '../components/DependencyReport';
import { RuntimeFiles, TargetFields } from '../components/RuntimeInputs';
import { defaultTarget } from '../components/targets';
import { Download } from '../components/workspace';

/** Application Dependency & Runtime Manager: what a package needs, checked against the chosen phone. */
export default function Dependencies() {
  const api = useApi();
  const { t } = usePreferences();
  const [choice, setChoice] = useState(initialChoice);
  const [target, setTarget] = useState(defaultTarget);
  const [firmwareId, setFirmwareId] = useState('');
  const [runtimes, setRuntimes] = useState<File[]>([]);
  const analyze = useMutation({
    mutationFn: async () => {
      const body = payload({
        action: 'dependencies',
        source: choice.source,
        reference: choice.reference,
        kind: choice.kind,
        target,
      });
      if (choice.source === 'upload') {
        if (!choice.file || choice.file.size > 32 * 1024 ** 2)
          throw Error(t('Choose SIS/SISX up to 32 MiB', 'Выберите SIS/SISX до 32 МиБ'));
        body.name = choice.file.name;
        body.content = await encode(choice.file);
      }
      if (firmwareId) body.firmware_id = firmwareId;
      body.runtimes = await Promise.all(
        runtimes.map(async (file) => ({
          source: 'upload',
          name: file.name,
          content: await encode(file),
        })),
      );
      return api.request('/api/inspector', body, dependencySchema);
    },
  });
  const report = analyze.data;
  return (
    <>
      <h1>{t('Dependencies & compatibility', 'Зависимости и совместимость')}</h1>
      <Card>
        <p className="note">
          {t(
            'Reads what a SIS/SISX declares and imports and checks it against the selected phone. Unknown dependencies are never treated as installed or compatible, and nothing is installed or run.',
            'Читает, что пакет SIS/SISX объявляет и импортирует, и сверяет с выбранным телефоном. Неизвестные зависимости никогда не считаются установленными или совместимыми, ничего не устанавливается и не запускается.',
          )}
        </p>
        <PackagePicker value={choice} onChange={setChoice} />
        <TargetFields
          target={target}
          onTarget={setTarget}
          firmwareId={firmwareId}
          onFirmware={setFirmwareId}
        />
        <RuntimeFiles files={runtimes} onFiles={setRuntimes} />
        <button
          className="btn primary"
          disabled={analyze.isPending}
          onClick={() => analyze.mutate()}
        >
          {t('Analyze dependencies', 'Проверить зависимости')}
        </button>
        <ErrorMessage error={analyze.error} />
      </Card>
      {report && (
        <Card>
          <h2>{t('Result', 'Результат')}</h2>
          <DependencyReport report={report} />
          <Download
            content={btoa(unescape(encodeURIComponent(JSON.stringify(report, null, 2))))}
            name="dependency-analysis.json"
            mime="application/json"
          />
          <p>
            <a className="btn secondary" href="#apps/kits">
              {t('Build an application kit →', 'Собрать комплект приложения →')}
            </a>
          </p>
        </Card>
      )}
    </>
  );
}
