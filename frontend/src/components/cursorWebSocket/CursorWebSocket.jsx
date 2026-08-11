import { useEffect, useRef } from "react";
import { useSelector } from "react-redux";
import { useMap as useLeafletMap } from "react-leaflet";
import L from "leaflet";
import { API_URLS } from "@/config/apiConfig.js";

const colors = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];
function getColor(userId) {
  const index = Math.abs(parseInt(userId, 10) || 0) % colors.length;
  return colors[index];
}

const cursorIcon = (color, name) => {
  const html = `
    <div style="position: relative; display: flex; align-items: center; pointer-events: none;">
      <svg width="14" height="18" viewBox="0 0 14 18" fill="none" xmlns="http://www.w3.org/2000/svg" style="transform: translate(-1px, -1px); filter: drop-shadow(1.5px 1.5px 1px rgba(0, 0, 0, 0.35));">
        <path d="M1 1V14.5L4.5 11.5L8.5 17L11.5 15L7.5 9.5H12.5L1 1Z" fill="${color}" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round"/>
      </svg>
      <div style="
        margin-left: 10px;
        background: ${color};
        color: white;
        font-family: sans-serif;
        font-size: 10px;
        font-weight: 600;
        padding: 2.5px 6px;
        border-radius: 4px;
        white-space: nowrap;
        box-shadow: 0px 1.5px 3px rgba(0,0,0,0.25);
        border: 1px solid rgba(255, 255, 255, 0.2);
      ">
        ${name}
      </div>
    </div>
  `;
  return L.divIcon({
    html,
    className: "collaborative-cursor",
    iconSize: [0, 0],
    iconAnchor: [0, 0]
  });
};

export default function CursorWebSocket({ caseId }) {
  const leafletMap = useLeafletMap();
  const currentUser = useSelector((s) => s.auth.user);
  const markersRef = useRef({});

  useEffect(() => {
    if (!caseId || !leafletMap) return;

    let socket = null;
    let reconnectTimeoutId = null;
    let reconnectDelay = 1000;
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted) return;

      const token =
        localStorage.getItem("token") ||
        localStorage.getItem("access_token") ||
        "";

      if (!token) {
        console.error("[CursorWS] Access token is missing.");
        return;
      }

      const websocketUrl = new URL(
        API_URLS.LAYERS,
        window.location.origin
      );

      websocketUrl.protocol =
        websocketUrl.protocol === "https:"
          ? "wss:"
          : "ws:";

      websocketUrl.pathname = `/ws/cases/${caseId}/cursors`;
      websocketUrl.search = `?token=${encodeURIComponent(token)}`;

      console.log("[CursorWS] Connecting to:", websocketUrl.toString());

      socket = new WebSocket(websocketUrl.toString());

      let lastSent = 0;
      const THROTTLE_MS = 100;

      const handleMouseMove = (e) => {
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        const now = Date.now();
        if (now - lastSent < THROTTLE_MS) return;
        lastSent = now;
        socket.send(JSON.stringify({
          lat: e.latlng.lat,
          lng: e.latlng.lng
        }));
      };

      socket.onopen = () => {
        console.log("[CursorWS] Connected for case:", caseId);
        reconnectDelay = 1000;
        leafletMap.on("mousemove", handleMouseMove);
      };

      socket.onmessage = (event) => {
        if (isUnmounted) return;

        try {
          const message = JSON.parse(event.data);

          if (message.event === "cursor.moved") {
            const { user_id, user_full_name, lat, lng } = message;
            if (currentUser && Number(user_id) === Number(currentUser.id)) return;

            const latlng = L.latLng(lat, lng);
            const color = getColor(user_id);
            
            if (markersRef.current[user_id]) {
              markersRef.current[user_id].setLatLng(latlng);
            } else {
              const marker = L.marker(latlng, {
                icon: cursorIcon(color, user_full_name),
                interactive: false,
                zIndexOffset: 2000
              }).addTo(leafletMap);
              markersRef.current[user_id] = marker;
            }
          } else if (message.event === "cursor.left") {
            const { user_id } = message;
            if (markersRef.current[user_id]) {
              leafletMap.removeLayer(markersRef.current[user_id]);
              delete markersRef.current[user_id];
            }
          }
        } catch (err) {
          console.error("[CursorWS] Error parsing message:", err);
        }
      };

      socket.onclose = (event) => {
        console.log(`[CursorWS] Closed for case ${caseId}. Code: ${event.code}`);
        leafletMap.off("mousemove", handleMouseMove);
        if (isUnmounted) return;

        if (event.code === 1008) {
          console.error("[CursorWS] Authentication failed. Reconnect disabled.");
          return;
        }

        const delay = reconnectDelay;
        console.log(`[CursorWS] Reconnecting in ${delay}ms...`);
        reconnectTimeoutId = window.setTimeout(connect, delay);
        reconnectDelay = Math.min(reconnectDelay * 2, 16000);
      };

      socket.onerror = (error) => {
        console.error("[CursorWS] Connection error:", error);
        try {
          socket.close();
        } catch (_) {}
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimeoutId) window.clearTimeout(reconnectTimeoutId);
      if (socket) {
        socket.onclose = null;
        try {
          socket.close();
        } catch (_) {}
      }
      Object.keys(markersRef.current).forEach((user_id) => {
        try { leafletMap.removeLayer(markersRef.current[user_id]); } catch (_) {}
      });
      markersRef.current = {};
    };
  }, [caseId, leafletMap, currentUser]);

  return null;
}
