const { getDataset } = require("./mockData");

function extractBudget(query) {
  const poundMatch = query.match(/£\s*(\d+)/i);
  if (poundMatch) return Number(poundMatch[1]);

  const underMatch = query.match(/under\s+(\d+)/i);
  if (underMatch) return Number(underMatch[1]);

  const maxMatch = query.match(/max\s+(\d+)/i);
  if (maxMatch) return Number(maxMatch[1]);

  return null;
}

function scoreOption(option, budget) {
  let score = 0;

  if (budget !== null) {
    if (option.price <= budget) {
      score += 30;
      score += Math.max(0, budget - option.price) * 0.08;
    } else {
      score -= (option.price - budget) * 1.2;
    }
  }

  score += option.rating * 6;
  score += option.official ? 10 : -18;
  score += option.refundable ? 8 : -7;
  score += Math.max(0, 10 - option.distanceKm * 4);

  return Number(score.toFixed(2));
}

function finderAgent(query, budget) {
  const options = getDataset(query)
    .map((item) => ({ ...item, score: scoreOption(item, budget) }))
    .sort((a, b) => b.score - a.score);

  return {
    agent: "finder",
    budget,
    options
  };
}

function judgeAgent(found) {
  const top = found.options.slice(0, 3);
  const best = top[0];
  const alternatives = top.slice(1);

  return {
    agent: "judge",
    best,
    alternatives,
    reasoning: [
      `${best.name} has the strongest overall score in this sample set.`,
      `It balances price (${currency(best.price)}), rating (${best.rating}/10), and risk profile (${best.official ? "official" : "unofficial"}).`,
      best.refundable ? "Refundability strengthens it." : "Its lack of refundability weakens it slightly."
    ]
  };
}

function criticAgent(judged, budget) {
  const caveats = [];
  const best = judged.best;

  if (!best.official) {
    caveats.push("Chosen option is not from an official/verified route, so trust is weaker.");
  }
  if (!best.refundable) {
    caveats.push("Chosen option is not refundable.");
  }
  if (budget !== null && best.price > budget) {
    caveats.push(`Chosen option is above the stated budget by ${currency(best.price - budget)}.`);
  }
  if (best.distanceKm > 1.0) {
    caveats.push("Chosen option is not especially central / convenient.");
  }

  const challenger = judged.alternatives[0];
  if (challenger && challenger.price < best.price && challenger.rating >= best.rating - 0.5) {
    caveats.push(`${challenger.name} deserves attention because it is cheaper and not dramatically worse.`);
  }

  if (caveats.length === 0) {
    caveats.push("No major red flags inside this tiny V1 dataset, but live price/fee checks are not implemented yet.");
  }

  return {
    agent: "critic",
    caveats
  };
}

function confidence(best, critic) {
  let value = 0.82;
  if (!best.official) value -= 0.18;
  if (!best.refundable) value -= 0.08;
  value -= Math.min(0.18, critic.caveats.length * 0.03);
  return Number(Math.max(0.35, Math.min(0.95, value)).toFixed(2));
}

function currency(value) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0
  }).format(value);
}

function runChorus(query) {
  const budget = extractBudget(query);
  const found = finderAgent(query, budget);
  const judged = judgeAgent(found);
  const critic = criticAgent(judged, budget);
  const best = judged.best;

  return {
    mode: "chorus-v1",
    query,
    budget,
    best: {
      id: best.id,
      name: best.name,
      category: best.category,
      price: best.price,
      price_display: currency(best.price),
      rating: best.rating,
      official: best.official,
      refundable: best.refundable,
      notes: best.notes
    },
    alternatives: judged.alternatives.map((item) => ({
      id: item.id,
      name: item.name,
      price: item.price,
      price_display: currency(item.price),
      rating: item.rating,
      official: item.official,
      refundable: item.refundable
    })),
    judge_reasoning: judged.reasoning,
    critic_caveats: critic.caveats,
    confidence: confidence(best, critic),
    debug: {
      finder_ranked_ids: found.options.map((item) => item.id),
      note: "This V1 uses mocked data so the workflow can be built before live retrieval is plugged in."
    }
  };
}

module.exports = { runChorus };
