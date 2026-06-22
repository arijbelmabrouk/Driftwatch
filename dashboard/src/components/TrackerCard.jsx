// components/TrackerCard.jsx
export default function TrackerCard({ tracker, isSelected, onClick }) {
  const lastRun = tracker.last_run
    ? new Date(tracker.last_run).toLocaleDateString("en-GB", {
        day: "numeric", month: "short",
      })
    : "Never run";

  return (
    <div
      onClick={onClick}
      style={{
        ...styles.card,
        ...(isSelected ? styles.cardSelected : {}),
      }}
    >
      <div style={styles.header}>
        <span style={styles.topic}>{tracker.topic}</span>
        <span style={styles.dot(tracker.status)} />
      </div>

      <div style={styles.meta}>
        Last run: {lastRun}
      </div>

      <div style={styles.footer}>
        <span style={styles.badge}>{tracker.frequency}</span>
        <span style={styles.badge}>{tracker.report_mode}</span>
        {tracker.signal_count > 0 && (
          <span style={styles.signals}>{tracker.signal_count} papers</span>
        )}
      </div>
    </div>
  );
}

const styles = {
  card: {
    background: "#161619",
    border: "1px solid #222228",
    borderRadius: 8,
    padding: "14px 16px",
    cursor: "pointer",
    transition: "border-color 0.15s",
  },
  cardSelected: {
    borderColor: "#4a4aaa",
    background: "#17171e",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  topic: {
    fontSize: 13,
    fontWeight: 600,
    color: "#e8e8f0",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    maxWidth: "85%",
  },
  dot: (status) => ({
    width: 7,
    height: 7,
    borderRadius: "50%",
    flexShrink: 0,
    background:
      status === "running" ? "#f0a030" :
      status === "error"   ? "#e05050" :
                             "#30b060",
  }),
  meta: {
    fontSize: 11,
    color: "#555560",
    marginBottom: 10,
  },
  footer: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
  },
  badge: {
    fontSize: 10,
    color: "#666672",
    background: "#1e1e26",
    border: "1px solid #2a2a34",
    borderRadius: 4,
    padding: "2px 7px",
    textTransform: "capitalize",
  },
  signals: {
    fontSize: 10,
    color: "#4a9a6a",
    background: "#152018",
    border: "1px solid #1e3024",
    borderRadius: 4,
    padding: "2px 7px",
  },
};