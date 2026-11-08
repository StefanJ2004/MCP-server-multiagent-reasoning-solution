# Demo video script (2 minutes)

Raw screen recording of the UI (no audio): `docs/video/demo-raw.webm` (not in git, ~12 MB; it covers scenes 3
and 4). Record the narration over it, or re-record live with `python -m web.server` + `npm run dev` in `web/ui`.
Running scenes 3 and 4 live costs about one cent.

| Time | Scene | On screen | Narration |
|---|---|---|---|
| 0:00–0:15 | 1. Problem | README title + hero screenshot | "Can a team of AI agents answer questions about company filings better than a single agent? We built both on the same data and measured it." |
| 0:15–0:35 | 2. Architecture | README diagram | "An MCP server exposes three tools over SEC filings of 18 companies: financial numbers, and a search over 10-K text that we wrote by hand. On top of it: a single agent, and a planner that splits the question across parallel researchers, with a synthesizer that writes the answer. No agent frameworks; the loop is about a hundred lines." |
| 0:35–1:05 | 3. Live, side by side | UI, "Uporedo", question B1 (all 18 companies) | "Here both run live. The single agent asks for all 18 companies in one step. The planner creates 18 subtasks and the researchers run in parallel; every model call and tool call streams to the browser over server-sent events." |
| 1:05–1:25 | 4. Citations | UI, "Multi-agent", question E3, click a green citation | "Every number and claim is cited. Green means a tool really returned that source in this run; clicking it shows the exact passage from Micron's 10-K." |
| 1:25–1:50 | 5. Results | README "Key results" table | "We ran 16 questions, three times each, with two models, graded blind. With a strong model the multi-agent system was just as accurate but three times more expensive. With a weaker model it won by 21 points on the hard questions, because the single agent ran out of steps on a broad task." |
| 1:50–2:00 | 6. Takeaway | README "Limitations and risks" | "So multi-agent is not free: it pays off for weaker models and broad tasks. And its planner decides before it sees data, which we documented as its main risk." |

Tips: record at 1440×900 or larger, zoom the browser to 110–125% so the text is readable in the video, and
keep each scene on screen a moment longer than feels necessary.
