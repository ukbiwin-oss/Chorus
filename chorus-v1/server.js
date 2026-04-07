const express = require("express");
const path = require("path");
const { runChorus } = require("./lib/orchestrator");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: "1mb" }));
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

    const result = runChorus(query);
    return res.json(result);
  } catch (error) {
    console.error("/chorus failed:", error);
    return res.status(500).json({
      error: "Internal server error",
      detail: error.message
    });
  }
});

app.listen(PORT, () => {
  console.log(`Chorus V1 listening on http://localhost:${PORT}`);
});
