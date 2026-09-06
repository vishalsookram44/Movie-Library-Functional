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

/*---------
Swaps the comment's text for an inline textarea + Save/Cancel controls.
onSave receives the new content and should return the updated comment
object from the server (or null on failure).
----------*/
function startEdit(item, comment, onSave) {
  const contentElem = item.querySelector(".comment-content");
  const actionsElem = item.querySelector(".comment-actions");

  const editWrapper = document.createElement("div");
  editWrapper.classList.add("comment-edit-wrapper");
  editWrapper.innerHTML = `
    <textarea class="comment-input comment-edit-input"></textarea>
    <div class="comment-edit-actions">
      <button type="button" class="btn-login comment-submit" data-edit-save>Save</button>
      <button type="button" class="comment-action-btn" data-edit-cancel>Cancel</button>
    </div>
    <p class="comment-error" data-edit-error></p>
  `;
  editWrapper.querySelector("textarea").value = comment.content;

  contentElem.replaceWith(editWrapper);
  actionsElem.style.display = "none";

  function restore() {
    editWrapper.replaceWith(contentElem);
    actionsElem.style.display = "";
  }

  editWrapper.querySelector("[data-edit-cancel]").addEventListener("click", restore);

  editWrapper
    .querySelector("[data-edit-save]")
    .addEventListener("click", async function () {
      const textarea = editWrapper.querySelector("textarea");
      const errorElem = editWrapper.querySelector("[data-edit-error]");
      const newContent = textarea.value.trim();
      if (!newContent) return;

      const updated = await onSave(newContent);
      if (updated) {
        comment.content = updated.content;
        contentElem.textContent = updated.content;
        restore();
      } else {
        errorElem.textContent = "Could not save your changes. Please try again.";
      }
    });
}

function renderCommentItem(comment, currentUserId, { onDelete, onEdit }) {
  const item = document.createElement("div");
  item.classList.add("comment-item");

  const isOwner = currentUserId != null && comment.user_id === currentUserId;

  item.innerHTML = `
    <div class="comment-header">
      <span class="comment-username">${comment.username}</span>
      <span class="comment-date">${formatDate(comment.created_at)}</span>
    </div>
    <p class="comment-content"></p>
    ${
      isOwner
        ? `<div class="comment-actions">
             <button type="button" class="comment-action-btn" data-action="edit">Edit</button>
             <button type="button" class="comment-action-btn" data-action="delete">Delete</button>
           </div>`
        : ""
    }
  `;

  // set as textContent (not innerHTML) so user comments can never inject markup
  item.querySelector(".comment-content").textContent = comment.content;

  if (isOwner) {
    item
      .querySelector('[data-action="delete"]')
      .addEventListener("click", () => onDelete(comment.id, item));

    item
      .querySelector('[data-action="edit"]')
      .addEventListener("click", () =>
        startEdit(item, comment, (newContent) => onEdit(comment.id, newContent))
      );
  }

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
  const currentUserId = user ? user.id : null;

  async function handleDelete(commentId, itemElem) {
    if (!confirm("Delete this comment?")) return;

    const res = await apiFetch(`/api/comments/${commentId}`, {
      method: "DELETE",
    });

    if (res.ok) {
      itemElem.remove();
      if (!listElem.querySelector(".comment-item")) {
        listElem.innerHTML = `<p class="no-comments">No comments yet. Be the first to share your thoughts!</p>`;
      }
    }
  }

  async function handleEdit(commentId, content) {
    const res = await apiFetch(`/api/comments/${commentId}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    });

    if (res.ok) {
      return await res.json();
    }
    return null;
  }

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
          const noComments = listElem.querySelector(".no-comments");
          if (noComments) noComments.remove();
          listElem.prepend(
            renderCommentItem(comment, currentUserId, {
              onDelete: handleDelete,
              onEdit: handleEdit,
            })
          );
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
        listElem.appendChild(
          renderCommentItem(comment, currentUserId, {
            onDelete: handleDelete,
            onEdit: handleEdit,
          })
        );
      }
    }
  }
}
