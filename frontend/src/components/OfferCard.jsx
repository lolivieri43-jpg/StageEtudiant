import React from "react";
import { Link } from "react-router-dom";
import { MapPin, Clock, Briefcase, CheckCircle2, Wifi, ExternalLink } from "lucide-react";
import { Badge } from "./ui/badge";

const SOURCE_LABELS = {
  StageConnect: "StageEtudiant",
  StageEtudiant: "StageEtudiant",
  HelloWork: "HelloWork",
  LinkedIn: "LinkedIn",
  Indeed: "Indeed",
  WelcomeToTheJungle: "WTTJ",
  FranceTravail: "France Travail",
  JobTeaser: "JobTeaser",
  StudentJob: "StudentJob",
  LEtudiant: "L'Étudiant",
  Apec: "Apec",
  Meteojob: "Meteojob",
  Monster: "Monster",
  TalentCom: "Talent.com",
  "La Bonne Alternance": "LBA",
  Ashby: "Ashby",
  Arbeitnow: "Arbeitnow",
  Remotive: "Remotive",
  RemoteOK: "RemoteOK",
  Jobicy: "Jobicy",
  Greenhouse: "Greenhouse",
  Adzuna: "Adzuna",
  Jooble: "Jooble",
  EURES: "EURES",
};

export default function OfferCard({ offer }) {
  const isExternalUrl = offer.source && offer.source !== "StageConnect" && (offer.external_url || offer.apply_url);
  const externalHref = offer.external_url || offer.apply_url;
  const sourceLabel = SOURCE_LABELS[offer.source] || offer.source || "StageEtudiant";
  const inner = (
    <>
      <div className="absolute top-3 right-3 bg-red-500 text-white text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded-full shadow-sm" data-testid={`source-badge-${offer.offer_id}`} title={`Source: ${sourceLabel}`}>
        Origine : {sourceLabel}
      </div>
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-slate-100 overflow-hidden shrink-0 grid place-items-center text-slate-400 font-bold">
          {offer.company_logo ? <img src={offer.company_logo} className="w-full h-full object-cover" alt="" /> : offer.company_name?.[0]}
        </div>
        <div className="flex-1 min-w-0 pr-20">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-slate-700 truncate">{offer.company_name}</span>
            {offer.verified && <CheckCircle2 className="w-4 h-4 text-blue-500 shrink-0" />}
          </div>
          <h3 className="font-bold text-slate-900 leading-snug mb-2 truncate">{offer.title}</h3>
          <div className="flex flex-wrap gap-1.5 text-xs">
            <Badge variant="secondary" className="rounded-full bg-blue-50 text-blue-700 border-0">
              <Briefcase className="w-3 h-3 mr-1" />{offer.contract_type === "stage" ? "Stage" : "Alternance"}
            </Badge>
            <Badge variant="secondary" className="rounded-full bg-violet-50 text-violet-700 border-0">
              <MapPin className="w-3 h-3 mr-1" />{offer.city}
            </Badge>
            <Badge variant="secondary" className="rounded-full bg-slate-100 text-slate-700 border-0">
              <Clock className="w-3 h-3 mr-1" />{offer.duration}
            </Badge>
            {offer.remote && (
              <Badge variant="secondary" className="rounded-full bg-emerald-50 text-emerald-700 border-0">
                <Wifi className="w-3 h-3 mr-1" />Télétravail
              </Badge>
            )}
            {offer.distance_km !== undefined && (
              <Badge variant="secondary" className="rounded-full bg-amber-50 text-amber-700 border-0">
                {offer.distance_km} km
              </Badge>
            )}
          </div>
        </div>
      </div>
      {isExternalUrl && (
        <div className="mt-3 text-xs text-red-600 font-semibold flex items-center gap-1">
          <ExternalLink className="w-3 h-3" />Ouvrir sur {sourceLabel}
        </div>
      )}
    </>
  );

  if (isExternalUrl) {
    return (
      <a href={externalHref} target="_blank" rel="noopener noreferrer" className="card-soft p-5 block hover-lift hover:border-red-300 relative" data-testid={`offer-card-${offer.offer_id}`}>
        {inner}
      </a>
    );
  }
  return (
    <Link to={`/offers/${offer.offer_id}`} data-testid={`offer-card-${offer.offer_id}`} className="card-soft p-5 block hover-lift hover:border-blue-300 relative">
      {inner}
    </Link>
  );
}
