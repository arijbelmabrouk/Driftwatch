import { useState } from "react";
import { createTracker } from "../api";

export default function NewTrackerModal({ onClose, onCreated }) {
  const [topic, setTopic]           = useState("");
  const [frequency, setFrequency]   = useState("weekly");
  const [mode, setMode]             = useState("both");
  const [maxResults, setMaxResults] = useState(20);
  const [nResults, setNResults]     = useState(10);   // ← new
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");

  async function handleCreate() {
    if (!topic.trim()) {
      setError("Topic is required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await createTracker({
        topic:       topic.trim(),
        frequency:   frequency,
        report_mode: mode,
        max_results: parseInt(maxResults),
        n_results:   parseInt(nResults),   // ← new
      });
      onCreated();
    } catch {
      setError("Failed to create tracker. Make sure the API is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>

        <div style={styles.header}>
          <span style={styles.title}>New tracker</span>
          <button onClick={onClose} style={styles.closeBtn}>✕</button>
        </div>

        <div style={styles.body}>

          <Field label="Topic">
            <input
              style={styles.input}
              placeholder='e.g. "fraud detection with deep learning"'
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              autoFocus
            />
            <div style={styles.hint}>
              Plain English — Driftwatch converts it to an ArXiv query automatically.
            </div>
          </Field>

          <Field label="Frequency">
            <Select value={frequency} onChange={setFrequency} options={[
              { value: "daily",    label: "Daily" },
              { value: "weekly",   label: "Weekly (default)" },
              { value: "biweekly", label: "Biweekly" },
              { value: "monthly",  label: "Monthly" },
            ]} />
          </Field>

          <Field label="Report mode">
            <Select value={mode} onChange={setMode} options={[
              { value: "summary", label: "Summary only — what's happening" },
              { value: "delta",   label: "Delta only — what changed" },
              { value: "both",    label: "Both (default)" },
            ]} />
          </Field>

          <Field label="Max papers per run">
            <input
              style={{ ...styles.input, width: 80 }}
              type="number"
              min={5}
              max={100}
              value={maxResults}
              onChange={(e) => setMaxResults(e.target.value)}
            />
            <div style={styles.hint}>
              How many papers to fetch from ArXiv each run.
            </div>
          </Field>

          <Field label="Chunks retrieved per report">
            <input
              style={{ ...styles.input, width: 80 }}
              type="number"
              min={5}
              max={20}
              value={nResults}
              onChange={(e) => setNResults(e.target.value)}
            />
            <div style={styles.hint}>
              How many chunks the LLM reads to generate the report (default: 10).
            </div>
          </Field>

          {error && <div style={styles.error}>{error}</div>}

        </div>

        <div style={styles.footer}>
          <button onClick={onClose} style={styles.cancelBtn}>Cancel</button>
          <button
            onClick={handleCreate}
            disabled={loading || !topic.trim()}
            style={styles.createBtn(loading || !topic.trim())}
          >
            {loading ? "Creating..." : "Create tracker"}
          </button>
        </div>

      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={fieldStyles.label}>{label}</div>
      {children}
    </div>
  );
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={fieldStyles.select}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

const fieldStyles = {
  label: {
    fontSize: 11,
    color: "#666672",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  select: {
    width: "100%",
    background: "#161619",
    border: "1px solid #2a2a34",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#c0c0d0",
    fontSize: 13,
    outline: "none",
    cursor: "pointer",
  },
};

const styles = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 100,
  },
  modal: {
    background: "#161619",
    border: "1px solid #2a2a34",
    borderRadius: 10,
    width: 440,
    maxWidth: "90vw",
    boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 20px",
    borderBottom: "1px solid #222228",
  },
  title: {
    fontSize: 14,
    fontWeight: 600,
    color: "#e8e8f0",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "#555560",
    cursor: "pointer",
    fontSize: 14,
    padding: 4,
  },
  body: {
    padding: "20px 20px 8px",
  },
  input: {
    width: "100%",
    background: "#111114",
    border: "1px solid #2a2a34",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#c0c0d0",
    fontSize: 13,
    outline: "none",
    boxSizing: "border-box",
  },
  hint: {
    fontSize: 11,
    color: "#444450",
    marginTop: 5,
  },
  error: {
    background: "#1e1010",
    border: "1px solid #3a1818",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#c05050",
    fontSize: 12,
    marginBottom: 8,
  },
  footer: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 8,
    padding: "12px 20px 16px",
    borderTop: "1px solid #222228",
  },
  cancelBtn: {
    padding: "8px 16px",
    background: "transparent",
    border: "1px solid #2a2a34",
    borderRadius: 6,
    color: "#888896",
    fontSize: 13,
    cursor: "pointer",
  },
  createBtn: (disabled) => ({
    padding: "8px 18px",
    background: disabled ? "#1e1e26" : "#2e2e8a",
    border: "1px solid " + (disabled ? "#2a2a34" : "#3a3aaa"),
    borderRadius: 6,
    color: disabled ? "#444450" : "#a0a0e8",
    fontSize: 13,
    cursor: disabled ? "not-allowed" : "pointer",
  }),
};