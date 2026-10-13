"use strict";
function wireTabs(selector) {
  const tabs = [...document.querySelectorAll(selector)];
  function select(tab) {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute("aria-selected", String(active));
      item.tabIndex = active ? 0 : -1;
      const namedPanel = document.getElementById(item.getAttribute("aria-controls"));
      if (namedPanel) namedPanel.hidden = !active;
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", event => {
      let next;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % tabs.length;
      if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); select(tabs[next]); tabs[next].focus(); }
    });
  });
  return select;
}
const selectFeature = wireTabs("[data-panel]");
wireTabs("[data-install]");
document.querySelectorAll("[data-open-feature]").forEach(link => {
  link.addEventListener("click", () => {
    const tab = document.querySelector('[data-panel="' + link.dataset.openFeature + '"]');
    if (tab) selectFeature(tab);
  });
});
const sectionLinks = [...document.querySelectorAll('.site-rail nav a[href^="#"]')];
function updateSectionNavigation() {
  const reference = window.innerWidth <= 980 ? 170 : 90;
  let active = sectionLinks[0];
  sectionLinks.forEach(link => {
    const target = document.getElementById(link.hash.slice(1));
    if (target && target.getBoundingClientRect().top <= reference) active = link;
  });
  sectionLinks.forEach(link => {
    if (link === active) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}
if (sectionLinks.length) {
  let navigationScheduled = false;
  window.addEventListener("scroll", () => {
    if (navigationScheduled) return;
    navigationScheduled = true;
    requestAnimationFrame(() => { navigationScheduled = false; updateSectionNavigation(); });
  }, { passive: true });
  window.addEventListener("resize", updateSectionNavigation);
  updateSectionNavigation();
}
const dialog = document.getElementById("update-dialog");
if (dialog) {
  document.getElementById("update-demo")?.addEventListener("click", () => dialog.showModal());
  dialog.querySelectorAll(".dialog-close,.dialog-close-action").forEach(button => button.addEventListener("click", () => dialog.close()));
}
function textRelease(key, text) {
  document.querySelectorAll('[data-release="' + key + '"]').forEach(node => { node.textContent = text; });
}
function validRelease(value, kind) {
  const product = kind === "vehicle" ? "SealionHome" : kind === "phone" ? "SealionLink" : null;
  return product && value && /^\d+\.\d+\.\d+$/.test(value.versionName) && /^[0-9a-f]{64}$/.test(value.sha256) && Number.isSafeInteger(value.bytes) && value.bytes > 0 && value.bytes <= 209715200 && value.file === "downloads/" + product + "-" + value.versionName + "-" + kind + "-release.apk";
}
async function loadReleases() {
  try {
    const response = await fetch("releases.json", { cache: "no-store" });
    if (!response.ok) throw new Error("release metadata unavailable");
    const releases = await response.json();
    if (releases.schema !== 1) throw new Error("release schema");
    for (const kind of ["vehicle", "phone"]) {
      const value = releases[kind];
      if (!validRelease(value, kind)) continue;
      textRelease(kind + "-version", value.versionName);
      textRelease(kind + "-size", (value.bytes / 1048576).toFixed(1) + " MB");
      textRelease(kind + "-hash", "SHA-256\n" + value.sha256);
      const button = document.querySelector('[data-app="' + kind + '"]');
      button.href = value.file;
      button.setAttribute("download", value.file.split("/").pop());
      button.removeAttribute("aria-disabled");
      button.classList.remove("is-disabled");
      button.replaceChildren(document.createTextNode("APK 다운로드 "));
      const arrow = document.createElement("span"); arrow.textContent = "↗"; button.append(arrow);
    }
    if (validRelease(releases.vehicle, "vehicle") && validRelease(releases.phone, "phone")) {
      document.getElementById("release-status").textContent = "공개 베타 · " + releases.date + " 업데이트 · 회원가입 없이 다운로드";
    }
  } catch (_) {
    // An unavailable release feed must not turn into a broken download link.
    const status = document.getElementById("release-status");
    if (status) status.textContent = "공개 주소와 배포 파일을 아직 연결하지 않았습니다. 다운로드는 준비 중입니다.";
  }
}
if (document.getElementById("download")) loadReleases();
