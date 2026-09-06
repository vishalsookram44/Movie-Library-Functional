"use strict";

import { apiFetch, getCurrentUser } from "./auth.js";

/*---------
Builds and appends the like/dislike section to the movie detail page.
Called from detail.js once the movie has loaded.
----------*/
export async function renderReactions(movieId) {
  const pageContent = document.querySelector("[page-content]");

  const section = document.createElement("section");
  section.classList.add("reactions-section");
  section.ariaLabel = "Movie reactions";

  section.innerHTML = `
    <div class="reactions-wrapper">
      <button type="button" class="reaction-btn" data-reaction="like">
        <span class="reaction-icon">&#128077;</span>
        <span class="reaction-count" data-count="like">0</span>
      </button>
      <button type="button" class="reaction-btn" data-reaction="dislike">
        <span class="reaction-icon">&#128078;</span>
        <span class="reaction-count" data-count="dislike">0</span>
      </button>
    </div>
  `;

  pageContent.appendChild(section);

  const likeBtn = section.querySelector('[data-reaction="like"]');
  const dislikeBtn = section.querySelector('[data-reaction="dislike"]');
  const likeCount = section.querySelector('[data-count="like"]');
  const dislikeCount = section.querySelector('[data-count="dislike"]');

  function paint(data) {
    likeCount.textContent = data.likes;
    dislikeCount.textContent = data.dislikes;
    likeBtn.classList.toggle("active", data.user_reaction === "like");
    dislikeBtn.classList.toggle("active", data.user_reaction === "dislike");
  }

  const res = await apiFetch(`/api/movies/${movieId}/reactions`);
  if (res.ok) {
    paint(await res.json());
  }

  async function handleClick(reaction) {
    const user = await getCurrentUser();
    if (!user) {
      window.location.href = "./login.html";
      return;
    }

    const res = await apiFetch(`/api/movies/${movieId}/reactions`, {
      method: "POST",
      body: JSON.stringify({ reaction }),
    });

    if (res.ok) {
      paint(await res.json());
    }
  }

  likeBtn.addEventListener("click", () => handleClick("like"));
  dislikeBtn.addEventListener("click", () => handleClick("dislike"));
}
