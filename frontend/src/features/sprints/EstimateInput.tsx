import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Input } from '@/components/ui/input'
import { mutationErrorMessage } from '@/lib/errors'
import { updateIssue, type IssueSummary } from '@/services/issues'

const MAX_STORY_POINTS = 100

function parsePoints(value: string): number | null | undefined {
  if (value.trim() === '') return null
  const points = Number(value.replace(',', '.'))
  const valid =
    Number.isFinite(points) && points >= 0 && points <= MAX_STORY_POINTS && (points * 2) % 1 === 0
  return valid ? points : undefined
}

/** Estimativa editável em linha: grava ao sair do campo ou com Enter. */
export function EstimateInput({ issue, disabled }: { issue: IssueSummary; disabled?: boolean }) {
  const queryClient = useQueryClient()
  const current = issue.storyPoints === null ? '' : String(issue.storyPoints)
  const [value, setValue] = useState(current)
  const [error, setError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: (storyPoints: number | null) =>
      updateIssue(issue.id, { version: issue.version, storyPoints }),
    onSuccess: () => {
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ['issues'] })
      void queryClient.invalidateQueries({ queryKey: ['sprints'] })
    },
    onError: (failure) => {
      setValue(current)
      setError(mutationErrorMessage(failure))
    },
  })

  const commit = () => {
    if (value === current) return
    const points = parsePoints(value)
    if (points === undefined) {
      setError(`Entre 0 e ${MAX_STORY_POINTS}, em múltiplos de 0,5`)
      setValue(current)
      return
    }
    mutation.mutate(points)
  }

  return (
    <div>
      <Input
        aria-label={`Story points de ${issue.key}`}
        inputMode="decimal"
        className="h-8 w-20"
        value={value}
        disabled={disabled || mutation.isPending}
        aria-invalid={error ? true : undefined}
        onChange={(event) => setValue(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault()
            commit()
          }
        }}
      />
      {error && (
        <p role="alert" className="mt-1 text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
