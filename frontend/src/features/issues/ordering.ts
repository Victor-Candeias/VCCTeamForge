/** Move `id` para a posição `to`; devolve a nova ordem e os vizinhos para a API de rank. */
export function reorder(ids: string[], id: string, to: number) {
  const from = ids.indexOf(id)
  if (from === -1 || to < 0 || to >= ids.length || from === to) return null
  const order = ids.filter((value) => value !== id)
  order.splice(to, 0, id)
  return { order, afterId: order[to - 1], beforeId: order[to + 1] }
}
