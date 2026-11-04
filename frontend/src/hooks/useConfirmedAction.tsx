import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ConfirmDialog } from '../components/ui';
// An explicit, one-shot confirmation. On failure the pending action is consumed;
// an uncertain write can never be retried by pressing Confirm a second time.
export function useConfirmedAction<T>() {
  const [pending, setPending] = useState<{ message: string; value: T } | null>(null);
  const [consumed, setConsumed] = useState(false);
  const mutation = useMutation({ mutationFn: async (task: () => Promise<unknown>) => task() });
  function ask(message: string, value: T) {
    mutation.reset();
    setConsumed(false);
    setPending({ message, value });
  }
  function dialog(run: (value: T) => Promise<unknown>) {
    return pending ? (
      <ConfirmDialog
        message={pending.message}
        busy={mutation.isPending}
        error={mutation.error}
        onCancel={() => {
          setPending(null);
          mutation.reset();
        }}
        onConfirm={() => {
          if (consumed) return;
          setConsumed(true);
          const value = pending.value;
          mutation.mutate(() => run(value), { onSuccess: () => setPending(null) });
        }}
      />
    ) : null;
  }
  return { ask, dialog, busy: mutation.isPending, error: mutation.error };
}
