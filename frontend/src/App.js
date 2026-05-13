import React from "react";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import { AuthProvider, useAuth } from "./context/AuthContext";
import Header from "./components/Header";

import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import AuthCallback from "./pages/AuthCallback";
import DashboardPage from "./pages/DashboardPage";
import OffersPage from "./pages/OffersPage";
import OfferDetailPage from "./pages/OfferDetailPage";
import PublishOfferPage from "./pages/PublishOfferPage";
import ProfilePage from "./pages/ProfilePage";
import FeedPage from "./pages/FeedPage";
import MessagesPage from "./pages/MessagesPage";
import ContactsPage from "./pages/ContactsPage";
import NotificationsPage from "./pages/NotificationsPage";
import SettingsPage from "./pages/SettingsPage";
import AdminPage from "./pages/AdminPage";

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="pt-24 text-center text-slate-400">Chargement...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/offers" element={<OffersPage />} />
        <Route path="/offers/new" element={<Protected><PublishOfferPage /></Protected>} />
        <Route path="/offers/:id" element={<OfferDetailPage />} />
        <Route path="/profile/:id" element={<ProfilePage />} />
        <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
        <Route path="/feed" element={<Protected><FeedPage /></Protected>} />
        <Route path="/messages" element={<Protected><MessagesPage /></Protected>} />
        <Route path="/contacts" element={<Protected><ContactsPage /></Protected>} />
        <Route path="/notifications" element={<Protected><NotificationsPage /></Protected>} />
        <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
        <Route path="/admin" element={<Protected><AdminPage /></Protected>} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
          <Toaster position="top-right" richColors />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
