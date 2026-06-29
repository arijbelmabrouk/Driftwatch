import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import TrackerCard from "./components/TrackerCard";
import ReportPanel from "./components/ReportPanel";
import NewTrackerModal from "./components/NewTrackerModal";
import AuthScreen from "./components/AuthScreen";
import { getTrackers, getCurrentUser, loginUser, registerUser } from "./api";

export default function App() {
  const [trackers, setTrackers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("driftwatch_token");
    if (!token) {
      setAuthLoading(false);
      return;
    }

    loadSession();
  }, []);

  useEffect(() => {
    if (user) {
      loadTrackers();
    } else {
      setTrackers([]);
      setSelectedId(null);
    }
  }, [user]);

  async function loadSession() {
    setAuthLoading(true);
    try {
      const data = await getCurrentUser();
      setUser(data.user);
      setAuthError("");
    } catch {
      localStorage.removeItem("driftwatch_token");
      setUser(null);
    } finally {
      setAuthLoading(false);
    }
  }

  async function loadTrackers() {
    setLoading(true);
    try {
      const data = await getTrackers();
      setTrackers(data);
      if (!selectedId && data.length > 0) {
        setSelectedId(data[0].id);
      }
    } catch {
      setTrackers([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleAuth(mode, email, password) {
    setAuthLoading(true);
    setAuthError("");
    try {
      const data = mode === "login"
        ? await loginUser(email, password)
        : await registerUser(email, password);

      localStorage.setItem("driftwatch_token", data.access_token);
      const session = await getCurrentUser();
      setUser(session.user);
    } catch (error) {
      setAuthError(error.message || "Authentication failed");
    } finally {
      setAuthLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("driftwatch_token");
    setUser(null);
    setTrackers([]);
    setSelectedId(null);
    setAuthError("");
  }

  const selectedTracker = trackers.find((t) => t.id === selectedId) ?? null;

  if (authLoading) {
    return <div style={styles.authLoading}>Loading...</div>;
  }

  if (!user) {
    return <AuthScreen onSubmit={handleAuth} loading={authLoading} error={authError} />;
  }

  return (
    <div style={styles.app}>
      <div style={styles.topBar}>
        <div style={styles.userInfo}>Signed in as {user.email}</div>
        <button onClick={handleLogout} style={styles.logoutBtn}>Logout</button>
      </div>

      <div style={styles.dashboard}>
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
  authLoading: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#13131a",
    color: "#e8e8f0",
    fontFamily: "'Inter', system-ui, sans-serif",
  },
  app: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: "#13131a",
    fontFamily: "'Inter', system-ui, sans-serif",
    color: "#e8e8f0",
    overflow: "hidden",
  },
  topBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 20px",
    borderBottom: "1px solid #1e1e26",
    background: "#171722",
  },
  userInfo: {
    fontSize: 13,
    color: "#8d8da3",
  },
  logoutBtn: {
    background: "transparent",
    border: "1px solid #2a2a34",
    color: "#e8e8f0",
    padding: "8px 12px",
    borderRadius: 8,
    cursor: "pointer",
  },
  dashboard: {
    display: "flex",
    flex: 1,
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