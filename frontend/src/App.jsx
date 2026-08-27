import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const API = "http://localhost:8000/api";

function App() {
  const [kpis, setKpis] = useState(null);
  const [serieVentes, setSerieVentes] = useState([]);
  const [prevision, setPrevision] = useState([]);
  const [clientsRisque, setClientsRisque] = useState([]);
  const [reconciliation, setReconciliation] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/kpis`).then((r) => r.json()),
      fetch(`${API}/ventes-mensuelles`).then((r) => r.json()),
      fetch(`${API}/prevision`).then((r) => r.json()),
      fetch(`${API}/clients-risque`).then((r) => r.json()),
      fetch(`${API}/reconciliation-impayes`).then((r) => r.json()),
    ])
      .then(([kpisData, serieData, previsionData, clientsData, reconciliationData]) => {
        setKpis(kpisData);
        setSerieVentes(serieData);
        setPrevision(previsionData);
        setClientsRisque(clientsData);
        setReconciliation(reconciliationData);
      })
      .catch((err) => setErreur(err.message));
  }, []);

  const donneesGraphique = [
    ...serieVentes.map((p) => ({
      mois: `${p.annee}-${String(p.mois).padStart(2, "0")}`,
      reel: Math.round(p.montant_total),
      prevu: null,
    })),
    ...prevision.map((p) => ({
      mois: p.date_mois.slice(0, 7),
      reel: null,
      prevu: Math.round(p.montant_prevu),
    })),
  ];

  const couleurNiveau = { Faible: "#3B6D11", Moyen: "#854F0B", "Élevé": "#D85A30" };
  const couleurStatut = { "Payée": "#3B6D11", "Partielle": "#854F0B", "Impayée": "#D85A30" };

  const envoyerQuestion = async () => {
    const question = chatInput.trim();
    if (!question || chatLoading) return;

    setChatMessages((msgs) => [...msgs, { role: "user", texte: question }]);
    setChatInput("");
    setChatLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      const texte = res.ok ? data.reponse : `Erreur : ${data.detail}`;
      setChatMessages((msgs) => [...msgs, { role: "bot", texte, sql: data.sql }]);
    } catch (err) {
      setChatMessages((msgs) => [...msgs, { role: "bot", texte: `Erreur : ${err.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  if (erreur) return <p style={{ padding: "2rem", color: "red" }}>Erreur : {erreur}</p>;
  if (!kpis) return <p style={{ padding: "2rem" }}>Chargement...</p>;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: 1100, margin: "0 auto" }}>
      <h1>As Plastique — Pilotage data</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "2rem" }}>
        <CarteKPI label="Ventes totales" valeur={`${kpis.total_ventes_dh.toLocaleString()} DH`} />
        <CarteKPI label="Documents extraits" valeur={kpis.nb_documents} />
        <CarteKPI label="Clients" valeur={kpis.nb_clients} />
        <CarteKPI label="Impayés totaux (snapshot)" valeur={`${kpis.total_impaye_dh.toLocaleString()} DH`} accent="#D85A30" />
      </div>

      <h2>Ventes mensuelles &amp; prévision (6 prochains mois)</h2>
      <div style={{ background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: "1rem" }}>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={donneesGraphique}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="mois" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v) => v?.toLocaleString() + " DH"} />
            <Legend />
            <Line type="monotone" dataKey="reel" name="Réel" stroke="#0E7C7B" strokeWidth={2} dot={false} connectNulls />
            <Line type="monotone" dataKey="prevu" name="Prévision" stroke="#9CA3AF" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 3 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h2 style={{ marginTop: "2rem" }}>Top clients — risque impayés</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #eee" }}>
            <th style={{ padding: "8px" }}>Client</th>
            <th style={{ padding: "8px" }}>Score</th>
            <th style={{ padding: "8px" }}>Niveau</th>
            <th style={{ padding: "8px" }}>Montant impayé</th>
            <th style={{ padding: "8px" }}>Relevés</th>
            <th style={{ padding: "8px" }}>Ancienneté (j)</th>
          </tr>
        </thead>
        <tbody>
          {clientsRisque.slice(0, 10).map((c, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
              <td style={{ padding: "8px" }}>{c.client}</td>
              <td style={{ padding: "8px" }}>{c.score_risque}</td>
              <td style={{ padding: "8px" }}>
                <span style={{
                  padding: "3px 10px", borderRadius: 12, fontSize: 12,
                  background: `${couleurNiveau[c.niveau_risque]}22`,
                  color: couleurNiveau[c.niveau_risque],
                }}>
                  {c.niveau_risque}
                </span>
              </td>
              <td style={{ padding: "8px" }}>{c.montant_total_impaye?.toLocaleString()} DH</td>
              <td style={{ padding: "8px" }}>{c.nombre_releves}</td>
              <td style={{ padding: "8px" }}>{c.anciennete_moyenne_jours?.toFixed(0) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* --- Réconciliation grand livre (Sprint 5) --- */}
      <h2 style={{ marginTop: "2rem" }}>Réconciliation impayés — grand livre client</h2>
      <p style={{ fontSize: 13, color: "#666", marginTop: -8 }}>
        Comparaison entre les montants listés impayés dans nos relevés extraits (à un instant T) et
        le solde réellement dû selon le grand livre client de l'entreprise.
      </p>

      {reconciliation && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1rem" }}>
            <CarteKPI
              label="Impayé listé (snapshot)"
              valeur={`${reconciliation.total_impaye_snapshot.toLocaleString()} DH`}
            />
            <CarteKPI
              label="Solde réel (grand livre)"
              valeur={`${reconciliation.total_solde_reel.toLocaleString()} DH`}
              accent="#D85A30"
            />
            <CarteKPI
              label="Montant réglé depuis / à corriger"
              valeur={`${reconciliation.montant_regularise.toLocaleString()} DH`}
              accent="#3B6D11"
            />
            <CarteKPI
              label="Taux de rapprochement"
              valeur={`${reconciliation.taux_rapprochement_pct}%`}
            />
          </div>

          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "2px solid #eee" }}>
                <th style={{ padding: "8px" }}>Statut réel</th>
                <th style={{ padding: "8px" }}>Nombre de lignes</th>
                <th style={{ padding: "8px" }}>Montant snapshot</th>
                <th style={{ padding: "8px" }}>Solde réel</th>
              </tr>
            </thead>
            <tbody>
              {reconciliation.par_statut.map((s, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                  <td style={{ padding: "8px" }}>
                    <span style={{
                      padding: "3px 10px", borderRadius: 12, fontSize: 12,
                      background: `${couleurStatut[s.statut_reel] || "#999"}22`,
                      color: couleurStatut[s.statut_reel] || "#666",
                    }}>
                      {s.statut_reel}
                    </span>
                  </td>
                  <td style={{ padding: "8px" }}>{s.nombre}</td>
                  <td style={{ padding: "8px" }}>{s.montant_snapshot?.toLocaleString()} DH</td>
                  <td style={{ padding: "8px" }}>{s.montant_solde_reel?.toLocaleString()} DH</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* --- Assistant conversationnel (Sprint 5) --- */}
      <h2 style={{ marginTop: "2rem" }}>Assistant data</h2>
      <p style={{ fontSize: 13, color: "#666", marginTop: -8 }}>
        Pose une question libre sur les ventes, les impayés ou les produits — l'agent interroge
        directement la base de données.
      </p>
      <div style={{ background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: "1rem", marginBottom: "2rem" }}>
        <div style={{ maxHeight: 300, overflowY: "auto", marginBottom: "0.75rem" }}>
          {chatMessages.length === 0 && (
            <p style={{ color: "#999", fontSize: 13 }}>
              Exemples : "Quel client a le plus d'impayés ?", "Combien de factures ont été payées selon le grand livre ?"
            </p>
          )}
          {chatMessages.map((m, i) => (
            <div key={i} style={{ marginBottom: "0.6rem", textAlign: m.role === "user" ? "right" : "left" }}>
              <div style={{
                display: "inline-block", maxWidth: "80%", padding: "8px 12px", borderRadius: 14,
                background: m.role === "user" ? "#0E7C7B" : "#f2f2f2",
                color: m.role === "user" ? "#fff" : "#222", fontSize: 14,
              }}>
                {m.texte}
              </div>
              {m.sql && (
                <div style={{ fontSize: 11, color: "#999", marginTop: 2, fontFamily: "monospace" }}>
                  SQL : {m.sql}
                </div>
              )}
            </div>
          ))}
          {chatLoading && <p style={{ color: "#999", fontSize: 13 }}>L'agent réfléchit...</p>}
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && envoyerQuestion()}
            placeholder="Pose ta question..."
            style={{ flex: 1, padding: "8px 12px", borderRadius: 8, border: "1px solid #ddd" }}
          />
          <button
            onClick={envoyerQuestion}
            disabled={chatLoading}
            style={{
              padding: "8px 16px", borderRadius: 8, border: "none",
              background: "#0E7C7B", color: "#fff", cursor: "pointer",
            }}
          >
            Envoyer
          </button>
        </div>
      </div>
    </div>
  );
}

function CarteKPI({ label, valeur, accent = "#0E7C7B" }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: "1rem" }}>
      <p style={{ fontSize: 12, color: "#666", margin: "0 0 6px" }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 600, margin: 0, color: accent }}>{valeur}</p>
    </div>
  );
}

export default App;