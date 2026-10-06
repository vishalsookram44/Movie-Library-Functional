"use strict";

import { apiFetch } from "./auth.js";

const form = document.querySelector("[register-form]");
const errorElem = document.querySelector("[form-error]");

form.addEventListener("submit", async function (e) {
  e.preventDefault();
  errorElem.textContent = "";

  const username = form.username.value.trim();
  const email = form.email.value.trim();
  const password = form.password.value;
  const confirmPassword = form.confirmPassword.value;

  if (password !== confirmPassword) {
    errorElem.textContent = "Passwords do not match.";
    return;
  }

  const res = await apiFetch("/api/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });

  if (res.ok) {
    window.location.href = "./login.html";
  } else {
    const data = await res.json().catch(() => ({}));
    errorElem.textContent = data.detail || "Could not create your account.";
  }
});
