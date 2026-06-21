// Next.js 15 + Node.js 22+ experimental --localstorage-file flag creates a
// broken localStorage stub server-side. Patch it to a safe no-op so next-auth
// and other libs that guard with typeof-check don't crash during SSR.
export async function register() {
  if (typeof localStorage !== "undefined" && typeof localStorage.getItem !== "function") {
    const noop = () => null;
    Object.defineProperty(globalThis, "localStorage", {
      value: {
        getItem: noop,
        setItem: noop,
        removeItem: noop,
        clear: noop,
        key: noop,
        length: 0,
      },
      writable: true,
    });
  }
}
