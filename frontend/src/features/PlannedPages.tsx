import { Image, FlaskConical, TestTube } from 'lucide-react';
import type { PlannedSpec } from '../nav/Planned';

export const plannedSpecs: Record<string, PlannedSpec> = {
  'personalize/wallpapers': {
    icon: Image,
    title: ['Wallpapers', 'Обои'],
    summary: [
      'Preparing and sending wallpapers sized for the phone screen. Only the ready-made E52 CLEAR PNGs exist today.',
      'Подготовка и передача обоев под экран телефона. Сейчас есть только готовые PNG E52 CLEAR.',
    ],
    capabilities: [
      [
        'Crop and scale pictures to 240×320 / 320×240 profiles',
        'Кадрирование и масштаб до профилей 240×320 / 320×240',
      ],
      ['Preview on the correct phone proportions', 'Просмотр в верных пропорциях телефона'],
      ['Send to the Images folder with confirmation', 'Передача в папку Images с подтверждением'],
    ],
    related: [
      {
        route: 'personalize/themes',
        label: ['Download E52 CLEAR wallpapers', 'Скачать обои E52 CLEAR'],
      },
      { route: 'phone/media', label: ['Media', 'Медиа'] },
    ],
  },
  'dev/app-tests': {
    icon: FlaskConical,
    title: ['Application testing', 'Тестирование приложений'],
    summary: [
      'A guided test plan for applications: static checks, emulator run and a manual protocol for the real phone. Each level is reported separately.',
      'Сценарий проверки приложений: статический анализ, запуск в эмуляторе и ручной протокол на настоящем телефоне. Каждый уровень отчитывается отдельно.',
    ],
    capabilities: [
      [
        'One report that keeps static, emulator and physical results apart',
        'Единый отчёт, где статика, эмулятор и телефон не смешиваются',
      ],
      [
        'Reusable test cases for installation, launch and uninstall',
        'Повторяемые проверки установки, запуска и удаления',
      ],
      ['Export for bug reports', 'Экспорт для сообщений об ошибках'],
    ],
    related: [
      { route: 'dev/lab', label: ['Emulator Lab', 'Emulator Lab'] },
      { route: 'tools/certificates', label: ['Certificate Inspector', 'Certificate Inspector'] },
      { route: 'apps/dependencies', label: ['Dependencies', 'Зависимости'] },
    ],
  },
  'dev/theme-tests': {
    icon: TestTube,
    title: ['Theme testing', 'Тестирование тем'],
    summary: [
      'A guided check of a theme on each screen: standby, menu, dialogs and built-in applications. Today the manual device checklist and Emulator Lab cover parts of it.',
      'Пошаговая проверка темы по экранам: ожидание, меню, диалоги и стандартные приложения. Сейчас часть покрывают ручной чек-лист и Emulator Lab.',
    ],
    capabilities: [
      ['Per-screen checklist with screenshots attached', 'Чек-лист по экранам со скриншотами'],
      ['Compare a theme build against the previous one', 'Сравнение сборки темы с предыдущей'],
      [
        'Record the exact installer message and firmware',
        'Фиксация точного сообщения установщика и прошивки',
      ],
    ],
    related: [
      {
        route: 'tools/diagnostics',
        label: ['Device diagnostics (checklist)', 'Диагностика устройства (чек-лист)'],
      },
      { route: 'dev/lab', label: ['Emulator Lab', 'Emulator Lab'] },
    ],
  },
};
