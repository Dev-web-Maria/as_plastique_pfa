import { useState } from "react";

const API = "http://localhost:8000/api";

const EXEMPLES = [
  "Quel client a le plus d'impayés ?",
  "Combien de factures ont été payées selon le grand livre ?",
  "Combien de produits différents sont vendus par l'entreprise ?",
  "Quel est le chiffre d'affaires total en 2020 ?",
];

function AssistantData() {
  const [messages, setMessages] = useState([]);
  const [saisie, setSaisie] = useState("");
  const [chargement, setChargement] = useState(false);

  const envoyerQuestion = async (question) => {
    if (!question.trim() || chargement) return;

    setMessages((msgs) => [...msgs, { role: "user", texte: question }]);
    setSaisie("");
    setChargement(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      const texte = res.ok ? data.reponse : `Erreur : ${data.detail}`;
      setMessages((msgs) => [...msgs, { role: "bot", texte, sql: data.sql }]);
    } catch (err) {
      setMessages((msgs) => [...msgs, { role: "bot", texte: `Erreur : ${err.message}` }]);
    } finally {
      setChargement(false);
    }
  };

  return (
    <>
      {messages.length === 0 && (
        <div className="carte" style={{ marginBottom: "1rem" }}>
          <p style={{ fontSize: 13, color: "var(--gris-texte)", marginTop: 0 }}>Exemples de questions :</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {EXEMPLES.map((q, i) => (
              <button
                key={i}
                onClick={() => envoyerQuestion(q)}
                style={{
                  padding: "8px 14px", borderRadius: 20, border: "1px solid var(--gris-bordure)",
                  background: "#fff", fontSize: 13, cursor: "pointer", color: "var(--bleu-marine)",
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="carte" style={{ display: "flex", flexDirection: "column", minHeight: 400 }}>
        <div style={{ flex: 1, overflowY: "auto", marginBottom: "1rem" }}>
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: "0.8rem", textAlign: m.role === "user" ? "right" : "left" }}>
              <div style={{
                display: "inline-block", maxWidth: "75%", padding: "10px 14px", borderRadius: 14,
                background: m.role === "user" ? "var(--bleu-marine)" : "#f2f2f2",
                color: m.role === "user" ? "#fff" : "#222", fontSize: 14, whiteSpace: "pre-wrap",
              }}>
                {m.texte}
              </div>
            </div>
          ))}
          {chargement && <p style={{ color: "var(--gris-texte)", fontSize: 13 }}>L'agent réfléchit...</p>}
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && envoyerQuestion(saisie)}
            placeholder="Pose ta question..."
            style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid var(--gris-bordure)", fontSize: 14 }}
          />
          <button
            onClick={() => envoyerQuestion(saisie)}
            disabled={chargement}
            style={{
              padding: "10px 20px", borderRadius: 8, border: "none",
              background: "var(--bleu-marine)", color: "#fff", cursor: "pointer", fontWeight: 600,
            }}
          >
            Envoyer
          </button>
        </div>
      </div>
    </>
  );
}

export default AssistantData;