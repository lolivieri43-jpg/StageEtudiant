/**
 * Reliable cross-browser PDF/file download from a Blob.
 *
 * Some browsers (Firefox, Safari, certain Chromium policies) ignore .click() on
 * an anchor that is NOT attached to the DOM. This helper ensures the anchor is
 * appended, clicked synchronously, then removed and the object URL revoked.
 */
export function triggerBlobDownload(blob, filename) {
  if (!(blob instanceof Blob)) {
    blob = new Blob([blob], { type: "application/octet-stream" });
  }
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "download";
  a.style.display = "none";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  // Give the browser a tick to start the download before cleanup
  setTimeout(() => {
    try { document.body.removeChild(a); } catch (_) {}
    window.URL.revokeObjectURL(url);
  }, 100);
}
