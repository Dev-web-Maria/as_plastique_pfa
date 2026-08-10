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
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/kpis`).then((r) => r.json()),
      fetch(`${API}/ventes-mensuelles`).then((r) => r.json()),
      fetch(`${API}/prevision`).then((r) => r.json()),
      fetch(`${API}/clients-risque`).then((r) => r.json()),
    ])
      .then(([kpisData, serieData, previsionData, clientsData]) => {
        setKpis(kpisData);
        setSerieVentes(serieData);
        setPrevision(previsionData);
        setClientsRisque(clientsData);
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

  if (erreur) return <p style={{ padding: "2rem", color: "red" }}>Erreur : {erreur}</p>;
  if (!kpis) return <p style={{ padding: "2rem" }}>Chargement...</p>;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: 1100, margin: "0 auto" }}>
      <h1>As Plastique — Pilotage data</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "2rem" }}>
        <CarteKPI label="Ventes totales" valeur={`${kpis.total_ventes_dh.toLocaleString()} DH`} />
        <CarteKPI label="Documents extraits" valeur={kpis.nb_documents} />
        <CarteKPI label="Clients" valeur={kpis.nb_clients} />
        <CarteKPI label="Impayés totaux" valeur={`${kpis.total_impaye_dh.toLocaleString()} DH`} accent="#D85A30" />
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