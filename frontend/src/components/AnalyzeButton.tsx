type AnalyzeButtonProps = {
  disabled: boolean
  loading: boolean
}

export function AnalyzeButton({ disabled, loading }: AnalyzeButtonProps) {
  return (
    <button
      type="submit"
      disabled={disabled}
      aria-busy={loading}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 disabled:shadow-none"
    >
      {loading ? (
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
          aria-hidden="true"
        />
      ) : null}
      {loading ? 'Analyzing...' : 'Analyze Match'}
    </button>
  )
}
