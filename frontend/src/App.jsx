import { useEffect, useState } from "react";

function App() {
  const [message, setMessage] = useState("Connexion en cours...");

  useEffect(() => {
    fetch("http://localhost:8000/api/ping")
      .then((res) => res.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage("Erreur : backend injoignable"));
  }, []);

  return <h1>{message}</h1>;
}

export default App;