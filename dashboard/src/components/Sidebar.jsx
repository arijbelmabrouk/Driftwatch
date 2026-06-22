// components/Sidebar.jsx
export default function Sidebar({ trackers, selectedId, onSelect, onNewTracker }) {
  return (
    <aside style={styles.sidebar}>
      <div style={styles.logo}>Driftwatch</div>

      <nav style={styles.nav}>
        <div style={styles.navLabel}>My Trackers</div>
        {trackers.map((t) => (
          <div
            key={t.id}
            onClick={() => onSelect(t.id)}
            style={{
              ...styles.navItem,
              ...(t.id === selectedId ? styles.navItemActive : {}),
            }}
          >
            <span style={styles.navDot(t.status)} />
            <span style={styles.navText}>{t.topic}</span>
          </div>
        ))}
      </nav>

      <button onClick={onNewTracker} style={styles.newBtn}>
        + New tracker
      </button>
    </aside>
  );
}

const styles = {
  sidebar: {
    width: 220,
    minHeight: "100vh",
    background: "#111114",
    borderRight: "1px solid #222228",
    display: "flex",
    flexDirection: "column",
    padding: "0 0 16px 0",
    flexShrink: 0,
  },
  logo: {
    padding: "20px 20px 16px",
    fontSize: 15,
    fontWeight: 600,
    color: "#e8e8f0",
    borderBottom: "1px solid #222228",
    letterSpacing: "0.01em",
  },
  nav: {
    flex: 1,
    padding: "12px 0",
    overflowY: "auto",
  },
  navLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: "#555560",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    padding: "4px 20px 8px",
  },
  navItem: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "7px 20px",
    cursor: "pointer",
    borderRadius: 4,
    margin: "1px 8px",
    color: "#888896",
    fontSize: 13,
    transition: "background 0.1s",
  },
  navItemActive: {
    background: "#1e1e26",
    color: "#e8e8f0",
  },
  navText: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  navDot: (status) => ({
    width: 6,
    height: 6,
    borderRadius: "50%",
    flexShrink: 0,
    background:
      status === "running" ? "#f0a030" :
      status === "error"   ? "#e05050" :
                             "#30b060",
  }),
  newBtn: {
    margin: "0 12px",
    padding: "9px 0",
    background: "transparent",
    border: "1px solid #333340",
    borderRadius: 6,
    color: "#888896",
    fontSize: 13,
    cursor: "pointer",
    transition: "border-color 0.1s, color 0.1s",
  },
};