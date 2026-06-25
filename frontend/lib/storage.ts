// Safe wrapper for localStorage that handles SSR and restricted environments
const createSafeStorage = () => {
  if (globalThis.window === undefined) {
    // Server-side rendering
    return {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
      key: () => null,
      length: 0,
    };
  }

  try {
    // Test if localStorage is accessible
    const test = '__localStorage_test__';
    globalThis.window.localStorage.setItem(test, test);
    globalThis.window.localStorage.removeItem(test);
    return globalThis.window.localStorage;
  } catch {
    // localStorage is disabled or quota exceeded
    // Create in-memory fallback
    const store: Record<string, string> = {};
    return {
      getItem: (key: string) => store[key] || null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
      clear: () => { Object.keys(store).forEach(key => delete store[key]); },
      key: (index: number) => Object.keys(store)[index] || null,
      length: Object.keys(store).length,
    };
  }
};

export const safeLocalStorage = createSafeStorage();

// Polyfill localStorage globally for client-side
if (globalThis.window !== undefined && !('localStorage' in globalThis.window)) {
  (globalThis.window as any).localStorage = safeLocalStorage;
}
