// components/ReportPanel.jsx
import { useState } from "react";
import { runTracker, getLatestReport, askAboutReport } from "../api";

export default function ReportPanel({ tracker, onTrackerUpdated }) {
  const [report, setReport]       = useState(null);
  const [answer, setAnswer]       = useState("");
  const [question, setQuestion]   = useState("");
  const [loading, setLoading]     = useState(false);
  const [asking, setAsking]       = useState(false);
  const [error, setError]         = useState("");

  // Load saved report on mount / tracker change
  useState(() => {
    if (!tracker) return;
    getLatestReport(tracker.id).then(setReport).catch(() => setReport(null));
  }, [tracker?.id]);

  async function handleRun() {
    setLoading(true);
    setError("");
    setAnswer("");
    try {
      const result = await runTracker(tracker.id);
      if (result.delta) {
        setReport({
          report:        result.delta.report,
          week_current:  result.delta.week_current,
          week_previous: result.delta.week_previous,
          metadata: {
            new_papers:        result.delta.new_papers,
            continuing_papers: result.delta.continuing,
            dropped_papers:    result.delta.dropped,
          },
        });
      } else if (result.summary) {
        setReport({ report: result.summary, week_current: result.week_current });
      }
      if (result.errors?.length) setError(result.errors.join(" · "));
      onTrackerUpdated();
    } catch (e) {
      setError("Pipeline failed. Check the API terminal for details.");
    } finally {
      setLoading(false);
    }
  }

  async function handleAsk() {
    if (!question.trim()) return;
    setAsking(true);
    setAnswer("");
    try {
      const ans = await askAboutReport(tracker.id, question);
      setAnswer(ans);
    } catch {
      setAnswer("Could not get an answer. Make sure a report exists for this tracker.");
    } finally {
      setAsking(false);
    }
  }

  if (!tracker) {
    return (
      <div style={styles.empty}>
        Select a tracker or create one to get started.
      </div>
    );
  }

  return (
    <div style={styles.panel}>

      {/* Header */}
      <div style={styles.header}>
        <div>
          <div style={styles.title}>{tracker.topic}</div>
          {report && (
            <div style={styles.subtitle}>
              {report.week_previous
                ? `${report.week_previous} → ${report.week_current}`
                : report.week_current}
            </div>
          )}
        </div>
        <button
          onClick={handleRun}
          disabled={loading}
          style={styles.runBtn(loading)}
        >
          {loading ? "Running..." : "Run pipeline"}
        </button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Tracker cards grid */}
      <div style={styles.section}>
        <div style={styles.sectionLabel}>Tracker info</div>
        <div style={styles.infoGrid}>
          <InfoItem label="Frequency"   value={tracker.frequency} />
          <InfoItem label="Mode"        value={tracker.report_mode} />
          <InfoItem label="Max papers"  value={tracker.max_results} />
          <InfoItem label="Status"      value={tracker.status} />
          {report?.metadata && (
            <>
              <InfoItem label="New papers"       value={report.metadata.new_papers} />
              <InfoItem label="Continuing"       value={report.metadata.continuing_papers} />
              <InfoItem label="Dropped"          value={report.metadata.dropped_papers} />
            </>
          )}
        </div>
      </div>

      {/* Report */}
      {report ? (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>
            {report.week_previous ? "Delta report" : "Summary report"}
          </div>
          <div style={styles.reportBox}>
            {parseReport(report.report)}
          </div>
        </div>
      ) : (
        <div style={styles.noReport}>
          No report yet. Click "Run pipeline" to generate one.
        </div>
      )}

      {/* Answer from ask bar */}
      {answer && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Answer</div>
          <div style={styles.answerBox}>{answer}</div>
        </div>
      )}

      {/* Ask bar */}
      <div style={styles.askBar}>
        <input
          style={styles.askInput}
          placeholder="Ask about this report..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          disabled={asking}
        />
        <button
          onClick={handleAsk}
          disabled={asking || !question.trim()}
          style={styles.askBtn(asking || !question.trim())}
        >
          {asking ? "..." : "Ask"}
        </button>
      </div>

    </div>
  );
}

// ── Report renderer ───────────────────────────────────────────────────────────
// Splits the LLM report text into labeled sections for display.

function parseReport(text) {
  if (!text) return null;

  const sectionHeaders = [
    "1. MAIN THEME",
    "2. NOTABLE FINDINGS",
    "3. CONTESTED",
    "4. OPEN GAP",
    "1. NEW THIS WEEK",
    "2. STILL ACTIVE",
    "3. FADING OUT",
    "4. EMERGING DISPUTE",
  ];

  const lines = text.split("\n");
  const sections = [];
  let current = null;

  for (const line of lines) {
    const trimmed = line.trim();
    const isHeader = sectionHeaders.some((h) => trimmed.startsWith(h));

    if (isHeader) {
      if (current) sections.push(current);
      current = { header: trimmed, body: [] };
    } else if (current && trimmed) {
      current.body.push(trimmed);
    }
  }
  if (current) sections.push(current);

  if (sections.length === 0) {
    return <p style={styles.reportText}>{text}</p>;
  }

  return sections.map((s, i) => (
    <div key={i} style={styles.reportSection}>
      <div style={styles.reportHeader}>{s.header}</div>
      <div style={styles.reportText}>{s.body.join(" ")}</div>
    </div>
  ));
}

// ── Small info item ───────────────────────────────────────────────────────────

function InfoItem({ label, value }) {
  return (
    <div style={styles.infoItem}>
      <span style={styles.infoLabel}>{label}</span>
      <span style={styles.infoValue}>{value ?? "—"}</span>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = {
  panel: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    background: "#13131a",
    overflowY: "auto",
    position: "relative",
  },
  empty: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#444450",
    fontSize: 13,
    background: "#13131a",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "20px 28px 16px",
    borderBottom: "1px solid #1e1e26",
  },
  title: {
    fontSize: 16,
    fontWeight: 600,
    color: "#e8e8f0",
    textTransform: "capitalize",
    marginBottom: 2,
  },
  subtitle: {
    fontSize: 11,
    color: "#555560",
    fontFamily: "monospace",
  },
  runBtn: (disabled) => ({
    padding: "7px 16px",
    background: disabled ? "#1e1e26" : "#2e2e8a",
    border: "1px solid " + (disabled ? "#2a2a34" : "#3a3aaa"),
    borderRadius: 6,
    color: disabled ? "#444450" : "#a0a0e8",
    fontSize: 12,
    cursor: disabled ? "not-allowed" : "pointer",
    flexShrink: 0,
  }),
  error: {
    margin: "0 28px",
    padding: "8px 12px",
    background: "#1e1010",
    border: "1px solid #3a1818",
    borderRadius: 6,
    color: "#c05050",
    fontSize: 12,
    marginTop: 12,
  },
  section: {
    padding: "16px 28px",
    borderBottom: "1px solid #1a1a22",
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: "#444450",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    marginBottom: 10,
  },
  infoGrid: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  infoItem: {
    background: "#161619",
    border: "1px solid #222228",
    borderRadius: 6,
    padding: "6px 12px",
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  infoLabel: {
    fontSize: 9,
    color: "#444450",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  infoValue: {
    fontSize: 12,
    color: "#a0a0b0",
    textTransform: "capitalize",
  },
  reportBox: {
    background: "#111114",
    border: "1px solid #1e1e28",
    borderRadius: 8,
    padding: "16px 20px",
  },
  reportSection: {
    marginBottom: 16,
  },
  reportHeader: {
    fontSize: 11,
    fontWeight: 700,
    color: "#6060b0",
    letterSpacing: "0.06em",
    marginBottom: 6,
    fontFamily: "monospace",
  },
  reportText: {
    fontSize: 13,
    color: "#b0b0c0",
    lineHeight: 1.65,
  },
  noReport: {
    padding: "20px 28px",
    fontSize: 13,
    color: "#444450",
  },
  answerBox: {
    background: "#111118",
    border: "1px solid #1e1e2e",
    borderRadius: 8,
    padding: "14px 18px",
    fontSize: 13,
    color: "#b0b0c0",
    lineHeight: 1.65,
  },
  askBar: {
    position: "sticky",
    bottom: 0,
    display: "flex",
    gap: 8,
    padding: "12px 28px",
    background: "#13131a",
    borderTop: "1px solid #1e1e26",
  },
  askInput: {
    flex: 1,
    background: "#161619",
    border: "1px solid #262630",
    borderRadius: 6,
    padding: "9px 14px",
    color: "#c0c0d0",
    fontSize: 13,
    outline: "none",
  },
  askBtn: (disabled) => ({
    padding: "9px 18px",
    background: disabled ? "#1a1a22" : "#2a2a6a",
    border: "1px solid " + (disabled ? "#242430" : "#3636a0"),
    borderRadius: 6,
    color: disabled ? "#3a3a4a" : "#8080d0",
    fontSize: 13,
    cursor: disabled ? "not-allowed" : "pointer",
  }),
};