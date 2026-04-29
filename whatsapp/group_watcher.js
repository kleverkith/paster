const fs = require("fs");
const path = require("path");
const express = require("express");
const cors = require("cors");
const qrcode = require("qrcode-terminal");
const { Client, LocalAuth } = require("whatsapp-web.js");

const baseDir = path.resolve(__dirname, "..");
const dataDir = path.join(baseDir, "data");
const mediaDir = path.join(dataDir, "media");
const statusPath = path.join(dataDir, "status.json");
const messagesPath = path.join(dataDir, "messages.jsonl");
const timezone = process.env.WHATSAPP_TIMEZONE || "Africa/Nairobi";

fs.mkdirSync(dataDir, { recursive: true });
fs.mkdirSync(mediaDir, { recursive: true });

function parseArgs(argv) {
  const options = {
    group: process.env.WHATSAPP_GROUP_NAME || "",
    port: Number(process.env.WHATSAPP_WATCHER_PORT || 3001),
    saveMedia: process.env.WHATSAPP_SAVE_MEDIA !== "false",
    historyLimit: Number(process.env.WHATSAPP_HISTORY_LIMIT || 2000),
  };

  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if ((arg === "--group" || arg === "-g") && argv[index + 1]) {
      options.group = argv[index + 1];
      index += 1;
    } else if (arg === "--port" && argv[index + 1]) {
      options.port = Number(argv[index + 1]);
      index += 1;
    } else if (arg === "--no-media") {
      options.saveMedia = false;
    } else if (arg === "--history-limit" && argv[index + 1]) {
      options.historyLimit = Number(argv[index + 1]);
      index += 1;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    }
  }

  return options;
}

function printHelp() {
  console.log("Usage: npm run watch -- --group \"Your Group Name\"");
  console.log("Options:");
  console.log("  --group, -g   Exact WhatsApp group name to watch");
  console.log("  --port        Local status API port, default 3001");
  console.log("  --no-media    Skip downloading attached media");
  console.log("  --history-limit  Number of recent group messages to backfill on startup");
}

function readJson(pathName) {
  if (!fs.existsSync(pathName)) {
    return {};
  }
  try {
    const raw = fs.readFileSync(pathName, "utf8").trim();
    if (!raw) {
      return {};
    }
    return JSON.parse(raw);
  } catch (_error) {
    return {};
  }
}

function updateStatus(patch) {
  const next = {
    ...readJson(statusPath),
    ...patch,
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(statusPath, JSON.stringify(next, null, 2));
}

function appendJsonl(filePath, payload) {
  fs.appendFileSync(filePath, `${JSON.stringify(payload)}\n`, "utf8");
}

function rewriteJsonl(filePath, payloads) {
  const lines = payloads.map((payload) => JSON.stringify(payload)).join("\n");
  fs.writeFileSync(filePath, lines ? `${lines}\n` : "", "utf8");
}

function sanitizeFileName(value) {
  return value.replace(/[^a-zA-Z0-9._-]/g, "_");
}

function normalizeGroupName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function currentLocalDate() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function localDateForIso(value) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

async function saveMedia(message) {
  const media = await message.downloadMedia();
  if (!media) {
    return null;
  }

  const extension = media.mimetype.split("/")[1]?.split(";")[0] || "bin";
  const filename = sanitizeFileName(`${Date.now()}-${message.id.id}.${extension}`);
  const filePath = path.join(mediaDir, filename);
  fs.writeFileSync(filePath, media.data, { encoding: "base64" });
  return {
    filePath,
    mimetype: media.mimetype,
    filename,
  };
}

function loadExistingRecords() {
  if (!fs.existsSync(messagesPath)) {
    return [];
  }
  return fs
    .readFileSync(messagesPath, "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch (_error) {
        return null;
      }
    })
    .filter(Boolean);
}

function toRecord(message, chatName, author, mediaInfo) {
  return {
    id: message.id.id,
    chatName,
    from: message.from,
    author,
    timestamp: new Date(message.timestamp * 1000).toISOString(),
    body: message.body || "",
    caption: message._data?.caption || "",
    type: message.type,
    hasMedia: Boolean(message.hasMedia),
    media: mediaInfo,
  };
}

async function bootstrap() {
  const options = parseArgs(process.argv);
  if (!options.group) {
    printHelp();
    process.exit(1);
  }

  updateStatus({
    state: "starting",
    groupName: options.group,
    port: options.port,
    saveMedia: options.saveMedia,
    historyLimit: options.historyLimit,
    session: "initializing",
    timezone,
    currentDay: currentLocalDate(),
    error: null,
  });

  const recentMessages = loadExistingRecords().slice(-500);
  const seenMessageIds = new Set(recentMessages.map((record) => record.id));
  let availableGroups = [];
  let activeGroupName = options.group;

  function refreshDailyWindow() {
    const today = currentLocalDate();
    const filtered = recentMessages.filter((record) => localDateForIso(record.timestamp) === today);
    if (filtered.length !== recentMessages.length) {
      recentMessages.splice(0, recentMessages.length, ...filtered);
      seenMessageIds.clear();
      for (const record of recentMessages) {
        seenMessageIds.add(record.id);
      }
      rewriteJsonl(messagesPath, recentMessages);
    }
    updateStatus({
      currentDay: today,
      totalCachedMessages: recentMessages.length,
      error: null,
    });
  }

  refreshDailyWindow();
  const app = express();
  app.use(cors());

  app.get("/status", (_req, res) => {
    res.json(readJson(statusPath));
  });

  app.get("/messages", (_req, res) => {
    refreshDailyWindow();
    res.json(recentMessages.slice(-200));
  });

  app.get("/groups", (_req, res) => {
    res.json(availableGroups);
  });

  app.listen(options.port, () => {
    updateStatus({ api: `http://localhost:${options.port}` });
    console.log(`Watcher API ready at http://localhost:${options.port}`);
  });

  setInterval(() => {
    refreshDailyWindow();
  }, 60000);

  const client = new Client({
    authStrategy: new LocalAuth({ clientId: "paster" }),
    puppeteer: {
      headless: false,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    },
  });

  client.on("qr", (qr) => {
    console.log("\nScan this QR code with WhatsApp:\n");
    qrcode.generate(qr, { small: true });
    updateStatus({ state: "awaiting_qr_scan", session: "qr_ready" });
  });

  client.on("authenticated", () => {
    console.log("WhatsApp authenticated.");
    updateStatus({ state: "authenticated", session: "authenticated" });
  });

  client.on("auth_failure", (message) => {
    console.error("Authentication failure:", message);
    updateStatus({ state: "auth_failure", error: message });
  });

  async function syncRecentHistory() {
    const chats = await client.getChats();
    availableGroups = chats.filter((item) => item.isGroup).map((item) => item.name).sort();
    const exactMatch = chats.find((item) => item.isGroup && item.name === options.group);
    const desired = normalizeGroupName(options.group);
    const partialMatches = chats.filter(
      (item) =>
        item.isGroup &&
        (normalizeGroupName(item.name).includes(desired) || desired.includes(normalizeGroupName(item.name))),
    );
    const chat = exactMatch || (partialMatches.length === 1 ? partialMatches[0] : null);
    if (!chat) {
      updateStatus({
        state: "group_not_found",
        session: "ready",
        availableGroups: availableGroups.slice(0, 50),
        matchingGroups: partialMatches.map((item) => item.name),
        error: null,
      });
      console.error(`Group not found: ${options.group}`);
      return;
    }

    activeGroupName = chat.name;

    updateStatus({ state: "syncing_history", session: "ready" });
    const fetched = await chat.fetchMessages({ limit: options.historyLimit });
    const normalized = fetched.sort((a, b) => a.timestamp - b.timestamp);
    let added = 0;

    for (const message of normalized) {
      if (!message.id?.id || seenMessageIds.has(message.id.id)) {
        continue;
      }
      const contact = await message.getContact();
      const record = toRecord(
        message,
        chat.name,
        contact.pushname || contact.name || message.author || message.from,
        null,
      );
      if (localDateForIso(record.timestamp) !== currentLocalDate()) {
        continue;
      }
      recentMessages.push(record);
      seenMessageIds.add(record.id);
      added += 1;
    }

    if (recentMessages.length > 500) {
      recentMessages.splice(0, recentMessages.length - 500);
    }
    rewriteJsonl(messagesPath, recentMessages);
    updateStatus({
      state: "watching",
      session: "ready",
      activeGroupName,
      currentDay: currentLocalDate(),
      syncedHistoryCount: added,
      totalCachedMessages: recentMessages.length,
      lastMessageAt: recentMessages.length ? recentMessages[recentMessages.length - 1].timestamp : null,
      error: null,
    });
    console.log(`History sync complete. Added ${added} messages.`);
  }

  client.on("ready", async () => {
    console.log(`Watcher is ready. Filtering group: ${options.group}`);
    updateStatus({ state: "ready", session: "ready" });
    try {
      await syncRecentHistory();
    } catch (error) {
      console.error("History sync failed:", error);
      updateStatus({ state: "history_sync_failed", error: error.message, session: "ready" });
    }
  });

  client.on("disconnected", (reason) => {
    console.error("WhatsApp disconnected:", reason);
    updateStatus({ state: "disconnected", reason });
  });

  client.on("message", async (message) => {
    try {
      const chat = await message.getChat();
      if (!chat.isGroup || chat.name !== activeGroupName) {
        return;
      }

      const contact = await message.getContact();
      let mediaInfo = null;
      if (options.saveMedia && message.hasMedia) {
        mediaInfo = await saveMedia(message);
      }

      if (!message.id?.id || seenMessageIds.has(message.id.id)) {
        return;
      }

      const record = toRecord(
        message,
        chat.name,
        contact.pushname || contact.name || message.author || message.from,
        mediaInfo,
      );
      refreshDailyWindow();
      if (localDateForIso(record.timestamp) !== currentLocalDate()) {
        return;
      }

      recentMessages.push(record);
      seenMessageIds.add(record.id);
      if (recentMessages.length > 500) {
        recentMessages.shift();
      }

      appendJsonl(messagesPath, record);
      updateStatus({
        state: "watching",
        currentDay: currentLocalDate(),
        lastMessageAt: record.timestamp,
        lastAuthor: record.author,
        lastType: record.type,
        totalCachedMessages: recentMessages.length,
        error: null,
      });

      console.log(`[${record.timestamp}] ${record.author}: ${record.body || "[media]"}`);
    } catch (error) {
      console.error("Failed to process message:", error);
      updateStatus({ state: "error", error: error.message });
    }
  });

  await client.initialize();
}

bootstrap().catch((error) => {
  console.error(error);
  updateStatus({ state: "fatal_error", error: error.message });
  process.exit(1);
});
