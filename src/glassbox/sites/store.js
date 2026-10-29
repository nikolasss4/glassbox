// Tiny namespaced localStorage helper shared by the mock sites.
// Eval success checks read these same keys, so keep names stable.
window.gbStore = {
  get(key, fallback) {
    const raw = localStorage.getItem("gb:" + key);
    return raw === null ? fallback : JSON.parse(raw);
  },
  set(key, value) {
    localStorage.setItem("gb:" + key, JSON.stringify(value));
  },
};
