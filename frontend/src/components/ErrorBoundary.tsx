import { Component, type PropsWithChildren } from 'react';
export class ErrorBoundary extends Component<PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="card">
        <h1>SymPort</h1>
        <p>
          Не удалось открыть раздел. Обновите страницу. / Unable to open this view. Reload the page.
        </p>
        <button className="btn primary" onClick={() => location.reload()}>
          Обновить / Reload
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
