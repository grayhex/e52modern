import { ModelProfileSelect } from '../components/ModelProfileSelect';
import { deviceProfiles } from '../components/deviceProfiles';
import type { Target } from '../components/targets';
import { encode } from '../utils/files';
import { PageHeader } from '../components/kit';
import { useConfirmedAction } from '../hooks/useConfirmedAction';
import { initialTarget } from '../components/targets';
import { initialChoice } from '../utils/packages';
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { useApi, usePreferences } from '../state/app';
import { inspectorSchema, labSchema } from '../api/lab';
import { objectSchema, payload, text } from '../api/workspace';
import { Card, DeviceSelect, ErrorMessage } from '../components/ui';
import { Download, Field, JsonReport } from '../components/workspace';
import { PackagePicker } from '../components/PackagePicker';
export default function Inspector() {
  const api = useApi(),
    { t, device, setDevice } = usePreferences();
  const [choice, setChoice] = useState(initialChoice),
    [target, setTarget] = useState<Target>(initialTarget),
    [path, setPath] = useState(
      () => new URLSearchParams(location.hash.split('?')[1]).get('path') ?? '',
    ),
    [destination, setDestination] = useState(''),
    [date, setDate] = useState(''),
    [profile, setProfile] = useState<File | null>(null),
    [report, setReport] = useState<z.infer<typeof inspectorSchema> | null>(null),
    [code, setCode] = useState(''),
    [ack, setAck] = useState(false),
    [message, setMessage] = useState(''),
    [status, setStatus] = useState('');
  const confirm = useConfirmedAction<'emulate' | 'transfer'>();
  const lab = useQuery({
    queryKey: ['lab'],
    queryFn: ({ signal }) => api.request('/api/lab', { action: 'state' }, labSchema, signal),
  });
  const history = useQuery({
    queryKey: ['inspections'],
    queryFn: ({ signal }) =>
      api.request(
        '/api/inspector',
        { action: 'list' },
        z.object({ reports: z.array(inspectorSchema) }),
        signal,
      ),
  });
  const analyze = useMutation({
    mutationFn: async () => {
      const data = payload({
        action: 'analyze',
        source: choice.source,
        reference: choice.reference,
        device,
        path,
        kind: choice.kind,
        target,
      });
      if (choice.source === 'upload') {
        if (!choice.file || choice.file.size > 32 * 1024 ** 2)
          throw Error(t('Choose SIS/SISX up to 32 MiB', 'Выберите SIS/SISX до 32 МиБ'));
        data.name = choice.file.name;
        data.content = await encode(choice.file);
      }
      if (date) data.at = date;
      if (profile) {
        if (profile.size > 1024 ** 2) throw Error('Profile limit: 1 MiB');
        data.firmware_profile = objectSchema.parse(JSON.parse(await profile.text()) as unknown);
      }
      const result = await api.request('/api/inspector', data, inspectorSchema);
      setReport(result);
      setDestination(result.name);
      await history.refetch();
    },
  });
  const diagnose = useMutation({
    mutationFn: () =>
      api.request(
        '/api/inspector',
        { action: 'diagnose', message },
        z.object({ code: z.string(), recommendations: z.array(z.string()) }),
      ),
  });
  const targetArtwork = deviceProfiles.find((p) => p.target_model === target.model);
  return (
    <>
      <PageHeader title={t('Certificate Inspector', 'Certificate Inspector')} />
      <Card>
        <p className="note">
          {t(
            'Certificate validity, mathematical signature and trust on the phone are separate checks.',
            'Срок действия, математическая подпись и доверие телефона — отдельные проверки.',
          )}
        </p>
        <PackagePicker
          value={choice}
          onChange={setChoice}
          deviceSource
          labSources={
            lab.data?.reports
              .filter((r) => r.package)
              .map((r) => ({ id: r.id, name: r.package?.name ?? r.id })) ?? []
          }
        />
        <div className="react-fields">
          <DeviceSelect value={device} onChange={setDevice} />
          <Field label={t('Package path on phone', 'Путь пакета на телефоне')}>
            <input value={path} onChange={(e) => setPath(e.target.value)} />
          </Field>
          <ModelProfileSelect target={target} onTarget={setTarget} />
          {targetArtwork && (
            <img
              src={targetArtwork.image}
              alt={target.model}
              style={{ height: 110, width: 70, objectFit: 'contain' }}
            />
          )}
          {Object.entries(target).map(([k, v]) => (
            <Field
              label={t(
                { model: 'Model', rm: 'RM', firmware: 'Firmware', os: 'Symbian' }[k] ?? k,
                { model: 'Модель', rm: 'RM', firmware: 'Прошивка', os: 'Symbian' }[k] ?? k,
              )}
              key={k}
            >
              <input value={v} onChange={(e) => setTarget({ ...target, [k]: e.target.value })} />
            </Field>
          ))}
          <Field label={t('Validity check date', 'Дата проверки')}>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field
            label={t('Optional firmware profile JSON', 'Профиль прошивки JSON (необязательно)')}
          >
            <input
              type="file"
              accept=".json"
              onChange={(e) => setProfile(e.target.files?.[0] ?? null)}
            />
          </Field>
        </div>
        <button
          className="btn primary"
          disabled={analyze.isPending}
          onClick={() => analyze.mutate()}
        >
          {t('Analyze package', 'Проверить пакет')}
        </button>
        <ErrorMessage error={analyze.error ?? lab.error} />
        <p role="status">{status}</p>
      </Card>
      {report && (
        <Card>
          <h2>{report.name}</h2>
          <dl className="device-details">
            {[
              ['UID', '0x' + report.package.uid.toString(16)],
              [t('Version', 'Версия'), report.package.version.join('.')],
              [t('Publisher', 'Издатель'), report.package.vendor_names.join(', ')],
              [t('Signature', 'Подпись'), report.signatures.status],
              [t('Phone trust', 'Доверие телефона'), report.signatures.trust],
              [t('Compatibility', 'Совместимость'), report.compatibility],
              ['Capabilities', report.capabilities.join(', ')],
              ['SHA-256', report.sha256],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd className="lab-value">{v}</dd>
              </div>
            ))}
          </dl>
          {Object.entries(report.recommendations).map(([k, items]) => (
            <div className="note" key={k}>
              <strong>{k}</strong>
              {items.map((s) => (
                <p key={s}>{s}</p>
              ))}
            </div>
          ))}
          <JsonReport
            value={report}
            label={t(
              'Certificates, dependencies and evidence',
              'Сертификаты, зависимости и доказательства',
            )}
          />
          <Download
            content={btoa(unescape(encodeURIComponent(JSON.stringify(report, null, 2))))}
            name="certificate-inspection.json"
            mime="application/json"
          />
          <div className="form-row">
            <Field label={t('Emulator firmware', 'Прошивка эмулятора')}>
              <select value={code} onChange={(e) => setCode(e.target.value)}>
                <option value="">—</option>
                {lab.data?.health?.firmware?.devices.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.model} · {d.code}
                  </option>
                ))}
              </select>
            </Field>
            <button
              className="btn primary"
              disabled={!code || confirm.busy}
              onClick={() =>
                confirm.ask(
                  t(
                    'Install these inspected bytes in the emulator? This does not verify the physical phone.',
                    'Установить проверенный пакет в эмуляторе? Это не подтверждает работу на телефоне.',
                  ),
                  'emulate',
                )
              }
            >
              {t('Test in emulator', 'Проверить в эмуляторе')}
            </button>
          </div>
          <div className="form-row">
            <Field label={t('Destination', 'Назначение')}>
              <input value={destination} onChange={(e) => setDestination(e.target.value)} />
            </Field>
            <label>
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
              {t(
                'I acknowledge unverified emulator installation',
                'Я понимаю, что установка в эмуляторе может быть не подтверждена',
              )}
            </label>
            <button
              className="btn secondary"
              disabled={!device || confirm.busy}
              onClick={() =>
                confirm.ask(
                  t(
                    'Transfer the inspected package? Complete installation on Nokia.',
                    'Передать проверенный пакет? Завершите установку на Nokia.',
                  ),
                  'transfer',
                )
              }
            >
              {t('Transfer to phone', 'Передать на телефон')}
            </button>
          </div>
        </Card>
      )}
      <Card>
        <h2>{t('Inspection history', 'История проверок')}</h2>
        <ErrorMessage error={history.error} />
        {history.data?.reports.map((r) => (
          <button
            className="btn ghost"
            key={r.id}
            onClick={() => {
              setReport(r);
              setDestination(r.name);
            }}
          >
            {r.name} · {r.compatibility}
          </button>
        ))}
      </Card>
      <Card>
        <h2>{t('Installer error diagnosis', 'Диагностика ошибки установщика')}</h2>
        <Field label={t('Exact message from phone', 'Точное сообщение телефона')}>
          <textarea maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} />
        </Field>
        <button
          className="btn secondary"
          disabled={!message || diagnose.isPending}
          onClick={() => diagnose.mutate()}
        >
          {t('Explain error', 'Объяснить ошибку')}
        </button>
        <ErrorMessage error={diagnose.error} />
        {diagnose.data && (
          <>
            <strong>{diagnose.data.code}</strong>
            {diagnose.data.recommendations.map((s) => (
              <p className="note" key={s}>
                {s}
              </p>
            ))}
          </>
        )}
        <a className="text-link" href="#tools/jailbreak">
          Experimental Jailbreak Manager →
        </a>
      </Card>
      {confirm.dialog(async (action) => {
        if (!report) return;
        const r = await api.request(
          '/api/inspector',
          {
            action,
            id: report.id,
            code,
            device,
            path: destination,
            confirm: true,
            ack_unverified: ack,
          },
          objectSchema,
        );
        if (action === 'emulate')
          location.assign('#dev/lab?report=' + encodeURIComponent(text(r.id)));
        else setStatus(text(r.status));
      })}
    </>
  );
}
