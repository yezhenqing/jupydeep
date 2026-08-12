import { useState, useEffect } from 'react';

interface ICountdownProps {
  targetDate: number;
  title?: string;
  className?: string;
}

export default function CountdownTimer({
  targetDate,
  title = 'Initialization Timeout',
  className = ''
}: ICountdownProps) {
  const [timeLeft, setTimeLeft] = useState<number>(() =>
    Math.max(0, targetDate - Date.now())
  );

  useEffect(() => {
    const timer = setInterval(() => {
      const remaining = targetDate - Date.now();
      if (remaining <= 0) {
        clearInterval(timer);
        setTimeLeft(0);
      } else {
        setTimeLeft(remaining);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [targetDate]);

  if (timeLeft <= 0) {
    return (
      <div className={`flex flex-col items-center gap-2 ${className}`}>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-2xl text-xs
          font-medium transition-all hover:opacity-90 active:scale-95 shadow-sm cursor-pointer"
          style={{
            backgroundColor: 'var(--jp-brand-color1)',
            color: 'var(--jp-ui-inverse-font-color1)',
          }}
        >
          <span>🔄</span>
          <span>Retry (Refresh Page)</span>
        </button>
      </div>
    );
  }

  const pad = (n: number) => String(n).padStart(2, '0');
  const hours = pad(Math.floor((timeLeft / (1000 * 60 * 60)) % 24));
  const minutes = pad(Math.floor((timeLeft / (1000 * 60)) % 60));
  const seconds = pad(Math.floor((timeLeft / 1000) % 60));

  return (
    <div
      className={`inline-flex items-center gap-3 px-4 py-2.5 rounded-2xl bg-slate-950/60 border border-slate-800/80 shadow-xl backdrop-blur-md ${className}`}
    >
      <div className="flex items-center gap-2 pr-2 border-r border-slate-800">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
        </span>
        <span className="text-xs font-medium text-slate-100">{title}</span>
      </div>

      <div className="font-mono text-base font-bold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-indigo-200 via-white to-purple-200">
        <span>{hours}</span>
        <span className="mx-0.5 text-indigo-400/60 font-sans animate-pulse">
          :
        </span>
        <span>{minutes}</span>
        <span className="mx-0.5 text-indigo-400/60 font-sans animate-pulse">
          :
        </span>
        <span>{seconds}</span>
      </div>
    </div>
  );
}
