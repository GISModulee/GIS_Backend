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

