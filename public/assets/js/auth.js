"use strict";

/*---------
Shared auth helpers used across every page (index, movie-list, detail,
login, register). Talks to the FastAPI backend which is served from the
SAME origin as this frontend, so plain relative paths + cookies work.
----------*/

export async function apiFetch(path, options = {}) {
  return fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
}

export async function getCurrentUser() {
  try {
    const res = await apiFetch("/api/me");
    if (!res.ok) return null;
    const data = await res.json();
    return data.authenticated ? data : null;
  } catch (err) {
    console.error("Failed to check auth status:", err);
    return null;
  }
}

export async function logout() {
  await apiFetch("/api/logout", { method: "POST" });
  window.location.href = "./index.html";
}

/*---------
Fills the [auth-nav] placeholder in the header with either
a "Login" link or a greeting + logout button.
----------*/
export async function renderAuthNav() {
  const authNav = document.querySelector("[auth-nav]");
  if (!authNav) return;

  const user = await getCurrentUser();

  if (user) {
    const avatarSrc = user.profile_picture || "./assets/images/logo2.png";
    authNav.innerHTML = `
      <a href="./profile.html" class="auth-profile-link">
        <img src="${avatarSrc}" class="nav-avatar" alt="" />
        <span class="auth-greeting">Hi, ${user.username}</span>
      </a>
      <button type="button" class="btn-login" logout-btn>Logout</button>
    `;
    authNav.querySelector("[logout-btn]").addEventListener("click", logout);
  } else {
    authNav.innerHTML = `<a href="./login.html" class="btn-login">Login</a>`;
  }
}

renderAuthNav();
