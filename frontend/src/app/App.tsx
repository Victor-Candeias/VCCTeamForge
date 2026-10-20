import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router'

import { createQueryClient } from '@/app/queryClient'
import { createAppRouter } from '@/app/router'

const queryClient = createQueryClient()
const router = createAppRouter()

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
