import '@testing-library/jest-dom'

// Stub scrollIntoView for jsdom (not implemented)
Element.prototype.scrollIntoView = () => {}

// Clear all mocks before each test
beforeEach(() => {
  vi.clearAllMocks()
})
