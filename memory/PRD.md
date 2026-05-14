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

## Iteration 5 (2026-02) — Photos PC, Premium, Bug fixes, Indexes
- ✅ **Carte interactive France retirée** (remplacée par chips de régions avec compteurs d'offres)
- ✅ **Upload photo de profil** (`/api/me/avatar`) avec compression Pillow auto à 512×512 JPEG q85, formats acceptés JPG/PNG/WebP
- ✅ **Upload bannière** (`/api/me/banner`) compression à 1600×600 JPEG q82
- ✅ **Avatars/bannières servies publiquement** (sans token) pour permettre l'affichage dans `<img src>`
- ✅ **Suppression photo/bannière** via DELETE
- ✅ **Cascade rename entreprise** : `/api/profile-v2` met à jour `users.name` + propagate à `offers.company_name`, `applications.company_name`, `posts.author_name`, `comments.author_name`, `messages.from_name`/`to_name`
- ✅ **Sécurité** : whitelist des champs dans `/profile-v2` — impossible d'écrire `is_premium`, `verified`, etc. en dehors des endpoints admin
- ✅ **Featured candidates** : `/api/candidates/featured` — random + premium en priorité (50% des slots), badge "Premium" amber sur les cartes
- ✅ **Système premium étudiant** : `is_premium`, `premium_start_date`, `premium_end_date`, `premium_status`
- ✅ **Admin grant premium** : `POST /admin/grant-premium/{user_id}?days=N` + bouton dans /admin
- ✅ **Mongo indexes** : offers(city/region/source/status/contract_type/created_at/company_id), users(role/region/city/is_premium), applications(candidate/company/status), messages(conv+created/to+read), deals(status/author), notifications(user+created)
- ✅ **Vraie API France Travail** : OAuth2 client_credentials + endpoint `/partenaire/offresdemploi/v2/offres/search` (fallback simulation si `FRANCE_TRAVAIL_CLIENT_ID/SECRET` absents)
- ✅ **Tests** : 17/18 backend pass · 2 fixes critiques (privacy fichiers avatars + faille security profile-v2)

## Iteration 4 (2026-02) — Phase B : Distance, Temps réel WebSocket, Connecteurs externes
- ✅ **Géocodage** : table statique de 50+ villes françaises → coordonnées GPS, formule de Haversine
- ✅ **Recherche par rayon** : `/api/offers-nearby?city=Paris&distance_km=80` retourne les offres triées par distance, avec badge "km" sur chaque carte
- ✅ **Recherche étudiants par rayon** : `/api/search/students-nearby` (réservé entreprises)
- ✅ **Filtres frontend** : sélecteur ville + slider distance (10-300 km) sur /offers et /search/students
- ✅ **WebSocket** `/api/ws?token=...` : ConnectionManager avec broadcast, présence online/offline, événements typing
- ✅ **Messagerie temps réel** : nouveaux messages poussés instantanément (plus de polling 5s), indicateur "écrit..." avec timeout 3s, badge Live/Offline dans header
- ✅ **Présence en ligne** : pastille verte synchronisée en temps réel sur chaque contact (broadcast aux contacts à la (dé)connexion)
- ✅ **Endpoint /messages-rt** : nouveau POST qui push via WebSocket en plus d'insérer en DB (l'ancien /messages reste compatible)
- ✅ **Framework connecteurs externes** : classe `ExternalConnector` extensible, implémentations stub `HelloWorkConnector` + `FranceTravailConnector` (status `simulation_only` tant que pas de contrat partenaire)
- ✅ **Admin** : `/api/admin/refresh-external?source=HelloWork` pour fetch + persistance idempotente · `/api/admin/external-connectors` pour lister
- ✅ Structure prête à recevoir de vraies API (il suffit d'implémenter `fetch()` avec une vraie URL)

## Iteration 3 (2026-02) — Multi-source + Massive seed + Profils enrichis + Apps détaillées
- ✅ Seed massif : 110 entreprises fictives + 320 offres (mix interne StageConnect + 12 sources externes : HelloWork, LinkedIn, Indeed, Welcome to the Jungle, France Travail, JobTeaser, StudentJob, L'Étudiant, Apec, Meteojob, Monster, Talent.com)
- ✅ Badges rouges visibles sur chaque offre indiquant l'origine
- ✅ Offres externes redirigent vers le site source (cible _blank)
- ✅ Filtre source côté backend (`/api/offers?source=...`) + dropdown frontend
- ✅ Carte de France : version mobile avec toggle Liste/Carte/Filtres
- ✅ Page "Rechercher un étudiant" (entreprises) avec filtres nom/niveau/domaine/ville/compétence/statut
- ✅ Page détail candidature (`/applications/:id`) avec téléchargement CV/lettre/convention, note interne, statuts étendus (vue / en_analyse / entretien_propose / acceptée / refusée / archivée), retrait par étudiant
- ✅ Documents étudiants multiples (CV, lettre, convention, portfolio) avec visibilité (privé / connectés / après_candidature / public)
- ✅ Galerie photos entreprise avec upload via stockage objet Emergent
- ✅ Upload de fichiers réel via Emergent Object Storage (`/api/upload`, `/api/files/:id`)
- ✅ Privacy: téléchargement de fichiers contrôlé par règles de visibilité côté serveur
- ✅ Offres sauvegardées (`/saved-offers`) + toggle bouton
- ✅ Statuts enrichis : étudiant (en_recherche/à_l_écoute/déjà_trouvé/non_disponible) + entreprise (recrute_stagiaire/recrute_alternant/recrute_les_deux/pas_de_recrutement)
- ✅ Contact lifecycle complet : status none→sent→connected→removed→blocked, annulation invitation, suppression contact, blocage
- ✅ Bouton dynamique sur profil selon contact_status
- ✅ Tests : 66/66 backend pass + 2 fixes critiques appliqués (privacy fichiers + ownership upload + idempotence block)

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
