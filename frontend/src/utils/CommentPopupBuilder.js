export const buildCommentPopupHTML = (commentsList, featureBackendId, loggedInUser = null, isLoading = false) => {
  if (!window.commentAttachmentsCache) {
    window.commentAttachmentsCache = {};
  }

  return `
    <div style="min-width: 250px; max-width: 320px; font-family: system-ui, -apple-system, sans-serif; font-size: 13px; line-height: 1.4; padding: 4px;">
      <div class="comment-popup-title" style="font-weight: 700; font-size: 13px; margin-bottom: 8px; padding-bottom: 6px;">
        Comments
      </div>
      <div class="popup-comments-container" style="max-height: 160px; overflow-y: auto; display: flex; flex-direction: column-reverse; gap: 6px; margin-bottom: 8px; padding-right: 8px; ${isLoading ? "justify-content: center; align-items: center; min-height: 60px;" : ""}">
        ${isLoading ? `
          <style>
            @keyframes popup-spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          </style>
          <div style="display: flex; flex-direction: column; align-items: center; gap: 6px; color: #6b7280; font-size: 11px; padding: 20px 0; width: 100%;">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" width="20" height="20" style="animation: popup-spin 1s linear infinite; color: #2563eb;">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" style="opacity: 0.25;"></circle>
              <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" style="opacity: 0.75;"></path>
            </svg>
            <span>Loading comments...</span>
          </div>
        ` : [...commentsList].reverse().map(c => {
    const isCurrentUser = loggedInUser && (Number(c.user_id) === Number(loggedInUser.id) || !c.user_id);
    const commentUserEmail = c.user_email || c.email || c.user?.email;
    const commentUserName = c.user_username || c.username || c.user?.username || c.user_full_name || c.user?.full_name;
    const email = commentUserEmail || (isCurrentUser ? loggedInUser.email : "") || commentUserName || "User";
    const displayName = email;
    const letter = displayName.charAt(0).toUpperCase();

    const filename = (c.attachment_filename || c.attachment || c.image || "").toLowerCase();
    const isImg = (c.attachment_content_type && c.attachment_content_type.startsWith("image/")) ||
      filename.endsWith(".png") ||
      filename.endsWith(".jpg") ||
      filename.endsWith(".jpeg") ||
      filename.endsWith(".gif") ||
      filename.endsWith(".webp") ||
      filename.endsWith(".svg") ||
      c.has_image ||
      c.image_id;

    let attachmentHTML = "";
    if (c.imgSrc) {
      // Save base64 data to memory cache to avoid passing large data in inline click attribute
      window.commentAttachmentsCache[c.id] = {
        data: c.imgSrc,
        filename: c.attachment_filename || "attachment",
        contentType: c.attachment_content_type || "application/octet-stream"
      };

      if (isImg) {
        attachmentHTML = `
                <a href="javascript:void(0)" onclick="window.openCommentAttachment('${c.id}')" style="display: block; margin-top: 6px;" title="Click to view full image">
                  <img class="comment-img" src="${c.imgSrc}" style="width: 100%; max-height: 120px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e7eb;" />
                </a>
              `;
      } else {
        const displayFilename = c.attachment_filename || "View Attachment";
        attachmentHTML = `
                <a href="javascript:void(0)" onclick="window.openCommentAttachment('${c.id}')" style="margin-top: 6px; display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 6px; font-size: 11px; text-decoration: none; font-weight: 600; cursor: pointer;" title="Click to open attachment">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                  </svg>
                  <span style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${displayFilename}</span>
                </a>
              `;
      }
    }

    return `
            <div class="comment-card" style="border-radius: 8px; padding: 8px; display: flex; gap: 8px; align-items: flex-start; margin-top: 2px;">
              <div style="width: 20px; height: 20px; border-radius: 50%; background-color: #2563eb; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; flex-shrink: 0; margin-top: 2px;">
                ${letter}
              </div>
              <div style="flex: 1; min-width: 0;">
                <div class="comment-user" style="font-size: 10px; font-weight: 600; margin-bottom: 2px; truncate; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${displayName}">${displayName}</div>
                <div class="comment-text" style="font-weight: 500; word-break: break-word;">${c.comment || c.text || ""}</div>
                ${attachmentHTML}
              </div>
            </div>
          `;
  }).join("")}
      </div>

      <!-- Popup Quick Comment Form -->
      <div style="border-top: 1.5px solid #f3f4f6; padding-top: 8px; margin-top: 8px; display: flex; flex-direction: column; gap: 6px;">
        <div style="display: flex; gap: 4px; align-items: center;">
          <input id="popup-comment-input-${featureBackendId}" class="popup-comment-input" type="text" placeholder="Add a comment..." onkeydown="if(event.key === 'Enter') { event.preventDefault(); window.submitPopupComment('${featureBackendId}'); }" style="flex: 1; border-radius: 6px; padding: 4px 8px; font-size: 11px; outline: none;" />
          
          <!-- Pin Icon (Attach file) -->
          <button onclick="document.getElementById('popup-file-input-${featureBackendId}').click()" style="background: none; border: none; cursor: pointer; padding: 2px; color: #10b981; display: flex; align-items: center;" title="Attach file">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
            </svg>
          </button>
          <input type="file" id="popup-file-input-${featureBackendId}" accept="image/*,.pdf,.doc,.docx,.txt" style="display: none;" onchange="window.handlePopupFileChange('${featureBackendId}', this)" />

          <!-- Send / Submit Icon -->
          <button onclick="window.submitPopupComment('${featureBackendId}')" style="background: #2563eb; border: none; border-radius: 6px; cursor: pointer; padding: 4px; color: #fff; display: flex; align-items: center; justify-content: center;" title="Send">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
        <!-- Preview of selected file -->
        <div id="popup-file-preview-${featureBackendId}" class="popup-file-preview" style="display: none; font-size: 10px; align-items: center; gap: 4px; padding-left: 2px;">
          <span id="popup-file-name-${featureBackendId}" style="font-weight: 500; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">📎 File selected</span>
          <button onclick="window.clearPopupFile('${featureBackendId}')" style="background: none; border: none; cursor: pointer; color: #ef4444; display: inline-flex; align-items: center; justify-content: center; padding: 2px;" title="Remove file">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>
    </div>
  `;
};
