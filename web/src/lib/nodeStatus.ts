export type NodeState = 'available' | 'unavailable' | 'untested' | 'disabled' | 'expired'

export function nodeState(item: { status: string; expired: boolean; enabled?: number | boolean }): NodeState {
  if (item.expired) return 'expired'
  if ('enabled' in item && !item.enabled) return 'disabled'
  if (item.status === '可用') return 'available'
  if (item.status === '不可用') return 'unavailable'
  return 'untested'
}

export function stateText(state: NodeState) {
  return {
    available: '可用',
    unavailable: '不可用',
    untested: '未测速',
    disabled: '停用',
    expired: '到期',
  }[state]
}

export function stateTone(state: NodeState): 'green' | 'red' | 'gray' | 'blue' {
  return {
    available: 'green',
    unavailable: 'red',
    untested: 'gray',
    disabled: 'gray',
    expired: 'red',
  }[state] as 'green' | 'red' | 'gray' | 'blue'
}

export function stateTip(state: NodeState) {
  return {
    available: '服务器可以通过该节点访问外网，可绑定到用户套餐。',
    unavailable: '服务器无法通过该节点访问外网，本地 Clash 可用不代表服务器可用。',
    untested: '还没有从服务器发起测速，建议先测速确认是否可作为上游。',
    disabled: '入口已停用，不会参与生成或转发。',
    expired: '已超过到期时间，需要续期或重新生成。',
  }[state]
}

export const stateLegend = [
  { state: 'available' as const },
  { state: 'unavailable' as const },
  { state: 'untested' as const },
  { state: 'disabled' as const },
  { state: 'expired' as const },
]
