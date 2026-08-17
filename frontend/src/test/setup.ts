import '@testing-library/jest-dom'

// jsdom implements neither of these, and Mantine's provider calls matchMedia on
// mount while several of its components observe element size. Without the shims
// any test that renders a Mantine tree throws before its first assertion.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

// MessageList scrolls to the newest message on mount.
window.HTMLElement.prototype.scrollIntoView = () => {}
