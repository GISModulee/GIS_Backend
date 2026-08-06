import layerService from "@/utils/layerService.js";

// ── Tooltip HTML ──────────────────────────────────────────
export function buildTooltipHTML(feature, layer, area) {
  const name = feature.name || layer.name || "Untitled";
  const type = feature.type || "—";
  const category = feature.category || "—";
  const color = feature.color || "#2563eb";

  return `
    <div style="min-width:190px;font-family:system-ui,sans-serif;font-size:13px;line-height:1.5;">
      <div class="tooltip-title" style="font-weight:600;font-size:14px;margin-bottom:6px;">${name}</div>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td class="tooltip-label" style="padding:2px 0;width:80px;">Name</td>
            <td class="tooltip-value" style="font-weight:500;">${name}</td></tr>
        <tr><td class="tooltip-label" style="padding:2px 0;">Type</td>
            <td class="tooltip-value" style="font-weight:500;">${type}</td></tr>
        <tr><td class="tooltip-label" style="padding:2px 0;">Category</td>
            <td class="tooltip-value" style="font-weight:500;">${category}</td></tr>
        <tr><td class="tooltip-label" style="padding:2px 0;">Area</td>
            <td class="tooltip-value" style="font-weight:500;">${area ? Math.round(area).toLocaleString() + ' sqm' : '—'}</td></tr>
      </table>
    </div>
  `;
}

// ── Load + inject comments into tooltip ───────────────────
export async function loadComments(feature) {
  const caseId = feature.case_id;
  const featureNumber = feature.feature_number;
  if (!caseId || !featureNumber) return;
  const el = document.getElementById(`tooltip-comments-${feature.localId}`);
  if (!el) return;

  const layerId = feature.layer_id || 16;
  try {
    const comments = await layerService.getComments(caseId, layerId, featureNumber);

    if (!comments || comments.length === 0) {
      el.innerHTML = `<span style="color:#aaa;font-size:12px;">No comments</span>`;
      return;
    }

    const withImages = await Promise.all(
      comments.map(async (c) => {
        let imgSrc = null;
        if (c.has_image || c.image_id || c.image) {
          try {
            imgSrc = await layerService.getCommentImage(caseId, layerId, featureNumber, c.id);
          } catch (_) { }
        }
        return { ...c, imgSrc };
      })
    );

    el.innerHTML = `
      <div style="font-size:12px;color:#888;margin-bottom:4px;font-weight:600;">
        Comments (${withImages.length})
      </div>
      ${withImages.map((c) => `
        <div style="background:#f9f9f9;border-radius:6px;padding:6px 8px;
          margin-bottom:4px;font-size:12px;color:#444;line-height:1.4;">
          <div>${c.comment || c.text || ""}</div>
          ${c.imgSrc ? `
            <img src="${c.imgSrc}"
              style="margin-top:5px;width:100%;max-height:120px;
                object-fit:cover;border-radius:4px;border:1px solid #eee;"
              onerror="this.style.display='none'" />
          ` : ""}
        </div>
      `).join("")}
    `;
  } catch (_) {
    const el2 = document.getElementById(`tooltip-comments-${feature.localId}`);
    if (el2)
      el2.innerHTML = `<span style="color:#aaa;font-size:12px;">No comments</span>`;
  }
}
