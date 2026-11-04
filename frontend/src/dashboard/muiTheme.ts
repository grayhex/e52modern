import { createTheme, type Theme } from '@mui/material/styles';

/** MUI theme bound to the Nokia Classic palette (design tokens in nokia-classic.css). */
export function nokiaTheme(mode: 'light' | 'dark'): Theme {
  const dark = mode === 'dark';
  return createTheme({
    cssVariables: false,
    palette: {
      mode,
      primary: { main: dark ? '#91b8ff' : '#124191', contrastText: dark ? '#0b1b33' : '#ffffff' },
      success: { main: dark ? '#7fd0a0' : '#247447' },
      warning: { main: dark ? '#e9b866' : '#935d0c' },
      error: { main: dark ? '#f1999e' : '#a92f36' },
      background: { default: dark ? '#101b2a' : '#f1f3f6', paper: dark ? '#19283a' : '#ffffff' },
      text: { primary: dark ? '#f0f4f8' : '#24364d', secondary: dark ? '#c1ccda' : '#586a7b' },
      divider: dark ? '#3a4c60' : '#cbd3dc',
    },
    shape: { borderRadius: 7 },
    typography: { fontFamily: '"Segoe UI", Tahoma, Arial, sans-serif', fontSize: 14 },
    components: {
      MuiCard: {
        defaultProps: { variant: 'outlined' },
        styleOverrides: { root: { boxShadow: 'none', backgroundImage: 'none' } },
      },
      MuiButton: { styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } } },
      MuiChip: { styleOverrides: { root: { borderRadius: 4, fontWeight: 600 } } },
    },
  });
}
