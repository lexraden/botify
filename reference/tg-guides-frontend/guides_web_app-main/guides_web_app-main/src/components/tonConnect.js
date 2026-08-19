import { TonConnectUI } from '@tonconnect/ui'

let tonConnectUI

export function getTonConnectUI() {
  if (!tonConnectUI) {
    tonConnectUI = new TonConnectUI({
      manifestUrl: 'https://guides.ledokol.it/tonconnect-manifest.json'
    })
  }
  return tonConnectUI
}
