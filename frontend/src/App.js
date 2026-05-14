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
import DealsPage from "./pages/DealsPage";
import DealDetailPage from "./pages/DealDetailPage";
import NewDealPage from "./pages/NewDealPage";
import MyDealsPage from "./pages/MyDealsPage";
import SubscribePage from "./pages/SubscribePage";
import BoostPage from "./pages/BoostPage";
import PaymentSuccessPage from "./pages/PaymentSuccessPage";
import PaymentCancelPage from "./pages/PaymentCancelPage";
import AdminMonetizationPage from "./pages/AdminMonetizationPage";
import SearchStudentsPage from "./pages/SearchStudentsPage";
import ApplicationDetailPage from "./pages/ApplicationDetailPage";
import SavedOffersPage from "./pages/SavedOffersPage";

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
        <Route path="/deals" element={<DealsPage />} />
        <Route path="/deals/new" element={<Protected><NewDealPage /></Protected>} />
        <Route path="/deals/mine" element={<Protected><MyDealsPage /></Protected>} />
        <Route path="/deals/:id" element={<DealDetailPage />} />
        <Route path="/payments/subscribe" element={<Protected><SubscribePage /></Protected>} />
        <Route path="/payments/boost" element={<Protected><BoostPage /></Protected>} />
        <Route path="/payment/success" element={<PaymentSuccessPage />} />
        <Route path="/payment/cancel" element={<PaymentCancelPage />} />
        <Route path="/admin/monetization" element={<Protected><AdminMonetizationPage /></Protected>} />
        <Route path="/search/students" element={<Protected><SearchStudentsPage /></Protected>} />
        <Route path="/applications/:id" element={<Protected><ApplicationDetailPage /></Protected>} />
        <Route path="/saved-offers" element={<Protected><SavedOffersPage /></Protected>} />
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
