import { useState } from "react";

const MOIS = [
  "Tous les mois", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

// À ajuster selon la vraie couverture de données (2018-2021 confirmée par le projet)
const ANNEES = [2018, 2019, 2020, 2021];

function FiltrePeriode({ onAppliquer }) {
  const [annee, setAnnee] = useState(ANNEES[ANNEES.length - 1]);
  const [mois, setMois] = useState(0); // 0 = "Tous les mois"
  const [dateDebut, setDateDebut] = useState("");
  const [dateFin, setDateFin] = useState("");

  const appliquer = () => {
    onAppliquer({
      annee,
      mois: mois === 0 ? null : mois,
      dateDebut: dateDebut || null,
      dateFin: dateFin || null,
    });
  };

  return (
    <div style={styles.conteneur}>
      <div style={styles.groupe}>
        <label style={styles.label}>Année</label>
        <select value={annee} onChange={(e) => setAnnee(Number(e.target.value))} style={styles.select}>
          {ANNEES.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      <div style={styles.groupe}>
        <label style={styles.label}>Mois</label>
        <select value={mois} onChange={(e) => setMois(Number(e.target.value))} style={styles.select}>
          {MOIS.map((m, i) => (
            <option key={m} value={i}>{m}</option>
          ))}
        </select>
      </div>

      <div style={styles.groupe}>
        <label style={styles.label}>Période (optionnel)</label>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} style={styles.dateInput} />
          <span style={{ color: "var(--gris-texte)" }}>au</span>
          <input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} style={styles.dateInput} />
        </div>
      </div>

      <button onClick={appliquer} style={styles.bouton}>
        Appliquer
      </button>
    </div>
  );
}

const styles = {
  conteneur: {
    display: "flex",
    alignItems: "flex-end",
    gap: "1rem",
    background: "#fff",
    border: "1px solid var(--gris-bordure)",
    borderRadius: 12,
    padding: "1rem 1.25rem",
    marginBottom: "1.5rem",
    flexWrap: "wrap",
  },
  groupe: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    color: "var(--gris-texte)",
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  select: {
    padding: "7px 10px",
    borderRadius: 6,
    border: "1px solid var(--gris-bordure)",
    fontSize: 13,
    minWidth: 130,
  },
  dateInput: {
    padding: "6px 8px",
    borderRadius: 6,
    border: "1px solid var(--gris-bordure)",
    fontSize: 13,
  },
  bouton: {
    padding: "9px 18px",
    borderRadius: 8,
    border: "none",
    background: "var(--bleu-marine)",
    color: "#fff",
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
    height: 34,
  },
};

export default FiltrePeriode;