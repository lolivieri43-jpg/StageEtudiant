# StagiaireConnect — Product Requirements Document

## Original Problem Statement
Build a modern, professional, responsive French platform connecting companies with student interns and apprentices (stagiaires/alternants). Two user types (Entreprise / Stagiaire-Alternant), with LinkedIn-style profiles, Facebook-style feed, internal messaging, offers/applications, interactive France map, dashboards and admin panel. Style inspired by LinkedIn, Facebook and Welcome to the Jungle.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) + JWT auth + Emergent Google OAuth bridge
- **Frontend**: React 19 + React Router 7 + Tailwind + Shadcn UI + Sonner toasts + date-fns
- **Database collections**: users, user_sessions, offers, applications, posts, comments, messages, conversations, contacts, contact_requests, notifications
- **Auth**: Bearer JWT (localStorage) for email/password + session_token cookie for Emergent Google OAuth

## User Personas
1. **Étudiant·e (stagiaire/alternant)** — recherche un stage ou une alternance
2. **Recruteur·euse (entreprise)** — publie des offres et trouve des candidats
3. **Administrateur** — modère et vérifie les entreprises

## Core Requirements (static)
- Inscription dual (entreprise vs candidat)
- Recherche d'offres + filtres + carte de France interactive
- Profils publics LinkedIn-like (banner + avatar + sections)
- Système d'offres + candidatures avec suivi de statut
- Fil d'actualité (posts, likes, commentaires)
- Messagerie interne avec statut en ligne
- Réseau de contacts (demandes, acceptation, refus)
- Notifications + dashboards par rôle
- Espace admin (vérification entreprise, stats)

## Implemented (2026-02 — initial MVP)
- ✅ Landing page (hero, search, carte France SVG 13 régions, latest offers, top companies, candidates, CTA)
- ✅ Auth JWT (register, login, me, logout) + Emergent Google OAuth (/auth/session, AuthCallback)
- ✅ Profils entreprise + candidat avec édition inline
- ✅ Offres: CRUD, filtres (q, region, city, contract_type, domain, level, remote), stats par région
- ✅ Candidatures avec statuts (envoyée / vue / en attente / acceptée / refusée)
- ✅ Fil d'actualité avec catégories (annonce, recherche, conseil, général), likes, commentaires
- ✅ Messagerie polling 5s, conversations, statut non-lu
- ✅ Contacts: demande, accept, refuse, liste
- ✅ Notifications avec badge unread dans le header
- ✅ Dashboards entreprise & candidat avec stats
- ✅ Admin: stats globales, liste users, vérification entreprise
- ✅ Seed automatique: 1 admin, 10 entreprises, 12 candidats, 12 offres, 6 publications

## Iteration 2 (2026-02) — Espace Bons Plans + Monétisation Stripe
- ✅ Bons plans CRUD avec catégories (food, sport, culture, transport, study, fashion, tech)
- ✅ Étudiants: publication GRATUITE avec validation admin obligatoire (status=pending → published)
- ✅ Entreprises: publication réservée aux abonnés Pro Bons Plans (HTTP 402 sinon)
- ✅ Abonnement Pro Bons Plans: 1€/mois ou 10€/an via Stripe Checkout
- ✅ Boosts: 1€/7j étudiant (boosted_until) + 10€/7j entreprise (sponsored_until)
- ✅ Page /deals avec sections triées: Sponsorisés → Mis en avant → Tous
- ✅ Page /deals/mine: gestion publications + sauvegardés + historique boosts/factures
- ✅ Stripe Checkout sécurisé (packages côté backend, URLs dynamiques, polling status, webhook)
- ✅ Espace admin Monétisation: revenus totaux/par type, modération bons plans en attente, transactions
- ✅ Tracking: vues, clics (CTA tracking), sauvegardes, partages

## Backlog (P1/P2 — for next iterations)
### P1 — Important
- Upload de fichiers (CV, logos, photos) via stockage objet Emergent
- Demande de réinitialisation mot de passe + vérification email
- Bouton "Suivre une entreprise" (séparé des contacts)
- Sauvegarder une offre (liste perso)
- Modération de publications & système de signalement
- Recherche par distance (rayon autour d'une ville)
- Indexes Mongo + recherche full-text

### P2 — Avancé
- Messagerie temps réel (WebSocket)
- Matching IA candidat ↔ offre
- IA pour améliorer le CV / rédiger une offre
- Visio-entretien intégrée
- Agenda d'entretien
- Application mobile native
- Abonnements premium recruteur, mise en avant d'offres
- CVthèque avancée
- Rate limiting auth + protection brute-force
- Split server.py en routers par domaine

## Next Tasks
1. Intégration uploads de fichiers (CV, logo) — playbook object storage Emergent
2. Filtre distance/rayon sur la carte
3. Suivi d'entreprise + sauvegarde d'offres
4. Vérification email + mot de passe oublié
5. Modération admin (publications + signalements)
