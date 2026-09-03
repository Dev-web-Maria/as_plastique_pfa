import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./Layout";
import VueGlobale from "./VueGlobale";
import Ventes from "./Ventes";
import Impayes from "./Impayes";
import Clients from "./Clients";
import ClientDetail from "./ClientDetail";
import BonsLivraison from "./BonsLivraison";
import Factures from "./Factures";
import Previsions from "./Previsions";
import AssistantData from "./AssistantData";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout titre="Vue globale"><VueGlobale /></Layout>} />
        <Route path="/ventes" element={<Layout titre="Ventes"><Ventes /></Layout>} />
        <Route path="/clients" element={<Layout titre="Clients"><Clients /></Layout>} />
        <Route path="/clients/:id" element={<Layout titre="Détail client"><ClientDetail /></Layout>} />
        <Route path="/bons-livraison" element={<Layout titre="Bons de livraison"><BonsLivraison /></Layout>} />
        <Route path="/factures" element={<Layout titre="Factures"><Factures /></Layout>} />
        <Route path="/impayes" element={<Layout titre="Impayés"><Impayes /></Layout>} />
        <Route path="/previsions" element={<Layout titre="Prévisions"><Previsions /></Layout>} />
        <Route path="/assistant" element={<Layout titre="Assistant Data"><AssistantData /></Layout>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;