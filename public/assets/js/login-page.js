"use strict";

import { apiFetch } from "./auth.js";

const form = document.querySelector("[login-form]");
const errorElem = document.querySelector("[form-error]");

form.addEventListener("submit", async function (e) {
  e.preventDefault();
  errorElem.textContent = "";

  const username = form.username.value.trim();
  const password = form.password.value;

  const res = await apiFetch("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

  if (res.ok) {
    window.location.href = "./index.html";
  } else {
    const data = await res.json().catch(() => ({}));
    errorElem.textContent = data.detail || "Incorrect username or password.";
  }
});
