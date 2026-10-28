// Web push. On iPhone this only works once t1ld3 is on the home screen
// (iOS 16.4+), and every notification comes from the server: a home-screen
// app can't schedule its own. See supabase/functions.

export function isStandalone() {
  return matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
}

export function pushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

// "on", "off", "blocked" or "unsupported".
export async function pushStatus() {
  if (!pushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  if (Notification.permission !== "granted") return "off";
  const registration = await navigator.serviceWorker.ready;
  return (await registration.pushManager.getSubscription()) ? "on" : "off";
}

function keyBytes(base64) {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

// Call straight from a tap: iOS only asks for permission in response to one.
export async function enablePush(cloud) {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("notifications are off for t1ld3 in Settings");
  const registration = await navigator.serviceWorker.ready;
  const key = await cloud.vapidKey();
  if (!key) throw new Error("the push server isn't set up yet (see phone/README.md)");
  const subscription = (await registration.pushManager.getSubscription())
    ?? (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) }));
  // The time zone lets the server work out when "09:30" is for this phone.
  await cloud.saveSubscription(subscription, Intl.DateTimeFormat().resolvedOptions().timeZone);
}

export async function disablePush(cloud) {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  await cloud.deleteSubscription(subscription.endpoint).catch(() => {});
  await subscription.unsubscribe();
}
