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

// ProseMirror (the rich text editor) measures the selection to scroll it into
// view and to place suggestion popups; jsdom has no layout, so give it empty
// rectangles rather than letting it throw.
const emptyRect = { x: 0, y: 0, top: 0, left: 0, bottom: 0, right: 0, width: 0, height: 0, toJSON: () => ({}) }
Range.prototype.getBoundingClientRect = () => emptyRect as DOMRect
Range.prototype.getClientRects = () =>
  ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] }) as unknown as DOMRectList
document.elementFromPoint ??= () => null
