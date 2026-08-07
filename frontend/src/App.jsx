import { useEffect, useState } from "react";

function App() {
  const [kpis, setKpis] = useState(null);
  const [documents, setDocuments] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/kpis")
      .then((res) => res.json())
      .then(setKpis)
      .catch(() => console.error("Erreur KPIs"));

    fetch("http://localhost:8000/api/documents?statut=ok")
      .then((res) => res.json())
      .then(setDocuments)
      .catch(() => console.error("Erreur documents"));
  }, []);

  if (!kpis) return <p>Chargement...</p>;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>As Plastique — Extraction (échantillon)</h1>
      <ul>
        <li>Documents extraits : {kpis.documents_extraits} / {kpis.documents_echantillon}</li>
        <li>Taux d'extraction : {kpis.taux_extraction_pct}%</li>
        <li>Montant total extrait : {kpis.montant_total_extrait} DH</li>
        <li>Bons de livraison : {kpis.nb_bons_livraison}</li>
        <li>Factures : {kpis.nb_factures}</li>
      </ul>

      <h2>Documents ({documents.length})</h2>
      <table border="1" cellPadding="6">
        <thead>
          <tr>
            <th>Fichier</th><th>Onglet</th><th>Type</th><th>N° Doc</th><th>Date</th><th>Articles</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((d, i) => (
            <tr key={i}>
              <td>{d.fichier}</td><td>{d.onglet}</td><td>{d.type_detecte}</td>
              <td>{d.doc_number}</td><td>{d.date}</td><td>{d.n_items}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;