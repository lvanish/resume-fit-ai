import { useState } from 'react'
import type { FormEvent } from 'react'
import { analyzeMatch } from './api/matchApi.ts'
import { AnalyzeButton } from './components/AnalyzeButton.tsx'
import { ErrorAlert } from './components/ErrorAlert.tsx'
import { Footer } from './components/Footer.tsx'
import { Header } from './components/Header.tsx'
import { Hero } from './components/Hero.tsx'
import { JobDescriptionInput } from './components/JobDescriptionInput.tsx'
import { MatchResult } from './components/MatchResult.tsx'
import { ResumeInput } from './components/ResumeInput.tsx'
import type { MatchResponse } from './types.ts'

function displayError(message: string): string {
  const normalized = message.toLowerCase()
  if (normalized.includes('resume') && (normalized.includes('blank') || normalized.includes('required'))) {
    return 'Please enter your resume.'
  }
  if (
    (normalized.includes('job description') || normalized.includes('jobdescription')) &&
    (normalized.includes('blank') || normalized.includes('required'))
  ) {
    return 'Please enter a job description.'
  }
  if (normalized.includes('could not reach')) {
    return message
  }
  return 'Laya could not analyze this request. Please try again.'
}

export default function App() {
  const [resume, setResume] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<MatchResponse | null>(null)

  const canSubmit = resume.trim().length > 0 && jobDescription.trim().length > 0 && !loading

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!resume.trim()) {
      setError('Please enter your resume.')
      return
    }
    if (!jobDescription.trim()) {
      setError('Please enter a job description.')
      return
    }
    if (loading) {
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const match = await analyzeMatch({
        resume: resume.trim(),
        jobDescription: jobDescription.trim(),
      })
      setResult(match)
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Analysis failed.'
      setError(displayError(message))
    } finally {
      setLoading(false)
    }
  }

  function onReset() {
    setResult(null)
    setError(null)
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <Header />
      <Hero />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
        <form className="space-y-6" onSubmit={onSubmit}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <ResumeInput value={resume} onChange={setResume} disabled={loading} />
            <JobDescriptionInput value={jobDescription} onChange={setJobDescription} disabled={loading} />
          </div>
          <AnalyzeButton disabled={!canSubmit} loading={loading} />
        </form>

        {error ? (
          <div className="mt-6">
            <ErrorAlert message={error} />
          </div>
        ) : null}

        {result ? (
          <div className="mt-6">
            <MatchResult score={result.score} onReset={onReset} />
          </div>
        ) : null}
      </main>
      <Footer />
    </div>
  )
}
