import { writable } from "svelte/store";
import { browser } from "$app/environment";
import { PUBLIC_WS_URL } from "$env/static/public";

function createRoomsStore() {
  const { subscribe, set } = writable([]);

  let reconnectTimeout = null;
  let ws = null;
  let reconnectAttempts = 0;
  const baseReconnectDelayMs = 1000;
  const maxReconnectDelayMs = 30000;
  let isTornDown = false;

  function connect() {
    ws = new WebSocket(`${PUBLIC_WS_URL}/ws/rooms`);

    ws.onopen = () => {
      console.log("WebSocket connected");
      reconnectAttempts = 0;
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error("Failed to parse rooms WebSocket message", error, event.data);
        return;
      }

      if (!Array.isArray(data)) {
        console.error("Unexpected rooms WebSocket payload, expected an array", data);
        return;
      }

      set(data);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected, retrying...");
      reconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function reconnect() {
    if (isTornDown) {
      return;
    }

    clearTimeout(reconnectTimeout);

    const expDelay = Math.min(
      maxReconnectDelayMs,
      baseReconnectDelayMs * Math.pow(2, reconnectAttempts)
    );
    const jitter = Math.random() * (expDelay * 0.5);
    const delay = expDelay + jitter;

    reconnectAttempts += 1;
    reconnectTimeout = setTimeout(connect, delay);
  }

  if (browser) {
    connect();
  }

  return {
    subscribe,
    destroy() {
      isTornDown = true;
      clearTimeout(reconnectTimeout);
      if (
        ws &&
        (ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING)
      ) {
        ws.close();
      }
    },
  };
}

export const roomsStore = createRoomsStore();
