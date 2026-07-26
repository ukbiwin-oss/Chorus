const express = require("express");
const path = require("path");
const { runChorus } = require("./lib/orchestrator");

const app = express();
const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || "127.0.0.1";
const MAX_QUERY_LENGTH = 1000;

app.disable("x-powered-by");
app.use(express.json({ limit: "16kb" }));
app.use(express.static(path.join(__dirname, "public")));

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "chorus-v1", time: new Date().toISOString() });
});

app.post("/chorus", (req, res) => {
  try {
    const query = String(req.body?.query || "").trim();

    if (!query) {
      return res.status(400).json({
        error: "Missing query",
        hint: "POST JSON like { \"query\": \"best hotel in Manchester under £120\" }"
      });
    }

    if (query.length > MAX_QUERY_LENGTH) {
      return res.status(413).json({
        error: "Query too long",
        maximum_characters: MAX_QUERY_LENGTH
      });
    }

    const result = runChorus(query);
    return res.json(result);
  } catch (error) {
    console.error("/chorus failed:", error);
    return res.status(500).json({
      error: "Internal server error"
    });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`Chorus V1 listening on http://${HOST}:${PORT}`);
});
