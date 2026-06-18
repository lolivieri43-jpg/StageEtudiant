import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import {
  GraduationCap, Briefcase, Building2, MessageSquare, Search,
  Sparkles, MapPin, FileText, Heart, Globe2, Shield, Users,
  ArrowRight, Mail,
} from "lucide-react";
import { Button } from "../components/ui/button";
import PremiumBadge from "../components/PremiumBadge";

const Section = ({ title, children, icon: Icon, accent = "blue" }) => (
  <section className={`card-soft p-7 mb-6`} data-testid={`about-section-${title.toLowerCase().replace(/\s|'/g, "-")}`}>
    <div className="flex items-center gap-3 mb-4">
      {Icon && (
        <div className={`w-11 h-11 rounded-xl bg-${accent}-100 text-${accent}-700 grid place-items-center`}>
          <Icon className="w-5 h-5" />
        </div>
      )}
      <h2 className="text-xl font-black tracking-tight text-slate-900 dark:text-slate-100">{title}</h2>
    </div>
    {children}
  </section>
);

const Item = ({ children }) => (
  <li className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
    <span className="mt-1.5 inline-block w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
    <span>{children}</span>
  </li>
);

export default function AboutPage() {
  const [official, setOfficial] = useState(null);

  useEffect(() => {
    api.get("/official-profile").then((r) => setOfficial(r.data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen pt-20 pb-16 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        {/* Hero */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 via-blue-700 to-violet-700 text-white p-8 sm:p-12 mb-8" data-testid="about-hero">
          <div className="absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_20%_20%,white,transparent_40%)]" />
          <div className="relative">
            <div className="flex items-center gap-3 mb-3">
              <PremiumBadge role="official" size="md" />
              <span className="text-xs uppercase tracking-widest text-blue-100">À propos</span>
            </div>
            <h1 className="text-3xl sm:text-5xl font-black tracking-tight mb-3">
              À propos de {official?.display_name || "StageEtudiant.com"}
            </h1>
            <p className="text-blue-100 text-base sm:text-lg max-w-2xl">
              {official?.description ||
                "La plateforme française qui connecte étudiants, alternants, entreprises, CFA et lycées professionnels pour trouver, gérer et réussir leurs stages et alternances."}
            </p>
            {official?.slogan && (
              <p className="mt-3 text-blue-200 italic">« {official.slogan} »</p>
            )}
          </div>
        </div>

        {/* Objectif */}
        <Section title="Notre objectif" icon={Sparkles} accent="violet">
          <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
            StageEtudiant.com a pour objectif de <strong>simplifier la recherche de stage et d&apos;alternance</strong> en
            centralisant les offres, les profils, les entreprises, les candidatures, les bons plans étudiants et les outils
            de mise en relation — le tout dans une expérience claire, moderne et pensée pour l&apos;écosystème français.
          </p>
        </Section>

        {/* Étudiants */}
        <Section title="Pour les étudiants" icon={GraduationCap} accent="emerald">
          <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
            <Item>Créer un profil professionnel</Item>
            <Item>Créer un CV en ligne façon LinkedIn</Item>
            <Item>Ajouter un CV PDF, une lettre de motivation, une convention de stage</Item>
            <Item>Rechercher des offres de stage et d&apos;alternance</Item>
            <Item>Rechercher des entreprises à contacter</Item>
            <Item>Suivre ses candidatures, sauvegarder ses offres</Item>
            <Item>Échanger via la messagerie intégrée</Item>
            <Item>Utiliser la recherche IA en langage naturel</Item>
            <Item>Consulter les bons plans étudiants</Item>
            <Item>Être mis en avant avec un profil Premium</Item>
          </ul>
        </Section>

        {/* Entreprises */}
        <Section title="Pour les entreprises" icon={Briefcase} accent="blue">
          <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
            <Item>Créer une page entreprise complète</Item>
            <Item>Publier des offres et recevoir des candidatures</Item>
            <Item>Rechercher des étudiants et consulter les profils</Item>
            <Item>Échanger par messagerie temps réel</Item>
            <Item>Gérer les candidatures et leurs statuts</Item>
            <Item>Ajouter photos, vidéos et personnaliser sa page</Item>
            <Item>Publier des bons plans pour les étudiants</Item>
            <Item>Créer des publicités dans l&apos;espace Bons Plans</Item>
          </ul>
        </Section>

        {/* CFA / Écoles */}
        <Section title="Pour les CFA, lycées professionnels & centres de formation" icon={Building2} accent="amber">
          <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
            <Item>Aider les jeunes à trouver une entreprise d&apos;accueil</Item>
            <Item>Orienter vers des offres locales et qualifiées</Item>
            <Item>Utiliser la plateforme comme outil de suivi</Item>
            <Item>Valoriser les profils des étudiants</Item>
          </ul>
        </Section>

        {/* Pourquoi StageEtudiant */}
        <Section title="Pourquoi utiliser StageEtudiant.com ?" icon={Heart} accent="rose">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[
              { icon: MapPin, label: "Recherche locale & carte interactive" },
              { icon: Globe2, label: "Offres internes + agrégation multi-sources" },
              { icon: Users, label: "Profils complets pour candidats & entreprises" },
              { icon: MessageSquare, label: "Messagerie temps réel" },
              { icon: FileText, label: "Candidatures suivies, statuts clairs" },
              { icon: Sparkles, label: "Recherche IA en langage naturel" },
              { icon: Shield, label: "Modération et bons plans validés" },
              { icon: Search, label: "Filtres précis : ville, rayon, secteur, niveau" },
              { icon: Heart, label: "Gratuit pour les étudiants sur l'essentiel" },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-start gap-2 rounded-xl bg-slate-50 dark:bg-slate-800 p-3">
                <div className="w-8 h-8 rounded-lg bg-white dark:bg-slate-700 grid place-items-center text-blue-600 shrink-0">
                  <Icon className="w-4 h-4" />
                </div>
                <span className="text-sm text-slate-700 dark:text-slate-300">{label}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Contact section */}
        <Section title="Nous contacter" icon={Mail} accent="violet">
          <p className="text-slate-700 dark:text-slate-300 mb-4">
            Une question, un retour, un partenariat ? Notre équipe vous répond rapidement.
          </p>
          <a
            href="mailto:contact@stageetudiant.com"
            className="inline-flex items-center gap-2 rounded-full bg-violet-600 hover:bg-violet-700 text-white font-semibold px-5 h-11 transition"
            data-testid="about-contact-mailto"
          >
            <Mail className="w-4 h-4" />contact@stageetudiant.com
          </a>
        </Section>

        {/* CTA */}
        <div className="rounded-3xl bg-gradient-to-br from-blue-600 to-violet-700 text-white p-8 sm:p-10 text-center" data-testid="about-cta">
          <h3 className="text-2xl sm:text-3xl font-black mb-2">Prêt à commencer ?</h3>
          <p className="text-blue-100 mb-6">Crée ton compte ou lance ta recherche en quelques secondes.</p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link to="/register?role=candidate"><Button className="rounded-full bg-white text-blue-700 hover:bg-blue-50 h-11 px-5" data-testid="about-cta-candidate">Créer un compte étudiant</Button></Link>
            <Link to="/register?role=company"><Button variant="outline" className="rounded-full border-white text-white hover:bg-white hover:text-blue-700 bg-transparent h-11 px-5" data-testid="about-cta-company">Créer un compte entreprise</Button></Link>
            <Link to="/offers"><Button variant="outline" className="rounded-full border-white text-white hover:bg-white hover:text-blue-700 bg-transparent h-11 px-5" data-testid="about-cta-search">Rechercher une offre <ArrowRight className="w-4 h-4 ml-1" /></Button></Link>
            <Link to="/companies"><Button variant="outline" className="rounded-full border-white text-white hover:bg-white hover:text-blue-700 bg-transparent h-11 px-5" data-testid="about-cta-companies">Trouver une entreprise</Button></Link>
          </div>
        </div>

        <p className="text-center text-xs text-slate-500 dark:text-slate-400 mt-8">
          © 2026 StageEtudiant.com — Plateforme française du stage et de l&apos;alternance.
        </p>
      </div>
    </div>
  );
}
