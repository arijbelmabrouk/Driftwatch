import { useState } from "react";

export default function AuthScreen({ onSubmit, loading, error }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit(mode, email, password);
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.card}>
        <h2 style={styles.title}>Driftwatch</h2>
        <p style={styles.subtitle}>Sign in to view your trackers and reports.</p>

        <div style={styles.toggleRow}>
          <button
            type="button"
            onClick={() => setMode("login")}
            style={{ ...styles.toggleBtn, ...(mode === "login" ? styles.toggleActive : {}) }}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            style={{ ...styles.toggleBtn, ...(mode === "register" ? styles.toggleActive : {}) }}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={styles.input}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={styles.input}
          />
          {error ? <div style={styles.error}>{error}</div> : null}
          <button type="submit" disabled={loading} style={styles.submitBtn}>
            {loading ? "Please wait..." : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#13131a",
    color: "#e8e8f0",
    fontFamily: "'Inter', system-ui, sans-serif",
  },
  card: {
    width: 360,
    background: "#1b1b24",
    border: "1px solid #2a2a34",
    borderRadius: 14,
    padding: 24,
    boxShadow: "0 12px 30px rgba(0,0,0,0.25)",
  },
  title: {
    fontSize: 24,
    margin: "0 0 8px",
  },
  subtitle: {
    margin: "0 0 16px",
    color: "#8d8da3",
    fontSize: 14,
  },
  toggleRow: {
    display: "flex",
    gap: 8,
    marginBottom: 16,
  },
  toggleBtn: {
    flex: 1,
    padding: "10px 12px",
    background: "#23232d",
    color: "#e8e8f0",
    border: "1px solid #2f2f3a",
    borderRadius: 8,
    cursor: "pointer",
  },
  toggleActive: {
    background: "#2f6eea",
    borderColor: "#2f6eea",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  input: {
    padding: "12px 14px",
    borderRadius: 8,
    border: "1px solid #2f2f3a",
    background: "#101018",
    color: "#e8e8f0",
  },
  submitBtn: {
    padding: "12px 14px",
    borderRadius: 8,
    border: "none",
    background: "#2f6eea",
    color: "white",
    cursor: "pointer",
    fontWeight: 600,
  },
  error: {
    color: "#ff8a8a",
    fontSize: 13,
  },
};
