import '@testing-library/jest-dom/vitest';

Element.prototype.scrollIntoView = () => {};

class ResizeObserverMock implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverMock;
