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

## Iteration 20 (2026-02-28) — Phase R : Recherche fine + Split server.py (Phase 2)
- ✅ **Recherche étudiant flexible** : `/api/search/students` `q` cherche désormais dans `name`, `profile.first_name`, `profile.last_name` (l'entreprise peut taper le prénom ou le nom seul).
- ✅ **Recherche d'offres par entreprise précise** : la saisie « Entreprise précise » sur OffersPage déclenche désormais aussi un appel à `/api/francetravail/search?q=<nom>` (avec post-filtre client côté nom d'entreprise, accents-insensible). Permet par exemple de trouver les offres « Sofratom » au-delà des sources internes. `/api/offers` `q` cherche aussi dans `company_name`.
- ✅ **Split server.py — Phase 2** : extraction de quatre nouveaux routers `routes/auth.py` (151 l), `routes/users.py` (65 l), `routes/offers.py` (222 l), `routes/admin.py` (63 l). Pattern `register_xxx_routes(api, db, get_current_user, …)` réutilisé. `_enrich_offers_with_premium` exposé par `register_offers_routes.enrich` pour rester accessible depuis `/offers-nearby` (toujours dans server.py). **Bilan** : `server.py` passe de **3899 → 3542 lignes** (-9 %). Tests régression 15/15 passés (`/app/test_reports/iteration_20.json`).


## Iteration 19 (2026-02-28) — Phase Q : Premium, Filtres explicites, Profil officiel, À propos & Géocoding élargi
- ✅ **PremiumBadge** réutilisable (`/app/frontend/src/components/PremiumBadge.jsx`) avec helper `isPremiumActive` (vérifie `is_premium`, `premium_status='active'`, `premium_end_date` non expirée). Badges affichés sur : `OfferCard`, `SearchStudentsPage`, `ContactsPage`, `MessagesPage` (liste + en-tête conversation), `ProfilePage`, `ApplicationDetailPage`. Tri prioritaire premium-first dans `/api/offers` et `/api/offers-nearby` (helper backend `_enrich_offers_with_premium` qui joint les offres aux utilisateurs `company` premium actifs).
- ✅ **Bouton "Rechercher" explicite** sur `OffersPage` (data-testid=`apply-filters-btn`) + `SearchStudentsPage` (`apply-students-btn`) : draft state interne, l'envoi de la requête API n'a lieu QUE sur clic. Inclut bouton Réinitialiser, état de chargement, message d'aide « Sélectionnez vos critères puis cliquez sur Rechercher », compteur de résultats live (`results-count`).
- ✅ **Profil officiel StageEtudiant.com** : page admin `/admin/official-profile` avec preview live (bannière, avatar, slogan, badge "Compte officiel" bleu), formulaire (nom, slogan, description, URLs photo/bannière, couleur principale, site web, email contact, visibilité). `GET /api/official-profile` public, `PATCH /api/admin/official-profile` gardé admin. Noms réservés au register (`StageEtudiant.com`, `stage etudiant`, `stageetudiant`, `admin`, `support`, `moderation`) → HTTP 400.
- ✅ **Page publique `/a-propos`** (et alias `/about`) : hero, sections "Pour les étudiants/entreprises/CFA", "Notre objectif", "Pourquoi utiliser StageEtudiant.com ?", CTA buttons → /register et /offers. Mode clair/sombre compatible. Liens "À propos" ajoutés au header (anonyme + menu utilisateur) et au footer du LandingPage.
- ✅ **Géocoding élargi** : `get_coords_async()` côté backend → 1) `CITY_COORDS` legacy, 2) `FR_CITIES` (`geo_search`), 3) fallback Nominatim/OSM (User-Agent propre, cache Mongo 30 j, logs `geocoding_api_logs`). `/api/offers-nearby` et `/api/search/students-nearby` utilisent désormais ce fallback : les villes hors FR_CITIES (ex: Saumur, Sablé-sur-Sarthe) sont géocodées automatiquement. Si introuvable → message clair « Ville introuvable, vérifiez l'orthographe ou élargissez la recherche. »
- ✅ Tests Iteration 19 : 12/12 backend pytest (`/app/backend/tests/test_iter19_phaseI.py`) + flux frontend complet validé par testing agent (100 % succès).


## Iteration 8 (2026-02) — Phase B : Annuaire d'Entreprises officiel
- ✅ **API Recherche d'Entreprises (gouv.fr)** : publique, sans clé, intégrée via `/app/backend/external_companies.py` (normalize + cache)
- ✅ **Endpoints** : `GET /api/companies/search?q&code_postal&departement&region&activite_principale&page&per_page` (400 si pas de critère) ; `GET /api/companies/siret/{siret}` (404 si inconnu)
- ✅ **Cache MongoDB** : `external_company_search_cache` (TTL 7j) + `external_company_details_cache` (TTL 30j) avec `cache_hit` flag
- ✅ **Logs** : `api_request_logs` + `api_error_logs`
- ✅ **Admin** : `GET/DELETE /api/admin/external-cache` (lister/purger), `POST /api/admin/external-cache/refresh` (force-refresh)
- ✅ **Champs profil** : `siren`, `postal_code`, `naf_code`, `siret_verified`, `siret_verified_at` ajoutés à `/profile-v2` (COMPANY_FIELDS)
- ✅ **Page `/companies`** : recherche par nom/CP/dpt/région/NAF avec pagination + badge "Cache"
- ✅ **Composant `SiretLookup`** : autocomplete dans `/register` (mode entreprise) + modale d'édition profil entreprise → préremplit nom/SIRET/ville/CP/région/adresse/NAF
- ✅ **Header** : lien "Entreprises" → /companies
- ✅ **Bug fix** : nested `<form>` dans SiretLookup (HIGH) — remplacé par `<div>` + `type=button` + `onKeyDown Enter`
- ✅ Tests : 17/17 backend pass · `/companies` 100% · Register entreprise: 8 picks + préremplissage validé manuellement


- ✅ **Mode clair/sombre/auto** : `ThemeContext` + tokens CSS `:root` / `.dark` (bleu nuit pro), overrides Tailwind hardcodés, bouton bascule Header (`theme-toggle`), sélecteur 3 options Settings
- ✅ **Persistance thème** : localStorage anonyme + `user.theme_preference` via `PATCH /api/me/theme` (light|dark|system)
- ✅ **Profile views** : `profile_views` collection + log fire-and-forget dans `GET /users/{id}` (dédup 30 min)
- ✅ **API vues** : `/api/me/profile-views/stats` (public — total/7j/30j/distinct) + `/api/me/profile-views` (détails, 402 Free → CTA Premium)
- ✅ **Composant `ProfileViews`** sur dashboards candidat+entreprise
- ✅ **Compteur "stages obtenus"** : statuts `internship_obtained`, `apprenticeship_obtained`, `contract_signed` ajoutés à `PATCH /applications/{id}/status`
- ✅ **`/api/stats/platform`** public + `/api/admin/platform-stats` (GET/PUT) avec mode marketing override `use_manual_count` + message custom + show_counter on/off
- ✅ **`PlatformCounter`** affiché Landing + Dashboards (compact)
- ✅ **Admin** : bloc `admin-platform-stats` avec inputs Show/Manual/Displayed/Message + save
- ✅ Tests : 14/14 backend pass + 18/18 frontend pass


- ✅ **CV en ligne CRUD** : `/api/cv` (GET/PUT) + `/api/users/{id}/cv` (lecture publique selon visibilité public/connected/after_application/private)
- ✅ **5 modèles PDF distincts** : Moderne (bleu, 1 col), Classique (Times serif centré + divider), Étudiant (bannière colorée + chips), Alternance (violet 2 colonnes), Professionnel (sidebar sombre)
- ✅ **Modèle par défaut** : `pdf_template` sauvegardé dans le profil CV + sélecteur à l'export (CVPage, modale de candidature, ApplicationDetailPage)
- ✅ **Robustesse PDF** : `_norm_skills()` accepte skills sous forme str OU dict {name,level} — pas de 500 sur PDF
- ✅ **IA CV (Emergent LLM)** : `/api/cv/ai/{improve,rephrase,correct,summary,skills,cover_letter,adapt}`
- ✅ **Candidature enrichie** : POST `/applications` accepte `use_online_cv`, `online_cv_template`, `uploaded_doc_ids` ; stocke `online_cv_snapshot` figé + `selected_documents`
- ✅ **Vue entreprise** : `/applications/{id}/cv` et `/applications/{id}/cv/export` (PDF) — accessible candidat + entreprise propriétaire + admin, 403 sinon
- ✅ **Frontend** : ApplicationDetailPage affiche un bloc "CV en ligne du candidat" avec preview HTML + bouton "Télécharger PDF" + lien "Plein écran" (/cv/{id})
- ✅ **Modale candidature** : checkbox CV en ligne + sélecteur modèle + cases à cocher pour les documents uploadés (CV, lettre, convention, etc.) + lettre de motivation
- ✅ **ProfilePage** : bouton "Mon CV en ligne" (owner) / "Voir le CV en ligne" (visiteur si CV accessible)
- ✅ **Header** : entrée "Mon CV en ligne" dans le menu utilisateur candidate
- ✅ Tests backend : 21/22 pass (1 skipped par manque de fixture, pas un bug code)


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

## Iteration 18 (2026-02) — Recherche d'offres v2 + Owner admin
- ✅ **Nouveau module `/app/backend/geo_search.py`** : normalize_text (accent-insensitive), companies_match (strict + word-boundary), haversine_km, geocode_french_city (~125 villes), EU_COUNTRIES + COUNTRY_ALIASES (FR↔EN↔ISO), countries_match
- ✅ **`/api/offers` refondu** : 6 nouveaux params (`company`, `country`, `european_only`, `radius_km`, et city/source existants) — filtres stricts appliqués post-DB
- ✅ **`/api/external-offers/all` aligné** : mêmes filtres pour offres externes (Adzuna, Ashby, Arbeitnow, etc.)
- ✅ **France par défaut** : sans `european_only` ni `country`, on n'affiche que les offres FR (ou sans country, traitées comme FR)
- ✅ **Catégorie "Pays européens"** : checkbox + dropdown 12 pays principaux (Belgique/Suisse/Luxembourg/Allemagne/Espagne/Italie/UK/Pays-Bas/Portugal/Irlande/Autriche/Pologne)
- ✅ **Badge pays** sur OfferCard pour les offres non-FR + affichage distance `_distance_km` en mode rayon
- ✅ **Owner admin auto-seedé** : `bernardolivieri1326@gmail.com` / `OwnerAdmin2026!` (idempotent via `ensure_owner_admin`)
- ✅ **Redirect /admin automatique** après login pour role=admin (et notamment l'owner)
- ✅ **Bouton "Admin" dans le header** visible uniquement pour role=admin (data-testid=nav-admin)
- 📊 **Tests** : 14/14 backend + tous flows frontend critiques (iter 18)


- ✅ **5 nouveaux splits** : `routes/contacts.py` (159), `routes/notifications.py` (21), `routes/deals.py` (227), `routes/moderation.py` (178), `routes/applications.py` (106)
- ✅ **Modèles centralisés** : `ContactRequestIn`, `DealIn`, `ApplicationIn` ajoutés à `/app/backend/models.py`

## Iteration 17 (2026-02) — Split de server.py (suite) + Modération du fil social
- ✅ 5 nouveaux splits : routes/contacts.py (159), routes/notifications.py (21), routes/deals.py (227), routes/moderation.py (178), routes/applications.py (106)
- ✅ Modèles centralisés (ContactRequestIn, DealIn, ApplicationIn) dans `/app/backend/models.py`
- ✅ 8 routers actifs : ads + posts + messages + contacts + notifications + deals + moderation + applications = 1231 lignes externalisées
- ✅ Signalements posts/comments (P2) avec 8 raisons, anti-doublon, refuse self-report
- ✅ Queue admin /admin/reports + actions (Conserver/Supprimer/Archiver)
- 📊 server.py 3967 → 3574 (-393)

- ✅ **8 routers actifs** : ads + posts + messages + contacts + notifications + deals + moderation + applications = 1231 lignes externalisées
- ✅ **Signalements posts/comments (P2)** : `POST /api/reports` (8 raisons, anti-doublon, refuse self-report), `GET /api/reports/mine`
- ✅ **Queue admin** : `GET /api/admin/reports` (snapshot+compteurs), `POST /admin/reports/{id}/dismiss|remove`, notif auteur si supprimé
- ✅ **Frontend** : menu "..." Signaler sur PostCard, Flag hover sur commentaires, page `/admin/reports` (4 onglets) + menu Header admin
- 📊 **Résultat** : server.py 3967 → **3574 lignes (-393)**. Tests : 22/22 nouveaux + 35/35 régression.

## Iteration 16 (2026-02) — Refactor : split de server.py + modèles partagés
- ✅ Modèles Pydantic centralisés dans `/app/backend/models.py`
- ✅ Posts extraits vers `routes/posts.py` (156 lignes), Messages vers `routes/messages.py` (86 lignes)
- ✅ Routers séparés par domaine : `ads_router`, `posts_router`, `messages_router`
- 📊 server.py 4197 → 3967 (-230). 29/29 nouveaux + 36/36 régression.
- ✅ **Modèles Pydantic centralisés** dans `/app/backend/models.py` (PostIn, PostMedia, LinkPreview, CommentIn, MessageIn, MessageAttachment) — fini la duplication
- ✅ **Posts** extraits vers `/app/backend/routes/posts.py` (156 lignes — create, list, like, comment, comments, link-preview avec cache)
- ✅ **Messages** extraits vers `/app/backend/routes/messages.py` (86 lignes — send, conversations, get)
- ✅ **Routers séparés par domaine** : `ads_router`, `posts_router`, `messages_router` (chacun avec son APIRouter et son include_router) au lieu d'un fourre-tout `ads_api`
- ✅ **Pattern** : `register_*_routes(api_router, db, get_current_user, notify, **deps)` éprouvé et appliqué de manière homogène
- 📊 **Résultat** : `server.py` passe de 4197 → 3967 lignes (-230). Aucune régression : 29/29 nouveaux tests pytest + 36/36 régressions précédentes (iter14/15) passent.


## Iteration 15 (2026-02) — Phase I + J + Étape 2 (drag-drop) + Rate-limit
- ✅ **Phase I — Médias riches fil social** :
  - Upload élargi : `mp4`/`webm`/`mov` (vidéos jusqu'à 50 Mo), `pdf` (15 Mo), `docx`/`xlsx`/`pptx`, images 8 Mo
  - `POST /api/posts` accepte `media: [{type, url, file_id, filename, mime, size}]` + `link_preview: {url, title, description, image, domain}`
  - `POST /api/posts/link-preview` → extraction Open Graph (avec cache 7j dans `link_preview_cache`, fetch en `asyncio.to_thread`)
  - `GET /api/files/{id}` rendu public pour `kind ∈ (avatar, banner, post, ad, deal, feed)`
  - FeedPage : composer avec 3 boutons upload (image/vidéo/PDF), détection automatique des URLs collées avec aperçu, rendu de vidéos `<video controls>` et PDFs cliquables
- ✅ **Phase J — Pièces jointes messagerie** :
  - `MessageIn.attachments: List[MessageAttachment]` (compat avec champ `attachment` legacy)
  - WebSocket push inchangé (transmet `attachments[]`)
  - MessagesPage : icône trombone (paperclip) ouvre le file picker, prévisualisation des pendingAttachments avec X, rendu en bulle ("MessageAttachmentView") : image/vidéo/PDF
- ✅ **Étape 2 — Éditeur drag-and-drop des publicités** :
  - `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` installés
  - Nouveau composant `AdBuilder` : palette gauche (7 types : heading/text/image/logo/button/promo_code/link), canvas central trié, propriétés à droite (contenu/taille/alignement/couleur/URL)
  - Toggle `Mode simple / Composer` dans `/ads/new`
  - `RenderBlocks` rendu côté preview + dans `SponsoredAdPreview` (fallback layout simple si pas de blocks)
- ✅ **Rate-limit IP** : collection `ad_tracking_dedup` + TTL index 1h sur `expires_at` → un même couple (ad_id, action, IP) n'est compté qu'une fois par heure
- ✅ **Améliorations** : index Mongo ajoutés (ad_tracking_dedup, link_preview_cache, ads.status/company_id), gestion `onError` sur images broken dans link previews
- ✅ **Tests** : 14/14 backend pytest (`test_iter15_media_attachments.py`), 5/5 frontend critique (iteration_15.json)

- ✅ **Workflow deals refondu** : tous les bons plans (entreprise + étudiant) passent automatiquement en `status="pending"` à la création. Nouveau statut `suspended` ajouté. L'édition d'un deal validé/refusé/suspendu par l'auteur le repasse en `pending` (re-validation).
- ✅ **Endpoints admin deals** : `GET /api/admin/deals?status=...&q=...` (avec compteurs par statut), `POST /api/admin/deals/{id}/validate` actions `approve|refuse|suspend|reactivate|expire` + raison de modération + notification.
- ✅ **Nouvelle entité `ads`** (collection Mongo `ads`) : `/app/backend/ads_routes.py` — CRUD complet (`POST /api/ads`, `GET /api/ads/mine`, `GET /api/ads/public`, `PATCH/DELETE /api/ads/{id}`) + tracking views/clicks anonymes.
- ✅ **Quota** : gratuit = 1 publicité active (pending+published+suspended), Pro = 9999 (illimité). Brouillons exclus du quota. Re-vérification du quota sur draft→submit.
- ✅ **Admin ads** : `GET /api/admin/ads` (compteurs + stats agrégées: total_views, total_clicks, ctr cappé à 100%), `POST /api/admin/ads/{id}/validate`.
- ✅ **Pages frontend** : `/admin/deals` (modération deals, 7 onglets statut), `/admin/ads` (modération + 4 stat tiles), `/ads/new` (éditeur avec 4 templates pro, 3 color pickers, 3 alignements, **aperçu desktop/mobile**), `/ads/mine` (liste + bannière quota), `/ads/:id/edit` (re-édition → re-validation).
- ✅ **Intégration** : section "Publicités sponsorisées" dans `/deals` avec carte cliquable (tracking auto views+clicks), badge "Sponsorisé" et liens vers le CTA externe. Header → menus admin/company dédiés.
- ✅ **Tests** : 22/22 backend pytest pass (`test_iter14_deals_ads.py`), 5/5 frontend critique pass (iteration_14.json).

## Iteration 13 (2026-02) — Phase H : APIs externes avec clés
- ✅ **Adzuna FR** : `/app/backend/external_keyed.py::fetch_adzuna()` → 100 offres réelles par refresh (cache 12h)
- ⚠️ **Jooble** : implémenté, mais clé retourne HTTP 403 upstream (à activer côté Jooble) — retiré du dropdown frontend
- ⚠️ **EURES via Apify** : implémenté, mais actor Apify EURES est payant (HTTP 403 "rent a paid Actor")
- ✅ **Endpoints** : `GET /api/external-offers/keyed`, `GET /api/external-offers/all` (merge keyless+keyed dédupliqué)
- ✅ **Admin Sources API** : carte `admin-sources-api` dans `/admin` avec table 11 sources + boutons refresh/purge

## Next Tasks
1. ✅ ~~Phase I — Médias riches fil social~~ (DONE iter 15)
2. ✅ ~~Phase J — Pièces jointes messagerie~~ (DONE iter 15)
3. ✅ ~~Éditeur drag-and-drop ads~~ (DONE iter 15)
4. ✅ ~~Rate-limit IP tracking ads~~ (DONE iter 15)
5. **Split server.py** en routers par domaine (auth/users/offers/admin) — P2 (gros refactor, ~4200 lignes)
6. **Modération admin** : signalement de publications + comments + threads — P2
7. **Activation Jooble** : contacter le support Jooble pour valider la clé (HTTP 403 actuellement) — P3
8. **Location actor Apify EURES** (~$30/mois) ou scraper EURES maison — P3
9. **Hardening** : magic-byte sniffing sur upload, streaming pour gros fichiers, Pydantic stricter validation pour ads (`min_length`, `HttpUrl`) — P3
