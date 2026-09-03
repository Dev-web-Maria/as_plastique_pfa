import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const API = "http://localhost:8000/api";

function Previsions() {
  const [serieVentes, setSerieVentes] = useState([]);
  const [prevision, setPrevision] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/ventes-mensuelles`).then((r) => r.json()),
      fetch(`${API}/prevision`).then((r) => r.json()),
    ])
      .then(([serieData, previsionData]) => {
        setSerieVentes(serieData);
        setPrevision(previsionData);
        setErreur(null);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  }, []);

  const historiqueRecent = serieVentes.slice(-12);

  const donneesGraphique = [
    ...historiqueRecent.map((p) => ({
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

  const totalPrevu = prevision.reduce((acc, p) => acc + p.montant_prevu, 0);
  const moyenneMensuellePrevue = prevision.length ? totalPrevu / prevision.length : 0;

  if (chargement) return <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>;
  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;

  return (
    <>
      <div className="grille-kpi">
        <CarteKPI label="Prévision totale (6 mois)" valeur={`${totalPrevu.toLocaleString(undefined, { maximumFractionDigits: 0 })} DH`} />
        <CarteKPI label="Moyenne mensuelle prévue" valeur={`${moyenneMensuellePrevue.toLocaleString(undefined, { maximumFractionDigits: 0 })} DH`} />
        <CarteKPI label="Modèle retenu" valeur="XGBoost" />
        <CarteKPI label="Fiabilité (MAPE, validation croisée)" valeur="19,9%" />
      </div>

      <div className="carte">
        <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>
          Historique récent (12 derniers mois) &amp; prévision (6 prochains mois)
        </h3>
        <p style={{ fontSize: 12, color: "var(--gris-texte)", marginTop: -8 }}>
          Modèle XGBoost, retenu après validation croisée temporelle (walk-forward, 4 plis).
        </p>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={donneesGraphique}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="mois" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v) => v?.toLocaleString() + " DH"} />
            <Legend />
            <Line type="monotone" dataKey="reel" name="Réel" stroke="var(--bleu-marine)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            <Line type="monotone" dataKey="prevu" name="Prévision" stroke="var(--rouge-accent)" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 3 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="carte" style={{ marginTop: "1rem" }}>
        <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Détail mois par mois</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
              <th style={{ padding: "8px 4px" }}>Mois</th>
              <th style={{ padding: "8px 4px" }}>Montant prévu</th>
            </tr>
          </thead>
          <tbody>
            {prevision.map((p, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                <td style={{ padding: "8px 4px" }}>{p.date_mois.slice(0, 7)}</td>
                <td style={{ padding: "8px 4px", fontWeight: 600 }}>{p.montant_prevu.toLocaleString(undefined, { maximumFractionDigits: 0 })} DH</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function CarteKPI({ label, valeur }) {
  return (
    <div className="carte">
      <p style={{ fontSize: 12, color: "var(--gris-texte)", margin: "0 0 6px" }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "var(--bleu-marine)" }}>{valeur}</p>
    </div>
  );
}

export default Previsions;