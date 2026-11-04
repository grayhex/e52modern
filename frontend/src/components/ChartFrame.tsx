import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
/** Explicit positive chart width avoids negative SVG geometry when Activity hides a retained view. */
export function ChartFrame({ children }: { children: (width: number) => ReactNode }) {
  const ref = useRef<HTMLDivElement>(null),
    [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width ?? 0;
      setWidth(Math.floor(next));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return (
    <div className="p1-chart" ref={ref}>
      {width >= 180 ? children(width) : null}
    </div>
  );
}
