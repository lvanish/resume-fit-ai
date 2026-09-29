type ResumeInputProps = {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

export function ResumeInput({ value, onChange, disabled = false }: ResumeInputProps) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm sm:p-5">
      <label htmlFor="resume" className="block text-sm font-semibold text-zinc-950">
        Your Resume
      </label>
      <p className="mt-1 text-sm text-zinc-500">Paste the full text of your resume.</p>
      <textarea
        id="resume"
        name="resume"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        rows={14}
        placeholder="Paste your resume here..."
        className="mt-4 min-h-64 w-full resize-y rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3 text-sm leading-6 text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-70"
      />
    </section>
  )
}
