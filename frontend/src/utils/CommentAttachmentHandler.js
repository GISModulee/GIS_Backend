import toast from "react-hot-toast";

export const openCommentAttachment = (commentId) => {
  const attachment = window.commentAttachmentsCache?.[commentId];
  if (!attachment || !attachment.data) {
    toast.error("Attachment data not loaded.");
    return;
  }

  try {
    const base64Data = attachment.data;
    const filename = attachment.filename || "attachment";
    const contentType = attachment.contentType || "application/octet-stream";

    const byteCharacters = atob(base64Data.split(',')[1]);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: contentType });
    const blobUrl = URL.createObjectURL(blob);

    const newTab = window.open();
    if (newTab) {
      newTab.location.href = blobUrl;
    } else {
      // fallback
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  } catch (err) {
    console.error("Failed to open attachment:", err);
    toast.error("Failed to open attachment.");
  }
};
