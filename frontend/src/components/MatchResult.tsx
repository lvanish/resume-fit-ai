type MatchResultProps = {
  score: number
  onReset: () => void
}

export function MatchResult({ score, onReset }: MatchResultProps) {
  const radius = 52
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference - (score / 100) * circumference

  return (
    <section
      className="result-in rounded-xl border border-zinc-200 bg-white p-6 shadow-sm sm:p-8"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-zinc-500">MATCH SCORE</p>
          <p className="mt-2 text-5xl font-semibold tracking-tight text-zinc-950 sm:text-6xl">
            {score}
            <span className="text-2xl font-medium text-zinc-400"> / 100</span>
          </p>
        </div>
        <div
          className="relative h-36 w-36 shrink-0"
          role="img"
          aria-label={`Match score ${score} out of 100`}
        >
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
            <circle cx="60" cy="60" r={radius} fill="none" stroke="#e4e4e7" strokeWidth="8" />
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#4f46e5"
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-xl font-semibold text-zinc-950">
            {score}
          </span>
        </div>
      </div>
      <div className="mt-6">
        <button
          type="button"
          onClick={onReset}
          className="inline-flex h-10 items-center rounded-lg border border-zinc-200 bg-white px-4 text-sm font-semibold text-zinc-800 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
        >
          Analyze Another Job
        </button>
      </div>
    </section>
  )
}
