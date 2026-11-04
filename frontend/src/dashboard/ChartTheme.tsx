import { useMemo, type PropsWithChildren } from 'react';
import createCache from '@emotion/cache';
import { CacheProvider } from '@emotion/react';
import { ThemeProvider } from '@mui/material/styles';
import { useApi, usePreferences } from '../state/app';
import { useMedia } from '../nav/useMedia';
import { nokiaTheme } from './muiTheme';
/** Shared theme and session CSP nonce for charts on retained React pages. */
export function ChartTheme({ children }: PropsWithChildren) {
  const api = useApi(),
    { theme } = usePreferences(),
    systemDark = useMedia('(prefers-color-scheme: dark)');
  const dark = theme === 'dark' || (theme === 'system' && systemDark);
  const cache = useMemo(
    () => createCache({ key: 'telemetry', nonce: api.styleNonce, prepend: true }),
    [api.styleNonce],
  );
  const mui = useMemo(() => nokiaTheme(dark ? 'dark' : 'light'), [dark]);
  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={mui}>{children}</ThemeProvider>
    </CacheProvider>
  );
}
