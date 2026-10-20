import { ApiError } from '@/services/apiClient'

/** Mensagem para erros de mutações (409 com `currentVersion` = edição concorrente). */
export function mutationErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.isConflict && error.extensions.currentVersion !== undefined) {
      return 'Os dados foram alterados por outra pessoa. Recarregue a página e repita a alteração.'
    }
    return error.message
  }
  return 'Ocorreu um erro inesperado. Tente novamente.'
}
