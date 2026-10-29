// Seed accounts. Passwords can be changed by the reset flow (stored in gbStore).
const ACCOUNTS = {
  alice: { password: "sunflower-42", email: "alice@example.com", twoFactor: false },
  bob: { password: "river-9", email: "bob@example.com", twoFactor: true },
  carol: { password: "maple-syrup-7", email: "carol@example.com", twoFactor: false },
  dave: { password: "unknown-old-pass", email: "dave@example.com", twoFactor: false },
};
function passwordFor(user) {
  return gbStore.get("login:password:" + user, ACCOUNTS[user] && ACCOUNTS[user].password);
}
// The authenticator code is fixed per user so the eval stays deterministic.
const TOTP = { bob: "482915" };
