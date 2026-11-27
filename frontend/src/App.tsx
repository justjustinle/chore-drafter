import { Link, Route, Routes } from "react-router-dom";
import { ApiChoice } from "./api/context";
import { httpApi } from "./api/client";
import AcceptInvite from "./pages/AcceptInvite";
import Demo from "./pages/Demo";
import Home from "./pages/Home";
import HouseholdPage from "./pages/HouseholdPage";

export default function App() {
  return (
    <div className="page">
      <header className="topbar">
        <Link to="/" className="brand">
          <span aria-hidden="true">🪙</span> Chore Draft
        </Link>
      </header>
      <Routes>
        <Route path="/demo/*" element={<Demo />} />
        <Route
          path="*"
          element={
            <ApiChoice.Provider value={httpApi}>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/invites/:token" element={<AcceptInvite />} />
                <Route path="/h/:id" element={<HouseholdPage />} />
                <Route path="/h/:id/history" element={<HouseholdPage tab="history" />} />
                <Route path="*" element={<p>This path leads nowhere. <Link to="/">Back to the front door</Link></p>} />
              </Routes>
            </ApiChoice.Provider>
          }
        />
      </Routes>
    </div>
  );
}
