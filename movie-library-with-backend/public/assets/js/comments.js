"use strict";

import { apiFetch, getCurrentUser } from "./auth.js";

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function renderCommentItem(comment) {
  const item = document.createElement("div");
  item.classList.add("comment-item");

  item.innerHTML = `
    <div class="comment-header">
      <span class="comment-username">${comment.username}</span>
      <span class="comment-date">${formatDate(comment.created_at)}</span>
    </div>
    <p class="comment-content"></p>
  `;

  // set as textContent (not innerHTML) so user comments can never inject markup
  item.querySelector(".comment-content").textContent = comment.content;

  return item;
}

/*---------
Builds and appends the comments section to the movie detail page.
Called from detail.js once the movie has loaded.
----------*/
export async function renderComments(movieId, movieTitle) {
  const pageContent = document.querySelector("[page-content]");

  const section = document.createElement("section");
  section.classList.add("comments-section");
  section.ariaLabel = "Comments";

  section.innerHTML = `
    <div class="title-wrapper">
      <h3 class="title-large">Comments</h3>
    </div>

    <div class="comment-form-wrapper" comment-form-wrapper></div>
    <div class="comment-list" comment-list></div>
  `;

  pageContent.appendChild(section);

  const formWrapper = section.querySelector("[comment-form-wrapper]");
  const listElem = section.querySelector("[comment-list]");

  const user = await getCurrentUser();

  if (user) {
    formWrapper.innerHTML = `
      <form class="comment-form" comment-form>
        <textarea
          class="comment-input"
          placeholder="Share your thoughts about this movie..."
          comment-input
          required
        ></textarea>

        <button type="submit" class="btn-login comment-submit">Post Comment</button>

        <p class="comment-error" comment-error></p>
      </form>
    `;

    formWrapper
      .querySelector("[comment-form]")
      .addEventListener("submit", async function (e) {
        e.preventDefault();

        const input = formWrapper.querySelector("[comment-input]");
        const errorElem = formWrapper.querySelector("[comment-error]");
        const content = input.value.trim();
        if (!content) return;

        const res = await apiFetch(`/api/movies/${movieId}/comments`, {
          method: "POST",
          body: JSON.stringify({
            movie_id: Number(movieId),
            movie_title: movieTitle,
            content,
          }),
        });

        if (res.ok) {
          const comment = await res.json();
          listElem.prepend(renderCommentItem(comment));
          input.value = "";
          errorElem.textContent = "";
        } else {
          errorElem.textContent = "Could not post your comment. Please try again.";
        }
      });
  } else {
    formWrapper.innerHTML = `
      <p class="comment-login-prompt">
        <a href="./login.html">Log in</a> to leave a comment.
      </p>
    `;
  }

  const res = await apiFetch(`/api/movies/${movieId}/comments`);
  if (res.ok) {
    const commentList = await res.json();

    if (commentList.length === 0) {
      listElem.innerHTML = `<p class="no-comments">No comments yet. Be the first to share your thoughts!</p>`;
    } else {
      for (const comment of commentList) {
        listElem.appendChild(renderCommentItem(comment));
      }
    }
  }
}
