import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

function Layout({ titre, children }) {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="contenu-principal" style={{ marginLeft: 240 }}>
        <Topbar titre={titre} />
        <div className="zone-page">{children}</div>
      </div>
    </div>
  );
}

export default Layout;