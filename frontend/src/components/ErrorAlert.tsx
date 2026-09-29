type ErrorAlertProps = {
  message: string
}

export function ErrorAlert({ message }: ErrorAlertProps) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {message}
    </div>
  )
}
