import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import TrackerCard from "./components/TrackerCard";
import ReportPanel from "./components/ReportPanel";
import NewTrackerModal from "./components/NewTrackerModal";
import { getTrackers } from "./api";

export default function App() {
  const [trackers, setTrackers]         = useState([]);
  const [selectedId, setSelectedId]     = useState(null);
  const [showModal, setShowModal]       = useState(false);
  const [loading, setLoading]           = useState(true);

  // Load trackers on mount
  useEffect(() => {
    loadTrackers();
  }, []);

  async function loadTrackers() {
    setLoading(true);
    try {
      const data = await getTrackers();
      setTrackers(data);
      // Auto-select the first tracker if none selected
      if (!selectedId && data.length > 0) {
        setSelectedId(data[0].id);
      }
    } catch {
      setTrackers([]);
    } finally {
      setLoading(false);
    }
  }

  const selectedTracker = trackers.find((t) => t.id === selectedId) ?? null;

  return (
    <div style={styles.app}>

      {/* Left sidebar — tracker list + new tracker button */}
      <Sidebar
        trackers={trackers}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onNewTracker={() => setShowModal(true)}
      />

      {/* Main area */}
      <div style={styles.main}>

        {/* Tracker cards grid */}
        <div style={styles.gridArea}>
          <div style={styles.gridLabel}>Your trackers</div>
          {loading ? (
            <div style={styles.gridEmpty}>Loading...</div>
          ) : trackers.length === 0 ? (
            <div style={styles.gridEmpty}>
              No trackers yet. Click "+ New tracker" to create one.
            </div>
          ) : (
            <div style={styles.grid}>
              {trackers.map((t) => (
                <TrackerCard
                  key={t.id}
                  tracker={t}
                  isSelected={t.id === selectedId}
                  onClick={() => setSelectedId(t.id)}
                />
              ))}
              {/* Add tracker card */}
              <div
                onClick={() => setShowModal(true)}
                style={styles.addCard}
              >
                + Add tracker
              </div>
            </div>
          )}
        </div>

        {/* Delta report panel */}
        <ReportPanel
          tracker={selectedTracker}
          onTrackerUpdated={loadTrackers}
        />

      </div>

      {/* New tracker modal */}
      {showModal && (
        <NewTrackerModal
          onClose={() => setShowModal(false)}
          onCreated={() => {
            setShowModal(false);
            loadTrackers();
          }}
        />
      )}

    </div>
  );
}

const styles = {
  app: {
    display: "flex",
    height: "100vh",
    background: "#13131a",
    fontFamily: "'Inter', system-ui, sans-serif",
    color: "#e8e8f0",
    overflow: "hidden",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  gridArea: {
    padding: "20px 28px 0",
    borderBottom: "1px solid #1e1e26",
    flexShrink: 0,
  },
  gridLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: "#555560",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    marginBottom: 12,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
    gap: 10,
    paddingBottom: 16,
  },
  gridEmpty: {
    fontSize: 13,
    color: "#444450",
    paddingBottom: 16,
  },
  addCard: {
    background: "transparent",
    border: "1px dashed #2a2a34",
    borderRadius: 8,
    padding: "14px 16px",
    cursor: "pointer",
    color: "#444450",
    fontSize: 13,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 80,
    transition: "border-color 0.15s, color 0.15s",
  },
};