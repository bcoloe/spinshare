import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

// Catches dynamic import failures (stale cache after deploy) and forces a reload.
export default class ChunkErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    if (
      error.name === 'ChunkLoadError' ||
      error.message.includes('Failed to fetch dynamically imported module') ||
      error.message.includes('Importing a module script failed')
    ) {
      window.location.reload()
    } else {
      this.setState({ hasError: true })
    }
  }

  render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}
