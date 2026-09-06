"use strict";

import { apiFetch, getCurrentUser } from "./auth.js";

async function init() {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = "./login.html";
    return;
  }

  renderUser(user);
  setupTabs();
  setupUsernameForm();
  setupPasswordForm();
  setupPictureForm();
}

function renderUser(user) {
  document.querySelector("[profile-username]").textContent = user.username;
  document.querySelector("[profile-email]").textContent = user.email;

  if (user.profile_picture) {
    document.getElementById("profile-avatar").src = user.profile_picture;
  }
}

function setupTabs() {
  const tabs = document.querySelectorAll(".profile-tab");
  const panels = document.querySelectorAll(".profile-panel");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      const target = tab.dataset.tab;
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.panel !== target;
      });
    });
  });
}

function setupUsernameForm() {
  const form = document.getElementById("username-form");
  const errorElem = document.querySelector('[data-error="username"]');
  const successElem = document.querySelector('[data-success="username"]');

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    errorElem.textContent = "";
    successElem.textContent = "";

    const username = form.username.value.trim();

    const res = await apiFetch("/api/me/username", {
      method: "PUT",
      body: JSON.stringify({ username }),
    });

    if (res.ok) {
      const updated = await res.json();
      document.querySelector("[profile-username]").textContent = updated.username;
      successElem.textContent = "Username updated.";
      form.reset();
    } else {
      const data = await res.json().catch(() => ({}));
      errorElem.textContent = data.detail || "Could not update username.";
    }
  });
}

function setupPasswordForm() {
  const form = document.getElementById("password-form");
  const errorElem = document.querySelector('[data-error="password"]');
  const successElem = document.querySelector('[data-success="password"]');

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    errorElem.textContent = "";
    successElem.textContent = "";

    const res = await apiFetch("/api/me/password", {
      method: "PUT",
      body: JSON.stringify({
        current_password: form.currentPassword.value,
        new_password: form.newPassword.value,
      }),
    });

    if (res.ok) {
      successElem.textContent = "Password updated.";
      form.reset();
    } else {
      const data = await res.json().catch(() => ({}));
      errorElem.textContent = data.detail || "Could not update password.";
    }
  });
}

function fileToDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function setupPictureForm() {
  const form = document.getElementById("picture-form");
  const errorElem = document.querySelector('[data-error="picture"]');
  const successElem = document.querySelector('[data-success="picture"]');

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    errorElem.textContent = "";
    successElem.textContent = "";

    const file = form.picture.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      errorElem.textContent = "Image must be smaller than 2MB.";
      return;
    }

    const dataUrl = await fileToDataURL(file);

    const res = await apiFetch("/api/me/picture", {
      method: "PUT",
      body: JSON.stringify({ image_base64: dataUrl }),
    });

    if (res.ok) {
      const updated = await res.json();
      document.getElementById("profile-avatar").src = updated.profile_picture;
      successElem.textContent = "Profile picture updated.";
      form.reset();
    } else {
      const data = await res.json().catch(() => ({}));
      errorElem.textContent = data.detail || "Could not upload picture.";
    }
  });
}

init();
